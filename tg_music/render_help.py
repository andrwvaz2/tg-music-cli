from __future__ import annotations

import curses
import time

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
        overlay_w = min(68, width - 4)
        overlay_h = min(28, height - 4)
        start_y = max(1, (height - overlay_h) // 2)
        start_x = max(1, (width - overlay_w) // 2)

        panel_attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLACK)
        border_attr = self.color_attr(curses.COLOR_CYAN, curses.COLOR_BLACK) | curses.A_BOLD
        title_attr = self.color_attr(curses.COLOR_BLACK, curses.COLOR_CYAN) | curses.A_BOLD
        section_attr = self.color_attr(curses.COLOR_CYAN, curses.COLOR_BLACK) | curses.A_BOLD
        key_attr = self.color_attr(curses.COLOR_GREEN, curses.COLOR_BLACK) | curses.A_BOLD
        desc_attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLACK)
        dim_attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLACK) | curses.A_DIM

        for y in range(start_y, start_y + overlay_h):
            self.screen.addnstr(y, start_x, " " * overlay_w, overlay_w, panel_attr)
        self.screen.addnstr(start_y, start_x, "\u250c" + "\u2500" * (overlay_w - 2) + "\u2510", overlay_w, border_attr)
        for y in range(start_y + 1, start_y + overlay_h - 1):
            self.screen.addnstr(y, start_x, "\u2502", 1, border_attr)
            self.screen.addnstr(y, start_x + overlay_w - 1, "\u2502", 1, border_attr)
        self.screen.addnstr(
            start_y + overlay_h - 1, start_x, "\u2514" + "\u2500" * (overlay_w - 2) + "\u2518", overlay_w, border_attr
        )

        title = " TG-MUSIC Help "
        self.screen.addnstr(
            start_y, start_x + max(1, (overlay_w - len(title)) // 2), title, max(overlay_w - 2, 0), title_attr
        )

        sections = [
            (
                "Playback",
                [
                    ("Enter", "Play selected track"),
                    ("Space", "Expand/collapse details"),
                    ("n / Right", "Next track"),
                    ("p / Left", "Previous track"),
                    ("S", "Stop playback"),
                    ("s", "Toggle shuffle"),
                    ("r", "Toggle repeat"),
                ],
            ),
            (
                "Navigation",
                [
                    ("Up/Down", "Move selection"),
                    ("PgUp/PgDn", "Page up/down"),
                    ("Home/End", "First/last track"),
                    ("Tab", "Switch panel (split)"),
                    ("c", "Switch to channels"),
                ],
            ),
            (
                "Library",
                [
                    ("/", "Search (live filter)"),
                    ("f", "Toggle favorite"),
                    ("t", "Tag prompt"),
                    ("1", "Filter favorites only"),
                    ("a", "Add channel"),
                    ("u", "Scan channel"),
                    ("g", "Open local folder"),
                    ("m", "Show missing tracks"),
                ],
            ),
            (
                "Playlists",
                [
                    ("y", "Toggle playlists view"),
                    ("Y", "Add to playlist"),
                    ("e", "Add to play queue"),
                    ("E", "Clear play queue"),
                ],
            ),
            (
                "Display",
                [
                    ("L", "Toggle lyrics"),
                    ("M", "Mini player mode"),
                    ("P", "Split view (3 panels)"),
                    ("C", "Classic view"),
                    (":", "Command mode"),
                    ("T", "Cycle theme"),
                    ("F2", "Theme picker"),
                    ("? / H / F1", "Toggle this help"),
                    ("q", "Quit"),
                ],
            ),
        ]

        content_y = start_y + 2
        for section_name, keys in sections:
            if content_y >= start_y + overlay_h - 2:
                break
            self.screen.addnstr(content_y, start_x + 2, f" {section_name} ", max(overlay_w - 4, 0), section_attr)
            content_y += 1
            for key, desc in keys:
                if content_y >= start_y + overlay_h - 1:
                    break
                self.screen.addnstr(content_y, start_x + 4, f"{key:<14}", max(overlay_w - 8, 0), key_attr)
                self.screen.addnstr(
                    content_y, start_x + 18, desc[: max(overlay_w - 22, 0)], max(overlay_w - 22, 0), desc_attr
                )
                content_y += 1
            content_y += 1

        footer = f" {overlay_w - 2} cols "
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
        right_text = "v0.1.0"
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
            bar = self._make_progress_bar(
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
