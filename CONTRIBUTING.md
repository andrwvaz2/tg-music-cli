# Contributing to tg-music-cli

Thanks for your interest in contributing! Here's how to get started.

## Setup

```bash
git clone https://github.com/andrwvaz2/tg-music-cli.git
cd tg-music-cli
uv sync --all-extras
```

This installs the project and all dev dependencies (pytest).

## Running tests

```bash
uv run pytest tests/ -v
```

All tests should pass before submitting a PR.

## Code style

- Python 3.11+ (uses `from __future__ import annotations`)
- Linter: `uv run ruff check tg_music/` (must pass before PR)
- Use type hints on function signatures
- Keep functions focused and testable (pure logic in `tests/test_pure.py`)

## Opening a PR

1. Create a branch: `git checkout -b feat/my-feature` or `fix/my-fix`
2. Make your changes
3. Run tests: `uv run pytest tests/ -v`
4. Commit with a descriptive message: `feat: add playlist shuffle` or `fix: handle missing track`
5. Push and open a PR against `main`

## Project structure

```
tg_music/
├── cli.py              # CLI commands (argparse)
├── config.py           # AppSettings, load/save
├── db.py               # SQLite database layer
├── models.py           # Track, Channel dataclasses
├── player.py           # BackgroundPlayer (mpv IPC)
├── telegram_client.py  # Telethon client
├── cover.py            # Cover art extraction
├── lyrics.py           # Lyrics fetching
├── local.py            # Local folder playback
├── tui.py              # TUI main class
├── tui_player.py       # PlayerMixin (playback logic)
├── tui_render.py       # RenderMixin (compositor)
├── render_base.py      # Helpers, colors, keybinds
├── render_panels.py    # Tracks, channels, detail panels
├── render_split.py     # 3-panel split view
├── render_cover.py     # Cover art rendering
└── render_help.py      # Help overlay, mini view
```

## Reporting bugs

Open an issue with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Your OS, Python version, and terminal emulator
