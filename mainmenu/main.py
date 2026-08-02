import os

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMainWindow

from logger import debug
from video import VideoWindow
from dispatcher import StreamDispatcher
from raid_monitor import RaidMonitor
from .app_runtime import MainMenuRuntime
from .channel_state import MainMenuStreamState
from .current_watching import CurrentWatchingPanel
from .dispatcher_panel import DispatcherPanel
from .live_followed import LiveFollowedPanel
from .chat_panel import ChatPanel
from .next_stream import NextStreamPanel
from .raid_runtime import MainMenuRaidRuntime
from .viewer_tracker import ViewerTracker
from .viewer_monitor import ViewerMonitor
from .analytics_engine import AnalyticsEngine
from .window_state import MainMenuWindowState
from .workers import wait_for_pending


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)


class MainMenu(
    QMainWindow,
    MainMenuWindowState,
    MainMenuRuntime,
    MainMenuStreamState,
    MainMenuRaidRuntime
):

    def __init__(self, api):

        super().__init__()

        self.api = api

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

        self.video_window = VideoWindow()
        self.log_window = None


        #
        # Analytics system
        #
        self.viewer_tracker = ViewerTracker()

        self.analytics_engine = AnalyticsEngine(
            viewer_tracker=self.viewer_tracker
        )


        self.viewer_monitor = ViewerMonitor(
            api=self.api,
            tracker=self.viewer_tracker,
            get_live_channels=lambda: self.live_channels,
            update_callback=self.update_current_stream_view
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


        self.viewer_monitor.start()

        self.log(
            "Viewer monitor started."
        )


        self.load_twitch()



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
            self.viewer_monitor.stop()
        except Exception:
            pass


        try:
            self.video_window.save_window_state()
        except Exception:
            pass


        try:
            self.raid_monitor.stop()
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