import os

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMainWindow

from logger import debug
from video import VideoWindow
from core import StreamDispatcher, RaidMonitor, ViewerTracker, ViewerMonitor, wait_for_pending, TimeBoss
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


class MainMenu(
    QMainWindow,
    MainMenuWindowState,
    MainMenuRuntime,
    MainMenuStreamState,
    MainMenuRaidRuntime
):

    def __init__(self, api, video_window=None):

        super().__init__()

        self.api = api

        self._injected_video_window = video_window

        self.settings = QSettings(
            "Twitcher",
            "TwitcherControlCenter"
        )

        self.user = None
        self.live_channels = []
        self.current_stream = None
        self.current_channel = None
        self.next_stream = None

        self.resume_attempted = False
        self.is_closing = False
        self.raid_transition_active = False
        self.is_loading_channels = False
        self.pending_channel = None

        self.video_window = self._injected_video_window or VideoWindow()
        self.log_window = None


        #
        # Analytics system
        #
        self.viewer_tracker = ViewerTracker()

        self.analytics_engine = AnalyticsEngine(
            viewer_tracker=self.viewer_tracker
        )


        self.time_boss = TimeBoss(self)

        self.viewer_monitor = ViewerMonitor(
            api=self.api,
            tracker=self.viewer_tracker,
            get_live_channels=self._fetch_live_channels,
            update_callback=self.update_current_stream_view,
            analytics_engine=self.analytics_engine,
        )


        self.avatar_cache = {}

        self.project_root = PROJECT_ROOT

        self.current_panel_cls = CurrentWatchingPanel
        self.next_panel_cls = NextStreamPanel
        self.live_followed_panel_cls = LiveFollowedPanel
        self.chat_panel_cls = ChatPanel
        self.dispatcher_panel_cls = DispatcherPanel


        self.raid_monitor = RaidMonitor(
            self.api
        )


        self.raid_monitor.signals.raid_detected.connect(
            self.handle_raid
        )

        self.raid_monitor.signals.status.connect(
            self.handle_raid_status
        )

        self.raid_monitor.signals.error.connect(
            self.handle_raid_error
        )


        # Register raid monitor with TimeBoss (no separate thread timer).
        self.raid_monitor.start(self.time_boss)


        self.dispatcher = StreamDispatcher(
            api=self.api,
            video_window=self.video_window,
            on_status=self.handle_dispatcher_status,
            on_log=self.handle_dispatcher_log,
            on_stream_changed=self.handle_stream_changed,
            on_raid_announcement=self.handle_raid_announcement,
        )


        self.setWindowTitle(
            "Twitcher Control Center"
        )

        self.setMinimumSize(
            1400,
            800
        )


        self.build_interface()

        self.restore_window_geometry()


        # Give TimeBoss direct control of the video window (highest priority).
        self.time_boss.set_video_window(self.video_window)

        # Register video auto-play as the highest-priority slot.
        # This makes the video window completely independent of Twitch auth:
        # it only uses local channel history + the auth-free stream resolver.
        self.time_boss.register(
            "video_player",
            lambda: self.time_boss.ensure_video_playing(self._get_recent_channels_for_video),
            priority=TimeBoss.PRIORITY_VIDEO,
        )

        self.viewer_monitor.start(self.time_boss)

        # Register a TimeBoss task to periodically fetch SG data for live channels.
        self.time_boss.register(
            "sg_fetch",
            lambda: self.analytics_engine.fetch_all_live_channels(
                self.live_channels
            ),
            priority=TimeBoss.PRIORITY_ANALYTICS,
        )

        self.time_boss.start()

        self.log(
            "Viewer monitor started (TimeBoss-driven)."
        )

        # Restore cached streamer data into UI panels so they render
        # immediately without waiting for Twitch API responses.
        self._load_cached_streamer_data()


        self.load_twitch()



    def _get_recent_channels_for_video(self):
        """Return recent channels for TimeBoss video auto-play from DB."""
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
                full = get_streamer(login)
                avatar = full.get("avatar_url")
                if avatar:
                    self.avatar_cache[login] = avatar
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
            or ""
        ).strip()


        if not login:
            return stream_data


        if login in self.avatar_cache:

            stream_data["avatar_url"] = self.avatar_cache[login]

            return stream_data


        try:

            profile = self.api.get_user_profile(
                login
            )


        except Exception as exc:

            self.log(
                f"Could not fetch avatar for {login}: {exc}"
            )

            return stream_data


        avatar_url = str(
            profile.get("profile_image_url")
            or ""
        ).strip()


        if avatar_url:

            self.avatar_cache[login] = avatar_url

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


        self.current_channel = (
            channel.lower().strip()
        )


        #
        # Needed by ViewerMonitor
        #
        self.current_stream = {
            "user_login": self.current_channel,
            "user_name": self.current_channel
        }


        self.save_last_streamer(
            self.current_channel
        )


        self.log(
            f"Current stream changed to #{self.current_channel}"
        )


        self.update_next_stream()



    def handle_raid_announcement(self, data):

        announcement_type = data.get(
            "type"
        )


        if announcement_type == "raid":

            self.log(
                f"📢 RAID: {data.get('from_streamer','unknown')} → "
                f"{data.get('to_streamer','unknown')} "
                f"({data.get('viewers',0):,} viewers)"
            )


        elif announcement_type == "stream":

            self.log(
                f"📢 STREAM ANNOUNCEMENT: "
                f"{data.get('streamer','unknown')}"
            )



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
            self.viewer_monitor.stop(self.time_boss)
        except Exception:
            pass

        try:
            self.raid_monitor.stop(self.time_boss)
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