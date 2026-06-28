from __future__ import annotations

import os
import re
import sys

GRADIENT = [
    (255, 170, 0),
    (255, 145, 0),
    (255, 120, 0),
    (255, 95, 0),
    (255, 70, 0),
    (255, 45, 0),
    (230, 20, 0),
    (210, 0, 0),
]


def _ansi_fg(r: int, g: int, b: int) -> str:
    return f"\033[38;2;{r};{g};{b}m"


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
WHITE = "\033[37m"
GREEN = "\033[32m"
MAGENTA = "\033[35m"


def _visible_len(s: str) -> int:
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


def _pad(s: str, width: int) -> str:
    vis = _visible_len(s)
    return s + " " * max(0, width - vis)


def supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    term = os.environ.get("TERM", "")
    if "dumb" in term:
        return False
    return True


def colorize_text(text: str) -> str:
    if not supports_color():
        return text
    colored = ""
    for i, char in enumerate(text):
        gi = min(i * len(GRADIENT) // len(text), len(GRADIENT) - 1)
        r, g, b = GRADIENT[gi]
        colored += f"{_ansi_fg(r, g, b)}{char}"
    colored += RESET
    return colored


def _box_line(content: str, border_color: str, width: int) -> str:
    inner = width - 2
    padded = _pad(content, inner)
    return f"{border_color}│{RESET}{padded}{border_color}│{RESET}"


def render_welcome_dashboard() -> str:
    width = 60
    border_h = "─" * (width - 2)
    lines: list[str] = []
    
    # Border color: CYAN
    border_color = CYAN
    
    # Top border
    lines.append(f"{border_color}┌{border_h}┐{RESET}")
    
    # Title section
    lines.append(_box_line("", border_color, width))
    title_text = "T G  -  M U S I C"
    colored_title = f"{BOLD}{colorize_text(title_text)}{RESET}"
    title_line = f"  {colored_title}"
    
    # Center title line
    title_visible_len = len(title_text)
    left_padding = (width - 2 - title_visible_len) // 2
    centered_title_line = " " * left_padding + colored_title
    lines.append(_box_line(centered_title_line, border_color, width))
    
    subtitle = "Terminal music player for Telegram channels"
    left_padding_sub = (width - 2 - len(subtitle)) // 2
    centered_sub_line = " " * left_padding_sub + f"{DIM}{subtitle}{RESET}"
    lines.append(_box_line(centered_sub_line, border_color, width))
    lines.append(_box_line("", border_color, width))
    
    # Divider
    lines.append(f"{border_color}├{border_h}┤{RESET}")
    
    # SETUP section
    lines.append(_box_line("", border_color, width))
    lines.append(_box_line(f"  {BOLD}SETUP{RESET}", border_color, width))
    lines.append(_box_line("", border_color, width))
    
    steps = [
        f"{GREEN}1.{RESET} Go to {BOLD}https://my.telegram.org/apps{RESET}",
        f"{GREEN}2.{RESET} Log in and get your {BOLD}api_id{RESET} and {BOLD}api_hash{RESET}",
        f"{GREEN}3.{RESET} Run configuration command:",
    ]
    
    for step in steps:
        lines.append(_box_line(f"     {step}", border_color, width))
        
    lines.append(_box_line(f"     {GREEN}$ {BOLD}tg-music init{RESET}", border_color, width))
    lines.append(_box_line("", border_color, width))
    
    # Divider
    lines.append(f"{border_color}├{border_h}┤{RESET}")
    
    # QUICKSTART section
    lines.append(_box_line("", border_color, width))
    lines.append(_box_line(f"  {BOLD}QUICKSTART{RESET}", border_color, width))
    lines.append(_box_line("", border_color, width))
    
    cmds = [
        ("Scan a channel", "tg-music scan @channel --limit 300"),
        ("Open the player", "tg-music tui"),
        ("Cache tracks", "tg-music cache @channel --limit 50"),
    ]
    
    for desc, cmd in cmds:
        lines.append(_box_line(f"     {DIM}{desc:<18}{RESET} {GREEN}{BOLD}{cmd}{RESET}", border_color, width))
        
    lines.append(_box_line("", border_color, width))
    
    # Bottom border
    lines.append(f"{border_color}└{border_h}┘{RESET}")
    
    return "\n".join(lines)


def show_welcome() -> None:
    print()
    print(render_welcome_dashboard())
    print()


def is_configured() -> bool:
    from .config import CONFIG_FILE

    if not CONFIG_FILE.exists():
        return False
    import configparser

    parser = configparser.ConfigParser()
    parser.read(CONFIG_FILE)
    if not parser.has_section("telegram"):
        return False
    api_id = parser.get("telegram", "api_id", fallback="").strip()
    api_hash = parser.get("telegram", "api_hash", fallback="").strip()
    return bool(api_id and api_hash)


if __name__ == "__main__":
    show_welcome()
