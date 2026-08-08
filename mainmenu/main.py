import os
from PySide6.QtCore import QSettings, Signal, QObject, Qt, QTimer, QMetaObject, Qt
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
from core.analytics_engine_v2 import AnalyticsEngine
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
        # Initialize new AnalyticsEngine with AnalyticsDB
        from core.analytics_db import AnalyticsDB
        analytics_db = AnalyticsDB()
        self.analytics_engine = AnalyticsEngine(db=analytics_db)
        # Connect signal for UI updates
        self.analytics_engine.add_listener(
            lambda login, platform, data: self._on_external_data_ready(login, platform, data)
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
        self._video_timer.setInterval(500)  # 0.5s - faster video auto-play check
        self._video_timer.timeout.connect(self._auto_play_video)
        self._video_timer.start()
        # NOTE: The old 30-second SG fetch timer (_sg_timer) was removed.
        # ViewerMonitor already triggers SullyGoose fetches every 4s per
        # channel via analytics_engine.update_stream() -> sullygoose_for(),
        # so the dedicated timer was redundant (P5 fix).
        # MOM+SG refresh timer
        # Staggered: start 500 ms after the ViewerMonitor so that
        # background channel checks have time to complete and deliver
        # their results to viewer_analysis before we read it.
        # Without this stagger, the 4 s timers can fire in an
        # order where refresh_momsg reads stale analysis from the
        # previous tick (Fix #7 — timer phase misalignment).
        self._momsg_timer = QTimer(self)
        self._momsg_timer.setInterval(4000)
        self._momsg_timer.timeout.connect(self._refresh_momsg)
        QTimer.singleShot(500, self._momsg_timer.start)
        # Live channels refresh timer
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(3000)  # 3s - live channels refresh
        self._live_timer.timeout.connect(self._refresh_live_channels)
        self._live_timer.start()
        self.viewer_monitor.start()
        self.log(
            "Viewer monitor started."
        )
        # Restore cached streamer data into UI panels so they render
        # immediately without waiting for Twitch API responses.
        self._load_cached_streamer_data()
        self.load_twitch()
    def _on_external_data_ready(self, login: str, platform: str, data: Dict[str, Any]):
        """Handle external data ready signal from AnalyticsEngine.
        
        Called from background thread. Uses Qt.QueuedConnection to safely
        update widget on main UI thread.
        """
        # STRICT guard: only update widget for the current channel
        if not self.current_channel:
            return
        
        if login != self.current_channel:
            return
        
        # Schedule widget update on main thread (thread-safe)
        QMetaObject.invokeMethod(
            self,
            "_update_widget_safely",
            Qt.QueuedConnection,
            Q_ARG(str, login),
            Q_ARG(object, data),
        )
    
    @QMetaObject.invokeMethod
    def _update_widget_safely(self, login: str, data: Dict[str, Any]):
        """Update widget - guaranteed to run on main Qt thread."""
        if hasattr(self, 'current_panel') and self.current_panel:
            try:
                # Store data in panel
                self.current_panel._latest_sully_data = data
                
                # Update widget
                self.current_panel.sully_widget.update_metrics(data)
                debug(f"[MAIN MENU] Updated SullyGoose widget for {login}")
            except Exception as e:
                debug(f"[MAIN MENU] Widget update error: {e}")
    
    def _on_analytics_signal(self, stream, analysis):
        """Handle analytics update from background thread via signal."""
        debug(f"[MAIN MENU] _on_analytics_signal: stream={stream.get('user_login') if stream else None}, has_sullygoose={'sullygoose' in (analysis or {})}")
        if stream and analysis:
            # Guard — only accept analytics for the channel currently
            # playing in the video window.  SullyGoose fetches are kicked
            # off for *all* live channels via fetch_all_live_channels,
            # so the signal can fire for a non-current channel.
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
            # Second guard: the analysis payload carries _fetch_login, the
            # login the SullyGoose background fetch was actually for.  If
            # that doesn't match the stream in the signal, the result is
            # stale cross-channel data and must be discarded (P1 fix).
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
    def _fetch_sg_data(self):
        """Fetch analytics data for the CURRENT channel only."""
        try:
            # Only fetch for current channel to avoid lag
            if self.current_channel:
                self.analytics_engine.get_external_data(self.current_channel, platform="twitch")
        except Exception as e:
            debug(f"[SG] Fetch error: {e}")
    def _refresh_momsg(self):
        """Refresh MOM and SG widgets every 4 seconds."""
        if hasattr(self, 'current_panel') and self.current_panel:
            self.current_panel.refresh_momsg(self.current_stream, self.current_panel.viewer_analysis)
        # Trigger background fetch for analytics data
        self._fetch_sg_data()
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
        # Kick and YouTube streams already carry their avatar URL.
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
        self.update_next_stream()
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
