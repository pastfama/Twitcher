import os
from datetime import datetime, timezone

from PySide6.QtCore import (
    Qt,
    QSettings,
    QTimer,
)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QGroupBox,
    QTextEdit,
    QMessageBox,
    QFrame,
)

from chat import ChatWidget
from logger import debug, info, warning, error
from video import VideoWindow
from dispatcher import StreamDispatcher
from raid_monitor import RaidMonitor
from .current_watching import CurrentWatchingPanel
from .next_stream import NextStreamPanel
from .live_followed import LiveFollowedPanel
from .chat_panel import ChatPanel
from .dispatcher_panel import DispatcherPanel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "..", "twitcher.log")


class MainMenu(QMainWindow):

    # ========================================================
    # INITIALIZATION
    # ========================================================

    def __init__(self, api):

        super().__init__()

        self.api = api

        self.settings = QSettings("Twitcher", "TwitcherControlCenter")

        self.user = None
        self.live_channels = []
        self.current_stream = None
        self.current_channel = None
        self.next_stream = None
        self.resume_attempted = False
        self.is_closing = False
        self.raid_transition_active = False

        self.video_window = VideoWindow()
        self.log_window = None

        self.raid_monitor = RaidMonitor(self.api)
        self.raid_monitor.signals.raid_detected.connect(self.handle_raid)
        self.raid_monitor.signals.status.connect(self.handle_raid_status)
        self.raid_monitor.signals.error.connect(self.handle_raid_error)

        self.dispatcher = StreamDispatcher(
            api=self.api,
            video_window=self.video_window,
            on_status=self.handle_dispatcher_status,
            on_log=self.handle_dispatcher_log,
            on_stream_changed=self.handle_stream_changed,
            on_raid_announcement=self.handle_raid_announcement,
        )

        self.setWindowTitle("Twitcher Control Center")
        self.setMinimumSize(1400, 800)

        self.build_interface()
        self.restore_window_geometry()
        self.load_twitch()

    # ========================================================
    # WINDOW GEOMETRY
    # ========================================================

    def restore_window_geometry(self):
        geometry = self.settings.value("main_window_geometry")

        if geometry:
            try:
                if self.restoreGeometry(geometry):
                    self.log("Control Center geometry restored.")
                    return
            except Exception as error:
                self.log(f"Could not restore geometry: {error}")

        self.log("No saved Control Center geometry.")

    def save_window_geometry(self):
        try:
            self.settings.setValue("main_window_geometry", self.saveGeometry())
            self.settings.sync()
        except Exception as error:
            print(f"[SETTINGS] Could not save geometry: {error}")

    # ========================================================
    # LAST STREAMER
    # ========================================================

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

    # ========================================================
    # MOVE TO SECONDARY MONITOR
    # ========================================================

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

    # ========================================================
    # UI
    # ========================================================

    def build_interface(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        self.setStyleSheet(
            """
            QMainWindow,
            QWidget {
                background-color: #08090f;
                color: #f2f2f5;
                font-family: "Segoe UI";
            }
            QGroupBox {
                background-color: #10121c;
                border: 1px solid #292d42;
                border-radius: 12px;
                margin-top: 12px;
                padding: 10px;
                font-size: 13px;
                font-weight: bold;
                color: #aeb8ff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 8px;
                background-color: #08090f;
            }
            QLabel {
                color: #eeeeF5;
            }
            QPushButton {
                background-color: #191c2c;
                color: #ffffff;
                border: 1px solid #353a58;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #272c48;
                border: 1px solid #5964a0;
            }
            QPushButton:pressed {
                background-color: #10121e;
            }
            QListWidget {
                background-color: #0c0e16;
                border: 1px solid #292d42;
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #1e2232;
            }
            QListWidget::item:hover {
                background-color: #181c2d;
            }
            QListWidget::item:selected {
                background-color: #30385e;
                border-left: 3px solid #7f8cff;
            }
            QTextEdit {
                background-color: #0b0d14;
                border: 1px solid #292d42;
                border-radius: 8px;
                color: #eeeeF5;
                padding: 8px;
            }
            QFrame#CurrentCard {
                background-color: #141827;
                border: 1px solid #3c456b;
                border-radius: 14px;
            }
            QFrame#NextCard {
                background-color: #101c1b;
                border: 1px solid #315f58;
                border-radius: 14px;
            }
            """
        )

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

        self.current_panel = CurrentWatchingPanel()
        self.next_panel = NextStreamPanel()

        stream_cards.addWidget(self.current_panel, 1)
        stream_cards.addWidget(self.next_panel, 1)

        main_layout.addLayout(stream_cards)

        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(10)

        self.live_followed_panel = LiveFollowedPanel()
        self.live_followed_panel.channel_selected.connect(self.channel_selected)
        self.live_followed_panel.refresh_requested.connect(self.load_live_channels)
        self.live_followed_panel.watch_requested.connect(self.watch_selected)
        self.live_followed_panel.stop_requested.connect(self.stop_video)

        self.chat_panel = ChatPanel(access_token=os.getenv("TWITCH_ACCESS_TOKEN", ""))
        self.dispatcher_panel = DispatcherPanel()

        middle_layout.addWidget(self.live_followed_panel, 25)
        middle_layout.addWidget(self.chat_panel, 50)
        middle_layout.addWidget(self.dispatcher_panel, 25)

        main_layout.addLayout(middle_layout, 1)

        self.channel_list = self.live_followed_panel.channel_list
        self.chat_widget = self.chat_panel.chat_widget
        self.dispatcher_status = self.dispatcher_panel.dispatcher_status
        self.next_status = self.dispatcher_panel.next_status
        self.event_log = self.dispatcher_panel.event_log

        self.channel_label = self.current_panel.channel_label
        self.viewers_label = self.current_panel.viewers_label
        self.category_label = self.current_panel.category_label
        self.uptime_label = self.current_panel.uptime_label
        self.title_label = self.current_panel.title_label

        self.next_channel_label = self.next_panel.next_channel_label
        self.next_viewers_label = self.next_panel.next_viewers_label
        self.next_category_label = self.next_panel.next_category_label
        self.next_reason_label = self.next_panel.next_reason_label

    # ========================================================
    # LOGGING

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.event_log.append(f"[{timestamp}] {message}")

    def open_logs(self):
        if self.log_window is None:
            self.log_window = LogWindow(LOG_FILE)
        self.log_window.show()
        self.log_window.raise_()
        self.log_window.activateWindow()

    def reauthenticate(self):
        try:
            import subprocess
            import sys

            script = os.path.join(os.path.dirname(__file__), "twitch_auth.py")
            subprocess.Popen([sys.executable, script])
            self.log("Started Twitch auth flow in a separate process.")
            QMessageBox.information(
                self,
                "Re-authenticate",
                "Twitch auth has been started in a new window.\nComplete the browser login to update the token."
            )
        except Exception as error:
            self.log(f"RE-AUTH ERROR: {error}")
            QMessageBox.critical(self, "Re-authenticate Failed", str(error))

    def handle_dispatcher_status(self, message):
        self.dispatcher_status.setText(f"Status: {message}")

    def handle_dispatcher_log(self, message):
        self.log(f"[DISPATCHER] {message}")

    def handle_stream_changed(self, data):
        channel = data.get("streamer", "")
        if not channel:
            return
        self.current_channel = channel.lower().strip()
        self.save_last_streamer(self.current_channel)
        self.log(f"Current stream changed to #{self.current_channel}")
        self.update_next_stream()

    def handle_raid_announcement(self, data):
        announcement_type = data.get("type")
        if announcement_type == "raid":
            from_streamer = data.get("from_streamer", "unknown")
            to_streamer = data.get("to_streamer", "unknown")
            viewers = data.get("viewers", 0)
            self.log(f"📢 RAID: {from_streamer} → {to_streamer} ({viewers:,} viewers)")
        elif announcement_type == "stream":
            streamer = data.get("streamer", "unknown")
            self.log(f"📢 STREAM ANNOUNCEMENT: {streamer}")

    def load_twitch(self):
        try:
            self.user = self.api.get_current_user()
            self.connection_label.setText("● CONNECTED")
            self.connection_label.setStyleSheet("color: #72d6a0;")
            self.log(f"Logged in as {self.user['display_name']}")
            self.chat_widget.username = self.user["login"]
            self.dispatcher_status.setText("Status: Connected to Twitch")
            self.load_live_channels()
        except Exception as error:
            self.connection_label.setText("● ERROR")
            self.connection_label.setStyleSheet("color: #ff7777;")
            self.dispatcher_status.setText("Status: Twitch connection error")
            self.log(f"ERROR: {error}")
            QMessageBox.critical(self, "Twitch Error", str(error))

    def load_live_channels(self):
        if not self.user:
            return
        try:
            self.dispatcher_status.setText("Status: Checking live channels...")
            QApplication.processEvents()
            followed = self.api.get_followed_channels(self.user["id"])
            self.live_channels = self.api.get_live_streams(followed)
            self.live_channels.sort(key=lambda stream: stream.get("viewer_count", 0), reverse=True)
            self.live_followed_panel.set_streams(self.live_channels)
            self.update_next_stream()
            self.dispatcher_status.setText(f"Status: {len(self.live_channels)} channels live")
            self.log(f"Found {len(self.live_channels)} live channels.")
            self.try_resume_last_streamer()
        except Exception as error:
            self.dispatcher_status.setText("Status: API error")
            self.log(f"ERROR: {error}")

    def try_resume_last_streamer(self):
        if self.resume_attempted:
            return
        self.resume_attempted = True
        last_streamer = self.load_last_streamer()
        if not last_streamer:
            self.log("No previous streamer saved.")
            return
        matching_stream = None
        for stream in self.live_channels:
            login = stream.get("user_login", "").lower().strip()
            username = stream.get("user_name", "").lower().strip()
            if last_streamer in (login, username):
                matching_stream = stream
                break
        if not matching_stream:
            self.log(f"Previous streamer #{last_streamer} is not currently live.")
            return
        self.log(f"Resuming previous streamer: #{last_streamer}")
        self.current_stream = matching_stream
        self.update_current_broadcast(matching_stream)
        self.start_channel(last_streamer, manual=False, resume=True)

    def update_next_stream(self):
        current = (self.current_channel or "").lower().strip()
        candidates = [
            stream
            for stream in self.live_channels
            if stream.get("user_login", "").lower().strip() != current
        ]
        if not candidates:
            self.next_stream = None
            self.next_channel_label.setText("No next stream available")
            self.next_viewers_label.setText("👁 — viewers")
            self.next_category_label.setText("🎮 —")
            self.next_reason_label.setText("No other followed channels are currently live.")
            self.next_status.setText("Next: No available stream")
            return
        candidates.sort(key=lambda stream: stream.get("viewer_count", 0), reverse=True)
        self.next_stream = candidates[0]
        channel = self.next_stream.get("user_name", "Unknown")
        viewers = self.next_stream.get("viewer_count", 0)
        category = self.next_stream.get("game_name") or "No category"
        self.next_channel_label.setText(channel)
        self.next_viewers_label.setText(f"👁 {viewers:,} viewers")
        self.next_category_label.setText(f"🎮 {category}")
        self.next_reason_label.setText("If the current stream ends without a raid, Twitcher will switch here.")
        self.next_status.setText(f"Next: #{channel} ({viewers:,} viewers)")

    def channel_selected(self, stream):
        if not stream:
            return
        self.current_stream = stream
        channel = stream.get("user_login")
        self.update_current_broadcast(stream)
        self.log(f"Selected {channel}")

    def update_current_broadcast(self, stream):
        channel = stream.get("user_name", "Unknown")
        self.channel_label.setText(f"#{channel}")
        self.viewers_label.setText(f"👁 {stream.get('viewer_count', 0):,} viewers")
        self.category_label.setText(f"🎮 {stream.get('game_name') or 'No category'}")
        self.title_label.setText(stream.get("title", "—"))
        started_at = stream.get("started_at")
        if not started_at:
            self.uptime_label.setText("⏱ —")
            return
        try:
            started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            duration = datetime.now(timezone.utc) - started
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            self.uptime_label.setText(f"⏱ {hours}h {minutes}m")
        except Exception:
            self.uptime_label.setText("⏱ —")

    def connect_chat(self, channel):
        if not channel:
            return
        self.chat_widget.channel_input.setText(channel)
        self.chat_widget.connect_to_channel()
        self.log(f"Chat connecting to #{channel}")

    def watch_selected(self):
        if not self.current_stream:
            QMessageBox.warning(self, "No Channel Selected", "Select a live channel first.")
            return
        channel = self.current_stream.get("user_login")
        if channel:
            self.start_channel(channel, manual=True)

    def start_channel(self, channel, manual=False, resume=False):
        if not channel:
            return
        channel = channel.lower().strip()
        if manual:
            self.log(f"Manual channel selection: {channel}")
        elif resume:
            self.log(f"Resuming previous channel: {channel}")
        else:
            self.log(f"Automatic channel switch: {channel}")
        try:
            self.dispatcher_status.setText(f"Status: Resolving {channel}...")
            QApplication.processEvents()
            url = self.api.get_stream_url(channel)
            if not url:
                raise RuntimeError(f"Could not resolve stream URL for {channel}")
            switched = self.dispatcher.switch_stream(streamer=channel, url=url, announce=manual)
            if not switched:
                self.log("Dispatcher rejected stream switch.")
                return
            self.current_channel = channel
            self.save_last_streamer(channel)
            self.connect_chat(channel)
            self.raid_monitor.start(channel)
            self.dispatcher_status.setText(f"Status: ▶ Watching {channel}")
            self.update_next_stream()
        except Exception as error:
            self.dispatcher_status.setText("Status: Video error")
            self.log(f"VIDEO ERROR: {error}")
            QMessageBox.critical(self, "Video Error", str(error))

    def handle_raid(self, from_channel, to_channel):
        if self.raid_transition_active:
            return
        self.raid_transition_active = True
        self.log("================================")
        self.log(f"RAID DETECTED: {from_channel} → {to_channel}")
        self.dispatcher_status.setText(f"Status: RAID {from_channel} → {to_channel}")
        try:
            switched = self.dispatcher.handle_raid(from_streamer=from_channel, to_streamer=to_channel)
            if not switched:
                self.log("Raid switch failed.")
                return
            self.current_channel = to_channel.lower().strip()
            self.save_last_streamer(self.current_channel)
            self.connect_chat(self.current_channel)
            self.raid_monitor.start(self.current_channel)
            self.log(f"Now monitoring raids from {self.current_channel}")
            self.update_next_stream()
        except Exception as error:
            self.log(f"RAID SWITCH ERROR: {error}")
            self.dispatcher_status.setText("Status: Raid switch error")
        finally:
            self.raid_transition_active = False

    def handle_raid_status(self, message):
        self.log(f"[RAID] {message}")

    def handle_raid_error(self, message):
        self.log(f"[RAID ERROR] {message}")

    def stop_video(self):
        try:
            self.raid_monitor.stop()
        except Exception:
            pass
        try:
            self.dispatcher.stop()
        except Exception as error:
            self.log(f"Dispatcher stop error: {error}")
        self.current_channel = None
        self.current_stream = None
        self.dispatcher_status.setText("Status: Video stopped")
        self.log("Video stopped.")
        self.update_next_stream()

    def closeEvent(self, event):
        debug("MainMenu.closeEvent invoked")
        if self.is_closing:
            event.accept()
            return
        self.is_closing = True
        self.save_window_geometry()
        try:
            self.video_window.save_window_state()
        except Exception as error:
            print(f"[SETTINGS] Could not save VideoWindow state: {error}")
        try:
            self.raid_monitor.stop()
        except Exception:
            pass
        try:
            self.dispatcher.shutdown()
        except Exception:
            pass
        try:
            self.chat_widget.disconnect()
        except Exception:
            pass
        try:
            self.video_window.close()
        except Exception:
            pass
        event.accept()
