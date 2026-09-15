from __future__ import annotations

import asyncio
import types
from unittest.mock import MagicMock

import pytest

import tg_music.telegram_client as tc
import tg_music.tui as tui
from tg_music.tui import Tui, _LoginCancelled


def _method(func, obj):
    return types.MethodType(func, obj)


def _make_fake_client(**kwargs):
    """Async context manager faking a TelegramClient for is_authorized_async."""

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def is_user_authorized(self):
            if "authorized" in kwargs:
                return kwargs["authorized"]
            if "exc" in kwargs:
                raise kwargs["exc"]
            return True

    return FakeClient()


def test_is_authorized_async_no_session_file(tmp_path, monkeypatch):
    sf = tmp_path / "session"
    monkeypatch.setattr(tc, "SESSION_FILE", sf)
    monkeypatch.setattr(tc, "get_client", lambda: _make_fake_client())
    sf.unlink(missing_ok=True)
    assert asyncio.run(tc.is_authorized_async()) is False


def test_is_authorized_async_valid_session(tmp_path, monkeypatch):
    sf = tmp_path / "session"
    monkeypatch.setattr(tc, "SESSION_FILE", sf)
    monkeypatch.setattr(tc, "get_client", lambda: _make_fake_client(authorized=True))
    sf.write_text("")
    assert asyncio.run(tc.is_authorized_async()) is True


def test_is_authorized_async_corrupt_session_invalidates(tmp_path, monkeypatch):
    from telethon.errors import AuthKeyUnregisteredError

    sf = tmp_path / "session"
    monkeypatch.setattr(tc, "SESSION_FILE", sf)
    monkeypatch.setattr(
        tc, "get_client", lambda: _make_fake_client(exc=AuthKeyUnregisteredError(None))
    )
    sf.write_text("")
    assert asyncio.run(tc.is_authorized_async()) is False
    assert not sf.exists()


def test_invalid_session_marks_flag_on_scan(monkeypatch):
    from telethon.errors import AuthKeyUnregisteredError

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get_entity(self, *a, **k):
            raise AuthKeyUnregisteredError(None)

        async def iter_messages(self, *a, **k):
            return
            yield  # pragma: no cover

    monkeypatch.setattr(tc, "get_client", lambda: FailingClient())
    tc.reset_session_expired()
    with pytest.raises(AuthKeyUnregisteredError):
        asyncio.run(tc.scan_channel("https://t.me/somechannel", 1))
    assert tc.is_session_expired() is True


def _make_stub():
    class Stub:
        def __init__(self):
            self.screen = MagicMock()
            self.screen.getmaxyx.return_value = (24, 80)
            self.dirty = False
            self.status = ""
            self.color_primary = 0
            self._session_expired_notified = False
            self.start_calls = 0
            self.stop_calls = 0

        def color_attr(self, *a, **k):
            return 0

        def add(self, *a, **k):
            return None

        def input_prompt(self, prompt, max_len=160, mask=False):
            return ""

        def start_watch_thread(self):
            self.start_calls += 1

        def stop_watch_thread(self):
            self.stop_calls += 1

        def set_cursor_visible(self, visible):
            pass

        def pause_input_timeout(self):
            pass

        def restore_input_timeout(self):
            pass

    stub = Stub()
    stub.login_modal = _method(Tui.login_modal, stub)
    stub._do_login = _method(Tui._do_login, stub)
    stub._login_read = _method(Tui._login_read, stub)
    stub._draw_login_box = _method(Tui._draw_login_box, stub)
    return stub


def test_login_modal_success():
    stub = _make_stub()
    stub._login_read = lambda prompt, mask=False: "+123456789"
    captured = {}

    async def fake_do_login(phone):
        captured["phone"] = phone

    stub._do_login = fake_do_login
    stub.login_modal()
    assert "iniciada" in stub.status
    assert captured["phone"] == "+123456789"
    assert stub.stop_calls == 1 and stub.start_calls == 1


def test_login_modal_esc_cancel():
    stub = _make_stub()
    stub._login_read = lambda prompt, mask=False: (_ for _ in ()).throw(_LoginCancelled())
    do_called = []

    async def fake_do_login(phone):
        do_called.append(phone)

    stub._do_login = fake_do_login
    stub.login_modal()
    assert do_called == []
    assert stub.stop_calls == 1 and stub.start_calls == 1


def test_login_modal_invalid_code_retries_then_esc():
    stub = _make_stub()
    from telethon.errors import PhoneCodeInvalidError

    reads = iter(["+123456789"])

    def fake_read(prompt, mask=False):
        try:
            return next(reads)
        except StopIteration:
            raise _LoginCancelled()

    stub._login_read = fake_read

    async def fake_do_login(phone):
        raise PhoneCodeInvalidError(None)

    stub._do_login = fake_do_login
    stub.login_modal()
    assert "Codigo" in stub.status
    assert stub.stop_calls == 1


def test_login_modal_wrong_2fa_then_esc():
    stub = _make_stub()
    from telethon.errors import PasswordHashInvalidError

    reads = iter(["+123456789"])

    def fake_read(prompt, mask=False):
        try:
            return next(reads)
        except StopIteration:
            raise _LoginCancelled()

    stub._login_read = fake_read

    async def fake_do_login(phone):
        raise PasswordHashInvalidError(None)

    stub._do_login = fake_do_login
    stub.login_modal()
    assert "2FA" in stub.status
    assert stub.stop_calls == 1


def test_login_modal_floodwait_aborts():
    stub = _make_stub()
    from telethon.errors import FloodWaitError

    stub._login_read = lambda prompt, mask=False: "+123456789"

    async def fake_do_login(phone):
        raise FloodWaitError(None, 30)

    stub._do_login = fake_do_login
    stub.login_modal()
    assert "Demasiados intentos" in stub.status
    assert stub.stop_calls == 1


def test_is_authorized_gate(monkeypatch):
    stub = _make_stub()
    stub._is_authorized = _method(Tui._is_authorized, stub)

    async def authorized_true():
        return True

    async def authorized_false():
        return False

    monkeypatch.setattr(tui, "is_authorized_async", authorized_true)
    assert stub._is_authorized() is True
    monkeypatch.setattr(tui, "is_authorized_async", authorized_false)
    assert stub._is_authorized() is False


def test_login_read_esc_raises():
    stub = _make_stub()
    stub.screen.getch.return_value = 27
    with pytest.raises(_LoginCancelled):
        stub._login_read("Tel: ")


def test_input_prompt_accepts_digits(monkeypatch):
    import curses

    stub = _make_stub()
    stub.input_prompt = _method(Tui.input_prompt, stub)
    keys = [ord("5"), ord("4"), ord("1"), ord("2"), 10]
    stub.screen.getch = lambda: keys.pop(0) if keys else -1
    stub.screen.getmaxyx.return_value = (24, 80)
    monkeypatch.setattr(curses, "noecho", lambda: None)
    monkeypatch.setattr(curses, "beep", lambda: None)
    result = stub.input_prompt("Telefono: ")
    assert result == "5412"


def test_input_prompt_masked_returns_plain(monkeypatch):
    import curses

    stub = _make_stub()
    stub.input_prompt = _method(Tui.input_prompt, stub)
    keys = [ord("s"), ord("3"), ord("c"), ord("r"), 10]
    stub.screen.getch = lambda: keys.pop(0) if keys else -1
    stub.screen.getmaxyx.return_value = (24, 80)
    monkeypatch.setattr(curses, "noecho", lambda: None)
    monkeypatch.setattr(curses, "beep", lambda: None)
    result = stub.input_prompt("Contrasena: ", mask=True)
    assert result == "s3cr"
