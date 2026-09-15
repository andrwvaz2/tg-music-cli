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
├── cache.py            # Cache manager & download worker pool
├── cli.py              # CLI commands (argparse)
├── config.py           # AppSettings, load/save
├── cover.py            # Cover art extraction
├── db.py               # SQLite database layer & FTS5 search
├── local.py            # Local folder playback
├── lyrics.py           # Lyrics fetching from lrclib
├── models.py           # Track, Channel dataclasses
├── player.py           # BackgroundPlayer (mpv IPC)
├── render_base.py      # Helpers, colors, keybinds
├── render_classic.py   # 2-panel classic layout (cmus style)
├── render_cover.py     # Cover art rendering via chafa
├── render_help.py      # Help overlay, mini view
├── render_panels.py    # Tracks, channels, detail panels
├── render_split.py     # 3-panel split view
├── shared.py           # Shared state & utility functions
├── telegram_client.py  # Telethon client & session management
├── themes.py           # Color themes definitions
├── tui.py              # TUI main class & orchestrator
├── tui_player.py       # PlayerMixin (playback logic)
├── tui_render.py       # RenderMixin (compositor)
└── welcome.py          # Setup wizard & welcome screen
```

## Reporting bugs

Open an issue with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Your OS, Python version, and terminal emulator
