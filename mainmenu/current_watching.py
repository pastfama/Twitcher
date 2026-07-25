from datetime import datetime, timezone
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel


class CurrentWatchingPanel(QFrame):

    def __init__(self):

        super().__init__()
        self.setObjectName("CurrentCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        title = QLabel("▶  CURRENTLY WATCHING")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #9daaff;")
        layout.addWidget(title)

        self.channel_label = QLabel("—")
        self.channel_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        layout.addWidget(self.channel_label)

        self.viewers_label = QLabel("👁 — viewers")
        layout.addWidget(self.viewers_label)

        self.category_label = QLabel("🎮 —")
        layout.addWidget(self.category_label)

        self.uptime_label = QLabel("⏱ —")
        layout.addWidget(self.uptime_label)

        self.title_label = QLabel("—")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("color: #a8adbd;")
        layout.addWidget(self.title_label)

    def set_stream(self, stream):

        if not stream:
            self.clear()
            return

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
            seconds = int((datetime.now(timezone.utc) - started).total_seconds())
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            self.uptime_label.setText(f"⏱ {hours}h {minutes}m")
        except Exception:
            self.uptime_label.setText("⏱ —")

    def clear(self):

        self.channel_label.setText("—")
        self.viewers_label.setText("👁 — viewers")
        self.category_label.setText("🎮 —")
        self.uptime_label.setText("⏱ —")
        self.title_label.setText("—")
