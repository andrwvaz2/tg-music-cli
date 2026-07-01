from __future__ import annotations

import curses
import re
import textwrap

CSI_RE = re.compile(r"\x1b\[([0-?]*)([ -/]*)([@-~])")


def clear_terminal_images() -> None:
    import sys

    try:
        sys.stdout.write("\x1b_Ga=d,d=A\x1b\\")
        sys.stdout.flush()
    except OSError:
        pass


def wrap(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=max(width, 10)) or [""]


def parse_ansi_sgr(text: str) -> list[tuple[str, int | None, int | None]]:
    parts: list[tuple[str, int | None, int | None]] = []
    pos = 0
    fg = -1
    bg = -1
    for match in CSI_RE.finditer(text):
        if match.start() > pos:
            parts.append((text[pos : match.start()], fg, bg))
        if match.group(3) != "m":
            pos = match.end()
            continue

        codes = [int(code) if code else 0 for code in match.group(1).split(";")]
        index = 0
        while index < len(codes):
            code = codes[index]
            if code == 0:
                fg = -1
                bg = -1
            elif code == 39:
                fg = -1
            elif code == 49:
                bg = -1
            elif code == 38 and index + 2 < len(codes) and codes[index + 1] == 5:
                fg = codes[index + 2]
                index += 2
            elif code == 48 and index + 2 < len(codes) and codes[index + 1] == 5:
                bg = codes[index + 2]
                index += 2
            index += 1
        pos = match.end()
    if pos < len(text):
        parts.append((text[pos:], fg, bg))
    return parts


class RenderBaseMixin:
    def add(self, y: int, x: int, text: str, attr: int = curses.A_NORMAL) -> None:
        height, width = self.screen.getmaxyx()
        if y < height and x < width:
            self.screen.addstr(y, x, text[: max(width - x - 1, 0)], attr)

    def add_ansi(self, y: int, x: int, text: str, max_width: int) -> None:
        height, width = self.screen.getmaxyx()
        if y >= height or x >= width:
            return

        col = x
        visible = 0
        for chunk, fg, bg in parse_ansi_sgr(text):
            if not chunk:
                continue
            attr = self.color_attr(fg, bg)
            for char in chunk:
                if visible >= max_width or col >= width - 1:
                    return
                self.screen.addstr(y, col, char, attr)
                col += 1
                visible += 1

    def init_colors(self) -> None:
        if not curses.has_colors():
            return
        curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            pass

        ct = self.current_color_theme()
        self.color_primary = ct.primary
        self.color_success = ct.success
        self.color_warning = ct.warning
        self.color_error = ct.error

        standards = [
            (ct.primary, -1, 1),
            (ct.success, -1, 2),
            (ct.warning, -1, 3),
            (ct.error, -1, 4),
            (curses.COLOR_BLUE, -1, 5),
            (curses.COLOR_MAGENTA, -1, 6),
            (ct.selected_fg, ct.selected_bg, 7),
            (ct.header_fg, ct.header_bg, 8),
        ]

        for fg, bg, pair_id in standards:
            try:
                curses.init_pair(pair_id, fg, bg)
                self.color_pairs[(fg, bg)] = pair_id
            except curses.error:
                pass

    def color_attr(self, fg: int, bg: int) -> int:
        if not curses.has_colors():
            return curses.A_NORMAL
        if fg >= curses.COLORS:
            fg = -1
        if bg >= curses.COLORS:
            bg = -1
        key = (fg, bg)
        pair = self.color_pairs.get(key)
        if pair is None:
            pair = len(self.color_pairs) + 1
            if pair >= curses.COLOR_PAIRS:
                return curses.A_NORMAL
            try:
                curses.init_pair(pair, fg, bg)
            except curses.error:
                return curses.A_NORMAL
            self.color_pairs[key] = pair
        return curses.color_pair(pair)

    def _make_progress_bar(self, elapsed: float, duration: float, width: int) -> str:
        bar_width = max(width, 8)
        percent = min(elapsed / duration, 1.0) if duration > 0 else 0
        filled = int(percent * bar_width)
        fraction = (percent * bar_width) - filled
        bar = "\u2588" * filled
        if filled < bar_width:
            if fraction >= 0.75:
                bar += "\u258a"
            elif fraction >= 0.5:
                bar += "\u258c"
            elif fraction >= 0.25:
                bar += "\u258e"
            else:
                bar += "\u2591"
            remaining = bar_width - len(bar)
            if remaining > 0:
                bar += "\u2591" * remaining
        return bar

    def cover_size(self, screen_height: int | None = None, screen_width: int | None = None) -> tuple[int, int]:
        if screen_height is None or screen_width is None:
            screen_height, screen_width = self.screen.getmaxyx()
        right_width = max(screen_width - (max(42, int(screen_width * 0.58)) + 1), 0)
        panel_height = screen_height - 5
        return self.cover_box_size(right_width, panel_height)

    def cover_box_size(self, panel_width: int, panel_height: int) -> tuple[int, int]:
        if panel_width <= 0 or panel_height <= 0:
            return (24, 6)
        cover_width = max(24, min(panel_width - 4, 60))
        cover_height = max(6, min(panel_height - 8, 30))
        return cover_width, cover_height

    def visible_width(self, text: str) -> int:
        return len(CSI_RE.sub("", text))

    def keycap(self, key: str, label: str) -> str:
        return f"[{key}] {label}"

    def keybind_line(self, width: int) -> str:
        bindings = [
            self.keycap("Enter", "open"),
            self.keycap("Space", "expand"),
            self.keycap("e", "queue"),
            self.keycap("m", "missing"),
            self.keycap("f", "fav"),
            self.keycap("1", "fav filt"),
            self.keycap("t", "tag"),
            self.keycap("y", "playlists"),
            self.keycap("Y", "add pl"),
            self.keycap("g", "local"),
            self.keycap("/", "search"),
            self.keycap("s", "shuffle"),
            self.keycap("r", "repeat"),
            self.keycap("S", "stop"),
            self.keycap("M", "mini"),
            self.keycap("P", "split"),
            self.keycap("C", "classic"),
            self.keycap("Tab", "panel"),
            self.keycap(":", "cmd"),
            self.keycap("?", "help"),
            self.keycap("q", "quit"),
        ]
        text = "  ".join(bindings)
        if len(text) <= width - 1:
            return text
        return " ".join([self.keycap("?", "help"), self.keycap("q", "quit")])[: max(width - 1, 0)]
