import pygame.font


class Button:
    """为游戏创建按钮的类"""

    def __init__(self, ai_game):
        """初始化按钮的属性"""
        self.screen = ai_game.screen
        self.settings = ai_game.settings
        self.screen_rect = self.screen.get_rect()

        # 加载飞船图像并获取其外接矩形
        self.image = pygame.image.load('images/开始按钮.png')
        # 调整飞船大小（设置为屏幕宽度的1/20）
        ship_width = self.settings.screen_width // 3
        ship_height = int(self.image.get_height() * (ship_width / self.image.get_width()))
        self.image = pygame.transform.scale(self.image, (ship_width, ship_height))

        self.rect = self.image.get_rect()

        # 创建按钮的rect对象，并使其居中
        self.rect.center = self.screen_rect.center

    def draw_button(self):
        """绘制开始按钮"""
        self.screen.blit(self.image, self.rect)
