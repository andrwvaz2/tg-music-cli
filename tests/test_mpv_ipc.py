from __future__ import annotations

import socket
import threading
import time

from tg_music.mpv_ipc import MpvIpcClient


class _FakePlayer:
    def __init__(self) -> None:
        self._state_lock = threading.Lock()
        self.position = 0.0
        self.paused = False
        self.duration = None

    def _set_position(self, value: float) -> None:
        with self._state_lock:
            self.position = value

    def _set_paused(self, value: bool) -> None:
        with self._state_lock:
            self.paused = value

    def _set_duration(self, value: float | None) -> None:
        with self._state_lock:
            self.duration = value

    def get_position(self) -> float:
        with self._state_lock:
            return self.position


def _wait(player: _FakePlayer, pred) -> bool:
    for _ in range(100):
        with player._state_lock:
            if pred():
                return True
        time.sleep(0.02)
    return False


def test_property_change_events_parsed() -> None:
    server, client = socket.socketpair()
    client.settimeout(0.5)
    player = _FakePlayer()
    client_held = client

    client_thread_sock = client_held
    c = MpvIpcClient("fake-path", player)
    c._connect_with_retry = lambda: client_thread_sock  # type: ignore[assignment]
    c.start()
    try:
        server.sendall(b'{"event":"property-change","name":"time-pos","data":42.0}\n')
        server.sendall(b'{"event":"property-change","name":"pause","data":true}\n')
        server.sendall(b'{"event":"property-change","name":"duration","data":200.0}\n')
        assert _wait(player, lambda: player.position == 42.0 and player.paused and player.duration == 200.0)
        # A command response (request_id) must be ignored, not treated as state.
        server.sendall(b'{"request_id":1,"error":"success"}\n')
        server.sendall(b'{"event":"end-file","reason":"eof"}\n')
        time.sleep(0.1)
        with player._state_lock:
            assert player.position == 42.0
    finally:
        c.stop()
        server.close()
        client.close()


def test_fragmented_message_across_recv() -> None:
    server, client = socket.socketpair()
    client.settimeout(0.5)
    player = _FakePlayer()
    client_held = client

    c = MpvIpcClient("fake-path", player)
    c._connect_with_retry = lambda: client_held  # type: ignore[assignment]
    c.start()
    try:
        # Split a single JSON object across two recv() calls (no newline yet).
        server.sendall(b'{"event":"property-change","name":"time-pos","data":')
        time.sleep(0.1)
        with player._state_lock:
            assert player.position == 0.0, "must not parse a partial line"
        server.sendall(b'7.5}\n')
        assert _wait(player, lambda: player.position == 7.5)
    finally:
        c.stop()
        server.close()
        client.close()


def test_reader_thread_joins_on_stop_without_socket() -> None:
    player = _FakePlayer()
    c = MpvIpcClient("/nonexistent/path.sock", player)
    c.start()
    c.stop()
    assert c._thread is not None
    assert not c._thread.is_alive()
