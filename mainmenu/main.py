import os
from PySide6.QtCore import QSettings, Signal, QObject, Qt, QTimer
from PySide6.QtWidgets import QMainWindow
from logger import debug
from video import VideoWindow
from core import StreamDispatcher, ViewerTracker, ViewerMonitor, wait_for_pending
from core.viewer_monitor import ChatMetricsTracker
from .app_runtime import MainMenuRuntime
from .couch_mode import CouchModeManager
from .channel_state import MainMenuStreamState
from .currwatching import CurrentWatchingPanel
from .dispatcher_panel import DispatcherPanel
from .livefollowed import LiveFollowedPanel
from .chatpanel import ChatPanel
from .nextstream import NextStreamPanel
from .commentator import CommentatorPanel
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
        self.chat_metrics_tracker = ChatMetricsTracker(window_seconds=60)
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
        self.next_panel_cls = CommentatorPanel
        # Inject analytics engine into commentator panel
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

        # Couch mode (Ctrl+L to toggle)
        self.couch_mode = CouchModeManager(self)
        self.couch_mode.button.setParent(self)
        self.couch_mode.button.move(10, 10)
        self.couch_mode.button.raise_()
        self.couch_mode.button.show()

        # Vision analysis timer (capture + GPT-4o analysis every 10s)
        self._vision_timer = QTimer(self)
        self._vision_timer.setInterval(10000)  # 10 seconds
        self._vision_timer.timeout.connect(self._analyze_stream_frame)
        QTimer.singleShot(10000, self._vision_timer.start)  # start after 10s delay
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
        """Update chat panel with 36-metric dashboard data.

        Computes all 36 metrics from stream data, viewer history, and
        local chat metrics, then feeds them to the dashboard.
        """
        if not hasattr(self, 'chat_panel') or not self.chat_panel:
            debug("[MAIN MENU] No chat panel available")
            return
        if not self.current_channel:
            debug("[MAIN MENU] No current channel")
            return

        debug(f"[MAIN MENU] Updating 36-metric dashboard for {self.current_channel}")

        try:
            from core.db import get_viewer_history

            stream = self.current_stream or {}
            platform = stream.get("platform", "twitch")
            login = self.current_channel

            # Get viewer history from DB
            viewer_history = get_viewer_history(login, platform=platform, limit=50)

            # Get local chat metrics snapshot
            chat_metrics = self.chat_metrics_tracker.snapshot(
                current_viewers=int(stream.get("viewer_count", 0))
            )

            # Compute all 36 metrics via the analytics engine
            if self.analytics_engine:
                dashboard_data = self.analytics_engine.analyze_dashboard_metrics(
                    stream=stream,
                    viewer_history=viewer_history,
                    chat_metrics=chat_metrics,
                )
            else:
                # Minimal fallback
                dashboard_data = self._minimal_dashboard_fallback(stream)

            # Feed to dashboard
            self.chat_panel.update_dashboard_metrics(dashboard_data)

            # Feed to commentator panel (include channel + stream info)
            if hasattr(self, 'next_panel') and self.next_panel:
                if hasattr(self.next_panel, 'update_commentary'):
                    dashboard_data["channel"] = login
                    # Pass current stream data so the commentator can update its profile
                    if self.current_stream:
                        self.next_panel._current_stream = self.current_stream
                    self.next_panel.update_commentary(dashboard_data)

            debug(f"[MAIN MENU] Dashboard updated for {login}")

        except Exception as e:
            debug(f"[MAIN MENU] Dashboard update error: {e}")
            import traceback
            traceback.print_exc()

    def _minimal_dashboard_fallback(self, stream: dict) -> dict:
        """Minimal fallback when analytics engine is unavailable."""
        viewers = int(stream.get("viewer_count", 0))
        return {
            "viewers": viewers, "session_peak": viewers, "session_avg": viewers,
            "velocity": 0.0, "volatility": 0.0, "unique_est": int(viewers * 1.3),
            "chat_rate": 0.0, "chat_density": 0.0, "emote_ratio": 0.0,
            "sentiment": 0.0, "avg_msg_len": 0.0, "new_chatters": 0,
            "cat_rank": 1, "duration": "—", "game_changes": 0,
            "title_score": 30, "tag_score": 30, "freshness": 0,
            "follow_rate": 0.0, "growth_trajectory": viewers, "loyalty": 50,
            "discovery": 30, "raid_potential": 20, "network_effect": 50,
            "bounce_rate": 40, "session_depth": 20, "peak_efficiency": 0.0,
            "consistency": 60, "uptime_score": 95, "stream_health": 50,
            "competitive_index": 50, "audience_match": 50, "optimal_remaining": "—",
            "best_category": "—", "monetization": 30, "overall_rank": "C",
        }

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
            
            # Update dashboard with fresh analysis (triggers 36-metric update)
            if hasattr(self, 'chat_panel') and self.chat_panel:
                debug(f"[MAIN MENU] Calling chat_panel.update_ai_metrics()")
                self.chat_panel.update_ai_metrics(analysis)
                debug(f"[MAIN MENU] Dashboard metrics updated")
            
            # Update commentator panel if it's showing this channel
            if hasattr(self, 'next_panel') and self.next_panel:
                next_channel = getattr(self.next_panel, '_current_channel', None)
                if next_channel == login:
                    if hasattr(self.next_panel, 'update_commentary'):
                        self.next_panel.update_commentary(analysis)
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
        """Periodically refresh the live channels list.

        Every 3 seconds:
        - If the list is empty, do a full API fetch.
        - Otherwise, ensure the current stream is in the list and
          update the LiveFollowed panel with the latest viewer counts
          from self.live_channels (which ViewerMonitor keeps fresh).
        - Every 5th tick (≈15 s), do a full API re-fetch so the list
          stays up-to-date with channels going live/offline.
        """
        if self.is_closing or not self.user:
            return

        # Counter for periodic full refresh
        if not hasattr(self, '_live_refresh_counter'):
            self._live_refresh_counter = 0
        self._live_refresh_counter += 1

        if not self.live_channels:
            debug("[LIVE CHANNELS] Refreshing (empty list)")
            self.load_live_channels()
            return

        # Ensure current stream is in the list
        if self.current_stream:
            current_login = self.current_stream.get('user_login')
            in_list = any(
                s.get('user_login') == current_login
                for s in self.live_channels
            )
            if not in_list:
                debug(f"[LIVE CHANNELS] Adding current_stream {current_login} to list")
                self.live_channels.append(self.current_stream)

        # Push latest viewer counts to the LiveFollowed panel every tick
        self.live_followed_panel.set_streams(list(self.live_channels))

        # Full API re-fetch every 5 ticks (~15 seconds)
        if self._live_refresh_counter >= 5:
            self._live_refresh_counter = 0
            debug("[LIVE CHANNELS] Periodic full refresh")
            self.load_live_channels()

    def _analyze_stream_frame(self):
        """Capture a screenshot from the video window and send to GPT-4o Vision.

        Called by _vision_timer on the GUI thread. Capture runs here (safe for
        Qt widgets), then the Azure API call runs in a background thread so
        the UI never freezes.
        """
        if self.is_closing:
            return

        # Only analyze if video is playing
        try:
            state = self.video_window.get_player_state()
            if not state or not state.get("playing"):
                return
        except Exception:
            return

        # Capture screenshot directly on the GUI thread (safe — we're already here)
        try:
            from core.vision_client import capture_widget_screenshot, analyze_frame
            image_bytes = capture_widget_screenshot(self.video_window)
        except Exception as e:
            debug(f"[VISION] Capture failed: {e}")
            return

        if not image_bytes:
            return

        debug(f"[VISION] Captured {len(image_bytes)} bytes, sending to Azure...")

        # Send to Azure in a background thread to avoid blocking the UI
        import threading

        def bg_analyze():
            try:
                observation = analyze_frame(image_bytes)
                if observation:
                    # Deliver result to GUI thread
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(
                        0,
                        lambda: self.chat_panel.dashboard.ticker.add_insight(
                            f"🎬 {observation}", "#aa44ff"
                        ),
                    )
                    debug(f"[VISION] Observation: {observation[:80]}...")
                else:
                    debug("[VISION] Azure returned empty observation")
            except Exception as e:
                debug(f"[VISION] Azure analysis error: {e}")

        threading.Thread(target=bg_analyze, daemon=True).start()

    def _feed_vision_to_commentator(self, observation: str):
        """Feed a GPT-4o vision observation directly to the commentator."""
        if hasattr(self, 'next_panel') and self.next_panel:
            bot = getattr(self.next_panel, 'bot', None)
            bubble = getattr(self.next_panel, 'bubble', None)
            if bot and bubble:
                bot.set_expression("mind_blown")
                bubble.show_text(f"🎬 {observation}", "#aa44ff")

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
        for timer in [self._video_timer, self._momsg_timer, self._live_timer, self._vision_timer]:
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
