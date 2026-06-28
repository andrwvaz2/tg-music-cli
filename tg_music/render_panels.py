from __future__ import annotations

import curses

from .db import connect
from .models import format_duration
from .render_base import clear_terminal_images, wrap


class RenderPanelsMixin:
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
            parts.append(f"\u25b8 Search: {self.query}")
        if self.favorites_only:
            parts.append("\u25b8 \u2665 Favoritos")
        if self.tag_filter:
            parts.append(f"\u25b8 Tag: {self.tag_filter}")
        if self.playlist_filter:
            parts.append(f"\u25b8 Playlist: {self.playlist_filter}")

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
            left_title = "PLAYLISTS"
        elif self.view == "channels":
            left_title = "CHANNELS"
        else:
            left_title = "TRACKS"
            if self.channel_filter:
                channel_title = self.channel_filter
                for ch in self.channels:
                    if ch.channel == self.channel_filter and ch.title:
                        channel_title = ch.title
                        break
                left_title = f"TRACKS: {channel_title}"
            if self.playlist_filter:
                left_title = f"PLAYLIST: {self.playlist_filter}"
        self.add(5, 0, f" {left_title} "[: max(left_width - 1, 0)], self.color_attr(self.color_primary, -1) | curses.A_BOLD)
        if right_width > 12:
            self.add(5, right_x, " DETAILS "[: max(right_width - 1, 0)], self.color_attr(self.color_primary, -1) | curses.A_BOLD)
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
            is_sel = (self.offset + row - body_top) == self.selected
            if is_sel:
                if self.is_light:
                    attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLUE) | curses.A_BOLD
                else:
                    attr = self.color_attr(curses.COLOR_BLACK, curses.COLOR_CYAN) | curses.A_BOLD
            else:
                attr = curses.A_NORMAL

            kind = item.get("kind", "")
            if kind == "local":
                is_expanded = LOCAL_CHANNEL in self.expanded_channels
                active = "\u25bc" if is_expanded else "\u25b6"
                title = item.get("title", "Local")
                count = item.get("count", 0)
                line = f"{active} / {title} ({count})"
                ch_filter = item.get("channel")
                if self.channel_filter == ch_filter:
                    attr = self.color_attr(self.color_success, -1) | curses.A_BOLD
            elif kind == "track":
                track = item.get("track")
                if not track:
                    continue
                is_playing = self.current_track and track.id == self.current_track.id
                if is_playing:
                    attr = self.color_attr(self.color_success, -1) | curses.A_BOLD
                playing = "\u25b6" if is_playing else " "
                dur = format_duration(track.duration)
                line = f"    {playing} {dur:>5}  {track.display_title}"
                if not track.local_path:
                    attr |= curses.A_DIM
            else:
                ch = item.get("channel")
                if not ch:
                    continue
                is_expanded = ch.channel in self.expanded_channels
                active = "\u25bc" if is_expanded else "\u25b6"
                title = ch.title or ch.channel
                count = item.get("count", 0)
                line = f"{active} {title} ({count})"
                if self.channel_filter == ch.channel:
                    attr = self.color_attr(self.color_success, -1) | curses.A_BOLD

            self.add(row, 0, line[: max(left_width - 1, 0)], attr)

    def draw_playlists(self, body_top: int, visible_height: int, left_width: int) -> None:
        from .db import list_playlists
        with connect() as conn:
            playlists = list_playlists(conn)
        for row_idx, pl in enumerate(playlists[self.offset : self.offset + visible_height], start=body_top):
            is_sel = (self.offset + (row_idx - body_top)) == self.selected
            if is_sel:
                if self.is_light:
                    attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLUE) | curses.A_BOLD
                else:
                    attr = self.color_attr(curses.COLOR_BLACK, curses.COLOR_CYAN) | curses.A_BOLD
            else:
                attr = curses.A_NORMAL
            count = pl.get("count", 0)
            line = f"  \U0001f3b5 {pl['name']} ({count})"
            self.add(row_idx, 0, line[: max(left_width - 1, 0)], attr)

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
            if x - 1 >= 0:
                self.screen.addch(row, x - 1, "\u2502", border_attr)
        row = top
        if self.view == "channels":
            self.add(row, x + 1, "Library Browser", self.color_attr(self.color_primary, -1) | curses.A_BOLD)
            row += 1
            lines = [
                "Navigate channels and tracks.",
                "",
                "Enter: open folder",
                "Space/Right: expand",
                "Backspace/Left: collapse",
                "a: add a channel",
                "u: scan current folder",
                "/: search current view",
            ]
            for text in lines:
                for line in wrap(text, width - 2):
                    if row >= top + height:
                        return
                    self.add(row, x + 1, line)
                    row += 1
            return

        cover_top = None
        if self.current_track is not None:
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

        self.add(row, x + 1, "NOW PLAYING", self.color_attr(self.color_primary, -1) | curses.A_BOLD)
        row += 1
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
            ("Cache", "Ready" if self.current_track.local_path else "Remote"),
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
