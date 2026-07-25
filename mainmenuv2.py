import os
from datetime import datetime, timezone

from PySide6.QtCore import Qt, QSettings, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from chat import ChatWidget
from video import VideoWindow
from dispatcher import StreamDispatcher
from raid_monitor import RaidMonitor


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "twitcher.log")
LAST_CHANNEL_FILE = os.path.join(BASE_DIR, "last_channel.txt")


class StreamCard(QFrame):

    clicked = Signal(dict)

    def __init__(self, stream, parent=None):

        super().__init__(parent)

        self.stream = stream
        self.setObjectName("StreamCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        channel = stream.get("user_name", "Unknown")
        viewers = stream.get("viewer_count", 0)
        category = stream.get("game_name") or "No category"
        title = stream.get("title") or "No title"

        self.channel_label = QLabel(f"●  {channel}")
        self.channel_label.setFont(
            QFont("Segoe UI", 13, QFont.Weight.Bold)
        )
        self.channel_label.setStyleSheet(
            "color: #b8c1ff;"
        )

        self.viewers_label = QLabel(
            f"👁  {viewers:,} viewers"
        )

        self.category_label = QLabel(
            f"🎮  {category}"
        )

        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumHeight(42)
        self.title_label.setStyleSheet(
            "color: #858ca5;"
        )

        layout.addWidget(self.channel_label)
        layout.addWidget(self.viewers_label)
        layout.addWidget(self.category_label)
        layout.addWidget(self.title_label)

    def mousePressEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.stream)

        super().mousePressEvent(event)


class RaidIndicator(QWidget):

    def __init__(self, parent=None):

        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.light = QLabel("○")
        self.light.setFont(
            QFont("Segoe UI", 12, QFont.Weight.Bold)
        )

        self.label = QLabel("Raid monitor")
        self.label.setFont(
            QFont("Segoe UI", 9, QFont.Weight.Bold)
        )

        layout.addWidget(self.light)
        layout.addWidget(self.label)

        self.set_status("inactive")

    def set_status(self, status):

        if status == "active":

            self.light.setText("●")
            self.light.setStyleSheet(
                "color: #62d99a;"
            )

            self.label.setStyleSheet(
                "color: #82958b;"
            )

        elif status == "raid":

            self.light.setText("●")
            self.light.setStyleSheet(
                "color: #ff4355;"
            )

            self.label.setStyleSheet(
                "color: #ff6f7c;"
            )

        else:

            self.light.setText("○")
            self.light.setStyleSheet(
                "color: #45495a;"
            )

            self.label.setStyleSheet(
                "color: #666b7d;"
            )


class LogWindow(QMainWindow):

    def __init__(self, log_file):

        super().__init__()

        self.log_file = log_file

        self.setWindowTitle("Twitcher Logs")
        self.resize(950, 650)

        self.text = QTextEdit()
        self.text.setReadOnly(True)

        self.setCentralWidget(self.text)

        self.load_logs()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_logs)
        self.timer.start(1000)

    def load_logs(self):

        try:

            if not os.path.exists(self.log_file):
                self.text.setPlainText("No logs yet.")
                return

            with open(
                self.log_file,
                "r",
                encoding="utf-8"
            ) as file:

                content = file.read()

            self.text.setPlainText(content)

            scrollbar = self.text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

        except Exception:
            pass


