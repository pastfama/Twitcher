"""Periodic live-channel monitor.  All API calls run on the
QThreadPool so the GUI thread never blocks.

Supports all platforms (Twitch, Kick, YouTube) by routing each
channel through the platform manager based on its ``platform`` field.
"""

from PySide6.QtCore import QObject, QTimer

from core.workers import run_in_background
from logger import debug


class ViewerMonitor(QObject):
    """Live-channel monitor with its own QTimer.

    Periodically checks live channels and dispatches per-channel checks
    to the thread pool. No network I/O happens on the GUI thread.
    """

    def __init__(
        self,
        api,
        tracker,
        get_live_channels,
        update_callback,
        analytics_engine=None,
        interval_ms=4000,
    ):

        super().__init__()

        self.api = api
        self.tracker = tracker
        self.get_live_channels = get_live_channels
        self.update_callback = update_callback
        self.analytics_engine = analytics_engine

        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.tick)

    def start(self):
        """Start the periodic monitoring."""
        self._timer.start()
        debug("[VIEWER MONITOR] Started")

    def stop(self):
        """Stop the periodic monitoring."""
        self._timer.stop()
        debug("[VIEWER MONITOR] Stopped")

    def tick(self):
        """Called on every timer tick.

        Dispatches per-channel checks to the thread pool and returns
        immediately.
        """

        try:

            channels = self.get_live_channels()
            debug(f"[VIEWER MONITOR] Got {len(channels)} channels from get_live_channels()")

            if not channels:
                debug("[VIEWER MONITOR] No live channels")
                return

            for channel in channels:

                try:

                    if isinstance(channel, str):

                        login = channel
                        platform = "twitch"

                    else:

                        login = (
                            channel.get("user_login")
                            or channel.get("user_name")
                            or channel.get("channel")
                            or channel.get("broadcaster_login")
                        )

                        platform = (
                            channel.get("platform")
                            or "twitch"
                        )

                    if not login:
                        continue

                    run_in_background(
                        lambda login=login, platform=platform: self._check_channel(login, platform),
                        lambda result, login=login: self._on_channel_checked(login, result),
                        lambda message, login=login: self._on_channel_error(login, message),
                    )

                except Exception as exc:

                    debug(f"[VIEWER MONITOR] {login} dispatch error: {exc}")

        except Exception as exc:

            debug(f"[VIEWER MONITOR ERROR] {exc}")

    def _check_channel(self, login, platform="twitch"):
        """Runs on a thread-pool thread.  Returns (stream, analytics)."""

        stream = self._get_stream_info(login, platform)

        if not stream:
            return None

        analytics = None

        if self.analytics_engine:
            analytics = self.analytics_engine.update_stream(stream)
        elif self.tracker:
            analytics = self.tracker.update_stream(stream)

        return stream, analytics

    def _get_stream_info(self, login, platform):
        """Fetch stream info for the correct platform.

        Twitch uses the main Twitch API client; Kick and YouTube use
        the unified platform manager.
        """
        try:
            if platform == "twitch":
                return self.api.get_stream_info(login)

            from platforms import get_platform_manager
            pm = get_platform_manager()
            return pm.get_stream_info(platform, login)
        except Exception as exc:
            debug(f"[VIEWER MONITOR] {platform}/{login} fetch error: {exc}")
            return None

    def _on_channel_checked(self, login, result):
        """Delivered on the GUI thread with the worker's result."""

        try:

            if not result:
                debug(f"[VIEWER MONITOR] No result for {login}")
                return

            stream, analytics = result
            debug(f"[VIEWER MONITOR] Result for {login}: viewers={stream.get('viewer_count', 0)}")

            if self.update_callback:
                self.update_callback(stream, analytics)

        except Exception as exc:

            debug(f"[VIEWER MONITOR] {login} callback error: {exc}")

    def _on_channel_error(self, login, message):

        debug(f"[VIEWER MONITOR] {login} error: {message}")