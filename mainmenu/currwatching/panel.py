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

        # --- Viewer count + history graph ---
        viewer_count = stream.get("viewer_count", 0)
        self.viewer_history_graph.add_point(viewer_count)

        # --- Update enlarged LCD counter with viewer count ---
        self.enlarged_lcd_counter.display(viewer_count)

        # --- Title ---
        title = stream.get("title", "—")
        self.title_label.setText(title)

        # --- Avatar ---
        avatar_url = stream.get("avatar_url")
        self.set_avatar_image(avatar_url)

        # --- Neon viewer counter ---
        self.neon_viewer_counter.set_active(viewer_count > 0)

        # --- Uptime ---
        started_at = stream.get("started_at")
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

        # Visible debug: change color to confirm callback is firing
        has_sully = bool(analysis.get("sullygoose"))
        if has_sully:
            self.momentum_label.setStyleSheet("color: #00ff00; font-size: 11px; font-weight: bold;")
        else:
            self.momentum_label.setStyleSheet("color: #ff0000; font-size: 11px; font-weight: bold;")

        self.momentum_label.setText(f"{status} {percent:+}% {'✅SG' if has_sully else '❌NoSG'}")

        # Update mini gauge with momentum.
        # Map percent (-50 to +50) to gauge scale (0 to 100).
        gauge_value = int(percent + 50)  # -50→0, 0→50, +50→100
        gauge_value = max(0, min(100, gauge_value))
        self.mini_gauge.set_value(gauge_value, "MOM")

        # Update SullyGoose widget directly.
        sully = analysis.get("sullygoose", {})
        if hasattr(self, 'sully_widget') and self.sully_widget:
            self.sully_widget.update_metrics(sully, analysis)

    def _clear_sullygoose(self):
        """Reset SullyGoose widget to placeholder state."""
        if hasattr(self, 'sully_widget') and self.sully_widget:
            self.sully_widget.update_metrics(None)

    # ============================================================
    # CLEAR
    # ============================================================

    def clear(self):
        self.channel_label.setText("—")
        self.enlarged_lcd_counter.display(0)
        self.title_label.setText("—")
        self.momentum_label.setText("📊 Waiting...")
        self._clear_sullygoose()
        self.set_avatar_image(None)
        self.neon_viewer_counter.set_active(False)

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
        """Refresh MOM and SG widgets every 4 seconds via TimeBoss.
        
        Updates:
        - MOM gauge (momentum), LCD (viewer count), graph (history)
        - SG metrics that change frequently
        
        Also persists viewer history to DB.
        """
        if not stream:
            return

        # Get current data
        viewer_count = stream.get("viewer_count", 0)
        login = (stream.get("user_login") or stream.get("user_name") or "").lower().strip()

        # Update LCD counter
        self.enlarged_lcd_counter.display(viewer_count)

        # Add point to viewer history graph
        self.viewer_history_graph.add_point(viewer_count)

        # Persist viewer history to DB
        if login:
            store_viewer_history(login, viewer_count)

        # Update momentum label and gauge from analysis
        if analysis:
            status = analysis.get("status", "")
            percent = analysis.get("percent") or 0
            has_sully = bool(analysis.get("sullygoose"))

            # Visual debug indicator
            if has_sully:
                self.momentum_label.setStyleSheet("color: #00ff00; font-size: 11px; font-weight: bold;")
            else:
                self.momentum_label.setStyleSheet("color: #ff0000; font-size: 11px; font-weight: bold;")

            self.momentum_label.setText(f"{status} {percent:+}% {'✅SG' if has_sully else '❌NoSG'}")

            # Update gauge
            gauge_value = max(0, min(100, int(percent + 50)))
            self.mini_gauge.set_value(gauge_value, "MOM")

            # Update SullyGoose widget
            sully = analysis.get("sullygoose", {})
            if hasattr(self, 'sully_widget') and self.sully_widget:
                self.sully_widget.update_metrics(sully, analysis)
