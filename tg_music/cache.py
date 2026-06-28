from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .db import connect, update_local_path
from .telegram_client import ProgressCallback, download_track_with_client, get_client
from .models import Track


@dataclass(frozen=True)
class CacheResult:
    track: Track
    path: Path | None
    error: Exception | None


ProgressFactory = Callable[[Track], ProgressCallback | None]
ResultCallback = Callable[[CacheResult, int, int], None]


async def cache_tracks_async(
    tracks: list[Track],
    workers: int = 1,
    progress_factory: ProgressFactory | None = None,
    result_callback: ResultCallback | None = None,
) -> list[CacheResult]:
    workers = max(1, min(workers, 3))
    queue: asyncio.Queue[tuple[int, Track]] = asyncio.Queue()
    for index, track in enumerate(tracks):
        queue.put_nowait((index, track))

    results: list[CacheResult | None] = [None] * len(tracks)
    completed = 0
    lock = asyncio.Lock()

    async def worker(client) -> None:
        nonlocal completed
        while True:
            try:
                index, track = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            progress = progress_factory(track) if progress_factory else None
            try:
                path = await download_track_with_client(client, track, progress=progress)
                with connect() as conn:
                    update_local_path(conn, track.id, str(path))
                result = CacheResult(track=track, path=path, error=None)
            except Exception as exc:
                result = CacheResult(track=track, path=None, error=exc)
            results[index] = result
            async with lock:
                completed += 1
                if result_callback:
                    result_callback(result, completed, len(tracks))
            queue.task_done()

    async with get_client() as client:
        await asyncio.gather(*(worker(client) for _ in range(workers)))
    return [result for result in results if result is not None]
