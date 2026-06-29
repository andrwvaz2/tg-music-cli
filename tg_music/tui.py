from __future__ import annotations

import asyncio
import curses
import os
import subprocess
import threading
import time
import traceback
from curses import wrapper
from pathlib import Path

from .cache import cache_tracks_async
from .config import DATA_DIR, load_settings, save_settings
from .themes import THEMES, ColorTheme, get_theme, list_themes
from .db import (
    add_to_playlist,
    connect,
    create_playlist,
    get_all_favorite_ids,
    get_playlist_by_name,
    get_playlist_tracks,
    latest_for_channel,
    latest_message_id_for_channel,
    list_channels,
    list_playlists,
    list_tracks,
    list_uncached_tracks,
    tag_track,
    toggle_favorite,
)
from .lyrics import fetch_lyrics
from .models import Channel, Track
from .player import BackgroundPlayer
from .shared import fuzzy_match, notify_user
from .telegram_client import normalize_channel, scan_channel, scan_channel_since
from .tui_render import RenderMixin
from .render_base import clear_terminal_images
from .tui_player import PlayerMixin


class Tui(RenderMixin, PlayerMixin):
    def __init__(self, screen: curses.window) -> None:
        self.screen = screen
        self.selected = 0
        self.offset = 0
        self.query = ""
        self.channel_filter: str | None = None
        self.channels: list[Channel] = []
        self.view = "channels"
        self.status = "Enter opens, Backspace goes up, e queues, / searches, r refreshes, q quits"
        self.tracks: list[Track] = []
        self.browser_rows: list[dict[str, object]] = []
        self.play_queue: list[int] = []
        self.expanded_channels: set[str] = set()
        self.help_visible = False
        self.download_missing_thread: threading.Thread | None = None
        self.new_music_thread: threading.Thread | None = None
        self.watch_enabled = True
        self.watch_interval = 300
        self.watch_stop_event = threading.Event()
        self.watch_thread: threading.Thread | None = None
        self.watch_last_seen: dict[str, int | None] = {}

        settings = load_settings()
        self.player = BackgroundPlayer(volume=settings.volume, crossfade=settings.crossfade)
        self.volume = settings.volume
        self.repeat_mode = False
        self.shuffle_mode = False

        self.now_playing = ""
        self.current_track: Track | None = None
        self.current_audio_path: Path | None = None
        self.cover_path: Path | None = None
        self.cover_lines: list[str] = []
        self.cover_graphics: bytes | None = None
        self.cover_graphics_pos: tuple[int, int] | None = None
        self.cover_graphics_draw_key: tuple[str, tuple[int, int], tuple[int, int]] | None = None
        self.cover_render_key: tuple[str, int, int, bool] | None = None
        self.color_pairs: dict[tuple[int, int], int] = {}
        self.cache_line = "Cache: Listo"
        self.dirty = True
        self.precache_ids: set[int] = set()
        self.downloading_track_id: int | None = None
        self.precache_thread: threading.Thread | None = None
        self.is_light = self.detect_light_theme()
        self.play_start_time: float | None = None
        self.last_elapsed_seconds: int = 0
        self.manual_stop = False
        self.input_timeout_ms = 200
        self.last_screen_size: tuple[int, int] | None = None
        self.mini_mode = False
        self.lyrics_visible = False
        self.lyrics_text: str = ""
        self.lyrics_thread: threading.Thread | None = None
        self.tag_filter: str | None = None
        self.favorites_only = False
        self.split_mode = False
        self.split_panel = 0
        self.favorite_ids: set[int] = set()
        self.playlists: list[dict] = []
        self.playlist_filter: str | None = None
        self.local_folder: str | None = None

    def detect_light_theme(self) -> bool:
        settings = load_settings()
        theme = get_theme(settings.theme)
        if theme.is_light:
            return True
        if settings.theme in ("dark",) + tuple(t for t in THEMES if not THEMES[t].is_light):
            return False
        fgbg = os.environ.get("COLORFGBG", "")
        if fgbg:
            try:
                parts = fgbg.split(";")
                if len(parts) >= 2:
                    bg = int(parts[-1])
                    if bg in (7, 15) or bg > 8:
                        return True
            except ValueError:
                pass
        try:
            res = subprocess.check_output(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1,
            )
            if "prefer-light" in res.lower():
                return True
        except Exception:
            pass  # Terminal query failed; default to dark theme
        return False

    def current_color_theme(self) -> ColorTheme:
        settings = load_settings()
        return get_theme(settings.theme)

    def run(self) -> None:
        curses.curs_set(0)
        try:
            curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
        except Exception:
            pass  # Mouse not supported; continue without it
        self.init_colors()
        self.screen.timeout(self.input_timeout_ms)
        self.reload()
        self.start_watch_thread()
        self.last_screen_size = self.screen.getmaxyx()
        try:
            while True:
                current_size = self.screen.getmaxyx()
                if current_size != self.last_screen_size:
                    self.last_screen_size = current_size
                    self.dirty = True
                    clear_terminal_images()

                if self.play_start_time is not None:
                    if self.player.is_playing():
                        elapsed = int(time.time() - self.play_start_time)
                        if elapsed != self.last_elapsed_seconds:
                            self.last_elapsed_seconds = elapsed
                            if not self.dirty and self.draw_playback_tick():
                                continue
                            self.dirty = True
                    else:
                        returncode = self.player.returncode()
                        self.play_start_time = None
                        self.last_elapsed_seconds = 0
                        if not self.manual_stop and returncode == 0:
                            self.play_next(auto=True)
                        else:
                            self.manual_stop = False
                            self.dirty = True

                if self.dirty:
                    try:
                        self.draw()
                    except Exception as exc:
                        self.log_exception("draw", exc)
                        self.cover_graphics = None
                        self.cover_graphics_pos = None
                        self.cover_graphics_draw_key = None
                        self.status = f"Render error: {exc}"
                        self.screen.erase()
                        self.screen.addnstr(0, 0, self.status, max(self.screen.getmaxyx()[1] - 1, 0))
                        self.screen.refresh()
                        self.dirty = False
                key = self.screen.getch()
                if key == -1:
                    continue
                try:
                    if self.handle_key(key):
                        return
                except Exception as exc:
                    self.log_exception("key handler", exc)
                    self.status = f"Error: {exc}"
                    self.cover_graphics = None
                    self.cover_graphics_pos = None
                    self.cover_graphics_draw_key = None
                    self.dirty = True
        finally:
            self.stop_watch_thread()
            self.player.stop()
            clear_terminal_images()

    def handle_key(self, key: int) -> bool:
        if key == 409 or key == curses.KEY_MOUSE:
            self.handle_mouse()
            return False
        if self.help_visible:
            if key in (ord("?"), 27, curses.KEY_F1, ord("h"), ord("q")):
                self.help_visible = False
                self.dirty = True
            return False
        if key in (ord("q"), 27):
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.move(1)
        elif key in (curses.KEY_UP, ord("k")):
            self.move(-1)
        elif key in (curses.KEY_RIGHT, ord("l"), ord(" ")):
            self.expand_selected_channel()
        elif key in (curses.KEY_LEFT, curses.KEY_BACKSPACE, 127, ord("h")):
            self.go_back()
        elif key in (curses.KEY_NPAGE,):
            self.move(10)
        elif key in (curses.KEY_PPAGE,):
            self.move(-10)
        elif key in (ord("r"),):
            self.reload()
        elif key in (ord("a"),):
            if self.view == "playlists":
                self.create_playlist_prompt()
            else:
                self.add_channel_prompt()
        elif key in (ord("c"),):
            self.show_channels()
        elif key in (ord("u"),):
            self.scan_more_prompt()
        elif key in (ord("s"),):
            self.stop_playback()
        elif key in (ord("n"),):
            self.play_next(auto=False)
        elif key in (ord("x"),):
            self.ignore_selected()
        elif key in (ord("e"),):
            self.enqueue_selected()
        elif key in (ord("m"),):
            self.download_missing_prompt()
        elif key in (ord("w"),):
            self.check_new_music_prompt()
        elif key in (ord("W"),):
            self.toggle_watch()
        elif key in (9,):
            if self.split_mode:
                self.split_panel = (self.split_panel + 1) % 3
                if self.split_panel == 0:
                    self.view = "channels"
                else:
                    self.view = "tracks"
                self.status = ["Channels", "Tracks", "Details"][self.split_panel] + " panel"
                self.dirty = True
        elif key in (ord("["),):
            self.move_queue(-1)
        elif key in (ord("]"),):
            self.move_queue(1)
        elif key in (ord("/"),):
            self.search()
        elif key in (ord(":"),):
            self.command_mode_prompt()
        elif key in (ord("?"), ord("H"), curses.KEY_F1):
            self.toggle_help()
        elif key in (ord("f"),):
            self.toggle_favorite_selected()
        elif key in (ord("R"),):
            self.toggle_repeat()
        elif key in (ord("S"),):
            self.toggle_shuffle()
        elif key in (ord("+"), ord("=")):
            self.adjust_volume(5)
        elif key in (ord("-"),):
            self.adjust_volume(-5)
        elif key in (ord("L"),):
            self.toggle_lyrics()
        elif key in (ord("M"),):
            self.toggle_mini_mode()
        elif key in (ord("T"),):
            self.toggle_theme()
        elif key in (curses.KEY_F2,):
            self.theme_picker()
        elif key in (ord("P"),):
            self.toggle_split_mode()
        elif key in (ord("t"),):
            self.tag_prompt()
        elif key in (ord("1"),):
            self.filter_favorites()
        elif key in (ord("y"),):
            self.show_playlists()
        elif key in (ord("Y"),):
            self.add_to_playlist_prompt()
        elif key in (ord("g"),):
            self.focus_local_entry()
        elif key in (10, 13):
            if self.split_mode:
                if self.split_panel == 0:
                    self.open_selected_channel()
                elif self.split_panel == 1:
                    self.play_selected()
            elif self.view == "channels":
                self.open_selected_channel()
            elif self.view == "playlists":
                self.open_selected_playlist()
            else:
                self.play_selected()
        self.dirty = True
        return False

    def log_exception(self, context: str, exc: Exception) -> None:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with (DATA_DIR / "tui-crash.log").open("a", encoding="utf-8") as fh:
                fh.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {context}: {exc}\n")
                fh.write(traceback.format_exc())
        except OSError:
            pass

    def handle_mouse(self) -> None:
        try:
            _, mx, my, _, bstate = curses.getmouse()
        except Exception:
            return  # No mouse event available
        if bstate & curses.BUTTON1_CLICKED:
            height, width = self.screen.getmaxyx()
            left_width = max(42, int(width * 0.58))
            if width < 90:
                left_width = width
            body_top = 6
            visible_height = max(height - body_top - 1, 1)
            if my >= body_top and my < body_top + visible_height and mx < left_width:
                new_selected = self.offset + (my - body_top)
                items_len = len(self.browser_rows) if self.view == "channels" else len(self.tracks)
                if 0 <= new_selected < items_len:
                    self.selected = new_selected
                    self.dirty = True

    def toggle_mini_mode(self) -> None:
        self.mini_mode = not self.mini_mode
        self.status = "Mini view on" if self.mini_mode else "Mini view off"
        self.dirty = True

    def toggle_theme(self) -> None:
        settings = load_settings()
        themes = list_themes()
        idx = themes.index(settings.theme) if settings.theme in themes else 0
        settings.theme = themes[(idx + 1) % len(themes)]
        save_settings(settings)
        self.is_light = self.detect_light_theme()
        self.init_colors()
        self.status = f"Theme: {get_theme(settings.theme).name}"
        self.dirty = True

    def theme_picker(self) -> None:
        settings = load_settings()
        themes = list_themes()
        current = settings.theme
        picker_selected = themes.index(current) if current in themes else 0
        while True:
            self.screen.erase()
            height, width = self.screen.getmaxyx()
            overlay_w = min(50, width - 4)
            overlay_h = min(len(themes) + 6, height - 4)
            start_x = max(2, (width - overlay_w) // 2)
            start_y = max(2, (height - overlay_h) // 2)

            panel_attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLACK)
            frame_attr = self.color_attr(self.color_primary, curses.COLOR_BLACK) | curses.A_BOLD
            title_attr = self.color_attr(curses.COLOR_BLACK, curses.COLOR_CYAN) | curses.A_BOLD

            for row in range(start_y, start_y + overlay_h):
                self.add(row, start_x, " " * overlay_w, panel_attr)
            self.add(start_y, start_x, "\u250c" + "\u2500" * (overlay_w - 2) + "\u2510", frame_attr)
            for row in range(start_y + 1, start_y + overlay_h - 1):
                self.add(row, start_x, "\u2502", frame_attr)
                self.add(row, start_x + overlay_w - 1, "\u2502", frame_attr)
            self.add(start_y + overlay_h - 1, start_x, "\u2514" + "\u2500" * (overlay_w - 2) + "\u2518", frame_attr)

            title = " SELECT THEME "
            self.add(start_y, start_x + max(2, (overlay_w - len(title)) // 2), title, title_attr)

            for i, theme_name in enumerate(themes):
                y = start_y + 1 + i
                ct = THEMES[theme_name]
                marker = "\u25b8" if i == picker_selected else " "
                active = "\u25cf" if theme_name == current else "\u25cb"
                line = f" {marker} {active} {ct.name}"
                if i == picker_selected:
                    attr = self.color_attr(curses.COLOR_BLACK, curses.COLOR_CYAN) | curses.A_BOLD
                elif theme_name == current:
                    attr = self.color_attr(self.color_success, -1) | curses.A_BOLD
                else:
                    attr = curses.A_NORMAL
                self.add(y, start_x + 1, line[: overlay_w - 2], attr)

            close_text = "Enter: apply | q/Esc: cancel"
            self.add(
                start_y + overlay_h - 1, start_x + max(2, (overlay_w - len(close_text)) // 2), close_text, frame_attr
            )
            self.screen.refresh()

            key = self.screen.getch()
            if key in (ord("q"), 27):
                return
            elif key in (curses.KEY_UP, ord("k")):
                picker_selected = (picker_selected - 1) % len(themes)
            elif key in (curses.KEY_DOWN, ord("j")):
                picker_selected = (picker_selected + 1) % len(themes)
            elif key in (10, 13):
                chosen = themes[picker_selected]
                settings = load_settings()
                settings.theme = chosen
                save_settings(settings)
                self.is_light = self.detect_light_theme()
                self.init_colors()
                self.status = f"Theme: {get_theme(chosen).name}"
                self.dirty = True
                return
            self.dirty = True

    def toggle_split_mode(self) -> None:
        leaving_split = self.split_mode
        previous_panel = self.split_panel
        self.split_mode = not self.split_mode
        clear_terminal_images()
        self.cover_graphics_pos = None
        self.cover_graphics_draw_key = None
        if self.split_mode:
            self.view = "channels"
            self.split_panel = 0
            self.selected = 0
        elif leaving_split and (previous_panel > 0 or self.channel_filter or self.current_track is not None):
            self.view = "tracks"
            if self.current_track is not None:
                track_index = next(
                    (index for index, track in enumerate(self.tracks) if track.id == self.current_track.id), None
                )
                if track_index is not None:
                    self.selected = track_index
            self.selected = min(self.selected, max(len(self.tracks) - 1, 0))
            self.offset = min(self.offset, self.selected)
            self.split_panel = 0
        self.status = "Split view on" if self.split_mode else "Split view off"
        self.dirty = True

    def toggle_lyrics(self) -> None:
        if self.current_track is None:
            self.status = "Play a track first"
            self.dirty = True
            return
        self.lyrics_visible = not self.lyrics_visible
        if self.lyrics_visible and not self.lyrics_text:
            self.fetch_lyrics_async()
        self.status = "Lyrics on" if self.lyrics_visible else "Lyrics off"
        self.dirty = True

    def fetch_lyrics_async(self) -> None:
        if self.lyrics_thread and self.lyrics_thread.is_alive():
            return
        self.lyrics_thread = threading.Thread(target=self._fetch_lyrics_worker, daemon=True)
        self.lyrics_thread.start()

    def _fetch_lyrics_worker(self) -> None:
        try:
            track = self.current_track
            if track is None:
                return
            result = fetch_lyrics(
                track.performer or track.channel_title,
                track.title or track.filename,
                track.duration,
            )
            if result and (result.synced or result.plain):
                self.lyrics_text = result.synced or result.plain or ""
            else:
                self.lyrics_text = "(No lyrics found)"
        except Exception:
            self.lyrics_text = "(Lyrics lookup error)"  # Network/parse failure
        finally:
            self.dirty = True

    def adjust_volume(self, delta: int) -> None:
        self.volume = max(0, min(150, self.volume + delta))
        self.player.set_volume(self.volume)
        settings = load_settings()
        settings.volume = self.volume
        save_settings(settings)
        self.status = f"Volume: {self.volume}"
        self.dirty = True

    def toggle_repeat(self) -> None:
        self.repeat_mode = not self.repeat_mode
        self.status = f"Repeat: {'on' if self.repeat_mode else 'off'}"
        self.dirty = True

    def toggle_shuffle(self) -> None:
        self.shuffle_mode = not self.shuffle_mode
        self.status = f"Shuffle: {'on' if self.shuffle_mode else 'off'}"
        self.dirty = True

    def toggle_favorite_selected(self) -> None:
        if self.view == "channels" or not self.tracks:
            return
        track = self.tracks[self.selected]
        with connect() as conn:
            is_now_fav = toggle_favorite(conn, track.id)
        if is_now_fav:
            self.favorite_ids.add(track.id)
        else:
            self.favorite_ids.discard(track.id)
        state = "favorito" if is_now_fav else "removido"
        self.status = f"{track.display_title}: {state}"
        self.dirty = True

    def filter_favorites(self) -> None:
        self.favorites_only = not self.favorites_only
        self.tag_filter = None
        self.view = "tracks"
        self.query = ""
        self.selected = 0
        self.offset = 0
        self.reload()
        self.status = "Favorites filter on" if self.favorites_only else "Favorites filter off"
        self.dirty = True

    def tag_prompt(self) -> None:
        if self.view == "channels" or not self.tracks:
            self.status = "Select a track first"
            self.dirty = True
            return
        track = self.tracks[self.selected]
        tag_name = self.input_prompt(f"Tag para '{track.display_title[:30]}': ")
        if not tag_name:
            self.status = "Tag cancelado"
            self.dirty = True
            return
        with connect() as conn:
            tag_track(conn, track.id, tag_name)
        self.status = f"Tag '{tag_name}' agregado"
        self.dirty = True

    def show_playlists(self) -> None:
        with connect() as conn:
            self.playlists = list_playlists(conn)
        if not self.playlists:
            self.status = "No playlists. Create one with: tg-music playlist create <name>"
            self.dirty = True
            return
        self.view = "playlists"
        self.selected = 0
        self.offset = 0
        self.status = "Playlists (Enter opens, a creates new, q returns)"
        self.dirty = True

    def add_to_playlist_prompt(self) -> None:
        if self.view == "channels" or not self.tracks:
            self.status = "Select a track first"
            self.dirty = True
            return
        track = self.tracks[self.selected]
        with connect() as conn:
            playlists = list_playlists(conn)
        if not playlists:
            self.status = "No playlists. Press 'a' in playlists view to create one"
            self.dirty = True
            return
        names = ", ".join(f"{i + 1}:{p['name']}" for i, p in enumerate(playlists))
        choice = self.input_prompt(f"Track: {track.display_title[:25]}. Playlist ({names}): ")
        if not choice:
            self.status = "Cancelled"
            self.dirty = True
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(playlists):
                pl = playlists[idx]
                with connect() as conn:
                    add_to_playlist(conn, pl["id"], track.id)
                self.status = f"Added to '{pl['name']}'"
            else:
                self.status = "Invalid index"
        except ValueError:
            with connect() as conn:
                pl = get_playlist_by_name(conn, choice)
                if pl:
                    with connect() as conn2:
                        add_to_playlist(conn2, pl["id"], track.id)
                    self.status = f"Added to '{pl['name']}'"
                else:
                    create_choice = self.input_prompt(f"Create playlist '{choice}'? (y/n): ")
                    if create_choice.lower() == "s":
                        with connect() as conn2:
                            pl_id = create_playlist(conn2, choice)
                            add_to_playlist(conn2, pl_id, track.id)
                        self.status = f"Playlist '{choice}' creada y track agregado"
                    else:
                        self.status = "Cancelled"
        self.dirty = True

    def open_selected_playlist(self) -> None:
        if not self.playlists:
            return
        pl = self.playlists[self.selected]
        with connect() as conn:
            self.tracks = get_playlist_tracks(conn, pl["id"])
        self.playlist_filter = pl["name"]
        self.view = "tracks"
        self.channel_filter = None
        self.query = ""
        self.selected = 0
        self.offset = 0
        self.status = f"Playlist: {pl['name']} ({len(self.tracks)} tracks)"
        self.dirty = True

    def create_playlist_prompt(self) -> None:
        name = self.input_prompt("Nombre de la playlist nueva: ")
        if not name:
            self.status = "Cancelled"
            self.dirty = True
            return
        with connect() as conn:
            pl_id = create_playlist(conn, name)
        self.status = f"Playlist '{name}' creada (id: {pl_id})"
        with connect() as conn:
            self.playlists = list_playlists(conn)
        self.dirty = True

    def browse_folder(self) -> str | None:
        from pathlib import Path

        home = Path.home().expanduser()
        current = home
        selected = 0
        offset = 0

        while True:
            height, width = self.screen.getmaxyx()
            entries = self._list_dir(current)
            if not entries:
                entries = []

            if selected >= len(entries):
                selected = max(0, len(entries) - 1)
            if selected < offset:
                offset = selected
            if selected >= offset + height - 6:
                offset = selected - height + 7

            self.screen.erase()
            header_attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLUE) | curses.A_BOLD

            self.add(0, 0, " " * width, header_attr)
            title = f" BROWSE: {current}"
            self.add(0, 0, title[: width - 1], header_attr)

            info = "Enter: open/select  Backspace: up  q: cancel"
            self.add(1, 0, info[: width - 1], curses.A_DIM)
            self.add(2, 0, "─" * max(width - 1, 0), curses.A_DIM)

            body_top = 3
            body_h = max(height - body_top - 1, 1)

            for i, entry in enumerate(entries[offset : offset + body_h]):
                y = body_top + i
                is_sel = (offset + i) == selected
                name = entry.name

                if entry.is_dir():
                    icon = "/ "
                    if name == "..":
                        icon = "^ "
                else:
                    ext = entry.suffix.lower()
                    if ext in {".mp3", ".flac", ".ogg", ".wav", ".m4a", ".aac", ".opus"}:
                        icon = "* "
                    else:
                        icon = "  "

                line = f" {icon}{name}"

                if is_sel:
                    if self.is_light:
                        attr = self.color_attr(curses.COLOR_WHITE, curses.COLOR_BLUE) | curses.A_BOLD
                    else:
                        attr = self.color_attr(curses.COLOR_BLACK, curses.COLOR_CYAN) | curses.A_BOLD
                elif entry.is_dir():
                    attr = self.color_attr(curses.COLOR_CYAN, -1)
                else:
                    attr = curses.A_NORMAL

                self.add(y, 0, line[: width - 1], attr)

            if not entries:
                self.add(body_top, 0, " (vacio)", curses.A_DIM)

            self.screen.refresh()

            key = self.screen.getch()
            if key == -1:
                continue
            if key in (ord("q"), 27):
                return None
            if key in (curses.KEY_UP, ord("k")):
                selected = max(0, selected - 1)
            elif key in (curses.KEY_DOWN, ord("j")):
                selected = min(len(entries) - 1, selected + 1)
            elif key in (curses.KEY_NPAGE,):
                selected = min(len(entries) - 1, selected + body_h)
            elif key in (curses.KEY_PPAGE,):
                selected = max(0, selected - body_h)
            elif key in (ord("g"), curses.KEY_HOME):
                selected = 0
            elif key in (ord("G"), curses.KEY_END):
                selected = max(0, len(entries) - 1)
            elif key in (curses.KEY_BACKSPACE, 127, ord("h")):
                current = current.parent
                selected = 0
                offset = 0
            elif key in (10, 13):
                if not entries:
                    continue
                chosen_entry = entries[selected]
                if chosen_entry.is_dir():
                    if chosen_entry.name == "..":
                        current = current.parent
                    else:
                        current = chosen_entry
                    selected = 0
                    offset = 0
                else:
                    return str(current)
            elif key in (curses.KEY_RIGHT, ord("l")):
                if entries and entries[selected].is_dir():
                    chosen_entry = entries[selected]
                    if chosen_entry.name == "..":
                        current = current.parent
                    else:
                        current = chosen_entry
                    selected = 0
                    offset = 0
            elif key in (curses.KEY_LEFT,):
                current = current.parent
                selected = 0
                offset = 0

    def focus_local_entry(self) -> None:

        if self.view != "channels":
            self.show_channels()
        for i, row in enumerate(self.browser_rows):
            if row.get("kind") == "local":
                self.selected = i
                self.dirty = True
                self.status = "Press Enter to open Local folder"
                return
        self.status = "No Local entry"
        self.dirty = True

    def _list_dir(self, path: Path) -> list[Path]:
        entries: list[Path] = []
        if path.parent != path:
            entries.append(path.parent / "..")
        try:
            for entry in sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    entries.append(entry)
        except PermissionError:
            pass
        try:
            for entry in sorted(path.iterdir(), key=lambda e: e.name.lower()):
                if entry.is_file():
                    ext = entry.suffix.lower()
                    if ext in {".mp3", ".flac", ".ogg", ".wav", ".m4a", ".aac", ".opus", ".wma", ".aiff"}:
                        entries.append(entry)
        except PermissionError:
            pass
        return entries

    def reload(self) -> None:
        if self.view == "playlists":
            with connect() as conn:
                self.playlists = list_playlists(conn)
                self.favorite_ids = get_all_favorite_ids(conn)
            self.selected = min(self.selected, max(len(self.playlists) - 1, 0))
            self.dirty = True
            return
        from .local import LOCAL_CHANNEL

        track_channel = None if self.view == "channels" else self.channel_filter
        if self.local_folder and self.view == "tracks":
            local_tracks = [t for t in self.tracks if t.channel == LOCAL_CHANNEL]
            with connect() as conn:
                telegram_tracks = list_tracks(
                    conn,
                    limit=5000,
                    query=self.query or None,
                    channel=track_channel,
                    favorites_only=self.favorites_only,
                    tag=self.tag_filter,
                )
                self.channels = list_channels(conn)
                self.favorite_ids = get_all_favorite_ids(conn)
            self.tracks = local_tracks + telegram_tracks
        else:
            with connect() as conn:
                self.tracks = list_tracks(
                    conn,
                    limit=5000,
                    query=self.query or None,
                    channel=track_channel,
                    favorites_only=self.favorites_only,
                    tag=self.tag_filter,
                )
                self.channels = list_channels(conn)
                self.favorite_ids = get_all_favorite_ids(conn)
        if self.query:
            self.tracks = [
                t
                for t in self.tracks
                if fuzzy_match(self.query, t.display_title) or fuzzy_match(self.query, t.channel_title)
            ]
        self.browser_rows = self.build_browser_rows()
        items_len = len(self.browser_rows) if self.view == "channels" else len(self.tracks)
        self.selected = min(self.selected, max(items_len - 1, 0))
        detail = f"{len(self.channels)} channels | {len(self.tracks)} tracks"
        if self.channel_filter:
            detail += f" | carpeta: {self.channel_filter}"
        if self.query:
            detail += f" filtrados por '{self.query}'"
        if self.favorites_only:
            detail += " | favoritos"
        if self.tag_filter:
            detail += f" | tag:{self.tag_filter}"
        if self.now_playing and self.player.is_playing():
            detail += f" | Playing: {self.now_playing}"
        if self.watch_enabled:
            detail += " | watch:on"
        if self.repeat_mode:
            detail += " | repeat"
        if self.shuffle_mode:
            detail += " | shuffle"
        detail += f" | vol:{self.volume}"
        self.status = detail

    def start_watch_thread(self) -> None:
        if self.watch_thread and self.watch_thread.is_alive():
            return
        self.watch_stop_event.clear()
        self.watch_thread = threading.Thread(target=self.watch_loop, daemon=True)
        self.watch_thread.start()

    def stop_watch_thread(self) -> None:
        self.watch_stop_event.set()
        if self.watch_thread and self.watch_thread.is_alive():
            self.watch_thread.join(timeout=1)

    def toggle_watch(self) -> None:
        self.watch_enabled = not self.watch_enabled
        self.status = "Background watch on" if self.watch_enabled else "Background watch off"
        if self.watch_enabled:
            self.start_watch_thread()
        self.dirty = True

    def current_watch_channel(self) -> str | None:
        if self.view == "tracks":
            return self.channel_filter
        item = self.current_browser_item()
        if item is None:
            return self.channel_filter
        if item.get("kind") == "channel":
            return item["channel"].channel
        return str(item["channel"])

    def watch_loop(self) -> None:
        while not self.watch_stop_event.is_set():
            if not self.watch_enabled:
                if self.watch_stop_event.wait(1):
                    return
                continue

            channel = self.current_watch_channel()
            if channel:
                try:
                    self.check_new_music_for_channel(channel, background=True)
                except Exception as exc:
                    self.status = f"Watch error: {exc}"
                    self.dirty = True

            if self.watch_stop_event.wait(self.watch_interval):
                return

    def check_new_music_for_channel(self, channel: str, background: bool = False) -> None:
        with connect() as conn:
            since = self.watch_last_seen.get(channel)
            if since is None:
                since = latest_message_id_for_channel(conn, channel)
                self.watch_last_seen[channel] = since
            if since is None:
                if not background:
                    self.status = "No local baseline yet"
                    self.dirty = True
                return

        new_count = asyncio.run(scan_channel_since(channel, since, limit=50))

        with connect() as conn:
            latest_seen = latest_message_id_for_channel(conn, channel)
            self.watch_last_seen[channel] = latest_seen

            if not new_count:
                if not background:
                    self.status = f"No new tracks in {channel}"
                    self.dirty = True
                return

            track = latest_for_channel(conn, channel)

        title = track.display_title if track else channel
        message = f"{channel}: {new_count} new track(s)"
        notify_user("TG Music", f"{message}\n{title}")
        self.cache_line = f"Cache: new music in {channel}"
        self.status = f"New music: {new_count} track(s) in {channel}"
        self.dirty = True

    def build_browser_rows(self) -> list[dict[str, object]]:
        if self.view != "channels":
            return []

        rows: list[dict[str, object]] = []
        tracks_by_channel: dict[str, list[Track]] = {}
        for track in self.tracks:
            tracks_by_channel.setdefault(track.channel, []).append(track)

        from .local import LOCAL_CHANNEL

        local_tracks = tracks_by_channel.get(LOCAL_CHANNEL, [])
        local_count = len(local_tracks)
        local_title = "Local"
        if self.local_folder:
            from pathlib import Path

            local_title = f"Local ({Path(self.local_folder).name})"
        rows.append({"kind": "local", "channel": LOCAL_CHANNEL, "title": local_title, "count": local_count})
        if LOCAL_CHANNEL in self.expanded_channels:
            for track in local_tracks[:5]:
                rows.append({"kind": "track", "channel": LOCAL_CHANNEL, "track": track})

        for channel in self.channels:
            rows.append({"kind": "channel", "channel": channel})
            if channel.channel not in self.expanded_channels:
                continue
            for track in tracks_by_channel.get(channel.channel, [])[:5]:
                rows.append({"kind": "track", "channel": channel.channel, "track": track})
        return rows

    def move(self, delta: int) -> None:
        if self.split_mode:
            if self.split_panel == 0:
                items_len = len(self.channels)
            elif self.split_panel == 1:
                channel_name = self.channel_filter
                if channel_name:
                    items_len = len([t for t in self.tracks if t.channel == channel_name])
                else:
                    items_len = len(self.tracks)
            else:
                return
        elif self.view == "playlists":
            items_len = len(self.playlists)
        else:
            items_len = len(self.browser_rows) if self.view == "channels" else len(self.tracks)
        if not items_len:
            return
        self.selected = max(0, min(items_len - 1, self.selected + delta))
        self.dirty = True

    def go_back(self) -> None:
        if self.split_mode:
            if self.split_panel > 0:
                self.split_panel = 0
                self.view = "channels"
                self.selected = 0
                self.dirty = True
                return
        if self.view == "channels":
            item = self.current_browser_item()
            if item and item.get("kind") == "track":
                channel_name = str(item["channel"])
                parent_index = self.find_browser_channel_index(channel_name)
                if parent_index is not None:
                    self.selected = parent_index
                return
            if self.toggle_selected_channel_expansion(collapse_only=True):
                return
        elif self.view == "tracks" and (self.channel_filter is not None or self.local_folder):
            self.show_channels()
            return
        self.move(-1)

    def current_browser_item(self) -> dict[str, object] | None:
        if self.view != "channels" or not self.browser_rows:
            return None
        if not (0 <= self.selected < len(self.browser_rows)):
            return None
        return self.browser_rows[self.selected]

    def find_browser_channel_index(self, channel_name: str) -> int | None:
        for index, item in enumerate(self.browser_rows):
            if item.get("kind") == "channel":
                channel = item["channel"]
                if getattr(channel, "channel", None) == channel_name:
                    return index
        return None

    def toggle_selected_channel_expansion(self, collapse_only: bool = False) -> bool:
        item = self.current_browser_item()
        if not item or item.get("kind") != "channel":
            return False
        channel = item["channel"]
        channel_name = channel.channel
        if channel_name in self.expanded_channels:
            self.expanded_channels.remove(channel_name)
            self.reload()
            parent_index = self.find_browser_channel_index(channel_name)
            if parent_index is not None:
                self.selected = parent_index
            self.status = f"Collapsed: {channel.title or channel.channel}"
            self.dirty = True
            return True
        if collapse_only:
            return False
        self.expanded_channels.add(channel_name)
        self.reload()
        parent_index = self.find_browser_channel_index(channel_name)
        if parent_index is not None:
            self.selected = parent_index
        self.status = f"Expanded: {channel.title or channel.channel}"
        self.dirty = True
        return True

    def expand_selected_channel(self) -> None:
        if self.view == "channels":
            self.toggle_selected_channel_expansion()

    def search(self) -> None:
        clear_terminal_images()
        self.set_cursor_visible(True)
        self.pause_input_timeout()
        old_query = self.query
        try:
            height, width = self.screen.getmaxyx()
            prompt = "Search: "
            last_reload_len = -1
            while True:
                self.add(height - 1, 0, " " * max(width - 1, 0))
                display = f"{prompt}{self.query}_"
                self.add(height - 1, 0, display[: max(width - 1, 0)])
                self.screen.refresh()

                ch = self.screen.getch()

                if ch in (10, 13):
                    break
                elif ch in (27,):
                    self.query = old_query
                    break
                elif ch in (curses.KEY_BACKSPACE, 127, 8):
                    self.query = self.query[:-1]
                elif 32 <= ch <= 126:
                    self.query += chr(ch)

                if len(self.query) != last_reload_len:
                    last_reload_len = len(self.query)
                    self.view = "tracks" if self.query else "channels"
                    self.selected = 0
                    self.offset = 0
                    self.reload()
                    self.draw()
        finally:
            self.restore_input_timeout()
            self.set_cursor_visible(False)
        self.view = "tracks" if self.query else "channels"
        self.selected = 0
        self.offset = 0
        self.reload()
        self.dirty = True

    def command_mode_prompt(self) -> None:
        clear_terminal_images()
        self.set_cursor_visible(True)
        self.pause_input_timeout()
        try:
            height, width = self.screen.getmaxyx()
            prompt = ":"
            buf: list[str] = []
            while True:
                self.add(height - 1, 0, " " * max(width - 1, 0))
                display = prompt + "".join(buf)
                self.add(height - 1, 0, display[: max(width - 1, 0)])
                self.screen.refresh()

                ch = self.screen.getch()
                if ch in (10, 13):
                    break
                elif ch in (27,):
                    buf.clear()
                    break
                elif ch in (curses.KEY_BACKSPACE, 127, 8):
                    if buf:
                        buf.pop()
                elif 32 <= ch <= 256 and len(buf) < 80:
                    buf.append(chr(ch))
        finally:
            self.restore_input_timeout()
            self.set_cursor_visible(False)
            self.dirty = True

        cmd_str = "".join(buf).strip().split()
        if not cmd_str:
            return

        cmd = cmd_str[0].lower()
        args = cmd_str[1:]

        if cmd in ("q", "quit", "exit"):
            self.stop_playback()
            clear_terminal_images()
            raise SystemExit(0)
        elif cmd == "theme" and args:
            from .themes import get_theme, list_themes

            theme_name = args[0]
            if theme_name in list_themes():
                settings = load_settings()
                settings.theme = theme_name
                save_settings(settings)
                self.is_light = self.detect_light_theme()
                self.init_colors()
                self.status = f"Theme: {get_theme(theme_name).name}"
            else:
                self.status = f"Unknown theme: {theme_name}"
        elif cmd == "vol" and args:
            try:
                v = int(args[0])
                self.volume = max(0, min(v, 150))
                self.player.set_volume(self.volume)
                self.status = f"Volume: {self.volume}%"
            except ValueError:
                self.status = "Volume must be numeric"
        elif cmd == "help":
            self.toggle_help()
        elif cmd == "mini":
            self.toggle_mini_mode()
        elif cmd == "split":
            self.toggle_split_mode()
        elif cmd == "repeat":
            self.toggle_repeat()
        elif cmd == "shuffle":
            self.toggle_shuffle()
        elif cmd == "lyrics":
            self.toggle_lyrics()
        elif cmd == "channels":
            self.show_channels()
        elif cmd == "stop":
            self.stop_playback()
        elif cmd == "next":
            self.play_next(auto=False)
        elif cmd in ("tag", "t") and args:
            self.tag_prompt()
        elif cmd == "fav":
            self.toggle_favorite_selected()
        elif cmd in ("rm", "remove") and args:
            try:
                with connect() as conn:
                    from .db import remove_tag

                    tag_name = args[1] if len(args) > 1 else ""
                    if tag_name:
                        remove_tag(conn, tag_name)
                        self.status = f"Tag '{tag_name}' eliminado"
                    else:
                        self.status = "Uso: :rm <tag_name>"
            except (ValueError, IndexError):
                self.status = "Uso: :rm <tag_name>"
        elif cmd == "themes":
            themes_list = ", ".join(list_themes())
            self.status = f"Themes: {themes_list}"
        else:
            self.status = f"Unknown command: {cmd} (? for help)"

    def input_prompt(self, prompt: str, max_len: int = 160) -> str:
        clear_terminal_images()
        self.set_cursor_visible(True)
        self.pause_input_timeout()
        try:
            height, width = self.screen.getmaxyx()
            self.add(height - 1, 0, " " * max(width - 1, 0))
            self.add(height - 1, 0, prompt[: max(width - 1, 0)])
            self.screen.refresh()
            buf: list[int] = []
            while True:
                key = self.screen.getch()
                if key == 27:
                    return ""
                elif key in (10, 13):
                    curses.beep()
                    return "".join(buf).strip()
                elif key in (curses.KEY_BACKSPACE, 127, 8):
                    if buf:
                        buf.pop()
                        y = height - 1
                        self.add(y, 0, " " * max(width - 1, 0))
                        display = prompt + "".join(buf)
                        self.add(y, 0, display[: max(width - 1, 0)])
                elif 32 <= key < 256 and len(buf) < max_len:
                    buf.append(key)
                    y = height - 1
                    self.add(y, 0, " " * max(width - 1, 0))
                    display = prompt + "".join(buf)
                    self.add(y, 0, display[: max(width - 1, 0)])
                self.screen.refresh()
        finally:
            curses.noecho()
            self.restore_input_timeout()
            self.set_cursor_visible(False)

    def pause_input_timeout(self) -> None:
        try:
            self.screen.timeout(-1)
        except curses.error:
            pass

    def restore_input_timeout(self) -> None:
        try:
            self.screen.timeout(self.input_timeout_ms)
        except curses.error:
            pass

    def set_cursor_visible(self, visible: bool) -> None:
        try:
            curses.curs_set(1 if visible else 0)
        except curses.error:
            pass

    def add_channel_prompt(self) -> None:
        channel = self.input_prompt("Channel URL/@username: ")
        if not channel:
            self.status = "Add channel cancelled"
            self.dirty = True
            return
        limit_raw = self.input_prompt("Mensajes a revisar [300]: ", max_len=8)
        limit = int(limit_raw) if limit_raw.isdigit() else 300
        self.status = f"Scanning {channel}..."
        self.draw()
        try:
            count = asyncio.run(scan_channel(channel, limit))
            self.channel_filter = normalize_channel(channel)
            self.view = "tracks"
            self.query = ""
            self.selected = 0
            self.offset = 0
            self.reload()
            self.status = f"Added {self.channel_filter}: {count} tracks"
        except Exception as exc:
            self.status = f"Error adding channel: {exc}"
        self.dirty = True

    def enqueue_selected(self) -> None:
        if self.view == "channels":
            self.status = "Open a folder before queueing tracks"
            self.dirty = True
            return
        if not self.tracks:
            return
        track = self.tracks[self.selected]
        if self.current_track and self.current_track.id == track.id:
            self.status = "That track is already playing"
            self.dirty = True
            return
        if track.id not in self.play_queue:
            self.play_queue.append(track.id)
            self.status = f"Enqueued: {track.display_title}"
        else:
            self.status = f"Already queued: {track.display_title}"
        self.dirty = True

    def download_missing_prompt(self) -> None:
        if self.download_missing_thread and self.download_missing_thread.is_alive():
            self.status = "A bulk download is already running"
            self.dirty = True
            return
        if self.view == "channels":
            item = self.current_browser_item()
            if item and item.get("kind") == "channel":
                channel = item["channel"].channel
            elif item and item.get("kind") == "track":
                channel = str(item["channel"])
            else:
                channel = self.channel_filter
        else:
            channel = self.channel_filter

        self.status = "Downloading missing tracks..."
        self.dirty = True
        self.download_missing_thread = threading.Thread(
            target=self.run_download_missing_worker,
            args=(channel,),
            daemon=True,
        )
        self.download_missing_thread.start()

    def run_download_missing_worker(self, channel: str | None) -> None:
        try:
            with connect() as conn:
                tracks = list_uncached_tracks(conn, limit=5000, channel=channel)
            if not tracks:
                self.cache_line = "Cache: No missing tracks"
                self.status = "No missing tracks"
                return
            self.cache_line = f"Cache: Downloading missing tracks ({len(tracks)})..."
            asyncio.run(cache_tracks_async(tracks, workers=2))
            self.cache_line = f"Cache: Complete ({len(tracks)})"
            self.status = "Missing track download complete"
            self.reload()
        except Exception as exc:
            self.cache_line = "Cache: Error downloading missing tracks"
            self.status = f"Error downloading missing tracks: {exc}"
        finally:
            self.dirty = True

    def check_new_music_prompt(self) -> None:
        if self.new_music_thread and self.new_music_thread.is_alive():
            self.status = "A check is already running"
            self.dirty = True
            return
        if self.view == "channels":
            item = self.current_browser_item()
            if item and item.get("kind") == "channel":
                channel = item["channel"].channel
            elif item and item.get("kind") == "track":
                channel = str(item["channel"])
            else:
                channel = self.channel_filter
        else:
            channel = self.channel_filter
        if not channel:
            self.status = "No active channel to check"
            self.dirty = True
            return
        self.status = f"Checking for updates in {channel}..."
        self.dirty = True
        self.new_music_thread = threading.Thread(
            target=self.run_new_music_check_worker,
            args=(channel,),
            daemon=True,
        )
        self.new_music_thread.start()

    def run_new_music_check_worker(self, channel: str) -> None:
        try:
            self.check_new_music_for_channel(channel, background=False)
        except Exception as exc:
            self.status = f"Error checking updates: {exc}"
        finally:
            self.dirty = True

    def move_queue(self, delta: int) -> None:
        if self.view != "tracks" or not self.tracks or not self.play_queue:
            return
        if not (0 <= self.selected < len(self.tracks)):
            return
        track_id = self.tracks[self.selected].id
        if track_id not in self.play_queue:
            self.status = "Select a queued track to reorder it"
            self.dirty = True
            return
        index = self.play_queue.index(track_id)
        target = index + delta
        if target < 0 or target >= len(self.play_queue):
            return
        self.play_queue[index], self.play_queue[target] = self.play_queue[target], self.play_queue[index]
        self.status = "Queue moved"
        self.dirty = True

    def show_channels(self) -> None:
        self.view = "channels"
        self.selected = 0
        self.offset = 0
        self.favorites_only = False
        self.tag_filter = None
        self.playlist_filter = None
        self.channel_filter = None
        self.local_folder = None
        self.reload()
        self.status = "Browsing channels"
        self.dirty = True

    def open_selected_channel(self) -> None:
        from .local import LOCAL_CHANNEL, scan_folder

        if self.split_mode:
            if not self.channels:
                self.status = "No channels. Press a to add one."
                self.dirty = True
                return
            if 0 <= self.selected < len(self.channels):
                channel = self.channels[self.selected]
                self.channel_filter = channel.channel
                self.view = "tracks"
                self.split_panel = 1
                self.query = ""
                self.selected = 0
                self.offset = 0
                self.dirty = True
                self.reload()
            return
        if self.view == "channels":
            item = self.current_browser_item()
            if item is None:
                self.status = "No channels. Press a to add one."
                self.dirty = True
                return
            if item.get("kind") == "track":
                track = item["track"]
                self.view = "tracks"
                self.channel_filter = str(item["channel"])
                self.query = ""
                self.reload()
                track_index = next((index for index, row in enumerate(self.tracks) if row.id == track.id), None)
                self.selected = track_index if track_index is not None else 0
                self.play_track(track, selected_index=track_index)
                return
            if item.get("kind") == "local":
                chosen = self.browse_folder()
                if not chosen:
                    self.status = "Cancelled"
                    self.dirty = True
                    return
                try:
                    local_tracks = scan_folder(chosen)
                except Exception as e:
                    self.status = f"Error: {e}"
                    self.dirty = True
                    return
                if not local_tracks:
                    self.status = "No audio files in that folder"
                    self.dirty = True
                    return
                self.local_folder = chosen
                telegram_tracks = [t for t in self.tracks if t.channel != LOCAL_CHANNEL]
                self.tracks = local_tracks + telegram_tracks
                self.expanded_channels.add(LOCAL_CHANNEL)
                self.channel_filter = None
                self.view = "tracks"
                self.query = ""
                self.selected = 0
                self.offset = 0
                self.status = f"Local: {chosen} ({len(local_tracks)} tracks)"
                self.dirty = True
                if self.tracks:
                    self.play_track(self.tracks[0], selected_index=0)
                return
            channel = item["channel"]
        else:
            if not self.channels:
                self.status = "No channels. Press a to add one."
                self.dirty = True
                return
            channel = self.channels[self.selected]
        self.channel_filter = channel.channel
        self.view = "tracks"
        self.query = ""
        self.selected = 0
        self.offset = 0
        self.reload()
        self.status = f"Open folder: {channel.title or channel.channel}"
        self.dirty = True

    def scan_more_prompt(self) -> None:
        channel = self.channel_filter
        if self.view == "channels":
            item = self.current_browser_item()
            if item is not None:
                if item.get("kind") == "channel":
                    channel = item["channel"].channel
                else:
                    channel = str(item["channel"])
        if not channel:
            raw = self.input_prompt("Channel to scan: ")
            channel = normalize_channel(raw) if raw else None
        if not channel:
            self.status = "No channel selected"
            self.dirty = True
            return
        limit_raw = self.input_prompt("Extra messages to scan [300]: ", max_len=8)
        limit = int(limit_raw) if limit_raw.isdigit() else 300
        self.status = f"Scanning more from {channel}..."
        self.draw()
        try:
            count = asyncio.run(scan_channel(channel, limit))
            self.channel_filter = channel
            self.view = "tracks"
            self.reload()
            self.status = f"Scan complete: {count} tracks in {channel}"
        except Exception as exc:
            self.status = f"Error scanning channel: {exc}"
        self.dirty = True


def run_tui() -> None:
    from .welcome import is_configured, show_welcome

    if not is_configured():
        show_welcome()
        print("Run 'tg-music init' to configure, then 'tg-music tui' to start.")
        return

    import traceback as _tb
    import sys as _sys

    def _safe_wrapper(screen):
        try:
            Tui(screen).run()
        except SystemExit:
            pass
        except Exception as e:
            curses.endwin()
            print(f"Error: {e}", file=_sys.stderr)
            _tb.print_exc(file=_sys.stderr)

    wrapper(_safe_wrapper)
