from __future__ import annotations

import os
from pathlib import Path

from mutagen import File as MutagenFile

from .models import Track

AUDIO_EXTENSIONS = {".mp3", ".flac", ".ogg", ".wav", ".m4a", ".aac", ".wma", ".opus", ".aiff"}

LOCAL_CHANNEL = "__local__"
LOCAL_CHANNEL_TITLE = "Local"


def scan_folder(path: str | Path, recursive: bool = False) -> list[Track]:
    folder = Path(path).expanduser().resolve()
    if not folder.is_dir():
        raise FileNotFoundError(f"No existe la carpeta: {folder}")

    files: list[Path] = []
    if recursive:
        for root, _dirs, filenames in os.walk(folder):
            for fn in filenames:
                fp = Path(root) / fn
                if fp.suffix.lower() in AUDIO_EXTENSIONS:
                    files.append(fp)
    else:
        for fp in folder.iterdir():
            if fp.is_file() and fp.suffix.lower() in AUDIO_EXTENSIONS:
                files.append(fp)

    files.sort(key=lambda f: f.name.lower())

    tracks: list[Track] = []
    for i, fp in enumerate(files, start=1):
        title, performer, duration = _read_metadata(fp)
        tracks.append(
            Track(
                id=-(i),
                channel=LOCAL_CHANNEL,
                channel_title=LOCAL_CHANNEL_TITLE,
                message_id=i,
                title=title,
                performer=performer,
                duration=duration,
                mime_type=_mime_from_ext(fp.suffix),
                filename=fp.name,
                size=fp.stat().st_size,
                date="",
                local_path=str(fp),
                ignored=False,
                play_count=0,
            )
        )
    return tracks


def _read_metadata(fp: Path) -> tuple[str, str, int | None]:
    title = fp.stem
    performer = ""
    duration: int | None = None
    try:
        audio = MutagenFile(str(fp), easy=True)
        if audio is not None:
            if audio.info and audio.info.length:
                duration = int(audio.info.length)
            if audio.tags:
                if "title" in audio.tags and audio.tags["title"]:
                    title = audio.tags["title"][0]
                if "artist" in audio.tags and audio.tags["artist"]:
                    performer = audio.tags["artist"][0]
                elif "albumartist" in audio.tags and audio.tags["albumartist"]:
                    performer = audio.tags["albumartist"][0]
    except Exception:
        pass
    return title, performer, duration


def _mime_from_ext(ext: str) -> str:
    mapping = {
        ".mp3": "audio/mpeg",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".wma": "audio/x-ms-wma",
        ".opus": "audio/opus",
        ".aiff": "audio/aiff",
    }
    return mapping.get(ext.lower(), "audio/unknown")
