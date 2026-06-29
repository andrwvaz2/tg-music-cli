from __future__ import annotations

import curses
from dataclasses import dataclass


@dataclass
class ColorTheme:
    name: str
    is_light: bool
    primary: int
    success: int
    warning: int
    error: int
    header_fg: int
    header_bg: int
    selected_fg: int
    selected_bg: int
    playing_fg: int
    playing_bg: int
    dim: bool


THEMES: dict[str, ColorTheme] = {
    "dracula": ColorTheme(
        name="Dracula",
        is_light=False,
        primary=curses.COLOR_MAGENTA,
        success=curses.COLOR_GREEN,
        warning=curses.COLOR_YELLOW,
        error=curses.COLOR_RED,
        header_fg=curses.COLOR_WHITE,
        header_bg=curses.COLOR_MAGENTA,
        selected_fg=curses.COLOR_BLACK,
        selected_bg=curses.COLOR_CYAN,
        playing_fg=curses.COLOR_GREEN,
        playing_bg=-1,
        dim=True,
    ),
    "nord": ColorTheme(
        name="Nord",
        is_light=False,
        primary=curses.COLOR_CYAN,
        success=curses.COLOR_GREEN,
        warning=curses.COLOR_YELLOW,
        error=curses.COLOR_RED,
        header_fg=curses.COLOR_WHITE,
        header_bg=curses.COLOR_BLUE,
        selected_fg=curses.COLOR_BLACK,
        selected_bg=curses.COLOR_CYAN,
        playing_fg=curses.COLOR_GREEN,
        playing_bg=-1,
        dim=True,
    ),
    "solarized-dark": ColorTheme(
        name="Solarized Dark",
        is_light=False,
        primary=curses.COLOR_CYAN,
        success=curses.COLOR_GREEN,
        warning=curses.COLOR_YELLOW,
        error=curses.COLOR_RED,
        header_fg=curses.COLOR_YELLOW,
        header_bg=curses.COLOR_BLUE,
        selected_fg=curses.COLOR_BLACK,
        selected_bg=curses.COLOR_CYAN,
        playing_fg=curses.COLOR_GREEN,
        playing_bg=-1,
        dim=True,
    ),
    "solarized-light": ColorTheme(
        name="Solarized Light",
        is_light=True,
        primary=curses.COLOR_BLUE,
        success=curses.COLOR_GREEN,
        warning=curses.COLOR_YELLOW,
        error=curses.COLOR_RED,
        header_fg=curses.COLOR_WHITE,
        header_bg=curses.COLOR_BLUE,
        selected_fg=curses.COLOR_WHITE,
        selected_bg=curses.COLOR_BLUE,
        playing_fg=curses.COLOR_GREEN,
        playing_bg=-1,
        dim=True,
    ),
    "gruvbox-dark": ColorTheme(
        name="Gruvbox Dark",
        is_light=False,
        primary=curses.COLOR_YELLOW,
        success=curses.COLOR_GREEN,
        warning=curses.COLOR_YELLOW,
        error=curses.COLOR_RED,
        header_fg=curses.COLOR_BLACK,
        header_bg=curses.COLOR_YELLOW,
        selected_fg=curses.COLOR_BLACK,
        selected_bg=curses.COLOR_CYAN,
        playing_fg=curses.COLOR_GREEN,
        playing_bg=-1,
        dim=True,
    ),
    "tokyo-night": ColorTheme(
        name="Tokyo Night",
        is_light=False,
        primary=curses.COLOR_BLUE,
        success=curses.COLOR_GREEN,
        warning=curses.COLOR_YELLOW,
        error=curses.COLOR_RED,
        header_fg=curses.COLOR_WHITE,
        header_bg=curses.COLOR_BLUE,
        selected_fg=curses.COLOR_BLACK,
        selected_bg=curses.COLOR_CYAN,
        playing_fg=curses.COLOR_GREEN,
        playing_bg=-1,
        dim=True,
    ),
    "catppuccin": ColorTheme(
        name="Catppuccin Mocha",
        is_light=False,
        primary=curses.COLOR_MAGENTA,
        success=curses.COLOR_GREEN,
        warning=curses.COLOR_YELLOW,
        error=curses.COLOR_RED,
        header_fg=curses.COLOR_WHITE,
        header_bg=curses.COLOR_MAGENTA,
        selected_fg=curses.COLOR_BLACK,
        selected_bg=curses.COLOR_CYAN,
        playing_fg=curses.COLOR_GREEN,
        playing_bg=-1,
        dim=True,
    ),
    "monokai": ColorTheme(
        name="Monokai",
        is_light=False,
        primary=curses.COLOR_GREEN,
        success=curses.COLOR_GREEN,
        warning=curses.COLOR_YELLOW,
        error=curses.COLOR_RED,
        header_fg=curses.COLOR_WHITE,
        header_bg=curses.COLOR_GREEN,
        selected_fg=curses.COLOR_BLACK,
        selected_bg=curses.COLOR_CYAN,
        playing_fg=curses.COLOR_GREEN,
        playing_bg=-1,
        dim=True,
    ),
    "light": ColorTheme(
        name="Light",
        is_light=True,
        primary=curses.COLOR_BLUE,
        success=curses.COLOR_BLUE,
        warning=curses.COLOR_RED,
        error=curses.COLOR_RED,
        header_fg=curses.COLOR_WHITE,
        header_bg=curses.COLOR_BLUE,
        selected_fg=curses.COLOR_WHITE,
        selected_bg=curses.COLOR_BLUE,
        playing_fg=curses.COLOR_BLUE,
        playing_bg=-1,
        dim=True,
    ),
    "dark": ColorTheme(
        name="Dark",
        is_light=False,
        primary=curses.COLOR_CYAN,
        success=curses.COLOR_GREEN,
        warning=curses.COLOR_YELLOW,
        error=curses.COLOR_RED,
        header_fg=curses.COLOR_WHITE,
        header_bg=curses.COLOR_CYAN,
        selected_fg=curses.COLOR_BLACK,
        selected_bg=curses.COLOR_CYAN,
        playing_fg=curses.COLOR_GREEN,
        playing_bg=-1,
        dim=True,
    ),
}

THEME_ORDER = [
    "dark",
    "light",
    "dracula",
    "nord",
    "solarized-dark",
    "solarized-light",
    "gruvbox-dark",
    "tokyo-night",
    "catppuccin",
    "monokai",
]

DEFAULT_THEME = "dark"


def get_theme(name: str) -> ColorTheme:
    return THEMES.get(name, THEMES[DEFAULT_THEME])


def list_themes() -> list[str]:
    return THEME_ORDER
