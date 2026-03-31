from __future__ import annotations

import math
import sys

import pygame

from classes.campaign import MAX_LEVELS, get_level_config
from classes.constants import HEIGHT, WIDTH
from classes.display import create_game_display, ensure_game_display
from classes.frontend import (
    FrontendSession,
    create_frontend_session,
    draw_backdrop,
    draw_panel,
)
from classes.progress import ProgressData


def _fit_text_surface(
    text: str,
    font_name: str,
    start_size: int,
    color: tuple[int, int, int],
    max_width: int,
    *,
    min_size: int = 14,
    bold: bool = False,
) -> pygame.Surface:
    for size in range(start_size, min_size - 1, -1):
        font = pygame.font.SysFont(font_name, size, bold=bold)
        surface = font.render(text, True, color)
        if surface.get_width() <= max_width:
            return surface

    font = pygame.font.SysFont(font_name, min_size, bold=bold)
    trimmed = text
    while trimmed:
        candidate = f"{trimmed}..."
        surface = font.render(candidate, True, color)
        if surface.get_width() <= max_width:
            return surface
        trimmed = trimmed[:-1]
    return font.render(text, True, color)


def _move_grid_selection(current_level: int, direction: str) -> int:
    row = (current_level - 1) // 5
    column = (current_level - 1) % 5

    if direction == "left":
        column = max(0, column - 1)
    elif direction == "right":
        column = min(4, column + 1)
    elif direction == "up":
        row = max(0, row - 1)
    elif direction == "down":
        row = min(1, row + 1)

    return row * 5 + column + 1


def _level_buttons() -> list[tuple[int, pygame.Rect]]:
    buttons: list[tuple[int, pygame.Rect]] = []
    button_width = 196
    button_height = 104
    gap = 16
    start_x = (WIDTH - (button_width * 5 + gap * 4)) // 2
    start_y = 364

    for level in range(1, 11):
        row = (level - 1) // 5
        column = (level - 1) % 5
        rect = pygame.Rect(
            start_x + column * (button_width + gap),
            start_y + row * (button_height + gap),
            button_width,
            button_height,
        )
        buttons.append((level, rect))

    return buttons


def _animate_launch(screen: pygame.Surface, frontend_session: FrontendSession) -> None:
    for frame in range(10):
        tick_ms = pygame.time.get_ticks() + frame * 30
        draw_backdrop(screen, frontend_session, tick_ms)
        pulse = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pulse.fill((*frontend_session.palette.accent_hot, min(120, 20 + frame * 10)))
        screen.blit(pulse, (0, 0))
        pygame.display.flip()
        pygame.time.wait(20)


def _attempt_level_start(progress: ProgressData, level_number: int) -> int | None:
    if level_number <= progress.highest_unlocked_level:
        return level_number
    return None


