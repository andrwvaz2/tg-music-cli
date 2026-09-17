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
    palette_256: dict[str, str] | None = None


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
        palette_256={
            "primary": "#BD93F9",
            "success": "#50FA7B",
            "warning": "#F1FA8C",
            "error": "#FF5555",
            "header_fg": "#F8F8F2",
            "header_bg": "#BD93F9",
            "selected_fg": "#282A36",
            "selected_bg": "#8BE9FD",
            "playing_fg": "#50FA7B",
            "blue": "#6272A4",
            "magenta": "#FF79C6",
        },
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
        palette_256={
            "primary": "#88C0D0",
            "success": "#A3BE8C",
            "warning": "#EBCB8B",
            "error": "#BF616A",
            "header_fg": "#ECEFF4",
            "header_bg": "#5E81AC",
            "selected_fg": "#2E3440",
            "selected_bg": "#88C0D0",
            "playing_fg": "#A3BE8C",
            "blue": "#81A1C1",
            "magenta": "#B48EAD",
        },
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
        palette_256={
            "primary": "#7AA2F7",
            "success": "#9ECE6A",
            "warning": "#E0AF68",
            "error": "#F7768E",
            "header_fg": "#C0CAF5",
            "header_bg": "#7AA2F7",
            "selected_fg": "#1A1B26",
            "selected_bg": "#7AA2F7",
            "playing_fg": "#9ECE6A",
            "blue": "#7DCFFF",
            "magenta": "#FF007C",
        },
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
        palette_256={
            "primary": "#CBA6F7",
            "success": "#A6E3A1",
            "warning": "#F9E2AF",
            "error": "#F38BA8",
            "header_fg": "#CDD6F4",
            "header_bg": "#CBA6F7",
            "selected_fg": "#1E1E2E",
            "selected_bg": "#89B4FA",
            "playing_fg": "#A6E3A1",
            "blue": "#89B4FA",
            "magenta": "#F5E0DC",
        },
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
