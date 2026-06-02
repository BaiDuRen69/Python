import sys
from time import sleep

import pygame

import settings
import ship
from game_stats import GameStats
from bullet import Bullet
from alien import Alien
from button import Button
from scoreboard import Scoreboard


class AlienInvasion:
    """管理游戏资源和行为的类"""

    def __init__(self):
        """初始化游戏并创建游戏资源"""
        # 初始化背景
        pygame.init()
        # 创建时钟对象，用于控制游戏帧率
        self.clock = pygame.time.Clock()
        # 创建设置对象，用于管理游戏设置
        self.settings = settings.Settings()
        # 创建一个显示窗口，用于绘制游戏元素
        # 全屏模式运行
        # self.screen = pygame.display.set_mode(
        #     (self.settings.screen_width, self.settings.screen_height), pygame.FULLSCREEN)
        # 非全屏模式运行
        self.screen = pygame.display.set_mode((self.settings.screen_width, self.settings.screen_height))
        # 设置游戏窗口标题
        pygame.display.set_caption("Alien Invasion")

        # 创建存储游戏统计信息的实例，并创建记分牌
        self.stats = GameStats(self)
        self.sb = Scoreboard(self)

        # 创建飞船
        self.ship = ship.Ship(self)
        # 创建一个用于存储子弹的编组
        self.bullets = pygame.sprite.Group()
        # 创建一个用于存储外星人的编组
        self.aliens = pygame.sprite.Group()
        self._create_fleet()

        # 游戏启动后处于活动状态
        self.game_active = False

        # 创建开始按钮
        self.play_button = Button(self, "Play")

    def run_game(self):
        """开始游戏的主循环"""
        while True:
            # 监听键盘和鼠标事件
            self._check_events()

            if self.game_active:
                self.ship.update()
                self._update_aliens()
                # 删除已消失的子弹
                self._update_bullets()

            # 每次循环都重绘屏幕
            self._update_screen()
            # 设置游戏帧率为60
            self.clock.tick(60)

    def _check_events(self):
        """响应按键和鼠标事件"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.stats.save_high_score()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                self._check_keydown_events(event)
            elif event.type == pygame.KEYUP:
                self._check_keyup_events(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._check_play_button(pygame.mouse.get_pos())

    def _check_keydown_events(self, event):
        """检测按键按下"""
        if self.game_active:
            if event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                # 向右移动飞船
                self.ship.moving_right = True
            elif event.key == pygame.K_LEFT or event.key == pygame.K_a:
                # 向左移动飞船
                self.ship.moving_left = True
            elif event.key == pygame.K_ESCAPE:
                sys.exit()
            elif event.key == pygame.K_SPACE:
                self._fire_bullet()
            elif event.key==pygame.K_r:
                self._start_game()

    def _check_keyup_events(self, event):
        """检测按键松开"""
        if event.key == pygame.K_RIGHT or event.key == pygame.K_d:
            # 向右移动飞船
            self.ship.moving_right = False
        elif event.key == pygame.K_LEFT or event.key == pygame.K_a:
            # 向左移动飞船
            self.ship.moving_left = False

    def _check_play_button(self, mouse_pos):
        """在玩家单机Play按钮时开始新游戏"""
        button_clicked=self.play_button.rect.collidepoint(mouse_pos)
        if button_clicked and not self.game_active:
            # 还原游戏设置
            self._start_game()
            # 隐藏光标
            pygame.mouse.set_visible(False)

    def _check_fleet_edges(self):
        """在有外星人到达边缘时采取的措施,向下移动并转向"""
        for alien in self.aliens.sprites():
            if alien.check_edges():
                self._change_fleet_direction()
                break

    def _check_bullet_alien_collisions(self):
        """响应子弹和外星人的碰撞"""
        # 删除发生碰撞的子弹和外星人
        collisions = pygame.sprite.groupcollide(self.bullets, self.aliens, True, True)

        if collisions:
            for aliens in collisions.values():
                self.stats.score += self.settings.alien_points * len(aliens)
            self.sb.prep_score()
            self.sb.check_high_score()

        if not self.aliens:
            # 删除现有的子弹并创建一个新的外星舰队
            self.bullets.empty()
            self._create_fleet()
            self.settings.increase_speed()

            # 提高等级
            self.stats.level += 1
            self.sb.prep_level()

    def _check_aliens_bottom(self):
        """检查是否有外星人到了屏幕下边缘"""
        for alien in self.aliens.sprites():
            if alien.rect.bottom >= self.screen.get_rect().bottom:
                # 像飞船被撞到一样进行处理
                self._ship_hit()
                break

    def _update_screen(self):
        """更新屏幕上的图像，并切换到新屏幕"""
        self.screen.fill(self.settings.bg_color)
        for bullet in self.bullets.sprites():
            bullet.draw_bullet()
        self.ship.blitme()
        self.aliens.draw(self.screen)

        # 显示得分
        self.sb.show_score()

        # 如果游戏处于非活动状态，就绘制开始按钮
        if not self.game_active:
            self.play_button.draw_button()
        # 让最近绘制的屏幕可见
        pygame.display.flip()

    def _update_bullets(self):
        """更新子弹的位置，并删除已消失的子弹"""
        # 更新子弹的位置
        self.bullets.update()
        # 删除已消失的子弹
        for bullet in self.bullets.copy():
            if bullet.rect.bottom <= 0:
                self.bullets.remove(bullet)
        self._check_bullet_alien_collisions()

    def _update_aliens(self):
        """检查是否有外星人位于屏幕边缘，并更新整个外星舰队的位置"""
        self._check_fleet_edges()
        self.aliens.update()

        # 检查外星人和飞船之间的碰撞
        if pygame.sprite.spritecollideany(self.ship, self.aliens):
            self._ship_hit()

        # 检查是否有外星人到达屏幕底端
        self._check_aliens_bottom()

    def _fire_bullet(self):
        """创建一颗子弹，并将其加入编组bullets"""
        if len(self.bullets) < self.settings.bullets_allowed:
            self.bullets.add(Bullet(self))

    def _create_fleet(self):
        """创建一个外星人舰队"""
        # 创建一个外星人，在不断添加，直到没有空间添加外星人
        # 外星人间距为外星人宽度和外星人的高度
        alien = Alien(self)
        alien_width, alien_height = alien.rect.size

        current_x, current_y = alien_width, alien_height
        while current_y < (self.settings.screen_height - 6 * alien_height):
            while current_x < (self.settings.screen_width - 2 * alien_width):
                self._create_alien(current_x, current_y)
                current_x += 2 * alien_width

            # 添加一行外星人后，重置x值并递增y值
            current_x = alien_width
            current_y += int(alien_height * 1.5)

    def _create_alien(self, x_position, y_position):
        """创建一个外星人并将其放在当前行中"""
        new_alien = Alien(self)
        new_alien.rect.x = x_position
        new_alien.rect.y = y_position
        new_alien.x = float(x_position)
        self.aliens.add(new_alien)

    def _change_fleet_direction(self):
        """将整个外星舰队向下移动，并改变他们的方向"""
        for alien in self.aliens.sprites():
            alien.rect.y += self.settings.fleet_drop_speed
        self.settings.fleet_direction *= -1

    def _ship_hit(self):
        """响应飞船和外星人的碰撞"""
        if self.stats.ships_left > 0:
            # 将ships_left减1并更新记分牌
            self.stats.ships_left -= 1
            self.sb.prep_ships()

            # 清空外星人列表和子弹列表
            self.aliens.empty()
            self.bullets.empty()
            self._create_fleet()
            self.ship.center_ship()

            # 暂停
            sleep(0.5)
        else:
            self.game_active = False
            pygame.mouse.set_visible(True)

    def _start_game(self):
        # 重置游戏统计信息
        self.stats.reset_stats()
        self.game_active = True

        # 清空外星人编组和子弹编组
        self.bullets.empty()
        self.aliens.empty()

        # 创建一群新的外星人，并将飞船放在屏幕底部中央
        self._create_fleet()
        self.ship.center_ship()

        self.settings.initialize_dynamic_settings()
        self.sb.prep_score()
        self.sb.prep_level()
        self.sb.prep_ships()




if __name__ == '__main__':
    # 创建游戏实例并运行游戏
    ai = AlienInvasion()
    ai.run_game()
