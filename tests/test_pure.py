from __future__ import annotations

import pytest

from tg_music.models import Track, format_duration
from tg_music.telegram_client import normalize_channel, safe_name, clean_message_text
from tg_music.shared import fuzzy_match, format_bytes
from tg_music.lyrics import fetch_lyrics
from tg_music.render_base import CSI_RE, parse_ansi_sgr


class TestFormatDuration:
    def test_none(self) -> None:
        assert format_duration(None) == "--:--"

    def test_seconds(self) -> None:
        assert format_duration(45) == "0:45"

    def test_minutes(self) -> None:
        assert format_duration(125) == "2:05"

    def test_hours(self) -> None:
        assert format_duration(3661) == "1:01:01"

    def test_zero(self) -> None:
        assert format_duration(0) == "0:00"


class TestNormalizeChannel:
    def test_username(self) -> None:
        assert normalize_channel("@mychannel") == "mychannel"

    def test_tme_url(self) -> None:
        assert normalize_channel("https://t.me/mychannel") == "mychannel"

    def test_http_url(self) -> None:
        assert normalize_channel("http://t.me/mychannel") == "mychannel"

    def test_plain(self) -> None:
        assert normalize_channel("mychannel") == "mychannel"

    def test_strips_slash(self) -> None:
        assert normalize_channel("t.me/mychannel/") == "mychannel"


class TestSafeName:
    def test_normal(self) -> None:
        assert safe_name("Hello World") == "Hello World"

    def test_special_chars(self) -> None:
        result = safe_name("Hello/World@Test!")
        assert "/" not in result
        assert "@" not in result
        assert "!" not in result

    def test_empty(self) -> None:
        assert safe_name("") == "unknown"


class TestCleanMessageText:
    def test_normal(self) -> None:
        assert clean_message_text("Hello World") == "Hello World"

    def test_multiple_spaces(self) -> None:
        assert clean_message_text("Hello   World") == "Hello World"

    def test_truncated(self) -> None:
        text = "a" * 200
        assert len(clean_message_text(text)) == 120


class TestFuzzyMatch:
    def test_empty_query(self) -> None:
        assert fuzzy_match("", "anything") is True

    def test_exact_match(self) -> None:
        assert fuzzy_match("hello", "hello world") is True

    def test_partial_match(self) -> None:
        assert fuzzy_match("hlo", "hello world") is True

    def test_no_match(self) -> None:
        assert fuzzy_match("xyz", "hello world") is False

    def test_case_insensitive(self) -> None:
        assert fuzzy_match("HELLO", "hello world") is True

    def test_scattered(self) -> None:
        assert fuzzy_match("hwd", "hello world") is True


class TestFormatBytes:
    def test_bytes(self) -> None:
        assert format_bytes(500) == "500.0 B"

    def test_kb(self) -> None:
        assert format_bytes(1536) == "1.5 KB"

    def test_mb(self) -> None:
        assert format_bytes(1048576) == "1.0 MB"

    def test_gb(self) -> None:
        assert format_bytes(1073741824) == "1.0 GB"


class TestAnsiRendering:
    def test_parse_sgr_256_color_sequences(self) -> None:
        result = parse_ansi_sgr("\x1b[38;5;238;48;5;237m##\x1b[0m..")

        assert result == [
            ("##", 238, 237),
            ("..", -1, -1),
        ]

    def test_visible_width_ignores_chafa_control_sequences(self) -> None:
        line = "\x1b[?25l\x1b[38;5;24;48;5;237m██\x1b[0m\x1b[?25h"

        assert len(CSI_RE.sub("", line)) == 2


