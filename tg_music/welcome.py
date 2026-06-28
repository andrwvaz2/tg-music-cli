from __future__ import annotations

import os
import re
import sys
import textwrap


PIXEL_LETTERS: dict[str, list[str]] = {
    "T": [
        "#####",
        "  #  ",
        "  #  ",
        "  #  ",
        "  #  ",
    ],
    "G": [
        " ### ",
        "#    ",
        "#  ##",
        "#   #",
        " ### ",
    ],
    "M": [
        "#   #",
        "## ##",
        "# # #",
        "#   #",
        "#   #",
    ],
    "U": [
        "#   #",
        "#   #",
        "#   #",
        "#   #",
        " ### ",
    ],
    "S": [
        " ###",
        "#   ",
        " ## ",
        "   #",
        "### ",
    ],
    "I": [
        "###",
        " # ",
        " # ",
        " # ",
        "###",
    ],
    "C": [
        " ###",
        "#   ",
        "#   ",
        "#   ",
        " ###",
    ],
    " ": [
        "     ",
        "     ",
        "     ",
        "     ",
        "     ",
    ],
    "-": [
        "     ",
        "     ",
        "#####",
        "     ",
        "     ",
    ],
}

GRADIENT = [
    (255, 170, 0),
    (255, 140, 0),
    (255, 100, 0),
    (255, 60, 0),
    (255, 30, 0),
    (220, 0, 0),
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


def render_title(text: str) -> list[str]:
    rows: list[str] = [""] * 5
    for ch in text.upper():
        glyph = PIXEL_LETTERS.get(ch, PIXEL_LETTERS[" "])
        for i in range(5):
            rows[i] += glyph[i] + " "
    return rows


def colorize_title(rows: list[str]) -> list[str]:
    colored: list[str] = []
    for row in rows:
        parts: list[str] = []
        col = 0
        for ch in row:
            if ch == "#":
                gi = min(col // 1, len(GRADIENT) - 1)
                r, g, b = GRADIENT[gi]
                parts.append(f"{_ansi_fg(r, g, b)}\u2588{RESET}")
            else:
                parts.append(" ")
            col += 1
        colored.append("".join(parts))
    return colored


def supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    term = os.environ.get("TERM", "")
    if "dumb" in term:
        return False
    return True


def _box_line(content: str, border_color: str, width: int) -> str:
    inner = width - 2
    padded = _pad(content, inner)
    return f"{border_color}\u2502{RESET}{padded}{border_color}\u2502{RESET}"


def render_welcome_box() -> str:
    width = 58
    border_h = "\u2500" * (width - 2)
    lines: list[str] = []
    lines.append(f"{CYAN}\u250c{border_h}\u2510{RESET}")
    lines.append(_box_line("", CYAN, width))

    title_rows = render_title("TG-MUSIC")
    if supports_color():
        colored = colorize_title(title_rows)
    else:
        colored = title_rows

    for cr in colored:
        lines.append(_box_line(f"  {cr}", CYAN, width))

    lines.append(_box_line("", CYAN, width))
    lines.append(_box_line(f"{BOLD}Terminal music player for Telegram channels{RESET}", CYAN, width))
    lines.append(_box_line("", CYAN, width))
    lines.append(f"{CYAN}\u2514{border_h}\u2518{RESET}")

    return "\n".join(lines)


def render_setup_instructions() -> str:
    width = 58
    inner = width - 2
    border_h = "\u2500" * inner
    lines: list[str] = []
    lines.append("")
    lines.append(f"{YELLOW}\u250c{border_h}\u2510{RESET}")
    lines.append(_box_line(f"{BOLD}SETUP{RESET}", YELLOW, width))
    lines.append(_box_line("", YELLOW, width))

    steps = [
        f"{GREEN}1.{RESET} Go to {BOLD}https://my.telegram.org/apps{RESET}",
        f"{GREEN}2.{RESET} Enter your phone number and log in",
        f"{GREEN}3.{RESET} Enter the code sent to your Telegram",
        f"{GREEN}4.{RESET} Fill the form (app title, short name, platform)",
        f"{GREEN}5.{RESET} Click {BOLD}Create application{RESET}",
        f"{GREEN}6.{RESET} Copy your {BOLD}api_id{RESET} and {BOLD}api_hash{RESET}",
    ]

    for step in steps:
        wrapped = textwrap.wrap(step, width=inner - 4)
        for wline in wrapped:
            lines.append(_box_line(f"  {wline}", YELLOW, width))

    lines.append(_box_line("", YELLOW, width))
    lines.append(_box_line(f"{CYAN}{BOLD}Run this to configure:{RESET}", YELLOW, width))

    cmd = "tg-music init"
    lines.append(_box_line(f"  {GREEN}{BOLD}{cmd}{RESET}", YELLOW, width))

    lines.append(_box_line("", YELLOW, width))
    lines.append(f"{YELLOW}\u2514{border_h}\u2518{RESET}")

    return "\n".join(lines)


def render_quickstart() -> str:
    width = 58
    inner = width - 2
    border_h = "\u2500" * inner
    lines: list[str] = []
    lines.append("")
    lines.append(f"{MAGENTA}\u250c{border_h}\u2510{RESET}")
    lines.append(_box_line(f"{BOLD}QUICKSTART{RESET}", MAGENTA, width))
    lines.append(_box_line("", MAGENTA, width))

    cmds = [
        ("Scan a channel:", "tg-music scan @channel --limit 300"),
        ("Open the player:", "tg-music tui"),
        ("Download tracks:", "tg-music cache @channel --limit 50"),
    ]

    for desc, cmd in cmds:
        lines.append(_box_line(f"  {DIM}{desc}{RESET}", MAGENTA, width))
        lines.append(_box_line(f"    {GREEN}{BOLD}{cmd}{RESET}", MAGENTA, width))
        lines.append(_box_line("", MAGENTA, width))

    lines.append(f"{MAGENTA}\u2514{border_h}\u2518{RESET}")

    return "\n".join(lines)


def show_welcome() -> None:
    print()
    print(render_welcome_box())
    print(render_setup_instructions())
    print(render_quickstart())
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
