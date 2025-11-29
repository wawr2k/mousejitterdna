from qfluentwidgets import FluentIcon
import time

from ok import Logger, TaskDisabledException
from src.tasks.CommissionsTask import CommissionsTask, QuickMoveTask, Mission, _default_movement
from src.tasks.BaseCombatTask import BaseCombatTask
from src.tasks.DNAOneTimeTask import DNAOneTimeTask

logger = Logger.get_logger(__name__)

DEFAULT_ACTION_TIMEOUT = 10


class AutoExploration(DNAOneTimeTask, CommissionsTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.name = "自动探险"
        self.description = "半自动"
        self.group_name = "半自动"
        self.group_icon = FluentIcon.VIEW

        self.default_config.update({
            '轮次': 3,
        })

        self.setup_commission_config()

        self.config_description.update({
            '轮次': '打几个轮次',
            '超时时间': '超时后将发出提示',
        })

        self.action_timeout = DEFAULT_ACTION_TIMEOUT
        self.quick_move_task = QuickMoveTask(self)
        self.external_movement = _default_movement
        self._external_config = None
        self.skill_tick = self.create_skill_ticker()
        self._merged_config_cache = None

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
        self.external_movement = _default_movement
        try:
            return self.do_run()
        except TaskDisabledException:
            pass
        except Exception as e:
            logger.error("AutoExploration error", e)
            raise

    def do_run(self):
        self.init_all()
        self.load_char()

        if self.external_movement is not _default_movement and self.in_team():
            self.open_in_mission_menu()

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
                self.log_info("任务中止")
                self.quit_mission()
            elif _status == Mission.CONTINUE:
                self.log_info("任务继续")
                self.init_for_next_round()
                self.wait_until(self.in_team, time_out=DEFAULT_ACTION_TIMEOUT)
                self.sleep(2)
                self.handle_mission_start()

            self.sleep(0.1)

    def init_all(self):
        self.init_for_next_round()
        self.skill_tick.reset()
        self.current_round = 0

    def init_for_next_round(self):
        self.init_runtime_state()

    def init_runtime_state(self):
        self.runtime_state = {"start_time": 0, "wait_next_round": False}

    def handle_in_mission(self):
        if self.find_serum():
            if self.runtime_state["start_time"] == 0:
                self.runtime_state["start_time"] = time.time()
                self.quick_move_task.reset()
            
            if not self.runtime_state["wait_next_round"] and time.time() - self.runtime_state["start_time"] >= self.config.get("超时时间", 120):
                if self.external_movement is not _default_movement:
                    self.log_info("任务超时")
                    self.open_in_mission_menu()
                    return
                else:
                    self.log_info_notify("任务超时")
                    self.soundBeep()
                    self.runtime_state["wait_next_round"] = True
            
            if not self.runtime_state["wait_next_round"]:
                self.skill_tick()
        else:
            if self.runtime_state["start_time"] > 0:
                self.init_runtime_state()
            self.quick_move_task.run()

    def handle_mission_start(self):
        if self.external_movement is not _default_movement:
            self.log_info("任务开始")
            self.external_movement()
            self.log_info(f"外部移动执行完毕，等待战斗开始，{DEFAULT_ACTION_TIMEOUT+10}秒后超时")
            if not self.wait_until(self.find_serum, time_out=DEFAULT_ACTION_TIMEOUT+10):
                self.log_info("超时重开")
                self.open_in_mission_menu()
            else:
                self.log_info("战斗开始")
        else:
            self.log_info_notify("任务开始")
            self.soundBeep()
        
    def stop_func(self):
        self.get_round_info()
        if self.current_round >= self.config.get("轮次", 3):
            return True

    def find_serum(self):
        return bool(self.find_one("serum_icon"))
