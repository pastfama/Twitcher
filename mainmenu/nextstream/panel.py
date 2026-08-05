"""Next Stream Panel — shows the next live channel to auto-switch to.

Clean rewrite with:
- Avatar + thumbnail loading via ImageCache
- Consistent styling via module-level constants
- Properly connected watch_requested signal
"""

from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
)
from ..theme import Theme
from ..currwatching.image_cache import ImageCache
from widgets.base import SizeVariant
from widgets.sullygoose import SullyGooseWidget
from widgets.mom import AnalogGauge

# Badge colors centralized in Theme.BADGE_COLORS

# --- Button styles ---
_ACTIVE_BTN_STYLE = f"""
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
"""

_INACTIVE_BTN_STYLE = f"""
    QPushButton {{
        background-color: {Theme.DARK_PANEL};
        color: {Theme.DIM};
        border: 1px solid {Theme.LIGHT_INACTIVE};
        border-radius: 4px;
        padding: 6px 12px;
        font-weight: bold;
    }}
"""


class NextStreamPanel(QFrame):
    """Compact card showing the next stream in queue.

    Layout:
        ┌─────────────────────────────┐
        │  NEXT STREAM                │
        │  [thumb]  #channel  TWITCH  │
        │           👤 name           │
        │  👁 12,345   📈 Rising      │
        │  Category: Just Chatting    │
        │  Auto-switch reason...      │
        │  [  SWITCH NOW  ]           │
        └─────────────────────────────┘
    """

    watch_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self._current_channel = None
        self.image_cache = ImageCache.shared()
        self._init_ui()

    def _init_ui(self):
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

        # --- Channel row (avatar + name + platform) ---
        channel_row = QHBoxLayout()
        channel_row.setSpacing(6)

        self.next_avatar_label = QLabel()
        self.next_avatar_label.setFixedSize(32, 32)
        self.next_avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_avatar_label.setStyleSheet(
            f"background-color: {Theme.AVATAR_BG}; "
            f"border: 1px solid {Theme.SECTION_BORDER}; "
            f"border-radius: 16px; color: {Theme.DIM}; font-size: 10px;"
        )
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

        # --- S-size analytics widgets (compact) ---
        analytics_row = QHBoxLayout()
        analytics_row.setSpacing(6)

        self.next_mom_gauge = AnalogGauge(variant=SizeVariant.S)
        analytics_row.addWidget(self.next_mom_gauge)

        self.next_sg_widget = SullyGooseWidget(size=SizeVariant.S)
        analytics_row.addWidget(self.next_sg_widget, 1)

        layout.addLayout(analytics_row)

        # Log widget init
        import logging
        logging.getLogger(__name__).debug(
            "[WIDGET] NextStream: AnalogGauge (S) 50x50px + SullyGooseWidget (S) 5 metrics + 2 bars"
        )

        # --- Category ---
        self.next_category_label = QLabel("--")
        self.next_category_label.setStyleSheet(
            f"color: {Theme.MUTED}; font-size: 10px;"
        )
        layout.addWidget(self.next_category_label)

        # (Reason and SWITCH NOW button removed to save space)

    # ================================================================
    # PUBLIC API
    # ================================================================

    def set_stream(self, stream):
        """Update the panel with the next stream's data."""
        if not stream:
            self.clear()
            return

        channel = stream.get("user_name", "Unknown")
        viewers = stream.get("viewer_count", 0)
        category = stream.get("game_name") or "No category"
        platform = stream.get("platform", "twitch")
        avatar_url = stream.get("avatar_url")
        trend = stream.get("trend", "")

        self._current_channel = stream.get("user_login") or channel.lower()

        # Channel name
        self.next_channel_label.setText(channel)

        # Platform badge
        badge_color = Theme.BADGE_COLORS.get(platform, "#888888")
        self.next_platform_label.setText(platform.upper())
        self.next_platform_label.setStyleSheet(
            f"color: {badge_color}; font-size: 8px; font-weight: bold;"
        )

        # Viewers
        self.next_viewers_label.setText(f"  {viewers:,} viewers")

        # Trend
        if trend:
            self.next_trend_label.setText(trend)
        else:
            self.next_trend_label.setText("")

        # Category
        self.next_category_label.setText(category)

        # (Reason text removed)

        # Avatar
        self.image_cache.load(
            self.next_avatar_label, avatar_url,
            (32, 32), placeholder="?",
        )

        # S-size analytics widgets
        self._update_analytics(stream)


    def _update_analytics(self, stream):
        """Update S-size MOM gauge and SG widget with analytics data."""
        login = stream.get("user_login") or stream.get("user_name") or ""
        login = login.lower().strip()
        viewers = int(stream.get("viewer_count", 0))
        platform = stream.get("platform", "twitch")

        # MOM gauge — show viewer momentum if available
        # Default to 50 (stable) when no trend data
        momentum = stream.get("trend_momentum", 50)
        self.next_mom_gauge.set_value(momentum, "MOM")

        # SG widget — look up cached SullyGoose data
        sully = None
        try:
            # Access analytics engine via the parent MainMenu
            # The panel doesn't hold a direct reference, so we look it up
            # through the app's analytics engine
            app = self.window()
            if app and hasattr(app, 'analytics_engine'):
                sully = app.analytics_engine.sullygoose_for(
                    login, viewers, platform=platform
                )
        except Exception:
            pass

        if sully:
            self.next_sg_widget.update_metrics(sully, {"score": 0})

    def clear(self):
        """Reset to empty state."""
        self._current_channel = None
        self.next_channel_label.setText("--")
        self.next_platform_label.setText("")
        self.next_viewers_label.setText("--")
        self.next_trend_label.setText("")
        self.next_category_label.setText("--")
        self.next_avatar_label.setText("?")

        # Clear analytics widgets
        self.next_mom_gauge.set_value(50, "MOM")
        self.next_sg_widget.update_metrics(None)

    # ================================================================
    # INTERNAL
    # ================================================================

    def _on_switch_clicked(self):
        if self._current_channel:
            self.watch_requested.emit(self._current_channel)