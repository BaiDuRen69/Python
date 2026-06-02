from pathlib import Path
import os
import sys


class GameStats:
    """跟踪游戏的统计信息"""

    def __init__(self, ai_game):
        """初始化统计信息"""
        self.settings = ai_game.settings
        self.reset_stats()
        # 在任何情况下都不应重置的最高分
        # 使用绝对路径，兼容打包后的环境
        self.high_score_file = self._get_data_path('high_score.txt')
        try:
            if self.high_score_file.exists():
                self.high_score = int(self.high_score_file.read_text())
            else:
                self.high_score = 0
        except (ValueError, FileNotFoundError):
            self.high_score = 0

    def _get_data_path(self, filename):
        """获取数据文件的绝对路径（兼容开发环境和打包环境）"""
        if getattr(sys, 'frozen', False):
            # 打包后的环境：使用 exe 所在目录
            base_path = Path(sys.executable).parent
        else:
            # 开发环境：使用项目根目录
            base_path = Path(__file__).parent.parent.parent
        
        # 数据文件保存在用户文档目录，避免权限问题
        import getpass
        try:
            username = getpass.getuser()
            save_dir = Path(f"C:/Users/{username}/Documents/AlienInvasion")
        except Exception:
            # 如果获取用户名失败，使用当前目录
            save_dir = base_path
        
        # 确保目录存在
        save_dir.mkdir(parents=True, exist_ok=True)
        
        return save_dir / filename

    def reset_stats(self):
        """初始化在游戏运行期间可能变化的统计信息"""
        self.ships_left = self.settings.ship_limit
        self.score = 0
        self.level = 1

    def save_high_score(self):
        """将最高分保存到文件中"""
        try:
            self.high_score_file.write_text(str(self.high_score))
        except (PermissionError, OSError) as e:
            print(f"Failed to save high score: {e}")
