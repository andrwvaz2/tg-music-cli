from __future__ import annotations

import curses
import time

from .cover import render_cover
from .models import format_duration


class RenderSplitMixin:
    def draw_split_playback_tick(self) -> bool:
        if self.current_track is None or self.play_start_time is None:
            return False
        height, width = self.screen.getmaxyx()
        body_top = 3
        sep1 = max(width // 3, 20)
        sep2 = 2 * sep1 + 1
        if sep2 >= width - 5:
            sep2 = width - 6
        p3_start = sep2 + 1
        p3_w = max(width - p3_start - 1, 0)
        body_h = max(height - body_top - 2, 1)
        if p3_w <= 5:
            return False

        row = body_top + 1
        if self.current_track.performer:
            row += 1
        if row >= body_top + body_h:
            return False

        elapsed = int(time.time() - self.play_start_time)
        duration = self.current_track.duration or 0
        elapsed = min(elapsed, duration) if duration > 0 else elapsed
        elapsed_str = format_duration(elapsed)
        dur_str = format_duration(duration)
        bar_w = max(p3_w - len(elapsed_str) - len(dur_str) - 4, 6)
        bar = self._make_progress_bar(elapsed, duration, bar_w)
        text = f"{elapsed_str} {bar} {dur_str}"
        attr = self.color_attr(self.color_success, -1)
        self.screen.addnstr(row, p3_start + 1, " " * max(p3_w - 2, 0), max(p3_w - 2, 0), attr)
        self.screen.addnstr(row, p3_start + 1, text[: max(p3_w - 2, 0)], max(p3_w - 2, 0), attr)
        self.screen.refresh()
        return True

    def draw_split(self) -> None:
        self.screen.erase()
        self.cover_graphics_pos = None
        height, width = self.screen.getmaxyx()

        hdr_bg = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLUE) | curses.A_BOLD
        hdr_dim = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLUE) | curses.A_DIM
        sep_attr = self.color_attr(self.color_primary, -1) | curses.A_DIM
        body_attr = self.color_attr(self.color_primary, -1)
        body_bold = body_attr | curses.A_BOLD

        header_text = "\u266b TG-MUSIC \u25b8 Split View"
        if self.query:
            header_text += f" \u25b8 Search: {self.query}"
        if self.favorites_only:
            header_text += " \u25b8 \u2665 Fav"
        self.screen.addnstr(0, 0, header_text[:width - 1], width - 1, hdr_bg)
        ver = "v0.1.0"
        self.screen.addnstr(0, max(0, width - len(ver) - 1), ver, len(ver), hdr_dim)

        self.screen.addnstr(1, 0, f"Status: {self.status}"[:width - 1], width - 1, body_attr)
        self.screen.addnstr(2, 0, "\u2500" * (width - 1), width - 1, sep_attr)

        body_top = 3
        sep1 = max(width // 3, 20)
        sep2 = 2 * sep1 + 1
        if sep2 >= width - 5:
            sep2 = width - 6
        p1_w = sep1
        p2_start = sep1 + 1
        p2_w = sep2 - p2_start
        p3_start = sep2 + 1
        p3_w = max(width - p3_start - 1, 0)
        body_h = max(height - body_top - 2, 1)

        panel_labels = [
            (0, " CHANNELS ", p1_w),
            (p2_start, " \u266b TRACKS ", p2_w),
        ]
        if p3_w > 5:
            panel_labels.append((p3_start, " DETAILS ", p3_w))

        for px, label, pw in panel_labels:
            self.screen.addnstr(body_top - 1, px, label[:max(pw - 1, 0)], max(pw - 1, 0), body_bold)
            if px > 0:
                self.screen.addnstr(body_top - 1, px - 1, "\u2502", 1, sep_attr)

        sel_attr = self.color_attr(curses.COLOR_BLACK, curses.COLOR_CYAN) | curses.A_BOLD if not self.is_light else self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLUE) | curses.A_BOLD

        for row_idx in range(body_h):
            y = body_top + row_idx
            for sx in (sep1, sep2):
                if sx < width - 1:
                    self.screen.addnstr(y, sx, "\u2502", 1, sep_attr)

        from .local import LOCAL_CHANNEL
        split_channels: list[tuple[str, str, int]] = []
        if self.local_folder:
            from pathlib import Path
            local_count = sum(1 for t in self.tracks if t.channel == LOCAL_CHANNEL)
            local_name = f"Local ({Path(self.local_folder).name})"
            split_channels.append((LOCAL_CHANNEL, local_name, local_count))
        for ch in self.channels:
            count = sum(1 for t in self.tracks if t.channel == ch.channel)
            split_channels.append((ch.channel, ch.title or ch.channel, count))

        for row_idx, (ch_id, ch_name, count) in enumerate(split_channels[:body_h]):
            y = body_top + row_idx
            is_sel = (row_idx == self.selected and self.view == "channels")
            if is_sel:
                attr = sel_attr
            elif ch_id == self.channel_filter:
                attr = self.color_attr(self.color_success, -1) | curses.A_BOLD
            else:
                attr = curses.A_NORMAL
            active = "\u25cf" if ch_id == self.channel_filter else "\u25cb"
            icon = " " if ch_id != LOCAL_CHANNEL else "/"
            display_name = ch_name[:max(p1_w - 9, 1)]
            line = f"{active} {icon} {display_name} ({count})"
            self.screen.addnstr(y, 0, line[:max(p1_w - 1, 0)], max(p1_w - 1, 0), attr)

        tracks_to_show = self.tracks if self.channel_filter is None else [t for t in self.tracks if t.channel == self.channel_filter]
        track_offset = self.offset if self.view == "tracks" else 0
        for row_idx, track in enumerate(tracks_to_show[track_offset:track_offset + body_h]):
            y = body_top + row_idx
            real_idx = track_offset + row_idx
            is_sel = (real_idx == self.selected and self.view == "tracks")
            is_playing = self.current_track and track.id == self.current_track.id

            if is_sel:
                attr = sel_attr
            elif is_playing:
                attr = self.color_attr(self.color_success, -1) | curses.A_BOLD
            elif not track.local_path:
                attr = curses.A_DIM
            else:
                attr = curses.A_NORMAL

            playing = "\u25b6" if is_playing else " "
            is_caching = (track.id in self.precache_ids and not track.local_path) or (self.downloading_track_id == track.id)
            if is_caching:
                cache = "\u23f3"
            else:
                cache = "\u25bc" if track.local_path else "\u2601"
            dur = format_duration(track.duration)

            if is_playing:
                status_label = " [Playing]"
            elif is_caching:
                status_label = " [Caching]"
            elif track.local_path:
                status_label = " [Cached]"
            else:
                status_label = " [Remote]"

            line = f"{playing}{cache} {track.id:4d} {dur:>5} {track.display_title}{status_label}"
            self.screen.addnstr(y, p2_start, line[:max(p2_w - 1, 0)], max(p2_w - 1, 0), attr)

        if p3_w > 5:
            self.draw_split_details(body_top, p3_start, p3_w, body_h)

        self.draw_split_footer(height, width)
        if self.help_visible:
            self.draw_help_overlay(width, height)

        self.screen.refresh()
        if not self.help_visible:
            self.draw_graphics_cover()
        self.dirty = False

    def draw_split_details(self, top: int, x: int, width: int, height: int) -> None:
        row = top
        if self.current_track is None:
            self.screen.addnstr(row, x + 1, "No playing"[:max(width - 2, 0)], max(width - 2, 0), curses.A_DIM)
            return

        self.screen.addnstr(row, x + 1, self.current_track.title[:max(width - 2, 0)], max(width - 2, 0), self.color_attr(self.color_success, -1) | curses.A_BOLD)
        row += 1

        if self.current_track.performer:
            if row >= top + height:
                return
            self.screen.addnstr(row, x + 1, self.current_track.performer[:max(width - 2, 0)], max(width - 2, 0), curses.A_NORMAL)
            row += 1

        if self.play_start_time is not None and row < top + height:
            elapsed = int(time.time() - self.play_start_time)
            duration = self.current_track.duration or 0
            elapsed = min(elapsed, duration) if duration > 0 else elapsed
            elapsed_str = format_duration(elapsed)
            dur_str = format_duration(duration)
            bar_w = max(width - len(elapsed_str) - len(dur_str) - 4, 6)
            bar = self._make_progress_bar(elapsed, duration, bar_w)
            self.screen.addnstr(row, x + 1, f"{elapsed_str} {bar} {dur_str}"[:max(width - 2, 0)], max(width - 2, 0), self.color_attr(self.color_success, -1))
            row += 1

        queue_lines = 0
        if self.play_queue:
            queue_lines = 1 + min(len(self.play_queue), max(0, top + height - row - 3))

        remaining = top + height - row - queue_lines
        cover_h = max(remaining - 1, 0)
        cover_w = max(width - 4, 6)
        inner_width = max(cover_w - 2, 0)
        inner_height = max(cover_h - 2, 0)
        cover_x = x + 2

        if self.cover_path and cover_h >= 2:
            self.refresh_cover_art_size(
                max(inner_width, 6),
                max(inner_height, 4),
            )

        cover_lines = self.cover_lines
        if not self.cover_graphics and not cover_lines and self.cover_path:
            cover_w_for_render = max(cover_w - 4, 10)
            cover_lines = render_cover(self.cover_path, max_width=cover_w_for_render, max_height=max(cover_h - 4, 4))

        if self.cover_graphics and cover_h >= 2:
            blank_rows = min(inner_height, max(0, top + height - row))
            for blank_row in range(row, row + blank_rows):
                self.screen.addnstr(blank_row, cover_x, " " * inner_width, max(width - (cover_x - x) - 1, 0), curses.A_DIM)
            if blank_rows > 0:
                self.cover_graphics_pos = (row, cover_x)
                row += blank_rows
        elif cover_lines and cover_h >= 2:
            self.screen.addnstr(row, x + 1, "\u250c" + "\u2500" * (cover_w - 2) + "\u2510", max(width - 2, 0), curses.A_DIM)
            row += 1
            max_inner = min(cover_h - 2, top + height - row - 1)
            for i, cl in enumerate(cover_lines[:max(0, max_inner)]):
                vis_len = self.visible_width(cl)
                pad_l = max((cover_w - 2 - vis_len) // 2, 0)
                pad_r = max(cover_w - 2 - pad_l - vis_len, 0)
                self.screen.addnstr(row, x + 1, "\u2502", max(width - 2, 0), curses.A_DIM)
                self.screen.addnstr(row, x + 2, " " * inner_width, max(width - 3, 0), curses.A_DIM)
                if inner_width > 0:
                    self.add_ansi(row, x + 2 + pad_l, cl, max(inner_width - pad_l - pad_r, 0))
                self.screen.addnstr(row, x + 1 + cover_w - 1, "\u2502", max(width - cover_w - 1, 0), curses.A_DIM)
                row += 1
            if row < top + height:
                self.screen.addnstr(row, x + 1, "\u2514" + "\u2500" * (cover_w - 2) + "\u2518", max(width - 2, 0), curses.A_DIM)
                row += 1
        elif cover_h >= 2:
            self.screen.addnstr(row, x + 1, "\u250c" + "\u2500" * (cover_w - 2) + "\u2510", max(width - 2, 0), curses.A_DIM)
            row += 1
            for i in range(cover_h - 2):
                if row >= top + height - 1:
                    break
                if i == (cover_h - 2) // 2:
                    label = "No cover art" if not self.cover_path else "Cover Art"
                    pad = max((cover_w - 2 - len(label)) // 2, 0)
                    line = "\u2502" + " " * pad + label + " " * max(cover_w - 2 - pad - len(label), 0) + "\u2502"
                else:
                    line = "\u2502" + " " * (cover_w - 2) + "\u2502"
                self.screen.addnstr(row, x + 1, line, max(width - 2, 0), curses.A_DIM)
                row += 1
            if row < top + height:
                self.screen.addnstr(row, x + 1, "\u2514" + "\u2500" * (cover_w - 2) + "\u2518", max(width - 2, 0), curses.A_DIM)
                row += 1

        if self.play_queue and row < top + height:
            self.screen.addnstr(row, x + 1, "Queue:", max(width - 2, 0), self.color_attr(self.color_primary, -1) | curses.A_BOLD)
            row += 1
            q_lookup = {t.id: t for t in self.tracks}
            for qid in self.play_queue[:max(0, top + height - row)]:
                if row >= top + height:
                    break
                qt = q_lookup.get(qid)
                if qt:
                    self.screen.addnstr(row, x + 1, f"-> {qt.display_title}"[:max(width - 2, 0)], max(width - 2, 0), curses.A_DIM)
                    row += 1

    def draw_split_footer(self, height: int, width: int) -> None:
        panel_names = ["Channels", "Tracks", "Details"]
        panels_str = ""
        for idx, name in enumerate(panel_names):
            if idx == self.split_panel:
                panels_str += f" \u25b8 {name.upper()} "
            else:
                panels_str += f"   {name}  "

        if self.split_panel == 0:
            hints = [
                self.keycap("Enter", "open"),
                self.keycap("Space", "expand"),
                self.keycap("a", "add"),
                self.keycap("u", "scan"),
                self.keycap("Tab", "panel"),
                self.keycap("?", "help"),
            ]
        elif self.split_panel == 1:
            hints = [
                self.keycap("Enter", "play"),
                self.keycap("e", "queue"),
                self.keycap("f", "fav"),
                self.keycap("t", "tag"),
                self.keycap("L", "lyrics"),
                self.keycap("Tab", "panel"),
                self.keycap("?", "help"),
            ]
        else:
            hints = [
                self.keycap("Tab", "panel"),
                self.keycap("?", "help"),
            ]

        hints_str = "  ".join(hints)
        footer_attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLUE) | curses.A_BOLD
        sep_attr = self.color_attr(self.color_primary, -1) | curses.A_DIM
        self.screen.addnstr(height - 2, 0, "\u2500" * max(width - 1, 0), width - 1, sep_attr)
        self.screen.addnstr(height - 1, 0, " " * (width - 1), footer_attr)
        combined = f"{panels_str} \u2502  {hints_str}"
        if len(combined) > width - 1:
            combined = f"Panel: {panel_names[self.split_panel]}  |  {hints_str}"
            if len(combined) > width - 1:
                combined = hints_str
        self.screen.addnstr(height - 1, 0, combined[:width - 1], footer_attr)
