from __future__ import annotations

import json
import os
import socket
import threading
import time


class MpvIpcClient:
    """Lee el socket IPC de mpv (newline-delimited JSON) para mantener el
    estado de reproducción (posición, pausa, duración) en tiempo real.

    Vive en su propio daemon thread y escribe en el ``BackgroundPlayer`` bajo
    un lock, de forma que el hilo main del TUI y el servicio MPRIS pueden
    leer ``position``/``paused``/``duration`` sin condición de carrera.
    """

    def __init__(self, socket_path: str, player: "object") -> None:
        self._socket_path = socket_path
        self._player = player
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

    def _run(self) -> None:
        sock = self._connect_with_retry()
        if sock is None:
            return
        try:
            self._send_observations(sock)
            self._read_loop(sock)
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def _connect_with_retry(self) -> socket.socket | None:
        if not hasattr(socket, "AF_UNIX"):
            return None
        deadline = time.time() + 2.0
        while not self._stop.is_set():
            if os.path.exists(self._socket_path):
                try:
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.settimeout(0.5)
                    s.connect(self._socket_path)
                    return s
                except OSError:
                    pass
            if time.time() > deadline:
                return None
            time.sleep(0.1)
        return None

    def _send_observations(self, sock: socket.socket) -> None:
        for obs_id, prop in ((1, "time-pos"), (2, "pause"), (3, "duration")):
            cmd = {"command": ["observe_property", obs_id, prop]}
            try:
                sock.sendall((json.dumps(cmd) + "\n").encode())
            except OSError:
                return

    def _read_loop(self, sock: socket.socket) -> None:
        sock.settimeout(0.5)
        buffer = b""
        while not self._stop.is_set():
            try:
                data = sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data:
                break
            buffer += data
            # mpv manda un objeto JSON por línea; lo incompleto se queda en buffer.
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                self._handle_line(line)

    def _handle_line(self, raw: bytes) -> None:
        raw = raw.strip()
        if not raw:
            return
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return
        # Respuestas a comandos (si alguna vez usáramos request_id) se ignoran.
        if "request_id" in msg:
            return
        if msg.get("event") != "property-change":
            return
        name = msg.get("name")
        value = msg.get("data")
        if name == "time-pos":
            self._player._set_position(float(value) if isinstance(value, (int, float)) else 0.0)
        elif name == "pause":
            self._player._set_paused(bool(value))
        elif name == "duration":
            self._player._set_duration(float(value) if isinstance(value, (int, float)) else None)
