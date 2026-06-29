from __future__ import annotations

import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def _isolate_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect all config/data/cache paths to tmp_path so tests never touch real files."""
    import tg_music.config as cfg
    import tg_music.db as db

    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    cache_dir = tmp_path / "cache"

    config_dir.mkdir()
    data_dir.mkdir()
    cache_dir.mkdir()

    # Patch config module
    monkeypatch.setattr(cfg, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(cfg, "CONFIG_FILE", config_dir / "config.ini")
    monkeypatch.setattr(cfg, "DATA_DIR", data_dir)
    monkeypatch.setattr(cfg, "DB_FILE", data_dir / "library.sqlite3")
    monkeypatch.setattr(cfg, "SESSION_FILE", data_dir / "session")
    monkeypatch.setattr(cfg, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(cfg, "AUDIO_CACHE_DIR", cache_dir / "audio")
    monkeypatch.setattr(cfg, "COVER_CACHE_DIR", cache_dir / "covers")

    # Patch db module (it has its own binding of DB_FILE)
    monkeypatch.setattr(db, "DB_FILE", data_dir / "library.sqlite3")
