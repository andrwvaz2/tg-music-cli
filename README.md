# tg-music-cli

![tg-music banner](assets/banner.jpg)

Terminal music player for Telegram channels.



https://github.com/user-attachments/assets/fdd5f457-2e5a-4c84-bf5b-d8f0cad070d7





```text
┌──────────────────────────────────────────────────────────┐
│                                                          │
│                    T G  -  M U S I C                     │
│       Terminal music player for Telegram channels        │
│                                                          │
├──────────────────────────────────────────────────────────┤
│                                                          │
│                          SETUP                           │
│                                                          │
│     1. Go to https://my.telegram.org/apps                │
│     2. Log in and get your api_id and api_hash           │
│     3. Run configuration command:                        │
│     $ tg-music init                                      │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

## Features

* **Folder-like Navigation:** Browse indexed Telegram channels as if they were local directories.
* **Smart Pre-caching:** Background download of the next 3 tracks in the play queue to prevent playback gaps.
* **Embedded Cover Art:** Album art rendering in the terminal using `chafa` (with high-resolution support in Kitty/Ghostty and character-art fallback in other terminals).
* **Local Database:** Fast SQLite integration for tracking playback history, favorites, and tags.
* **Multiple Layouts:** Classic view, 3-panel Split View (`P`), and a compact single-line Mini View (`M`).
* **Blocklist:** Ignore tracks to automatically prevent them from showing up or being bulk-downloaded.

---

## System Compatibility

* **Linux:** Fully supported (native experience).
* **macOS:** Fully supported (requires installation of dependencies via Homebrew).
* **Windows:** Supported via **WSL (Windows Subsystem for Linux)** (recommended) or native Windows (requires Unix socket support in Windows Terminal/OS, see below).

---

## Installation & Setup

### 1. Install System Dependencies

This project relies on `mpv` for audio playback and `chafa` (optional) for terminal cover art rendering.

#### Linux

##### Debian / Ubuntu
```bash
sudo apt update && sudo apt install -y mpv chafa
```

##### Arch Linux
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

### 2. Install the Project

Clone this repository:
```bash
git clone https://github.com/yourusername/tg-music-cli.git
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

---

## Quickstart

1. **Configure Telegram Credentials:**
   Before running the app, you need an API ID and Hash. Go to [my.telegram.org](https://my.telegram.org), log in, create an application, and retrieve your credentials.
   
   Run the initialization wizard:
   ```bash
   # If installed via uv tool or pip:
   tg-music init
   
   # Or using uv run:
   uv run tg-music init
   ```

2. **Scan a Music Channel:**
   Index metadata from a public Telegram channel:
   ```bash
   # If installed globally:
   tg-music scan https://t.me/Christian_Electronic --limit 300
   
   # Or using uv run:
   uv run tg-music scan https://t.me/Christian_Electronic --limit 300
   ```

3. **Start the TUI Player:**
   Launch the interactive interface:
   ```bash
   # If installed globally:
   tg-music tui
   
   # Or using uv run:
   uv run tg-music tui
   ```

*Note: On first execution, the Telegram client will prompt you for your phone number and verification code to authenticate. The session details are securely stored locally at `~/.local/share/tg-music/session.session`.*

---

## TUI Layouts

### Split View (Press `P`)
Splits the interface into three columns:
1. **Channels:** List of added channels and local folders.
2. **Tracks:** Songs inside the selected channel.
3. **Details:** Current track metadata, cover art, and play queue.

### Mini View (Press `M`)
Reduces the TUI to a single bottom bar showing progress, track title, volume, and playback state.

---

## Keybindings

### Navigation and Playback

| Key | Action |
|---|---|
| `Arrows` / `j`/`k` | Move cursor |
| `Enter` | Open channel / Play selected track |
| `Space` / `→` | Expand channel |
| `Backspace` / `←` | Collapse channel / Return to channels list |
| `s` | Stop playback |
| `n` | Next track |
| `+` / `-` | Adjust volume |
| `/` | Search in active list |
| `r` | Refresh list |
| `q` | Exit player |

### Management and Queue

| Key | Action |
|---|---|
| `e` | Enqueue selected track |
| `[` / `]` | Move track up/down in the play queue |
| `f` | Toggle favorite status |
| `1` | Filter list by favorites |
| `t` | Edit tags for selected track |
| `L` | Toggle lyrics display |
| `m` | Download all missing tracks in current view |
| `u` | Scan older tracks in selected channel |
| `w` | Check for updates in active channel |
| `W` | Toggle background watcher daemon |
| `x` | Ignore track (deletes local file and skips in future downloads) |

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

## Contributions & Feedback

Contributions, bug reports, and feature requests are welcome! Feel free to open an issue or submit a pull request on the GitHub repository.

---

## Disclaimer

This software is provided for educational and personal use only. The developer does not host, distribute, or promote the download of copyrighted material. 

The user is solely responsible for ensuring that accessing and playing content from Telegram channels through this tool complies with local laws and the platform's Terms of Service.
