import asyncio
import json
import threading
import time

import websockets

from PySide6.QtCore import QObject, Signal


EVENTSUB_URL = (
    "wss://eventsub.wss.twitch.tv/ws"
)


class RaidSignals(QObject):

    raid_detected = Signal(
        str,
        str
    )

    status = Signal(
        str
    )

    error = Signal(
        str
    )


class RaidMonitor:

    def __init__(

        self,

        api

    ):

        self.api = api

        self.signals = RaidSignals()

        self.thread = None

        self.running = False

        self.current_channel = None

        self.stop_event = threading.Event()

        self.lock = threading.Lock()

        print(

            "[RAID MONITOR] Initialized."

        )


    # ========================================================
    # START
    # ========================================================

    def start(

        self,

        channel

    ):

        if not channel:

            self.signals.error.emit(

                "Cannot start raid monitor without a channel."

            )

            return

        channel = (

            str(channel)

            .strip()

            .lower()

            .lstrip("#")

        )

        self.stop()

        with self.lock:

            self.current_channel = channel

            self.running = True

            self.stop_event.clear()

        self.thread = threading.Thread(

            target=self._thread_worker,

            name="RaidMonitor",

            daemon=True

        )

        self.thread.start()

        self.signals.status.emit(

            f"Raid monitor started for {channel}"

        )


    # ========================================================
    # STOP
    # ========================================================

    def stop(

        self

    ):

        with self.lock:

            was_running = self.running

            self.running = False

            self.current_channel = None

            self.stop_event.set()

        if was_running:

            self.signals.status.emit(

                "Raid monitor stopped."

            )


    # ========================================================
    # THREAD WORKER
    # ========================================================

    def _thread_worker(

        self

    ):

        try:

            asyncio.run(

                self._async_worker()

            )

        except Exception as error:

            if self.is_running():

                self.signals.error.emit(

                    f"Raid monitor thread error: {error}"

                )


    # ========================================================
    # ASYNC WORKER
    # ========================================================

    async def _async_worker(

        self

    ):

        while self.is_running():

            channel = self.get_current_channel()

            if not channel:

                return

            try:

                await self._monitor_channel(

                    channel

                )

            except asyncio.CancelledError:

                return

            except Exception as error:

                if not self.is_running():

                    return

                self.signals.error.emit(

                    f"Raid monitor error: {error}"

                )

                self.signals.status.emit(

                    "Raid monitor reconnecting in 5 seconds..."

                )

                await self._sleep_interruptible(

                    5

                )


    # ========================================================
    # MONITOR CHANNEL
    # ========================================================

    async def _monitor_channel(

        self,

        channel

    ):

        self.signals.status.emit(

            f"Connecting to Twitch EventSub for {channel}..."

        )

        async with websockets.connect(

            EVENTSUB_URL,

            ping_interval=20,

            ping_timeout=20,

            close_timeout=10,

        ) as websocket:

            self.signals.status.emit(

                f"EventSub WebSocket connected for {channel}"

            )

            # ------------------------------------------------
            # WELCOME
            # ------------------------------------------------

            raw_message = await websocket.recv()

            welcome = json.loads(

                raw_message

            )

            metadata = welcome.get(

                "metadata",

                {}

            )

            if metadata.get(

                "message_type"

            ) != "session_welcome":

                raise RuntimeError(

                    "Expected EventSub session_welcome."

                )

            session = (

                welcome

                .get(

                    "payload",

                    {}

                )

                .get(

                    "session",

                    {}

                )

            )

            session_id = session.get(

                "id"

            )

            if not session_id:

                raise RuntimeError(

                    "EventSub did not provide a session ID."

                )

            self.signals.status.emit(

                "EventSub session established."

            )

            # ------------------------------------------------
            # RESOLVE CHANNEL
            # ------------------------------------------------

            user = self.api.get_user(

                channel

            )

            if not user:

                raise RuntimeError(

                    f"Could not resolve Twitch user: {channel}"

                )

            broadcaster_id = str(

                user.get(

                    "id",

                    ""

                )

            )

            if not broadcaster_id:

                raise RuntimeError(

                    f"No broadcaster ID found for {channel}"

                )

            self.signals.status.emit(

                f"Resolved {channel} to Twitch ID "

                f"{broadcaster_id}"

            )

            # ------------------------------------------------
            # CREATE EVENTSUB SUBSCRIPTION
            # ------------------------------------------------

            self.signals.status.emit(

                "Creating Twitch raid subscription..."

            )

            result = self.api.subscribe_to_raid(

                broadcaster_user_id=broadcaster_id,

                session_id=session_id

            )

            if not result:

                raise RuntimeError(

                    "Twitch returned an empty raid subscription response."

                )

            self.signals.status.emit(

                f"🟢 Monitoring raids from #{channel}"

            )

            # ------------------------------------------------
            # LISTEN
            # ------------------------------------------------

            while self.is_running():

                if (

                    self.get_current_channel()

                    != channel

                ):

                    self.signals.status.emit(

                        "Monitored channel changed."

                    )

                    return

                raw_message = await websocket.recv()

                message = json.loads(

                    raw_message

                )

                metadata = message.get(

                    "metadata",

                    {}

                )

                message_type = metadata.get(

                    "message_type"

                )

                # ------------------------------------------------
                # KEEPALIVE
                # ------------------------------------------------

                if message_type == "session_keepalive":

                    continue

                # ------------------------------------------------
                # RECONNECT
                # ------------------------------------------------

                if message_type == "session_reconnect":

                    self.signals.status.emit(

                        "Twitch requested EventSub reconnect."

                    )

                    return

                # ------------------------------------------------
                # IGNORE NON-NOTIFICATIONS
                # ------------------------------------------------

                if message_type != "notification":

                    continue

                if metadata.get(

                    "subscription_type"

                ) != "channel.raid":

                    continue

                # ------------------------------------------------
                # RAID EVENT
                # ------------------------------------------------

                payload = message.get(

                    "payload",

                    {}

                )

                event = payload.get(

                    "event",

                    {}

                )

                from_channel = (

                    event.get(

                        "from_broadcaster_user_login"

                    )

                    or ""

                )

                to_channel = (

                    event.get(

                        "to_broadcaster_user_login"

                    )

                    or ""

                )

                from_channel = (

                    from_channel

                    .strip()

                    .lower()

                )

                to_channel = (

                    to_channel

                    .strip()

                    .lower()

                )

                if not from_channel or not to_channel:

                    continue

                self.signals.status.emit(

                    f"Raid detected: "

                    f"{from_channel} → {to_channel}"

                )

                self.signals.raid_detected.emit(

                    from_channel,

                    to_channel

                )

                return


    # ========================================================
    # STATE
    # ========================================================

    def is_running(

        self

    ):

        with self.lock:

            return self.running


    def get_current_channel(

        self

    ):

        with self.lock:

            return self.current_channel


    # ========================================================
    # INTERRUPTIBLE SLEEP
    # ========================================================

    async def _sleep_interruptible(

        self,

        seconds

    ):

        end_time = (

            time.monotonic()

            + seconds

        )

        while self.is_running():

            remaining = (

                end_time

                - time.monotonic()

            )

            if remaining <= 0:

                return

            await asyncio.sleep(

                min(

                    0.25,

                    remaining

                )

            )


    # ========================================================
    # SHUTDOWN
    # ========================================================

    def shutdown(

        self

    ):

        self.stop()

        self.signals.status.emit(

            "Raid monitor shut down."

        )