# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.5.0] - 2026-09-16

### Added
- MPRIS2 D-Bus service support for multimedia keys and desktop player integration (GNOME, KDE, Waybar, etc.).
- External player control via tools like `playerctl` (play, pause, next, previous, stop, seek, and track metadata).
- Embedded album art URI export via `mpris:artUrl`.
- Real-time player state synchronization through `mpv` JSON IPC socket.
- Graceful degradation for headless or SSH sessions without active D-Bus session bus.
- Added `dbus-next` dependency.

## [0.4.0] - 2026-09-16

### Added
- 256-color themes support with built-in palettes (Dark, Light, Dracula, Nord, etc.).
- In-TUI theme shortcuts: cycle themes (`T`) and interactive theme picker modal (`F2`).
- Animated visual equalizer next to the NOW PLAYING banner.
- Slider-based progress and volume bars replacing legacy text meters.
- Clean track-list status badges (REPRODUCIENDO, Cacheando, Local, Remoto).

### Fixed
- Fixed duplicate NOW PLAYING banner overlap and lyrics panel overlap.

## [0.3.1] - 2026-09-15

### Fixed
- Fixed login modal crash on first keystroke in TUI.
- Read package version dynamically instead of hardcoding.

## [0.3.0] - 2026-09-14

### Added
- Interactive Telegram authentication flow in both CLI (`tg-music login`) and TUI modal.
- Classic 2-panel view layout inspired by cmus and ncmpcpp (press `C`).
- Full-text search CLI command using SQLite FTS5 (`tg-music search`).
- Playlist playback and track reordering commands in CLI.

## [0.2.0] - 2026-09-14

### Added
- Integrated playlists panel in TUI (press `y`) and shortcut to add tracks (press `Y`).
- Global full-text search overlay across all indexed tracks (press `G`).
- Queue and playlist track reordering via `[` and `]` keybindings.

## [0.1.0] - 2025-07-01

### Added
- TUI player with 3 layouts: Classic, Split View (3 panels), Mini View.
- Local folder playback (`tg-music play-folder /path/to/music`).
- Telegram channel scanning and audio indexing via Telethon.
- SQLite database for playback history, favorites, and tags.
- Smart pre-caching of upcoming tracks in background.
- Embedded cover art rendering via chafa (Sixel/iTerm2 + ASCII fallback).
- Playlists with create/add/remove/delete operations.
- Lyrics fetching from lrclib.net.
- Export/import playlists as M3U files.
- 10 color themes (Dracula, Nord, Solarized, Gruvbox, Tokyo Night, Catppuccin, Monokai).
- As-you-type search with live filtering.
- Vim-style command mode (`:`).
- Tab completion for bash, zsh, and fish.
- Welcome screen with setup instructions.
- CLI commands: scan, cache, play, tag, favorite, ignore, export, import.
- GitHub Actions CI (pytest on Python 3.11/3.12/3.13).
- Ruff linter integration.
- CONTRIBUTING.md with development workflow.
- Unit test suite.
