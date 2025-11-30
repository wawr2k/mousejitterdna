from qfluentwidgets import FluentIcon
import time
import random

from ok import Logger, TaskDisabledException
from src.tasks.DNAOneTimeTask import DNAOneTimeTask
from src.tasks.BaseCombatTask import BaseCombatTask
from src.tasks.CommissionsTask import CommissionsTask, Mission

logger = Logger.get_logger(__name__)


class AutoExpulsion(DNAOneTimeTask, CommissionsTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.name = "Auto Expulsion"
        self.description = "Full Auto"
        self.group_name = "Full-Auto"
        self.group_icon = FluentIcon.CAFE

        self.default_config.update({
            "Random Walk": False,
            "Repeat Count": 999,
            "AFK Mode": "Reset Position at Start",
            "Move Forward Duration": 0.0
        })

        self.setup_commission_config()
        keys_to_remove = ["Enable Auto Resonance"]
        for key in keys_to_remove:
            self.default_config.pop(key, None)

        self.config_description.update({
            "Random Walk": "Randomly move during mission",
            "Move Forward Duration": "Seconds to move forward at start"
        })
        self.config_type["AFK Mode"] = {
            "type": "drop_down",
            "options": ["Reset Position at Start", "Move Forward"],
        }

        self.default_config.pop("Enable Auto Resonance", None)
        self.action_timeout = 10
        
        self.skill_tick = self.create_skill_ticker()
        self.random_walk_tick = self.create_random_walk_ticker()
        self.external_movement_tick = self.create_external_movement_ticker()

    def run(self):
        DNAOneTimeTask.run(self)
        self.move_mouse_to_safe_position(save_current_pos=False)
        self.set_check_monthly_card()
        try:
            return self.do_run()
        except TaskDisabledException:
            pass
        except Exception as e:
            logger.error("AutoExpulsion error", e)
            raise

    def do_run(self):
        self.init_all()
        self.load_char()
        self.count = 0
        while True:
            if self.in_team():
                self.handle_in_mission()

            _status = self.handle_mission_interface(stop_func=self.stop_func)
            if _status == Mission.START:
                self.wait_until(self.in_team, time_out=30)
                self.sleep(2)
                self.init_all()
                self.handle_mission_start()
            elif _status == Mission.STOP:
                pass
            elif _status == Mission.CONTINUE:
                pass

            self.sleep(0.1)

    def init_all(self):
        self.init_for_next_round()
        self.skill_tick.reset()
        self.external_movement_tick.reset()
        self.current_round = 0

    def init_for_next_round(self):
        self.init_runtime_state()

    def init_runtime_state(self):
        self.runtime_state = {"start_time": 0}
        self.random_walk_tick.reset()

    def handle_in_mission(self):
        if self.runtime_state["start_time"] == 0:
            self.move_on_begin()
            self.runtime_state["start_time"] = time.time()
            self.count += 1

        if time.time() - self.runtime_state["start_time"] >= self.config.get("Timeout", 120):
            logger.info("Timeout, restarting task...")
            self.give_up_mission()
            self.wait_until(lambda: not self.in_team(), time_out=30, settle_time=1)

        self.random_walk_tick()
        self.skill_tick()
        self.external_movement_tick()

    def handle_mission_start(self):
        if self.count >= self.config.get("Repeat Count", 999):
            self.sleep(1)
            self.open_in_mission_menu()
            self.log_info_notify("Task Terminated")
            if self.config.get("Play Sound Notification", True):
                self.soundBeep()
            return
        self.log_info("Task Started")
    
    def stop_func(self):
        pass

    def move_on_begin(self):
        if self.config.get("AFK Mode") == "Reset Position at Start":
            # Reset plan
            self.reset_and_transport()
            # Anti-stuck
            self.send_key("w", down_time=0.5)
        elif self.config.get("AFK Mode") == "Move Forward":
            if (walk_sec := self.config.get("Move Forward Duration", 0)) > 0:
                self.send_key("w", down_time=walk_sec)

    def create_random_walk_ticker(self):
        """Create a random walk ticker function."""
        last_time = 0

        def tick():
            nonlocal last_time
            if not self.config.get("Random Walk", False):
                return
            
            interval = 3
            duration = 1
            now = time.perf_counter()
            if now - last_time >= interval:
                last_time = now
                direction = random.choice(["w", "a", "s", "d"])
                self.send_key(direction, down_time=duration)

        def reset():
            nonlocal last_time
            last_time = 0

        tick.reset = reset
        return tick
