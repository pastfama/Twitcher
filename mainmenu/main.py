"""Main menu — thin shell that wires StreamState, services, and panels.

After the fundamental rewrite:
- All state lives in StreamState (single source of truth)
- All timers replaced by UpdateScheduler (single master clock)
- All API calls go through ServiceLayer (isolated)
- MainMenu is just the wiring layer — creates widgets, connects signals
"""

import os

from PySide6.QtCore import QSettings, Signal, QObject, Qt
from PySide6.QtWidgets import QMainWindow

from logger import debug
from video import VideoWindow
from core import StreamDispatcher, RaidMonitor, ViewerTracker, ViewerMonitor, wait_for_pending
from core.stream_state import StreamState
from core.update_scheduler import UpdateScheduler
from core.service_layer import ServiceLayer
from .app_runtime import MainMenuRuntime
from .channel_state import MainMenuStreamState
from .currwatching import CurrentWatchingPanel
from .dispatcher_panel import DispatcherPanel
from .livefollowed import LiveFollowedPanel
from .chatpanel import ChatPanel
from .nextstream import NextStreamPanel
from .raid_runtime import MainMenuRaidRuntime
from core.analytics_engine import AnalyticsEngine
from .window_state import MainMenuWindowState


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)


class _AnalyticsBridge(QObject):
    """Thread-safe bridge: background threads emit, GUI thread receives."""
    analytics_updated = Signal(object, object)


