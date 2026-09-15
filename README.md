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
* **Global Search (FTS5):** Instant full-text search across all indexed tracks and channels (`G`).
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
| [chafa](https://hpjansson.org/chafa/) | Any recent | No | Terminal cover art rendering |
| [uv](https://docs.astral.sh/uv/) | Any recent | Recommended | Fast package and environment manager |

* **Linux:** Fully supported (native experience).
* **macOS:** Fully supported (requires installation of dependencies via Homebrew).
* **Windows:** Supported via **WSL (Windows Subsystem for Linux)** (recommended) or native Windows (via Scoop/Chocolatey).

---

## Installation & Setup

### 1. Install System Dependencies

This project relies on `mpv` for audio playback and `chafa` (optional) for terminal cover art rendering.

#### Linux

##### Debian / Ubuntu / Mint
```bash
sudo apt update && sudo apt install -y mpv chafa
```

##### Arch Linux / Manjaro
```bash
sudo pacman -S mpv chafa
```

##### Fedora
```bash
sudo dnf install mpv chafa
```

##### NixOS
Add `mpv` and `chafa` to `environment.systemPackages` or run them in a shell:
```bash
nix-shell -p mpv chafa
```

#### macOS
```bash
brew install mpv chafa
```

#### Windows
* **Via WSL (Recommended):** Open your WSL terminal (e.g., Ubuntu) and follow the **Linux** installation commands.
* **Native Windows:** Install dependencies via [Scoop](https://scoop.sh/) or [Chocolatey](https://chocolatey.org/):
  ```powershell
  # Using Scoop
  scoop install mpv chafa
  # Using Chocolatey
  choco install mpv chafa
  ```

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
| <kbd>Enter</kbd> | Open channel / Play selected track |
| <kbd>Space</kbd> / <kbd>→</kbd> | Expand channel |
| <kbd>Backspace</kbd> / <kbd>←</kbd> | Collapse channel / Return to channels list |
| <kbd>s</kbd> | Stop playback |
| <kbd>n</kbd> | Next track |
| <kbd>+</kbd> / <kbd>-</kbd> | Adjust volume |
| <kbd>/</kbd> | Search / filter in active list |
| <kbd>r</kbd> | Refresh list |
| <kbd>C</kbd> | Toggle Classic View |
| <kbd>P</kbd> | Toggle Split View |
| <kbd>M</kbd> | Toggle Mini View |
| <kbd>q</kbd> | Exit player |

### Management, Playlists and Queue

| Key | Action |
|:---:|---|
| <kbd>e</kbd> | Enqueue selected track |
| <kbd>[</kbd> / <kbd>]</kbd> | Reorder selected track in play queue or active playlist |
| <kbd>f</kbd> | Toggle favorite status |
| <kbd>1</kbd> | Filter list by favorites |
| <kbd>t</kbd> | Edit tags for selected track |
| <kbd>y</kbd> | Show playlists panel |
| <kbd>Y</kbd> | Add selected track to a playlist (creates one if needed) |
| <kbd>G</kbd> | Global full-text search (FTS5) across all tracks |
| <kbd>L</kbd> | Toggle lyrics display |
| <kbd>m</kbd> | Download all missing tracks in current view |
| <kbd>u</kbd> | Scan older tracks in selected channel |
| <kbd>w</kbd> | Check for updates in active channel |
| <kbd>W</kbd> | Toggle background watcher daemon |
| <kbd>x</kbd> | Ignore track (removes cached file and skips in future syncs) |

---

## CLI Commands

The `tg-music` command allows managing the player directly from the shell:

### Channels
```bash
tg-music add-channel <URL_OR_USER> --limit 300   # Add a channel
tg-music channels                               # List saved channels
tg-music scan <URL_OR_USER> --limit 300          # Index metadata
tg-music scan <URL_OR_USER> --cache              # Index and download audio
```

### Playback and Downloads
```bash
tg-music play <ID>                              # Play a specific track
tg-music play-latest <URL_OR_USER>               # Play latest track in a channel
tg-music cache <URL_OR_USER> --workers 2          # Download missing tracks to cache
```

### Tags Management
```bash
tg-music tag add <ID> <tag>                     # Add a tag to a track
tg-music tag remove <ID> <tag>                  # Remove a tag
tg-music tag list                               # List all tags in the system
tg-music tag show <ID>                          # Show tags of a track
```

### Ignoring & Favorites
```bash
tg-music favorite <ID>                          # Toggle favorite status
tg-music ignore <ID>                            # Ignore track (deletes local file)
tg-music unignore <ID>                          # Stop ignoring track
tg-music ignored                                # List ignored tracks
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