class TestTrack:
    def test_display_title_with_performer(self) -> None:
        track = Track(
            id=1, channel="test", channel_title="Test",
            message_id=1, title="Song", performer="Artist",
            duration=180, mime_type="audio/mpeg", filename="song.mp3",
            size=1000000, date="2024-01-01", local_path=None,
        )
        assert track.display_title == "Artist - Song"

    def test_display_title_without_performer(self) -> None:
        track = Track(
            id=1, channel="test", channel_title="Test",
            message_id=1, title="Song", performer="",
            duration=180, mime_type="audio/mpeg", filename="song.mp3",
            size=1000000, date="2024-01-01", local_path=None,
        )
        assert track.display_title == "Song"

    def test_display_title_fallback_to_filename(self) -> None:
        track = Track(
            id=1, channel="test", channel_title="Test",
            message_id=1, title="", performer="",
            duration=180, mime_type="audio/mpeg", filename="song.mp3",
            size=1000000, date="2024-01-01", local_path=None,
        )
        assert track.display_title == "song.mp3"

    def test_display_title_fallback_to_message_id(self) -> None:
        track = Track(
            id=1, channel="test", channel_title="Test",
            message_id=42, title="", performer="",
            duration=180, mime_type="audio/mpeg", filename="",
            size=1000000, date="2024-01-01", local_path=None,
        )
        assert track.display_title == "message 42"

    def test_telegram_url(self) -> None:
        track = Track(
            id=1, channel="mychannel", channel_title="Test",
            message_id=123, title="Song", performer="",
            duration=180, mime_type="audio/mpeg", filename="",
            size=1000000, date="2024-01-01", local_path=None,
        )
        assert track.telegram_url == "https://t.me/mychannel/123"

    def test_play_count_default(self) -> None:
        track = Track(
            id=1, channel="test", channel_title="Test",
            message_id=1, title="Song", performer="",
            duration=180, mime_type="audio/mpeg", filename="",
            size=1000000, date="2024-01-01", local_path=None,
        )
        assert track.play_count == 0
        assert track.last_played_at is None


class TestLyrics:
    def test_fetch_returns_none_on_failure(self) -> None:
        result = fetch_lyrics("Nonexistent Artist", "Nonexistent Song 12345")
        assert result is None

    def test_fetch_real_song(self) -> None:
        result = fetch_lyrics("Queen", "Bohemian Rhapsody", duration=354)
        if result is not None:
            assert result.artist == "Queen"
            assert result.title == "Bohemian Rhapsody"


class TestRenderBase:
    def test_wrap_short_text(self) -> None:
        from tg_music.render_base import wrap
        result = wrap("hello", 80)
        assert result == ["hello"]

    def test_wrap_long_text(self) -> None:
        from tg_music.render_base import wrap
        result = wrap("hello world this is a long line", 10)
        assert len(result) >= 2
        assert all(len(line) <= 10 for line in result)

    def test_parse_ansi_sgr_plain(self) -> None:
        from tg_music.render_base import parse_ansi_sgr
        parts = parse_ansi_sgr("hello")
        assert len(parts) == 1
        assert parts[0] == ("hello", -1, -1)

    def test_parse_ansi_sgr_with_color(self) -> None:
        from tg_music.render_base import parse_ansi_sgr
        parts = parse_ansi_sgr("\x1b[38;5;1mred\x1b[0m normal")
        assert len(parts) == 2
        assert parts[0] == ("red", 1, -1)
        assert parts[1] == (" normal", -1, -1)


class TestDBPlaylists:
    def test_list_playlists_empty(self) -> None:
        from tg_music.db import connect, list_playlists
        with connect() as conn:
            result = list_playlists(conn)
        assert isinstance(result, list)

    def test_list_playlists_has_count(self) -> None:
        from tg_music.db import connect, list_playlists
        with connect() as conn:
            result = list_playlists(conn)
        for pl in result:
            assert "count" in pl
            assert isinstance(pl["count"], int)


