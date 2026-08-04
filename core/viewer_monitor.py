"""Periodic live-channel monitor.  All Twitch API calls run on the
QThreadPool so the GUI thread never blocks.
"""

from PySide6.QtCore import QObject

from core.workers import run_in_background


class ViewerMonitor(QObject):
    """Live-channel monitor driven by the central TimeBoss.

    IMPORTANT: This no longer owns its own QTimer.  The app's TimeBoss
    calls :meth:`tick` every refresh cycle.  That method only *dispatches*
    work to the thread pool — no network I/O, no tracker/UI updates here.
    """

    def __init__(
        self,
        api,
        tracker,
        get_live_channels,
        update_callback,
        analytics_engine=None,
    ):

        super().__init__()

        self.api = api
        self.tracker = tracker
        self.get_live_channels = get_live_channels
        self.update_callback = update_callback
        self.analytics_engine = analytics_engine

    # ================================================================
    # TIME-BOSS INTERFACE
    # ================================================================

    # ================================================================
    # LIFECYCLE (called by TimeBoss owner, typically MainMenu)
    # ================================================================

    def start(self, time_boss):
        """Register this monitor with the central TimeBoss."""
        time_boss.register("viewer_monitor", self.tick)

    def stop(self, time_boss):
        """Unregister from the TimeBoss."""
        time_boss.unregister("viewer_monitor", self.tick)

    def tick(self):
        """Called by TimeBoss on every refresh cycle.

        Dispatches per-channel checks to the thread pool and returns
        immediately.
        """

        print(
            "[VIEWER MONITOR] Tick (dispatching)"
        )

        try:

            channels = self.get_live_channels()

            if not channels:
                print(
                    "[VIEWER MONITOR] No live channels"
                )
                return

            for channel in channels:

                try:

                    if isinstance(channel, str):

                        login = channel

                    else:

                        login = (
                            channel.get("user_login")
                            or channel.get("user_name")
                            or channel.get("broadcaster_login")
                        )

                    if not login:
                        continue

                    # --------------------------------------------------
                    # All blocking Twitch API + tracker work happens on
                    # the thread pool; the callback is delivered back on
                    # the GUI thread via the queued signal in workers.py
                    # --------------------------------------------------

                    run_in_background(
                        lambda login=login: self._check_channel(login),
                        lambda stream, login=login: self._on_channel_checked(login, stream),
                        lambda message, login=login: self._on_channel_error(login, message),
                    )

                except Exception as exc:

                    print(
                        f"[VIEWER MONITOR] {login} dispatch error: {exc}"
                    )

        except Exception as exc:

            print(
                f"[VIEWER MONITOR ERROR] {exc}"
            )

    # ================================================================
    # WORKER THREAD WORK
    # ================================================================

    def _check_channel(self, login):
        """Runs on a thread-pool thread.  Returns (stream, analytics)."""

        stream = self.api.get_stream_info(
            login
        )

        if not stream:
            return None

        analytics = None

        # Use the shared AnalyticsEngine if provided; otherwise fall back
        # to the legacy tracker.  Creating a new engine per-channel per-tick
        # exhausts the thread pool and hangs the GUI.
        if self.analytics_engine:

            analytics = self.analytics_engine.update_stream(
                stream
            )

        elif self.tracker:

            analytics = self.tracker.update_stream(
                stream
            )

        return stream, analytics

    # ================================================================
    # GUI-THREAD CALLBACKS (queued by run_in_background)
    # ================================================================

    @staticmethod
    def _safe_print(text):
        """Print to console, replacing non-ASCII chars safely."""
        try:
            print(text)
        except UnicodeEncodeError:
            safe = text.encode("ascii", errors="replace").decode("ascii")
            print(safe)

    def _on_channel_checked(self, login, result):
        """Delivered on the GUI thread with the worker's result."""

        try:

            if not result:
                return

            stream, analytics = result

            # The analytics dict contains emoji status labels (🚀🟢📉🔴🟡),
            # which are fine for Qt UI but crash Windows console print()
            # with the charmap codec. Convert to a safe string first.
            analytics_text = ""
            if analytics:
                status = analytics.get("status", "")
                safe_status = status.encode("ascii", errors="replace").decode("ascii") if isinstance(status, str) else str(status)
                analytics_text = f" ({safe_status})"

            if self.update_callback:

                self.update_callback(
                    stream
                )

            self._safe_print(
                f"[VIEWER MONITOR] "
                f"{login}: "
                f"{stream.get('viewer_count', 0)} viewers"
                f"{analytics_text}"
            )

        except Exception as exc:

            self._safe_print(
                f"[VIEWER MONITOR] {login} callback error: {exc}"
            )

    def _on_channel_error(self, login, message):

        print(
            f"[VIEWER MONITOR] {login} error: {message}"
        )