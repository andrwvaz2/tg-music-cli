from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Track:
    id: int
    channel: str
    channel_title: str
    message_id: int
    title: str
    performer: str
    duration: int | None
    mime_type: str
    filename: str
    size: int | None
    date: str
    local_path: str | None
    ignored: bool = False
    play_count: int = 0
    last_played_at: str | None = None

    @property
    def display_title(self) -> str:
        if self.performer and self.title:
            return f"{self.performer} - {self.title}"
        return self.title or self.filename or f"message {self.message_id}"

    @property
    def telegram_url(self) -> str:
        return f"https://t.me/{self.channel}/{self.message_id}"


@dataclass(frozen=True)
class Channel:
    channel: str
    title: str
    last_scan_at: str | None = None
    created_at: str | None = None


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "--:--"
    minutes, sec = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{sec:02d}"
    return f"{minutes:d}:{sec:02d}"
