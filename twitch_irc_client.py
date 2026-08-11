#!/usr/bin/env python3
"""Twitch IRC client — connects, reads, and parses Twitch IRC with tags."""

import socket
import ssl
import threading
import logging

from PySide6.QtCore import (
    QObject,
    Signal,
)


logger = logging.getLogger("twitch_irc")
TWITCH_IRC_HOST = "irc.chat.twitch.tv"
TWITCH_IRC_PORT = 6697
TWITCH_IRC_CAPABILITIES = "twitch.tv/tags twitch.tv/commands"


class TwitchChatClient(QObject):
    """A lightweight, threaded Twitch IRC client.

    Signals
    -------
    message_received(username, channel, message, tags)
    system_message(message)
    connected()
    disconnected()
    authentication_failed(reason)
    """

    message_received = Signal(str, str, str, object)
    system_message = Signal(str)
    connected = Signal()
    disconnected = Signal()
    authentication_failed = Signal(str)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(
        self,
        access_token="",
        channel="",
        username=None,
        host=TWITCH_IRC_HOST,
        port=TWITCH_IRC_PORT,
    ):
        super().__init__()
        self.access_token = access_token
        self.channel = channel
        self.username = username
        self.host = host
        self.port = port

        self._socket = None
        self._buffer = ""
        self.running = False
        self._read_thread = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API — mirrors what chat.py expects
    # ------------------------------------------------------------------
    def connect_chat(self):
        """Connect to Twitch IRC and join *self.channel*."""
        import ssl as ssl_mod
        import socket as sock_mod

        try:
            context = ssl_mod.create_default_context()
            raw = sock_mod.socket(
                sock_mod.AF_INET, sock_mod.SOCK_STREAM
            )
            raw.settimeout(30)
            raw.connect((self.host, self.port))
            self._socket = context.wrap_socket(
                raw, server_hostname=self.host
            )

            # Authenticate.
            if self.access_token:
                self._send_raw(
                    f"PASS oauth:{self.access_token}"
                )

            nick = self.username or "justinfan12345"
            self._send_raw(f"NICK {nick}")
            self._send_raw(
                f"CAP REQ :{TWITCH_IRC_CAPABILITIES}"
            )

            if self.channel:
                self._send_raw(f"JOIN #{self.channel}")

            self.running = True
            self.connected.emit()
            logger.info(
                "Connected to Twitch IRC as %s, joined #%s",
                nick,
                self.channel,
            )

            self._read_thread = threading.Thread(
                target=self._read_loop, daemon=True
            )
            self._read_thread.start()

        except Exception as exc:
            logger.exception("Connection error")
            self.authentication_failed.emit(str(exc))
            self.disconnected.emit()

    def disconnect_chat(self):
        """Disconnect from the IRC server."""
        self.running = False
        if self._socket:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        if self._read_thread:
            self._read_thread.join(timeout=5)
        self.disconnected.emit()
        logger.info("Disconnected from IRC")

    def send_message(self, message):
        """Send *message* to the current channel."""
        if not self.running or not self._socket:
            return False
        try:
            safe = message.replace("\n", " ").replace("\r", " ")
            self._send_raw(
                f"PRIVMSG #{self.channel} :{safe}"
            )
            return True
        except Exception as exc:
            logger.exception("Send error")
            self.system_message.emit(
                f"Send failed: {exc}"
            )
            return False

    def send_raw(self, data):
        """Public alias for _send_raw."""
        self._send_raw(data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _send_raw(self, data):
        """Send raw data (CRLF appended) to the IRC socket."""
        if self._socket:
            self._socket.sendall(
                (data + "\r\n").encode("utf-8")
            )

    def _read_loop(self):
        """Continuously read lines from the socket until stopped."""
        import socket as sock_mod

        while self.running and self._socket:
            try:
                chunk = self._socket.recv(4096)
                if not chunk:
                    self.running = False
                    self.disconnected.emit()
                    return
                self._buffer += chunk.decode(
                    "utf-8", errors="replace"
                )
                while "\n" in self._buffer:
                    line, self._buffer = self._buffer.split(
                        "\n", 1
                    )
                    line = line.strip()
                    if line:
                        self._handle_line(line)
            except (TimeoutError, sock_mod.timeout):
                # Socket timeout — just loop back and check self.running.
                continue
            except Exception as exc:
                logger.exception("Read error")
                self.running = False
                self.disconnected.emit()
                return

    def _handle_line(self, line):
        """Dispatch a single IRC line to the right handler."""
        try:
            if line.startswith("PING"):
                self._handle_ping(line)
            else:
                self._handle_privmsg(line)
        except Exception as exc:
            logger.exception("Error handling line: %s", exc)

    def _handle_ping(self, line):
        """Respond to server PING with PONG."""
        if "PONG" not in line:
            self._send_raw("PONG :tmi.twitch.tv")
            logger.debug("Sent PONG")

    def _handle_privmsg(self, line):
        """Parse an IRC line and emit signals if it's a PRIVMSG."""
        try:
            tags = {}

            # --- Parse tags (if present) ---
            if line.startswith("@"):
                tag_section, _, remainder = line.partition(" ")
                for tag_item in tag_section[1:].split(";"):
                    key, _, value = tag_item.partition("=")
                    if key:
                        tags[key] = self._unescape_tag(
                            value
                        )
                line = remainder

            # --- Parse prefix ---
            prefix = ""
            if line.startswith(":"):
                prefix, line = line[1:].split(" ", 1)

            # --- Parse command + params ---
            parts = line.split(" ", 1)
            if len(parts) < 2:
                return

            command = parts[0]
            params = parts[1] if len(parts) > 1 else ""

            if command == "PRIVMSG":
                self._emit_privmsg(
                    prefix, params, tags
                )
            elif command == "001":
                self.connected.emit()
            elif command == "NOTICE":
                self.system_message.emit(
                    self._extract_message(params)
                )
            elif command == "422" or command == "421":
                self.system_message.emit(
                    self._extract_message(params)
                )

        except Exception as exc:
            logger.exception("Error in _handle_privmsg: %s", exc)

    def _emit_privmsg(self, prefix, params, tags):
        """Emit a message_received signal from PRIVMSG params."""
        # params format: "#channel :message text"
        channel_part, sep, raw_message = params.partition(" ")
        if not sep:
            return

        message = raw_message
        if message.startswith(":"):
            message = message[1:]

        # Extract username from prefix.
        username = ""
        if prefix.startswith(":"):
            prefix = prefix[1:]
        userinfo = prefix.split("!")
        if len(userinfo) > 0:
            username = userinfo[0]

        channel = channel_part.lstrip("#")

        self.message_received.emit(
            username, channel, message, tags
        )

    def _extract_message(self, params):
        """Extract the human-readable message from params."""
        _, sep, msg = params.partition(":")
        if sep:
            return msg
        return params

    @staticmethod
    def _unescape_tag(value):
        """Unescape IRC tag per the spec."""
        if not value:
            return value
        return (
            value.replace("\\", "\\")
            .replace("\\s", " ")
            .replace("\\:", ":")
        )
