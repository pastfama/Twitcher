"""Next Stream Panel — AI-powered next stream recommendation card.

Features:
- Channel info with avatar and platform badge
- AI comparison bars (current vs next)
- AI-generated reasoning and prediction
- Glowing switch button when next stream is significantly better
"""

from PySide6.QtGui import QFont, QPixmap, QColor
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QProgressBar, QGraphicsDropShadowEffect, QWidget,
)
from ..theme import Theme
from logger import debug


class _ComparisonBar(QWidget):
    """A horizontal bar comparing current vs next stream on a metric."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(18)
        self._current_val = 0
        self._next_val = 0
        self._label = label

    def set_values(self, current: float, next_val: float):
        self._current_val = max(0, current)
        self._next_val = max(0, next_val)
        self.update()

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Label
        p.setPen(QColor(Theme.MUTED))
        p.setFont(QFont("Segoe UI", 7))
        p.drawText(0, 0, 60, h, Qt.AlignmentFlag.AlignVCenter, self._label)

        bar_x = 62
        bar_w = w - bar_x - 4
        mid = bar_x + bar_w // 2

        total = max(self._current_val + self._next_val, 1)
        curr_w = int(bar_w * 0.45 * self._current_val / max(total * 0.5, 1))
        next_w = int(bar_w * 0.45 * self._next_val / max(total * 0.5, 1))

        # Current bar (left-aligned, muted)
        p.setBrush(QColor(Theme.SECTION_BORDER))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(bar_x, 3, curr_w, h - 6, 2, 2)

        # Next bar (right of center, teal or green if better)
        next_color = Theme.TEAL if self._next_val >= self._current_val else Theme.ORANGE
        p.setBrush(QColor(next_color))
        p.drawRoundedRect(bar_x + curr_w + 2, 3, next_w, h - 6, 2, 2)

        p.end()


class NextStreamPanel(QFrame):
    """Next stream card with AI comparison and recommendation."""

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
        layout.setSpacing(4)

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

        self.next_viewers_label = QLabel("--")
        self.next_viewers_label.setStyleSheet(
            f"color: {Theme.TEXT_SECONDARY}; font-size: 11px;"
        )
        metrics_row.addWidget(self.next_viewers_label)

        self.next_growth_label = QLabel("")
        self.next_growth_label.setStyleSheet(
            f"color: {Theme.GREEN}; font-size: 11px; font-weight: bold;"
        )
        metrics_row.addWidget(self.next_growth_label)

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

        # --- AI Comparison bars ---
        self._comp_viewers = _ComparisonBar("Viewers")
        self._comp_score = _ComparisonBar("Score")
        self._comp_chat = _ComparisonBar("Chat")
        self._comp_growth = _ComparisonBar("Growth")
        layout.addWidget(self._comp_viewers)
        layout.addWidget(self._comp_score)
        layout.addWidget(self._comp_chat)
        layout.addWidget(self._comp_growth)

        # --- AI Reasoning ---
        self.next_reason_label = QLabel("Waiting for analytics...")
        self.next_reason_label.setWordWrap(True)
        self.next_reason_label.setStyleSheet(
            f"color: {Theme.DIM}; font-size: 9px; padding: 4px; "
            f"border: 1px solid {Theme.SECTION_BORDER}; border-radius: 3px; "
            f"background-color: {Theme.DARK_PANEL};"
        )
        layout.addWidget(self.next_reason_label)

        # --- Switch Now button ---
        self.switch_button = QPushButton("SWITCH NOW")
        self.switch_button.setFont(QFont(Theme.FAMILY, 9, QFont.Weight.Bold))
        self._set_switch_style(glowing=False)
        self.switch_button.clicked.connect(self._on_switch_clicked)
        layout.addWidget(self.switch_button)

    def _set_switch_style(self, glowing: bool = False):
        """Set switch button style, optionally with a glow effect."""
        if glowing:
            self.switch_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Theme.TEAL};
                    color: #000000;
                    border: 2px solid {Theme.GREEN};
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background-color: {Theme.GREEN};
                }}
            """)
            # Add glow effect
            glow = QGraphicsDropShadowEffect(self.switch_button)
            glow.setBlurRadius(16)
            glow.setColor(QColor(Theme.TEAL))
            glow.setOffset(0, 0)
            self.switch_button.setGraphicsEffect(glow)
        else:
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
            self.switch_button.setGraphicsEffect(None)

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
        """Fetch AI analytics data for the current next stream."""
        if not self._analytics or not self._current_channel:
            return

        platform = "twitch"
        if self._current_stream:
            platform = self._current_stream.get("platform", "twitch")

        # Get AI analysis data from DB
        ai_data = self._analytics.get_ai_analysis(self._current_channel, platform)
        if ai_data:
            self._update_analytics_ui(ai_data)
        else:
            # No AI data — show basic info from viewer count
            viewers = 0
            if self._current_stream:
                viewers = int(self._current_stream.get("viewer_count", 0))
            # Calculate simple score
            if viewers >= 10000:
                score = 75
            elif viewers >= 1000:
                score = 50
            elif viewers >= 100:
                score = 25
            else:
                score = 10
            self.next_score_label.setText(f"Score: {score}")
            self.next_growth_label.setText("--")
            self.next_reason_label.setText(
                f"{viewers:,} viewers" if viewers else "No analytics data"
            )

    def _update_analytics_ui(self, ai_data):
        """Update UI with AI analytics metrics."""
        # Growth (momentum)
        momentum_percent = ai_data.get("momentum_percent", 0)
        growth_text = f"{momentum_percent:+.1f}%"
        self.next_growth_label.setText(growth_text)
        if momentum_percent > 0:
            self.next_growth_label.setStyleSheet(
                f"color: {Theme.GREEN}; font-size: 11px; font-weight: bold;"
            )
        elif momentum_percent < 0:
            self.next_growth_label.setStyleSheet(
                f"color: {Theme.RED_DARK}; font-size: 11px; font-weight: bold;"
            )
        else:
            self.next_growth_label.setStyleSheet(
                f"color: {Theme.TEXT_SECONDARY}; font-size: 11px; font-weight: bold;"
            )

        # Score
        score = ai_data.get("quality_score", 0)
        if score:
            self.next_score_label.setText(f"Score: {score}")

        # Reason based on AI insights
        recommendations = ai_data.get("recommendations", [])
        if recommendations:
            # Show first recommendation as reason
            self.next_reason_label.setText(recommendations[0])
        elif ai_data.get("ai_insight"):
            self.next_reason_label.setText(ai_data.get("ai_insight"))
        else:
            self.next_reason_label.setText("AI analysis available")

    def update_comparison(self, current_metrics: dict, next_metrics: dict):
        """Update the comparison bars between current and next stream."""
        self._comp_viewers.set_values(
            current_metrics.get("viewers", 0),
            next_metrics.get("viewers", 0),
        )
        self._comp_score.set_values(
            current_metrics.get("score", 0),
            next_metrics.get("score", 0),
        )
        self._comp_chat.set_values(
            current_metrics.get("chat_rate", 0),
            next_metrics.get("chat_rate", 0),
        )
        self._comp_growth.set_values(
            abs(current_metrics.get("velocity", 0)),
            abs(next_metrics.get("velocity", 0)),
        )

        # Determine if the switch button should glow
        next_viewers = next_metrics.get("viewers", 0)
        curr_viewers = current_metrics.get("viewers", 1)
        next_score = next_metrics.get("score", 0)
        curr_score = current_metrics.get("score", 1)

        # Glow if next stream has 50%+ more viewers or 20+ higher score
        should_glow = (
            (next_viewers > curr_viewers * 1.5 and next_viewers > 100)
            or (next_score > curr_score + 20)
        )
        self._set_switch_style(glowing=should_glow)

        # Generate AI comparison text
        self._generate_ai_reasoning(current_metrics, next_metrics)

    def _generate_ai_reasoning(self, current: dict, next_s: dict):
        """Generate AI comparison reasoning in background."""
        import threading

        def bg():
            try:
                from core.sk_engine import generate_comparison
                text = generate_comparison(current, next_s)
                if text:
                    from PySide6.QtCore import QMetaObject, Q_ARG
                    QMetaObject.invokeMethod(
                        self.next_reason_label, "setText",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, text)
                    )
            except Exception as e:
                debug(f"[NEXT STREAM] AI comparison error: {e}")

        threading.Thread(target=bg, daemon=True).start()

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
