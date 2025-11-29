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
    """地图识别错误异常"""
    pass


class AutoExploration_Fast(DNAOneTimeTask, CommissionsTask, BaseCombatTask):
    """全自动探险/无尽，感谢群友的行动逻辑"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.group_icon = FluentIcon.CAFE
        self.name = "自动探险/无尽"
        self.description = "全自动"
        self.group_name = "全自动"
        self.default_config.update({
            '轮次': 3,
            '超时时间': 120,
            '解密失败自动重开': True,
            '地图选择': '全部地图',
        })
        self.config_description.update({
            '轮次': '打几个轮次',
            '超时时间': '超时后将发出提示',
            '解密失败自动重开': '不重开时会发出声音提示',
            '地图选择': '选择要自动执行的地图类型',
        })
        self.setup_commission_config()
        keys_to_remove = ["启用自动穿引共鸣"]
        for key in keys_to_remove:
            self.default_config.pop(key, None)
        
        self.action_timeout = DEFAULT_ACTION_TIMEOUT
        self.quick_move_task = QuickMoveTask(self)
        self.external_movement_tick = self.create_external_movement_ticker()
        
    def run(self):
        DNAOneTimeTask.run(self)
        self.move_mouse_to_safe_position(save_current_pos=False)
        self.set_check_monthly_card()
        self.ensure_game_focused()
        try:
            _to_do_task = self.get_task_by_class(AutoExploration)
            _to_do_task.config_external_movement(self.walk_to_aim, self.config)
            return _to_do_task.do_run()
        except TaskDisabledException:
            pass
        except Exception as e:
            logger.error('AutoExploration error', e)
            raise
            
    def walk_to_aim(self):
        """
        主寻路函数：根据识别到的坐标选择路径
        """
        try:
            self.send_key_down("lalt")
            self.sleep(2) # 保持原有的启动延迟

            # 使用 if-elif 结构，优先级清晰，且只执行一个分支
            if self.find_track_point(0.20, 0.54, 0.22, 0.59):
                # 分支1：无电梯
                self.execute_ground_map()
                
            elif self.find_track_point(0.66, 0.67, 0.69, 0.72):
                # 分支2：电梯右
                self.execute_elevator_map()
                
            elif self.find_track_point(0.32, 0.67, 0.35, 0.73):
                # 分支3：电梯左
                self.execute_elevator_map()
                
            elif self.find_track_point(0.50, 0.71, 0.53, 0.76):
                # 分支4：电梯中
                self.execute_platform_map()
            
            else:
                self.log_info("Warning: No map track point matched! Character will not move.")
                self.log_info("Please ensure you are in a supported map or check the map detection.")

        except Exception as e:
            logger.error("Error in walk_to_aim", e)
        finally:
            self.send_key_up("lalt")
            
    def execute_elevator_map(self):
        """执行电梯地图逻辑"""
        self.log_info("识别到电梯地图")
        
        # 移动逻辑...
        self.send_key_down("w")
        self.sleep(2)
        self.external_movement_tick()
        self.send_key_up("w")
        
        # 解密逻辑
        if not self.try_solving_puzzle():
            return

        # 继续移动...
        self.send_key_down("w")
        self.sleep(2)
        self.external_movement_tick()
        self.send_key_up("w")
        
    def execute_platform_map(self):
        """执行平台地图逻辑"""
        self.log_info("识别到平台地图")
        
        # 移动逻辑...
        self.send_key_down("w")
        self.sleep(2)
        self.external_movement_tick()
        self.send_key_up("w")
        
        # 解密逻辑
        if not self.try_solving_puzzle():
            return
            
        # 继续移动...
        self.send_key_down("w")
        self.sleep(2)
        self.external_movement_tick()
        self.send_key_up("w")

    def execute_ground_map(self):
        """执行地面地图逻辑"""
        self.log_info("识别到地面地图")
        
        # 移动逻辑...
        self.send_key_down("w")
        self.sleep(2)
        self.external_movement_tick()
        self.send_key_up("w")
        
        # 解密逻辑
        if not self.try_solving_puzzle():
            return
            
        # 继续移动...
        self.send_key_down("w")
        self.sleep(2)
        self.external_movement_tick()
        self.send_key_up("w")

    def find_track_point(self, x1, y1, x2, y2) -> bool:
        box = self.box_of_screen_scaled(2560, 1440, 2560*x1, 1440*y1, 2560*x2, 1440*y2, name="find_track_point", hcenter=True)
        result = super().find_track_point(threshold=0.7, box=box)
        # 调试信息：记录检测结果
        logger.debug(f"地图检测点 ({x1}, {y1}, {x2}, {y2}) 检测结果: {result}")
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
            if not self.wait_until(self.in_team, time_out = 1.5):           
                if self.config.get("解密失败自动重开", True):                    
                    self.log_info("未成功处理解密，等待重开")
                    self.open_in_mission_menu()
                else:
                    self.log_info_notify("未成功处理解密，请求人工接管")
                    self.soundBeep()
                    self.wait_until(self.in_team, time_out = 60)
                return False               
        return True
