from __future__ import annotations

import asyncio
import random
import threading
import time

from .cache import cache_tracks_async
from .cover import extract_embedded_cover
from .db import connect, get_track, list_tracks, record_play, set_ignored
from .models import Track
from .shared import delete_cached_files, format_bytes
from .telegram_client import download_cover, download_track


class PlayerMixin:
    def play_selected(self) -> None:
        if self.view == "channels":
            item = self.current_browser_item()
            if item and item.get("kind") == "track":
                track = item["track"]
                self.view = "tracks"
                self.channel_filter = str(item["channel"])
                self.query = ""
                self.reload()
                track_index = next((index for index, row in enumerate(self.tracks) if row.id == track.id), None)
                self.selected = track_index if track_index is not None else 0
                self.play_track(track, selected_index=track_index)
            return
        if self.view == "playlists":
            self.open_selected_playlist()
            return
        if self.favorites_only or self.tag_filter:
            filtered = self.tracks
            if self.selected < len(filtered):
                track = filtered[self.selected]
                self.play_track(track, selected_index=self.selected)
            return
        track = self.tracks[self.selected]
        self.play_track(track, selected_index=self.selected)

    def play_track(self, track: Track, selected_index: int | None = None) -> None:
        from .local import LOCAL_CHANNEL
        if selected_index is not None:
            self.selected = selected_index
        self.status = f"Preparando cache: {track.display_title}"
        self.draw()
        try:
            if track.channel == LOCAL_CHANNEL:
                path = track.local_path
            else:
                self.downloading_track_id = track.id
                try:
                    path = asyncio.run(download_track(track, progress=self.download_progress))
                finally:
                    self.downloading_track_id = None
            if not path:
                self.status = "No se pudo obtener el archivo"
                return
            self.cover_path = extract_embedded_cover(path, track)
            if not self.cover_path and track.channel != LOCAL_CHANNEL:
                self.cover_path = asyncio.run(download_cover(track))
            self.cover_render_key = None
            screen_height, screen_width = self.screen.getmaxyx()
            self.refresh_cover_art(screen_height, screen_width)
            self.player.play(path)
            self.manual_stop = False
            self.play_start_time = time.time()
            self.last_elapsed_seconds = 0
            self.current_track = track
            self.current_audio_path = path
            self.now_playing = track.display_title
            self.cache_line = "Cache: Listo"
            self.status = f"Sonando: {track.display_title}"
            if track.channel != LOCAL_CHANNEL:
                with connect() as conn:
                    record_play(conn, track.id)
                    self.tracks = list_tracks(
                        conn,
                        limit=5000,
                        query=self.query or None,
                        channel=self.channel_filter,
                        favorites_only=self.favorites_only,
                        tag=self.tag_filter,
                    )
            self.lyrics_text = ""
            self.draw()
            self.start_precache_after_selection()
        except Exception as exc:
            self.status = f"Error: {exc}"
        finally:
            self.screen.clear()
            self.cover_graphics_draw_key = None

    def stop_playback(self) -> None:
        self.manual_stop = True
        self.player.stop()
        self.status = "Reproduccion detenida"
        self.play_start_time = None
        self.last_elapsed_seconds = 0
        self.dirty = True

    def play_next(self, auto: bool) -> None:
        if not self.tracks:
            return
        if self.play_queue:
            queued_id = self.play_queue.pop(0)
            queued_index = next((index for index, track in enumerate(self.tracks) if track.id == queued_id), None)
            queued_track = self.tracks[queued_index] if queued_index is not None else None
            if queued_track is None:
                with connect() as conn:
                    queued_track = get_track(conn, queued_id)
            if queued_track is not None:
                self.status = "Queued next" if auto else "Queued"
                self.dirty = True
                self.play_track(queued_track, selected_index=queued_index)
                return

        if self.shuffle_mode:
            available = [t for t in self.tracks if self.current_track is None or t.id != self.current_track.id]
            if available:
                next_track = random.choice(available)
                next_index = next((i for i, t in enumerate(self.tracks) if t.id == next_track.id), 0)
                self.selected = next_index
                self.status = "Shuffle"
                self.dirty = True
                track = self.tracks[next_index]
                self.play_track(track, selected_index=next_index)
                return

        start = self.selected
        if self.current_track:
            for index, track in enumerate(self.tracks):
                if track.id == self.current_track.id:
                    start = index
                    break
        next_index = start + 1
        if next_index >= len(self.tracks):
            if self.repeat_mode:
                self.selected = 0
                self.status = "Repeat"
                self.dirty = True
                track = self.tracks[0]
                self.play_track(track, selected_index=0)
                return
            self.status = "Fin de la lista"
            self.current_track = None
            self.now_playing = ""
            self.current_audio_path = None
            self.play_start_time = None
            self.last_elapsed_seconds = 0
            self.dirty = True
            return
        self.selected = next_index
        self.status = "Auto-next" if auto else "Next"
        self.dirty = True
        track = self.tracks[next_index]
        self.play_track(track, selected_index=next_index)

    def ignore_selected(self) -> None:
        track: Track | None = None
        if self.view == "channels":
            item = self.current_browser_item()
            if item is None:
                return
            if item.get("kind") == "track":
                track = item["track"]
                self.view = "tracks"
                self.channel_filter = str(item["channel"])
                self.query = ""
                self.reload()
                self.selected = next((index for index, row in enumerate(self.tracks) if row.id == track.id), 0)
            else:
                self.open_selected_channel()
                return
        if track is None:
            if not self.tracks:
                return
            track = self.tracks[self.selected]
        if self.current_track and self.current_track.id == track.id:
            self.stop_playback()
            self.current_track = None
            self.current_audio_path = None
            self.cover_path = None
            self.cover_lines = []
            self.cover_graphics = None
            self.cover_graphics_draw_key = None
            from .tui_render import clear_terminal_images
            clear_terminal_images()
        if track.id in self.play_queue:
            self.play_queue = [queued for queued in self.play_queue if queued != track.id]
        delete_cached_files(track)
        with connect() as conn:
            set_ignored(conn, track.id, True)
            self.tracks = list_tracks(
                conn,
                limit=5000,
                query=self.query or None,
                channel=self.channel_filter,
            )
        self.selected = min(self.selected, max(len(self.tracks) - 1, 0))
        self.status = f"Ignored: {track.display_title}"
        self.dirty = True

    def download_progress(self, downloaded: int, total: int) -> None:
        if total:
            percent = downloaded / total * 100
            bar_width = 15
            filled = int(percent / 100 * bar_width)
            bar = "\u2588" * filled + "\u2591" * (bar_width - filled)
            self.cache_line = (
                f"Cache: [{bar}] {percent:5.1f}%  ({format_bytes(downloaded)} / "
                f"{format_bytes(total)})"
            )
        else:
            self.cache_line = f"Cache: {format_bytes(downloaded)}"
        self.draw()

    def start_precache_after_selection(self) -> None:
        if self.precache_thread and self.precache_thread.is_alive():
            return
        candidates = [
            track
            for track in self.tracks[self.selected + 1 : self.selected + 8]
            if not track.local_path and track.id not in self.precache_ids and track.id not in self.play_queue
        ][:3]
        if not candidates:
            return
        for track in candidates:
            self.precache_ids.add(track.id)
        self.cache_line = f"Pre-descargando: {len(candidates)} track(s) en segundo plano..."
        self.dirty = True
        self.precache_thread = threading.Thread(
            target=self.run_precache_worker,
            args=(candidates,),
            daemon=True,
        )
        self.precache_thread.start()

    def run_precache_worker(self, tracks: list[Track]) -> None:
        async def run() -> None:
            await cache_tracks_async(tracks, workers=1)

        try:
            asyncio.run(run())
            self.reload()
            self.cache_line = f"Pre-descarga completa: {len(tracks)} track(s)"
        except Exception as exc:
            self.cache_line = f"Pre-descarga error: {exc}"
        finally:
            self.dirty = True
