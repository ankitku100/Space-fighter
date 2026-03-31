from __future__ import annotations

import pygame

from classes.display import ensure_game_display
from classes.frontend import FrontendSession, draw_modal_overlay


def music_background() -> None:
    pygame.mixer.music.load("game_sounds/background_music.mp3")
    pygame.mixer.music.set_volume(0.25)
    pygame.mixer.music.play(loops=-1)


def _get_screen() -> pygame.Surface:
    return ensure_game_display()


def _show_center_message(
    frontend_session: FrontendSession,
    title: str,
    subtitle: str,
    title_color: tuple[int, int, int],
    delay_ms: int,
    *,
    kicker: str = "",
    footer: str = "",
) -> None:
    screen = _get_screen()
    draw_modal_overlay(
        screen,
        frontend_session,
        title,
        subtitle,
        kicker=kicker,
        footer=footer,
        title_color=title_color,
    )
    pygame.display.flip()
    pygame.time.delay(delay_ms)


def show_game_over(score: int, frontend_session: FrontendSession) -> None:
    _show_center_message(
        frontend_session,
        "GAME OVER",
        f"SCORE {score}",
        frontend_session.palette.warning,
        2800,
    )
    pygame.mixer.music.load("game_sounds/gameover.mp3")
    pygame.mixer.music.play()
    pygame.time.delay(1800)


def show_level_complete(level_number: int, score: int, frontend_session: FrontendSession) -> None:
    pygame.mixer.music.load("game_sounds/win.mp3")
    pygame.mixer.music.play()
    _show_center_message(
        frontend_session,
        f"LEVEL {level_number} COMPLETE",
        f"SCORE {score}",
        frontend_session.palette.text_primary,
        1600,
    )


def show_game_win(score: int, frontend_session: FrontendSession) -> None:
    pygame.mixer.music.load("game_sounds/win.mp3")
    pygame.mixer.music.play()
    _show_center_message(
        frontend_session,
        "CAMPAIGN CLEARED",
        f"SCORE {score}",
        frontend_session.palette.text_primary,
        2200,
    )