def _draw_header(
    screen: pygame.Surface,
    frontend_session: FrontendSession,
    progress: ProgressData,
    selected_config,
    now: int,
    intro_offset: int,
) -> pygame.Rect:
    palette = frontend_session.palette
    title_font = pygame.font.SysFont("Impact", 54)
    body_font = pygame.font.SysFont("Georgia", 22)

    hero_rect = pygame.Rect(52, 42 - intro_offset, 700, 250)
    detail_rect = pygame.Rect(780, 42 - intro_offset, 368, 250)

    draw_panel(
        screen,
        hero_rect,
        frontend_session,
        fill_alpha=196,
        border_color=palette.accent_hot,
        glow_color=palette.accent_warm,
        border_radius=30,
    )
    draw_panel(
        screen,
        detail_rect,
        frontend_session,
        fill_alpha=202,
        border_color=palette.accent_gold,
        glow_color=palette.accent_hot,
        border_radius=30,
    )

    hero_art = frontend_session.hero_art.copy()
    hero_art.set_alpha(120)
    hero_art_rect = hero_art.get_rect(topright=(hero_rect.right - 16, hero_rect.top + 12))
    screen.blit(hero_art, hero_art_rect)

    text_safe = pygame.Surface((hero_rect.width - 220, hero_rect.height - 34), pygame.SRCALPHA)
    text_safe.fill((*palette.shadow, 110))
    screen.blit(text_safe, (hero_rect.left + 16, hero_rect.top + 17))

    screen.blit(frontend_session.logo_large, (hero_rect.left + 22, hero_rect.top + 20))

    title_surface = title_font.render("MISSION HANGAR", True, palette.text_primary)
    screen.blit(title_surface, (hero_rect.left + 30, hero_rect.top + 122))

    summary_surface = body_font.render(
        f"HI-SCORE {progress.high_score}",
        True,
        palette.text_primary,
    )
    screen.blit(summary_surface, (hero_rect.left + 32, hero_rect.top + 184))

    preview_rect = pygame.Rect(detail_rect.left + 22, detail_rect.top + 32, 324, 118)
    preview_frame = pygame.Surface(preview_rect.size, pygame.SRCALPHA)
    pygame.draw.rect(preview_frame, (*palette.panel_mid, 128), preview_frame.get_rect(), border_radius=18)
    pygame.draw.rect(preview_frame, (*palette.accent_warm, 150), preview_frame.get_rect(), width=2, border_radius=18)
    screen.blit(preview_frame, preview_rect.topleft)
    preview_art = frontend_session.preview_art.copy()
    preview_art.set_alpha(150)
    screen.blit(preview_art, preview_rect.topleft)

    preview_dim = pygame.Surface(preview_rect.size, pygame.SRCALPHA)
    preview_dim.fill((*palette.shadow, 84))
    screen.blit(preview_dim, preview_rect.topleft)

    mission_title = _fit_text_surface(
        f"L{selected_config.number:02d}  {selected_config.name.upper()}",
        "Impact",
        40,
        palette.text_primary,
        detail_rect.width - 44,
        min_size=24,
        bold=False,
    )
    screen.blit(mission_title, (detail_rect.left + 22, detail_rect.top + 168))

    target_surface = body_font.render(
        f"Target {selected_config.target_score}",
        True,
        palette.text_primary,
    )
    target_rect = target_surface.get_rect(bottomright=(detail_rect.right - 24, detail_rect.bottom - 24))
    screen.blit(target_surface, target_rect)

    sweep_x = detail_rect.left + 18 + int((math.sin(now / 650) + 1) * 110)
    pygame.draw.line(
        screen,
        palette.accent_warm,
        (sweep_x, detail_rect.top + 66),
        (sweep_x, detail_rect.top + 148),
        2,
    )

    return detail_rect


