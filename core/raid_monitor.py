"""Raid monitor driven by the central TimeBoss via EventSub websocket.

All blocking work happens on the thread pool.  The websocket connection
is managed by the TimeBoss cycle; the monitor only registers interest
and receives events through signals.
"""

import asyncio
import json
import logging
import threading
import time

import websockets

from PySide6.QtCore import QObject, Signal, Slot


logger = logging.getLogger(__name__)


class RaidSignals(QObject):
    raid_detected = Signal(str, str)
    status = Signal(str)
    error = Signal(str)


class RaidMonitor(QObject):
    """Monitor Twitch raids via EventSub websocket.

    Lifecycle is controlled by the app's TimeBoss: :meth:`tick` is
    called on every refresh cycle and manages the websocket connection.
    """

    def __init__(self, api, reconnect_delay=5):
        super().__init__()
        self.api = api
        self.reconnect_delay = reconnect_delay

        self.signals = RaidSignals()
        self.current_channel = None
        self._ws = None
        self._task = None
        self._loop = None
        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._last_connect = 0

    # ================================================================
    # TIME-BOSS INTERFACE
    # ================================================================

    def start(self, time_boss):
        """Register with TimeBoss."""
        time_boss.register("raid_monitor", self.tick)

    def stop(self, time_boss):
        """Unregister and close websocket."""
        time_boss.unregister("raid_monitor", self.tick)
        self._close()

    def tick(self):
        """Called by TimeBoss on every refresh cycle."""
        if self._stop_event.is_set():
            return
        if not self.current_channel:
            return
        # Reconnect periodically to keep the websocket fresh.
        now = time.monotonic()
        if self._ws is None or now - self._last_connect > 300:
            self._launch_ws()

    # ================================================================
    # WEBSOCKET LIFECYCLE
    # ================================================================

    def _launch_ws(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._ws_thread,
            daemon=True,
        )
        self._thread.start()

    def _ws_thread(self):
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._connect())
        except Exception as exc:
            logger.debug("[RAID MONITOR] WS thread error: %s", exc)
        finally:
            self._close()

    async def _connect(self):
        url = (
            "wss://eventsub.wss.twitch.tv/ws"
        )
        try:
            async with websockets.connect(url) as ws:
                self._ws = ws
                self._last_connect = time.monotonic()
                self.signals.status.emit(
                    f"Raid monitor connected for #{self.current_channel}"
                )
                async for msg in ws:
                    self._handle_message(msg)
        except Exception as exc:
            logger.debug("[RAID MONITOR] WS error: %s", exc)

    def _handle_message(self, raw):
        try:
            data = json.loads(raw)
            payload = data.get("payload", {})
            msg_type = payload.get("type")
            if msg_type == "notification":
                event = payload.get("event", {})
                event_type = event.get("type", "")
                if event_type == "channel.raid":
                    from_broadcaster = event.get("from_broadcaster_user_name", "?")
                    to_broadcaster = event.get("to_broadcaster_user_name", "?")
                    viewers = event.get("viewers", 0)
                    self.signals.raid_detected.emit(
                        from_broadcaster,
                        to_broadcaster,
                    )
                    self.signals.status.emit(
                        f"Raid incoming: {viewers} viewers"
                    )
        except Exception:
            pass

    def _close(self):
        with self._lock:
            self._ws = None
        self._stop_event.set()