class TestPlaylistCommands:
    def test_create_and_list(self) -> None:
        from tg_music.db import connect, create_playlist, list_playlists, delete_playlist, get_playlist_by_name
        with connect() as conn:
            pl_id = create_playlist(conn, "test_pl_cmd")
            assert isinstance(pl_id, int)
            playlists = list_playlists(conn)
            names = [p["name"] for p in playlists]
            assert "test_pl_cmd" in names
            pl = get_playlist_by_name(conn, "test_pl_cmd")
            assert pl is not None
            delete_playlist(conn, pl["id"])

    def test_add_and_show(self) -> None:
        from tg_music.db import (
            connect, create_playlist, delete_playlist, get_playlist_by_name,
            add_to_playlist, get_playlist_tracks, get_track,
        )
        with connect() as conn:
            pl_id = create_playlist(conn, "test_pl_show")
            # Insert a real track so FK passes
            conn.execute(
                "INSERT INTO tracks (channel, channel_title, message_id, title, performer, mime_type, size) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("test", "Test", 99999, "Test Song", "Test Artist", "audio/mpeg", 0),
            )
            conn.commit()
            track = get_track(conn, conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            add_to_playlist(conn, pl_id, track.id)
            tracks = get_playlist_tracks(conn, pl_id)
            assert len(tracks) == 1
            assert tracks[0].title == "Test Song"
            # Cleanup
            conn.execute("DELETE FROM tracks WHERE id = ?", (track.id,))
            conn.commit()
            pl = get_playlist_by_name(conn, "test_pl_show")
            delete_playlist(conn, pl["id"])

    def test_remove_compacts_positions(self) -> None:
        from tg_music.db import (
            connect, create_playlist, delete_playlist, get_playlist_by_name,
            add_to_playlist, remove_from_playlist, get_playlist_tracks,
        )
        with connect() as conn:
            pl_id = create_playlist(conn, "test_pl_compact")
            # Insert tracks
            ids = []
            for i in range(3):
                conn.execute(
                    "INSERT INTO tracks (channel, channel_title, message_id, title, mime_type, size) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    ("test", "Test", 100000 + i, f"Track {i}", "audio/mpeg", 0),
                )
                conn.commit()
                tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                add_to_playlist(conn, pl_id, tid)
                ids.append(tid)
            # Remove middle
            remove_from_playlist(conn, pl_id, ids[1])
            tracks = get_playlist_tracks(conn, pl_id)
            assert len(tracks) == 2
            # Verify no gaps in positions
            rows = conn.execute(
                "SELECT position FROM playlist_tracks WHERE playlist_id = ? ORDER BY position",
                (pl_id,),
            ).fetchall()
            positions = [r["position"] for r in rows]
            assert positions == [0, 1]
            # Cleanup
            for tid in ids:
                conn.execute("DELETE FROM tracks WHERE id = ?", (tid,))
            conn.commit()
            pl = get_playlist_by_name(conn, "test_pl_compact")
            delete_playlist(conn, pl["id"])

    def test_reorder(self) -> None:
        from tg_music.db import (
            connect, create_playlist, delete_playlist, get_playlist_by_name,
            add_to_playlist, reorder_playlist_track, get_playlist_tracks,
        )
        with connect() as conn:
            pl_id = create_playlist(conn, "test_pl_reorder")
            ids = []
            for i in range(3):
                conn.execute(
                    "INSERT INTO tracks (channel, channel_title, message_id, title, mime_type, size) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    ("test", "Test", 200000 + i, f"Reorder {i}", "audio/mpeg", 0),
                )
                conn.commit()
                tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                add_to_playlist(conn, pl_id, tid)
                ids.append(tid)
            # Move first to last (pos 0 -> pos 2)
            ok = reorder_playlist_track(conn, pl_id, ids[0], 2)
            assert ok is True
            tracks = get_playlist_tracks(conn, pl_id)
            assert tracks[0].id == ids[1]
            assert tracks[1].id == ids[2]
            assert tracks[2].id == ids[0]
            # Move nonexistent
            ok = reorder_playlist_track(conn, pl_id, 999999, 0)
            assert ok is False
            # Cleanup
            for tid in ids:
                conn.execute("DELETE FROM tracks WHERE id = ?", (tid,))
            conn.commit()
            pl = get_playlist_by_name(conn, "test_pl_reorder")
            delete_playlist(conn, pl["id"])


class TestSearchCommands:
    def _insert_track(self, conn, title, performer, channel="schannel", filename="f.mp3"):
        conn.execute(
            "INSERT INTO tracks (channel, channel_title, message_id, title, performer, filename, mime_type, size) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (channel, channel, 500000 + abs(hash(title)) % 100000, title, performer, filename, "audio/mpeg", 0),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def test_search_simple(self) -> None:
        from tg_music.db import connect, search_tracks_fts
        with connect() as conn:
            self._insert_track(conn, "Sunset Love", "Maria", channel="rockchan")
            self._insert_track(conn, "Midnight Rain", "John", channel="popchan")
            results = search_tracks_fts(conn, "love", limit=20)
            titles = [t.title for t in results]
            assert any("Love" in t for t in titles)

    def test_search_no_results(self) -> None:
        from tg_music.db import connect, search_tracks_fts
        with connect() as conn:
            results = search_tracks_fts(conn, "zzzqqqnonexistent", limit=20)
            assert results == []

    def test_search_with_channel(self) -> None:
        from tg_music.db import connect, search_tracks_fts
        with connect() as conn:
            self._insert_track(conn, "Echo Song", "Ana", channel="chanA")
            self._insert_track(conn, "Echo Song", "Ana", channel="chanB")
            results = search_tracks_fts(conn, "echo", limit=20, channel="chanA")
            assert len(results) == 1
            assert results[0].channel == "chanA"

    def test_search_with_tag(self) -> None:
        from tg_music.db import connect, search_tracks_fts, add_tag, tag_track
        with connect() as conn:
            tid = self._insert_track(conn, "Tagged Melody", "Luis", channel="tagchan")
            add_tag(conn, "gold")
            tag_track(conn, tid, "gold")
            results = search_tracks_fts(conn, "melody", limit=20, tag="gold")
            assert len(results) == 1
            assert results[0].id == tid
            # Tag that no track has -> empty
            results = search_tracks_fts(conn, "melody", limit=20, tag="nonexistenttag")
            assert results == []

    def test_search_invalid_fts_syntax(self) -> None:
        from tg_music.db import connect, search_tracks_fts, SearchQueryError
        with connect() as conn:
            with pytest.raises(SearchQueryError):
                search_tracks_fts(conn, '"unclosed quote', limit=20)

    def test_cmd_search_invalid_returns_one(self) -> None:
        from argparse import Namespace
        from tg_music import cli
        args = Namespace(query='"unclosed quote', limit=20, channel=None, tag=None, json=False)
        rc = cli.cmd_search(args)
        assert rc == 1


class TestDBFavorites:
    def test_is_favorite_returns_bool(self) -> None:
        from tg_music.db import connect, is_favorite
        with connect() as conn:
            result = is_favorite(conn, 999999)
        assert isinstance(result, bool)

    def test_get_all_favorite_ids_returns_set(self) -> None:
        from tg_music.db import connect, get_all_favorite_ids
        with connect() as conn:
            result = get_all_favorite_ids(conn)
        assert isinstance(result, set)


class TestDBTags:
    def test_add_and_remove_tag(self) -> None:
        from tg_music.db import connect, add_tag, remove_tag
        with connect() as conn:
            tag_id = add_tag(conn, "test_tag_xyz")
            assert isinstance(tag_id, int)
            remove_tag(conn, "test_tag_xyz")

    def test_get_track_tags_returns_list(self) -> None:
        from tg_music.db import connect, get_track_tags
        with connect() as conn:
            result = get_track_tags(conn, 999999)
        assert isinstance(result, list)


class TestDBTracks:
    def test_get_track_nonexistent(self) -> None:
        from tg_music.db import connect, get_track
        with connect() as conn:
            result = get_track(conn, 999999999)
        assert result is None

    def test_list_tracks_returns_list(self) -> None:
        from tg_music.db import connect, list_tracks
        with connect() as conn:
            result = list_tracks(conn)
        assert isinstance(result, list)


class TestThemes:
    def test_list_themes(self) -> None:
        from tg_music.themes import list_themes
        themes = list_themes()
        assert isinstance(themes, list)
        assert len(themes) > 0
        assert "dark" in themes

    def test_get_theme_valid(self) -> None:
        from tg_music.themes import get_theme
        theme = get_theme("dark")
        assert theme is not None

    def test_get_theme_invalid(self) -> None:
        from tg_music.themes import get_theme
        theme = get_theme("nonexistent_theme_xyz")
        assert theme is not None  # returns default


class TestConfig:
    def test_load_settings(self) -> None:
        from tg_music.config import load_settings
        settings = load_settings()
        assert hasattr(settings, "volume")
        assert hasattr(settings, "theme")

    def test_save_and_load_settings(self) -> None:
        from tg_music.config import load_settings, save_settings
        settings = load_settings()
        original_volume = settings.volume
        settings.volume = 42
        save_settings(settings)
        reloaded = load_settings()
        assert reloaded.volume == 42
        # Restore
        settings.volume = original_volume
        save_settings(settings)
