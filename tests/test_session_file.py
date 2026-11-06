from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import tg_music.config as cfg
import tg_music.telegram_client as tc


def test_production_session_file_ends_with_session_extension(tmp_path):
    """Regression test for issue #2: SESSION_FILE must be the file Telethon writes.

    The test fixtures patch SESSION_FILE, so this runs a fresh interpreter
    with a clean HOME to check the real derivation in tg_music/config.py.
    """
    repo_root = Path(__file__).resolve().parents[1]
    env = {k: v for k, v in os.environ.items() if not k.startswith("XDG_")}
    env["HOME"] = str(tmp_path)
    env["PYTHONPATH"] = str(repo_root)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from tg_music.config import DATA_DIR, SESSION_FILE; "
            "assert SESSION_FILE == DATA_DIR / 'session.session', SESSION_FILE; "
            "print(SESSION_FILE)",
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("session.session")


def test_get_client_session_filename_is_exactly_session_file(tmp_path, monkeypatch):
    """Telethon must open exactly SESSION_FILE, not session.session.session.

    SQLiteSession only appends '.session' when the name lacks it, so a
    SESSION_FILE ending in '.session' must be used verbatim. This is the
    check the issue suggested: the session file exists at SESSION_FILE
    after get_client(), and is_authorized_async() can see it.
    """
    session_file = tmp_path / "session.session"
    monkeypatch.setattr(tc, "SESSION_FILE", session_file)
    monkeypatch.setattr(cfg, "SESSION_FILE", session_file)
    config_file = cfg.CONFIG_FILE
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("[telegram]\napi_id = 12345\napi_hash = abcdef1234567890abcdef1234567890\n")
    client = tc.get_client()
    try:
        assert client.session.filename == str(session_file)
        assert session_file.exists()
    finally:
        close = getattr(client.session, "close", None)
        if callable(close):
            close()


def test_ensure_session_permissions_chmods_all_siblings(tmp_path, monkeypatch):
    session_file = cfg.SESSION_FILE
    assert session_file.name == "session.session"
    paths = [session_file] + [Path(str(session_file) + suffix) for suffix in ("-journal", "-wal", "-shm")]
    for path in paths:
        path.write_bytes(b"x")
        path.chmod(0o644)
    cfg.ensure_session_permissions()
    for path in paths:
        assert path.stat().st_mode & 0o777 == 0o600


def test_invalidate_session_removes_all_siblings_but_not_a_stray_session(tmp_path, monkeypatch):
    session_file = tmp_path / "session.session"
    stray = tmp_path / "session"
    monkeypatch.setattr(tc, "SESSION_FILE", session_file)
    siblings = [session_file] + [Path(str(session_file) + suffix) for suffix in ("-journal", "-wal", "-shm")]
    for path in siblings:
        path.write_bytes(b"x")
    stray.write_bytes(b"x")
    tc.invalidate_session()
    assert not session_file.exists()
    assert not Path(str(session_file) + "-journal").exists()
    assert not Path(str(session_file) + "-wal").exists()
    assert not Path(str(session_file) + "-shm").exists()
    assert stray.exists()


def test_doctor_uses_session_file_constant_not_a_hardcoded_path():
    import tg_music.doctor as doctor

    source = Path(doctor.__file__).read_text(encoding="utf-8")
    assert "SESSION_FILE" in source
    assert '"session.session"' not in source
