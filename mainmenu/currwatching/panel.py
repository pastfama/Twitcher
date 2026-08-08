"""Current Watching panel — the card that shows what's playing right now.

Business logic only.  All widget creation lives in
:class:`~currwatching.ui.CurrentWatchingUIBuilder`; this class owns the
state-update methods (:meth:`set_stream`, :meth:`clear`,
:meth:`set_viewer_status`) and the async image-loading helpers that
delegate to the shared :class:`~currwatching.image_cache.ImageCache`.
"""

from datetime import datetime, timezone
import logging

from PySide6.QtWidgets import QFrame

from core.db import store_viewer_history
from .theme import Theme
from .image_cache import ImageCache
from .ui import CurrentWatchingUIBuilder

# Logger for currwatching module
logger = logging.getLogger(__name__)


class CurrentWatchingPanel(QFrame):
    """Card displaying the currently-watched stream: avatar, title,
    viewer count, game, uptime, momentum, and SullyGoose analytics."""

    #: Dimensions passed to ImageCache (matching Theme).
    AVATAR_SIZE = (Theme.AVATAR_SIZE, Theme.AVATAR_SIZE)
    THUMBNAIL_SIZE = (Theme.THUMBNAIL_SIZE, Theme.THUMBNAIL_SIZE)

    def __init__(self):
        super().__init__()
        self.image_cache = ImageCache.shared()
        self.viewer_analysis = None
        self._started_at = None
        self._latest_sully_data = {}
        CurrentWatchingUIBuilder(self)


    # ============================================================
    # STREAM UPDATE
    # ============================================================

    def set_stream(self, stream, analysis=None):
        if not stream:
            self.clear()
            return

        # --- Header ---
        channel = stream.get("user_name", "Unknown")
        self.channel_label.setText(f"#{channel}")

        # --- Platform badge ---
        platform = stream.get("platform", "twitch")
        badge_colors = {
            "twitch": "#9146FF",
            "kick": "#53FC18",
            "youtube": "#FF0000",
        }
        badge_color = badge_colors.get(platform, "#888888")
        self.platform_label.setText(platform.upper())
        self.platform_label.setStyleSheet(
            f"color: {badge_color}; font-size: 8px; font-weight: bold;"
        )

        # --- Viewer count ---
        # NOTE: we do NOT add a graph point here.  The 4s refresh_momsg
        # timer is the single source of history samples, so the X-axis
        # stays time-honest (one point per refresh cycle).
        viewer_count = stream.get("viewer_count", 0)

        # --- Update enlarged LCD counter with viewer count ---
        self.enlarged_lcd_counter.display(viewer_count)

        # --- Title ---
        title = stream.get("title", "—")
        self.title_label.setText(title)

        # --- Avatar ---
        avatar_url = stream.get("avatar_url")
        self.set_avatar_image(avatar_url)

        # --- Uptime ---
        started_at = stream.get("started_at")
        self._started_at = started_at
        self._update_uptime(started_at)
        self._update_time_labels()


        # --- Analytics ---
        self.viewer_analysis = analysis
        if analysis:
            self.set_viewer_status(analysis)
        else:
            self.momentum_label.setText("📊 Waiting...")

    # ============================================================
    # VIEWER ANALYSIS UPDATE
    # ============================================================

    def set_viewer_status(self, analysis):
        if not analysis:
            self.viewer_analysis = None
            self.momentum_label.setText("📊 Waiting...")
            return

        self.viewer_analysis = analysis

        status = analysis.get("status", "")
        percent = analysis.get("percent") or 0
        self._update_momentum(status, percent, analysis)

    def _update_momentum(self, status, percent, analysis):
        """Update momentum label, gauge, and SullyGoose widget.

        Consolidates logic that was duplicated between
        :meth:`set_viewer_status` and :meth:`refresh_momsg` so there
        is a single code path for momentum visuals.
        """
        # Color-code momentum based on trend direction.
        if status == "Rising":
            color = "#00ff00"
        elif status == "Declining":
            color = "#ff4444"
        else:
            color = "#f2f2f2"
        self.momentum_label.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: bold;"
        )
        self.momentum_label.setText(f"{status} {percent:+.1f}%")

        # Update mini gauge with momentum.
        # The gauge now takes the raw percent directly and clamps it
        # to its +/-50% dial semantics internally.
        self.mini_gauge.set_percent(percent, status)

        # Update SullyGoose widget directly.
        sully = analysis.get("sullygoose", {}) if analysis else {}
        if hasattr(self, 'sully_widget') and self.sully_widget:
            # Store latest data for future refreshes
            if sully:
                self._latest_sully_data = sully
            # Use stored data if analysis doesn't have it
            elif self._latest_sully_data:
                sully = self._latest_sully_data
            if sully:
                self.sully_widget.update_metrics(sully, analysis)

    def _current_channel_name(self):
        """Return the login name of the currently displayed channel, or empty string."""
        text = self.channel_label.text()
        if text and text.startswith("#"):
            return text[1:].lower().strip()
        return ""

    def _clear_sullygoose(self):
        """Reset SullyGoose widget to placeholder state."""
        self._latest_sully_data = {}
        if hasattr(self, 'sully_widget') and self.sully_widget:
            self.sully_widget.update_metrics(None)

    # ============================================================
    # CLEAR
    # ============================================================

    def clear(self):
        """Reset all widgets to their default/empty state."""
        self.channel_label.setText("—")
        self.enlarged_lcd_counter.display(0)
        self.title_label.setText("—")
        self.momentum_label.setText("📊 Waiting...")
        self._clear_sullygoose()
        self.set_avatar_image(None)
        self.live_label.setText("● OFFLINE")
        self.viewer_history_graph.clear()
        self.uptime_label.setText("⏱ —")
        self.streamer_time_label.setText("⏰ Streamer: —")
        self.my_time_label.setText("⏰ Me: —")
        self.mini_gauge.set_value(50, "MOM")
        self._started_at = None
        self.viewer_analysis = None


    # ============================================================
    # IMAGE LOADING (async via ImageCache)
    # ============================================================

    def set_avatar_image(self, avatar_url):
        """Load the broadcaster avatar asynchronously; show '?' until ready."""
        self.image_cache.load(
            self.avatar_label,
            avatar_url,
            self.AVATAR_SIZE,
            placeholder="?",
        )

    def set_game_thumbnail(self, thumbnail_url):
        """Load the game-category thumbnail asynchronously; show '🎮' until ready."""
        self.image_cache.load(
            self.game_thumbnail,
            thumbnail_url,
            self.THUMBNAIL_SIZE,
            placeholder="🎮",
        )

    # ============================================================
    # TIME LABELS
    # ============================================================

    def _update_time_labels(self):
        """Update streamer time, my time, and uptime labels."""
        # Get current time in UTC
        now_utc = datetime.now(timezone.utc)
        now_local = datetime.now()  # Local time for user
        
        # Format times as HH:MM
        streamer_time_str = now_utc.strftime("%H:%M") + " UTC"
        my_time_str = now_local.strftime("%H:%M") + " LOCAL"
        
        # Update the labels
        self.streamer_time_label.setText(f"⏰ Streamer: {streamer_time_str}")
        self.my_time_label.setText(f"⏰ Me: {my_time_str}")

    # ============================================================
    # UPTIME
    # ============================================================

    def _update_uptime(self, started_at):
        if not started_at:
            self.uptime_label.setText("⏱ —")
            return

        try:
            started = datetime.fromisoformat(
                started_at.replace("Z", "+00:00")
            )
            seconds = int(
                (datetime.now(timezone.utc) - started).total_seconds()
            )
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            self.uptime_label.setText(f"⏱ {hours}h {minutes}m")
        except Exception:
            self.uptime_label.setText("⏱ —")

    # ============================================================
    # TIMEBOSS REFRESH (every 4 seconds)
    # ============================================================

    def refresh_momsg(self, stream, analysis):
        """Refresh MOM and SG widgets every 4 seconds via timer.
        
        Updates:
        - MOM gauge (momentum), LCD (viewer count), graph (history)
        - SG metrics that change frequently
        
        Also persists viewer history to DB.
        """
        if not stream:
            return

        # Get current data
        viewer_count = stream.get("viewer_count", 0)
        login = (
            stream.get("user_login")
            or stream.get("user_name")
            or stream.get("channel")
            or ""
        ).lower().strip()

        # Update LCD counter
        self.enlarged_lcd_counter.display(viewer_count)

        # Add point to viewer history graph
        self.viewer_history_graph.add_point(viewer_count)

        # Persist viewer history to DB
        if login:
            store_viewer_history(
                login,
                viewer_count,
                platform=stream.get("platform", "twitch")
            )

        # ----------------------------------------------------------
        # Refresh time labels and uptime every cycle so they don't
        # go stale between stream changes (Fixes Issue #3).
        # ----------------------------------------------------------
        self._update_time_labels()
        self._update_uptime(self._started_at)

        # Update momentum, gauge, and SG widget via the unified helper
        # (single code path — Fixes duplicated logic, Issue #5).
        if analysis:
            status = analysis.get("status", "")
            percent = analysis.get("percent") or 0
            self._update_momentum(status, percent, analysis)

