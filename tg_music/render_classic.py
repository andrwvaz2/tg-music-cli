from __future__ import annotations

import curses
import time

from .models import format_duration


class RenderClassicMixin:
    def draw_classic(self) -> None:
        self.screen.erase()
        height, width = self.screen.getmaxyx()

        hdr_attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLUE) | curses.A_BOLD
        hdr_dim = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLUE) | curses.A_DIM
        sep_attr = self.color_attr(self.color_primary, -1) | curses.A_DIM
        body_attr = self.color_attr(self.color_primary, -1)
        sel_attr = self.color_attr(curses.COLOR_BLACK, curses.COLOR_CYAN) | curses.A_BOLD
        if self.is_light:
            sel_attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLUE) | curses.A_BOLD

        # ── Header ──
        header_text = "\u266b TG-MUSIC \u25b8 Classic View"
        self.screen.addnstr(0, 0, header_text[:width - 1], width - 1, hdr_attr)
        ver = "v0.1.0"
        self.screen.addnstr(0, max(0, width - len(ver) - 1), ver, len(ver), hdr_dim)

        # ── Layout zones ──
        lib_w = max(width // 4, 20)
        playlist_x = lib_w + 1
        playlist_w = width - playlist_x - 1

        control_h = 4
        lyrics_h = 6
        body_h = max(height - 2 - control_h - lyrics_h - 1, 1)

        # ── Library panel header ──
        self.screen.addnstr(1, 0, " LIBRARY "[:lib_w], lib_w, body_attr | curses.A_BOLD)
        self.screen.addnstr(1, lib_w, "\u2502", 1, sep_attr)
        pl_label = f" PLAYLIST ({len(self.tracks)} tracks) "
        self.screen.addnstr(1, playlist_x, pl_label, playlist_w, body_attr | curses.A_BOLD)

        # ── Vertical separator ──
        for y in range(2, 2 + body_h):
            self.screen.addnstr(y, lib_w, "\u2502", 1, sep_attr)

        # ── Library (left panel) ──
        from .local import LOCAL_CHANNEL
        lib_items: list[tuple[str, str, bool]] = []
        if self.local_folder:
            from pathlib import Path
            lib_items.append(("local", f"\U0001f4c1 {Path(self.local_folder).name}", True))
        for ch in self.channels:
            lib_items.append(("channel", f"\U0001f4ac {ch.title or ch.channel}", False))

        for row_idx, (kind, label, is_local) in enumerate(lib_items[:body_h]):
            y = 2 + row_idx
            is_sel = (row_idx == self.selected and self.view == "channels")
            if is_sel:
                attr = sel_attr
            elif kind == "local" and self.channel_filter == LOCAL_CHANNEL:
                attr = self.color_attr(self.color_success, -1) | curses.A_BOLD
            elif kind == "channel" and self.channel_filter == label[2:]:
                attr = self.color_attr(self.color_success, -1) | curses.A_BOLD
            else:
                attr = curses.A_NORMAL
            self.screen.addnstr(y, 0, label[:max(lib_w - 1, 0)], max(lib_w - 1, 0), attr)

        # ── Playlist (right panel, 4 columns) ──
        col_dur = 8
        col_artist = max(playlist_w // 4, 12)
        col_title = max(playlist_w // 3, 15)
        col_album = max(playlist_w - col_dur - col_artist - col_title - 4, 8)

        # Column headers
        hdr_y = 2
        hdr_line = f"{'Dur':>{col_dur}}  {'Artist':<{col_artist}}  {'Title':<{col_title}}  {'Album':<{col_album}}"
        hdr_attr = body_attr | curses.A_UNDERLINE
        self.screen.addnstr(hdr_y, playlist_x, hdr_line[:max(playlist_w - 1, 0)], max(playlist_w - 1, 0), hdr_attr)

        # Track rows
        track_offset = self.offset if self.view == "tracks" else 0
        for row_idx, track in enumerate(self.tracks[track_offset:track_offset + body_h - 2]):
            y = 3 + row_idx
            real_idx = track_offset + row_idx
            is_sel = (real_idx == self.selected and self.view == "tracks")
            is_playing = self.current_track and track.id == self.current_track.id

            if is_sel:
                attr = sel_attr
            elif is_playing:
                attr = self.color_attr(self.color_success, -1) | curses.A_BOLD
            else:
                attr = curses.A_NORMAL

            dur = format_duration(track.duration)
            artist = track.performer or ""
            title = track.title or track.filename or f"msg {track.message_id}"
            album = ""  # Track model doesn't have album field

            playing_mark = "\u25b6 " if is_playing else "  "
            line = f"{playing_mark}{dur:>{col_dur}}  {artist:<{col_artist}}  {title:<{col_title}}  {album:<{col_album}}"
            self.screen.addnstr(y, playlist_x, line[:max(playlist_w - 1, 0)], max(playlist_w - 1, 0), attr)

        # ── Horizontal separator ──
        sep_y = 2 + body_h
        self.screen.addnstr(sep_y, 0, "\u2500" * (width - 1), width - 1, sep_attr)

        # ── Control panel ──
        ctrl_y = sep_y + 1
        status_text = f"Status: {'Running' if self.player.is_playing() else 'Stopped'}"
        vol_text = f"Volume: {self.volume}"
        speed_text = "Speed: 1.0"
        gapless_text = "Gapless: True"
        ctrl_line = f"  {status_text}    {vol_text}    {speed_text}    {gapless_text}"
        self.screen.addnstr(ctrl_y, 0, ctrl_line[:width - 1], width - 1, body_attr)

        # Progress bar
        if self.current_track and self.play_start_time:
            elapsed = int(time.time() - self.play_start_time)
            duration = self.current_track.duration or 0
            elapsed = min(elapsed, duration) if duration > 0 else elapsed
            elapsed_str = format_duration(elapsed)
            dur_str = format_duration(duration)
            bar_w = max(width - len(elapsed_str) - len(dur_str) - 6, 10)
            bar = self._make_progress_bar(elapsed, duration, bar_w)
            progress_line = f"  {elapsed_str} {bar} {dur_str}"
            prog_attr = self.color_attr(self.color_success, -1)
            self.screen.addnstr(ctrl_y + 1, 0, progress_line[:width - 1], width - 1, prog_attr)
        else:
            self.screen.addnstr(ctrl_y + 1, 0, "  --:-- " + "\u2591" * 20 + " --:--", width - 1, curses.A_DIM)

        # ── Lyrics panel ──
        lyrics_y = ctrl_y + 3
        self.screen.addnstr(lyrics_y, 0, "\u2500" * (width - 1), width - 1, sep_attr)
        self.screen.addnstr(lyrics_y + 1, 0, " LYRICS ", width - 1, body_attr | curses.A_BOLD)

        if self.lyrics_visible and self.lyrics_text:
            for i, line in enumerate(self.lyrics_text.splitlines()[:lyrics_h - 2]):
                lyric_attr = self.color_attr(self.color_success, -1)
                self.screen.addnstr(lyrics_y + 2 + i, 1, line[:max(width - 2, 0)], max(width - 2, 0), lyric_attr)
        else:
            self.screen.addnstr(lyrics_y + 2, 1, "No lyrics available", width - 2, curses.A_DIM)

        # ── Help bar (footer) ──
        help_y = height - 1
        help_text = (
            " [?] Help  [q] Quit  [Enter] Play  [e] Queue  "
            "[f] Fav  [L] Lyrics  [/] Search  [P] Split  [M] Mini "
        )
        self.screen.addnstr(help_y, 0, " " * (width - 1), width - 1, hdr_attr)
        self.screen.addnstr(help_y, 0, help_text[:width - 1], width - 1, hdr_attr)

        self.screen.refresh()
        self.dirty = False
