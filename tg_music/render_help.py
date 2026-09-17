from __future__ import annotations

import curses
import time

from . import get_version
from .models import format_duration
from .render_base import clear_terminal_images


class RenderHelpMixin:
    def toggle_help(self) -> None:
        self.help_visible = not self.help_visible
        clear_terminal_images()
        self.cover_graphics_pos = None
        self.cover_graphics_draw_key = None
        self.dirty = True

    def draw_help_overlay(self, width: int, height: int) -> None:
        col1_sections = [
            (
                "Playback",
                [
                    ("Enter", "Play selected track"),
                    ("Space", "Expand / Collapse"),
                    ("n / Right", "Next track"),
                    ("p / Left", "Previous track"),
                    ("s", "Stop playback"),
                    ("S", "Toggle shuffle"),
                    ("R", "Toggle repeat"),
                    ("+ / -", "Adjust volume"),
                ],
            ),
            (
                "Playlists & Queue",
                [
                    ("y", "View playlists"),
                    ("Y", "Add to playlist"),
                    ("e", "Add to play queue"),
                    ("E", "Clear play queue"),
                    ("[ / ]", "Reorder in queue/pl"),
                ],
            ),
        ]

        col2_sections = [
            (
                "Navigation",
                [
                    ("Up / Down", "Move selection"),
                    ("PgUp / PgDn", "Jump 10 tracks"),
                    ("Home / End", "First / last track"),
                    ("Tab", "Switch panel (split)"),
                    ("c", "Channel browser"),
                    ("r", "Reload track list"),
                ],
            ),
            (
                "Library",
                [
                    ("/", "Search / filter"),
                    ("G", "Global search (FTS)"),
                    ("f", "Toggle favorite"),
                    ("1", "Filter favorites only"),
                    ("t", "Tag track"),
                    ("a", "Add channel/playlist"),
                    ("u", "Scan current channel"),
                    ("g", "Open local folder"),
                    ("m", "Download missing"),
                    ("x", "Ignore track"),
                ],
            ),
        ]

        col3_sections = [
            (
                "Views & Display",
                [
                    ("P", "Split view (3 panels)"),
                    ("C", "Classic view"),
                    ("M", "Mini player mode"),
                    ("L", "Toggle lyrics"),
                ],
            ),
            (
                "Themes",
                [
                    ("T", "Cycle theme"),
                    ("F2", "Theme picker"),
                ],
            ),
            (
                "General & Commands",
                [
                    (":", "Command mode"),
                    (":login", "Log in to Telegram"),
                    ("? / H / F1", "Toggle this help"),
                    ("q", "Quit"),
                ],
            ),
        ]

        if width >= 105:
            columns = [col1_sections, col2_sections, col3_sections]
            overlay_w = min(114, width - 4)
        elif width >= 72:
            columns = [col1_sections + col3_sections[:1], col2_sections + col3_sections[1:]]
            overlay_w = min(82, width - 4)
        else:
            columns = [col1_sections + col2_sections + col3_sections]
            overlay_w = min(68, width - 4)

        overlay_h = min(23, height - 2) if height >= 25 else max(10, height - 2)
        start_y = max(1, (height - overlay_h) // 2)
        start_x = max(1, (width - overlay_w) // 2)

        panel_attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLACK)
        border_attr = self.color_attr(self.color_primary, curses.COLOR_BLACK) | curses.A_BOLD
        title_attr = self.color_attr(curses.COLOR_BLACK, self.color_primary) | curses.A_BOLD
        section_attr = self.color_attr(self.color_primary, curses.COLOR_BLACK) | curses.A_BOLD
        key_attr = self.color_attr(self.color_success, curses.COLOR_BLACK) | curses.A_BOLD
        desc_attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLACK)
        dim_attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLACK) | curses.A_DIM

        # Clear background box
        for y in range(start_y, start_y + overlay_h):
            self.screen.addnstr(y, start_x, " " * overlay_w, overlay_w, panel_attr)

        # Draw outer borders with rounded corners
        self.screen.addnstr(start_y, start_x, "\u256d" + "\u2500" * (overlay_w - 2) + "\u256e", overlay_w, border_attr)
        for y in range(start_y + 1, start_y + overlay_h - 1):
            self.screen.addnstr(y, start_x, "\u2502", 1, border_attr)
            self.screen.addnstr(y, start_x + overlay_w - 1, "\u2502", 1, border_attr)
        self.screen.addnstr(
            start_y + overlay_h - 1, start_x, "\u2570" + "\u2500" * (overlay_w - 2) + "\u256f", overlay_w, border_attr
        )

        # Title
        title = f" TG-MUSIC Help (v{get_version()}) "
        self.screen.addnstr(
            start_y, start_x + max(1, (overlay_w - len(title)) // 2), title, max(overlay_w - 2, 0), title_attr
        )

        num_cols = len(columns)
        total_inner_w = overlay_w - 2 - (num_cols - 1)
        col_w = max(total_inner_w // num_cols, 20)

        # Render columns and vertical column dividers
        for col_idx, col_data in enumerate(columns):
            cur_col_x = start_x + 1 + col_idx * (col_w + 1)
            if col_idx > 0:
                sep_x = cur_col_x - 1
                for y in range(start_y + 1, start_y + overlay_h - 1):
                    self.screen.addnstr(y, sep_x, "\u2502", 1, dim_attr)

            content_y = start_y + 1
            for section_name, keys in col_data:
                if content_y >= start_y + overlay_h - 2:
                    break
                sec_header = f" \u25b8 {section_name} "
                self.screen.addnstr(content_y, cur_col_x + 1, sec_header[: col_w - 1], max(col_w - 1, 0), section_attr)
                content_y += 1

                for key, desc in keys:
                    if content_y >= start_y + overlay_h - 1:
                        break
                    key_str = f" {key:<10}"
                    self.screen.addnstr(content_y, cur_col_x + 1, key_str[: col_w - 1], max(col_w - 1, 0), key_attr)
                    desc_x = cur_col_x + 1 + len(key_str)
                    avail_desc = max(col_w - len(key_str) - 1, 0)
                    if avail_desc > 0:
                        self.screen.addnstr(content_y, desc_x, desc[:avail_desc], avail_desc, desc_attr)
                    content_y += 1
                content_y += 1

        footer = " Presiona [?] o [Esc] para cerrar "
        self.screen.addnstr(
            start_y + overlay_h - 1,
            start_x + max(1, (overlay_w - len(footer)) // 2),
            footer,
            max(overlay_w - 2, 0),
            dim_attr,
        )

    def draw_mini(self) -> None:
        self.screen.erase()
        height, width = self.screen.getmaxyx()

        header_attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLUE) | curses.A_BOLD
        self.screen.addnstr(0, 0, "\u266b TG-MUSIC Mini", width - 1, header_attr)
        right_text = get_version()
        self.screen.addnstr(
            0, max(0, width - len(right_text) - 1), right_text, len(right_text), header_attr | curses.A_DIM
        )

        if self.current_track:
            status_text = f"Status: {self.status}"
            self.screen.addnstr(1, 0, status_text[: width - 1], width - 1)

            elapsed_str = "00:00"
            dur_str = "00:00"
            if self.play_start_time is not None:
                elapsed = int(time.time() - self.play_start_time)
                duration = self.current_track.duration or 0
                if duration > 0:
                    elapsed = min(elapsed, duration)
                elapsed_str = format_duration(elapsed)
                dur_str = format_duration(duration)

            bar_width = max(width - len(elapsed_str) - len(dur_str) - 6, 8)
            bar = self._make_slider_bar(
                int(elapsed_str.split(":")[0]) * 60 + int(elapsed_str.split(":")[1]),
                int(dur_str.split(":")[0]) * 60 + int(dur_str.split(":")[1]),
                bar_width,
            )
            progress = f" {elapsed_str} {bar} {dur_str}"
            self.screen.addnstr(2, 0, progress[: width - 1], width - 1, self.color_attr(self.color_success, -1))

            self.screen.addnstr(
                3,
                0,
                f" {self.current_track.display_title}"[: width - 1],
                width - 1,
                self.color_attr(self.color_success, -1) | curses.A_BOLD,
            )

            fav_mark = "\u2665" if self.current_track.id in self.favorite_ids else " "
            rep_mark = "R" if self.repeat_mode else " "
            shuf_mark = "S" if self.shuffle_mode else " "
            vol_text = f"Vol:{self.volume}%"
            info = f" {fav_mark} {rep_mark}{shuf_mark} {vol_text}"
            self.screen.addnstr(4, 0, info[: width - 1], width - 1, curses.A_DIM)
        else:
            self.screen.addnstr(1, 0, "No track playing"[: width - 1], width - 1, curses.A_DIM)

        if self.play_queue:
            queue_text = f"Queue: {len(self.play_queue)} tracks"
            self.screen.addnstr(height - 1, 0, queue_text[: width - 1], width - 1, curses.A_DIM)

        self.screen.refresh()
        self.dirty = False
