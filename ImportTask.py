from qfluentwidgets import FluentIcon
import re
import time
import win32con
import win32api
import cv2
import os
import json
import numpy as np
from functools import cached_property

from pathlib import Path
from PIL import Image
from ok import Logger, TaskDisabledException, GenshinInteraction
from ok import find_boxes_by_name
from src.tasks.DNAOneTimeTask import DNAOneTimeTask
from src.tasks.CommissionsTask import CommissionsTask, Mission, QuickMoveTask
from src.tasks.BaseCombatTask import BaseCombatTask

from src.tasks.trigger.AutoMazeTask import AutoMazeTask
from src.tasks.trigger.AutoRouletteTask import AutoRouletteTask

from src.tasks.AutoDefence import AutoDefence
from src.tasks.AutoExpulsion import AutoExpulsion
from src.tasks.AutoExploration import AutoExploration

logger = Logger.get_logger(__name__)


class MacroFailedException(Exception):
    """External script failed exception."""
    pass


class ImportTask(DNAOneTimeTask, CommissionsTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.name = "Auto Dungeon with External Logic"
        self.description = "Full Auto"
        self.group_name = "Full Auto"
        self.group_icon = FluentIcon.CAFE
        self.last_f_time = 0
        self.last_f_was_interact = False

        self.default_config.update({
            'Rounds': 10,
            'External Folder': "",
            'Dungeon Type': "Default",
            "Jitter Mode": "Disabled",
            "External Movement Min Delay": 4.0,
            "External Movement Max Delay": 8.0,
            "External Movement Jitter Amount": 20,
            # 'Use Built-in Mechanism Unlock': False,
        })
        self.config_type['External Folder'] = {
            "type": "drop_down",
            "options": self.load_direct_folder(f'{Path.cwd()}/mod'),
        }

        self.config_type['Dungeon Type'] = {
            "type": "drop_down",
            "options": ["Default", "Endless Defence", "Endless Exploration", "Expulsion"],
        }
        self.config_type["Jitter Mode"] = {
            "type": "drop_down",
            "options": ["Disabled", "Always", "Combat Only"],
        }
        self.setup_commission_config()
        keys_to_remove = ["Enable Auto Resonance"]
        for key in keys_to_remove:
            self.default_config.pop(key, None)

        self.config_description.update({
            'Rounds': 'Number of rounds for endless mode',
            'External Folder': 'Select external logic from mod folder',
            'Dungeon Type': 'Select dungeon type',
            "Jitter Mode": "Control when mouse jitter happens (Disabled, Always, Combat Only)",
            "External Movement Min Delay": "Minimum interval for random mouse movement (seconds)",
            "External Movement Max Delay": "Maximum interval for random mouse movement (seconds)",
            "External Movement Jitter Amount": "Maximum pixel distance to move mouse (default: 20)",
            # 'Use Built-in Mechanism Unlock': 'Use ok built-in unlocking function',
        })

        self.skill_tick = self.create_skill_ticker()
        self.external_movement_tick = self.create_external_movement_ticker()
        self.action_timeout = 10
        self.quick_move_task = QuickMoveTask(self)

    def run(self):
        DNAOneTimeTask.run(self)
        self.move_mouse_to_safe_position(save_current_pos=False)
        self.set_check_monthly_card()
        self.ensure_game_focused()
        try:
            path = Path.cwd()
            self.script = self.process_json_files(f'{path}/mod/{self.config.get("External Folder")}/scripts')
            self.img = self.load_png_files(f'{path}/mod/{self.config.get("External Folder")}/map')
            _to_do_task = self
            dungeon_type = self.config.get('Dungeon Type')
            if dungeon_type == 'Endless Defence':
                _to_do_task = self.get_task_by_class(AutoDefence)
                _to_do_task.config_external_movement(self.walk_to_aim, self.config)
            elif dungeon_type == 'Endless Exploration':
                _to_do_task = self.get_task_by_class(AutoExploration)
                _to_do_task.config_external_movement(self.walk_to_aim, self.config)
            elif dungeon_type == 'Expulsion':
                _to_do_task = self.get_task_by_class(AutoExpulsion)
                _to_do_task.config_external_movement(self.walk_to_aim, self.config)
            return _to_do_task.do_run()
        except TaskDisabledException:
            pass
        except Exception as e:
            logger.error('AutoDefence error', e)
            raise

    def do_run(self):
        self.init_all()
        self.load_char()
        if self.in_team():
            self.open_in_mission_menu()
            self.sleep(0.5)
        while True:
            if self.in_team():
                self.get_wave_info()
                if self.current_wave != -1:
                    if self.current_wave != self.runtime_state["wave"]:
                        self.runtime_state["wave"] = self.current_wave
                self.skill_tick()
                self.external_movement_tick()
                if time.time() - self.runtime_state["wave_start_time"] >= self.config.get('Timeout', 180):
                    self.log_info('Task Timeout')
                    self.open_in_mission_menu()
                    self.sleep(0.5)
                if self.delay_index is not None and time.time() > self.runtime_state["delay_task_start"]:
                    self.runtime_state["delay_task_start"] += 1
                    if self.match_map(self.delay_index):
                        self.walk_to_aim(self.delay_index)
            _status = self.handle_mission_interface(stop_func=self.stop_func)
            if _status == Mission.START or _status == Mission.STOP:
                if _status == Mission.STOP:
                    self.quit_mission()
                    self.log_info('Task Stopped')
                    self.init_all()
                    continue
                self.wait_until(self.in_team, time_out=30)
                self.log_info('Task Started')
                self.init_all()
                self.sleep(2)
                self.walk_to_aim()
                now = time.time()
                self.runtime_state.update({"wave_start_time": now, "delay_task_start": now + 1})
            elif _status == Mission.CONTINUE:
                self.log_info('Task Continued')
                self.wait_until(self.in_team, time_out=30)
                self.init_for_next_round()
                now = time.time()
                self.runtime_state.update({"wave_start_time": now, "delay_task_start": now + 1})
            self.sleep(0.2)

    def init_all(self):
        self.init_for_next_round()
        self.delay_index = None
        self.skill_tick.reset()
        self.external_movement_tick.reset()
        self.current_round = 0

    def init_for_next_round(self):
        self.init_runtime_state()

    def init_runtime_state(self):
        self.runtime_state = {"wave_start_time": 0, "wave": -1, "delay_task_start": 0}
        self.reset_wave_info()

    def stop_func(self):
        self.get_round_info()
        n = self.config.get('Rounds', 3)
        if self.current_round >= n:
            return True

    def load_direct_folder(self, path):
        folders = []
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path) and item != 'builtin':
                folders.append(item)
        return folders

    def process_json_files(self, folder_path):
        json_files = {}
        for filename in os.listdir(folder_path):
            if filename.endswith('.json'):
                file_path = os.path.join(folder_path, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        json_files[filename.removesuffix(".json")] = data
                        self.log_info(f"Successfully loaded: {file_path}")
                except Exception as e:
                    self.log_info(f"Failed to load {file_path}: {e}")

        return json_files

    def load_png_files(self, folder_path):
        png_files = {}

        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"Folder not found: {folder_path}")

        for filename in os.listdir(folder_path):
            if filename.lower().endswith('.png'):
                file_path = os.path.join(folder_path, filename)
                try:
                    pil_img = Image.open(file_path)
                    img_array = np.array(pil_img)
                    if len(img_array.shape) == 3:
                        template = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                    else:
                        template = img_array

                    if template is None:
                        raise ValueError(f"Image conversion failed: {file_path}")

                    # Compatibility: Python 3.9+ supports removesuffix, lower versions use slice
                    key_name = filename.removesuffix(".png") if hasattr(filename, "removesuffix") else filename[:-4]

                    png_files[key_name] = template
                    self.log_info(f"Successfully loaded (grayscale): {filename}")

                except Exception as e:
                    self.log_error(f"Failed to load {filename}", e)
        png_files = {key: png_files[key] for key in sorted(png_files.keys(), key=lambda x: (len(x), x))}
        return png_files

    def walk_to_aim(self, former_index=None):
        """
        Try to match the next map node and execute macro.
        """
        # Precompile regex for efficiency
        # Logic: if no former point, skip names ending with letter (usually steps after start point)
        end_with_letter_pattern = re.compile(r'[a-zA-Z]$')
        # maze_task = self.get_task_by_class(AutoMazeTask)
        # roulette_task = self.get_task_by_class(AutoRouletteTask)

        while True:
            start_time = time.perf_counter()
            map_index = None

            # Try to find matching map within 5 seconds
            while map_index is None and time.perf_counter() - start_time < 5:
                # if self.config.get('Use Built-in Mechanism Unlock', False):
                #     maze_task.run()
                #     roulette_task.run()
                #     if maze_task.unlocked or roulette_task.unlocked:

                #         def find_next_child(parent_name):
                #             parent_name += "-"
                #             for name in self.img.keys():
                #                 if name.startswith(parent_name) and len(name) > len(parent_name):
                #                     return name
                #             return None

                #         step_1 = find_next_child(former_index)
                #         if step_1:
                #             self.log_info(f"Index jump: {former_index} -> {step_1}")
                #             former_index = step_1

                #             # Reset time and skip this match
                #             start_time = time.perf_counter()
                #             self.sleep(1)
                #             continue
                #         else:
                #             self.log_info(f"Cannot find next node for {former_index}")

                # Pass compiled regex object for performance
                map_index, count = self.match_map(former_index, pattern=end_with_letter_pattern)

                if count == 0:
                    self.log_info("No candidate maps, navigation ended")
                    return True

                if map_index is None:
                    # Avoid CPU 100% spin
                    self.sleep(0.1)

            if map_index is not None:
                self.log_info(f'Start executing macro: {map_index}')
                try:
                    self.play_macro_actions(map_index)
                    # Update former node for next logic judgment
                    former_index = map_index
                except MacroFailedException:
                    logger.warning(f"Macro execution failed: {map_index}")
                    return False
                except TaskDisabledException:
                    raise
                except Exception as e:
                    logger.error("ImportTask critical error", e)
                    raise
            else:
                self.log_info("Timeout matching map, assuming destination reached or path lost")
                return True

    def match_map(self, index, max_conf=0.0, pattern=None):  # Suggest giving max_conf a reasonable default like 0.6
        """
        Find best matching map template in current screen.
        """
        # 1. Extract image processing logic outside loop (huge performance boost)
        # Assume box definition is constant
        box = self.box_of_screen_scaled(2560, 1440, 1, 1, 2559, 1439, name="full_screen", hcenter=True)

        # Crop and convert screen only once
        cropped_screen = box.crop_frame(self.frame)
        screen_gray = cv2.cvtColor(cropped_screen, cv2.COLOR_BGR2GRAY)

        count = 0
        max_index = None
        best_threshold = max_conf  # Use passed threshold as baseline

        # If no precompiled regex passed, compile temporarily
        if pattern is None:
            pattern = re.compile(r'[a-zA-Z]$')

        for name, template_gray in self.img.items():
            # --- Filtering Logic ---
            # Logic 1: Start state (index is None)
            if index is None and not pattern.search(name):
                continue

            if index is not None:
                # Logic 2: Don't match self (check this first for efficiency)
                if index == name:
                    continue

                # Logic 3: Strict prefix matching
                
                # 1. Must start with index
                if not name.startswith(index):
                    continue
                
                # 2. Get suffix after removing index
                # e.g.: index="A-1", name="A-1-1" -> suffix="-1"
                # e.g.: index="A-1", name="A-10"  -> suffix="0"
                suffix = name[len(index):]

                # 3. Check separator: if not starting with '-', it's not hierarchy but number extension (e.g. 1 -> 10)
                # This prevents "60Character-A-1-1" matching "60Character-A-1-10"
                if not suffix.startswith('-'):
                    continue
                
                # 4. Hierarchy limit
                # If suffix contains 2 or more '-', it's a cross-level node (e.g. A -> A-1-1)
                # So suffix can only be "-1", not "-1-1"
                if suffix.count('-') >= 2:
                    continue

                # 5. Length limit (last line of defense)
                # Since we limited to one '-', this mainly limits "-xxxxx" length
                if len(suffix) > 4: 
                    continue

            count += 1

            # Execute match
            result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
            _, threshold, _, _, = cv2.minMaxLoc(result)

            # Only record if better than current best
            if threshold > best_threshold:
                best_threshold = threshold
                max_index = name
                # Only log debug when finding better match to reduce spam
                # logger.debug(f"Found potential match: {name} conf={threshold:.4f}")

        if max_index is not None:
            self.log_info(f"Successfully matched: {max_index} (conf={best_threshold:.4f})")
        else:
            # Only log when really not found, or use debug level
            # self.log_info("No valid map matched this round")
            pass

        return max_index, count

    @cached_property
    def genshin_interaction(self):
        """
        Cache Interaction instance to avoid recreating object on every mouse move.
        Ensure self.executor.interaction and self.hwnd are available when initializing.
        """
        # Ensure referencing correct class
        return GenshinInteraction(self.executor.interaction.capture, self.hwnd)

    def play_macro_actions(self, map_index):
        actions = self.script[map_index]["actions"]

        if "original_x_sensitivity" and "original_y_sensitivity" in self.script[map_index] :
            self.original_Xsensitivity = self.script[map_index]["original_x_sensitivity"]
            self.original_Ysensitivity = self.script[map_index]["original_y_sensitivity"]
        else:
            self.original_Xsensitivity = 1.0
            self.original_Ysensitivity = 1.0
      
        # Use perf_counter for higher precision time
        start_time = time.perf_counter()

        for action in actions:
            target_time = action['time']

            # Wait until reaching action timestamp
            while True:
                current_offset = time.perf_counter() - start_time
                if current_offset >= target_time:
                    break

                # Check interrupt condition
                if self.check_for_monthly_card()[0]:
                    raise MacroFailedException

                # next_frame should include tiny sleep to prevent CPU 100% spin
                if self.config.get("Jitter Mode") == "Always":
                    self.external_movement_tick()
                self.next_frame()

            if action['type'] == "delay":
                self.delay_index = map_index
            else:
                self.delay_index = None
                self.execute_action(action)

        self.sleep(2)

    def execute_action(self, action):
        """
        Dispatch action execution, replacing original execute_key_action
        """
        action_type = action['type']

        try:
            if action_type == "mouse_move":
                self.move_mouse_relative(action['dx'], action['dy'], self.original_Xsensitivity, self.original_Ysensitivity)

            elif action_type == "mouse_rotation":
                self.execute_mouse_rotation(action)

            elif action_type in ("mouse_down", "mouse_up"):
                self._handle_mouse_click(action_type, action['button'])

            elif action_type in ("key_down", "key_up"):
                self._handle_keyboard(action_type, action['key'])

            else:
                raise ValueError(f"Unknown action type: {action_type}")

        except Exception as e:
            # Get key info for log, if not exists then N/A
            key_info = action.get('key') or action.get('button') or 'N/A'
            self.log_info(f"Action execution failed -> type: {action_type}, key/btn: {key_info}, Error: {e}")
            raise

    def _handle_mouse_click(self, action_type, button):
        if action_type == "mouse_down":
            self.mouse_down(key=button)
        else:
            self.mouse_up(key=button)

    def _handle_keyboard(self, action_type, key):
        key = normalize_key(key)

        if key == 'f4':
            if action_type == "key_down":
                self.reset_and_transport()
            return

        # 3. Apply dynamic key mapping
        if key == 'lshift':
            key = self.get_dodge_key()
        elif key == 'f':
            key = self._resolve_f_key(action_type)
        elif key == '4':
            key = self.get_spiral_dive_key()
        elif key == 'e':
            key = self.get_combat_key()
        elif key == 'q':
            key = self.get_ultimate_key()

        # 4. Execute actual key operation
        if action_type == "key_down":
            self.send_key_down(key)
        elif action_type == "key_up":
            self.send_key_up(key)

    def _resolve_f_key(self, action_type):
        """
        Resolve F key behavior:
        - Interval >= 3s: Treat as Interact
        - Interval < 3s: Treat as Quick Hack (Original F)
        """
        if action_type == "key_down":
            current_time = time.time()
            last_time = self.last_f_time
            if current_time - last_time >= 3.0:
                # Determined as Interact
                self.last_f_time = current_time
                self.last_f_was_interact = True
                resolved_key = self.get_interact_key()
                return resolved_key
            else:
                # Determined as Quick Hack (Frequent press)
                self.last_f_was_interact = False
                return 'f'
        
        else: # key_up
            # Release corresponding key based on press determination
            if self.last_f_was_interact:
                self.last_f_was_interact = False
                return self.get_interact_key()
            else:
                return 'f'

    def execute_mouse_rotation(self, action):
        direction = action.get("direction", "up")
        angle = action.get("angle", 0)
        sensitivity = action.get("sensitivity", 10)

        pixels = int(angle * sensitivity)

        # Use dict mapping instead of if-elif chain
        direction_map = {"left": (-pixels, 0), "right": (pixels, 0), "up": (0, -pixels), "down": (0, pixels)}

        if direction not in direction_map:
            logger.warning(f"Unknown mouse direction: {direction}")
            return

        dx, dy = direction_map[direction]
        self.move_mouse_relative(dx, dy, self.original_Xsensitivity, self.original_Ysensitivity)
        logger.debug(f"Mouse rotation: {direction}, Angle: {angle}, Pixels: {pixels}")


def normalize_key(key: str) -> str:
    """
    Normalize key name
    """
    if not isinstance(key, str):
        return key

    key_lower = key.lower()
    if key_lower == 'shift':
        return 'lshift'
    if key_lower == 'ctrl':
        return 'lcontrol'
    return key
