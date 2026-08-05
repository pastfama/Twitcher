"""Raid monitor — watches for Twitch raids via EventSub websocket.

All blocking work happens on daemon threads. Has its own QTimer
for periodic reconnection checks.
"""

import asyncio
import json
import logging
import threading
import time

import websockets

from PySide6.QtCore import QObject, QTimer, Signal, Slot


logger = logging.getLogger(__name__)


class RaidSignals(QObject):
    raid_detected = Signal(str, str)
    status = Signal(str)
    error = Signal(str)


class RaidMonitor(QObject):
    """Monitor Twitch raids via EventSub websocket.

    Has its own QTimer for periodic reconnection checks.
    """

    def __init__(self, api, reconnect_delay=5, check_interval_ms=300000):
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

        # Timer for periodic reconnection checks
        self._timer = QTimer(self)
        self._timer.setInterval(check_interval_ms)
        self._timer.timeout.connect(self._on_tick)

    def start(self):
        """Start the raid monitor."""
        self._timer.start()
        logger.debug("[RAID MONITOR] Started")

    def stop(self):
        """Stop the raid monitor."""
        self._timer.stop()
        self._close()
        logger.debug("[RAID MONITOR] Stopped")

    def _on_tick(self):
        """Called on every timer tick to check/reconnect websocket."""
        if self._stop_event.is_set():
            return
        if not self.current_channel:
            return
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
        url = "wss://eventsub.wss.twitch.tv/ws"
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
        ws = None
        loop = None
        with self._lock:
            ws = self._ws
            loop = self._loop
            self._ws = None
            self._loop = None
        self._stop_event.set()
        if ws is not None and loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(ws.close(), loop)