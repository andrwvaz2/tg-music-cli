from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
from pathlib import Path

from .mpv_ipc import MpvIpcClient


def ensure_mpv() -> None:
    if shutil.which("mpv") is None:
        raise RuntimeError("No encuentro mpv en PATH. Instala mpv para reproducir audio.")


def play_file(path: str | Path, volume: int = 100) -> None:
    ensure_mpv()
    subprocess.run(["mpv", "--no-video", f"--volume={volume}", str(path)], check=False)


def _ipc_path() -> str:
    return os.path.join(tempfile.gettempdir(), "tg-music-mpv.sock")


def _send_ipc_command(command: list) -> None:
    sock_path = _ipc_path()
    if not os.path.exists(sock_path):
        return
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(sock_path)
        payload = json.dumps({"command": command}) + "\n"
        s.sendall(payload.encode())
        s.close()
    except Exception:
        pass  # IPC socket error; player continues running


class BackgroundPlayer:
    def __init__(self, volume: int = 100, crossfade: int = 0) -> None:
        self.process: subprocess.Popen | None = None
        self.volume = max(0, min(150, volume))
        self.crossfade = max(0, min(10, crossfade))
        self._state_lock = threading.Lock()
        self.position = 0.0
        self.paused = False
        self.duration: float | None = None
        self._ipc = MpvIpcClient(_ipc_path(), self)

    def play(self, path: str | Path) -> None:
        ensure_mpv()
        self.stop()
        sock_path = _ipc_path()
        if os.path.exists(sock_path):
            os.remove(sock_path)
        cmd = [
            "mpv",
            "--no-video",
            "--no-terminal",
            "--really-quiet",
            "--keep-open=no",
            f"--volume={self.volume}",
            f"--input-ipc-server={sock_path}",
        ]
        if self.crossfade > 0:
            cmd.extend([f"--af=lavfi=[afade=t=in:st=0:d={self.crossfade}]"])
        cmd.append(str(path))
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with self._state_lock:
            self.position = 0.0
            self.paused = False
        self._ipc.start()

    def stop(self) -> None:
        self._ipc.stop()
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        self.process = None
        sock_path = _ipc_path()
        if os.path.exists(sock_path):
            try:
                os.remove(sock_path)
            except OSError:
                pass

    def is_playing(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def returncode(self) -> int | None:
        if self.process is None:
            return None
        return self.process.poll()

    def get_position(self) -> float:
        with self._state_lock:
            return self.position

    def is_paused(self) -> bool:
        with self._state_lock:
            return self.paused

    def get_duration(self) -> float | None:
        with self._state_lock:
            return self.duration

    def _set_position(self, value: float) -> None:
        with self._state_lock:
            self.position = value

    def _set_paused(self, value: bool) -> None:
        with self._state_lock:
            self.paused = value

    def _set_duration(self, value: float | None) -> None:
        with self._state_lock:
            self.duration = value

    def pause(self) -> None:
        _send_ipc_command(["set_property", "pause", True])

    def resume(self) -> None:
        _send_ipc_command(["set_property", "pause", False])

    def toggle_pause(self) -> None:
        _send_ipc_command(["cycle", "pause"])

    def seek(self, delta_seconds: float) -> None:
        _send_ipc_command(["seek", delta_seconds])

    def seek_to(self, position_seconds: float) -> None:
        _send_ipc_command(["set_property", "time-pos", max(0.0, position_seconds)])

    def set_volume(self, volume: int) -> None:
        self.volume = max(0, min(150, volume))
        _send_ipc_command(["set_property", "volume", self.volume])
