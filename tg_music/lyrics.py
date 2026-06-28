from __future__ import annotations

import json
import urllib.request
import urllib.parse
from dataclasses import dataclass


@dataclass(frozen=True)
class LyricResult:
    artist: str
    title: str
    album: str | None
    duration: int | None
    synced: str | None
    plain: str | None


def fetch_lyrics(artist: str, title: str, duration: int | None = None) -> LyricResult | None:
    params: dict[str, str | int] = {
        "artist_name": artist,
        "track_name": title,
    }
    if duration is not None and duration > 0:
        params["duration"] = duration

    url = "https://lrclib.net/api/get?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "tg-music-cli/0.1"})

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None

    if not data:
        return None

    return LyricResult(
        artist=data.get("artistName", artist),
        title=data.get("trackName", title),
        album=data.get("albumName"),
        duration=data.get("duration"),
        synced=data.get("syncedLyrics"),
        plain=data.get("plainLyrics"),
    )
