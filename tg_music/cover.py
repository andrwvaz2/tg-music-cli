from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .config import COVER_CACHE_DIR
from .models import Track


def render_cover(path: Path | None, max_width: int, max_height: int) -> list[str]:
    if path is None or shutil.which("chafa") is None:
        return []
    try:
        output = subprocess.check_output(
            [
                "chafa",
                "--format=symbols",
                "--colors=256",
                "--color-space=din99d",
                "--dither=ordered",
                "--symbols=block+border+half+quad+sextant",
                f"--size={max_width}x{max_height}",
                str(path),
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.rstrip() for line in output.splitlines()]


def extract_embedded_cover(audio_path: Path, track: Track) -> Path | None:
    if shutil.which("ffmpeg") is None:
        return None
    COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = COVER_CACHE_DIR / f"{track.channel}-{track.message_id}-embedded-cover.jpg"
    if target.exists() and target.stat().st_size > 0:
        return target

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(audio_path),
                "-an",
                "-frames:v",
                "1",
                str(target),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if target.exists() and target.stat().st_size > 0:
        return target
    return None


def render_graphics_cover(path: Path | None, max_width: int, max_height: int) -> bytes | None:
    if path is None or not supports_graphics_cover() or shutil.which("chafa") is None:
        return None
    try:
        return subprocess.check_output(
            [
                "chafa",
                "--format=kitty",
                f"--size={max_width}x{max_height}",
                "--animate=off",
                str(path),
            ],
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def supports_graphics_cover() -> bool:
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    if "ghostty" in term_program:
        return True
    if os.environ.get("KITTY_WINDOW_ID"):
        return True
    return False
