from pathlib import Path

class GameStats:
    """跟踪游戏的统计信息"""
    def __init__(self, ai_game):
        """初始化统计信息"""
        self.settings=ai_game.settings
        self.reset_stats()
        # 在任何情况下都不应重置的最高分
        try:
            self.high_score=int(open('high_score.txt').read())
        except FileNotFoundError:
            self.high_score=0

    def reset_stats(self):
        """初始化在游戏运行期间可能变化的统计信息"""
        self.ships_left=self.settings.ship_limit
        self.score=0
        self.level=1

    def save_high_score(self):
        """将最高分保存到文件中"""
        with open('high_score.txt', 'w') as file_object:
            file_object.write(str(self.high_score))
            file_object.close()