def _draw_level_grid(
    screen: pygame.Surface,
    frontend_session: FrontendSession,
    progress: ProgressData,
    selected_level: int,
    exit_selected: bool,
    intro_offset: int,
) -> None:
    palette = frontend_session.palette
    level_font = pygame.font.SysFont("Impact", 30)
    body_font = pygame.font.SysFont("Georgia", 17)
    label_font = pygame.font.SysFont("Consolas", 16)

    for level, base_rect in _level_buttons():
        rect = base_rect.move(0, intro_offset)
        config = get_level_config(level)
        unlocked = level <= progress.highest_unlocked_level
        completed = level <= progress.highest_completed_level
        selected = level == selected_level and not exit_selected

        border_color = palette.accent_gold if selected else palette.accent_hot
        glow_color = palette.accent_warm if selected else palette.panel_soft
        fill_alpha = 220 if selected else 184

        draw_panel(
            screen,
            rect,
            frontend_session,
            fill_alpha=fill_alpha,
            border_color=border_color,
            glow_color=glow_color,
            border_radius=24,
        )

        banner_rect = pygame.Rect(rect.left + 12, rect.top + 12, rect.width - 24, 28)
        banner = pygame.Surface(banner_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(
            banner,
            (*palette.panel_mid, 124),
            banner.get_rect(),
            border_radius=12,
        )
        screen.blit(banner, banner_rect.topleft)

        number_surface = level_font.render(f"L{level:02d}", True, palette.text_primary if unlocked else palette.text_muted)
        screen.blit(number_surface, (rect.left + 16, rect.top + 10))

        tag_text = "DONE" if completed else "OPEN" if unlocked else "LOCK"
        tag_color = palette.success if completed else palette.accent_warm if unlocked else palette.warning
        tag_surface = label_font.render(tag_text, True, tag_color)
        tag_rect = tag_surface.get_rect(midright=(rect.right - 16, banner_rect.centery))
        screen.blit(tag_surface, tag_rect)

        name_surface = _fit_text_surface(
            config.name,
            "Georgia",
            17,
            palette.text_primary if unlocked else palette.text_muted,
            rect.width - 32,
            min_size=14,
        )
        screen.blit(name_surface, (rect.left + 16, rect.top + 52))

        target_surface = label_font.render(
            f"T {config.target_score}",
            True,
            palette.accent_gold if unlocked else palette.text_muted,
        )
        screen.blit(target_surface, (rect.left + 16, rect.top + 78))

        if not unlocked:
            lock_overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
            lock_overlay.fill((*palette.shadow, 110))
            screen.blit(lock_overlay, rect.topleft)


def _draw_footer(
    screen: pygame.Surface,
    frontend_session: FrontendSession,
    status_text: str,
    exit_selected: bool,
    intro_offset: int,
) -> pygame.Rect:
    palette = frontend_session.palette
    body_font = pygame.font.SysFont("Georgia", 20)

    footer_rect = pygame.Rect(52, 696 + intro_offset, WIDTH - 104, 66)
    draw_panel(
        screen,
        footer_rect,
        frontend_session,
        fill_alpha=196,
        border_color=palette.accent_hot,
        glow_color=palette.panel_soft,
        border_radius=28,
    )

    if status_text:
        status_surface = body_font.render(status_text, True, palette.warning)
        screen.blit(status_surface, (footer_rect.left + 24, footer_rect.top + 22))

    exit_button = pygame.Rect(footer_rect.right - 194, footer_rect.top + 9, 168, 48)
    draw_panel(
        screen,
        exit_button,
        frontend_session,
        fill_alpha=220 if exit_selected else 168,
        border_color=palette.accent_gold if exit_selected else palette.accent_hot,
        glow_color=palette.accent_warm if exit_selected else palette.panel_soft,
        border_radius=20,
    )
    exit_font = pygame.font.SysFont("Impact", 28)
    exit_surface = exit_font.render("LEAVE HANGAR", True, palette.text_primary)
    exit_rect = exit_surface.get_rect(center=exit_button.center)
    screen.blit(exit_surface, exit_rect)
    return exit_button


def _draw_menu(
    screen: pygame.Surface,
    frontend_session: FrontendSession,
    progress: ProgressData,
    selected_level: int,
    exit_selected: bool,
    status_text: str,
    menu_started_at: int,
) -> pygame.Rect:
    now = pygame.time.get_ticks()
    palette = frontend_session.palette
    selected_config = get_level_config(selected_level)
    intro_progress = min(1.0, (now - menu_started_at) / 550)
    intro_offset = int((1.0 - intro_progress) ** 2 * 44)

    draw_backdrop(screen, frontend_session, now)
    screen.blit(frontend_session.emblem, (24, HEIGHT - 140))

    _draw_header(screen, frontend_session, progress, selected_config, now, intro_offset)
    _draw_level_grid(screen, frontend_session, progress, selected_level, exit_selected, intro_offset)
    exit_button = _draw_footer(screen, frontend_session, status_text, exit_selected, intro_offset)

    return exit_button


def show_menu(progress: ProgressData, frontend_session: FrontendSession) -> int | None:
    pygame.display.set_caption("Cosmic Heat")
    screen = ensure_game_display()
    clock = pygame.time.Clock()

    pygame.mixer.music.load("game_sounds/menu.mp3")
    pygame.mixer.music.set_volume(0.25)
    pygame.mixer.music.play(-1)

    explosion_sound = pygame.mixer.Sound("game_sounds/explosions/explosion1.wav")
    explosion_sound.set_volume(0.25)

    joystick = None
    if pygame.joystick.get_count() > 0:
        joystick = pygame.joystick.Joystick(0)
        if not joystick.get_init():
            joystick.init()

    selected_level = min(max(progress.highest_unlocked_level, 1), MAX_LEVELS)
    exit_selected = False
    status_text = ""
    status_until = 0
    menu_started_at = pygame.time.get_ticks()

    while True:
        now = pygame.time.get_ticks()
        if status_text and now > status_until:
            status_text = ""

        exit_button = _draw_menu(
            screen,
            frontend_session,
            progress,
            selected_level,
            exit_selected,
            status_text,
            menu_started_at,
        )
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None

            if event.type == pygame.MOUSEMOTION:
                exit_selected = exit_button.collidepoint(event.pos)
                for level, rect in _level_buttons():
                    if rect.move(0, int((1.0 - min(1.0, (now - menu_started_at) / 550)) ** 2 * 44)).collidepoint(event.pos):
                        selected_level = level
                        exit_selected = False
                        break

            if event.type == pygame.MOUSEBUTTONDOWN:
                for level, rect in _level_buttons():
                    adjusted_rect = rect.move(0, int((1.0 - min(1.0, (now - menu_started_at) / 550)) ** 2 * 44))
                    if adjusted_rect.collidepoint(event.pos):
                        selected_level = level
                        exit_selected = False
                        chosen_level = _attempt_level_start(progress, level)
                        if chosen_level is not None:
                            explosion_sound.play()
                            _animate_launch(screen, frontend_session)
                            pygame.mixer.music.stop()
                            return chosen_level
                        status_text = "Clear previous sector."
                        status_until = now + 1700

                if exit_button.collidepoint(event.pos):
                    return None

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                if event.key == pygame.K_TAB:
                    exit_selected = not exit_selected
                elif event.key == pygame.K_LEFT and not exit_selected:
                    selected_level = _move_grid_selection(selected_level, "left")
                elif event.key == pygame.K_RIGHT and not exit_selected:
                    selected_level = _move_grid_selection(selected_level, "right")
                elif event.key == pygame.K_UP:
                    if exit_selected:
                        exit_selected = False
                    else:
                        selected_level = _move_grid_selection(selected_level, "up")
                elif event.key == pygame.K_DOWN:
                    if (selected_level - 1) // 5 == 1:
                        exit_selected = True
                    elif not exit_selected:
                        selected_level = _move_grid_selection(selected_level, "down")
                elif event.key == pygame.K_RETURN:
                    if exit_selected:
                        return None

                    chosen_level = _attempt_level_start(progress, selected_level)
                    if chosen_level is not None:
                        explosion_sound.play()
                        _animate_launch(screen, frontend_session)
                        pygame.mixer.music.stop()
                        return chosen_level

                    status_text = "Clear previous sector."
                    status_until = now + 1700

            if joystick and event.type == pygame.JOYHATMOTION:
                if event.value == (-1, 0) and not exit_selected:
                    selected_level = _move_grid_selection(selected_level, "left")
                elif event.value == (1, 0) and not exit_selected:
                    selected_level = _move_grid_selection(selected_level, "right")
                elif event.value == (0, -1):
                    if (selected_level - 1) // 5 == 1:
                        exit_selected = True
                    elif not exit_selected:
                        selected_level = _move_grid_selection(selected_level, "down")
                elif event.value == (0, 1):
                    exit_selected = False
                    selected_level = _move_grid_selection(selected_level, "up")

            if joystick and event.type == pygame.JOYBUTTONDOWN:
                if event.button == 1:
                    return None
                if event.button == 0:
                    if exit_selected:
                        return None

                    chosen_level = _attempt_level_start(progress, selected_level)
                    if chosen_level is not None:
                        explosion_sound.play()
                        _animate_launch(screen, frontend_session)
                        pygame.mixer.music.stop()
                        return chosen_level

                    status_text = "Clear previous sector."
                    status_until = now + 1700

        clock.tick(60)


if __name__ == "__main__":
    pygame.init()
    create_game_display()
    level = show_menu(ProgressData(), create_frontend_session())
    pygame.quit()
    if level is None:
        sys.exit(0)
