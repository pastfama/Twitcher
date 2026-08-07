"""Chat Panel — integrates Twitch chat into the main interface."""

from logger import debug
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
)
from chat import ChatWidget
from ..theme import Theme


class ChatPanel(QGroupBox):
    """Wraps ChatWidget in a styled group box with channel info and
    connection status in the header.

    State machine for the connection dot:
        IDLE  →  CONNECTING  →  LIVE
                        ↘            ↘
                      FAILED       OFFLINE
    """

    # ---- Connection status constants --------------------------------
    _STATUS_IDLE       = ("IDLE",       Theme.DIM)
    _STATUS_CONNECTING = ("CONNECTING…", Theme.ORANGE)
    _STATUS_LIVE       = ("LIVE",       Theme.GREEN)
    _STATUS_FAILED     = ("FAILED",     Theme.RED_DARK)
    _STATUS_OFFLINE    = ("OFFLINE",    Theme.RED_DARK)
    _STATUS_NA         = ("N/A",        Theme.DIM)

    def __init__(self, access_token):
        debug("ChatPanel.__init__ called")
        super().__init__("TWITCH CHAT")
        self.setStyleSheet(Theme.group_box_style(Theme.CYAN))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        # --- Channel info header ---
        header_row = QHBoxLayout()
        header_row.setSpacing(6)
        header_row.setContentsMargins(4, 0, 4, 0)

        self.channel_avatar = QLabel()
        self.channel_avatar.setFixedSize(24, 24)
        self.channel_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._reset_avatar()
        header_row.addWidget(self.channel_avatar)

        self.channel_info_label = QLabel("Not connected")
        self.channel_info_label.setFont(QFont(Theme.FAMILY, 11, QFont.Weight.Bold))
        self.channel_info_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        header_row.addWidget(self.channel_info_label, 1)

        self.connection_dot = QLabel()
        self._set_status(*self._STATUS_IDLE)
        header_row.addWidget(self.connection_dot)

        layout.addLayout(header_row)

        # --- Compact channel info strip (game + viewers + rewards) ---
        self.info_strip = QLabel("")
        self.info_strip.setStyleSheet(
            f"color: {Theme.MUTED}; font-size: 9px; padding: 0 4px;"
        )
        self.info_strip.setFixedHeight(14)
        layout.addWidget(self.info_strip)

        # --- Chat widget (16px font per user preference) ---
        self.chat_widget = ChatWidget(username="", access_token=access_token)
        self.chat_widget.setStyleSheet(f"""
            QTextEdit, QListWidget, QPlainTextEdit {{
                font-size: 16px;
                background-color: {Theme.DARK_PANEL};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                border-radius: 2px;
            }}
            QLineEdit {{
                font-size: 16px;
                padding: 4px;
            }}
            QPushButton {{
                font-size: 11px;
                padding: 4px 8px;
            }}
        """)

        # Hide the redundant internal widgets — the panel header replaces them.
        self._hide_redundant_widgets()

        layout.addWidget(self.chat_widget, 1)  # stretch=1 to maximize messages

        # Track the last channel we tried to connect to so we can
        # wire signals exactly once per connect attempt.
        self._connected_channel = None

    # ---- Public API ------------------------------------------------

    def set_username(self, username):
        """Set the local user's username on the underlying ChatWidget."""
        self.chat_widget.username = username

    def connect_chat(self, channel):
        """Connect the embedded ChatWidget to *channel*."""
        debug(f"ChatPanel.connect_chat called with channel: {channel}")
        if not channel:
            return

        # Disconnect any previous connection first.
        self._disconnect_internal()

        self.channel_info_label.setText(f"#{channel}")
        self._set_status(*self._STATUS_CONNECTING)

        self.chat_widget.channel_input.setText(channel)
        self.chat_widget.connect_to_channel()

        # Wire signals exactly once per connection attempt.
        client = getattr(self.chat_widget, "client", None)
        if client is not None:
            try:
                client.connected.connect(self._on_connected)
                client.disconnected.connect(self._on_disconnected)
                client.authentication_failed.connect(self._on_auth_failed)
            except Exception as exc:
                debug(f"[CHAT PANEL] Signal connect error: {exc}")

        self._connected_channel = channel

    def show_platform_unavailable(self, platform):
        """Show a graceful 'chat unavailable' state for non-Twitch platforms."""
        debug(f"ChatPanel.show_platform_unavailable called for {platform}")
        self._disconnect_internal()
        self.channel_info_label.setText(f"{platform.upper()} chat unavailable")
        self._set_status(*self._STATUS_NA)

    def disconnect_chat(self):
        """Public disconnect — called on shutdown / channel switch."""
        debug("ChatPanel.disconnect_chat called")
        self._disconnect_internal()
        self.channel_info_label.setText("Not connected")
        self._set_status(*self._STATUS_IDLE)
        self.info_strip.setText("")

    def set_avatar(self, avatar_url):
        """Load and display a channel avatar from a URL string."""
        if not avatar_url:
            self._reset_avatar()
            return
        try:
            import urllib.request
            data = urllib.request.urlopen(avatar_url, timeout=5).read()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    22, 22,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.channel_avatar.setPixmap(scaled)
                self.channel_avatar.setText("")
                self.channel_avatar.setStyleSheet(
                    f"border: 1px solid {Theme.SECTION_BORDER};"
                    f"border-radius: 11px;"
                    f"background-color: transparent;"
                )
            else:
                self._reset_avatar()
        except Exception as exc:
            debug(f"[CHAT PANEL] Failed to load avatar: {exc}")
            self._reset_avatar()

    def set_channel_info(self, game="", viewers=0, reward_count=0):
        """Update the compact info strip with channel data."""
        parts = []
        if game:
            parts.append(f"🎮 {game}")
        if viewers:
            parts.append(f"📺 {viewers:,}")
        if reward_count:
            parts.append(f"🎁 {reward_count} rewards")
        self.info_strip.setText("  │  ".join(parts))

    # ---- Internal helpers ------------------------------------------

    def _set_status(self, text, color):
        """Update the connection-dot label with *text* and *color*."""
        self.connection_dot.setText(text)
        self.connection_dot.setStyleSheet(f"""
            color: {color};
            font-size: 9px;
            font-weight: bold;
            padding: 1px 4px;
            border-radius: 3px;
            background-color: {Theme.DARK_PANEL};
        """)

    def _reset_avatar(self):
        """Reset the avatar label to the default '?' placeholder."""
        self.channel_avatar.setPixmap(QPixmap())
        self.channel_avatar.setText("?")
        self.channel_avatar.setStyleSheet(f"""
            background-color: {Theme.AVATAR_BG};
            border: 1px solid {Theme.SECTION_BORDER};
            border-radius: 11px;
            color: {Theme.DIM};
            font-size: 9px;
            min-width: 22px;
            min-height: 22px;
        """)

    def _hide_redundant_widgets(self):
        """Hide ChatWidget elements that the panel header replaces."""
        w = self.chat_widget
        # Status label — panel header's connection_dot replaces this.
        if hasattr(w, "status"):
            w.status.setVisible(False)
        # Channel input row — connection is managed automatically.
        if hasattr(w, "channel_input"):
            w.channel_input.setVisible(False)
        if hasattr(w, "connect_button"):
            w.connect_button.setVisible(False)
        if hasattr(w, "disconnect_button"):
            w.disconnect_button.setVisible(False)

    def _disconnect_internal(self):
        """Disconnect the ChatWidget and unhook signals to avoid leaks."""
        client = getattr(self.chat_widget, "client", None)
        if client is not None:
            for signal_slot in [
                (client.connected, self._on_connected),
                (client.disconnected, self._on_disconnected),
                (client.authentication_failed, self._on_auth_failed),
            ]:
                try:
                    signal_slot[0].disconnect(signal_slot[1])
                except (RuntimeError, TypeError):
                    pass
        try:
            self.chat_widget.disconnect()
        except Exception as exc:
            debug(f"[CHAT PANEL] Disconnect error: {exc}")
        self._connected_channel = None

    # ---- Signal handlers -------------------------------------------

    def _on_connected(self):
        debug("[CHAT PANEL] IRC connected")
        self._set_status(*self._STATUS_LIVE)

    def _on_disconnected(self):
        debug("[CHAT PANEL] IRC disconnected")
        current_text = self.connection_dot.text()
        if current_text in ("LIVE", "CONNECTING…"):
            self._set_status(*self._STATUS_OFFLINE)

    def _on_auth_failed(self, reason=""):
        debug(f"[CHAT PANEL] IRC auth failed: {reason}")
        self._set_status(*self._STATUS_FAILED)