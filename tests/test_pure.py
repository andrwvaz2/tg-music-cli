from __future__ import annotations

import pytest
from tg_music.models import Track, format_duration
from tg_music.telegram_client import normalize_channel, safe_name, clean_message_text
from tg_music.shared import fuzzy_match, format_bytes
from tg_music.lyrics import fetch_lyrics
from tg_music.tui_render import CSI_RE, parse_ansi_sgr


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
