from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel


class NextStreamPanel(QFrame):

    def __init__(self):

        super().__init__()
        self.setObjectName("NextCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        title = QLabel("⏭  NEXT STREAM")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #78d6c5;")
        layout.addWidget(title)

        self.next_channel_label = QLabel("No next stream selected")
        self.next_channel_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        layout.addWidget(self.next_channel_label)

        self.next_viewers_label = QLabel("👁 — viewers")
        layout.addWidget(self.next_viewers_label)

        self.next_category_label = QLabel("🎮 —")
        layout.addWidget(self.next_category_label)

        self.next_reason_label = QLabel("Waiting for live channels...")
        self.next_reason_label.setWordWrap(True)
        self.next_reason_label.setStyleSheet("color: #8baea8;")
        layout.addWidget(self.next_reason_label)

    def set_stream(self, stream):

        if not stream:
            self.clear()
            return

        channel = stream.get("user_name", "Unknown")
        viewers = stream.get("viewer_count", 0)
        category = stream.get("game_name") or "No category"

        self.next_channel_label.setText(channel)
        self.next_viewers_label.setText(f"👁 {viewers:,} viewers")
        self.next_category_label.setText(f"🎮 {category}")
        self.next_reason_label.setText(
            "If the current stream ends without a raid, Twitcher will switch here."
        )

    def clear(self):

        self.next_channel_label.setText("No next stream available")
        self.next_viewers_label.setText("👁 — viewers")
        self.next_category_label.setText("🎮 —")
        self.next_reason_label.setText(
            "No other followed channels are currently live."
        )
