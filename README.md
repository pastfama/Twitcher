# 🎮 Watcher

**Automated Stream Control Center** — monitors your followed channels across Twitch, Kick, and YouTube, auto-plays streams, tracks raids, and displays real-time analytics.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![PySide6](https://img.shields.io/badge/UI-PySide6-green.svg)](https://doc.qt.io/qtforpython/)

---

## 📥 Download

**Latest release:** [Download Watcher.exe](../../releases/latest)

> No Python installation needed — just download `Watcher.exe` and run it.
> VLC runtime is bundled — no separate VLC install required.

---

## ✨ Features

- **Auto-play** — starts playing your last-watched stream the moment you launch the app (no login required)
- **Multi-platform** — Twitch, Kick, and YouTube in one control center
- **Raid chain following** — automatically follows raids to the next channel via EventSub
- **Live followed channels** — shows all your followed channels that are currently live
- **Twitch chat** — built-in IRC chat with Latin→Cyrillic transliteration
- **Real-time analytics** — viewer momentum tracking, SullyGnome analytics integration, quality scoring
- **Next stream prediction** — suggests the best channel to switch to if the current stream ends
- **Anon-mode video** — plays streams via Streamlink without Twitch authentication

---

## 🚀 Quick Start (Packaged App)

1. Download `Watcher.exe` from the [latest release](../../releases/latest)
2. Double-click `Watcher.exe`
3. Follow the **Installation Wizard** (first run only):
   - **Welcome** — app overview and install folder confirmation
   - **License Agreement** — read and accept the MIT license + personal use terms
   - **Data & Database** — confirms where your data is stored (`%APPDATA%\Watcher\`)
   - **Shortcuts** — optionally create Desktop / Start Menu shortcuts
   - **Complete** — launch Watcher
4. Click **RE-AUTH** to authenticate with Twitch (opens browser)
5. Your followed live channels appear automatically

---

## 🛠️ Development Setup

### Prerequisites

- Python 3.12+
- VLC media player (for building the exe — runtime is bundled)
- Streamlink (`pip install streamlink`)
- A Twitch Developer application (for OAuth)

### Install

```bash
git clone https://github.com/pastfama/Twitcher.git
cd Twitcher
git checkout dev          # development branch (has tests)
pip install -r requirements.txt  # or install manually
```

### Run

```bash
python watcher.py
# or with auto-restart + logging:
powershell -File run_watcher.ps1
# or debug watch mode:
start_watcher_watch.bat
```

### Build the .exe

```bash
powershell -File build_exe.ps1
# Output: dist/Watcher.exe
```

---

## 🏗️ Architecture

```
Twitcher/
├── watcher.py             # Entry point — creates QApplication, auth, launches MainMenu
├── wizard.py              # Installation wizard (first-run setup)
├── paths.py               # Centralized path resolution (frozen exe vs dev)
├── api.py                 # Re-export shim for TwitchAPI
├── chat.py                # Twitch IRC chat client + transliteration
├── video.py               # VLC-based video window (anon-mode)
├── logger.py              # Centralized logging
├── twitch_auth.py         # OAuth device code flow
├── twitch_token_manager.py # Token refresh/validation
│
├── core/                  # Domain logic (non-UI)
│   ├── db.py                # SQLite database layer (all persistent data)
│   ├── analytics_engine.py  # Combines local + external intelligence
│   ├── dispatcher.py        # Stream switching logic
│   ├── raid_monitor.py      # EventSub raid detection
│   ├── stream_resolver.py   # Auth-free stream URL resolution
│   ├── viewer_monitor.py    # Periodic viewer count polling
│   ├── viewer_tracker.py    # Realtime viewer momentum tracking
│   ├── async_bridge.py      # Async-to-sync bridge
│   ├── workers.py           # QThreadPool background task runner
│   └── irc/                 # Twitch IRC client
│
├── mainmenu/              # PySide6 UI panels
│   ├── main.py              # MainMenu window (mixin composition)
│   ├── app_runtime.py       # Twitch connection logic
│   ├── channel_state.py     # Channel selection / stream state
│   ├── raid_runtime.py      # Raid handling
│   ├── window_state.py      # Layout, geometry, settings
│   ├── dispatcher_panel.py  # Automation status panel
│   ├── log_window.py        # Log viewer window
│   ├── style.py             # Main window stylesheet
│   ├── theme.py             # Shared theme constants
│   ├── chatpanel/           # Twitch chat panel
│   ├── currwatching/        # Currently-watching panel (analytics)
│   ├── livefollowed/        # Live followed channels panel
│   ├── nextstream/          # Next stream prediction panel
│   └── channel/             # Channel rewards panel
│
├── widgets/               # Reusable UI widgets
│   ├── mom/                 # Momentum gauge (AnalogGauge)
│   ├── sullygoose/          # SullyGnome analytics grid widget
│   ├── viewer_graph.py      # Viewer history sparkline
│   └── indicators.py        # Neon status indicators
│
├── platforms/             # Multi-platform abstraction
│   ├── base.py              # Platform ABC
│   ├── twitch.py            # Twitch platform
│   ├── kick.py              # Kick platform
│   ├── youtube.py           # YouTube platform
│   └── manager.py           # PlatformManager (unified)
│
├── twitch_api/            # Twitch API client (mixin-based)
├── kick_api/              # Kick API client
├── youtube_api/           # YouTube API client
├── sullygoose_api/        # Tokenless web scraping (SullyGnome + future)
├── account_manager/       # Multi-platform account/auth manager
├── tests/                 # Test scripts (dev branch only)
├── watcher.spec           # PyInstaller build config
└── build_exe.ps1          # Build script
```

### Key Design Principles

- **UI never blocks** — all API calls run on `QThreadPool` via `core/workers.py`
- **Anon-mode video** — plays immediately using local channel history + auth-free Streamlink
- **Multi-platform** — unified `PlatformManager` abstracts Twitch, Kick, and YouTube
- **Mixin architecture** — `MainMenu` composes `WindowState` + `Runtime` + `StreamState` + `RaidRuntime`
- **Centralized paths** — `paths.py` handles frozen exe vs dev path resolution

---

## 💾 Data Storage

| Data | Location (Packaged Exe) | Location (Dev) |
|------|------------------------|----------------|
| Database (`watcher.db`) | `%APPDATA%\Watcher\` | Project root |
| Logs (`watcher_debug.log`) | `%APPDATA%\Watcher\` | Project root |
| Config (`config.yaml`) | Bundled in exe | `twitch_api/config.yaml` |

No separate database software is required — SQLite is embedded in Python.

---

## 🌿 Git Workflow

| Branch | Purpose |
|--------|---------|
| `main` | Clean release branch (no tests, packaged exe in releases) |
| `dev`  | Development branch (includes `tests/`) |

---

## 📦 Bundled Dependencies & Licenses

| Dependency | License | Bundled? |
|-----------|---------|----------|
| PySide6 (Qt6) | LGPLv3 | ✅ (dynamic linking) |
| requests | Apache 2.0 | ✅ |
| streamlink | ISC/BSD | ✅ |
| Python | PSF | ✅ |
| VLC | LGPL | ✅ (bundled since v0.7.1) |
| beautifulsoup4 | MIT | ✅ |
| python-vlc | GPLv2 | ✅ |

---

## 📄 License

MIT License + Personal Use Addendum — see [LICENSE](LICENSE) for details.

This software is:
- **Open source** (MIT License)
- **Personal use only** — not for distribution or sharing
- **Not affiliated with** Twitch, Kick, or YouTube

Bundled dependencies retain their respective licenses (LGPLv3, Apache 2.0, ISC/BSD, PSF, MIT, GPLv2).
