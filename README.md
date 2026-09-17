<p align="center">
  <b>English</b> • <a href="README_es.md">Español</a>
</p>

# tg-music-cli

<p align="center">
  <a href="https://github.com/andrwvaz2/tg-music-cli/actions/workflows/ci.yml"><img src="https://github.com/andrwvaz2/tg-music-cli/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
</p>

<p align="center">
  <img src="assets/banner.jpg" alt="tg-music banner" width="100%">
</p>

<p align="center">
  <b>A fast, lightweight terminal music player and streamer for Telegram channels.</b>
</p>

---

## Features

* **Folder-like Navigation:** Browse indexed Telegram channels as if they were local directories.
* **Smart Pre-caching:** Automatically downloads the next 3 tracks in the play queue in the background to eliminate playback gaps.
* **Embedded Cover Art:** Album art rendering directly in the terminal via `chafa` (high-resolution graphics in Kitty/Ghostty, character-art fallback in other terminals).
* **Local Database:** Fast SQLite integration for tracking playback history, favorites, playlists, and tags.
* **Multiple Layouts:** Classic 2-panel view (`C`), 3-panel Split View (`P`), and a compact single-line Mini View (`M`).
* **Themes & Visual Equalizer:** Multiple 256-color themes (Dark, Dracula, Nord, Light, etc.), interactive theme picker (`F2`), animated visual equalizer, and slider progress bars.
* **Global Search (FTS5):** Instant full-text search across all indexed tracks and channels (`G`).
* **MPRIS2 Support:** Full Linux desktop media key integration, lock screen/widget control, and external control via `playerctl` with cover art support.
* **Blocklist:** Ignore tracks to remove them from local cache and automatically exclude them from future scans and downloads.

---

## Preview & Layouts

### Classic View (Press `C`)
A clean two-panel layout inspired by classic terminal music players like *cmus* and *ncmpcpp*:
1. **Library:** Left panel showing channels and local folders.
2. **Playlist:** Right panel with 4 columns: Duration, Artist, Title, Album.
3. **Control:** Status bar with playback state, volume, speed, and progress bar.
4. **Lyrics:** Dedicated box for lyrics display.
5. **Help bar:** Footer with keyboard shortcuts.

![tg-music Classic View](assets/classic-view.png)

### Split View (Press `P`)
Splits the interface into three columns:
1. **Channels:** List of added channels and local folders.
2. **Tracks:** Songs inside the selected channel.
3. **Details:** Current track metadata, cover art, and play queue.

![tg-music TUI split view](assets/screenshot.png)

### Mini View (Press `M`)
Reduces the TUI to a single bottom bar showing progress, track title, volume, and playback state.

### Demo Video
Check out the player in action, featuring navigation, pre-caching, and queue management:

https://github.com/user-attachments/assets/fdd5f457-2e5a-4c84-bf5b-d8f0cad070d7

*(Alternative local video mirror: [assets/demo.mp4](assets/demo.mp4))*

---

## Requirements

