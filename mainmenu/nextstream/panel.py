"""Next Stream Panel — displays information about the next stream."""

from PySide6.QtGui import QFont, QPixmap
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
)
from ..theme import Theme


class NextStreamPanel(QFrame):
    """Next stream card with analytics metrics and switch button."""

    watch_requested = Signal(str)

    def __init__(self, analytics_engine=None):
        super().__init__()
        self.setObjectName("NextCard")
        self.setStyleSheet(Theme.frame_style())
        self._analytics = analytics_engine
        self._current_channel = None
        self._current_stream = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # --- Title ---
        title = QLabel("NEXT STREAM")
        title.setFont(QFont(Theme.FAMILY, 9, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Theme.TEAL}; letter-spacing: 1px;")
        layout.addWidget(title)

        # --- Channel row (avatar + name + platform) ---
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

        self.next_platform_label = QLabel("")
        self.next_platform_label.setStyleSheet(
            "color: #888888; font-size: 8px; font-weight: bold;"
        )
        channel_row.addWidget(self.next_platform_label)
        layout.addLayout(channel_row)

        # --- Metrics row ---
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(12)

        # Viewers
        self.next_viewers_label = QLabel("--")
        self.next_viewers_label.setStyleSheet(
            f"color: {Theme.TEXT_SECONDARY}; font-size: 11px;"
        )
        metrics_row.addWidget(self.next_viewers_label)

        # Growth
        self.next_growth_label = QLabel("")
        self.next_growth_label.setStyleSheet(
            f"color: {Theme.GREEN}; font-size: 11px; font-weight: bold;"
        )
        metrics_row.addWidget(self.next_growth_label)

        # Score
        self.next_score_label = QLabel("")
        self.next_score_label.setStyleSheet(
            f"color: {Theme.CYAN}; font-size: 11px; font-weight: bold;"
        )
        metrics_row.addWidget(self.next_score_label)

        metrics_row.addStretch()
        layout.addLayout(metrics_row)

        # --- Category ---
        self.next_category_label = QLabel("--")
        self.next_category_label.setStyleSheet(
            f"color: {Theme.MUTED}; font-size: 10px;"
        )
        layout.addWidget(self.next_category_label)

        # --- Analytics reason ---
        self.next_reason_label = QLabel("Waiting for analytics...")
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

    def set_analytics_engine(self, analytics):
        """Inject the analytics engine for data fetching."""
        self._analytics = analytics

    def _on_switch_clicked(self):
        channel = getattr(self, "_current_channel", None)
        if channel:
            self.watch_requested.emit(channel)

    def set_stream(self, stream):
        if not stream:
            self.clear()
            return

        self._current_stream = stream
        channel = stream.get("user_name", "Unknown")
        viewers = stream.get("viewer_count", 0)
        category = stream.get("game_name") or "No category"

        self._current_channel = stream.get("user_login") or channel.lower()
        self.next_channel_label.setText(channel)

        # --- Platform badge ---
        platform = stream.get("platform", "twitch")
        badge_colors = {
            "twitch": "#9146FF",
            "kick": "#53FC18",
            "youtube": "#FF0000",
        }
        badge_color = badge_colors.get(platform, "#888888")
        self.next_platform_label.setText(platform.upper())
        self.next_platform_label.setStyleSheet(
            f"color: {badge_color}; font-size: 8px; font-weight: bold;"
        )

        self.next_viewers_label.setText(f"{viewers:,} viewers")
        self.next_category_label.setText(category)
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

        # Fetch analytics data for this stream
        self._fetch_analytics()

    def _fetch_analytics(self):
        """Fetch analytics data for the current next stream."""
        if not self._analytics or not self._current_channel:
            return

        platform = "twitch"
        if self._current_stream:
            platform = self._current_stream.get("platform", "twitch")

        # Get external analytics data
        data = self._analytics.get_external_data(self._current_channel, platform)
        if data:
            self._update_analytics_ui(data)
        else:
            self.next_reason_label.setText("Analytics loading...")

    def _update_analytics_ui(self, data):
        """Update UI with analytics metrics."""
        # Growth
        growth = data.get("viewer_growth", 0)
        if growth is not None:
            growth_text = f"{growth:+.1f}%"
            self.next_growth_label.setText(growth_text)
            if growth > 0:
                self.next_growth_label.setStyleSheet(
                    f"color: {Theme.GREEN}; font-size: 11px; font-weight: bold;"
                )
            elif growth < 0:
                self.next_growth_label.setStyleSheet(
                    f"color: {Theme.RED_DARK}; font-size: 11px; font-weight: bold;"
                )
            else:
                self.next_growth_label.setStyleSheet(
                    f"color: {Theme.TEXT_SECONDARY}; font-size: 11px; font-weight: bold;"
                )

        # Score
        score = data.get("score")
        if score is None and self._analytics:
            # Calculate score from viewers + data
            viewers = 0
            if self._current_stream:
                viewers = int(self._current_stream.get("viewer_count", 0))
            score = self._analytics.calculate_score({
                "viewers": viewers,
                "sullygoose": data,
            })
        if score is not None:
            self.next_score_label.setText(f"Score: {score}")

        # Reason based on analytics
        reliability = data.get("reliability_score", 0)
        discovery = data.get("discovery_score", 0)
        chat_activity = data.get("chat_activity", "Unknown")

        reason_parts = []
        if reliability >= 80:
            reason_parts.append("Reliable schedule")
        if discovery >= 70:
            reason_parts.append("Growing audience")
        if chat_activity == "High":
            reason_parts.append("Active chat")

        if reason_parts:
            self.next_reason_label.setText(" • ".join(reason_parts))
        else:
            self.next_reason_label.setText(" analytics available")

    def clear(self):
        self._current_channel = None
        self._current_stream = None
        self.next_channel_label.setText("--")
        self.next_platform_label.setText("")
        self.next_viewers_label.setText("--")
        self.next_growth_label.setText("")
        self.next_score_label.setText("")
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
