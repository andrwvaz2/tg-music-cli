from __future__ import annotations

import sqlite3
import time
import threading
from pathlib import Path

from .config import AUDIO_CACHE_DIR, DB_FILE, ensure_dirs
from .models import Channel, Track


SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel TEXT NOT NULL,
  channel_title TEXT NOT NULL,
  message_id INTEGER NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  performer TEXT NOT NULL DEFAULT '',
  duration INTEGER,
  mime_type TEXT NOT NULL DEFAULT '',
  filename TEXT NOT NULL DEFAULT '',
  size INTEGER,
  date TEXT NOT NULL DEFAULT '',
  local_path TEXT,
  ignored INTEGER NOT NULL DEFAULT 0,
  play_count INTEGER NOT NULL DEFAULT 0,
  last_played_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(channel, message_id)
);

CREATE INDEX IF NOT EXISTS idx_tracks_channel ON tracks(channel);
CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks(title, performer, filename);
CREATE INDEX IF NOT EXISTS idx_tracks_local_path ON tracks(local_path);

CREATE TABLE IF NOT EXISTS channels (
  channel TEXT PRIMARY KEY,
  title TEXT NOT NULL DEFAULT '',
  last_scan_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS favorites (
  track_id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(track_id) REFERENCES tracks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tags (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS track_tags (
  track_id INTEGER NOT NULL,
  tag_id INTEGER NOT NULL,
  PRIMARY KEY(track_id, tag_id),
  FOREIGN KEY(track_id) REFERENCES tracks(id) ON DELETE CASCADE,
  FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS playlists (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS playlist_tracks (
  playlist_id INTEGER NOT NULL,
  track_id INTEGER NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(playlist_id, track_id),
  FOREIGN KEY(playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
  FOREIGN KEY(track_id) REFERENCES tracks(id) ON DELETE CASCADE
);
"""

DB_WRITE_LOCK = threading.Lock()


def connect(db_file: Path = DB_FILE) -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(
        db_file,
        timeout=60,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    ensure_migrations(conn)
    return conn


def ensure_migrations(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(tracks)").fetchall()}
    if "ignored" not in columns:
        with DB_WRITE_LOCK:
            conn.execute("ALTER TABLE tracks ADD COLUMN ignored INTEGER NOT NULL DEFAULT 0")
            conn.commit()
    if "play_count" not in columns:
        with DB_WRITE_LOCK:
            conn.execute("ALTER TABLE tracks ADD COLUMN play_count INTEGER NOT NULL DEFAULT 0")
            conn.commit()
    if "last_played_at" not in columns:
        with DB_WRITE_LOCK:
            conn.execute("ALTER TABLE tracks ADD COLUMN last_played_at TEXT")
            conn.commit()

    channels_count = conn.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
    if channels_count:
        return

    tracks_count = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
    if not tracks_count:
        return

    with DB_WRITE_LOCK:
        conn.execute(
            """
            INSERT OR IGNORE INTO channels (channel, title, last_scan_at)
            SELECT channel, MAX(channel_title), MAX(updated_at)
            FROM tracks
            GROUP BY channel
            """
        )
        conn.commit()


def upsert_tracks_batch(conn: sqlite3.Connection, items: list[dict[str, object]]) -> None:
    if not items:
        return
    with DB_WRITE_LOCK:
        conn.executemany(
            """
            INSERT INTO tracks (
              channel, channel_title, message_id, title, performer, duration,
              mime_type, filename, size, date, local_path
            ) VALUES (
              :channel, :channel_title, :message_id, :title, :performer, :duration,
              :mime_type, :filename, :size, :date, :local_path
            )
            ON CONFLICT(channel, message_id) DO UPDATE SET
              channel_title=excluded.channel_title,
              title=excluded.title,
              performer=excluded.performer,
              duration=excluded.duration,
              mime_type=excluded.mime_type,
              filename=excluded.filename,
              size=excluded.size,
              date=excluded.date,
              updated_at=CURRENT_TIMESTAMP
            """,
            items,
        )
        conn.commit()


def upsert_channel(conn: sqlite3.Connection, channel: str, title: str) -> None:
    with DB_WRITE_LOCK:
        conn.execute(
            """
            INSERT INTO channels (channel, title, last_scan_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(channel) DO UPDATE SET
              title=excluded.title,
              last_scan_at=CURRENT_TIMESTAMP,
              updated_at=CURRENT_TIMESTAMP
            """,
            (channel, title),
        )
        conn.commit()


def list_channels(conn: sqlite3.Connection) -> list[Channel]:
    rows = conn.execute(
        """
        SELECT channel, title, last_scan_at, created_at
        FROM channels
        ORDER BY title COLLATE NOCASE, channel COLLATE NOCASE
        """
    ).fetchall()
    return [
        Channel(
            channel=row["channel"],
            title=row["title"],
            last_scan_at=row["last_scan_at"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def remove_channel(conn: sqlite3.Connection, channel: str) -> int:
    with DB_WRITE_LOCK:
        cursor = conn.execute("DELETE FROM channels WHERE channel = ?", (channel,))
        conn.commit()
        return cursor.rowcount


def update_local_path(conn: sqlite3.Connection, track_id: int, local_path: str) -> None:
    for attempt in range(5):
        try:
            with DB_WRITE_LOCK:
                conn.execute(
                    "UPDATE tracks SET local_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (local_path, track_id),
                )
                conn.commit()
            return
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == 4:
                raise
            time.sleep(0.25 * (attempt + 1))


def record_play(conn: sqlite3.Connection, track_id: int) -> None:
    with DB_WRITE_LOCK:
        conn.execute(
            """
            UPDATE tracks
            SET play_count = play_count + 1,
                last_played_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (track_id,),
        )
        conn.commit()


def get_track(conn: sqlite3.Connection, track_id: int) -> Track | None:
    row = conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
    return _track_from_row(row) if row else None


def set_ignored(conn: sqlite3.Connection, track_id: int, ignored: bool) -> None:
    with DB_WRITE_LOCK:
        conn.execute(
            """
            UPDATE tracks
            SET ignored = ?, local_path = CASE WHEN ? THEN NULL ELSE local_path END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (1 if ignored else 0, 1 if ignored else 0, track_id),
        )
        conn.commit()


def latest_for_channel(conn: sqlite3.Connection, channel: str) -> Track | None:
    row = conn.execute(
        """
        SELECT * FROM tracks
        WHERE channel = ?
          AND ignored = 0
        ORDER BY date DESC, message_id DESC
        LIMIT 1
        """,
        (channel,),
    ).fetchone()
    return _track_from_row(row) if row else None


def latest_message_id_for_channel(conn: sqlite3.Connection, channel: str) -> int | None:
    row = conn.execute(
        """
        SELECT MAX(message_id) AS max_message_id
        FROM tracks
        WHERE channel = ?
          AND ignored = 0
        """,
        (channel,),
    ).fetchone()
    if row is None:
        return None
    value = row["max_message_id"]
    return int(value) if value is not None else None


def list_tracks(
    conn: sqlite3.Connection,
    limit: int = 50,
    query: str | None = None,
    include_ignored: bool = False,
    channel: str | None = None,
    favorites_only: bool = False,
    tag: str | None = None,
) -> list[Track]:
    clauses = []
    params: list[object] = []
    if not include_ignored:
        clauses.append("t.ignored = 0")
    if channel:
        clauses.append("t.channel = ?")
        params.append(channel)
    if favorites_only:
        clauses.append("t.id IN (SELECT track_id FROM favorites)")
    if tag:
        clauses.append("t.id IN (SELECT tt.track_id FROM track_tags tt JOIN tags tg ON tt.tag_id = tg.id WHERE tg.name = ?)")
        params.append(tag)
    if query:
        query_clauses = []
        for token in query.split():
            like = f"%{token}%"
            query_clauses.append(
                "(t.title LIKE ? OR t.performer LIKE ? OR t.filename LIKE ? OR t.channel_title LIKE ?)"
            )
            params.extend((like, like, like, like))
        clauses.append("(" + " AND ".join(query_clauses) + ")")
    where = " AND ".join(clauses) if clauses else "1=1"
    params.append(limit)
    rows = conn.execute(
        """
            SELECT t.* FROM tracks t
            WHERE """ + where + """
            ORDER BY t.date DESC, t.message_id DESC
            LIMIT ?
        """,
        params,
    ).fetchall()
    return [_track_from_row(row) for row in rows]


def list_uncached_tracks(
    conn: sqlite3.Connection,
    limit: int = 50,
    channel: str | None = None,
) -> list[Track]:
    params: list[object] = []
    where = "ignored = 0 AND (local_path IS NULL OR local_path = '')"
    if channel:
        where += " AND channel = ?"
        params.append(channel)
    params.append(limit)
    rows = conn.execute(
        f"""
        SELECT * FROM tracks
        WHERE {where}
        ORDER BY date DESC, message_id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [_track_from_row(row) for row in rows]


def list_ignored_tracks(conn: sqlite3.Connection, limit: int = 50) -> list[Track]:
    rows = conn.execute(
        """
        SELECT * FROM tracks
        WHERE ignored = 1
        ORDER BY updated_at DESC, date DESC, message_id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_track_from_row(row) for row in rows]


def list_recently_played(conn: sqlite3.Connection, limit: int = 20) -> list[Track]:
    rows = conn.execute(
        """
        SELECT * FROM tracks
        WHERE last_played_at IS NOT NULL AND ignored = 0
        ORDER BY last_played_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_track_from_row(row) for row in rows]


def list_top_played(conn: sqlite3.Connection, limit: int = 20) -> list[Track]:
    rows = conn.execute(
        """
        SELECT * FROM tracks
        WHERE play_count > 0 AND ignored = 0
        ORDER BY play_count DESC, title ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_track_from_row(row) for row in rows]


def list_random_tracks(conn: sqlite3.Connection, limit: int = 1) -> list[Track]:
    rows = conn.execute(
        """
        SELECT * FROM tracks
        WHERE ignored = 0
        ORDER BY RANDOM()
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_track_from_row(row) for row in rows]


def toggle_favorite(conn: sqlite3.Connection, track_id: int) -> bool:
    existing = conn.execute(
        "SELECT 1 FROM favorites WHERE track_id = ?", (track_id,)
    ).fetchone()
    with DB_WRITE_LOCK:
        if existing:
            conn.execute("DELETE FROM favorites WHERE track_id = ?", (track_id,))
            conn.commit()
            return False
        else:
            conn.execute("INSERT OR IGNORE INTO favorites (track_id) VALUES (?)", (track_id,))
            conn.commit()
            return True


def is_favorite(conn: sqlite3.Connection, track_id: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM favorites WHERE track_id = ?", (track_id,)
    ).fetchone() is not None


def get_all_favorite_ids(conn: sqlite3.Connection) -> set[int]:
    rows = conn.execute("SELECT track_id FROM favorites").fetchall()
    return {row["track_id"] for row in rows}


def add_tag(conn: sqlite3.Connection, name: str) -> int:
    with DB_WRITE_LOCK:
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name.strip(),))
        conn.commit()
        row = conn.execute("SELECT id FROM tags WHERE name = ?", (name.strip(),)).fetchone()
        return row["id"]


def remove_tag(conn: sqlite3.Connection, name: str) -> None:
    with DB_WRITE_LOCK:
        conn.execute("DELETE FROM tags WHERE name = ?", (name.strip(),))
        conn.commit()


def tag_track(conn: sqlite3.Connection, track_id: int, tag_name: str) -> None:
    tag_id = add_tag(conn, tag_name)
    with DB_WRITE_LOCK:
        conn.execute(
            "INSERT OR IGNORE INTO track_tags (track_id, tag_id) VALUES (?, ?)",
            (track_id, tag_id),
        )
        conn.commit()


def untag_track(conn: sqlite3.Connection, track_id: int, tag_name: str) -> None:
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name.strip(),)).fetchone()
    if row:
        with DB_WRITE_LOCK:
            conn.execute(
                "DELETE FROM track_tags WHERE track_id = ? AND tag_id = ?",
                (track_id, row["id"]),
            )
            conn.commit()


def get_track_tags(conn: sqlite3.Connection, track_id: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT tg.name FROM track_tags tt
        JOIN tags tg ON tt.tag_id = tg.id
        WHERE tt.track_id = ?
        ORDER BY tg.name
        """,
        (track_id,),
    ).fetchall()
    return [row["name"] for row in rows]


def create_playlist(conn: sqlite3.Connection, name: str) -> int:
    with DB_WRITE_LOCK:
        conn.execute("INSERT OR IGNORE INTO playlists (name) VALUES (?)", (name.strip(),))
        conn.commit()
        row = conn.execute("SELECT id FROM playlists WHERE name = ?", (name.strip(),)).fetchone()
        return row["id"]


def delete_playlist(conn: sqlite3.Connection, playlist_id: int) -> None:
    with DB_WRITE_LOCK:
        conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        conn.commit()


def list_playlists(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT id, name, created_at FROM playlists ORDER BY name").fetchall()
    result = []
    for row in rows:
        count = conn.execute(
            "SELECT COUNT(*) as cnt FROM playlist_tracks WHERE playlist_id = ?", (row["id"],)
        ).fetchone()["cnt"]
        result.append({"id": row["id"], "name": row["name"], "count": count, "created_at": row["created_at"]})
    return result


def add_to_playlist(conn: sqlite3.Connection, playlist_id: int, track_id: int) -> None:
    max_pos = conn.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 as next_pos FROM playlist_tracks WHERE playlist_id = ?",
        (playlist_id,),
    ).fetchone()["next_pos"]
    with DB_WRITE_LOCK:
        conn.execute(
            "INSERT OR IGNORE INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
            (playlist_id, track_id, max_pos),
        )
        conn.commit()


def remove_from_playlist(conn: sqlite3.Connection, playlist_id: int, track_id: int) -> None:
    with DB_WRITE_LOCK:
        conn.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
            (playlist_id, track_id),
        )
        conn.commit()


def get_playlist_tracks(conn: sqlite3.Connection, playlist_id: int) -> list:
    rows = conn.execute(
        """
        SELECT t.* FROM tracks t
        JOIN playlist_tracks pt ON t.id = pt.track_id
        WHERE pt.playlist_id = ?
        ORDER BY pt.position
        """,
        (playlist_id,),
    ).fetchall()
    return [
        Track(
            id=row["id"],
            message_id=row["message_id"],
            channel=row["channel"],
            channel_title=row["channel_title"],
            performer=row["performer"],
            title=row["title"],
            filename=row["filename"],
            duration=row["duration"],
            date=row["date"],
            local_path=row["local_path"],
            ignored=row["ignored"],
            play_count=row["play_count"] if "play_count" in row.keys() else 0,
        )
        for row in rows
    ]


def rename_playlist(conn: sqlite3.Connection, playlist_id: int, new_name: str) -> None:
    with DB_WRITE_LOCK:
        conn.execute("UPDATE playlists SET name = ? WHERE id = ?", (new_name.strip(), playlist_id))
        conn.commit()


def get_playlist_by_name(conn: sqlite3.Connection, name: str) -> dict | None:
    row = conn.execute("SELECT id, name FROM playlists WHERE name = ?", (name.strip(),)).fetchone()
    if row:
        return {"id": row["id"], "name": row["name"]}
    return None


def list_all_tags(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT name FROM tags ORDER BY name").fetchall()
    return [row["name"] for row in rows]


def _track_from_row(row: sqlite3.Row) -> Track:
    local_path = row["local_path"]
    if local_path:
        path = Path(local_path)
        if not path.exists():
            if len(path.parts) >= 2:
                alternative_path = AUDIO_CACHE_DIR / path.parts[-2] / path.parts[-1]
            else:
                alternative_path = AUDIO_CACHE_DIR / path.name
            if alternative_path.exists():
                local_path = str(alternative_path)
            else:
                local_path = None

    return Track(
        id=row["id"],
        channel=row["channel"],
        channel_title=row["channel_title"],
        message_id=row["message_id"],
        title=row["title"],
        performer=row["performer"],
        duration=row["duration"],
        mime_type=row["mime_type"],
        filename=row["filename"],
        size=row["size"],
        date=row["date"],
        local_path=local_path,
        ignored=bool(row["ignored"]),
        play_count=row["play_count"] if "play_count" in row.keys() else 0,
        last_played_at=row["last_played_at"] if "last_played_at" in row.keys() else None,
    )
