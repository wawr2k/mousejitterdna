from qfluentwidgets import FluentIcon
import time

from ok import Logger, TaskDisabledException
from src.tasks.DNAOneTimeTask import DNAOneTimeTask
from src.tasks.BaseCombatTask import BaseCombatTask
from src.tasks.CommissionsTask import CommissionsTask, Mission, QuickMoveTask, _default_movement

logger = Logger.get_logger(__name__)

DEFAULT_ACTION_TIMEOUT = 10


class AutoDefence(DNAOneTimeTask, CommissionsTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.name = "Auto Defence"
        self.description = "Semi-Auto"
        self.group_name = "Semi-Auto"
        self.group_icon = FluentIcon.VIEW

        self.default_config.update({
            'Rounds': 3,
        })

        self.setup_commission_config()

        self.config_description.update({
            "Rounds": "Number of rounds",
            "Timeout": "Notify after wave timeout",
        })

        self.action_timeout = DEFAULT_ACTION_TIMEOUT
        self.quick_move_task = QuickMoveTask(self)
        self.external_movement = _default_movement
        self._external_config = None
        self._merged_config_cache = None
        self.skill_tick = self.create_skill_ticker()
        self.external_movement_tick = self.create_external_movement_ticker()

    @property
    def config(self):
        if self.external_movement == _default_movement:
            return super().config
        else:
            if self._merged_config_cache is None:
                self._merged_config_cache = super().config.copy()
            self._merged_config_cache.update(self._external_config)
            return self._merged_config_cache

    def config_external_movement(self, func: callable, config: dict):
        if callable(func):
            self.external_movement = func
        else:
            self.external_movement = _default_movement
        self._merged_config_cache = None
        self._external_config = config

    def run(self):
        DNAOneTimeTask.run(self)
        self.move_mouse_to_safe_position(save_current_pos=False)
        self.set_check_monthly_card()
        self.ensure_game_focused()
        self.external_movement = _default_movement
        try:
            return self.do_run()
        except TaskDisabledException:
            pass
        except Exception as e:
            logger.error("AutoDefence error", e)
            raise

    def do_run(self):
        self.init_all()
        self.load_char()

        if self.external_movement is not _default_movement and self.in_team():
            self.open_in_mission_menu()

        while True:
            if self.in_team():
                self.handle_in_mission()
                self.external_movement_tick()

            _status = self.handle_mission_interface(stop_func=self.stop_func)
            if _status == Mission.START:
                self.wait_until(self.in_team, time_out=30)
                self.sleep(2)
                self.init_all()
                self.handle_mission_start()
            elif _status == Mission.STOP:
                self.log_info("Task Stopped")
                self.quit_mission()
            elif _status == Mission.CONTINUE:
                self.log_info("Task Continued")
                self.init_for_next_round()
                self.wait_until(self.in_team, time_out=DEFAULT_ACTION_TIMEOUT)

            self.sleep(0.1)

    def init_all(self):
        self.init_for_next_round()
        self.skill_tick.reset()
        self.external_movement_tick.reset()
        self.current_round = 0

    def init_for_next_round(self):
        self.init_runtime_state()

    def init_runtime_state(self):
        self.runtime_state = {"wave_start_time": 0, "wave": -1, "wait_next_wave": False}
        self.reset_wave_info()

    def handle_in_mission(self):
        """处理在副本中的逻辑"""
        self.get_wave_info()
        if self.current_wave != -1:
            # 如果是新的波次，重置状态
            if self.current_wave != self.runtime_state["wave"]:
                self.runtime_state.update(
                    {"wave": self.current_wave, "wave_start_time": time.time(), "wait_next_wave": False})
                self.quick_move_task.reset()

            # Check if wave timeout
            if not self.runtime_state["wait_next_wave"] and time.time() - self.runtime_state[
                "wave_start_time"] >= self.config.get("Timeout", 120):
                if self.external_movement is not _default_movement:
                    self.log_info("Task Timeout")
                    self.open_in_mission_menu()
                    return
                else:
                    self.log_info_notify("Task Timeout")
                    self.soundBeep()
                    self.runtime_state["wait_next_wave"] = True

            # If not timeout, use skill
            if not self.runtime_state["wait_next_wave"]:
                self.skill_tick()
                self.external_movement_tick()
        else:
            if self.runtime_state["wave"] > 0:
                self.init_runtime_state()
            # If not in combat wave, execute move task
            self.quick_move_task.run()

    def handle_mission_start(self):
        """Handle mission start logic"""
        if self.external_movement is not _default_movement:
            self.log_info("Task Started, executing external movement")
            self.external_movement()
            self.log_info(f"External movement finished, waiting for combat start, timeout in {DEFAULT_ACTION_TIMEOUT+10}s")
            if not self.wait_until(lambda: self.current_wave != -1, post_action=self.get_wave_info,
                                   time_out=DEFAULT_ACTION_TIMEOUT+10):
                self.log_info("Timeout waiting for combat start, restarting")
                self.open_in_mission_menu()
            else:
                self.log_info("Combat Started")
        else:
            self.log_info_notify("Task Started")
            self.soundBeep()

    def stop_func(self):
        self.get_round_info()
        n = self.config.get("Rounds", 3)
        if self.current_round >= n:
            return True
