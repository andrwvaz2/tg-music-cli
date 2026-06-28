from __future__ import annotations

import curses
import re
import time

from .cover import render_cover, render_graphics_cover, supports_graphics_cover
from .db import connect, get_track_tags, is_favorite
from .models import format_duration

CSI_RE = re.compile(r"\x1b\[([0-?]*)([ -/]*)([@-~])")


class RenderMixin:
    def draw(self) -> None:
        from .local import LOCAL_CHANNEL
        if self.mini_mode:
            self.draw_mini()
            return
        if self.split_mode:
            self.draw_split()
            return
        self.screen.erase()
        self.cover_graphics_pos = None
        height, width = self.screen.getmaxyx()
        if not self.help_visible and self.current_track is not None and self.cover_path is not None:
            self.refresh_cover_art(height, width)

        header_attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLUE) | curses.A_BOLD
        header_dim = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLUE) | curses.A_DIM
        self.add(0, 0, " " * width, header_attr)

        parts = ["\u266b TG-MUSIC"]
        if self.view == "channels":
            parts.append("\u25b8 Channels")
        elif self.channel_filter:
            channel_title = self.channel_filter
            for ch in self.channels:
                if ch.channel == self.channel_filter and ch.title:
                    channel_title = ch.title
                    break
            parts.append(f"\u25b8 {channel_title}")
        if self.query:
            parts.append(f"\u25b8 \U0001f50d {self.query}")
        if self.favorites_only:
            parts.append("\u25b8 \u2665 Favoritos")
        if self.tag_filter:
            parts.append(f"\u25b8 \U0001f3f7 {self.tag_filter}")
        if self.playlist_filter:
            parts.append(f"\u25b8 \U0001f3b5 {self.playlist_filter}")

        breadcrumb = " ".join(parts)
        if len(breadcrumb) > width - 1:
            breadcrumb = breadcrumb[: width - 4] + "..."
        self.add(0, 0, breadcrumb, header_attr)

        right_text = "v0.1.0"
        self.add(0, max(0, width - len(right_text) - 1), right_text, header_dim)

        cache_status = self.cache_line[7:] if self.cache_line.startswith("Cache: ") else self.cache_line
        self.add(1, 0, f"Cache: {cache_status}"[: width - 1])
        self.add(2, 0, self.keybind_line(width), curses.A_DIM)
        self.add(3, 0, f"Status: {self.status}"[: width - 1], self.color_attr(self.color_primary, -1))
        self.add(4, 0, "\u2500" * max(width - 1, 0), self.color_attr(self.color_primary, -1) | curses.A_DIM)

        left_width = max(42, int(width * 0.58))
        if width < 90:
            left_width = width
        right_x = left_width + 1
        right_width = max(width - right_x, 0)
        body_top = 6
        if self.view == "playlists":
            left_title = "\U0001f3b5 PLAYLISTS"
        elif self.view == "channels":
            left_title = "\U0001f4f9 CHANNELS"
        else:
            left_title = "\u266b TRACKS"
            if self.channel_filter:
                channel_title = self.channel_filter
                for ch in self.channels:
                    if ch.channel == self.channel_filter and ch.title:
                        channel_title = ch.title
                        break
                left_title = f"\u266b {channel_title}"
            if self.playlist_filter:
                left_title = f"\U0001f3b5 {self.playlist_filter}"
        self.add(5, 0, f" {left_title} "[: max(left_width - 1, 0)], self.color_attr(self.color_primary, -1) | curses.A_BOLD)
        if right_width > 12:
            self.add(5, right_x, " \U0001f4fa DETAILS "[: max(right_width - 1, 0)], self.color_attr(self.color_primary, -1) | curses.A_BOLD)
        visible_height = max(height - body_top - 1, 1)
        if self.selected < self.offset:
            self.offset = self.selected
        elif self.selected >= self.offset + visible_height:
            self.offset = self.selected - visible_height + 1

        if self.view == "channels":
            self._draw_channel_rows(body_top, visible_height, left_width)
        elif self.view == "playlists":
            self.draw_playlists(body_top, visible_height, left_width)
        else:
            self.draw_tracks(body_top, visible_height, left_width)

        if right_width > 12:
            self.draw_right_panel(body_top, right_x, right_width, height - body_top)

        if self.help_visible:
            self.draw_help_overlay(width, height)

        self.screen.refresh()
        if not self.help_visible:
            self.draw_graphics_cover()
        self.dirty = False

    def _draw_channel_rows(self, body_top: int, visible_height: int, left_width: int) -> None:
        from .local import LOCAL_CHANNEL
        for row, item in enumerate(
            self.browser_rows[self.offset : self.offset + visible_height], start=body_top
        ):
            index = self.offset + row - body_top
            is_selected = index == self.selected
            attr = (
                self.color_attr(curses.COLOR_BLACK, curses.COLOR_CYAN) | curses.A_BOLD
                if is_selected and not self.is_light
                else self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLUE) | curses.A_BOLD
                if is_selected
                else curses.A_NORMAL
            )
            if item["kind"] == "local":
                title = item["title"]
                count = item["count"]
                is_expanded = LOCAL_CHANNEL in self.expanded_channels
                marker = "\u25be" if is_expanded else "\u25b8"
                active = "\u25cf" if self.channel_filter is None and self.local_folder else "\u25cb"
                line = f"{marker} \U0001f4c1 {title} ({count})"
            elif item["kind"] == "channel":
                channel = item["channel"]
                expanded = channel.channel in self.expanded_channels
                marker = "\u25be" if expanded else "\u25b8"
                active = "\u25cf" if channel.channel == self.channel_filter else "\u25cb"
                count = sum(1 for track in self.tracks if track.channel == channel.channel)
                title = channel.title or channel.channel
                line = f"{marker} {active}  \U0001f4ac  {channel.channel:24s}  {title} ({count})"
            else:
                track = item["track"]
                cache = "#" if track.local_path else "."
                prefix = "  \u251c\u2500"
                line = f"{prefix} {cache}  {track.display_title}"
                attr = self.color_attr(self.color_success, -1) | curses.A_DIM if not is_selected else attr
            self.add(row, 0, f"{line:<{left_width-1}}"[: max(left_width - 1, 0)], attr)

    def draw_mini(self) -> None:
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        if self.current_track is None:
            self.add(0, 0, "TG-MUSIC: No playing"[: width - 1], curses.A_BOLD)
            self.screen.refresh()
            self.dirty = False
            return

        elapsed = int(time.time() - self.play_start_time) if self.play_start_time else 0
        dur = format_duration(self.current_track.duration)
        elapsed_str = format_duration(elapsed)
        with connect() as conn:
            fav = "\u2665" if is_favorite(conn, self.current_track.id) else " "
        rep_indicator = "\u21bb" if self.repeat_mode else "-"
        shf_indicator = "\u21c6" if self.shuffle_mode else "-"
        play_state = "\u25b6" if self.player.is_playing() else "\u25a0"

        bar_width = max(width - len(elapsed_str) - len(dur) - 22, 8)
        bar = self._make_progress_bar(elapsed, self.current_track.duration or 0, bar_width)

        line1 = f"{play_state} {fav} [{rep_indicator}] [{shf_indicator}] {self.current_track.display_title}"
        line2 = f"  {elapsed_str} {bar} {dur}  vol:{self.volume}%"

        self.add(0, 0, line1[: width - 1], self.color_attr(self.color_success, -1) | curses.A_BOLD)
        if height > 1:
            self.add(1, 0, line2[: width - 1], self.color_attr(self.color_primary, -1))
        if height > 2:
            hints = "[q]uit [n]ext [s]top [+]vol [-]vol [R]epeat [S]huffle [T]heme [f]av [M]ini"
            self.add(2, 0, hints[: width - 1], curses.A_DIM)

        self.screen.refresh()
        self.dirty = False

    def draw_playlists(self, body_top: int, visible_height: int, left_width: int) -> None:
        if not self.playlists:
            msg = "No hay playlists. Presiona 'a' para crear una."
            self.add(body_top, 0, msg[: left_width - 1], curses.A_DIM)
            return
        for row_idx, pl in enumerate(self.playlists[self.offset : self.offset + visible_height]):
            y = body_top + row_idx
            real_idx = self.offset + row_idx
            is_sel = real_idx == self.selected
            if is_sel:
                attr = self.color_attr(curses.COLOR_BLACK, curses.COLOR_CYAN) | curses.A_BOLD if not self.is_light else self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLUE) | curses.A_BOLD
            else:
                attr = curses.A_NORMAL
            line = f" {pl['name']:<30s}  {pl['count']:4d} tracks"
            self.add(y, 0, line[: left_width - 1], attr)

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
            header_text += f" \u25b8 \U0001f50d {self.query}"
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
            (0, " \U0001f4f9 CHANNELS ", p1_w),
            (p2_start, " \u266b TRACKS ", p2_w),
        ]
        if p3_w > 5:
            panel_labels.append((p3_start, " \U0001f4fa DETAILS ", p3_w))

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
            local_name = f"\U0001f4c1 Local ({Path(self.local_folder).name})"
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
            icon = "\U0001f4ac" if ch_id != LOCAL_CHANNEL else "\U0001f4c1"
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
                status_label = " [Sonando]"
            elif is_caching:
                status_label = " [Cacheando]"
            elif track.local_path:
                status_label = " [Caché]"
            else:
                status_label = " [Remoto]"

            line = f"{playing}{cache} {track.id:4d} {dur:>5} {track.display_title}{status_label}"
            self.screen.addnstr(y, p2_start, line[:max(p2_w - 1, 0)], max(p2_w - 1, 0), attr)

        if p3_w > 5:
            self.draw_split_details(body_top, p3_start, p3_w, body_h)

        self.draw_split_footer(height, width)

        self.screen.refresh()
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
            self.screen.addnstr(row, x + 1, "Cola:", max(width - 2, 0), self.color_attr(self.color_primary, -1) | curses.A_BOLD)
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
                self.keycap("Enter", "abrir"),
                self.keycap("Space", "expandir"),
                self.keycap("a", "agregar"),
                self.keycap("u", "escanear"),
                self.keycap("Tab", "panel"),
                self.keycap("?", "ayuda"),
            ]
        elif self.split_panel == 1:
            hints = [
                self.keycap("Enter", "play"),
                self.keycap("e", "cola"),
                self.keycap("f", "fav"),
                self.keycap("t", "tag"),
                self.keycap("L", "letras"),
                self.keycap("Tab", "panel"),
                self.keycap("?", "ayuda"),
            ]
        else:
            hints = [
                self.keycap("Tab", "panel"),
                self.keycap("?", "ayuda"),
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

    def draw_tracks(self, body_top: int, visible_height: int, left_width: int) -> None:
        from .local import LOCAL_CHANNEL

        for row, track in enumerate(self.tracks[self.offset : self.offset + visible_height], start=body_top):
            index = self.offset + row - body_top

            is_selected = index == self.selected
            is_playing = self.current_track and track.id == self.current_track.id
            is_cached = bool(track.local_path)
            is_local = track.channel == LOCAL_CHANNEL

            marker = "\u276f" if is_selected else " "
            playing = "\u25b6" if is_playing else " "
            is_caching = (track.id in self.precache_ids and not is_cached) or (self.downloading_track_id == track.id)
            if is_caching:
                cache = "\u23f3"
            else:
                cache = "\u25bc" if is_cached else "\u2601"
            source = "\u25cb" if is_local else " "

            if is_selected:
                if self.is_light:
                    attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLUE) | curses.A_BOLD
                else:
                    attr = self.color_attr(curses.COLOR_BLACK, curses.COLOR_CYAN) | curses.A_BOLD
            elif is_playing:
                attr = self.color_attr(self.color_success, -1) | curses.A_BOLD
            elif is_local:
                attr = self.color_attr(self.color_warning, -1)
            else:
                attr = curses.A_NORMAL

            if not is_cached and not is_selected and not is_playing:
                attr |= curses.A_DIM

            dur = format_duration(track.duration)
            queue_mark = "Q" if track.id in self.play_queue else " "
            fav_mark = "\u2665" if track.id in self.favorite_ids else " "

            if is_playing:
                status_label = "[Sonando]"
            elif is_caching:
                status_label = "[Cacheando]"
            elif is_cached:
                status_label = "[Caché]"
            else:
                status_label = "[Remoto]"

            line = (
                f"{marker} {playing}{cache}{queue_mark}{fav_mark}{source} {track.id:4d}  \u2514\u2500 "
                f"{dur:>5}  {track.display_title} {status_label}"
            )
            if is_selected:
                line_padded = f"{line:<{left_width-1}}"
            else:
                line_padded = line
            self.add(row, 0, line_padded[: max(left_width - 1, 0)], attr)

    def draw_right_panel(self, top: int, x: int, width: int, height: int) -> None:
        border_attr = self.color_attr(self.color_primary, -1) | curses.A_DIM
        for row in range(top, top + height):
            self.add(row, x - 1, "\u2502", border_attr)

        title = "NOW PLAYING"
        self.add(top, x + 1, title[: max(width - 2, 0)], self.color_attr(self.color_primary, -1) | curses.A_BOLD)
        row = top + 1
        cover_top = None
        cover_x = None
        cover_width = 0
        cover_height = 0
        if self.current_track is not None and self.cover_path is not None:
            cover_width, cover_height = self.cover_box_size(width, height)
            cover_top = max(top + 2, top + height - cover_height - 1)
            cover_x = x + 1 + max(0, (width - 2 - cover_width) // 2)

        if self.lyrics_visible and self.lyrics_text:
            for line in self.lyrics_text.splitlines()[: max(0, top + height - row - 1)]:
                if cover_top is not None and row >= cover_top:
                    break
                self.add(row, x + 1, line[: max(width - 2, 0)], self.color_attr(self.color_success, -1))
                row += 1
            if row < top + height - 1:
                self.screen.refresh()
                self.dirty = False
                return

        if self.view == "channels":
            lines = [
                "Library browser",
                "",
                "Enter: open folder",
                "Space/Right: expand",
                "Backspace/Left: collapse",
                "a: add a channel",
                "u: scan current folder",
                "/: search current view",
            ]
            for text in lines:
                attr = self.color_attr(self.color_success, -1) | curses.A_BOLD if text == "Library browser" else curses.A_NORMAL
                for line in wrap(text, width - 2):
                    if cover_top is not None and row >= cover_top:
                        return
                    self.add(row, x + 1, line, attr)
                    row += 1
            return
        if self.current_track is None:
            for line in wrap("Select a track with Enter to start playback.", width - 2):
                if cover_top is not None and row >= cover_top:
                    return
                self.add(row, x + 1, line, curses.A_DIM)
                row += 1
            return

        for line in wrap(self.current_track.display_title, width - 2):
            if cover_top is not None and row >= cover_top:
                break
            self.add(row, x + 1, line, self.color_attr(self.color_success, -1) | curses.A_BOLD)
            row += 1

        with connect() as conn:
            fav = is_favorite(conn, self.current_track.id)
            tags = get_track_tags(conn, self.current_track.id)

        info_items = [
            ("Channel", self.current_track.channel_title),
            ("Duration", format_duration(self.current_track.duration)),
            ("Cache", "Ready" if self.current_audio_path else "Pending"),
            ("Queue", str(len(self.play_queue))),
            ("Favorite", "Yes" if fav else "No"),
            ("Volume", f"{self.volume}%"),
            ("Repeat", "On" if self.repeat_mode else "Off"),
            ("Shuffle", "On" if self.shuffle_mode else "Off"),
        ]
        if tags:
            info_items.append(("Tags", ", ".join(tags)))
        for label, val in info_items:
            label_text = f"{label}: "
            if cover_top is not None and row >= cover_top:
                break
            self.add(row, x + 1, label_text, self.color_attr(self.color_primary, -1))
            val_x = x + 1 + len(label_text)
            val_width = max(width - len(label_text) - 2, 5)
            for line in wrap(val, val_width):
                if cover_top is not None and row >= cover_top:
                    break
                self.add(row, val_x, line)
                row += 1

        if self.current_track is not None and self.play_start_time is not None:
            if row < top + height - 1 and (cover_top is None or row < cover_top):
                self.add(row, x + 1, "Progress", self.color_attr(self.color_primary, -1) | curses.A_BOLD)
                row += 1

                elapsed = int(time.time() - self.play_start_time)
                duration = self.current_track.duration or 0
                if duration > 0:
                    elapsed = min(elapsed, duration)
                elapsed_str = format_duration(elapsed)
                duration_str = format_duration(duration)

                bar_width = max(width - len(elapsed_str) - len(duration_str) - 6, 8)
                bar = self._make_progress_bar(elapsed, duration, bar_width)
                timeline_text = f" {elapsed_str} {bar} {duration_str}"
                self.add(row, x + 1, timeline_text[: max(width - 2, 0)], self.color_attr(self.color_success, -1))
                row += 1

        if self.play_queue:
            if row < top + height - 1 and (cover_top is None or row < cover_top):
                self.add(row, x + 1, "Queue", self.color_attr(self.color_primary, -1) | curses.A_BOLD)
                row += 1
                queued_lookup = {track.id: track for track in self.tracks}
                queued_tracks = [queued_lookup[qid] for qid in self.play_queue if qid in queued_lookup]
                self.add(row, x + 1, "[ / ] to reorder", curses.A_DIM)
                row += 1
                for queued in queued_tracks[: max(0, top + height - row - 1)]:
                    self.add(row, x + 1, f"\u2022 {queued.display_title}"[: max(width - 2, 0)], curses.A_DIM)
                    row += 1

        if self.cover_lines:
            if cover_top is not None:
                self.add(cover_top, x + 1, "Cover", self.color_attr(self.color_primary, -1) | curses.A_BOLD)
                text_row = cover_top + 1
                for line in self.cover_lines[: max(0, top + height - text_row - 1)]:
                    line_width = self.visible_width(line)
                    line_x = x + 1 + max(0, (width - 2 - line_width) // 2)
                    self.add_ansi(text_row, line_x, line, max(width - (line_x - x) - 1, 0))
                    text_row += 1
        elif self.cover_graphics:
            if cover_top is not None and cover_x is not None:
                self.add(cover_top, x + 1, "Cover", self.color_attr(self.color_primary, -1) | curses.A_BOLD)
                self.cover_graphics_pos = (cover_top + 1, cover_x)
                blank_rows = max(0, min(cover_height, top + height - (cover_top + 1) - 1))
                if blank_rows > 2:
                    for blank_row in range(cover_top + 1, cover_top + 1 + blank_rows):
                        self.add(blank_row, cover_x, " " * max(cover_width, 0))
                else:
                    self.add(cover_top + 1, cover_x, "No hay espacio vertical para la portada.", curses.A_DIM)
        elif self.cover_path:
            if cover_top is not None:
                fallback = "Install chafa to render the cover art here."
                for line in wrap(fallback, width - 2):
                    self.add(cover_top, x + 1 + max(0, (width - 2 - len(line)) // 2), line, curses.A_DIM)
                    break
        else:
            if cover_top is not None:
                for line in wrap("No cover art available.", width - 2):
                    self.add(cover_top, x + 1 + max(0, (width - 2 - len(line)) // 2), line, curses.A_DIM)
                    break

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
            self.keycap("R", "repeat"),
            self.keycap("S", "shuffle"),
            self.keycap("+/-", "vol"),
            self.keycap("L", "lyrics"),
            self.keycap("M", "mini"),
            self.keycap("P", "split"),
            self.keycap("Tab", "panel"),
            self.keycap(":", "cmd"),
            self.keycap("?", "help"),
            self.keycap("q", "quit"),
        ]
        text = "  ".join(bindings)
        if len(text) <= width - 1:
            return text
        return " ".join([self.keycap("?", "help"), self.keycap("q", "quit")])[: max(width - 1, 0)]

    def keycap(self, key: str, label: str) -> str:
        return f"[{key}] {label}"

    def toggle_help(self) -> None:
        self.help_visible = not self.help_visible
        if self.help_visible:
            self.status = "Help open"
            clear_terminal_images()
        self.dirty = True

    def draw_help_overlay(self, width: int, height: int) -> None:
        overlay_w = min(max(60, int(width * 0.64)), width - 4)
        overlay_h = min(28, height - 4)
        if overlay_w < 20 or overlay_h < 8:
            return
        start_x = max(2, (width - overlay_w) // 2)
        start_y = max(2, (height - overlay_h) // 2)
        if self.is_light:
            panel_attr = self.color_attr(curses.COLOR_BLACK, curses.COLOR_WHITE)
            frame_attr = self.color_attr(curses.COLOR_BLUE, curses.COLOR_WHITE) | curses.A_BOLD
            accent_attr = self.color_attr(curses.COLOR_BLUE, curses.COLOR_WHITE) | curses.A_BOLD
            title_attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLUE) | curses.A_BOLD
        else:
            panel_attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLACK)
            frame_attr = self.color_attr(curses.COLOR_CYAN, curses.COLOR_BLACK) | curses.A_BOLD
            accent_attr = self.color_attr(curses.COLOR_CYAN, curses.COLOR_BLACK) | curses.A_BOLD
            title_attr = self.color_attr(curses.COLOR_BLACK, curses.COLOR_CYAN) | curses.A_BOLD

        dim_attr = curses.A_DIM
        inner_w = overlay_w - 2

        for row in range(start_y, start_y + overlay_h):
            self.add(row, start_x, " " * overlay_w, panel_attr)
        self.add(start_y, start_x, "\u250c" + "\u2500" * (overlay_w - 2) + "\u2510", frame_attr)
        for row in range(start_y + 1, start_y + overlay_h - 1):
            self.add(row, start_x, "\u2502", frame_attr)
            self.add(row, start_x + overlay_w - 1, "\u2502", frame_attr)
        self.add(start_y + overlay_h - 1, start_x, "\u2514" + "\u2500" * (overlay_w - 2) + "\u2518", frame_attr)

        title = " KEYBOARD HELP "
        self.add(start_y, start_x + max(2, (overlay_w - len(title)) // 2), title[:inner_w], title_attr)
        close_text = "Press ? or F1 to close"
        self.add(start_y + overlay_h - 1, start_x + max(2, (overlay_w - len(close_text)) // 2), close_text[:inner_w], accent_attr)

        lines = [
            ("Navigation", "Enter open folder or play track"),
            ("", "Space / Right expands a channel"),
            ("", "Backspace / Left collapses or goes up"),
            ("", "j / k move, / search, r refresh"),
            ("Queue", "e enqueues the selected track"),
            ("", "[ and ] reorder queue items"),
            ("Library", "m downloads missing tracks"),
            ("", "w checks for new music on the active channel"),
            ("", "W toggles background watching"),
            ("Playback", "n next, s stop, x ignore selected"),
            ("", "+ / - volume, R repeat, S shuffle"),
            ("", "f favorite, L lyrics, M mini view, F2 theme picker"),
            ("", "P split view, Tab switch panel"),
            ("", "T toggle theme, t add tag, 1 filter favorites"),
            ("", "y view playlists, Y add to playlist"),
            ("", "g open local folder"),
            ("System", "c channels, a add channel, : commands, ? help, q quit"),
        ]
        row = start_y + 2
        for heading, text in lines:
            if row >= start_y + overlay_h - 1:
                break
            if heading:
                self.add(row, start_x + 2, heading, accent_attr)
                row += 1
                if row >= start_y + overlay_h - 1:
                    break
            self.add(row, start_x + 4, text[: overlay_w - 6], dim_attr)
            row += 1

    def add(self, y: int, x: int, text: str, attr: int = curses.A_NORMAL) -> None:
        height, width = self.screen.getmaxyx()
        if y < height and x < width:
            self.screen.addstr(y, x, text[: max(width - x - 1, 0)], attr)

    def draw_graphics_cover(self) -> None:
        if self.help_visible:
            if self.cover_graphics_draw_key is not None:
                clear_terminal_images()
                self.cover_graphics_draw_key = None
            return
        if not self.cover_graphics or self.cover_graphics_pos is None:
            if self.cover_graphics_draw_key is not None:
                clear_terminal_images()
                self.cover_graphics_draw_key = None
            return
        row, col = self.cover_graphics_pos
        draw_key = (self.cover_render_key, self.cover_graphics_pos)
        if draw_key == self.cover_graphics_draw_key:
            return
        try:
            clear_terminal_images()
            import sys
            sys.stdout.buffer.write(f"\x1b[{row + 1};{col + 1}H".encode("ascii"))
            sys.stdout.buffer.write(self.cover_graphics)
            sys.stdout.flush()
            self.cover_graphics_draw_key = draw_key
        except OSError:
            pass

    def refresh_cover_art(self, screen_height: int, screen_width: int) -> None:
        if self.cover_path is None:
            return

        cover_width, cover_height = self.cover_size(screen_height, screen_width)
        self.refresh_cover_art_size(cover_width, cover_height)

    def refresh_cover_art_size(self, cover_width: int, cover_height: int) -> None:
        if self.cover_path is None:
            return

        graphics_enabled = supports_graphics_cover() and __import__("shutil").which("chafa") is not None
        render_key = (str(self.cover_path), cover_width, cover_height, graphics_enabled)
        if render_key == self.cover_render_key:
            return

        self.cover_render_key = render_key
        self.cover_graphics_draw_key = None
        if graphics_enabled:
            self.cover_graphics = render_graphics_cover(
                self.cover_path,
                max_width=cover_width,
                max_height=cover_height,
            )
            self.cover_lines = []
            if self.cover_graphics is None:
                self.cover_lines = render_cover(
                    self.cover_path,
                    max_width=cover_width,
                    max_height=cover_height,
                )
        else:
            self.cover_graphics = None
            self.cover_lines = render_cover(
                self.cover_path,
                max_width=cover_width,
                max_height=cover_height,
            )

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


def clear_terminal_images() -> None:
    import sys
    try:
        sys.stdout.write("\x1b_Ga=d,d=A\x1b\\")
        sys.stdout.flush()
    except OSError:
        pass


def wrap(text: str, width: int) -> list[str]:
    import textwrap
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
