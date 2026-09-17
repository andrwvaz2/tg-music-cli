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


def hex_to_256(hex_value: str) -> int:
    """Map an ``#rrggbb`` hex color to the nearest xterm 256-color index."""
    hex_value = hex_value.lstrip("#")
    if len(hex_value) == 3:
        hex_value = "".join(ch * 2 for ch in hex_value)
    r = int(hex_value[0:2], 16)
    g = int(hex_value[2:4], 16)
    b = int(hex_value[4:6], 16)

    if r == g == b:
        idx = round((r - 8) / 247 * 23)
        return 232 + max(0, min(23, idx))

    cube = (0, 95, 135, 175, 215, 255)
    best = None
    for ri in range(6):
        for gi in range(6):
            for bi in range(6):
                cr, cg, cb = cube[ri], cube[gi], cube[bi]
                d = (cr - r) ** 2 + (cg - g) ** 2 + (cb - b) ** 2
                if best is None or d < best[0]:
                    best = (d, 16 + 36 * ri + 6 * gi + bi)
    return best[1]


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
        supports_256 = curses.COLORS >= 256

        def resolve(role: str, default: int) -> int:
            if supports_256 and ct.palette_256:
                hex_value = ct.palette_256.get(role)
                if hex_value:
                    return hex_to_256(hex_value)
            return default

        self.color_primary = resolve("primary", ct.primary)
        self.color_success = resolve("success", ct.success)
        self.color_warning = resolve("warning", ct.warning)
        self.color_error = resolve("error", ct.error)

        standards = [
            (self.color_primary, -1, 1),
            (self.color_success, -1, 2),
            (self.color_warning, -1, 3),
            (self.color_error, -1, 4),
            (resolve("blue", curses.COLOR_BLUE), -1, 5),
            (resolve("magenta", curses.COLOR_MAGENTA), -1, 6),
            (resolve("selected_fg", ct.selected_fg), resolve("selected_bg", ct.selected_bg), 7),
            (resolve("header_fg", ct.header_fg), resolve("header_bg", ct.header_bg), 8),
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

    def _make_slider_bar(self, elapsed: float, duration: float, width: int) -> str:
        width = max(width, 8)
        if duration <= 0:
            duration = 1
        percent = min(max(elapsed / duration, 0.0), 1.0)
        knob = int(round(percent * (width - 1)))
        knob = max(0, min(width - 1, knob))
        chars = ["\u2501"] * width
        chars[knob] = "\u25cf"
        return "".join(chars)

    def _make_volume_meter(self, volume: int, cells: int = 10) -> str:
        v = max(0, min(150, int(volume)))
        filled = int(round(v / 150 * cells))
        filled = max(0, min(cells, filled))
        return "\u25a0" * filled + "\u25a1" * (cells - filled)

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
            self.keycap("G", "g-search"),
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
