from __future__ import annotations

import importlib.metadata

__version__ = "0.1.0"


def get_version() -> str:
    try:
        return "v" + importlib.metadata.version("tg-music-cli")
    except importlib.metadata.PackageNotFoundError:
        return "dev"
