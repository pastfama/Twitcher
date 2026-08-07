# 🎮 Twitcher

**Automated Twitch Stream Control Center** — monitors your followed channels, auto-plays streams, and displays real-time analytics.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![PySide6](https://img.shields.io/badge/UI-PySide6-green.svg)](https://doc.qt.io/qtforpython/)

---

## 📥 Download

**Latest release:** [Download Twitcher.exe](../../releases/latest)

> No Python installation needed — just download `Twitcher.exe` and run it.
> Requires [VLC media player](https://www.videolan.org/) installed on your machine.

---

## ✨ Features

- **Auto-play** — starts playing your last-watched stream the moment you launch the app (no login required)
- **Live followed channels** — shows all your followed channels that are currently live
- **Twitch chat** — built-in IRC chat with Latin→Cyrillic transliteration
- **Real-time analytics** — viewer momentum tracking, SullyGnome analytics integration, quality scoring
- **Next stream prediction** — suggests the best channel to switch to if the current stream ends
- **Anon-mode video** — plays streams via Streamlink without Twitch authentication

---

## 🚀 Quick Start (Packaged App)

1. Download `Twitcher.exe` from the [latest release](../../releases/latest)
2. Install [VLC](https://www.videolan.org/) if you don't have it
3. Double-click `Twitcher.exe`
4. Click **RE-AUTH** to authenticate with Twitch (opens browser)
5. Your followed live channels appear automatically

---

## 🛠️ Development Setup

### Prerequisites

- Python 3.12+
- VLC media player
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
python twitcher.py
# or with auto-restart + logging:
powershell -File run_twitcher.ps1
# or debug watch mode:
start_twitcher_watch.bat
```

### Build the .exe

```bash
powershell -File build_exe.ps1
# Output: dist/Twitcher.exe
```

---

## 🏗️ Architecture

```
Twitcher/
├── twitcher.py            # Entry point — creates QApplication, auth, launches MainMenu
├── api.py                 # Re-export shim for TwitchAPI
├── chat.py                # Twitch IRC chat client + transliteration
├── video.py               # VLC-based video window (anon-mode)
├── logger.py              # Centralized logging
├── twitch_auth.py         # OAuth device code flow
├── twitch_token_manager.py # Token refresh/validation
│
├── core/                  # Domain logic (non-UI)
│   ├── analytics_engine.py  # Combines local + external intelligence
│   ├── channel_history.py   # Last-watched channels (auth-free)
│   ├── dispatcher.py        # Stream switching logic
│   ├── stream_resolver.py   # Auth-free stream URL resolution
│   ├── streamer_history.py  # Persistent streamer metadata
│   ├── time_boss.py         # Central QTimer scheduler
│   ├── viewer_monitor.py    # Periodic viewer count polling
│   ├── viewer_tracker.py    # Realtime viewer momentum tracking
│   └── workers.py           # QThreadPool background task runner
│
├── mainmenu/              # PySide6 UI panels
│   ├── main.py              # MainMenu window (mixin composition)
│   ├── app_runtime.py       # Twitch connection logic
│   ├── channel_state.py     # Channel selection / stream state
│   ├── window_state.py      # Layout, geometry, settings
│   ├── dispatcher_panel.py  # Automation status panel
│   ├── log_window.py        # Log viewer window
│   ├── style.py             # Main window stylesheet
│   ├── theme.py             # Shared theme constants
│   ├── chatpanel/           # Twitch chat panel
│   ├── currwatching/        # Currently-watching panel (analytics)
│   ├── livefollowed/        # Live followed channels panel
│   ├── nextstream/          # Next stream prediction panel
│   └── channel/             # Channel rewards panel (v0.4 — upcoming)
│
├── widgets/               # Reusable UI widgets
│   ├── mom/                 # Momentum gauge (AnalogGauge)
│   ├── sullygoose/          # SullyGnome analytics grid widget
│   ├── viewer_graph.py      # Viewer history sparkline
│   └── indicators.py        # Neon status indicators
│
├── twitch_api/            # Twitch API client (mixin-based)
├── sullygoose_api/        # Tokenless web scraping (SullyGnome + future)
├── tests/                 # Test scripts (dev branch only)
├── twitcher.spec          # PyInstaller build config
└── build_exe.ps1          # Build script
```

### Key Design Principles

- **UI never blocks** — all API calls run on `QThreadPool` via `core/workers.py`
- **Anon-mode video** — plays immediately using local channel history + auth-free Streamlink
- **Mixin architecture** — `MainMenu` composes `WindowState` + `Runtime` + `StreamState`

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
| VLC | LGPL | ❌ (detected at runtime — install separately) |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

Bundled dependencies retain their respective licenses (LGPLv3, Apache 2.0, ISC/BSD, PSF).