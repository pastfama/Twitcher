"""Raid monitor — watches for Twitch raids via EventSub websocket.

All blocking work happens on daemon threads. Has its own QTimer
for periodic reconnection checks.

EventSub websocket protocol (per Twitch docs):
- Server sends a ``session_welcome`` message with a session id.
- Client must POST a subscription using that session id.
- Notifications arrive as ``notification`` messages with
  ``metadata.message_type`` and ``payload.subscription.type``.
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
        self._session_id = None

        # Timer for periodic reconnection checks
        self._timer = QTimer(self)
        self._timer.setInterval(check_interval_ms)
        self._timer.timeout.connect(self._on_tick)

    def set_channel(self, channel):
        """Set the channel to monitor for incoming raids.

        Restarts the websocket connection so the new channel's
        subscription is registered.
        """
        channel = str(channel or "").strip().lower()
        if not channel:
            return
        self.current_channel = channel
        self._close()
        self._launch_ws()

    def start(self):
        """Start the raid monitor."""
        self._timer.start()
        if self.current_channel:
            self._launch_ws()
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
            metadata = data.get("metadata", {})
            message_type = metadata.get("message_type", "")

            if message_type == "session_welcome":
                self._on_session_welcome(data)
            elif message_type == "notification":
                self._on_notification(data)
            elif message_type == "session_reconnect":
                # Reconnect with a new websocket URL (not implemented —
                # the periodic timer will reconnect on the next tick).
                logger.debug("[RAID MONITOR] session_reconnect received")
        except Exception as exc:
            logger.debug("[RAID MONITOR] Message handling error: %s", exc)

    def _on_session_welcome(self, data):
        """Register the raid subscription using the session id."""
        payload = data.get("payload", {})
        session = payload.get("session", {})
        self._session_id = session.get("id")
        if not self._session_id:
            logger.debug("[RAID MONITOR] No session id in welcome")
            return

        channel = self.current_channel
        if not channel:
            return

        try:
            # Resolve the broadcaster user id for the channel.
            user = self.api.get_user(channel)
            if not user:
                logger.debug("[RAID MONITOR] Could not resolve user for %s", channel)
                return
            broadcaster_id = user.get("id")
            if not broadcaster_id:
                logger.debug("[RAID MONITOR] No user id for %s", channel)
                return

            self.api.subscribe_to_raid(
                broadcaster_user_id=broadcaster_id,
                session_id=self._session_id,
                direction="to",
            )
            self.signals.status.emit(
                f"Raid monitor subscribed for #{channel}"
            )
        except Exception as exc:
            logger.debug("[RAID MONITOR] Subscription error: %s", exc)
            self.signals.error.emit(f"Raid subscription failed: {exc}")

    def _on_notification(self, data):
        """Handle an EventSub notification."""
        payload = data.get("payload", {})
        subscription = payload.get("subscription", {})
        event_type = subscription.get("type", "")
        event = payload.get("event", {})

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

    def _close(self):
        ws = None
        loop = None
        with self._lock:
            ws = self._ws
            loop = self._loop
            self._ws = None
            self._loop = None
            self._session_id = None
        self._stop_event.set()
        if ws is not None and loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(ws.close(), loop)