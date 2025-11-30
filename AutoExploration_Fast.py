import time
from ok import Logger, TaskDisabledException
from qfluentwidgets import FluentIcon

from src.tasks.AutoExploration import AutoExploration
from src.tasks.CommissionsTask import CommissionsTask, QuickMoveTask
from src.tasks.DNAOneTimeTask import DNAOneTimeTask
from src.tasks.trigger.AutoMazeTask import AutoMazeTask
from src.tasks.trigger.AutoRouletteTask import AutoRouletteTask
from src.tasks.BaseCombatTask import BaseCombatTask

logger = Logger.get_logger(__name__)
DEFAULT_ACTION_TIMEOUT = 10


class MapDetectionError(Exception):
    """Map detection error exception"""
    pass


class AutoExploration_Fast(DNAOneTimeTask, CommissionsTask, BaseCombatTask):
    """Auto Exploration/Endless, thanks to community logic"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.group_icon = FluentIcon.CAFE
        self.name = "Auto Exploration/Endless"
        self.description = "Full Auto"
        self.group_name = "Full-Auto"
        self.default_config.update({
            'Rounds': 3,
            'Timeout': 120,
            'Restart on Puzzle Fail': True,
            'Map Selection': 'All Maps',
            "Jitter Mode": "Disabled",
            "External Movement Min Delay": 4.0,
            "External Movement Max Delay": 8.0,
            "External Movement Jitter Amount": 20,
        })
        self.config_description.update({
            'Rounds': 'Number of rounds to play',
            'Timeout': 'Notify after timeout',
            'Restart on Puzzle Fail': 'Play sound if not restarting',
            'Map Selection': 'Select map type to auto-execute',
            "Jitter Mode": "Control when mouse jitter happens (Disabled, Always, Combat Only)",
            "External Movement Min Delay": "Minimum interval for random mouse movement (seconds)",
            "External Movement Max Delay": "Maximum interval for random mouse movement (seconds)",
            "External Movement Jitter Amount": "Maximum pixel distance to move mouse (default: 20)",
        })
        self.setup_commission_config()
        keys_to_remove = ["Enable Auto Resonance"]
        for key in keys_to_remove:
            self.default_config.pop(key, None)
        
        # Set map selection dropdown
        self.config_type["Map Selection"] = {
            "type": "drop_down",
            "options": ["All Maps", "Exploration Elevator", "Exploration Platform", "Exploration Ground"],
        }
        self.config_type["Jitter Mode"] = {
            "type": "drop_down",
            "options": ["Disabled", "Always", "Combat Only"],
        }
        
        self.action_timeout = DEFAULT_ACTION_TIMEOUT
        self.quick_move_task = QuickMoveTask(self)
        self.external_movement_tick = self.create_external_movement_ticker()
        
        # Map detection points and execution function mapping
        self.map_configs = {
            "Exploration Elevator": {
                "track_point": (0.50, 0.69, 0.56, 0.77),
                "execute_func": self.execute_elevator_map
            },
            "Exploration Platform": {
                "track_point": (0.29, 0.54, 0.34, 0.62),
                "execute_func": self.execute_platform_map
            },
            "Exploration Ground": {
                "track_point": (0.44, 0.28, 0.49, 0.34),
                "execute_func": self.execute_ground_map
            }
        }

    def run(self):
        DNAOneTimeTask.run(self)
        self.move_mouse_to_safe_position(save_current_pos=False)
        self.set_check_monthly_card()
        self.ensure_game_focused()
        try:
            _to_do_task = self.get_task_by_class(AutoExploration)
            _to_do_task.config_external_movement(self.walk_to_aim, self.config)
            while True:
                try:
                    return _to_do_task.do_run()
                except MapDetectionError as e:
                    # Map detection error, log and retry
                    self.log_info(f"Map detection error: {e}, restarting task")
        except TaskDisabledException:
            pass
        except Exception as e:
            logger.error('AutoExploration error', e)
            raise

    def walk_to_aim(self):
        map_selection = self.config.get("Map Selection", "All Maps")
        
        # Detect current map type
        current_map = self.detect_current_map()
        
        # If unknown map detected, raise error
        if current_map == "Unknown Map":
            raise MapDetectionError("Unable to identify current map type")
        
        # If specific map selected but current is different, raise error
        if map_selection != "All Maps" and current_map != map_selection:
            raise MapDetectionError(f"Current map ({current_map}) does not match selected map ({map_selection})")
        
        # Execute corresponding map movement logic
        if current_map in self.map_configs:
            self.log_info(f"Map type identified: {current_map}, starting movement logic")
            return self.map_configs[current_map]["execute_func"]()
        else:
            # Should not happen as current_map comes from map_configs
            raise MapDetectionError(f"Map config inconsistency: Detected map ({current_map}) but no execution function found")
    
    def detect_current_map(self):
        """Detect current map type"""
        detected_maps = []
        
        for map_name, config in self.map_configs.items():
            x1, y1, x2, y2 = config["track_point"]
            if self.find_track_point(x1, y1, x2, y2):
                detected_maps.append(map_name)
                self.log_info(f"Map marker detected: {map_name} at ({x1}, {y1}, {x2}, {y2})")
        
        if len(detected_maps) == 0:
            logger.warning("Map detection failed: No known map markers detected")
            return "Unknown Map"
        elif len(detected_maps) == 1:
            return detected_maps[0]
        else:
            # Multiple markers detected, log warning and return first
            logger.warning(f"Map detection conflict: Multiple markers detected {detected_maps}, using first one")
            return detected_maps[0]
    
    def execute_elevator_map(self):
        """Execute Exploration Elevator map movement logic"""
        self.log_info("Executing Exploration Elevator map movement")
        self.reset_and_transport()
        self.send_key_down("lalt")
        self.sleep(0.05)
        self.send_key_down("a")
        self.sleep(0.1)
        self.send_key_down(self.get_dodge_key())
        self.sleep(0.8)
        self.send_key(self.get_dodge_key(), down_time=0.2,after_sleep=0.8)
        self.send_key(self.get_dodge_key(), down_time=0.2,after_sleep=1.6)
        
        if self.config.get("Jitter Mode") == "Always":
            self.external_movement_tick()
            
        self.send_key_down("s")
        self.send_key_up("a")
        self.sleep(0.3)
        self.send_key("space", down_time=0.1,after_sleep=0.4)
        self.send_key("space", down_time=0.1,after_sleep=0.4)
        self.send_key("space", down_time=0.1,after_sleep=0.7)
        self.send_key_up(self.get_dodge_key())
        self.send_key_up("s")
        self.sleep(0.6)
        self.send_key(self.get_interact_key(), down_time=0.1,after_sleep=0.8)
        if not self.try_solving_puzzle():
            return True
        self.send_key_down("a")
        self.sleep(0.1)
        self.send_key(self.get_dodge_key(), down_time=0.2,after_sleep=0.6)
        self.send_key_down(self.get_dodge_key())
        self.sleep(0.9)
        self.send_key_down("w")
        self.sleep(0.2)
        self.send_key_up("a")
        self.sleep(0.1)
        self.send_key_up(self.get_dodge_key())
        self.send_key_up("w")
        self.sleep(0.2)
        self.send_key_up("lalt")
        return True
    
    def execute_platform_map(self):
        """Execute Exploration Platform map movement logic"""
        self.log_info("Executing Exploration Platform map movement")
        self.send_key_down("lalt")
        self.sleep(0.05)
        self.send_key_down("w")
        self.sleep(0.1)
        self.send_key_down(self.get_dodge_key())
        self.sleep(1.2)
        
        if self.config.get("Jitter Mode") == "Always":
            self.external_movement_tick()
            
        self.send_key(self.get_dodge_key(),  down_time=0.2,after_sleep=0.3)
        self.send_key_down(self.get_dodge_key())
        self.sleep(0.1)
        self.send_key_down("a")
        self.sleep(0.1)
        self.send_key("space", down_time=0.1,after_sleep=0.1)
        self.send_key(self.get_dodge_key(),  down_time=0.2,after_sleep=0.3)
        self.send_key("space", down_time=0.1,after_sleep=0.7)
        self.send_key_up(self.get_dodge_key())
        self.send_key_up("w")
        self.sleep(0.1)
        self.send_key_up("a")
        self.sleep(0.6)
        self.send_key(self.get_interact_key(), down_time=0.1,after_sleep=0.8)
        if not self.try_solving_puzzle():
            return True
        self.send_key_down("d")
        self.sleep(0.1)
        self.send_key(self.get_dodge_key(),  down_time=0.2)
        self.sleep(0.1)
        self.send_key_up("d")
        self.sleep(0.1)
        self.send_key_down("s")
        self.sleep(0.1)
        self.send_key_up(self.get_dodge_key())
        self.send_key_up("s")
        self.sleep(0.2)
        self.middle_click()
        self.send_key_up("lalt")
        return True
    
    def execute_ground_map(self):
        """Execute Exploration Ground map movement logic"""
        self.log_info("Executing Exploration Ground map movement")
        self.reset_and_transport()
        self.send_key_down("lalt")
        self.sleep(0.05)
        self.send_key_down("a")
        self.sleep(0.1)
        self.send_key(self.get_dodge_key(), down_time=1.1)
        
        if self.config.get("Jitter Mode") == "Always":
            self.external_movement_tick()
            
        self.send_key_up("a")
        self.sleep(0.6)
        self.send_key(self.get_interact_key(), down_time=0.1,after_sleep=0.8)
        if not self.try_solving_puzzle():
            return True
        self.send_key('d',down_time=0.8,after_sleep=0.1)
        self.middle_click()
        self.send_key_up("lalt")
        return True
            
            
    def find_track_point(self, x1, y1, x2, y2) -> bool:
        box = self.box_of_screen_scaled(2560, 1440, 2560*x1, 1440*y1, 2560*x2, 1440*y2, name="find_track_point", hcenter=True)
        result = super().find_track_point(threshold=0.7, box=box)
        # Debug info: record detection result
        logger.debug(f"Map detection point ({x1}, {y1}, {x2}, {y2}) result: {result}")
        return result
        
    def try_solving_puzzle(self):
        maze_task = self.get_task_by_class(AutoMazeTask)
        roulette_task = self.get_task_by_class(AutoRouletteTask)
        if not self.wait_until(
            self.in_team, 
            post_action = lambda: self.send_key(self.get_interact_key(), after_sleep=0.1),
            time_out = 1.5
        ):
            maze_task.run()
            roulette_task.run()
            if not self.wait_until(self.in_team, time_out=1.5):           
                if self.config.get("Restart on Puzzle Fail", True):                    
                    self.log_info("Puzzle solving failed, waiting for restart")
                    self.open_in_mission_menu()
                else:
                    self.log_info_notify("Puzzle solving failed, requesting manual intervention")
                    if self.config.get("Play Sound Notification", True):
                        self.soundBeep()
                    self.wait_until(self.in_team, time_out = 60)
                return False               
        return True
