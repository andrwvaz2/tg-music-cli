from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from telethon import TelegramClient
from telethon.tl.types import (
    DocumentAttributeAudio,
    DocumentAttributeFilename,
    Message,
)

from .config import AUDIO_CACHE_DIR, COVER_CACHE_DIR, SESSION_FILE, ensure_session_permissions, load_config
from .db import connect, update_local_path, upsert_channel, upsert_tracks_batch
from .models import Track


AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wav", ".webm"}


def normalize_channel(channel: str) -> str:
    channel = channel.strip()
    if channel.startswith("http://") or channel.startswith("https://"):
        parsed = urlparse(channel)
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            raise ValueError(f"URL de Telegram invalida: {channel}")
        return parts[0]
    if channel.startswith("t.me/"):
        return channel.split("/", 1)[1].strip("/")
    return channel.lstrip("@")


def get_client() -> TelegramClient:
    cfg = load_config()
    ensure_session_permissions()
    return TelegramClient(str(SESSION_FILE), cfg.api_id, cfg.api_hash)


async def _scan_channel_impl(
    channel: str,
    limit: int,
    since_message_id: int | None = None,
) -> int:
    channel_name = normalize_channel(channel)
    count = 0
    batch: list[dict[str, object]] = []
    async with get_client() as client:
        entity = await client.get_entity(channel_name)
        title = getattr(entity, "title", channel_name) or channel_name
        username = getattr(entity, "username", None) or channel_name

        with connect() as conn:
            upsert_channel(conn, username, title)
            async for message in client.iter_messages(entity, limit=limit):
                if since_message_id is not None and message.id <= since_message_id:
                    break
                item = message_to_track_dict(message, username, title)
                if item is None:
                    continue
                batch.append(item)
                count += 1
                if len(batch) >= 100:
                    upsert_tracks_batch(conn, batch)
                    batch.clear()
            if batch:
                upsert_tracks_batch(conn, batch)
            conn.commit()
    return count


async def scan_channel(channel: str, limit: int) -> int:
    return await _scan_channel_impl(channel, limit)


async def scan_channel_since(channel: str, since_message_id: int | None, limit: int = 50) -> int:
    return await _scan_channel_impl(channel, limit, since_message_id)


ProgressCallback = Callable[[int, int], None]


async def download_track(track: Track, progress: ProgressCallback | None = None) -> Path:
    cached = Path(track.local_path).expanduser() if track.local_path else None
    if cached and cached.exists():
        if progress:
            size = cached.stat().st_size
            progress(size, size)
        return cached

    async with get_client() as client:
        downloaded = await download_track_with_client(client, track, progress=progress)

    with connect() as conn:
        update_local_path(conn, track.id, str(downloaded))
    return downloaded


async def download_track_with_client(
    client: TelegramClient,
    track: Track,
    progress: ProgressCallback | None = None,
    max_retries: int = 3,
) -> Path:
    cached = Path(track.local_path).expanduser() if track.local_path else None
    if cached and cached.exists():
        if progress:
            size = cached.stat().st_size
            progress(size, size)
        return cached

    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target_dir = AUDIO_CACHE_DIR / safe_name(track.channel)
    target_dir.mkdir(parents=True, exist_ok=True)

    entity = await client.get_entity(track.channel)
    message = await client.get_messages(entity, ids=track.message_id)
    if message is None:
        raise RuntimeError("No encontre el mensaje original en Telegram.")

    extension = Path(track.filename).suffix if track.filename else ".audio"
    filename = f"{track.message_id}-{safe_name(track.display_title)[:80]}{extension}"
    destination = target_dir / filename

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            downloaded = await client.download_media(
                message,
                file=str(destination),
                progress_callback=progress,
            )
            if downloaded is None:
                raise RuntimeError("Telegram no entrego ningun archivo descargable.")
            return Path(downloaded)
        except Exception as exc:
            last_error = exc
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
    raise last_error or RuntimeError("Descarga fallo despues de reintentos.")


async def download_cover(track: Track) -> Path | None:
    existing = sorted(COVER_CACHE_DIR.glob(f"{track.channel}-{track.message_id}-cover*"))
    for path in existing:
        if path.is_file():
            return path

    COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    async with get_client() as client:
        entity = await client.get_entity(track.channel)
        message = await client.get_messages(entity, ids=track.message_id)
        if message is None or not message.media:
            return None
        target = COVER_CACHE_DIR / f"{track.channel}-{track.message_id}-cover"
        downloaded = await client.download_media(message, thumb=-1, file=str(target))
        return Path(downloaded) if downloaded else None


def message_to_track_dict(
    message: Message, channel: str, channel_title: str
) -> dict[str, object] | None:
    document = message.document
    if document is None:
        return None

    mime_type = document.mime_type or ""
    filename = ""
    title = ""
    performer = ""
    duration = None

    for attr in document.attributes:
        if isinstance(attr, DocumentAttributeFilename):
            filename = attr.file_name or ""
        elif isinstance(attr, DocumentAttributeAudio):
            title = attr.title or ""
            performer = attr.performer or ""
            duration = attr.duration

    suffix = Path(filename).suffix.lower()
    is_audio = mime_type.startswith("audio/") or suffix in AUDIO_EXTENSIONS
    if not is_audio:
        return None

    fallback_title = clean_message_text(message.message or "")
    if not title:
        title = Path(filename).stem or fallback_title

    return {
        "channel": channel,
        "channel_title": channel_title,
        "message_id": message.id,
        "title": title or "",
        "performer": performer or "",
        "duration": duration,
        "mime_type": mime_type,
        "filename": filename or "",
        "size": document.size,
        "date": message.date.isoformat() if message.date else "",
        "local_path": None,
    }


def clean_message_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:120]


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._ -]+", "_", value).strip()
    value = re.sub(r"\s+", " ", value)
    return value or "unknown"
