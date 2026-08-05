import os
import subprocess
import sys
from datetime import datetime

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget, QMessageBox

from logger import LOG_FILE
from twitch_token_manager import get_valid_token
from .log_window import LogWindow
from .style import MAIN_WINDOW_STYLESHEET


class MainMenuWindowState:
    def build_interface(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)
        self.setStyleSheet(MAIN_WINDOW_STYLESHEET)

        # Header removed to maximize panel space

        # --- Create all panels ---
        self.current_panel = self.current_panel_cls()
        self.next_panel = self.next_panel_cls()
        self.live_followed_panel = self.live_followed_panel_cls()
        # Wire the new LiveFollowedPanel signals.
        self.live_followed_panel.channel_selected.connect(self.channel_selected)
        self.live_followed_panel.watch_requested.connect(self.watch_selected)
        self.live_followed_panel.watchlist_changed.connect(self._on_watchlist_changed)
        # Inject dependencies the new panel needs for analytics/avatars.
        self.live_followed_panel.set_api(self.api)
        self.live_followed_panel.set_viewer_tracker(self.viewer_tracker)
        self.live_followed_panel.set_analytics_engine(self.analytics_engine)
        self.chat_panel = self.chat_panel_cls(access_token=get_valid_token() or "")
        self.dispatcher_panel = self.dispatcher_panel_cls()

        # --- Connect StreamState signals for reactive panel updates ---
        self.state.stream_ready.connect(self.current_panel.set_stream)
        self.state.next_stream_changed.connect(self.next_panel.set_stream)
        self.state.live_channels_changed.connect(self.live_followed_panel.set_streams)

        # --- 3-column grid: chat is full-height center column ---
        # Layout per user sketch (red=chat center, green=4 equal side panels):
        #   ┌──────────────┬────────────────┬──────────────┐
        #   │ CURRENTLY    │                │  NEXT STREAM │
        #   │ WATCHING     │     CHAT       │              │
        #   ├──────────────┤  (full height) ├──────────────┤
        #   │ LIVE FOLLOWED│                │  DISPATCHER  │
        #   └──────────────┴────────────────┴──────────────┘
        #        30%              40%              30%
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(self.current_panel,       0, 0)        # top-left
        grid.addWidget(self.chat_panel,          0, 1, 2, 1)  # center, spans 2 rows
        grid.addWidget(self.next_panel,          0, 2)        # top-right
        grid.addWidget(self.live_followed_panel, 1, 0)        # bottom-left
        grid.addWidget(self.dispatcher_panel,    1, 2)        # bottom-right
        grid.setColumnStretch(0, 3)   # left  30%
        grid.setColumnStretch(1, 4)   # chat  40%
        grid.setColumnStretch(2, 3)   # right 30%
        grid.setRowStretch(0, 1)      # top    50%
        grid.setRowStretch(1, 1)      # bottom 50%
        main_layout.addLayout(grid, 1)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.dispatcher_panel.append_log(f"[{timestamp}] {message}")

    def open_logs(self):
        if self.log_window is None:
            self.log_window = LogWindow(LOG_FILE)
        self.log_window.show()
        self.log_window.raise_()
        self.log_window.activateWindow()

    def reauthenticate(self):
        script = os.path.join(self.project_root, "twitch_auth.py")
        if not os.path.exists(script):
            self.log(f"RE-AUTH ERROR: {script} not found.")
            QMessageBox.critical(self, "Re-authenticate Failed", f"Could not find twitch_auth.py at:\n{script}")
            return
        try:
            subprocess.Popen([sys.executable, script])
            self.log("Started Twitch auth flow in a separate process.")
            QMessageBox.information(self, "Re-authenticate", "Twitch auth has been started in a new window.\nComplete the browser login to update the token.")
        except Exception as exc:
            self.log(f"RE-AUTH ERROR: {exc}")
            QMessageBox.critical(self, "Re-authenticate Failed", str(exc))

    def restore_window_geometry(self):
        try:
            from core.db import get_setting
            geometry = get_setting("main_window_geometry")
            if geometry:
                from PySide6.QtCore import QByteArray
                ga = QByteArray.fromBase64(geometry.encode("ascii"))
                if self.restoreGeometry(ga):
                    self.log("Control Center geometry restored.")
                    return
        except Exception as exc:
            self.log(f"Could not restore geometry: {exc}")
        self.log("No saved Control Center geometry.")

    def save_window_geometry(self):
        try:
            from core.db import set_setting
            b64 = self.saveGeometry().toBase64().data().decode("ascii")
            set_setting("main_window_geometry", b64)
        except Exception as exc:
            print(f"[SETTINGS] Could not save geometry: {exc}")

    def save_last_streamer(self, channel):
        if not channel:
            return
        channel = str(channel).strip().lower()
        if not channel:
            return
        from core.db import set_setting
        set_setting("last_streamer", channel)
        self.log(f"Saved last streamer: #{channel}")

    def load_last_streamer(self):
        try:
            from core.db import get_setting
            channel = get_setting("last_streamer", "")
            if not channel:
                return None
            return str(channel).strip().lower()
        except Exception:
            return None

    def clear_last_streamer(self):
        try:
            from core.db import delete_setting
            delete_setting("last_streamer")
        except Exception:
            pass

    def _on_watchlist_changed(self):
        """Refresh live channels when the watchlist is modified."""
        if getattr(self, "is_closing", False):
            return
        try:
            if self.user:
                self.load_live_channels()
            else:
                self.log("Watchlist updated; connect to refresh live channels.")
        except Exception as exc:
            self.log(f"Could not refresh after watchlist change: {exc}")

    def move_to_secondary_monitor(self):
        screens = QApplication.screens()
        if len(screens) < 2:
            self.log("Only one monitor detected.")
            self.showMaximized()
            return
        primary = QApplication.primaryScreen()
        secondary = None
        for screen in screens:
            if screen != primary:
                secondary = screen
                break
        if not secondary:
            self.showMaximized()
            return
        geometry = secondary.availableGeometry()
        self.setGeometry(geometry)
        self.showMaximized()
        self.log("Control Center moved to secondary monitor.")
