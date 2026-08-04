# `gui/` — PySide6-free Twitcher dashboard (CustomTkinter)

Replacement GUI layer for Twitcher that uses **CustomTkinter** instead of
PySide6/Qt6. It keeps the existing `core/*` backend intact and only
translates the *view* layer (panels + custom gauge/graph/indicator widgets).

## Install
```powershell
.venv-1\Scripts\python -m pip install -r gui/requirements.txt
# (= customtkinter, which needs the Tk that ships with Python on Windows)
```

## Run (interactive window)
```powershell
.venv-1\Scripts\python -m gui.demo_dashboard     # full dashboard with mock metrics
#  or, metrics-card only:
.venv-1\Scripts\python -m gui.demo_metrics       # Current Watching card only
```

## Headless test (proves every panel + every metric updates, no display needed)
```powershell
.venv-1\Scripts\python -m gui._smoke
```

## How it's wired (mirrors the old PySide6 flow)
```
tkinter  after() tick   ==  Qt QTimer
  └─ app._loop() every 1s
        └─ provider() returns the real ViewerTracker.analyze() dict + history
              └─ DashboardApp → metrics.set_metrics(analysis, history)
                     → NextStream.update / LiveFollowed.update / Dispatcher.update / Chat.update
```

The demo uses `_DashboardProvider` (a mock). To point it at your real backend,
swap the provider for one that calls the existing `core/*`:
```python
from core import TimeBoss, ViewerMonitor, ViewerTracker
def real_provider():
    # whatever your TimeBoss/ViewerMonitor already compute
    return {"current": (analysis, history),
            "next": {...}, "live": [...],
            "dispatch": {...}, "chat": {...}, "connection": "● ONLINE …"}
from gui.dashboard import run_dashboard
run_dashboard(provider=real_provider)
```

## Ports from PySide6
| PySide6 (old)                      | CustomTkinter (new)               |
|---                                  |---|
| `QMainWindow`                       | `ctk.CTk` (DashboardApp)            |
| `QTimer`                              | `tkinter` `.after()` tick loop      |
| `QLabel(text=...)` / `setText`    | `CTkLabel(textvariable=StringVar)`  |
| `QListWidget` w/ avatars          | `CTkScrollableFrame` + canvas rows   |
| `QTextEdit` (read-only log/chat)| `CTkTextbox`                        |
| `QProgressBar` / `AnalogGauge`  | `AnalogGauge` on `tkinter.Canvas`   |
| `ViewerHistoryGraph`            | `MomentumSparkline` on `Canvas`     |
| `NeonIndicator`                 | `NeonIndicator` on `Canvas`         |
| `QSettings`                     | `tomllib`/`json` file               |
| `setStyleSheet` dark theme     | `Theme` constants + CTk colors      |
