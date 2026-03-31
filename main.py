from __future__ import annotations

import random
import sys
from dataclasses import dataclass

import pygame

from controls import move_player, move_player_with_joystick
from functions import (
    music_background,
    show_game_over,
    show_game_win,
    show_level_complete,
)
from menu import show_menu

from classes.bosses import Boss1, Boss2, Boss3
from classes.bullets import Bullet
from classes.campaign import MAX_LEVELS, get_level_config
from classes.constants import FPS, HEIGHT, SHOOT_DELAY, WIDTH
from classes.display import create_game_display
from classes.enemies import Enemy1, Enemy2
from classes.explosions import Explosion, Explosion2
from classes.frontend import FrontendSession, create_frontend_session, draw_modal_overlay, draw_panel
from classes.meteors import BlackHole, Meteors, Meteors2
from classes.player import Player
from classes.progress import ProgressData, load_progress, record_level_completion, record_score
from classes.refill import BulletRefill, MultiShotBonus, ExtraScore, HealthRefill


MAX_PLAYER_LIFE = 200
MAX_BULLETS = 200


@dataclass(frozen=True)
class Assets:
    backgrounds: tuple[pygame.Surface, ...]
    explosion_images: tuple[pygame.Surface, ...]
    explosion2_images: tuple[pygame.Surface, ...]
    explosion3_images: tuple[pygame.Surface, ...]
    enemy1_images: tuple[pygame.Surface, ...]
    enemy2_images: tuple[pygame.Surface, ...]
    boss_images: dict[str, pygame.Surface]
    health_refill_image: pygame.Surface
    bullet_refill_image: pygame.Surface
    multishot_image: pygame.Surface
    meteor_images: tuple[pygame.Surface, ...]
    meteor2_images: tuple[pygame.Surface, ...]
    extra_score_image: pygame.Surface
    black_hole_images: tuple[pygame.Surface, ...]
    life_bar_image: pygame.Surface
    bullet_bar_image: pygame.Surface
    warning_sound: pygame.mixer.Sound


@dataclass
class BossState:
    boss_type: str | None = None
    health: int = 0
    max_health: int = 0
    spawned: bool = False


@dataclass
class RunResult:
    progress: ProgressData
    quit_requested: bool = False


def load_assets() -> Assets:
    backgrounds = (
        pygame.image.load("images/bg/background.jpg").convert(),
        pygame.image.load("images/bg/background2.png").convert(),
        pygame.image.load("images/bg/background3.png").convert(),
        pygame.image.load("images/bg/background4.png").convert(),
    )
    explosion_images = tuple(
        pygame.image.load(f"images/explosion/explosion{i}.png").convert_alpha()
        for i in range(8)
    )
    explosion2_images = tuple(
        pygame.image.load(f"images/explosion2/explosion{i}.png").convert_alpha()
        for i in range(18)
    )
    explosion3_images = tuple(
        pygame.image.load(f"images/explosion3/explosion{i}.png").convert_alpha()
        for i in range(18)
    )
    enemy1_images = (
        pygame.image.load("images/enemy/enemy1_1.png").convert_alpha(),
        pygame.image.load("images/enemy/enemy1_2.png").convert_alpha(),
        pygame.image.load("images/enemy/enemy1_3.png").convert_alpha(),
    )
    enemy2_images = (
        pygame.image.load("images/enemy/enemy2_1.png").convert_alpha(),
        pygame.image.load("images/enemy/enemy2_2.png").convert_alpha(),
    )
    boss_images = {
        "boss1": pygame.image.load("images/boss/boss1.png").convert_alpha(),
        "boss2": pygame.image.load("images/boss/boss2_1.png").convert_alpha(),
        "boss3": pygame.image.load("images/boss/boss3.png").convert_alpha(),
    }
    warning_sound = pygame.mixer.Sound("game_sounds/warning.mp3")
    warning_sound.set_volume(0.35)

    return Assets(
        backgrounds=backgrounds,
        explosion_images=explosion_images,
        explosion2_images=explosion2_images,
        explosion3_images=explosion3_images,
        enemy1_images=enemy1_images,
        enemy2_images=enemy2_images,
        boss_images=boss_images,
        health_refill_image=pygame.image.load("images/refill/health_refill.png").convert_alpha(),
        bullet_refill_image=pygame.image.load("images/refill/bullet_refill.png").convert_alpha(),
        multishot_image=pygame.image.load("images/refill/double_refill.png").convert_alpha(),
        meteor_images=(
            pygame.image.load("images/meteors/meteor_1.png").convert_alpha(),
            pygame.image.load("images/meteors/meteor_2.png").convert_alpha(),
            pygame.image.load("images/meteors/meteor_3.png").convert_alpha(),
            pygame.image.load("images/meteors/meteor_4.png").convert_alpha(),
        ),
        meteor2_images=(
            pygame.image.load("images/meteors/meteor2_1.png").convert_alpha(),
            pygame.image.load("images/meteors/meteor2_2.png").convert_alpha(),
            pygame.image.load("images/meteors/meteor2_3.png").convert_alpha(),
            pygame.image.load("images/meteors/meteor2_4.png").convert_alpha(),
        ),
        extra_score_image=pygame.image.load("images/score/score_coin.png").convert_alpha(),
        black_hole_images=(
            pygame.image.load("images/hole/black_hole.png").convert_alpha(),
            pygame.image.load("images/hole/black_hole2.png").convert_alpha(),
        ),
        life_bar_image=pygame.image.load("images/life_bar.png").convert_alpha(),
        bullet_bar_image=pygame.image.load("images/bullet_bar.png").convert_alpha(),
        warning_sound=warning_sound,
    )


