"""irc3-based Twitch IRC client with Qt signal bridge.

Wraps the ``irc3`` library to provide a QObject that emits Qt signals
for incoming messages, connection state, and errors.  The irc3 async
loop runs on the shared asyncio bridge thread.
"""

import asyncio
import threading
from typing import Optional

import irc3
from PySide6.QtCore import QObject, Signal

from logger import debug, info, warning, error
from core.async_bridge import run_async, run_sync, get_loop
from .handler import parse_irc_line

TWITCH_IRC_HOST = "irc.chat.twitch.tv"
TWITCH_IRC_PORT = 6697


class IRCClient(QObject):
    """Twitch IRC client backed by irc3, emitting Qt signals.

    Signals:
        - ``message_received(dict)`` -- parsed PRIVMSG
        - ``system_message(str)`` -- status/error text
        - ``connected()`` -- joined channel successfully
        - ``disconnected()`` -- connection lost or closed
    """

    message_received = Signal(dict)
    system_message = Signal(str)
    connected = Signal()
    disconnected = Signal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._irc = None
        self._token: str = ""
        self._username: str = ""
        self._channel: str = ""
        self._running = False
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._running

    @property
    def channel(self) -> str:
        return self._channel

    @property
    def username(self) -> str:
        return self._username

    def connect_to_channel(self, token: str, username: str, channel: str) -> bool:
        """Connect to Twitch IRC and join *channel*."""
        token = token.replace("oauth:", "").strip()
        username = username.strip().lower()
        channel = channel.strip().lower().lstrip("#")

        with self._lock:
            if self._running:
                self.disconnect()

            self._token = token
            self._username = username
            self._channel = channel

            try:
                self._start_irc3()
                self._running = True
                self.system_message.emit(f"Connecting to #{channel}...")
                return True
            except Exception as exc:
                error(f"[IRC] Failed to start irc3: {exc}")
                self.system_message.emit(f"Chat connection error: {exc}")
                return False

    def _start_irc3(self):
        """Create and start the irc3 IrcBot on the async bridge."""
        config = {
            "nick": self._username,
            "password": f"oauth:{self._token}",
            "host": TWITCH_IRC_HOST,
            "port": TWITCH_IRC_PORT,
            "ssl": True,
            "auto_reconnect": True,
            "includes": [
                "irc3.plugins.core",
            ],
        }

        self._irc = irc3.IrcBot(**config)
        self._irc._watcher_client = self
        self._irc.include(_twitch_plugin)

        loop = get_loop()
        asyncio.run_coroutine_threadsafe(self._run_bot(), loop)

    async def _run_bot(self):
        """Run the irc3 bot coroutine."""
        try:
            await self._irc.connection()
            self._irc.send("CAP REQ :twitch.tv/tags twitch.tv/commands")
            self._irc.send(f"PASS oauth:{self._token}")
            self._irc.send(f"NICK {self._username}")
            self._irc.send(f"JOIN #{self._channel}")
            self.connected.emit()
            self.system_message.emit(f"Connected to #{self._channel}")
        except Exception as exc:
            error(f"[IRC] Connection error: {exc}")
            self.system_message.emit(f"Chat connection error: {exc}")
            self.disconnected.emit()

    def send_message(self, message: str) -> bool:
        """Send a PRIVMSG to the current channel."""
        if not self._running or not self._irc:
            return False
        try:
            self._irc.send(f"PRIVMSG #{self._channel} :{message}")
            return True
        except Exception as exc:
            error(f"[IRC] Send error: {exc}")
            return False

    def disconnect(self):
        """Disconnect from IRC."""
        with self._lock:
            self._running = False
            if self._irc:
                try:
                    run_sync(self._irc.quit(), timeout=5)
                except Exception:
                    pass
                self._irc = None
            self.disconnected.emit()
            self.system_message.emit("Disconnected from chat.")


# ---------------------------------------------------------------------------
# irc3 plugin -- bridges irc3 events to IRCClient signals
# ---------------------------------------------------------------------------

def _twitch_plugin(bot):
    """irc3 plugin factory that bridges events to IRCClient signals."""

    client = getattr(bot, "_watcher_client", None)

    @irc3.event(irc3.rfc.PRIVMSG)
    def on_privmsg(target, event):
        if client is None:
            return
        line = str(event)
        parsed = parse_irc_line(line)
        if parsed:
            client.message_received.emit(parsed)

    @irc3.event(irc3.rfc.JOIN)
    def on_join(target, event):
        debug(f"[IRC] JOIN: {event}")

    @irc3.event(irc3.rfc.PART)
    def on_part(target, event):
        debug(f"[IRC] PART: {event}")

    @irc3.event(irc3.rfc.RPL_WELCOME)
    def on_welcome(target, event):
        debug("[IRC] Welcome received")

    return {
        "on_privmsg": on_privmsg,
        "on_join": on_join,
        "on_part": on_part,
        "on_welcome": on_welcome,
    }
