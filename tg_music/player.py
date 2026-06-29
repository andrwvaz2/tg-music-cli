from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path


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

    def stop(self) -> None:
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

    def set_volume(self, volume: int) -> None:
        self.volume = max(0, min(150, volume))
        _send_ipc_command(["set_property", "volume", self.volume])
