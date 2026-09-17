from __future__ import annotations

import curses
import types

from tg_music.render_base import RenderBaseMixin
from tg_music.render_panels import RenderPanelsMixin


class _FakeScreen:
    def __init__(self, height: int, width: int) -> None:
        self.height = height
        self.width = width
        self.cells: dict[tuple[int, int], str] = {}

    def getmaxyx(self) -> tuple[int, int]:
        return (self.height, self.width)

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.cells[(y, x)] = text

    def addnstr(self, y: int, x: int, text: str, n: int, attr: int = 0) -> None:
        self.cells[(y, x)] = text[:n]

    def addch(self, y: int, x: int, ch: object, attr: int = 0) -> None:
        pass

    def erase(self) -> None:
        self.cells = {}

    def refresh(self) -> None:
        pass


def _make_track(title: str) -> object:
    return types.SimpleNamespace(
        display_title=title,
        channel_title="Test Channel",
        duration=200,
        local_path=None,
        id=1,
        title=title,
        filename=title,
        performer="Artist",
    )


class _FakeRenderer(RenderBaseMixin, RenderPanelsMixin):
    def __init__(self, screen: _FakeScreen, track: object) -> None:
        self.screen = screen
        self.color_pairs: dict[tuple[int, int], int] = {}
        self.color_primary = curses.COLOR_CYAN
        self.color_success = curses.COLOR_GREEN
        self.color_warning = curses.COLOR_YELLOW
        self.color_error = curses.COLOR_RED
        self.view = "tracks"
        self.mini_mode = False
        self.split_mode = False
        self.classic_mode = False
        self.lyrics_visible = False
        self.lyrics_text = ""
        self.current_track = track
        self.cover_path = None
        self.cover_lines = None
        self.cover_graphics = None
        self.cover_graphics_pos = None
        self.cover_graphics_draw_key = None
        self.play_queue: list[int] = []
        self.play_start_time = None
        self.repeat_mode = False
        self.shuffle_mode = False
        self.volume = 70
        self.favorite_ids: set[int] = set()
        self.eq_string = lambda: "\u2582\u2583\u2585\u2587\u2583"  # ▂▃▅▇▃
        self.channel_filter = None
        self.channels: list[object] = []
        self.tracks: list[object] = []
        self.selected = 0
        self.offset = 0
        self.query = None
        self.favorites_only = False
        self.tag_filter = None
        self.playlist_filter = None
        self.help_visible = False
        self.status = ""
        self.cache_line = "Cache: Ready"
        self.keybind_line = lambda w: ""


class TestNowPlayingHeader:
    def test_single_now_playing_line_no_duplicate(self, monkeypatch: object) -> None:
        from tg_music import render_panels as rp

        class _DummyConn:
            def __enter__(self) -> "_DummyConn":
                return self

            def __exit__(self, *exc: object) -> bool:
                return False

        monkeypatch.setattr(rp, "connect", lambda: _DummyConn())  # type: ignore[attr-defined]
        monkeypatch.setattr(rp, "is_favorite", lambda conn, tid: False)  # type: ignore[attr-defined]
        monkeypatch.setattr(rp, "get_track_tags", lambda conn, tid: [])  # type: ignore[attr-defined]
        monkeypatch.setattr(curses, "has_colors", lambda: False)  # type: ignore[attr-defined]

        screen = _FakeScreen(40, 120)
        track = _make_track("Lead Me Back (Psalm 139)")
        r = _FakeRenderer(screen, track)

        # Replicate draw()'s right-panel geometry.
        left_width = max(42, int(screen.width * 0.58))
        right_x = left_width + 1
        right_width = max(screen.width - right_x, 0)

        # Full panel render, then the per-tick overlay writes to the same screen.
        r.draw_right_panel(6, right_x, right_width, screen.height - 6)
        r.play_start_time = 100.0
        assert r.draw_playback_tick() is True

        now_playing_rows = sorted(
            {y for (y, x), t in screen.cells.items() if "NOW PLAYING" in t}
        )
        assert now_playing_rows == [6], now_playing_rows

        header = screen.cells.get((6, right_x + 1), "")
        assert "NOW PLAYING" in header
        assert "Lead Me Back" in header
        assert "\u2582\u2583\u2585\u2587\u2583" in header