| Dependency | Version | Required? | Purpose |
|------------|---------|:---------:|---------|
| Python | >= 3.11 | Yes | Runtime environment |
| [mpv](https://mpv.io/) | Any recent | Yes | Audio playback engine |
| [dbus-next](https://github.com/altdesktop/python-dbus-next) | >= 0.2.3 | Yes (Auto) | MPRIS2 desktop media key & D-Bus integration |
| [chafa](https://hpjansson.org/chafa/) | Any recent | No | Terminal cover art rendering |
| [playerctl](https://github.com/altdesktop/playerctl) | Any recent | No | CLI utility for desktop media controls |
| [uv](https://docs.astral.sh/uv/) | Any recent | Recommended | Fast package and environment manager |

* **Linux:** Fully supported (native experience).
* **macOS:** Fully supported (requires installation of dependencies via Homebrew).
* **Windows:** Supported via **WSL (Windows Subsystem for Linux)** (recommended) or native Windows (via Scoop/Chocolatey).

---

## Installation & Setup

### 1. Install System Dependencies

This project relies on `mpv` for audio playback, `chafa` (optional) for terminal cover art rendering, and `playerctl` (optional) for desktop media key controls. Python dependencies (such as `dbus-next`, `telethon`, and `mutagen`) are handled automatically during installation.

#### Linux

##### Debian / Ubuntu / Mint
```bash
sudo apt update && sudo apt install -y mpv chafa playerctl
```

##### Arch Linux / Manjaro
```bash
sudo pacman -S mpv chafa playerctl
```

##### Fedora
```bash
sudo dnf install mpv chafa playerctl
```

##### NixOS
Add `mpv`, `chafa`, and `playerctl` to `environment.systemPackages` or run them in a shell:
```bash
nix-shell -p mpv chafa playerctl
```

#### macOS
```bash
brew install mpv chafa
```

#### Windows
* **Native Windows (PowerShell):**
  Install `mpv` with the built-in Windows Package Manager (`winget`):
  ```powershell
  winget install mpv.mpv
  winget install chafa   # Optional, for terminal album art
  ```
  *(Alternative managers: `scoop install mpv chafa` or `choco install mpv chafa`)*.
* **Via WSL (Recommended for best terminal graphics):** Open your WSL terminal (e.g., Ubuntu) and follow the **Linux** installation commands.

---

### 2. Install the Project

Clone this repository:
```bash
git clone https://github.com/andrwvaz2/tg-music-cli.git
cd tg-music-cli
```

Choose one of the following methods to run or install:

#### Method A: Using `uv` (Recommended & Fastest)
You can run commands directly without a global installation:
```bash
uv run tg-music <command>
```
Or install it as a globally accessible command:
```bash
uv tool install .
```

#### Method B: Standard Python (pip & venv)
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows (cmd): .venv\Scripts\activate.bat

# Install the package and dependencies
pip install .
```

### Updating

To update to the latest version:

```bash
# If installed via uv tool:
uv tool install --upgrade .

# If cloned from git:
cd tg-music-cli
git pull
uv sync

# If installed via pip:
pip install --upgrade .
```

---

## Quickstart

### Why do I need Telegram API credentials?

This app uses [Telethon](https://docs.telethon.dev/) (an open-source Telegram client library) to connect directly to Telegram's API. Telegram requires all third-party clients to authenticate using an `api_id` and `api_hash` to identify application traffic. You can get yours free at [my.telegram.org/apps](https://my.telegram.org/apps) in under 2 minutes. **Your credentials never leave your machine** — they are stored locally in `~/.local/share/tg-music/session.session` and are only used to authenticate your personal Telegram account.

1. **Configure Telegram Credentials:**
   Go to [my.telegram.org](https://my.telegram.org), log in, create an application, and retrieve your credentials.
   
   Run the initialization wizard:
   ```bash
   tg-music init
   ```
   *(Or using uv: `uv run tg-music init`)*

2. **Scan a Music Channel:**
   Index metadata from a public Telegram channel:
   ```bash
   tg-music scan https://t.me/Christian_Electronic --limit 300
   ```

3. **Start the TUI Player:**
   Launch the interactive interface:
   ```bash
   tg-music tui
   ```

> [!NOTE]
> On first execution or when running `tg-music login`, the Telegram client will prompt you for your phone number and verification code to authenticate. The session details are securely stored locally at `~/.local/share/tg-music/session.session`.

---

## Keybindings

### Navigation and Playback

| Key | Action |
|:---:|---|
| <kbd>↑</kbd> <kbd>↓</kbd> / <kbd>j</kbd> <kbd>k</kbd> | Move cursor |
| <kbd>PgUp</kbd> <kbd>PgDn</kbd> | Jump 10 tracks up / down |
| <kbd>Home</kbd> / <kbd>End</kbd> | Jump to first / last track |
| <kbd>Enter</kbd> | Open channel / Play selected track |
| <kbd>Space</kbd> | Expand or collapse channel / folder |
| <kbd>Backspace</kbd> / <kbd>←</kbd> | Collapse channel / Return to channels list |
| <kbd>Tab</kbd> | Switch active panel focus (Split View) |
| <kbd>n</kbd> / <kbd>→</kbd> | Next track |
| <kbd>p</kbd> / <kbd>←</kbd> | Previous track |
| <kbd>s</kbd> | Stop playback |
| <kbd>S</kbd> | Toggle shuffle mode |
| <kbd>R</kbd> | Toggle repeat mode |
| <kbd>+</kbd> / <kbd>-</kbd> | Adjust volume |
| <kbd>/</kbd> | Search / filter in active list |
| <kbd>G</kbd> | Global full-text search (FTS5) across all tracks |
| <kbd>r</kbd> | Refresh current track list |
| <kbd>c</kbd> | Open channel browser |
| <kbd>g</kbd> | Open local music folder |
| <kbd>a</kbd> | Prompt to add channel or playlist |

### Views, Theming & General

| Key | Action |
|:---:|---|
| <kbd>C</kbd> | Toggle Classic View |
| <kbd>P</kbd> | Toggle Split View |
| <kbd>M</kbd> | Toggle Mini View |
| <kbd>L</kbd> | Toggle lyrics display |
| <kbd>T</kbd> | Cycle color theme (Dark, Light, Dracula, Nord, etc.) |
| <kbd>F2</kbd> | Open interactive theme picker |
| <kbd>:</kbd> | Command mode (e.g. `:login` to authenticate) |
| <kbd>?</kbd> / <kbd>H</kbd> / <kbd>F1</kbd> | Toggle interactive help overlay |
| <kbd>q</kbd> | Exit player |

### Playlists, Queue and Library

| Key | Action |
|:---:|---|
| <kbd>e</kbd> | Enqueue selected track |
| <kbd>E</kbd> | Clear play queue |
| <kbd>[</kbd> / <kbd>]</kbd> | Reorder selected track in play queue or active playlist |
| <kbd>f</kbd> | Toggle favorite status |
| <kbd>1</kbd> | Filter list by favorites |
| <kbd>t</kbd> | Edit tags for selected track |
| <kbd>y</kbd> | Show playlists panel |
| <kbd>Y</kbd> | Add selected track to a playlist (creates one if needed) |
| <kbd>m</kbd> | Download all missing tracks in current view |
| <kbd>u</kbd> | Scan older tracks in selected channel |
| <kbd>w</kbd> | Check for updates in active channel |
| <kbd>W</kbd> | Toggle background watcher daemon |
| <kbd>x</kbd> | Ignore track (removes cached file and skips in future syncs) |

---

## CLI Commands

The `tg-music` command (also aliased as `tgmusic-cli`) allows controlling the player directly from the shell. Running without subcommands opens the interactive TUI directly.

### Authentication & Setup
```bash
tg-music doctor                                 # Verify system dependencies, tools, and storage
tg-music init                                   # Run initial setup wizard (api_id & api_hash)
tg-music login                                  # Log in to Telegram interactively from CLI
```

### Channels & Scanning
```bash
tg-music add-channel <URL_OR_USER> --limit 300   # Add and index a channel
tg-music channels                               # List saved channels
tg-music scan <URL_OR_USER> --limit 300          # Index metadata
tg-music scan <URL_OR_USER> --cache              # Index and download audio
```

### Search (FTS5)
```bash
tg-music search "track title or artist"          # Instant full-text search
tg-music search "synthwave" --tag electronic     # Search filtered by tag
```

### Playback & Downloads
```bash
tg-music play <ID>                              # Play a specific track
tg-music play-latest <URL_OR_USER>               # Play latest track in a channel
tg-music play-folder /path/to/music --shuffle    # Play local directory with shuffle
tg-music random --limit 5                        # Play random tracks from library
tg-music cache <URL_OR_USER> --workers 2          # Download missing tracks to cache
```

### Playlists
```bash
tg-music playlist list                          # List all custom playlists
tg-music playlist create "Favorites 2026"        # Create a new playlist
tg-music playlist add "Favorites 2026" 12 15 22  # Add track IDs to playlist
tg-music playlist play "Favorites 2026"          # Play an entire playlist
tg-music playlist reorder "Favorites 2026" 15 1  # Move track ID 15 to position 1
tg-music playlist remove "Favorites 2026" 12     # Remove track ID from playlist
```

### Tags & Favorites
```bash
tg-music tag add <ID> <tag>                     # Add a tag to a track
tg-music tag remove <ID> <tag>                  # Remove a tag
tg-music tag list                               # List all tags in the system
tg-music tag show <ID>                          # Show tags of a track
tg-music favorite <ID>                          # Toggle favorite status
```

### Settings & Theming
```bash
tg-music settings show                          # Show current player settings
tg-music settings set theme dracula             # Set theme (dark, light, dracula, nord, etc.)
tg-music settings set volume 85                 # Set default volume (0-150)
```

### Desktop Media Keys & MPRIS2
When `tg-music` is playing, it registers an MPRIS2 D-Bus service (`org.mpris.MediaPlayer2.tgmusic`), allowing integration with Linux desktop media controls, lock screens, widgets, and `playerctl`:
```bash
playerctl play-pause                            # Play/Pause active playback
playerctl next                                  # Skip to next track
playerctl previous                              # Return to previous track
playerctl metadata                              # Display currently playing title, artist, and cover art
```

### Maintenance & Ignoring
```bash
tg-music ignore <ID>                            # Ignore track (deletes local file)
tg-music unignore <ID>                          # Stop ignoring track
tg-music ignored                                # List ignored tracks
tg-music cleanup --max-age 30                   # Clean cached files older than 30 days
tg-music status                                 # Display library summary & disk usage
```

---

## File Locations

* **Audio Cache:** `~/.cache/tg-music/audio`
* **SQLite Database:** `~/.local/share/tg-music/library.sqlite3`
* **Telegram Session:** `~/.local/share/tg-music/session.session`

---

## Troubleshooting

### Channel is private or inaccessible

If a channel returns no tracks or shows "channel not found", make sure:
- The channel is public (or you are a member of the private channel)
- The channel URL is correct (e.g., `https://t.me/channel_name`)
- You have authenticated with `tg-music init` and your session is valid

### Invalid API credentials

If you see "api_id/api_hash invalid" errors:
1. Go to [my.telegram.org/apps](https://my.telegram.org/apps)
2. Verify your credentials are correct
3. Run `tg-music init` again to update them
4. Delete the old session: `rm ~/.local/share/tg-music/session.session`

### mpv not found

If playback fails with "mpv not found":
- **Linux:** `sudo apt install mpv` (or `pacman -S mpv`, `dnf install mpv`)
- **macOS:** `brew install mpv`
- Verify: `mpv --version`

### Cover art not showing (chafa)

If cover art doesn't render in the terminal:
- Install chafa: `sudo apt install chafa` (or `brew install chafa`)
- Use a terminal with image support: **Kitty**, **Ghostty**, or **WezTerm** for best results
- Other terminals will fall back to ASCII art automatically
- Verify: `chafa --version`

---

## Contributions & Feedback

Contributions, bug reports, and feature requests are welcome! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines, or feel free to open an issue or submit a pull request on GitHub.

---

## Disclaimer

tg-music-cli is a personal music organization tool. It plays audio from public Telegram channels that you have access to through your own Telegram account. The developer does not provide, host, or distribute any media content.

You are responsible for how you use this tool. Make sure you have the right to access and play the content you listen to through Telegram.
