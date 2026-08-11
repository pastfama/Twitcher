import os
from PySide6.QtCore import QSettings, Signal, QObject, Qt, QTimer
from PySide6.QtWidgets import QMainWindow
from logger import debug
from video import VideoWindow
from core import StreamDispatcher, ViewerTracker, ViewerMonitor, wait_for_pending
from .app_runtime import MainMenuRuntime
from .channel_state import MainMenuStreamState
from .currwatching import CurrentWatchingPanel
from .dispatcher_panel import DispatcherPanel
from .livefollowed import LiveFollowedPanel
from .chatpanel import ChatPanel
from .nextstream import NextStreamPanel
import core.db as db
from .window_state import MainMenuWindowState

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

class _AnalyticsBridge(QObject):
    analytics_updated = Signal(object, object)  # stream, analysis

class MainMenu(
    QMainWindow,
    MainMenuWindowState,
    MainMenuRuntime,
    MainMenuStreamState,
):
    def __init__(self, api, video_window=None):
        super().__init__()
        self.api = api
        self._injected_video_window = video_window
        self.settings = QSettings(
            "Watcher",
            "WatcherControlCenter"
        )
        self.user = None
        self.live_channels = []
        self.current_stream = None
        self.current_channel = None
        self.next_stream = None
        self.resume_attempted = False
        self.is_closing = False
        self.is_loading_channels = False
        self.pending_channel = None
        self.video_window = self._injected_video_window or VideoWindow()
        self.log_window = None
        self._analytics_bridge = _AnalyticsBridge()
        self._analytics_bridge.analytics_updated.connect(self._on_analytics_signal, Qt.QueuedConnection)
        #
        # Analytics system
        #
        self.viewer_tracker = ViewerTracker()
        # Initialize AI-powered AnalyticsEngine
        from core.ai_analytics_engine import get_ai_analytics_engine
        self.analytics_engine = get_ai_analytics_engine()
        # Connect AI analysis complete signal to UI update
        if hasattr(self.analytics_engine, 'analysis_complete'):
            self.analytics_engine.analysis_complete.connect(
                self._on_ai_analysis_complete, Qt.QueuedConnection
            )
        #
        # Viewer Monitor (owns its own QTimer)
        #
        self.viewer_monitor = ViewerMonitor(
            api=self.api,
            tracker=self.viewer_tracker,
            get_live_channels=self._fetch_live_channels,
            update_callback=self.update_current_stream_view,
            analytics_engine=self.analytics_engine,
            interval_ms=4000,
        )
        # Initialize platform manager for multi-platform support
        self.platform_manager = None
        try:
            from platforms import get_platform_manager
            self.platform_manager = get_platform_manager()
            debug("[WATCHER] Platform manager initialized (Twitch, Kick, YouTube)")
        except Exception as e:
            debug(f"[WATCHER] Platform manager init failed: {e}")
        self.avatar_cache = {}
        self.project_root = PROJECT_ROOT
        self.current_panel_cls = CurrentWatchingPanel
        self.next_panel_cls = NextStreamPanel
        # Inject analytics engine into next stream panel
        if hasattr(self, 'next_panel') and self.next_panel:
            self.next_panel.set_analytics_engine(self.analytics_engine)
        self.live_followed_panel_cls = LiveFollowedPanel
        self.chat_panel_cls = ChatPanel
        self.dispatcher_panel_cls = DispatcherPanel
        self.dispatcher = StreamDispatcher(
            api=self.api,
            video_window=self.video_window,
            on_status=self.handle_dispatcher_status,
            on_log=self.handle_dispatcher_log,
            on_stream_changed=self.handle_stream_changed,
        )
        self.setWindowTitle(
            "Watcher Control Center"
        )
        self.setMinimumSize(
            1400,
            800
        )
        self.build_interface()
        self.restore_window_geometry()
        #
        # Periodic timers
        #
        # Video auto-play timer (highest priority)
        self._video_timer = QTimer(self)
        self._video_timer.setInterval(500)
        self._video_timer.timeout.connect(self._auto_play_video)
        self._video_timer.start()
        # MOM refresh timer
        self._momsg_timer = QTimer(self)
        self._momsg_timer.setInterval(4000)
        self._momsg_timer.timeout.connect(self._refresh_momsg)
        QTimer.singleShot(500, self._momsg_timer.start)
        # Live channels refresh timer
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(3000)
        self._live_timer.timeout.connect(self._refresh_live_channels)
        self._live_timer.start()
        self.viewer_monitor.start()
        self.log(
            "Viewer monitor started."
        )
        # Restore cached streamer data
        self._load_cached_streamer_data()
        self.load_twitch()

    def _update_chat_ai_metrics(self):
        """Update chat panel with cached or fallback AI metrics."""
        if not hasattr(self, 'chat_panel') or not self.chat_panel:
            debug("[MAIN MENU] No chat panel available")
            return
        if not self.current_channel:
            debug("[MAIN MENU] No current channel")
            return
        
        debug(f"[MAIN MENU] Updating chat metrics for {self.current_channel}")
        
        # Try to get cached analysis from DB
        try:
            from core.db import get_streamer
            streamer = get_streamer(self.current_channel, platform=self.current_stream.get("platform", "twitch"))
            debug(f"[MAIN MENU] Streamer data found: {streamer is not None}")
            if streamer:
                cached_ai = streamer.get("data", {}).get("ai_analysis", {})
                debug(f"[MAIN MENU] Cached AI data: {bool(cached_ai)}")
                if cached_ai:
                    debug(f"[MAIN MENU] Cached AI score: {cached_ai.get('quality_score')}")
                    # Convert cached format to UI format with derived metrics
                    score = cached_ai.get("quality_score", 50)
                    confidence = cached_ai.get("confidence", 0.0)
                    churn = cached_ai.get("churn_risk", 0.3)
                    analysis = {
                        "score": score,
                        "status": cached_ai.get("momentum", "Stable"),
                        "percent": cached_ai.get("momentum_percent", 0.0),
                        "confidence": confidence,
                        "health": min(100, int(score * 0.7 + confidence * 30)),
                        "retention": int((1.0 - churn) * 100),
                        "churn_risk": churn,
                        "viral_potential": cached_ai.get("viral_potential", 0.0),
                        "predicted_peak_viewers": cached_ai.get("predicted_peak_viewers", 0),
                        "ai_insight": cached_ai.get("ai_insight", ""),
                        "recommendations": cached_ai.get("recommendations", []),
                    }
                    self.chat_panel.update_ai_metrics(analysis)
                    debug(f"[MAIN MENU] Updated chat metrics with cached data for {self.current_channel}")
                    return
        except Exception as e:
            debug(f"[MAIN MENU] Failed to get cached AI data: {e}")
        
        # No cached AI data - show fallback metrics based on viewer count
        current_score = self.chat_panel.metric_cells["SCORE"].text()
        debug(f"[MAIN MENU] Current SCORE text: '{current_score}'")
        if current_score in ("...", "LOADING", "N/A"):
            debug(f"[MAIN MENU] Setting fallback metrics for {self.current_channel}")
            # Create fallback analysis based on current stream data
            viewers = self.current_stream.get("viewer_count", 0) if self.current_stream else 0
            # Use the AI engine's fallback which includes all derived metrics
            if self.analytics_engine and hasattr(self.analytics_engine, '_fallback_analysis'):
                fallback_analysis = self.analytics_engine._fallback_analysis(
                    self.current_stream or {"viewer_count": viewers}
                )
            else:
                fallback_analysis = {
                    "score": self._viewer_count_to_score(viewers),
                    "status": "Stable",
                    "percent": 0.0,
                    "confidence": 0.3,
                    "health": min(100, int(self._viewer_count_to_score(viewers) * 0.7 + 9)),
                    "retention": 70,
                    "churn_risk": 0.3,
                    "viral_potential": 0.3,
                    "predicted_peak_viewers": viewers,
                    "ai_insight": "AI analysis pending",
                    "recommendations": [],
                }
            self.chat_panel.update_ai_metrics(fallback_analysis)

    def _on_ai_analysis_complete(self, login: str, platform: str, analysis: dict):
        """Handle AI analysis complete signal.
        
        Updates UI with fresh AI insights when background analysis finishes.
        """
        debug(f"[MAIN MENU] AI analysis complete for {login}: score={analysis.get('score')}")
        debug(f"[MAIN MENU] Current channel: {self.current_channel}, analysis for: {login}")
        debug(f"[MAIN MENU] Match: {self.current_channel and login == self.current_channel}")
        
        # If this is the current channel, update the UI immediately
        if self.current_channel and login == self.current_channel:
            debug(f"[MAIN MENU] Updating UI for current channel {login}")
            # Update current watching panel
            if hasattr(self, 'current_panel') and self.current_panel:
                self.current_panel.set_stream(self.current_stream, analysis)
            
            # Update chat panel AI metrics
            if hasattr(self, 'chat_panel') and self.chat_panel:
                debug(f"[MAIN MENU] Calling chat_panel.update_ai_metrics()")
                self.chat_panel.update_ai_metrics(analysis)
                debug(f"[MAIN MENU] Chat metrics updated, SCORE now: {self.chat_panel.metric_cells['SCORE'].text()}")
            
            # Update next stream panel if it's showing this channel
            if hasattr(self, 'next_panel') and self.next_panel:
                next_channel = getattr(self.next_panel, '_current_channel', None)
                if next_channel == login:
                    self.next_panel._update_analytics_ui(analysis)
        else:
            debug(f"[MAIN MENU] Analysis for {login} but current channel is {self.current_channel} - skipping")

    def _on_analytics_signal(self, stream, analysis):
        """Handle analytics update from background thread via signal."""
        debug(f"[MAIN MENU] _on_analytics_signal: stream={stream.get('user_login') if stream else None}")
        if stream and analysis:
            signal_login = str(
                stream.get("user_login")
                or stream.get("user_name")
                or stream.get("channel")
                or ""
            ).strip().lower()
            if self.current_channel and signal_login:
                if signal_login != self.current_channel:
                    debug(f"[MAIN MENU] Discarding analytics for non-current channel '{signal_login}' (current: '{self.current_channel}')")
                    return
            fetch_login = analysis.get("_fetch_login")
            if fetch_login and signal_login:
                if str(fetch_login).lower() != signal_login:
                    debug(
                        "[MAIN MENU] Discarding mismatched analytics: "
                        "fetch was for '%s', signal stream is '%s'",
                        fetch_login, signal_login,
                    )
                    return
            self.current_stream = stream
            self.update_current_stream_view(stream, analysis)

    def _auto_play_video(self):
        """Auto-play video if nothing is playing."""
        try:
            channels = self._get_recent_channels_for_video()
            if not channels:
                return
            state = self.video_window.get_player_state()
            if state and state.get("playing"):
                return
            for channel in channels:
                try:
                    self.video_window.start_channel(channel)
                    return
                except Exception:
                    continue
        except Exception as e:
            debug(f"[VIDEO] Auto-play error: {e}")

    def _refresh_momsg(self):
        """Refresh MOM widget every 4 seconds."""
        if hasattr(self, 'current_panel') and self.current_panel:
            self.current_panel.refresh_momsg(self.current_stream, self.current_panel.viewer_analysis)
        # Update chat metrics with fresh data if AI analysis completed
        self._update_chat_ai_metrics()

    def _refresh_live_channels(self):
        """Periodically refresh the live channels list from Twitch API."""
        if self.is_closing or not self.user:
            return
        if not self.live_channels:
            debug("[LIVE CHANNELS] Refreshing (empty list)")
            self.load_live_channels()
        else:
            if self.current_stream:
                current_login = self.current_stream.get('user_login')
                in_list = any(
                    s.get('user_login') == current_login
                    for s in self.live_channels
                )
                if not in_list:
                    debug(f"[LIVE CHANNELS] Adding current_stream {current_login} to list")
                    self.live_channels.append(self.current_stream)

    def _viewer_count_to_score(self, viewers: int) -> int:
        """Convert viewer count to a simple quality score (0-100)."""
        if viewers >= 10000:
            return 75
        elif viewers >= 5000:
            return 65
        elif viewers >= 1000:
            return 50
        elif viewers >= 500:
            return 40
        elif viewers >= 100:
            return 25
        else:
            return 10

    def _get_recent_channels_for_video(self):
        """Return recent channels for video auto-play from DB."""
        try:
            from core.db import get_recent_channels
            return get_recent_channels(limit=10)
        except Exception:
            return []

    def _load_cached_streamer_data(self):
        """Populate UI panels with locally-cached streamer metadata from DB."""
        try:
            from core.db import list_streamers, get_streamer
            all_streamers = list_streamers()
            if not all_streamers:
                return
            count = 0
            for entry in all_streamers:
                login = entry.get("login")
                if not login:
                    continue
                platform = entry.get("platform", "twitch")
                full = get_streamer(login, platform=platform)
                avatar = full.get("avatar_url")
                if avatar:
                    self.avatar_cache[f"{platform}:{login}"] = avatar
                count += 1
            self.log(f"Loaded cached data for {count} streamers from DB")
        except Exception as exc:
            self.log(f"Could not load cached streamer data: {exc}")

    def enrich_stream_with_avatar(self, stream):
        if not stream:
            return None
        stream_data = dict(stream)
        login = str(
            stream_data.get("user_login")
            or stream_data.get("user_name")
            or stream_data.get("channel")
            or ""
        ).strip()
        if not login:
            return stream_data
        platform = str(
            stream_data.get("platform")
            or "twitch"
        ).lower().strip()
        cache_key = f"{platform}:{login}"
        if cache_key in self.avatar_cache:
            stream_data["avatar_url"] = self.avatar_cache[cache_key]
            return stream_data
        avatar_url = str(
            stream_data.get("avatar_url")
            or ""
        ).strip()
        if not avatar_url and platform == "twitch":
            try:
                profile = self.api.get_user_profile(
                    login
                )
                avatar_url = str(
                    profile.get("profile_image_url")
                    or ""
                ).strip()
            except Exception as exc:
                self.log(
                    f"Could not fetch avatar for {login}: {exc}"
                )
        if avatar_url:
            self.avatar_cache[cache_key] = avatar_url
            stream_data["avatar_url"] = avatar_url
        return stream_data

    def handle_dispatcher_status(self, message):
        self.dispatcher_panel.set_status(
            message
        )

    def handle_dispatcher_log(self, message):
        self.log(
            f"[DISPATCHER] {message}"
        )

    def handle_stream_changed(self, data):
        channel = data.get(
            "streamer",
            ""
        )
        if not channel:
            return
        platform = data.get(
            "platform",
            "twitch"
        )
        self.current_channel = (
            channel.lower().strip()
        )
        self.current_stream = {
            "user_login": self.current_channel,
            "user_name": self.current_channel,
            "platform": platform
        }
        self.save_last_streamer(
            self.current_channel
        )
        self.log(
            f"Current stream changed to #{self.current_channel}"
        )
        debug(f"[MAIN MENU] Stream changed to {self.current_channel}, triggering metrics update")
        self.update_next_stream()
        # Immediately update chat panel AI metrics with cached/fallback data
        # This is called ONLY on channel switch, not on every refresh cycle
        self._update_chat_ai_metrics()

    def closeEvent(self, event):
        debug(
            "MainMenu.closeEvent invoked"
        )
        if self.is_closing:
            event.accept()
            return
        self.is_closing = True
        self.save_window_geometry()
        try:
            self.viewer_monitor.stop()
        except Exception:
            pass
        # Stop all timers
        for timer in [self._video_timer, self._momsg_timer, self._live_timer]:
            try:
                timer.stop()
            except Exception:
                pass
        try:
            self.video_window.save_window_state()
        except Exception:
            pass
        try:
            self.dispatcher.shutdown()
        except Exception:
            pass
        try:
            self.chat_panel.disconnect_chat()
        except Exception:
            pass
        try:
            self.video_window.close()
        except Exception:
            pass
        wait_for_pending()
        event.accept()
