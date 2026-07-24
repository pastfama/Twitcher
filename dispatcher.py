from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, Signal


# ============================================================
#                    STREAM DISPATCHER
# ============================================================


class DispatcherSignals(QObject):

    status = Signal(str)

    log = Signal(str)

    stream_changed = Signal(dict)

    raid_announcement = Signal(dict)


# ============================================================
#                    STREAM DISPATCHER
# ============================================================


class StreamDispatcher:

    def __init__(
        self,
        api,
        video_window,
        on_status=None,
        on_log=None,
        on_stream_changed=None,
        on_raid_announcement=None,
    ):

        self.api = api

        self.video_window = video_window

        # ----------------------------------------------------
        # CALLBACKS
        # ----------------------------------------------------

        self.on_status = on_status

        self.on_log = on_log

        self.on_stream_changed = on_stream_changed

        self.on_raid_announcement = on_raid_announcement

        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

        self.current_streamer = None

        self.current_url = None

        self.is_running = False

        self.is_switching = False

        self.is_shutdown = False

        self.lock = threading.RLock()

        # ----------------------------------------------------
        # SIGNALS
        # ----------------------------------------------------

        self.signals = DispatcherSignals()

        # ----------------------------------------------------
        # STARTUP
        # ----------------------------------------------------

        self.status(

            "Dispatcher ready."

        )

    # ========================================================
    # CALLBACK HELPERS
    # ========================================================

    def status(

        self,

        message,

    ):

        message = str(

            message

        )

        if self.on_status:

            try:

                self.on_status(

                    message

                )

            except Exception:

                pass

        try:

            self.signals.status.emit(

                message

            )

        except Exception:

            pass

    # ========================================================

    def log(

        self,

        message,

    ):

        message = str(

            message

        )

        if self.on_log:

            try:

                self.on_log(

                    message

                )

            except Exception:

                pass

        try:

            self.signals.log.emit(

                message

            )

        except Exception:

            pass

    # ========================================================
    # STREAM DATA
    # ========================================================

    def build_stream_data(

        self,

        streamer,

        url,

    ):

        return {

            "streamer": streamer,

            "url": url,

            "timestamp": time.time(),

        }

    # ========================================================
    # SWITCH STREAM
    # ========================================================

    def switch_stream(

        self,

        streamer,

        url,

        announce=False,

    ):

        streamer = (

            str(

                streamer

            )

            .strip()

            .lower()

        )

        if not streamer:

            self.log(

                "Cannot switch to empty streamer."

            )

            return False

        if not url:

            self.log(

                f"No stream URL received for #{streamer}."

            )

            return False

        with self.lock:

            if self.is_shutdown:

                self.log(

                    "Dispatcher is shut down."

                )

                return False

            if self.is_switching:

                self.log(

                    "Stream switch already in progress."

                )

                return False

            self.is_switching = True

        try:

            self.status(

                f"Switching to #{streamer}..."

            )

            self.log(

                f"Loading stream: #{streamer}"

            )

            # ------------------------------------------------
            # STOP CURRENT VIDEO
            # ------------------------------------------------

            try:

                self.video_window.stop_video()

            except Exception as error:

                self.log(

                    f"Could not stop previous video: {error}"

                )

            # ------------------------------------------------
            # START NEW VIDEO
            # ------------------------------------------------

            self.video_window.start_video(

                url

            )

            # ------------------------------------------------
            # UPDATE STATE
            # ------------------------------------------------

            with self.lock:

                self.current_streamer = streamer

                self.current_url = url

                self.is_running = True

            stream_data = self.build_stream_data(

                streamer,

                url,

            )

            # ------------------------------------------------
            # CALLBACK
            # ------------------------------------------------

            if self.on_stream_changed:

                try:

                    self.on_stream_changed(

                        stream_data

                    )

                except Exception as error:

                    self.log(

                        f"Stream changed callback error: "

                        f"{error}"

                    )

            try:

                self.signals.stream_changed.emit(

                    stream_data

                )

            except Exception:

                pass

            if announce:

                self.announce_stream(

                    streamer

                )

            self.status(

                f"▶ Watching #{streamer}"

            )

            self.log(

                f"Stream switched successfully to #{streamer}."

            )

            return True

        except Exception as error:

            self.log(

                f"Stream switch failed: {error}"

            )

            self.status(

                "Stream switch failed."

            )

            return False

        finally:

            with self.lock:

                self.is_switching = False

    # ========================================================
    # RAID SWITCH
    # ========================================================

    def handle_raid(

        self,

        from_streamer,

        to_streamer,

    ):

        from_streamer = (

            str(

                from_streamer

            )

            .strip()

            .lower()

        )

        to_streamer = (

            str(

                to_streamer

            )

            .strip()

            .lower()

        )

        if not to_streamer:

            self.log(

                "Raid destination is empty."

            )

            return False

        if (

            from_streamer

            and

            from_streamer == to_streamer

        ):

            self.log(

                "Raid destination is the current streamer."

            )

            return False

        self.status(

            f"Raid detected: #{from_streamer} → #{to_streamer}"

        )

        self.log(

            f"Resolving raid destination #{to_streamer}..."

        )

        try:

            url = self.api.get_stream_url(

                to_streamer

            )

            switched = self.switch_stream(

                streamer=to_streamer,

                url=url,

                announce=False,

            )

            if not switched:

                self.log(

                    "Raid stream switch failed."

                )

                return False

            self.announce_raid(

                from_streamer,

                to_streamer,

            )

            return True

        except Exception as error:

            self.log(

                f"Raid resolution error: {error}"

            )

            return False

    # ========================================================
    # STREAM ANNOUNCEMENT
    # ========================================================

    def announce_stream(

        self,

        streamer,

    ):

        data = {

            "type": "stream",

            "streamer": streamer,

        }

        self.emit_announcement(

            data

        )

    # ========================================================
    # RAID ANNOUNCEMENT
    # ========================================================

    def announce_raid(

        self,

        from_streamer,

        to_streamer,

        viewers=0,

    ):

        data = {

            "type": "raid",

            "from_streamer": from_streamer,

            "to_streamer": to_streamer,

            "viewers": viewers,

        }

        self.emit_announcement(

            data

        )

    # ========================================================

    def emit_announcement(

        self,

        data,

    ):

        if self.on_raid_announcement:

            try:

                self.on_raid_announcement(

                    data

                )

            except Exception as error:

                self.log(

                    f"Announcement callback error: {error}"

                )

        try:

            self.signals.raid_announcement.emit(

                data

            )

        except Exception:

            pass

    # ========================================================
    # STOP
    # ========================================================

    def stop(self):

        with self.lock:

            if self.is_shutdown:

                return

            self.is_running = False

        try:

            self.video_window.stop_video()

        except Exception as error:

            self.log(

                f"Video stop error: {error}"

            )

        self.status(

            "Video stopped."

        )

        self.log(

            "Dispatcher stopped current stream."

        )

    # ========================================================
    # SHUTDOWN
    # ========================================================

    def shutdown(self):

        with self.lock:

            if self.is_shutdown:

                return

            self.is_shutdown = True

            self.is_running = False

            self.current_streamer = None

            self.current_url = None

        self.log(

            "Shutting down dispatcher..."

        )

        try:

            self.video_window.stop_video()

        except Exception:

            pass

        self.status(

            "Dispatcher shut down."

        )

        self.log(

            "Dispatcher shutdown complete."

        )