class MainMenu(
    QMainWindow,
    MainMenuWindowState,
    MainMenuRuntime,
    MainMenuStreamState,
    MainMenuRaidRuntime,
):
    """Watcher Control Center — the main application window.

    Architecture:
        self.state    → StreamState (all mutable state, signals)
        self.scheduler → UpdateScheduler (single master clock)
        self.services  → ServiceLayer (all API calls)
        self.viewer_monitor → ViewerMonitor (periodic viewer count polling)
        self.dispatcher     → StreamDispatcher (stream URL resolution + switching)
        self.analytics_engine → AnalyticsEngine (momentum + SullyGoose)
    """

    def __init__(self, api, video_window=None):
        super().__init__()

        self.api = api
        self._injected_video_window = video_window

        self.settings = QSettings("Watcher", "WatcherControlCenter")

        # ============================================================
        # STATE — single source of truth
        # ============================================================
        self.state = StreamState()
        self.state.is_closing = False

        # Backward-compat aliases for mixins (will be removed in Phase 7)
        # These proxy to self.state so existing mixin code keeps working.
        self._compat_setup()

        # ============================================================
        # SERVICES — all API calls go through here
        # ============================================================
        self.platform_manager = None
        try:
            from platforms import get_platform_manager
            self.platform_manager = get_platform_manager()
            debug("[WATCHER] Platform manager initialized")
        except Exception as e:
            debug(f"[WATCHER] Platform manager init failed: {e}")

        self.services = ServiceLayer(
            api=self.api,
            platform_manager=self.platform_manager,
        )

        # ============================================================
        # ANALYTICS
        # ============================================================
        self.viewer_tracker = ViewerTracker()
        self.analytics_bridge = _AnalyticsBridge()
        self.analytics_bridge.analytics_updated.connect(
            self._on_analytics_signal, Qt.QueuedConnection
        )
        self.analytics_engine = AnalyticsEngine(
            viewer_tracker=self.viewer_tracker,
            on_analytics_updated=lambda s, a: self.analytics_bridge.analytics_updated.emit(s, a),
        )

        # ============================================================
        # VIDEO + DISPATCHER + RAID
        # ============================================================
        self.video_window = self._injected_video_window or VideoWindow()
        self.log_window = None

        self.dispatcher = StreamDispatcher(
            api=self.api,
            video_window=self.video_window,
            on_status=self._on_dispatcher_status,
            on_log=self._on_dispatcher_log,
            on_stream_changed=self.handle_stream_changed,
            on_raid_announcement=self.handle_raid_announcement,
        )

        self.raid_monitor = RaidMonitor(self.api)
        self.raid_monitor.signals.raid_detected.connect(self.handle_raid)
        self.raid_monitor.signals.status.connect(self.handle_raid_status)
        self.raid_monitor.signals.error.connect(self.handle_raid_error)

        # ============================================================
        # VIEWER MONITOR — periodic viewer count polling
        # ============================================================
        self.viewer_monitor = ViewerMonitor(
            api=self.api,
            tracker=self.viewer_tracker,
            get_live_channels=self._fetch_live_channels,
            update_callback=self._on_viewer_update,
            analytics_engine=self.analytics_engine,
            interval_ms=2000,
        )

        # ============================================================
        # UI — build panels, connect signals
        # ============================================================
        self.setWindowTitle("Watcher Control Center")
        self.setMinimumSize(1400, 800)

        self.avatar_cache = {}
        self.project_root = PROJECT_ROOT

        self.current_panel_cls = CurrentWatchingPanel
        self.next_panel_cls = NextStreamPanel
        self.live_followed_panel_cls = LiveFollowedPanel
        self.chat_panel_cls = ChatPanel
        self.dispatcher_panel_cls = DispatcherPanel

        self.build_interface()
        self.restore_window_geometry()

        # ============================================================
        # SCHEDULER — single master clock replaces 5 QTimers
        # ============================================================
        self.scheduler = UpdateScheduler(parent=self)
        self.scheduler.register("panel_tick", 2000, self._tick_panel)
        self.scheduler.register("sg_fetch", 30000, self._fetch_sg_data)
        self.scheduler.register("live_refresh", 4000, self._refresh_live_channels)
        self.scheduler.register("video_autoplay", 4000, self._auto_play_video)

        # ============================================================
        # STARTUP
        # ============================================================
        self.scheduler.start()
        self.viewer_monitor.start()
        self.log("System started.")

        self._load_cached_streamer_data()
        self.load_twitch()

    # ================================================================
    # BACKWARD-COMPAT PROXIES — remove in Phase 7
    # ================================================================

    def _compat_setup(self):
        """Set up property aliases so mixin code (channel_state.py etc.)
        can still use self.current_stream, self.current_channel, etc.
        These will be removed when mixins are eliminated in Phase 7."""
        # Store original __dict__ to avoid recursion
        self.__dict__["_compat_state"] = self.state

    # Properties that proxy to self.state
    @property
    def current_stream(self):
        return self.state.current_stream

    @current_stream.setter
    def current_stream(self, value):
        self.state.set_current_stream(value)

    @property
    def current_channel(self):
        return self.state.current_channel

    @current_channel.setter
    def current_channel(self, value):
        self.state.set_current_channel(value)

    @property
    def live_channels(self):
        return self.state.live_channels

    @live_channels.setter
    def live_channels(self, value):
        self.state.set_live_channels(value)

    @property
    def next_stream(self):
        return self.state.next_stream

    @next_stream.setter
    def next_stream(self, value):
        self.state.set_next_stream(value)

    @property
    def user(self):
        return self.state.user

    @user.setter
    def user(self, value):
        self.state.set_user(value)

    @property
    def is_closing(self):
        return self.state.is_closing

    @is_closing.setter
    def is_closing(self, value):
        self.state.is_closing = value

    @property
    def is_loading_channels(self):
        return self.state.is_loading_channels

    @is_loading_channels.setter
    def is_loading_channels(self, value):
        self.state.is_loading_channels = value

    @property
    def pending_channel(self):
        return self.state.pending_channel

    @pending_channel.setter
    def pending_channel(self, value):
        self.state.pending_channel = value

    @property
    def resume_attempted(self):
        return self.state.resume_attempted

    @resume_attempted.setter
    def resume_attempted(self, value):
        self.state.resume_attempted = value

    # ================================================================
    # CALLBACKS from ViewerMonitor, Dispatcher, etc.
    # ================================================================

    def _on_viewer_update(self, stream, analytics):
        """Called by ViewerMonitor with fresh stream data + analytics."""
        self.update_current_stream_view(stream, analytics)

    def _on_analytics_signal(self, stream, analysis):
        """Handle analytics update from background thread via signal."""
        if stream and analysis:
            incoming = (stream.get("user_login") or stream.get("user_name") or "").lower().strip()
            if self.current_channel and incoming != self.current_channel:
                return
            self.current_stream = stream
            self.update_current_stream_view(stream, analysis)

    def _on_dispatcher_status(self, message):
        self.dispatcher_panel.set_status(message)

    def _on_dispatcher_log(self, message):
        self.log(f"[DISPATCHER] {message}")

    # ================================================================
    # SCHEDULER CALLBACKS
    # ================================================================

    def _tick_panel(self):
        """Lightweight 2s tick: graph + DB persist."""
        if hasattr(self, "current_panel") and self.current_panel:
            self.current_panel.tick()

    def _fetch_sg_data(self):
        """Fetch SullyGoose data — current channel first, then others."""
        try:
            channels = self._fetch_live_channels()
            if not channels:
                return
            if self.current_channel:
                current = [c for c in channels
                           if (c.get("user_login") or "").lower() == self.current_channel]
                others = [c for c in channels
                          if (c.get("user_login") or "").lower() != self.current_channel]
                if current:
                    self.analytics_engine.fetch_all_live_channels(current)
                if others:
                    self.analytics_engine.fetch_all_live_channels(others)
            else:
                self.analytics_engine.fetch_all_live_channels(channels)
        except Exception as e:
            debug(f"[SG] Fetch error: {e}")

    _live_refresh_counter = 0
    _LIVE_REFRESH_EVERY = 5  # API refresh every 5th tick (20s)

    def _refresh_live_channels(self):
        """Ensure current channel tracked + periodic API refresh."""
        if self.is_closing or not self.user:
            return
        if self.current_stream:
            login = self.current_stream.get("user_login")
            if login and not any(s.get("user_login") == login for s in self.live_channels):
                self.live_channels.append(self.current_stream)
        self._live_refresh_counter += 1
        if self._live_refresh_counter >= self._LIVE_REFRESH_EVERY:
            self._live_refresh_counter = 0
            if not self.is_loading_channels:
                self.load_live_channels()

    def _auto_play_video(self):
        """Auto-play video if nothing is playing."""
        try:
            channels = self._get_recent_channels_for_video()
            if not channels:
                return
            state = self.video_window.get_player_state()
            if state and state.get("playing"):
                return
            for ch in channels:
                try:
                    self.video_window.start_channel(ch)
                    return
                except Exception:
                    continue
        except Exception as e:
            debug(f"[VIDEO] Auto-play error: {e}")

    # ================================================================
    # HELPERS
    # ================================================================

    def _get_recent_channels_for_video(self):
        try:
            from core.db import get_recent_channels
            return get_recent_channels(limit=10)
        except Exception:
            return []

    def _load_cached_streamer_data(self):
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
        platform = str(stream_data.get("platform") or "twitch").lower().strip()
        cache_key = f"{platform}:{login}"
        if cache_key in self.avatar_cache:
            stream_data["avatar_url"] = self.avatar_cache[cache_key]
            return stream_data
        avatar_url = str(stream_data.get("avatar_url") or "").strip()
        if not avatar_url and platform == "twitch":
            try:
                profile = self.api.get_user_profile(login)
                avatar_url = str(profile.get("profile_image_url") or "").strip()
            except Exception as exc:
                self.log(f"Could not fetch avatar for {login}: {exc}")
        if avatar_url:
            self.avatar_cache[cache_key] = avatar_url
            stream_data["avatar_url"] = avatar_url
        return stream_data

    # ================================================================
    # DISPATCHER CALLBACKS
    # ================================================================

    def handle_stream_changed(self, data):
        """Dispatcher reports the video stream switched."""
        channel = data.get("streamer", "")
        if not channel:
            return
        platform = data.get("platform", "twitch")
        self.current_channel = channel.lower().strip()
        # Preserve existing stream data — don't overwrite with minimal dict.
        if self.current_stream is None or \
                self.current_stream.get("user_login", "").lower().strip() != self.current_channel:
            self.current_stream = {
                "user_login": self.current_channel,
                "user_name": self.current_channel,
                "platform": platform,
            }
        from core.db import set_setting
        set_setting("last_streamer", self.current_channel)
        self.log(f"Current stream changed to #{self.current_channel}")
        self.update_next_stream()

    def handle_raid_announcement(self, data):
        t = data.get("type")
        if t == "raid":
            self.log(f"RAID: {data.get('from_streamer','?')} → {data.get('to_streamer','?')} ({data.get('viewers',0):,})")
        elif t == "stream":
            self.log(f"STREAM: {data.get('streamer','?')}")

    # ================================================================
    # WINDOW EVENTS
    # ================================================================

    def closeEvent(self, event):
        debug("MainMenu.closeEvent invoked")
        if self.is_closing:
            event.accept()
            return
        self.is_closing = True
        self.save_window_geometry()
        try:
            self.viewer_monitor.stop()
        except Exception:
            pass
        try:
            self.raid_monitor.stop()
        except Exception:
            pass
        self.scheduler.stop()
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