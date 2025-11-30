import re
import time
import random
import win32api
import win32con
from enum import Enum

from ok import find_boxes_by_name, TaskDisabledException
from src.tasks.BaseDNATask import BaseDNATask, isolate_white_text_to_black


class Mission(Enum):
    START = 1
    CONTINUE = 2
    STOP = 3
    GIVE_UP = 4


class CommissionsTask(BaseDNATask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_round = 0
        self.current_wave = -1
        self.mission_status = None
        self.action_timeout = 10
        self.wave_future = None

    def setup_commission_config(self):
        self.default_config.update({
            'Timeout': 120,
            "Commission Manual": "Disabled",
            "Commission Manual Specific Rounds": "",
            "Use Skill": "Disabled",
            "Skill Cast Frequency": 5.0,
            "Enable Auto Resonance": True,
            "Play Sound Notification": True,
            "Auto Select First Letter and Reward": True,
            "Prioritize Letter Reward": "Disabled",
            "Jitter Mode": "Disabled",
            "External Movement Min Delay": 4.0,
            "External Movement Max Delay": 8.0,
            "External Movement Jitter Amount": 20,
        })
        self.config_description.update({
            "Commission Manual Specific Rounds": "Example: 3,5,8",
            "Timeout": "Restart task after timeout",
            "Skill Cast Frequency": "Cast skill every X seconds",
            "Enable Auto Resonance": "Enable auto resonance trigger when map traversal is needed",
            "Play Sound Notification": "Play sound notification when needed",
            "Auto Select First Letter and Reward": "Recommended to enable next option when farming weapon letters",
            "Prioritize Letter Reward": "Effective when previous option is enabled",
            "Jitter Mode": "Control when mouse jitter happens (Disabled, Always, Combat Only)",
            "External Movement Min Delay": "Minimum interval for random mouse movement (seconds)",
            "External Movement Max Delay": "Maximum interval for random mouse movement (seconds)",
            "External Movement Jitter Amount": "Maximum pixel distance to move mouse (default: 20)",
        })
        self.config_type["Commission Manual"] = {
            "type": "drop_down",
            "options": ["Disabled", "100%", "200%", "800%", "2000%"],
        }
        self.config_type["Jitter Mode"] = {
            "type": "drop_down",
            "options": ["Disabled", "Always", "Combat Only"],
        }
        self.config_type["Use Skill"] = {
            "type": "drop_down",
            "options": ["Disabled", "Combat Skill", "Ultimate Skill", "Geniemon Support"],
        }
        self.config_type["Prioritize Letter Reward"] = {
            "type": "drop_down",
            "options": ["Disabled", "Owned Count 0", "Owned Count Min", "Owned Count Max"],
        }

    def find_quit_btn(self, threshold=0, box=None):
        if box is None:
            box = self.box_of_screen_scaled(2560, 1440, 729, 960, 854, 1025, name="quit_mission", hcenter=True)
        return self.find_one("ingame_quit_icon", threshold=threshold, box=box)

    def find_continue_btn(self, threshold=0, box=None):
        if box is None:
            box = self.box_of_screen(0.610, 0.671, 0.647, 0.714, name="continue_mission", hcenter=True)
        return self.find_one("ingame_continue_icon", threshold=threshold, box=box)

    def find_bottom_start_btn(self, threshold=0):
        return self.find_start_btn(
            threshold=threshold, box=self.box_of_screen_scaled(2560, 1440, 2094, 1262, 2153, 1328, name="start_mission",
                                                               hcenter=True))

    def find_big_bottom_start_btn(self, threshold=0):
        return self.find_start_btn(
            threshold=threshold, box=self.box_of_screen_scaled(2560, 1440, 1667, 1259, 1728, 1328, name="start_mission",
                                                               hcenter=True))

    def find_letter_btn(self, threshold=0):
        return self.find_start_btn(
            threshold=threshold, box=self.box_of_screen_scaled(2560, 1440, 1630, 852, 1884, 920, name="letter_btn",
                                                               hcenter=True))

    def find_letter_reward_btn(self, threshold=0):
        return self.find_start_btn(
            threshold=threshold, box=self.box_of_screen_scaled(2560, 1440, 1071, 1160, 1120, 1230,
                                                               name="letter_reward_btn", hcenter=True))

    def find_drop_rate_btn(self, threshold=0):
        return self.find_start_btn(
            threshold=threshold, box=self.box_of_screen_scaled(2560, 1440, 1060, 935, 1420, 1000, name="drop_rate_btn",
                                                               hcenter=True))

    def find_esc_menu(self, threshold=0):
        return self.find_one("quit_big_icon", threshold=threshold)

    def open_in_mission_menu(self, time_out=20, raise_if_not_found=True):
        if self.find_esc_menu():
            return True
        found = False
        start = time.time()
        while time.time() - start < time_out:
            self.send_key("esc")
            if self.wait_until(self.find_esc_menu, time_out=2, raise_if_not_found=False):
                found = True
                break
        else:
            if raise_if_not_found:
                raise Exception("Mission menu not found")
        self.sleep(0.2)
        return found

    def start_mission(self, timeout=0):
        action_timeout = self.action_timeout if timeout == 0 else timeout
        box = self.box_of_screen_scaled(2560, 1440, 60, 1029, 2056, 1332, name="reward_drag_area", hcenter=True)
        start_time = time.time()
        while time.time() - start_time < action_timeout:
            if btn := self.find_retry_btn() or self.find_bottom_start_btn() or self.find_big_bottom_start_btn():
                self.move_mouse_to_safe_position(box=box)
                self.click_box(btn, after_sleep=0)
                self.move_back_from_safe_position()
            self.sleep(0.2)
            if self.wait_until(condition=lambda: self.find_start_btn() or self.find_letter_interface(), time_out=1):
                break
            if self.find_retry_btn() and self.calculate_color_percentage(retry_btn_color,
                                                                         self.get_box_by_name("retry_icon")) < 0.05:
                self.soundBeep()
                self.log_info_notify("Task cannot continue")
                raise TaskDisabledException
        else:
            raise Exception("Timeout waiting for mission start")

    def quit_mission(self, timeout=0):
        action_timeout = self.action_timeout if timeout == 0 else timeout
        quit_btn = self.wait_until(self.find_quit_btn, time_out=action_timeout, raise_if_not_found=True)
        self.sleep(0.5)
        self.wait_until(
            condition=lambda: not self.find_quit_btn(),
            post_action=lambda: self.click_box(quit_btn, after_sleep=0.25),
            time_out=action_timeout,
            raise_if_not_found=True,
        )
        self.sleep(1)
        self.wait_until(lambda: not self.in_team(), time_out=action_timeout, raise_if_not_found=True)

    def give_up_mission(self, timeout=0):
        def is_mission_start_iface():
            return self.find_retry_btn() or self.find_bottom_start_btn() or self.find_big_bottom_start_btn()

        action_timeout = self.action_timeout if timeout == 0 else timeout
        box = self.box_of_screen_scaled(2560, 1440, 1301, 776, 1365, 841, name="give_up_mission", hcenter=True)

        if self.open_in_mission_menu(time_out=10, raise_if_not_found=False):
            self.wait_until(
                condition=lambda: self.find_start_btn(box=box),
                post_action=lambda: self.click_relative(0.95, 0.91, after_sleep=0.25),
                time_out=action_timeout,
                raise_if_not_found=True,
            )
            self.sleep(0.5)
            self.wait_until(
                condition=lambda: not self.find_start_btn(box=box),
                post_action=lambda: self.click_box(self.find_start_btn(box=box), after_sleep=0.25),
                time_out=action_timeout,
                raise_if_not_found=True,
            )

        self.wait_until(condition=is_mission_start_iface, time_out=60, raise_if_not_found=True)

    def continue_mission(self, timeout=0):
        if self.in_team():
            return False
        action_timeout = self.action_timeout if timeout == 0 else timeout
        continue_btn = self.wait_until(self.find_continue_btn, time_out=action_timeout, raise_if_not_found=True)
        self.wait_until(
            condition=lambda: not self.find_continue_btn(),
            post_action=lambda: self.click_box(continue_btn, after_sleep=0.25),
            time_out=action_timeout,
            raise_if_not_found=True,
        )
        self.sleep(0.5)
        return True

    def choose_drop_rate(self, timeout=0):
        def click_drop_rate_btn():
            if (box:=self.find_drop_rate_btn()):
                self.click_box(box, after_sleep=0.25)
        action_timeout = self.action_timeout if timeout == 0 else timeout
        self.sleep(0.5)
        self.choose_drop_rate_item()
        self.wait_until(
            condition=lambda: not self.find_drop_item() and not self.find_drop_item(800),
            post_action=click_drop_rate_btn,
            time_out=action_timeout,
            raise_if_not_found=True,
        )

    def choose_drop_rate_item(self):
        if not hasattr(self, "config"):
            return
        drop_rate = self.config.get("Commission Manual", "Disabled")
        if drop_rate == "Disabled":
            return
        round_to_use = [int(num) for num in re.findall(r'\d+', self.config.get("Commission Manual Specific Rounds", ""))]
        if len(round_to_use) != 0:
            if self.mission_status != Mission.CONTINUE:
                if 1 not in round_to_use:
                    return
            elif self.current_round == 0 or (self.current_round + 1) not in round_to_use:
                return
        if drop_rate == "100%":
            self.click_relative(0.40, 0.56)
        elif drop_rate == "200%":
            self.click_relative(0.50, 0.56)
        elif drop_rate == "800%":
            self.click_relative(0.59, 0.56)
        elif drop_rate == "2000%":
            self.click_relative(0.68, 0.56)
        self.log_info(f"Using Commission Manual: {drop_rate}")
        self.sleep(0.25)

    def choose_letter(self, timeout=0):
        if not hasattr(self, "config"):
            return
        action_timeout = self.action_timeout if timeout == 0 else timeout
        if self.config.get("Auto Select First Letter and Reward", False):
            if self.find_letter_interface():
                box = self.box_of_screen_scaled(2560, 1440, 1195, 612, 2449, 817, name="letter_drag_area", hcenter=True)
                self.sleep(0.1)
                self.move_mouse_to_safe_position(box=box)
                self.click(0.56, 0.5, down_time=0.02)
                self.move_back_from_safe_position()
                self.sleep(0.1)
                self.wait_until(
                    condition=lambda: not self.find_letter_interface(),
                    post_action=lambda: (
                        self.move_mouse_to_safe_position(box=box),
                        self.click(0.79, 0.61),
                        self.move_back_from_safe_position(),
                        self.sleep(1),
                    ),
                    time_out=action_timeout,
                    raise_if_not_found=True,
                )
        else:
            self.log_info_notify("Please select letter manually")
            self.soundBeep()
            self.wait_until(
                lambda: not self.find_letter_interface(),
                time_out=300,
                raise_if_not_found=True,
            )

    def choose_target_letter_reward(self):
        reward_pattern = re.compile(r'[:：]\s*([0-9]+)')
        def get_rewards():
            box = self.box_of_screen(0.328, 0.643, 0.678, 0.672, hcenter=True, name="letter_reward")
            return self.ocr(box=box, match=reward_pattern)
        
        start = time.time()
        while time.time() - start < 10:
            rewards = get_rewards()
            if len(rewards) == 3:
                break
            self.sleep(0.1)
        else:
            self.log_info("Timeout: Failed to identify 3 reward options, using default reward")
            return

        self.sleep(0.3)
        rewards = get_rewards()

        if len(rewards) != 3:
            self.log_info(f"Error: Stable recognition count mismatch (found {len(rewards)}), using default reward")
            return

        rewards.sort(key=lambda reward: reward.x)

        parsed_items = []
        for idx, reward in enumerate(rewards):
            match = reward_pattern.search(reward.name)
            if not match:
                self.log_info(f"Failed to identify count for reward {idx + 1}, using default reward")
                return
            count = int(match.group(1))
            parsed_items.append({
                'index': idx + 1,
                'count': count,
                'reward_obj': reward,
                'name': reward.name
            })

        strategy = self.config.get("Prioritize Letter Reward")
        target_item = None

        self.log_info(f"Current reward owned counts: {[item['count'] for item in parsed_items]}")

        if strategy == "Owned Count 0":
            for item in parsed_items:
                if item['count'] == 0:
                    target_item = item
                    break
            if not target_item:
                self.log_info("No reward with 0 owned count found, using default reward")
                return

        elif strategy == "Owned Count Min":
            target_item = min(parsed_items, key=lambda x: x['count'])

        elif strategy == "Owned Count Max":
            target_item = max(parsed_items, key=lambda x: x['count'])

        if target_item:
            self.log_info(f"Strategy [{strategy}] -> Selecting reward {target_item['index']}, owned: {target_item['count']}")
            self.click_box(target_item['reward_obj'], down_time=0.02, after_sleep=0.5)

    def choose_letter_reward(self, timeout=0):
        if not hasattr(self, "config"):
            return
        action_timeout = self.action_timeout if timeout == 0 else timeout
        if self.config.get("Auto Select First Letter and Reward", False):
            if self.config.get("Prioritize Letter Reward", "Disabled") != "Disabled":
                self.choose_target_letter_reward()
            self.wait_until(
                condition=lambda: not self.find_letter_reward_btn(),
                post_action=lambda: self.click(0.50, 0.83, after_sleep=0.25),
                time_out=action_timeout,
                raise_if_not_found=True,
            )
        else:
            self.log_info_notify("Please select letter reward manually")
            self.soundBeep()
            self.wait_until(
                lambda: not self.find_letter_reward_btn(),
                time_out=300,
                raise_if_not_found=True,
            )
        self.sleep(3)

    def use_skill(self, skill_time):
        if not hasattr(self, "config"):
            return
        if self.config.get("Use Skill", "Disabled") != "Disabled" and time.time() - skill_time >= self.config.get("Skill Cast Frequency", 5):
            skill_time = time.time()
            if self.config.get("Use Skill") == "Combat Skill":
                self.get_current_char().send_combat_key()
            elif self.config.get("Use Skill") == "Ultimate Skill":
                self.get_current_char().send_ultimate_key()
            elif self.config.get("Use Skill") == "Geniemon Support":
                self.get_current_char().send_geniemon_key()
        return skill_time

    def create_skill_ticker(self):

        def action():
            if self.config.get("Use Skill", "Disabled") == "Disabled":
                return
            if self.config.get("Use Skill") == "Combat Skill":
                self.get_current_char().send_combat_key()
            elif self.config.get("Use Skill") == "Ultimate Skill":
                self.get_current_char().send_ultimate_key()
            elif self.config.get("Use Skill") == "Geniemon Support":
                self.get_current_char().send_geniemon_key()

        return self.create_ticker(action, interval=lambda: self.config.get("Skill Cast Frequency", 5))

    def create_external_movement_ticker(self):
        def action():
            if self.config.get("Jitter Mode", "Disabled") == "Disabled":
                # self.log_info("External movement disabled in config")
                return
            self.log_info("Triggering External Movement Logic...")
            try:
                self.try_bring_to_front()
            except Exception as e:
                self.log_error(f"Failed to focus window (ignoring): {e}")
            
            # self.try_bring_to_front() # Removed duplicate call
            
            try:
                # Check if mouse is in window
                if not self.is_mouse_in_window():
                    self.log_info("Mouse outside window, moving to center...")
                    # Move to center of window
                    hwnd_window = self.executor.device_manager.hwnd_window
                    center_x, center_y = hwnd_window.get_abs_cords(
                        self.width_of_screen(0.5), 
                        self.height_of_screen(0.5)
                    )
                    win32api.SetCursorPos((center_x, center_y))
                    return # Skip jitter this tick, we just moved it

                # Get current position
                current_x, current_y = win32api.GetCursorPos()
                
                # Get jitter amount from config
                jitter_amount = int(self.config.get("External Movement Jitter Amount", 20))
                
                # Generate small random offset (jitter)
                offset_x = random.randint(-jitter_amount, jitter_amount)
                offset_y = random.randint(-jitter_amount, jitter_amount)
                
                # Ensure we don't just stay in place
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

    def ensure_game_focused(self):
        """
        If external movement logic is enabled, force focus the game window immediately.
        This is useful to call at the start of a task to ensure the game is active.
        """
        if self.config.get("Jitter Mode", "Disabled") != "Disabled":
            self.log_info("External movement enabled: Forcing game window focus...")
            try:
                self.try_bring_to_front()
            except Exception as e:
                self.log_error(f"Failed to focus window: {e}")

    def get_round_info(self):
        """获取并更新当前轮次信息。"""
        if self.in_team():
            return

        self.sleep(1)
        round_info_box = self.box_of_screen_scaled(2560, 1440, 531, 517, 618, 602, name="round_info", hcenter=True)
        texts = self.ocr(box=round_info_box)

        prev_round = self.current_round
        new_round_from_ocr = None
        if texts and texts[0].name.isdigit():
            new_round_from_ocr = int(texts[0].name)

        if new_round_from_ocr is not None:
            self.current_round = new_round_from_ocr
        elif self.current_round != 0:  # OCR失败，但之前已有轮次记录，则递增
            self.current_round += 1

        if prev_round != self.current_round:
            self.info_set("Current Round", self.current_round)

    def get_wave_info(self):
        if not self.in_team():
            return
        if self.wave_future and self.wave_future.done():
            texts = self.wave_future.result()
            self.wave_future = None
            if texts and len(texts) == 1:
                prev_wave = self.current_wave
                if (m := re.match(r"(\d)/\d", texts[0].name)):
                    self.current_wave = int(m.group(1))
                else:
                    return
                if prev_wave != self.current_wave:
                    self.info_set("Current Wave", self.current_wave)
            return
        if self.wave_future is None:
            mission_info_box = self.box_of_screen_scaled(2560, 1440, 275, 372, 445, 470, name="mission_info",
                                                         hcenter=True)
            frame = self.frame.copy()
            self.wave_future = self.thread_pool_executor.submit(self.ocr, frame=frame,
                                                                box=mission_info_box,
                                                                frame_processor=isolate_white_text_to_black,
                                                                match=re.compile(r"\d/\d"))

    def reset_wave_info(self):
        if self.wave_future is not None:
            self.wave_future.cancel()
            self.wave_future = None
        self.current_wave = -1
        self.info_set("Current Wave", self.current_wave)

    def wait_until_get_wave_info(self):
        self.log_info("Waiting for wave info...")
        while self.current_wave == -1:
            self.get_wave_info()
            self.sleep(0.2)

    def handle_mission_interface(self, stop_func=lambda: False):
        if self.in_team():
            return False

        self.check_for_monthly_card()

        if self.find_letter_reward_btn():
            self.log_info("Handling mission interface: Selecting letter reward")
            self.choose_letter_reward()
            return

        if self.find_letter_interface():
            self.log_info("Handling mission interface: Selecting letter")
            self.choose_letter()
            return self.get_return_status()
        elif self.find_drop_item() or self.find_drop_item(800):
            self.log_info("Handling mission interface: Selecting commission manual")
            self.choose_drop_rate()
            return self.get_return_status()

        if self.find_retry_btn() or self.find_bottom_start_btn() or self.find_big_bottom_start_btn():
            self.log_info("Handling mission interface: Starting mission")
            self.start_mission()
            self.mission_status = Mission.START
            return
        elif self.find_continue_btn():
            if stop_func():
                self.log_info("Handling mission interface: Stopping mission")
                return Mission.STOP
            self.log_info("Handling mission interface: Continuing mission")
            self.continue_mission()
            self.mission_status = Mission.CONTINUE
            return
        elif self.find_esc_menu():
            self.log_info("Handling mission interface: Giving up mission")
            self.give_up_mission()
            return Mission.GIVE_UP
        return False

    def get_return_status(self):
        ret = self.mission_status if self.mission_status else Mission.START
        self.mission_status = None
        return ret

    def find_next_hint(self, x1, y1, x2, y2, s, box_name="hint_text"):
        texts = self.ocr(
            box=self.box_of_screen(x1, y1, x2, y2, hcenter=True),
            target_height=540,
            name=box_name,
        )
        target_text = find_boxes_by_name(texts, re.compile(s, re.IGNORECASE))
        if target_text:
            return True

    def reset_and_transport(self):
        self.open_in_mission_menu()
        self.sleep(0.8)
        self.wait_until(
            condition=lambda: not self.find_esc_menu(),
            post_action=self.click(0.73, 0.92, after_sleep=0.5),
            time_out=10,
        )
        setting_box = self.box_of_screen_scaled(2560, 1440, 738, 4, 1123, 79, name="other_section", hcenter=True)
        setting_other = self.wait_until(lambda: self.find_one("setting_other", box=setting_box), time_out=10,
                                        raise_if_not_found=True)
        self.wait_until(
            condition=lambda: self.calculate_color_percentage(setting_menu_selected_color, setting_other) > 0.24,
            post_action=lambda: self.click_box(setting_other, after_sleep=0.5),
            time_out=10,
        )
        confirm_box = self.box_of_screen_scaled(2560, 1440, 1298, 776, 1368, 843, name="confirm_btn", hcenter=True)
        self.wait_until(
            condition=lambda: self.find_start_btn(box=confirm_box),
            post_action=lambda: (
                self.move_mouse_to_safe_position(),
                self.click(0.60, 0.32),
                self.move_back_from_safe_position(),
                self.sleep(1),
            ),
            time_out=10,
        )
        if not self.wait_until(condition=self.in_team, post_action=self.click(0.59, 0.56, after_sleep=0.5),
                               time_out=10):
            self.ensure_main()
            return False
        return True

    def find_letter_interface(self):
        box = self.find_letter_btn() or self.find_not_use_letter_icon()
        return box


class QuickMoveTask:

    def __init__(self, owner: "CommissionsTask"):
        self._owner = owner
        self._move_task = None

    def run(self):
        if self._owner.config.get("Enable Auto Resonance", False):
            if not self._move_task:
                from src.tasks.trigger.AutoMoveTask import AutoMoveTask

                self._move_task = self._owner.get_task_by_class(AutoMoveTask)

            if self._move_task:
                self._move_task.try_connect_listener()
                self._move_task.run()

    def reset(self):
        if self._move_task:
            self._move_task.reset()
            self._move_task.try_disconnect_listener()


setting_menu_selected_color = {
    'r': (220, 255),  # Red range
    'g': (200, 255),  # Green range
    'b': (125, 250)  # Blue range
}

retry_btn_color = {
    'r': (220, 230),  # Red range
    'g': (175, 185),  # Green range
    'b': (79, 89)  # Blue range
}


def _default_movement():
    pass
