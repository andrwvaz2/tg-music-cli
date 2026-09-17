from __future__ import annotations

from types import SimpleNamespace

import pytest
from dbus_next import RequestNameReply

from tg_music import mpris as mp
from tg_music.models import Track


def _fake_tui() -> object:
    return SimpleNamespace(
        current_track=None,
        volume=100,
        shuffle_mode=False,
        repeat_mode=False,
        player=SimpleNamespace(
            get_position=lambda: 0.0,
            is_playing=lambda: False,
            is_paused=lambda: False,
        ),
    )


def _track() -> Track:
    return Track(
        id=7,
        channel="ch",
        channel_title="CH",
        message_id=5,
        title="Song",
        performer="Art",
        duration=210,
        mime_type="audio/mpeg",
        filename="song.mp3",
        size=1234,
        date="2024",
        local_path=None,
    )


def test_build_metadata_omits_album() -> None:
    md = mp.build_metadata(_track())
    assert md["mpris:trackid"].value == "/org/mpris/MediaPlayer2/track/7"
    assert md["xesam:title"].value == "Art - Song"
    assert md["xesam:artist"].value == ["Art"]
    assert "xesam:album" not in md
    assert md["mpris:length"].value == 210_000_000
    # artUrl only present when a cover file exists
    assert "mpris:artUrl" not in md


def test_set_position_ignores_stale_track_id() -> None:
    tui = _fake_tui()
    tui.current_track = _track()
    svc = mp.MprisService(tui)
    iface = mp.PlayerInterface(svc)
    iface.SetPosition("/org/mpris/MediaPlayer2/track/999", 50_000_000)
    assert svc._queue.qsize() == 0
    iface.SetPosition("/org/mpris/MediaPlayer2/track/7", 50_000_000)
    assert svc._queue.qsize() == 1
    assert svc._queue.queue[0] == ("seek_to", 50.0)


class _FakeBusExists:
    def __init__(self, bus_type: object) -> None:
        self.bus_type = bus_type

    async def connect(self):
        return self

    async def request_name(self, name: str, flags: object = 0):
        return RequestNameReply.EXISTS

    def export(self, path: str, iface: object) -> None:
        pass

    def release_name(self, name: str) -> None:
        pass

    def disconnect(self) -> None:
        pass


class _FakeBusOwner:
    def __init__(self, bus_type: object) -> None:
        self.bus_type = bus_type

    async def connect(self):
        return self

    async def request_name(self, name: str, flags: object = 0):
        return RequestNameReply.PRIMARY_OWNER

    def export(self, path: str, iface: object) -> None:
        pass

    def release_name(self, name: str) -> None:
        pass

    def disconnect(self) -> None:
        pass


def test_bus_name_already_taken(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mp, "MessageBus", _FakeBusExists)
    svc = mp.MprisService(_fake_tui())
    svc.start()
    svc._thread.join(timeout=2)
    assert svc.available is False
    assert svc.status_message is not None
    assert "otra instancia" in svc.status_message


def test_bus_name_acquired_then_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mp, "MessageBus", _FakeBusOwner)
    svc = mp.MprisService(_fake_tui())
    svc.start()
    svc._thread.join(timeout=2)
    assert svc.available is True
    svc.stop()
    assert not svc._thread.is_alive()


class _Recorder:
    def __init__(self, name: str, calls: list[str]) -> None:
        self.name = name
        self.calls = calls

    def stop(self) -> None:
        self.calls.append(self.name)


def test_shutdown_order_and_idempotency(monkeypatch: pytest.MonkeyPatch) -> None:
    from tg_music.tui import Tui

    class _Screen:
        pass

    tui = Tui(_Screen())
    calls: list[str] = []
    tui.mpris = _Recorder("mpris", calls)
    tui.player = _Recorder("player", calls)
    tui.stop_watch_thread = lambda: calls.append("watch")  # type: ignore[method-assign]

    tui._shutdown()
    assert calls == ["mpris", "player", "watch"]
    # Idempotent: a second call (e.g. from atexit) must not re-run cleanup.
    tui._shutdown()
    assert calls == ["mpris", "player", "watch"]
