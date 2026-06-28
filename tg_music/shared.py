from __future__ import annotations

import time
import shutil
import subprocess
import sys
from pathlib import Path

from .config import AUDIO_CACHE_DIR, COVER_CACHE_DIR
from .models import Track


def fuzzy_match(query: str, text: str) -> bool:
    if not query:
        return True
    query_lower = query.lower()
    text_lower = text.lower()
    qi = 0
    for char in text_lower:
        if qi < len(query_lower) and char == query_lower[qi]:
            qi += 1
    return qi == len(query_lower)


def format_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def notify_user(title: str, body: str) -> None:
    if shutil.which("notify-send") is not None:
        subprocess.run(["notify-send", title, body], check=False)
        return
    print(f"{title}: {body}")


def delete_cached_files(track: Track) -> None:
    if track.local_path:
        path = Path(track.local_path).expanduser()
        if path.exists() and path.is_file():
            path.unlink()
    for cover in COVER_CACHE_DIR.glob(f"{track.channel}-{track.message_id}-*cover*"):
        if cover.is_file():
            cover.unlink()


def cleanup_stale_cache(max_age_days: int = 30) -> int:
    cutoff = time.time() - (max_age_days * 86400)
    removed = 0
    for directory in (AUDIO_CACHE_DIR, COVER_CACHE_DIR):
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
    return removed
