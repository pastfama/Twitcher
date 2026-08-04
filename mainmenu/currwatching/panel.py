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

        # --- Game / category ---
        game_name = stream.get("game_name") or "No category"
        self.category_label.setText(game_name)
        self.set_game_thumbnail(stream.get("game_thumbnail"))
        
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
            self.additional_metrics_label.setText("📈 Peak: — | Avg: —")

    # ============================================================
    # VIEWER ANALYSIS UPDATE
    # ============================================================

    def set_viewer_status(self, analysis):
        if not analysis:
            self.viewer_analysis = None
            self.momentum_label.setText("📊 Waiting...")
            self.additional_metrics_label.setText("📈 Peak: — | Avg: —")
            return

        self.viewer_analysis = analysis

        status = analysis.get("status", "")
        percent = analysis.get("percent") or 0

        self.momentum_label.setText(f"{status} {percent:+}%")

        # Update mini gauge with momentum.
        # Map percent (-50 to +50) to gauge scale (0 to 100).
        gauge_value = int(percent + 50)  # -50→0, 0→50, +50→100
        gauge_value = max(0, min(100, gauge_value))
        self.mini_gauge.set_value(gauge_value, "MOM")

        # Update additional metrics label
        sully = analysis.get("sullygoose", {})
        if sully:
            peak = sully.get("peak_viewers", 0)
            avg = sully.get("avg_viewers", 0)
            self.additional_metrics_label.setText(f"📈 Peak: {peak:,} | Avg: {avg:,}")
        else:
            self.additional_metrics_label.setText("📈 Peak: — | Avg: —")

        # Update SullyGoose metrics.
        if sully:
            self._update_sullygoose(sully, analysis)
        else:
            self._clear_sullygoose()

    def _update_sullygoose(self, sully, analysis):
        # --- Viewers ---
        avg = sully.get("avg_viewers", 0)
        peak = sully.get("peak_viewers", 0)

        self.sully_avg_label.value_label.setText(f"{avg:,}")
        self.sully_peak_label.value_label.setText(f"{peak:,}")

        # --- Growth & Rank ---
        growth = sully.get("viewer_growth") or 0
        rank = sully.get("category_rank") or 0
        freq = sully.get("stream_frequency") or 0

        self.sully_growth_label.value_label.setText(f"{growth:+.1f}%")
        self._color_value(self.sully_growth_label.value_label, growth)

        self.sully_rank_label.value_label.setText(f"#{rank}")
        self.sully_freq_label.value_label.setText(f"{freq:.0f}h/wk")

        # --- Schedule ---
        duration = sully.get("avg_stream_duration", 0)
        start_h = sully.get("typical_start_hour", 0)
        end_h = sully.get("typical_end_hour", 0)

        self.sully_duration_label.value_label.setText(f"{duration:.1f}h")
        self.sully_start_label.value_label.setText(f"{start_h:02d}:00")
        self.sully_end_label.value_label.setText(f"{end_h:02d}:00")

        # --- Content ---
        games = sully.get("games_played_30d", 0)
        main_pct = sully.get("main_game_pct", 0)
        raid_freq = sully.get("raid_frequency", 0)

        self.sully_games_label.value_label.setText(f"{games}")
        self.sully_main_game_label.value_label.setText(f"{main_pct}%")
        self.sully_raid_freq_label.value_label.setText(f"{raid_freq}%")

        # --- Trends ---
        t7d = sully.get("trend_7d", "Stable")
        t7d_pct = sully.get("trend_7d_pct", 0)
        t30d = sully.get("trend_30d", "Stable")
        t30d_pct = sully.get("trend_30d_pct", 0)
        best_day = sully.get("best_day", "—")

        arrow7 = "↗" if t7d == "Rising" else ("↘" if t7d == "Declining" else "→")
        arrow30 = "↗" if t30d == "Rising" else ("↘" if t30d == "Declining" else "→")

        self.sully_trend_7d_label.value_label.setText(
            f"{arrow7} {t7d} {t7d_pct:+.1f}%"
        )
        self._color_trend(self.sully_trend_7d_label.value_label, t7d)

        self.sully_trend_30d_label.value_label.setText(
            f"{arrow30} {t30d} {t30d_pct:+.1f}%"
        )
        self._color_trend(self.sully_trend_30d_label.value_label, t30d)

        self.sully_best_day_label.value_label.setText(best_day)

        # --- Followers & Chat ---
        followers = sully.get("follower_count", 0)
        f_growth = sully.get("follower_growth_30d", 0)
        chat = sully.get("chat_activity", "—")

        self.sully_followers_label.value_label.setText(f"{followers:,}")
        self.sully_follower_growth_label.value_label.setText(f"{f_growth:+.1f}%")
        self._color_value(self.sully_follower_growth_label.value_label, f_growth)

        self.sully_chat_label.value_label.setText(chat)
        if chat == "High":
            self.sully_chat_label.value_label.setStyleSheet(
                f"color: {Theme.GREEN}; font-size: 11px; font-weight: bold;"
            )
        elif chat == "Medium":
            self.sully_chat_label.value_label.setStyleSheet(
                f"color: {Theme.ORANGE}; font-size: 11px; font-weight: bold;"
            )
        else:
            self.sully_chat_label.value_label.setStyleSheet(
                f"color: {Theme.MUTED}; font-size: 11px; font-weight: bold;"
            )

        # --- Score bars ---
        consistency = sully.get("consistency_score", 0)
        reliability = sully.get("reliability_score", 0)
        discovery = sully.get("discovery_score", 0)

        self.sully_consistency_bar.setValue(int(consistency))
        self.sully_consistency_bar.setFormat(f"{int(consistency)}")

        self.sully_reliability_bar.setValue(int(reliability))
        self.sully_reliability_bar.setFormat(f"{int(reliability)}")

        self.sully_discovery_bar.setValue(int(discovery))
        self.sully_discovery_bar.setFormat(f"{int(discovery)}")

        # --- Quality score ---
        score = analysis.get("score", 0)
        self.sully_score_bar.setValue(int(score))
        self.sully_score_bar.setFormat(f"★ {int(score)} / 100")

    def _color_value(self, label, value):
        if value > 0:
            label.setStyleSheet(
                f"color: {Theme.GREEN}; font-size: 11px; font-weight: bold;"
            )
        elif value < 0:
            label.setStyleSheet(
                f"color: {Theme.RED_DARK}; font-size: 11px; font-weight: bold;"
            )
        else:
            label.setStyleSheet(
                f"color: {Theme.BRIGHT}; font-size: 11px; font-weight: bold;"
            )

    def _color_trend(self, label, trend):
        if trend == "Rising":
            label.setStyleSheet(
                f"color: {Theme.GREEN}; font-size: 11px; font-weight: bold;"
            )
        elif trend == "Declining":
            label.setStyleSheet(
                f"color: {Theme.RED_DARK}; font-size: 11px; font-weight: bold;"
            )
        else:
            label.setStyleSheet(
                f"color: {Theme.ORANGE}; font-size: 11px; font-weight: bold;"
            )

    def _clear_sullygoose(self):
        """Reset every SullyGoose metric to its placeholder state."""

        for attr in [
            "sully_avg_label", "sully_peak_label",
            "sully_growth_label", "sully_rank_label", "sully_freq_label",
            "sully_duration_label", "sully_start_label", "sully_end_label",
            "sully_games_label", "sully_main_game_label", "sully_raid_freq_label",
            "sully_trend_7d_label", "sully_trend_30d_label", "sully_best_day_label",
            "sully_followers_label", "sully_follower_growth_label",
            "sully_chat_label",
        ]:
            widget = getattr(self, attr, None)
            if widget and hasattr(widget, "value_label"):
                widget.value_label.setText("—")
                widget.value_label.setStyleSheet(
                    f"color: {Theme.BRIGHT}; font-size: 11px; font-weight: bold;"
                )

        for attr in [
            "sully_consistency_bar",
            "sully_reliability_bar",
            "sully_discovery_bar",
            "sully_score_bar",
        ]:
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.setValue(0)
                widget.setFormat("—")

    # ============================================================
    # CLEAR
    # ============================================================

    def clear(self):
        self.channel_label.setText("—")
        self.enlarged_lcd_counter.display(0)
        self.category_label.setText("—")
        self.uptime_label.setText("⏱ —")
        self.streamer_time_label.setText("⏰ Streamer: —")
        self.my_time_label.setText("⏰ Me: —")
        self.title_label.setText("—")
        self.momentum_label.setText("📊 Waiting...")
        self.additional_metrics_label.setText("📈 Peak: — | Avg: —")
        self._clear_sullygoose()
        self.set_avatar_image(None)
        self.set_game_thumbnail(None)
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
