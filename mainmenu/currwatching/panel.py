"""Current Watching panel — the card that shows what's playing right now.

Clean architecture with two update paths:
- ``set_stream(stream, analysis)`` — full update (header, avatar, LCD, graph,
  gauge, momentum, SullyGoose).  Called by ViewerMonitor when fresh data arrives.
- ``tick()`` — lightweight 2s refresh (LCD, graph only).  Called by timer for
  smooth viewer-count display between ViewerMonitor ticks.

All widget creation lives in
:class:`~currwatching.ui.CurrentWatchingUIBuilder`.
"""

from datetime import datetime, timezone
import logging

from PySide6.QtWidgets import QFrame

from core.db import store_viewer_history
from .theme import Theme
from .image_cache import ImageCache
from .ui import CurrentWatchingUIBuilder

logger = logging.getLogger(__name__)

# Momentum color map — defined once, reused everywhere.
_MOMENTUM_COLORS = {
    "Rising": "#00ff00",
    "Declining": "#ff4444",
}
_DEFAULT_MOMENTUM_COLOR = "#f2f2f2"

# Platform badge colors.
_BADGE_COLORS = {
    "twitch": "#9146FF",
    "kick": "#53FC18",
    "youtube": "#FF0000",
}


class CurrentWatchingPanel(QFrame):
    """Card displaying the currently-watched stream.

    Data flow:
        ViewerMonitor (2s) → update_current_stream_view() → set_stream()
            → header, LCD, graph, gauge, momentum, SG  (all at once)

        _momsg_timer (2s)  → tick()
            → LCD + graph only  (lightweight, no SG recomputation)
    """

    AVATAR_SIZE = (Theme.AVATAR_SIZE, Theme.AVATAR_SIZE)
    THUMBNAIL_SIZE = (Theme.THUMBNAIL_SIZE, Theme.THUMBNAIL_SIZE)

    #: Write viewer history to DB every N ticks (8s at 2s intervals).
    DB_WRITE_INTERVAL = 4

    def __init__(self):
        super().__init__()
        self.image_cache = ImageCache.shared()
        self._refresh_tick_count = 0
        self._last_sg_fingerprint = None
        self._current_stream = None  # cached for tick()
        self._current_analysis = None  # cached for tick()
        CurrentWatchingUIBuilder(self)

    # ================================================================
    # FULL UPDATE — called by ViewerMonitor with fresh stream data
    # ================================================================

    def set_stream(self, stream, analysis=None):
        """Full panel update: header, LCD, graph, gauge, momentum, SG."""
        if not stream:
            self.clear()
            return

        self._current_stream = stream
        self._current_analysis = analysis

        # --- Header ---
        self.channel_label.setText(f"#{stream.get('user_name', 'Unknown')}")

        # --- Platform badge ---
        platform = stream.get("platform", "twitch")
        badge_color = _BADGE_COLORS.get(platform, "#888888")
        self.platform_label.setText(platform.upper())
        self.platform_label.setStyleSheet(
            f"color: {badge_color}; font-size: 8px; font-weight: bold;"
        )

        # --- Viewer count + graph ---
        viewer_count = stream.get("viewer_count", 0)
        self.enlarged_lcd_counter.display(viewer_count)
        self.viewer_history_graph.add_point(viewer_count)
        self.neon_viewer_counter.set_active(viewer_count > 0)

        # --- Title ---
        self.title_label.setText(stream.get("title", "—"))

        # --- Avatar ---
        self.set_avatar_image(stream.get("avatar_url"))

        # --- Uptime + time labels ---
        self._update_uptime(stream.get("started_at"))
        self._update_time_labels()

        # --- Momentum + gauge + SG (from analysis) ---
        self._apply_analysis(analysis)

    # ================================================================
    # LIGHTWEIGHT TICK — called every 2s by timer for smooth LCD/graph
    # ================================================================

    def tick(self):
        """Lightweight 2s refresh: graph + DB persist only.

        The LCD is already updated by set_stream() (called every 2s by
        ViewerMonitor).  This method only adds a graph data point and
        persists viewer history to DB on a throttled schedule.
        """
        stream = self._current_stream
        if not stream:
            return

        viewer_count = stream.get("viewer_count", 0)
        self.viewer_history_graph.add_point(viewer_count)

        # Persist to DB every Nth tick (8s at 2s intervals).
        self._refresh_tick_count += 1
        if self._refresh_tick_count % self.DB_WRITE_INTERVAL == 0:
            login = (
                stream.get("user_login")
                or stream.get("user_name")
                or stream.get("channel")
                or ""
            ).lower().strip()
            if login:
                store_viewer_history(
                    login,
                    viewer_count,
                    platform=stream.get("platform", "twitch"),
                )

    # ================================================================
    # MOMENTUM + GAUGE + SG — shared logic used by set_stream
    # ================================================================

    def _apply_analysis(self, analysis):
        """Update momentum label, gauge, and SullyGoose widget from analysis."""
        if not analysis:
            self.momentum_label.setText("📊 Waiting...")
            return

        status = analysis.get("status", "")
        percent = analysis.get("percent") or 0

        # Momentum label — color-coded.
        color = _MOMENTUM_COLORS.get(status, _DEFAULT_MOMENTUM_COLOR)
        self.momentum_label.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: bold;"
        )
        self.momentum_label.setText(f"{status} {percent:+.1f}%")

        # Gauge — map percent (-50..+50) to gauge (0..100).
        self.mini_gauge.set_value(
            max(0, min(100, int(percent + 50))), "MOM"
        )

        # SullyGoose — only update when data actually changed.
        sully = analysis.get("sullygoose") or {}
        if hasattr(self, "sully_widget") and self.sully_widget:
            fingerprint = sully.get("viewer_growth")
            if fingerprint != self._last_sg_fingerprint:
                self._last_sg_fingerprint = fingerprint
                self.sully_widget.update_metrics(sully, analysis)

    # ================================================================
    # CLEAR
    # ================================================================

    def clear(self):
        """Reset all widgets to placeholder state."""
        self._current_stream = None
        self._current_analysis = None
        self._last_sg_fingerprint = None

        self.channel_label.setText("—")
        self.enlarged_lcd_counter.display(0)
        self.title_label.setText("—")
        self.momentum_label.setText("📊 Waiting...")
        self.set_avatar_image(None)
        self.neon_viewer_counter.set_active(False)

        if hasattr(self, "sully_widget") and self.sully_widget:
            self.sully_widget.update_metrics(None)

    # ================================================================
    # IMAGE LOADING
    # ================================================================

    def set_avatar_image(self, avatar_url):
        """Load broadcaster avatar asynchronously; '?' until ready."""
        self.image_cache.load(
            self.avatar_label, avatar_url,
            self.AVATAR_SIZE, placeholder="?",
        )

    def set_game_thumbnail(self, thumbnail_url):
        """Load game thumbnail asynchronously; '🎮' until ready."""
        self.image_cache.load(
            self.game_thumbnail, thumbnail_url,
            self.THUMBNAIL_SIZE, placeholder="🎮",
        )

    # ================================================================
    # TIME + UPTIME
    # ================================================================

    def _update_time_labels(self):
        now_utc = datetime.now(timezone.utc)
        now_local = datetime.now()
        self.streamer_time_label.setText(
            f"⏰ Streamer: {now_utc.strftime('%H:%M')} UTC"
        )
        self.my_time_label.setText(
            f"⏰ Me: {now_local.strftime('%H:%M')} LOCAL"
        )

    def _update_uptime(self, started_at):
        if not started_at:
            self.uptime_label.setText("⏱ —")
            return
        try:
            started = datetime.fromisoformat(
                started_at.replace("Z", "+00:00")
            )
            seconds = int((datetime.now(timezone.utc) - started).total_seconds())
            self.uptime_label.setText(
                f"⏱ {seconds // 3600}h {(seconds % 3600) // 60}m"
            )
        except Exception:
            self.uptime_label.setText("⏱ —")