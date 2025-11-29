from qfluentwidgets import FluentIcon
import time
import cv2
import random
import win32api

from ok import Logger, TaskDisabledException
from src.tasks.BaseDNATask import BaseDNATask
from src.tasks.DNAOneTimeTask import DNAOneTimeTask

logger = Logger.get_logger(__name__)


class AutoFishTask(DNAOneTimeTask, BaseDNATask):
    """AutoFishTask
    No-Idle Auto Fishing
    """
    BAR_MIN_AREA = 1200
    ICON_MIN_AREA = 70
    ICON_MAX_AREA = 400
    CONTROL_ZONE_RATIO = 0.25

    def __init__(self, *args, **kwargs):
        logger.info("AutoFishTask initializing...")
        super().__init__(*args, **kwargs)
        self.name = "Auto Fishing"
        self.description = "No-Idle Auto Fishing (Original Author: Bilibili Invincible Big Melon)"
        self.group_name = "Full Auto"
        self.group_icon = FluentIcon.CAFE

        # Default config (will be covered by configs/AutoFishTask.json)
        self.default_config.update({
            "MAX_ROUNDS": 100,
            "END_WAIT_SPACE": 1.0,
            "MAX_START_SEC": 20.0,
            "MAX_FIGHT_SEC": 60.0,
            "MAX_END_SEC": 20.0,
            "Play Sound Notification": True,
            "Jitter Mode": "Disabled",
            "External Movement Min Delay": 4.0,
            "External Movement Max Delay": 8.0,
            "External Movement Jitter Amount": 20,
        })

        # ROI Config (Fish bar and icon search area, based on 1920x1080)
        self.roi_fish_bar_and_icon = [1620, 325, 1645, 725]

        # Config Description (for GUI display)
        self.config_description.update({
            "MAX_ROUNDS": "Max Rounds",
            "END_WAIT_SPACE": "Wait time after round (s)",
            "MAX_START_SEC": "Start phase timeout (s)",
            "MAX_FIGHT_SEC": "Fishing phase timeout (s)",
            "MAX_END_SEC": "End phase timeout (s)",
            "Play Sound Notification": "Play sound on completion",
            "Jitter Mode": "Control when mouse jitter happens (Disabled, Always, Combat Only)",
            "External Movement Min Delay": "Minimum interval for random mouse movement (seconds)",
            "External Movement Max Delay": "Maximum interval for random mouse movement (seconds)",
            "External Movement Jitter Amount": "Maximum pixel distance to move mouse (default: 20)",
        })

        # runtime
        self.stats = {
            "rounds_completed": 0,
            "total_time": 0.0,
            "start_time": None,
            "current_phase": "Preparing",
            "chance_used": 0,  # Chance used count
        }
        try:
            self.external_movement_tick = self.create_external_movement_ticker()
        except Exception as e:
            logger.error(f"Failed to create external movement ticker: {e}")
            self.external_movement_tick = lambda: None

    def run(self):
        DNAOneTimeTask.run(self)
        if self.config.get("Jitter Mode", "Disabled") != "Disabled":
            self.log_info("External movement enabled: Forcing game window focus...")
            try:
                self.try_bring_to_front()
            except Exception as e:
                self.log_error(f"Failed to focus window: {e}")
        try:
            return self.do_run()
        except TaskDisabledException:
            pass
        except Exception as e:
            logger.error("AutoFishTask error", e)
            raise

    def init(self):
        self.stats = {
            "rounds_completed": 0,
            "total_time": 0.0,
            "start_time": None,
            "current_phase": "Preparing",
            "chance_used": 0,  # Chance used count
        }
        self.external_movement_tick.reset()

    def find_fish_cast(self) -> tuple[bool, tuple]:
        """Find fish_cast icon (Cast/Reel), return (found, center)"""
        CAST_THRESHOLD = 0.8  # fish_cast match threshold
        fish_box = self.box_of_screen_scaled(3840, 2160, 3147, 1566, 3383, 1797, name="fish_bite")
        box = self.find_one("fish_cast", box=fish_box, threshold=CAST_THRESHOLD) or self.find_one("fish_ease",
                                                                                                  box=fish_box,
                                                                                                  threshold=CAST_THRESHOLD)
        if box:
            return True, (box.x + box.width // 2, box.y + box.height // 2)
        return False, (0, 0)

    def find_fish_bite(self) -> tuple[bool, tuple]:
        """Find fish_bite icon (Waiting for bite), return (found, center)"""
        BITE_THRESHOLD = 0.8  # fish_bite match threshold
        fish_box = self.box_of_screen_scaled(
            3840, 2160, 3147, 1566, 3383, 1797, name="fish_bite"
        )
        box = self.find_one("fish_bite", box=fish_box, threshold=BITE_THRESHOLD)
        if box:
            return True, (box.x + box.width // 2, box.y + box.height // 2)
        return False, (0, 0)

    def find_fish_chance(self) -> tuple[bool, tuple]:
        """Find fish_chance icon (Chance), return (found, center)"""
        CHANCE_THRESHOLD = 0.8  # fish_chance match threshold
        fish_chance_box = self.box_of_screen_scaled(3840, 2160, 3467, 1797, 3703, 2033, name="fish_chance")
        box = self.find_one("fish_chance", box=fish_chance_box, threshold=CHANCE_THRESHOLD)
        if box:
            return True, (box.x + box.width // 2, box.y + box.height // 2)
        return False, (0, 0)

    def find_bar_and_fish_by_area(self):
        """Find fish bar and icon area and size based on ROI

        Return: ((has_bar, bar_center, bar_rect), (has_icon, icon_center, icon_rect))
        Note: bar_center and icon_center are relative to ROI, bar_rect and icon_rect too
        """

        # Get ROI area
        box = self.box_of_screen_scaled(1920, 1080, 1620, 325, 1645, 725, name="fish_roi")

        try:
            # frame = self.frame
            # Box object uses x, y, width, height attributes
            # box_x1, box_y1 = box.x, box.y
            # box_x2, box_y2 = box.x + box.width, box.y + box.height
            # box_x1 = max(0, min(box_x1, frame_width - 1))
            # box_y1 = max(0, min(box_y1, frame_height - 1))
            # box_x2 = max(box_x1 + 1, min(box_x2, frame_width))
            # box_y2 = max(box_y1 + 1, min(box_y2, frame_height))
            # roi_img = frame[box_y1:box_y2, box_x1:box_x2]
            frame_height, _ = self.frame.shape[:2]
            res_ratio = frame_height / 1080
            roi_img = box.crop_frame(self.frame)

            # Convert to grayscale
            gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)

            # Binarize: Extract bright areas (bar and icon are white/bright)
            _, scene_bin = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

            # Find contours
            contours, _ = cv2.findContours(scene_bin, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

            # Collect all contours meeting minimum area
            blobs = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > self.ICON_MIN_AREA * res_ratio ** 2:
                    blobs.append({"contour": contour, "area": area})

            # Sort by area descending
            blobs.sort(key=lambda b: b["area"], reverse=True)

            has_bar = has_icon = False
            bar_center = bar_rect = icon_center = icon_rect = None
            bar_area = icon_area = 0.0

            # Find fish bar (largest valid contour)
            for blob in blobs:
                if blob["area"] > self.BAR_MIN_AREA * res_ratio ** 2:
                    contour = blob["contour"]
                    moments = cv2.moments(contour)
                    if moments["m00"] > 0:
                        has_bar = True
                        bar_area = blob["area"]
                        # Note: relative to ROI
                        bar_center = (
                            int(moments["m10"] / moments["m00"]),
                            int(moments["m01"] / moments["m00"]),
                        )
                        x, y, w, h = cv2.boundingRect(contour)
                        # Rect relative to ROI
                        bar_rect = (x, y, x + w, y + h)
                    break

            # Find fish icon (second largest valid contour, excluding bar)
            for blob in blobs:
                if blob["area"] == bar_area:
                    continue
                if self.ICON_MIN_AREA * res_ratio ** 2 < blob["area"] < self.ICON_MAX_AREA * res_ratio ** 2:
                    contour = blob["contour"]
                    moments = cv2.moments(contour)
                    if moments["m00"] > 0:
                        has_icon = True
                        icon_area = blob["area"]
                        # Relative to ROI
                        icon_center = (
                            int(moments["m10"] / moments["m00"]),
                            int(moments["m01"] / moments["m00"]),
                        )
                        x, y, w, h = cv2.boundingRect(contour)
                        icon_rect = (x, y, x + w, y + h)
                    break

            if has_bar:
                zone_ratio = bar_area / box.area()
                if self.CONTROL_ZONE_RATIO <= 0 or abs(
                        zone_ratio - self.CONTROL_ZONE_RATIO) / self.CONTROL_ZONE_RATIO > 0.1:
                    self.CONTROL_ZONE_RATIO = zone_ratio
                    self.log_info(f"set CONTROL_ZONE_RATIO {self.CONTROL_ZONE_RATIO}")

            # Update stats
            self.stats.update({
                "last_bar_found": has_bar,
                "last_bar_area": float(bar_area),
                "last_icon_found": has_icon,
                "last_icon_area": float(icon_area),
            })

            return (has_bar, bar_center, bar_rect), (has_icon, icon_center, icon_rect)
        except TaskDisabledException:
            # cv2.destroyAllWindows()
            raise
        except Exception as e:
            logger.error("find_bar_and_fish_by_area error", e)
            return (False, None, None), (False, None, None)

    def create_external_movement_ticker(self):
        def action():
            if self.config.get("Jitter Mode", "Disabled") == "Disabled":
                return
            self.log_info("Triggering External Movement Logic...")
            try:
                self.try_bring_to_front()
            except Exception as e:
                self.log_error(f"Failed to focus window (ignoring): {e}")
            
            try:
                if not self.is_mouse_in_window():
                    self.log_info("Mouse outside window, moving to center...")
                    hwnd_window = self.executor.device_manager.hwnd_window
                    center_x, center_y = hwnd_window.get_abs_cords(
                        self.width_of_screen(0.5), 
                        self.height_of_screen(0.5)
                    )
                    win32api.SetCursorPos((center_x, center_y))
                    return

                current_x, current_y = win32api.GetCursorPos()
                
                # Get jitter amount from config
                jitter_amount = int(self.config.get("External Movement Jitter Amount", 20))
                
                offset_x = random.randint(-jitter_amount, jitter_amount)
                offset_y = random.randint(-jitter_amount, jitter_amount)
                if offset_x == 0 and offset_y == 0:
                    offset_x = jitter_amount // 2 or 5
                
                # Use relative movement for better camera control compatibility
                self.move_mouse_relative(offset_x, offset_y)
                self.log_info(f"Jittering mouse relative by ({offset_x}, {offset_y})")
            except Exception as e:
                self.log_error(f"External movement error: {e}")

        return self.create_ticker(
            action,
            interval=lambda: random.uniform(
                float(self.config.get("External Movement Min Delay", 4.0)),
                float(self.config.get("External Movement Max Delay", 9.0))
            )
        )

    # ---- phases ----
    def phase_start(self) -> bool:
        cfg = self.config
        self.stats["current_phase"] = "Casting"
        self.info_set("Current Phase", "Casting")

        # ensure foreground handled by framework interaction activation
        start_deadline = time.monotonic() + cfg.get("MAX_START_SEC", 20.0)

        has_cast_icon, _ = self.find_fish_cast()
        self.stats["last_cast_icon_found"] = has_cast_icon

        # Check for fish chance
        has_chance_icon, _ = self.find_fish_chance()
        if has_chance_icon:
            logger.info("Detected fish_chance -> Pressing E to use chance")
            self.stats["chance_used"] = self.stats.get("chance_used", 0) + 1
            self.info_set("Chance Used", self.stats["chance_used"])
            # Previous round fish used as bait, decrement round count
            if self.stats["rounds_completed"] > 0:
                self.stats["rounds_completed"] -= 1
                self.info_set("Rounds Completed", self.stats["rounds_completed"])
                logger.info(f"Previous fish used as bait, rounds adjusted to: {self.stats['rounds_completed']}")
            self.send_key("e", down_time=0.06)
        elif not has_cast_icon:
            logger.info("fish_cast not found, trying Space to cast and wait for fish_bite")
            # press space to cast
            self.send_key("space", down_time=0.06)
        else:
            logger.info("Found fish_cast -> Pressing Space to cast")
            self.send_key("space", down_time=0.06)

        logger.info("Waiting for fish_bite...")
        ret = self.wait_until(lambda: self.find_fish_bite()[0], time_out=start_deadline, raise_if_not_found=False)
        self.stats["last_bite_icon_found"] = ret
        if ret:
            logger.info("Found fish_bite -> Waiting for bite")
        else:
            logger.info("Timeout: Waiting for fish_bite")
            return False
        
        self.external_movement_tick()

        # Wait for fish_bite to disappear (fish bit)
        logger.info("Waiting for fish to bite...")
        bite_gone_stable_time = 0.5  # Bite gone stable time
        ret = self.wait_until(lambda: not self.find_fish_bite()[0], time_out=start_deadline,
                              settle_time=bite_gone_stable_time)
        self.stats["last_bite_icon_found"] = not ret
        if not ret:
            logger.info("Timeout waiting for fish_bite to disappear")
            return False

        # Wait for fish_cast to appear (Reel hint)
        logger.info("Waiting for fish_cast (Reel hint)...")
        ret = self.wait_until(lambda: self.find_fish_cast()[0], time_out=start_deadline)
        self.stats["last_cast_icon_found"] = ret
        if ret:
            logger.info("Found fish_cast -> Pressing Space to reel, entering fighting phase")
            self.send_key("space", down_time=0.06)
            return True

        logger.info("Timeout: Waiting for fish_cast")
        return False

    def phase_fight(self) -> bool:
        cfg = self.config
        self.stats["current_phase"] = "Fighting"
        self.info_set("Current Phase", "Fighting")
        logger.info("Entering fighting phase...")

        # Hardcoded constants
        BAR_MISSING_TIMEOUT = 2.5  # Bar missing timeout
        MERGE_GRACE_SECONDS = 0.20  # Merge grace time

        # Runtime state
        is_holding_space = False
        icon_was_visible_prev = False
        last_known_icon_y_relative = 0.0

        bar_missing_start_time = None
        merge_start_time = None

        def set_hold(target_hold: bool):
            nonlocal is_holding_space
            if target_hold != is_holding_space:
                if target_hold:
                    self.send_key_down("space")
                else:
                    self.send_key_up("space")
                is_holding_space = target_hold
                self.stats["last_hold_state"] = is_holding_space

        try:
            while True:
                now = time.monotonic()
                if now >= time.monotonic() + cfg.get("MAX_FIGHT_SEC", 60.0):
                    logger.info("Fighting timeout")
                    return False

                (has_bar, bar_center, bar_rect), (has_icon, icon_center, icon_rect) = self.find_bar_and_fish_by_area()

                # Record icon relative position (for merge handling)
                if has_bar and has_icon:
                    last_known_icon_y_relative = icon_center[1] - bar_center[1]

                # Check if bar is missing
                if not has_bar:
                    if bar_missing_start_time is None:
                        bar_missing_start_time = now
                    elif now - bar_missing_start_time >= BAR_MISSING_TIMEOUT:
                        logger.info(f"Bar missing for > {BAR_MISSING_TIMEOUT}s -> Fighting ended")
                        return True
                else:
                    bar_missing_start_time = None

                # Main control logic: Two-layer control system
                if has_bar and bar_rect:
                    bar_top = bar_rect[1]
                    bar_bottom = bar_rect[3]
                    bar_height = bar_bottom - bar_top

                    if bar_height <= 0:
                        bar_height = 1

                    # Calculate control zone boundaries
                    control_zone_ratio = self.CONTROL_ZONE_RATIO
                    control_height = int(bar_height * control_zone_ratio)
                    control_top = bar_top + control_height
                    control_bottom = bar_bottom - control_height

                    is_merged = has_bar and (not has_icon) and icon_was_visible_prev

                    if has_icon:
                        merge_start_time = None
                        icon_y = icon_center[1]

                        # Simplified two-layer control logic
                        if icon_y < control_top:
                            # Icon in upper control zone -> Hold Space
                            set_hold(True)
                        elif icon_y > control_bottom:
                            # Icon in lower control zone -> Release Space
                            set_hold(False)
                        # else: Icon in neutral zone -> Maintain current state (Hysteresis)

                    else:
                        # Handle merge case
                        if is_merged:
                            if merge_start_time is None:
                                merge_start_time = now
                                self.stats["last_merge_event"] = (f"merged, last_rel={last_known_icon_y_relative:.1f}")
                            elapsed = now - merge_start_time
                            if elapsed <= MERGE_GRACE_SECONDS:
                                # Decide based on last known relative position
                                if last_known_icon_y_relative < 0:
                                    set_hold(True)
                                else:
                                    set_hold(False)
                        else:
                            merge_start_time = None
                else:
                    set_hold(False)

                icon_was_visible_prev = has_icon

                self.next_frame()
                self.external_movement_tick()

        except TaskDisabledException:
            self.send_key_up("space")
            raise
        finally:
            self.send_key_up("space")

    def phase_end(self) -> bool:
        cfg = self.config
        self.stats["current_phase"] = "Reeling"
        self.info_set("Current Phase", "Reeling")

        # wait and press space to collect
        logger.info(f"Waiting {cfg.get('END_WAIT_SPACE', 7.0)}s for fish info...")
        self.sleep(cfg.get("END_WAIT_SPACE", 7.0))
        self.external_movement_tick()

        logger.info("Reeling (Space)")
        self.send_key("space", down_time=0.06)

        # wait and verify
        confirm_deadline = time.monotonic() + cfg.get("MAX_END_SEC", 20.0)
        while time.monotonic() < confirm_deadline:
            has_cast_icon, _ = self.find_fish_cast()
            has_bite_icon, _ = self.find_fish_bite()
            has_chance_icon, _ = self.find_fish_chance()
            self.stats["last_cast_icon_found"] = has_cast_icon
            self.stats["last_bite_icon_found"] = has_bite_icon
            if has_cast_icon or has_bite_icon or has_chance_icon:
                if has_chance_icon:
                    logger.info("Confirmed back to casting interface (Chance detected)")
                else:
                    logger.info("Confirmed back to casting interface")
                return True
            self.send_key("space", down_time=0.06)
            self.sleep(1.0)
        logger.info("End phase verification failed")
        return False

    # main run
    def do_run(self):
        cfg = self.config
        max_rounds = cfg.get("MAX_ROUNDS", 1)

        logger.info("=" * 50)
        logger.info("Auto Fishing Task Started, using COCO detection")
        logger.info(f"Target Rounds: {max_rounds}")
        logger.info("=" * 50)

        # Init stats
        self.stats["rounds_completed"] = 0
        self.stats["start_time"] = time.time()
        self.stats["chance_used"] = 0

        # Init display
        self.info_set("Rounds Completed", 0)
        self.info_set("Chance Used", 0)
        self.info_set("Current Phase", "Preparing")
        self.info_set("Target Rounds", max_rounds)

        # main loop: start -> fight -> end
        while True:
            try:
                # Check if target rounds reached
                if self.stats["rounds_completed"] >= max_rounds:
                    # Check for chance one last time
                    has_chance_icon, _ = self.find_fish_chance()
                    if has_chance_icon:
                        logger.info("Chance detected, previous round doesn't count, continuing...")
                    else:
                        # Completed
                        elapsed_time = time.time() - self.stats["start_time"]
                        hours = int(elapsed_time // 3600)
                        minutes = int((elapsed_time % 3600) // 60)
                        seconds = int(elapsed_time % 60)

                        logger.info("=" * 50)
                        logger.info(f"✓ Target Rounds Reached: {self.stats['rounds_completed']}")
                        logger.info(f"✓ Total Time: {hours:02d}:{minutes:02d}:{seconds:02d}")
                        if self.stats["rounds_completed"] > 0:
                            avg_time = elapsed_time / self.stats["rounds_completed"]
                            logger.info(f"✓ Avg Time/Round: {avg_time:.1f} s")
                        logger.info("Auto Fishing Task Completed!")
                        logger.info("=" * 50)
                        self.soundBeep()
                        break

                if not self.phase_start():
                    self.sleep(1.0)
                    continue
                if not self.phase_fight():
                    self.sleep(1.0)
                    continue
                if not self.phase_end():
                    self.sleep(1.0)
                    continue

                # Round completed
                self.stats["rounds_completed"] += 1
                self.info_set("Rounds Completed", self.stats["rounds_completed"])

                elapsed_time = time.time() - self.stats["start_time"]
                hours = int(elapsed_time // 3600)
                minutes = int((elapsed_time % 3600) // 60)
                seconds = int(elapsed_time % 60)
                avg_time = elapsed_time / self.stats["rounds_completed"]

                # Update total time display
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                self.info_set("Total Time", time_str)

                logger.info("=" * 50)
                logger.info(f"✓ Round {self.stats['rounds_completed']} Completed")
                logger.info(f"  Total Time: {hours:02d}:{minutes:02d}:{seconds:02d}")
                logger.info(f"  Avg Time: {avg_time:.1f} s")
                remaining = max_rounds - self.stats["rounds_completed"]
                logger.info(f"  Remaining: {remaining}")
                logger.info("=" * 50)

                # Continue
                self.sleep(1.0)
                self.sleep(1.0)
            except TaskDisabledException:
                raise
            except Exception as e:
                logger.error("AutoFishTask fatal", e)
                break