class MainMenu(QMainWindow):

    def __init__(self, api):

        super().__init__()

        self.api = api

        self.settings = QSettings(
            "Twitcher",
            "TwitcherControlCenter"
        )

        self.user = None
        self.live_channels = []

        self.current_channel = None
        self.current_stream = None
        self.next_stream = None

        self.resume_attempted = False
        self.is_closing = False
        self.raid_transition_active = False

        self.log_window = None

        self.video_window = VideoWindow()

        self.raid_monitor = RaidMonitor(self.api)

        self.raid_monitor.signals.raid_detected.connect(
            self.handle_raid
        )

        self.raid_monitor.signals.status.connect(
            self.handle_raid_status
        )

        self.raid_monitor.signals.error.connect(
            self.handle_raid_error
        )

        self.dispatcher = StreamDispatcher(
            api=self.api,
            video_window=self.video_window,
            on_status=self.handle_dispatcher_status,
            on_log=self.handle_dispatcher_log,
            on_stream_changed=self.handle_stream_changed,
            on_raid_announcement=self.handle_raid_announcement,
        )

        self.setWindowTitle(
            "Twitcher Control Center"
        )

        self.setMinimumSize(1400, 800)

        self.build_interface()
        self.restore_window_geometry()

        self.channel_refresh_timer = QTimer(self)
        self.channel_refresh_timer.timeout.connect(
            self.load_live_channels
        )
        self.channel_refresh_timer.start(2000)

        self.load_twitch()

    def build_interface(self):

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 14, 16, 16)
        main_layout.setSpacing(12)

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
                padding: 8px 14px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #272c48;
                border: 1px solid #5964a0;
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

            QFrame#StreamCard {
                background-color: #141725;
                border: 1px solid #292e49;
                border-radius: 10px;
            }

            QFrame#StreamCard:hover {
                background-color: #1d2238;
                border: 1px solid #6672b5;
            }

            QScrollArea {
                border: none;
                background: transparent;
            }
            """
        )

        header_layout = QHBoxLayout()

        header = QLabel("TWITCHER")
        header.setFont(
            QFont(
                "Segoe UI",
                28,
                QFont.Weight.Bold
            )
        )
        header.setStyleSheet(
            "color: #aab4ff;"
        )

        subtitle = QLabel(
            "CONTROL CENTER"
        )
        subtitle.setFont(
            QFont(
                "Segoe UI",
                10,
                QFont.Weight.Bold
            )
        )
        subtitle.setStyleSheet(
            "color: #727991;"
        )

        header_layout.addWidget(header)
        header_layout.addWidget(subtitle)
        header_layout.addStretch()

        self.connection_label = QLabel(
            "● OFFLINE"
        )
        self.connection_label.setFont(
            QFont(
                "Segoe UI",
                11,
                QFont.Weight.Bold
            )
        )
        self.connection_label.setStyleSheet(
            "color: #ff7777;"
        )

        header_layout.addWidget(
            self.connection_label
        )

        self.raid_indicator = RaidIndicator()
        header_layout.addWidget(
            self.raid_indicator
        )

        self.logs_button = QPushButton("LOGS")
        self.logs_button.clicked.connect(
            self.open_logs
        )

        header_layout.addWidget(
            self.logs_button
        )

        main_layout.addLayout(
            header_layout
        )

        top_layout = QHBoxLayout()
        top_layout.setSpacing(12)

        current_card = QFrame()
        current_card.setObjectName(
            "CurrentCard"
        )

        current_layout = QVBoxLayout(
            current_card
        )

        current_title = QLabel(
            "▶  CURRENTLY WATCHING"
        )
        current_title.setFont(
            QFont(
                "Segoe UI",
                12,
                QFont.Weight.Bold
            )
        )
        current_title.setStyleSheet(
            "color: #9daaff;"
        )

        current_layout.addWidget(
            current_title
        )

        self.channel_label = QLabel("No stream")
        self.channel_label.setFont(
            QFont(
                "Segoe UI",
                22,
                QFont.Weight.Bold
            )
        )

        self.viewers_label = QLabel(
            "👁 — viewers"
        )

        self.category_label = QLabel(
            "🎮 —"
        )

        self.uptime_label = QLabel(
            "⏱ —"
        )

        self.title_label = QLabel(
            "Nothing is currently playing."
        )
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(
            "color: #a8adbd;"
        )

        current_layout.addWidget(
            self.channel_label
        )
        current_layout.addWidget(
            self.viewers_label
        )
        current_layout.addWidget(
            self.category_label
        )
        current_layout.addWidget(
            self.uptime_label
        )
        current_layout.addWidget(
            self.title_label
        )

        top_layout.addWidget(
            current_card,
            2
        )

        next_card = QFrame()
        next_card.setObjectName(
            "NextCard"
        )

        next_layout = QVBoxLayout(
            next_card
        )

        next_title = QLabel(
            "⏭  NEXT AVAILABLE"
        )
        next_title.setFont(
            QFont(
                "Segoe UI",
                12,
                QFont.Weight.Bold
            )
        )
        next_title.setStyleSheet(
            "color: #78d6c5;"
        )

        self.next_channel_label = QLabel(
            "No next stream"
        )
        self.next_channel_label.setFont(
            QFont(
                "Segoe UI",
                20,
                QFont.Weight.Bold
            )
        )

        self.next_viewers_label = QLabel(
            "👁 — viewers"
        )

        self.next_category_label = QLabel(
            "🎮 —"
        )

        self.next_reason_label = QLabel(
            "Waiting for live followed channels..."
        )
        self.next_reason_label.setWordWrap(True)
        self.next_reason_label.setStyleSheet(
            "color: #8baea8;"
        )

        next_layout.addWidget(next_title)
        next_layout.addWidget(
            self.next_channel_label
        )
        next_layout.addWidget(
            self.next_viewers_label
        )
        next_layout.addWidget(
            self.next_category_label
        )
        next_layout.addWidget(
            self.next_reason_label
        )

        top_layout.addWidget(
            next_card,
            1
        )

        main_layout.addLayout(
            top_layout
        )

        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(12)

        channels_box = QGroupBox(
            "LIVE FOLLOWED CHANNELS"
        )

        channels_layout = QVBoxLayout(
            channels_box
        )

        self.channel_scroll = QScrollArea()
        self.channel_scroll.setWidgetResizable(True)

        self.channel_container = QWidget()

        self.channel_layout = QVBoxLayout(
            self.channel_container
        )

        self.channel_layout.setContentsMargins(
            4,
            4,
            4,
            4
        )

        self.channel_layout.setSpacing(8)

        self.channel_scroll.setWidget(
            self.channel_container
        )

        channels_layout.addWidget(
            self.channel_scroll
        )

        middle_layout.addWidget(
            channels_box,
            28
        )

        chat_box = QGroupBox(
            "TWITCH CHAT"
        )

        chat_layout = QVBoxLayout(
            chat_box
        )

        token = os.getenv(
            "TWITCH_ACCESS_TOKEN",
            ""
        )

        self.chat_widget = ChatWidget(
            username="",
            access_token=token
        )

        chat_layout.addWidget(
            self.chat_widget
        )

        middle_layout.addWidget(
            chat_box,
            72
        )

        main_layout.addLayout(
            middle_layout,
            1
        )

    def log(self, message):

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        line = f"[{timestamp}] {message}"

        print(line)

        try:

            with open(
                LOG_FILE,
                "a",
                encoding="utf-8"
            ) as file:

                file.write(
                    line + "\n"
                )

        except Exception:
            pass

    def open_logs(self):

        if self.log_window is None:

            self.log_window = LogWindow(
                LOG_FILE
            )

        self.log_window.show()
        self.log_window.raise_()
        self.log_window.activateWindow()

    def save_last_channel(self, channel):

        if not channel:
            return

        try:

            with open(
                LAST_CHANNEL_FILE,
                "w",
                encoding="utf-8"
            ) as file:

                file.write(
                    channel.lower().strip()
                )

        except Exception as error:

            self.log(
                f"Could not save last channel: {error}"
            )

    def load_last_channel(self):

        try:

            if not os.path.exists(
                LAST_CHANNEL_FILE
            ):

                return ""

            with open(
                LAST_CHANNEL_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                return file.read().strip().lower()

        except Exception:

            return ""

    def load_twitch(self):

        try:

            self.user = self.api.get_current_user()

            self.connection_label.setText(
                "● CONNECTED"
            )

            self.connection_label.setStyleSheet(
                "color: #72d6a0;"
            )

            self.log(
                f"Logged in as "
                f"{self.user['display_name']}"
            )

            self.chat_widget.username = (
                self.user["login"]
            )

            self.load_live_channels()

        except Exception as error:

            self.connection_label.setText(
                "● ERROR"
            )

            self.connection_label.setStyleSheet(
                "color: #ff7777;"
            )

            self.log(
                f"TWITCH ERROR: {error}"
            )

            QMessageBox.critical(
                self,
                "Twitch Error",
                str(error)
            )

    def load_live_channels(self):

        if not self.user:
            return

        try:

            followed = self.api.get_followed_channels(
                self.user["id"]
            )

            streams = self.api.get_live_streams(
                followed
            )

            self.live_channels = sorted(
                streams,
                key=lambda stream: stream.get(
                    "viewer_count",
                    0
                ),
                reverse=True
            )

            self.rebuild_channel_cards()
            self.update_current_stream_data()
            self.update_next_stream()

            if not self.resume_attempted:

                self.try_resume_last_streamer()

        except Exception as error:

            self.log(
                f"CHANNEL REFRESH ERROR: {error}"
            )

    def rebuild_channel_cards(self):

        while self.channel_layout.count():

            item = self.channel_layout.takeAt(0)

            widget = item.widget()

            if widget:
                widget.deleteLater()

        current = (
            self.current_channel
            or ""
        ).lower().strip()

        streams = [

            stream

            for stream in self.live_channels

            if stream.get(
                "user_login",
                ""
            ).lower().strip()
            != current

        ]

        streams = streams[:7]

        if not streams:

            empty = QLabel(
                "No other followed channels are live."
            )

            empty.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            empty.setStyleSheet(
                "color: #777d91; padding: 30px;"
            )

            self.channel_layout.addWidget(
                empty
            )

        else:

            for stream in streams:

                card = StreamCard(stream)

                card.clicked.connect(
                    self.channel_card_clicked
                )

                self.channel_layout.addWidget(
                    card
                )

        self.channel_layout.addStretch()

    def channel_card_clicked(self, stream):

        channel = stream.get(
            "user_login",
            ""
        )

        if not channel:
            return

        self.start_channel(
            channel,
            manual=True
        )

    def update_current_stream_data(self):

        if not self.current_channel:
            return

        current = self.current_channel.lower().strip()

        for stream in self.live_channels:

            login = stream.get(
                "user_login",
                ""
            ).lower().strip()

            if login == current:

                self.current_stream = stream
                self.update_current_broadcast(
                    stream
                )

                return

    def update_current_broadcast(self, stream):

        channel = stream.get(
            "user_name",
            "Unknown"
        )

        self.channel_label.setText(
            f"#{channel}"
        )

        self.viewers_label.setText(
            f"👁 {stream.get('viewer_count', 0):,} viewers"
        )

        self.category_label.setText(
            f"🎮 {stream.get('game_name') or 'No category'}"
        )

        self.title_label.setText(
            stream.get(
                "title",
                "—"
            )
        )

        started_at = stream.get(
            "started_at"
        )

        if not started_at:

            self.uptime_label.setText(
                "⏱ —"
            )

            return

        try:

            started = datetime.fromisoformat(
                started_at.replace(
                    "Z",
                    "+00:00"
                )
            )

            seconds = int(
                (
                    datetime.now(timezone.utc)
                    - started
                ).total_seconds()
            )

            hours = seconds // 3600
            minutes = (seconds % 3600) // 60

            self.uptime_label.setText(
                f"⏱ {hours}h {minutes}m"
            )

        except Exception:

            self.uptime_label.setText(
                "⏱ —"
            )

    def update_next_stream(self):

        current = (
            self.current_channel
            or ""
        ).lower().strip()

        candidates = [

            stream

            for stream in self.live_channels

            if stream.get(
                "user_login",
                ""
            ).lower().strip()
            != current

        ]

        if not candidates:

            self.next_stream = None

            self.next_channel_label.setText(
                "No next stream"
            )

            self.next_viewers_label.setText(
                "👁 — viewers"
            )

            self.next_category_label.setText(
                "🎮 —"
            )

            self.next_reason_label.setText(
                "No other followed channels are live."
            )

            return

        self.next_stream = candidates[0]

        channel = self.next_stream.get(
            "user_name",
            "Unknown"
        )

        viewers = self.next_stream.get(
            "viewer_count",
            0
        )

        category = (
            self.next_stream.get(
                "game_name"
            )
            or
            "No category"
        )

        self.next_channel_label.setText(
            channel
        )

        self.next_viewers_label.setText(
            f"👁 {viewers:,} viewers"
        )

        self.next_category_label.setText(
            f"🎮 {category}"
        )

        self.next_reason_label.setText(
            "Best available live followed channel."
        )

    def try_resume_last_streamer(self):

        self.resume_attempted = True

        saved_channel = self.load_last_channel()

        if not saved_channel:

            if self.live_channels:

                channel = self.live_channels[0].get(
                    "user_login",
                    ""
                )

                if channel:

                    self.start_channel(
                        channel,
                        resume=True
                    )

            return

        for stream in self.live_channels:

            login = stream.get(
                "user_login",
                ""
            ).lower().strip()

            if login == saved_channel:

                self.log(
                    f"Resuming last channel: #{saved_channel}"
                )

                self.start_channel(
                    saved_channel,
                    resume=True
                )

                return

        if self.live_channels:

            fallback = self.live_channels[0].get(
                "user_login",
                ""
            )

            if fallback:

                self.log(
                    f"Last channel #{saved_channel} is offline. "
                    f"Starting #{fallback}"
                )

                self.start_channel(
                    fallback,
                    resume=True
                )

    def connect_chat(self, channel):

        if not channel:
            return

        try:

            self.chat_widget.channel_input.setText(
                channel
            )

            self.chat_widget.connect_to_channel()

            self.log(
                f"Chat connecting to #{channel}"
            )

        except Exception as error:

            self.log(
                f"CHAT ERROR: {error}"
            )

    def start_channel(
        self,
        channel,
        manual=False,
        resume=False
    ):

        if not channel:
            return

        channel = channel.lower().strip()

        if not channel:
            return

        self.log(
            f"Switching to #{channel}"
        )

        try:

            url = self.api.get_stream_url(
                channel
            )

            if not url:

                raise RuntimeError(
                    f"Could not resolve stream URL for #{channel}"
                )

            switched = self.dispatcher.switch_stream(
                streamer=channel,
                url=url,
                announce=manual
            )

            if not switched:

                self.log(
                    "Stream switch was rejected."
                )

                return

            self.current_channel = channel

            self.save_last_channel(
                channel
            )

            self.connect_chat(
                channel
            )

            self.raid_monitor.start(
                channel
            )

            self.raid_indicator.set_status(
                "active"
            )

            self.update_current_stream_data()
            self.update_next_stream()
            self.rebuild_channel_cards()

        except Exception as error:

            self.log(
                f"VIDEO ERROR: {error}"
            )

            QMessageBox.critical(
                self,
                "Video Error",
                str(error)
            )

    def handle_raid(
        self,
        from_channel,
        to_channel
    ):

        if self.raid_transition_active:
            return

        self.raid_transition_active = True

        self.raid_indicator.set_status(
            "raid"
        )

        self.log(
            f"RAID DETECTED: "
            f"{from_channel} -> {to_channel}"
        )

        try:

            switched = self.dispatcher.handle_raid(
                from_streamer=from_channel,
                to_streamer=to_channel
            )

            if not switched:
                return

            self.current_channel = (
                to_channel.lower().strip()
            )

            self.save_last_channel(
                self.current_channel
            )

            self.connect_chat(
                self.current_channel
            )

            self.raid_monitor.start(
                self.current_channel
            )

            self.raid_indicator.set_status(
                "active"
            )

            self.update_current_stream_data()
            self.update_next_stream()
            self.rebuild_channel_cards()

        except Exception as error:

            self.log(
                f"RAID SWITCH ERROR: {error}"
            )

        finally:

            self.raid_transition_active = False

    def handle_raid_status(self, message):

        self.log(
            f"[RAID] {message}"
        )

    def handle_raid_error(self, message):

        self.raid_indicator.set_status(
            "inactive"
        )

        self.log(
            f"[RAID ERROR] {message}"
        )

    def handle_dispatcher_status(self, message):

        self.log(
            f"[STREAM] {message}"
        )

    def handle_dispatcher_log(self, message):

        self.log(
            f"[STREAM] {message}"
        )

    def handle_stream_changed(self, data):

        channel = data.get(
            "streamer",
            ""
        )

        if not channel:
            return

        self.current_channel = (
            channel.lower().strip()
        )

        self.save_last_channel(
            self.current_channel
        )

        self.update_current_stream_data()
        self.update_next_stream()
        self.rebuild_channel_cards()

    def handle_raid_announcement(self, data):

        self.log(
            f"RAID ANNOUNCEMENT: {data}"
        )

    def restore_window_geometry(self):

        geometry = self.settings.value(
            "main_window_geometry"
        )

        if geometry:

            try:
                self.restoreGeometry(
                    geometry
                )

            except Exception:
                pass

    def save_window_geometry(self):

        self.settings.setValue(
            "main_window_geometry",
            self.saveGeometry()
        )

        self.settings.sync()

    def closeEvent(self, event):

        if self.is_closing:

            event.accept()
            return

        self.is_closing = True

        self.save_window_geometry()

        try:
            self.channel_refresh_timer.stop()
        except Exception:
            pass

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