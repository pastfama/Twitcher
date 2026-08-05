"""Next Stream Panel — displays information about the next stream."""

from PySide6.QtGui import QFont, QPixmap
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
)
from ..theme import Theme


class NextStreamPanel(QFrame):
    """Next stream card with thumbnail, avatar, trend, and switch button."""

    watch_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("NextCard")
        self.setStyleSheet(Theme.frame_style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # --- Title ---
        title = QLabel("NEXT STREAM")
        title.setFont(QFont(Theme.FAMILY, 9, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Theme.TEAL}; letter-spacing: 1px;")
        layout.addWidget(title)

        # --- Thumbnail ---
        self.next_thumbnail = QLabel()
        self.next_thumbnail.setFixedSize(160, 90)
        self.next_thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_thumbnail.setStyleSheet(f"""
            background-color: {Theme.DARK_PANEL};
            border: 1px solid {Theme.SECTION_BORDER};
            border-radius: 6px;
            color: {Theme.DIM};
            font-size: 11px;
        """)
        self.next_thumbnail.setText("--")
        layout.addWidget(self.next_thumbnail)

        # --- Channel row (avatar + name) ---
        channel_row = QHBoxLayout()
        channel_row.setSpacing(6)

        self.next_avatar_label = QLabel()
        self.next_avatar_label.setFixedSize(32, 32)
        self.next_avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_avatar_label.setStyleSheet(f"""
            background-color: {Theme.AVATAR_BG};
            border: 1px solid {Theme.SECTION_BORDER};
            border-radius: 16px;
            color: {Theme.DIM};
            font-size: 10px;
        """)
        self.next_avatar_label.setText("?")
        channel_row.addWidget(self.next_avatar_label)

        self.next_channel_label = QLabel("--")
        self.next_channel_label.setFont(QFont(Theme.FAMILY, 13, QFont.Weight.Bold))
        self.next_channel_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        channel_row.addWidget(self.next_channel_label, 1)
        layout.addLayout(channel_row)

        # --- Viewers + trend row ---
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)

        self.next_viewers_label = QLabel("--")
        self.next_viewers_label.setStyleSheet(
            f"color: {Theme.TEXT_SECONDARY}; font-size: 11px;"
        )
        stats_row.addWidget(self.next_viewers_label)

        self.next_trend_label = QLabel("")
        self.next_trend_label.setStyleSheet(
            f"color: {Theme.GREEN}; font-size: 11px; font-weight: bold;"
        )
        stats_row.addWidget(self.next_trend_label)

        stats_row.addStretch()
        layout.addLayout(stats_row)

        # --- Category ---
        self.next_category_label = QLabel("--")
        self.next_category_label.setStyleSheet(
            f"color: {Theme.MUTED}; font-size: 10px;"
        )
        layout.addWidget(self.next_category_label)

        # --- Reason ---
        self.next_reason_label = QLabel("Waiting for live channels...")
        self.next_reason_label.setWordWrap(True)
        self.next_reason_label.setStyleSheet(
            f"color: {Theme.DIM}; font-size: 9px;"
        )
        layout.addWidget(self.next_reason_label)

        # --- Switch Now button ---
        self.switch_button = QPushButton("SWITCH NOW")
        self.switch_button.setFont(QFont(Theme.FAMILY, 9, QFont.Weight.Bold))
        self.switch_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.DARK_PANEL};
                color: {Theme.TEAL};
                border: 1px solid {Theme.TEAL};
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Theme.TEAL};
                color: #000000;
            }}
            QPushButton:pressed {{
                background-color: #0a5c52;
            }}
        """)
        self.switch_button.clicked.connect(self._on_switch_clicked)
        layout.addWidget(self.switch_button)

    def _on_switch_clicked(self):
        channel = getattr(self, "_current_channel", None)
        if channel:
            self.watch_requested.emit(channel)

    def set_stream(self, stream):
        if not stream:
            self.clear()
            return

        channel = stream.get("user_name", "Unknown")
        viewers = stream.get("viewer_count", 0)
        category = stream.get("game_name") or "No category"

        self._current_channel = stream.get("user_login") or channel.lower()
        self.next_channel_label.setText(channel)
        self.next_viewers_label.setText(f"  {viewers:,} viewers")
        self.next_category_label.setText(category)
        self.next_reason_label.setText(
            "If the current stream ends without a raid, Watcher will switch here."
        )
        self.switch_button.setEnabled(True)
        self.switch_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.DARK_PANEL};
                color: {Theme.TEAL};
                border: 1px solid {Theme.TEAL};
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Theme.TEAL};
                color: #000000;
            }}
        """)

    def clear(self):
        self._current_channel = None
        self.next_channel_label.setText("--")
        self.next_viewers_label.setText("--")
        self.next_trend_label.setText("")
        self.next_category_label.setText("--")
        self.next_reason_label.setText(
            "No other followed channels are currently live."
        )
        self.switch_button.setEnabled(False)
        self.switch_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.DARK_PANEL};
                color: {Theme.DIM};
                border: 1px solid {Theme.LIGHT_INACTIVE};
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }}
        """)