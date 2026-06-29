# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2025-07-01

### Added
- TUI player with 3 layouts: Classic, Split View (3 panels), Mini View
- Local folder playback (`tg-music play-folder /path/to/music`)
- Telegram channel scanning and audio indexing via Telethon
- SQLite database for playback history, favorites, and tags
- Smart pre-caching of upcoming tracks in background
- Embedded cover art rendering via chafa (Sixel/iTerm2 + ASCII fallback)
- Playlists with create/add/remove/delete operations
- Lyrics fetching from lrclib.net
- Export/import playlists as M3U files
- 10 color themes (Dracula, Nord, Solarized, Gruvbox, Tokyo Night, Catppuccin, Monokai)
- As-you-type search with live filtering
- Vim-style command mode (`:`)
- Tab completion for bash, zsh, and fish
- Welcome screen with setup instructions
- CLI commands: scan, cache, play, tag, favorite, ignore, export, import
- GitHub Actions CI (pytest on Python 3.11/3.12/3.13)
- 42 unit tests
