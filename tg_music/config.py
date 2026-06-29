from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, field
from pathlib import Path


APP_NAME = "tg-music"


def _xdg_path(env_name: str, fallback: Path) -> Path:
    raw = os.environ.get(env_name)
    return Path(raw).expanduser() if raw else fallback


CONFIG_DIR = _xdg_path("XDG_CONFIG_HOME", Path.home() / ".config") / APP_NAME
CONFIG_FILE = CONFIG_DIR / "config.ini"


def _get_cache_dir() -> Path:
    default_cache = _xdg_path("XDG_CACHE_HOME", Path.home() / ".cache") / APP_NAME
    if CONFIG_FILE.exists():
        try:
            parser = configparser.ConfigParser()
            parser.read(CONFIG_FILE)
            if parser.has_section("settings") and parser.has_option("settings", "cache_dir"):
                val = parser.get("settings", "cache_dir").strip()
                if val:
                    return Path(val).expanduser()
            if parser.has_section("telegram") and parser.has_option("telegram", "cache_dir"):
                val = parser.get("telegram", "cache_dir").strip()
                if val:
                    return Path(val).expanduser()
        except Exception:
            pass  # Config unreadable; fall back to default cache path
    return default_cache


DATA_DIR = _xdg_path("XDG_DATA_HOME", Path.home() / ".local" / "share") / APP_NAME
CACHE_DIR = _get_cache_dir()
DB_FILE = DATA_DIR / "library.sqlite3"
SESSION_FILE = DATA_DIR / "session"
AUDIO_CACHE_DIR = CACHE_DIR / "audio"
COVER_CACHE_DIR = CACHE_DIR / "covers"


@dataclass(frozen=True)
class TelegramConfig:
    api_id: int
    api_hash: str


@dataclass
class AppSettings:
    volume: int = 100
    crossfade: int = 0
    theme: str = "auto"
    keybinds: dict[str, str] = field(default_factory=dict)


DEFAULT_KEYBINDS = {
    "quit": "q",
    "help": "?",
    "up": "k",
    "down": "j",
    "enter": "enter",
    "expand": "space",
    "collapse": "backspace",
    "enqueue": "e",
    "next": "n",
    "stop": "s",
    "ignore": "x",
    "search": "/",
    "refresh": "r",
    "channels": "c",
    "add_channel": "a",
    "scan_more": "u",
    "download_missing": "m",
    "check_new": "w",
    "toggle_watch": "W",
    "queue_left": "[",
    "queue_right": "]",
    "favorite": "f",
    "repeat": "R",
    "shuffle": "S",
    "volume_up": "+",
    "volume_down": "-",
    "lyrics": "L",
    "mini_view": "M",
}


def ensure_dirs() -> None:
    for path in (DATA_DIR, CACHE_DIR, CONFIG_DIR, AUDIO_CACHE_DIR, COVER_CACHE_DIR):
        if path.is_symlink() and not path.exists():
            path.unlink()  # Remove broken symlink
        path.mkdir(parents=True, exist_ok=True)


def load_config() -> TelegramConfig:
    parser = configparser.ConfigParser()
    parser.read(CONFIG_FILE)
    if not parser.has_section("telegram"):
        raise RuntimeError(f"Telegram is not configured. Run: tg-music init\nFile: {CONFIG_FILE}")

    api_id = parser.get("telegram", "api_id", fallback="").strip()
    api_hash = parser.get("telegram", "api_hash", fallback="").strip()
    if not api_id or not api_hash:
        raise RuntimeError(f"Incomplete config. Run: tg-music init\nFile: {CONFIG_FILE}")

    return TelegramConfig(api_id=int(api_id), api_hash=api_hash)


def load_settings() -> AppSettings:
    settings = AppSettings()
    if not CONFIG_FILE.exists():
        return settings
    parser = configparser.ConfigParser()
    parser.read(CONFIG_FILE)
    if parser.has_section("settings"):
        settings.volume = parser.getint("settings", "volume", fallback=100)
        settings.crossfade = parser.getint("settings", "crossfade", fallback=0)
        settings.theme = parser.get("settings", "theme", fallback="auto")
    if parser.has_section("keybinds"):
        for key, val in parser.items("keybinds"):
            settings.keybinds[key] = val
    return settings


def save_settings(settings: AppSettings) -> None:
    ensure_dirs()
    parser = configparser.ConfigParser()
    if CONFIG_FILE.exists():
        parser.read(CONFIG_FILE)
    if not parser.has_section("settings"):
        parser["settings"] = {}
    parser["settings"]["volume"] = str(settings.volume)
    parser["settings"]["crossfade"] = str(settings.crossfade)
    parser["settings"]["theme"] = settings.theme
    if not parser.has_section("keybinds"):
        parser["keybinds"] = {}
    for key, val in settings.keybinds.items():
        parser["keybinds"][key] = val
    with CONFIG_FILE.open("w", encoding="utf-8") as fh:
        parser.write(fh)
    CONFIG_FILE.chmod(0o600)


def ensure_session_permissions() -> None:
    if SESSION_FILE.exists():
        SESSION_FILE.chmod(0o600)
    session_journal = Path(str(SESSION_FILE) + "-journal")
    if session_journal.exists():
        session_journal.chmod(0o600)


def save_config(api_id: str, api_hash: str) -> None:
    ensure_dirs()
    parser = configparser.ConfigParser()
    parser["telegram"] = {"api_id": api_id.strip(), "api_hash": api_hash.strip()}
    with CONFIG_FILE.open("w", encoding="utf-8") as fh:
        parser.write(fh)
    CONFIG_FILE.chmod(0o600)