class GameSession:
    def __init__(
        self,
        screen: pygame.Surface,
        progress: ProgressData,
        starting_level: int,
        frontend_session: FrontendSession,
    ):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.progress = progress
        self.assets = load_assets()
        self.frontend_session = frontend_session

        self.run_score = 0
        self.level_score = 0
        self.player = Player()
        self.player_life = MAX_PLAYER_LIFE
        self.bullet_counter = MAX_BULLETS
        self.hi_score = max(progress.high_score, 0)
        self.initial_player_pos = (WIDTH // 2 - 100, HEIGHT - 100)
        self.multishot_until_ms = 0

        self.running = True
        self.quit_requested = False
        self.paused = False
        self.is_shooting = False
        self.last_shot_time = 0
        self.last_frame: pygame.Surface | None = None

        self.joystick = None
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            if not self.joystick.get_init():
                self.joystick.init()

        self.score_font = pygame.font.SysFont("Impact", 38)
        self.small_font = pygame.font.SysFont("Consolas", 18)
        self.body_font = pygame.font.SysFont("Georgia", 20)
        self.level_font = pygame.font.SysFont("Impact", 28)

        self._create_groups()
        self.prepare_level(starting_level)

    def _create_groups(self) -> None:
        self.explosions = pygame.sprite.Group()
        self.explosions2 = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.enemy1_group = pygame.sprite.Group()
        self.enemy1_bullets = pygame.sprite.Group()
        self.enemy2_group = pygame.sprite.Group()
        self.enemy2_bullets = pygame.sprite.Group()
        self.boss1_group = pygame.sprite.Group()
        self.boss2_group = pygame.sprite.Group()
        self.boss3_group = pygame.sprite.Group()
        self.boss1_bullets = pygame.sprite.Group()
        self.boss2_bullets = pygame.sprite.Group()
        self.boss3_bullets = pygame.sprite.Group()
        self.bullet_refill_group = pygame.sprite.Group()
        self.health_refill_group = pygame.sprite.Group()
        self.multishot_group = pygame.sprite.Group()
        self.extra_score_group = pygame.sprite.Group()
        self.meteor_group = pygame.sprite.Group()
        self.meteor2_group = pygame.sprite.Group()
        self.black_hole_group = pygame.sprite.Group()

    def clear_level_groups(self) -> None:
        self.explosions.empty()
        self.explosions2.empty()
        self.bullets.empty()
        self.enemy1_group.empty()
        self.enemy1_bullets.empty()
        self.enemy2_group.empty()
        self.enemy2_bullets.empty()
        self.boss1_group.empty()
        self.boss2_group.empty()
        self.boss3_group.empty()
        self.boss1_bullets.empty()
        self.boss2_bullets.empty()
        self.boss3_bullets.empty()
        self.bullet_refill_group.empty()
        self.health_refill_group.empty()
        self.multishot_group.empty()
        self.extra_score_group.empty()
        self.meteor_group.empty()
        self.meteor2_group.empty()
        self.black_hole_group.empty()

    def prepare_level(self, level_number: int, preserve_multishot: bool = False) -> None:
        self.current_level_number = level_number
        self.level_config = get_level_config(level_number)
        self.level_score = 0
        now = pygame.time.get_ticks()
        self.next_spawn_at = {
            "enemy1": now + 400,
            "enemy2": now + 1200,
            "meteor": now + 1400,
            "meteor2": now + 700,
            "black_hole": now + 2200,
            "extra_score": now + 1800,
        }
        self.boss_state = BossState(
            boss_type=self.level_config.boss_type,
            health=self.level_config.boss_health,
            max_health=self.level_config.boss_health,
            spawned=False,
        )
        self.clear_level_groups()
        self.player.rect.topleft = self.initial_player_pos
        self.player.image = self.player.original_image.copy()
        self.player_life = MAX_PLAYER_LIFE
        self.bullet_counter = MAX_BULLETS
        self.is_shooting = False
        self.last_shot_time = 0
        if not preserve_multishot:
            self.multishot_until_ms = 0
        self.current_background = self._background_for_level(level_number)
        self.background_top = self.current_background.copy()
        self.bg_y_shift = -HEIGHT
        self.bg_speed = 1 + min(3, (level_number - 1) // 3)
        self.last_frame = None

    def _background_for_level(self, level_number: int) -> pygame.Surface:
        if level_number <= 3:
            return self.assets.backgrounds[0]
        if level_number <= 6:
            return self.assets.backgrounds[1]
        if level_number <= 8:
            return self.assets.backgrounds[2]
        return self.assets.backgrounds[3]

    def _regular_threat_groups_empty(self) -> bool:
        return (
            len(self.enemy1_group) == 0
            and len(self.enemy2_group) == 0
            and len(self.meteor_group) == 0
            and len(self.meteor2_group) == 0
            and len(self.black_hole_group) == 0
        )

    def _all_threats_cleared(self) -> bool:
        return (
            self._regular_threat_groups_empty()
            and len(self.enemy1_bullets) == 0
            and len(self.enemy2_bullets) == 0
            and len(self.boss1_group) == 0
            and len(self.boss2_group) == 0
            and len(self.boss3_group) == 0
            and len(self.boss1_bullets) == 0
            and len(self.boss2_bullets) == 0
            and len(self.boss3_bullets) == 0
        )

    def _threats_remaining(self) -> int:
        active = (
            len(self.enemy1_group)
            + len(self.enemy1_bullets)
            + len(self.enemy2_group)
            + len(self.meteor_group)
            + len(self.meteor2_group)
            + len(self.black_hole_group)
            + len(self.enemy2_bullets)
            + len(self.boss1_group)
            + len(self.boss1_bullets)
            + len(self.boss2_group)
            + len(self.boss2_bullets)
            + len(self.boss3_group)
            + len(self.boss3_bullets)
        )
        if self.boss_state.boss_type and self.level_score >= self.level_config.target_score and not self.boss_state.spawned:
            active += 1
        return active

    def _level_progress_ready(self) -> bool:
        if self.boss_state.boss_type is None:
            return self.level_score >= self.level_config.target_score

        return self.boss_state.spawned and self.boss_state.health <= 0

    def _level_complete(self) -> bool:
        return (
            self._level_progress_ready()
            and self.level_score >= self.level_config.target_score
        )

    def _multishot_active(self) -> bool:
        return pygame.time.get_ticks() < self.multishot_until_ms

    def _add_score(self, points: int) -> None:
        self.run_score += points
        self.level_score += points

    def _fire_bullet(self, force: bool = False) -> None:
        now = pygame.time.get_ticks()
        if self.bullet_counter <= 0:
            return
        if not force and now - self.last_shot_time <= SHOOT_DELAY:
            return

        self.last_shot_time = now
        bullet_positions = [self.player.rect.centerx]
        if self._multishot_active():
            bullet_positions = [
                self.player.rect.centerx - 14,
                self.player.rect.centerx + 14,
            ]

        for index, bullet_x in enumerate(bullet_positions):
            self.bullets.add(
                Bullet(
                    bullet_x,
                    self.player.rect.top,
                    play_sound=index == 0,
                )
            )
        self.bullet_counter = max(0, self.bullet_counter - 1)

    def _spawn_enemy1(self) -> None:
        enemy = Enemy1(
            random.randint(100, WIDTH - 50),
            random.randint(-HEIGHT, -50),
            random.choice(self.assets.enemy1_images),
        )
        enemy.speed += self.level_config.enemy1_speed_bonus
        self.enemy1_group.add(enemy)

    def _spawn_enemy2(self) -> None:
        enemy = Enemy2(
            random.randint(200, WIDTH - 100),
            random.randint(-HEIGHT, -100),
            random.choice(self.assets.enemy2_images),
        )
        enemy.speed += self.level_config.enemy2_speed_bonus
        self.enemy2_group.add(enemy)

    def _spawn_meteor(self) -> None:
        meteor = Meteors(
            random.randint(0, 50),
            random.randint(0, 50),
            random.choice(self.assets.meteor_images),
        )
        meteor.speed += self.level_config.meteor_speed_bonus
        self.meteor_group.add(meteor)

    def _spawn_meteor2(self) -> None:
        meteor = Meteors2(
            random.randint(100, WIDTH - 50),
            random.randint(-HEIGHT, -50),
            random.choice(self.assets.meteor2_images),
        )
        meteor.speed += self.level_config.meteor2_speed_bonus
        self.meteor2_group.add(meteor)

    def _spawn_black_hole(self) -> None:
        black_hole = BlackHole(
            random.randint(100, WIDTH - 50),
            random.randint(-HEIGHT, -50),
            random.choice(self.assets.black_hole_images),
        )
        black_hole.speed += self.level_config.black_hole_speed_bonus
        self.black_hole_group.add(black_hole)

    def _spawn_extra_score(self) -> None:
        extra_score = ExtraScore(
            random.randint(50, WIDTH - 50),
            random.randint(-HEIGHT, -50),
            self.assets.extra_score_image,
        )
        extra_score.speed += self.level_config.extra_score_speed_bonus
        self.extra_score_group.add(extra_score)

    def _clear_regular_threats(self) -> None:
        self.enemy1_group.empty()
        self.enemy1_bullets.empty()
        self.enemy2_group.empty()
        self.enemy2_bullets.empty()
        self.meteor_group.empty()
        self.meteor2_group.empty()
        self.black_hole_group.empty()

    def _clear_hostile_projectiles(self) -> None:
        self.enemy1_bullets.empty()
        self.enemy2_bullets.empty()
        self.boss1_bullets.empty()
        self.boss2_bullets.empty()
        self.boss3_bullets.empty()

    def _spawn_boss(self) -> None:
        if self.boss_state.spawned or not self.boss_state.boss_type:
            return

        self.assets.warning_sound.play()
        self._clear_regular_threats()
        boss_type = self.boss_state.boss_type
        image = self.assets.boss_images[boss_type]
        position = (random.randint(200, WIDTH - 100), random.randint(-HEIGHT, -100))

        if boss_type == "boss1":
            self.boss1_group.add(Boss1(*position, image))
        elif boss_type == "boss2":
            self.boss2_group.add(Boss2(*position, image))
        else:
            self.boss3_group.add(Boss3(*position, image))

        self.boss_state.spawned = True

    def _update_level_spawns(self) -> None:
        now = pygame.time.get_ticks()
        target_reached = self.level_score >= self.level_config.target_score

        if self.boss_state.boss_type and target_reached and not self.boss_state.spawned:
            self._spawn_boss()

        if self.boss_state.spawned and self.boss_state.health <= 0:
            return

        boss_encounter_active = self.boss_state.spawned and self.boss_state.health > 0
        if boss_encounter_active:
            if len(self.extra_score_group) < 2 and now >= self.next_spawn_at["extra_score"]:
                self._spawn_extra_score()
                self.next_spawn_at["extra_score"] = now + self.level_config.extra_score_spawn_ms
            return

        if target_reached and self.boss_state.boss_type is None:
            return

        spawn_limits = {
            "enemy1": 4 + min(4, self.current_level_number // 2),
            "enemy2": 2 + min(2, max(0, self.current_level_number - 2) // 3),
            "meteor": 2 + min(2, self.current_level_number // 4),
            "meteor2": 3 + min(2, self.current_level_number // 3),
            "black_hole": 1 + min(2, max(0, self.current_level_number - 4) // 3),
            "extra_score": 2,
        }

        if len(self.enemy1_group) < spawn_limits["enemy1"] and now >= self.next_spawn_at["enemy1"]:
            self._spawn_enemy1()
            self.next_spawn_at["enemy1"] = now + self.level_config.enemy1_spawn_ms

        if len(self.enemy2_group) < spawn_limits["enemy2"] and now >= self.next_spawn_at["enemy2"]:
            self._spawn_enemy2()
            self.next_spawn_at["enemy2"] = now + self.level_config.enemy2_spawn_ms

        if len(self.meteor_group) < spawn_limits["meteor"] and now >= self.next_spawn_at["meteor"]:
            self._spawn_meteor()
            self.next_spawn_at["meteor"] = now + self.level_config.meteor_spawn_ms

        if len(self.meteor2_group) < spawn_limits["meteor2"] and now >= self.next_spawn_at["meteor2"]:
            self._spawn_meteor2()
            self.next_spawn_at["meteor2"] = now + self.level_config.meteor2_spawn_ms

        if len(self.black_hole_group) < spawn_limits["black_hole"] and now >= self.next_spawn_at["black_hole"]:
            self._spawn_black_hole()
            self.next_spawn_at["black_hole"] = now + self.level_config.black_hole_spawn_ms

        if len(self.extra_score_group) < spawn_limits["extra_score"] and now >= self.next_spawn_at["extra_score"]:
            self._spawn_extra_score()
            self.next_spawn_at["extra_score"] = now + self.level_config.extra_score_spawn_ms

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                self.quit_requested = True
                return

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                    self.quit_requested = True
                    return
                if event.key in (pygame.K_p, pygame.K_PAUSE):
                    self.paused = not self.paused
                elif event.key == pygame.K_SPACE and not self.paused:
                    self.is_shooting = True
                    self._fire_bullet(force=True)

            if event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
                self.is_shooting = False
                self.player.image = self.player.original_image.copy()

            if event.type == pygame.JOYBUTTONDOWN:
                if event.button == 0 and not self.paused:
                    self.is_shooting = True
                    self._fire_bullet(force=True)
                elif event.button == 7:
                    self.paused = not self.paused
                elif event.button == 1:
                    self.running = False
                    self.quit_requested = True
                    return

            if event.type == pygame.JOYBUTTONUP and event.button == 0:
                self.is_shooting = False
                self.player.image = self.player.original_image.copy()

    def _update_player(self) -> None:
        if self.joystick:
            move_player_with_joystick(self.joystick, self.player)

        move_player(pygame.key.get_pressed(), self.player)

        if self.is_shooting:
            self._fire_bullet()

    def _draw_background(self, advance: bool = True) -> None:
        self.screen.blit(self.current_background, (0, self.bg_y_shift))
        background_top_rect = self.background_top.get_rect(topleft=(0, self.bg_y_shift))
        background_top_rect.top = self.bg_y_shift + HEIGHT
        self.screen.blit(self.background_top, background_top_rect)

        if advance:
            self.bg_y_shift += self.bg_speed
            if self.bg_y_shift >= 0:
                self.bg_y_shift = -HEIGHT

    def _maybe_spawn_multishot_bonus(self, centerx: int, centery: int, chance: int | None = None) -> None:
        if chance is not None and random.randint(1, chance) != 1:
            return

        self.multishot_group.add(
            MultiShotBonus(centerx, centery, self.assets.multishot_image)
        )

    def _hit_hostile_projectile(self, projectile: pygame.sprite.Sprite) -> bool:
        if pygame.sprite.spritecollide(projectile, self.bullets, True):
            self.explosions.add(Explosion(projectile.rect.center, self.assets.explosion_images))
            projectile.kill()
            return True
        return False

    def _update_hostile_bullet_group(
        self,
        bullet_group: pygame.sprite.Group,
        player_damage: int,
    ) -> None:
        for bullet in list(bullet_group):
            bullet.update()
            if not bullet.alive():
                continue
            if self._hit_hostile_projectile(bullet):
                continue

            self.screen.blit(bullet.image, bullet.rect)
            if bullet.rect.colliderect(self.player.rect):
                self.player_life -= player_damage
                self.explosions.add(Explosion(self.player.rect.center, self.assets.explosion3_images))
                bullet.kill()

    def _update_pickups(self) -> None:
        for bullet_refill in list(self.bullet_refill_group):
            bullet_refill.update()
            bullet_refill.draw(self.screen)
            if self.player.rect.colliderect(bullet_refill.rect):
                self.bullet_counter = min(MAX_BULLETS, self.bullet_counter + 50)
                bullet_refill.kill()
                bullet_refill.sound_effect.play()

        for health_refill in list(self.health_refill_group):
            health_refill.update()
            health_refill.draw(self.screen)
            if self.player.rect.colliderect(health_refill.rect):
                self.player_life = min(MAX_PLAYER_LIFE, self.player_life + 50)
                health_refill.kill()
                health_refill.sound_effect.play()

        for extra_score in list(self.extra_score_group):
            extra_score.update()
            extra_score.draw(self.screen)
            if self.player.rect.colliderect(extra_score.rect):
                self._add_score(20)
                extra_score.kill()
                extra_score.sound_effect.play()

        for multishot_bonus in list(self.multishot_group):
            multishot_bonus.update()
            multishot_bonus.draw(self.screen)
            if self.player.rect.colliderect(multishot_bonus.rect):
                self.multishot_until_ms = pygame.time.get_ticks() + 10000
                multishot_bonus.kill()
                multishot_bonus.sound_effect.play()

    def _update_black_holes(self) -> None:
        for black_hole in list(self.black_hole_group):
            black_hole.update()
            black_hole.draw(self.screen)
            if black_hole.rect.colliderect(self.player.rect):
                self.player_life -= 1
                black_hole.sound_effect.play()

    def _update_meteors(self) -> None:
        for meteor in list(self.meteor_group):
            meteor.update()
            meteor.draw(self.screen)

            if meteor.rect.colliderect(self.player.rect):
                self.player_life -= 10
                self.explosions.add(Explosion(meteor.rect.center, self.assets.explosion_images))
                meteor.kill()
                self._add_score(50)
                continue

            if pygame.sprite.spritecollide(meteor, self.bullets, True):
                self.explosions.add(Explosion(meteor.rect.center, self.assets.explosion_images))
                meteor.kill()
                self._add_score(80)

        for meteor in list(self.meteor2_group):
            meteor.update()
            meteor.draw(self.screen)

            if meteor.rect.colliderect(self.player.rect):
                self.player_life -= 10
                self.explosions.add(Explosion(meteor.rect.center, self.assets.explosion_images))
                meteor.kill()
                self._add_score(20)
                continue

            if pygame.sprite.spritecollide(meteor, self.bullets, True):
                self.explosions.add(Explosion(meteor.rect.center, self.assets.explosion_images))
                meteor.kill()
                self._add_score(40)

    def _update_enemy1(self) -> None:
        for enemy in list(self.enemy1_group):
            enemy.update(self.enemy1_group, self.enemy1_bullets, self.player)
            self.screen.blit(enemy.image, enemy.rect)

            if enemy.rect.colliderect(self.player.rect):
                self.player_life -= 10
                self.explosions.add(Explosion(enemy.rect.center, self.assets.explosion_images))
                enemy.kill()
                self._add_score(20)
                continue

            if pygame.sprite.spritecollide(enemy, self.bullets, True):
                self.explosions.add(Explosion(enemy.rect.center, self.assets.explosion_images))
                enemy.kill()
                self._add_score(50)
                self._maybe_spawn_multishot_bonus(enemy.rect.centerx, enemy.rect.centery, 8)

                if random.randint(0, 8) == 0:
                    self.bullet_refill_group.add(
                        BulletRefill(
                            enemy.rect.centerx,
                            enemy.rect.centery,
                            self.assets.bullet_refill_image,
                        )
                    )

                if random.randint(0, 8) == 0:
                    self.health_refill_group.add(
                        HealthRefill(
                            random.randint(50, WIDTH - 30),
                            random.randint(-HEIGHT, -30),
                            self.assets.health_refill_image,
                        )
                    )

        self._update_hostile_bullet_group(self.enemy1_bullets, 8)

    def _update_enemy2(self) -> None:
        for enemy in list(self.enemy2_group):
            enemy.update(self.enemy2_group, self.enemy2_bullets, self.player)
            self.screen.blit(enemy.image, enemy.rect)

            if enemy.rect.colliderect(self.player.rect):
                self.player_life -= 40
                self.explosions2.add(Explosion2(enemy.rect.center, self.assets.explosion2_images))
                enemy.kill()
                self._add_score(20)
                continue

            if pygame.sprite.spritecollide(enemy, self.bullets, True):
                self.explosions2.add(Explosion2(enemy.rect.center, self.assets.explosion2_images))
                enemy.kill()
                self._add_score(80)
                self._maybe_spawn_multishot_bonus(enemy.rect.centerx, enemy.rect.centery, 6)

        self._update_hostile_bullet_group(self.enemy2_bullets, 10)

    def _active_boss_group(self) -> pygame.sprite.Group:
        if self.boss_state.boss_type == "boss1":
            return self.boss1_group
        if self.boss_state.boss_type == "boss2":
            return self.boss2_group
        return self.boss3_group

    def _active_boss_bullets(self) -> pygame.sprite.Group:
        if self.boss_state.boss_type == "boss1":
            return self.boss1_bullets
        if self.boss_state.boss_type == "boss2":
            return self.boss2_bullets
        return self.boss3_bullets

    def _update_bosses(self) -> None:
        if not self.boss_state.boss_type:
            return

        boss_group = self._active_boss_group()
        if not boss_group:
            return

        boss_bullets = self._active_boss_bullets()
        rewards = {"boss1": 400, "boss2": 800, "boss3": 1000}
        contact_damage = {"boss1": 20, "boss2": 2, "boss3": 1}
        hit_damage = {"boss1": 5, "boss2": 8, "boss3": 6}

        for boss in list(boss_group):
            boss.update(boss_bullets, self.player)
            self.screen.blit(boss.image, boss.rect)

            if boss.rect.colliderect(self.player.rect):
                self.player_life -= contact_damage[self.boss_state.boss_type]
                self.explosions2.add(Explosion2(boss.rect.center, self.assets.explosion2_images))

            bullet_hits = pygame.sprite.spritecollide(boss, self.bullets, True)
            for _ in bullet_hits:
                self.explosions2.add(Explosion2(boss.rect.center, self.assets.explosion2_images))
                self.boss_state.health -= hit_damage[self.boss_state.boss_type]
                if self.boss_state.health <= 0:
                    self.boss_state.health = 0
                    self.explosions.add(Explosion(boss.rect.center, self.assets.explosion3_images))
                    boss.kill()
                    self._clear_regular_threats()
                    self._clear_hostile_projectiles()
                    self._add_score(rewards[self.boss_state.boss_type])
                    self._maybe_spawn_multishot_bonus(boss.rect.centerx, boss.rect.centery)
                    break

        self._update_hostile_bullet_group(boss_bullets, 20)

        if boss_group and self.boss_state.max_health > 0:
            boss = boss_group.sprites()[0]
            self._draw_boss_health_bar(boss.rect.centerx, boss.rect.top)

    def _draw_boss_health_bar(self, centerx: int, top: int) -> None:
        bar_width = max(140, min(220, self.boss_state.max_health))
        bar_rect = pygame.Rect(0, 0, bar_width, 8)
        bar_rect.center = (centerx, top - 8)
        pygame.draw.rect(self.screen, (255, 0, 0), bar_rect)
        current_width = int((self.boss_state.health / self.boss_state.max_health) * bar_width)
        current_width = max(0, min(current_width, bar_width))
        pygame.draw.rect(
            self.screen,
            (0, 255, 0),
            pygame.Rect(bar_rect.left, bar_rect.top, current_width, bar_rect.height),
        )

    def _update_effects(self) -> None:
        for explosion in list(self.explosions):
            explosion.update()
            self.screen.blit(explosion.image, explosion.rect)

        for explosion in list(self.explosions2):
            explosion.update()
            self.screen.blit(explosion.image, explosion.rect)

        for bullet in list(self.bullets):
            bullet.update()
            self.screen.blit(bullet.image, bullet.rect)

    def _draw_player(self) -> None:
        self.screen.blit(self.player.image, self.player.rect)

    def _draw_hud_card(
        self,
        rect: pygame.Rect,
        border_color: tuple[int, int, int],
        glow_color: tuple[int, int, int] | None = None,
        fill_alpha: int = 194,
    ) -> None:
        draw_panel(
            self.screen,
            rect,
            self.frontend_session,
            fill_alpha=fill_alpha,
            border_color=border_color,
            glow_color=glow_color or border_color,
            border_radius=24,
        )

    def _draw_hud(self) -> None:
        palette = self.frontend_session.palette

        hud_shadow = pygame.Surface((WIDTH, 190), pygame.SRCALPHA)
        hud_shadow.fill((*palette.shadow, 72))
        self.screen.blit(hud_shadow, (0, 0))

        left_panel = pygame.Rect(16, 16, 360, 150)
        center_panel = pygame.Rect(402, 16, 398, 94)
        right_panel = pygame.Rect(WIDTH - 318, 16, 302, 150)

        self._draw_hud_card(left_panel, palette.accent_hot, palette.panel_soft)
        self._draw_hud_card(center_panel, palette.accent_gold, palette.accent_hot, 208)
        self._draw_hud_card(right_panel, palette.accent_warm, palette.accent_hot)

        life_width = max(0, min(200, int(self.player_life / MAX_PLAYER_LIFE * 200)))
        life_surface = pygame.Surface((200, 25), pygame.SRCALPHA, 32)
        life_fill = pygame.Surface((life_width, 30), pygame.SRCALPHA, 32)
        life_fill.fill((152, 251, 152) if self.player_life > 50 else (0, 0, 0))
        life_surface.blit(self.assets.life_bar_image, (0, 0))
        life_surface.blit(life_fill, (35, 0))
        self.screen.blit(life_surface, (left_panel.left + 18, left_panel.top + 24))

        bullet_width = max(0, min(200, int(self.bullet_counter / MAX_BULLETS * 200)))
        bullet_surface = pygame.Surface((200, 25), pygame.SRCALPHA, 32)
        bullet_fill = pygame.Surface((bullet_width, 30), pygame.SRCALPHA, 32)
        bullet_fill.fill((255, 23, 23) if self.bullet_counter > 50 else (0, 0, 0))
        bullet_surface.blit(self.assets.bullet_bar_image, (0, 0))
        bullet_surface.blit(bullet_fill, (35, 0))
        self.screen.blit(bullet_surface, (left_panel.left + 18, left_panel.top + 74))

        level_label = self.level_font.render(
            f"L{self.current_level_number}  {self.level_config.name}",
            True,
            palette.text_primary,
        )
        self.screen.blit(level_label, (left_panel.left + 18, left_panel.top + 112))

        threats_surface = self.body_font.render(
            f"THREATS {self._threats_remaining()}",
            True,
            palette.text_primary,
        )
        self.screen.blit(threats_surface, (center_panel.left + 22, center_panel.top + 22))

        hi_score_surface = self.small_font.render(
            f"HI {max(self.hi_score, self.run_score)}",
            True,
            palette.text_muted,
        )
        self.screen.blit(hi_score_surface, (center_panel.left + 22, center_panel.top + 58))
        emblem_rect = self.frontend_session.emblem.get_rect(midright=(center_panel.right - 18, center_panel.centery))
        self.screen.blit(self.frontend_session.emblem, emblem_rect)

        mission_surface = self.body_font.render(
            f"{self.level_score}/{self.level_config.target_score}",
            True,
            palette.text_primary,
        )
        self.screen.blit(mission_surface, (right_panel.left + 20, right_panel.top + 18))

        score_surface = self.score_font.render(f"{self.run_score}", True, palette.accent_gold)
        score_rect = score_surface.get_rect()
        score_rect.x = right_panel.left + 20
        score_rect.y = right_panel.top + 58
        self.screen.blit(
            self.assets.extra_score_image,
            (
                score_rect.right + 10,
                score_rect.centery - self.assets.extra_score_image.get_height() // 2,
            ),
        )
        self.screen.blit(score_surface, score_rect)

        if self._multishot_active():
            seconds_left = max(1, (self.multishot_until_ms - pygame.time.get_ticks() + 999) // 1000)
            multishot_surface = self.small_font.render(
                f"2X {seconds_left}s",
                True,
                palette.accent_gold,
            )
        else:
            multishot_surface = self.small_font.render(
                "2X READY",
                True,
                palette.text_muted,
            )
        self.screen.blit(multishot_surface, (right_panel.left + 20, right_panel.bottom - 26))

        watermark_rect = self.frontend_session.hud_watermark.get_rect(
            bottomright=(WIDTH - 12, HEIGHT - 10)
        )
        self.screen.blit(self.frontend_session.hud_watermark, watermark_rect)
        self.screen.blit(self.frontend_session.logo_small, (WIDTH - 238, HEIGHT - 92))

    def _draw_pause_overlay(self) -> None:
        draw_modal_overlay(
            self.screen,
            self.frontend_session,
            "PAUSED",
            "P resume   ESC exit",
            title_color=self.frontend_session.palette.accent_gold,
        )

    def _update_world(self) -> None:
        self._draw_background()
        self._update_player()
        self._update_level_spawns()
        self._update_black_holes()
        self._update_pickups()
        self._update_meteors()
        self._update_enemy1()
        self._update_enemy2()
        self._update_bosses()
        self._draw_player()
        self._update_effects()
        self._draw_hud()

    def run(self) -> RunResult:
        while self.running:
            self.clock.tick(FPS)
            self._handle_events()

            if not self.running:
                break

            if self.paused:
                if self.last_frame is not None:
                    self.screen.blit(self.last_frame, (0, 0))
                else:
                    self._update_world()
                    self.last_frame = self.screen.copy()
                self._draw_pause_overlay()
                pygame.display.flip()
                continue

            self._update_world()
            self.last_frame = self.screen.copy()
            pygame.display.flip()

            if self.player_life <= 0:
                self.progress = record_score(self.progress, self.run_score)
                show_game_over(self.run_score, self.frontend_session)
                return RunResult(self.progress, quit_requested=self.quit_requested)

            if self._level_complete():
                self.progress = record_level_completion(
                    self.progress,
                    self.current_level_number,
                    self.run_score,
                )

                if self.current_level_number == MAX_LEVELS:
                    show_game_win(self.run_score, self.frontend_session)
                    return RunResult(self.progress, quit_requested=self.quit_requested)

                show_level_complete(
                    self.current_level_number,
                    self.level_score,
                    self.frontend_session,
                )
                self.prepare_level(
                    self.current_level_number + 1,
                    preserve_multishot=self._multishot_active(),
                )
                music_background()

        self.progress = record_score(self.progress, self.run_score)
        return RunResult(self.progress, quit_requested=self.quit_requested)


def main() -> None:
    pygame.init()
    pygame.mixer.init()
    pygame.mixer.set_num_channels(20)

    screen = create_game_display()
    pygame.display.set_caption("Cosmic Heat")
    progress = load_progress()
    frontend_session = create_frontend_session()

    while True:
        selected_level = show_menu(progress, frontend_session)
        if selected_level is None:
            break

        music_background()
        result = GameSession(screen, progress, selected_level, frontend_session).run()
        progress = result.progress

        if result.quit_requested:
            break

    pygame.mixer.music.stop()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
