from __future__ import annotations

import shutil
from unittest.mock import patch

from tg_music.doctor import run_doctor
from tg_music.player import ensure_mpv, get_mpv_install_hint
import pytest


def test_doctor_runs_ok():
    code = run_doctor()
    assert code in (0, 1)


def test_doctor_missing_mpv(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda cmd: None if cmd == "mpv" else "/bin/" + cmd)
    code = run_doctor()
    assert code == 1


def test_ensure_mpv_raises_helpful_error(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    with pytest.raises(RuntimeError) as exc_info:
        ensure_mpv()
    assert "tg-music doctor" in str(exc_info.value)


def test_get_mpv_install_hint():
    with patch("sys.platform", "win32"):
        assert "winget" in get_mpv_install_hint()
    with patch("sys.platform", "darwin"):
        assert "brew" in get_mpv_install_hint()
    with patch("sys.platform", "linux"):
        assert "apt" in get_mpv_install_hint()
