import os
import subprocess
import sys
from datetime import datetime

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget, QMessageBox

from logger import LOG_FILE
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

        header_layout = QHBoxLayout()
        header = QLabel("TWITCHER")
        header.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        header.setStyleSheet("color: #aab4ff;")
        header_layout.addWidget(header)

        subtitle = QLabel("AUTOMATED STREAM CONTROL CENTER")
        subtitle.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        subtitle.setStyleSheet("color: #727991;")
        header_layout.addWidget(subtitle)
        header_layout.addStretch()

        self.connection_label = QLabel("● OFFLINE")
        self.connection_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.connection_label.setStyleSheet("color: #ff7777;")
        header_layout.addWidget(self.connection_label)

        self.logs_button = QPushButton("LOGS")
        self.logs_button.clicked.connect(self.open_logs)
        header_layout.addWidget(self.logs_button)

        self.reauth_button = QPushButton("RE-AUTH")
        self.reauth_button.clicked.connect(self.reauthenticate)
        header_layout.addWidget(self.reauth_button)

        main_layout.addLayout(header_layout)

        stream_cards = QHBoxLayout()
        stream_cards.setSpacing(10)
        self.current_panel = self.current_panel_cls()
        self.next_panel = self.next_panel_cls()
        stream_cards.addWidget(self.current_panel, 1)
        stream_cards.addWidget(self.next_panel, 1)
        main_layout.addLayout(stream_cards)

        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(10)
        self.live_followed_panel = self.live_followed_panel_cls()
        self.live_followed_panel.channel_selected.connect(self.channel_selected)
        self.live_followed_panel.refresh_requested.connect(self.load_live_channels)
        self.live_followed_panel.watch_requested.connect(self.watch_selected)
        self.live_followed_panel.stop_requested.connect(self.stop_video)
        self.chat_panel = self.chat_panel_cls(access_token=os.getenv("TWITCH_ACCESS_TOKEN", ""))
        self.dispatcher_panel = self.dispatcher_panel_cls()
        middle_layout.addWidget(self.live_followed_panel, 25)
        middle_layout.addWidget(self.chat_panel, 50)
        middle_layout.addWidget(self.dispatcher_panel, 25)
        main_layout.addLayout(middle_layout, 1)

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
        geometry = self.settings.value("main_window_geometry")
        if geometry:
            try:
                if self.restoreGeometry(geometry):
                    self.log("Control Center geometry restored.")
                    return
            except Exception as exc:
                self.log(f"Could not restore geometry: {exc}")
        self.log("No saved Control Center geometry.")

    def save_window_geometry(self):
        try:
            self.settings.setValue("main_window_geometry", self.saveGeometry())
            self.settings.sync()
        except Exception as exc:
            print(f"[SETTINGS] Could not save geometry: {exc}")

    def save_last_streamer(self, channel):
        if not channel:
            return
        channel = str(channel).strip().lower()
        if not channel:
            return
        self.settings.setValue("last_streamer", channel)
        self.settings.sync()
        self.log(f"Saved last streamer: #{channel}")

    def load_last_streamer(self):
        channel = self.settings.value("last_streamer", "")
        if not channel:
            return None
        return str(channel).strip().lower()

    def clear_last_streamer(self):
        self.settings.remove("last_streamer")
        self.settings.sync()

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
