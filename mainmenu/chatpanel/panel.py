"""Chat Panel — integrates Twitch chat into the main interface.

Redesigned for v0.8.1:
- Connection managed by ChatPanel header (channel name + status dot)
- ChatWidget bottom controls hidden (channel input, buttons)
- Auto-translit always enabled — no manual buttons needed
- Single input field: type message, press Enter to send
- Maximum chat display area
"""

from logger import debug
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QLabel
from chat import ChatWidget
from ..theme import Theme


class ChatPanel(QGroupBox):

    def __init__(self, access_token):
        debug("ChatPanel.__init__ called")
        super().__init__("TWITCH CHAT")
        self.setStyleSheet(Theme.group_box_style(Theme.CYAN))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # --- Channel info header ---
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        self.channel_avatar = QLabel()
        self.channel_avatar.setFixedSize(28, 28)
        self.channel_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.channel_avatar.setStyleSheet(
            f"background-color: {Theme.AVATAR_BG}; "
            f"border: 1px solid {Theme.SECTION_BORDER}; "
            f"border-radius: 14px; color: {Theme.DIM}; font-size: 10px;"
        )
        self.channel_avatar.setText("?")
        header_row.addWidget(self.channel_avatar)

        self.channel_info_label = QLabel("Not connected")
        self.channel_info_label.setFont(QFont(Theme.FAMILY, 12, QFont.Weight.Bold))
        self.channel_info_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        header_row.addWidget(self.channel_info_label, 1)

        self.connection_dot = QLabel("OFFLINE")
        self.connection_dot.setStyleSheet(Theme.connection_dot_style(Theme.RED_DARK))
        header_row.addWidget(self.connection_dot)

        layout.addLayout(header_row)

        # --- Chat widget ---
        self.chat_widget = ChatWidget(username="", access_token=access_token)
        self.chat_widget.setStyleSheet(
            f"QTextEdit, QListWidget, QPlainTextEdit {{ "
            f"font-size: 16px; background-color: {Theme.DARK_PANEL}; "
            f"color: {Theme.TEXT_PRIMARY}; border: 1px solid {Theme.SECTION_BORDER}; "
            f"border-radius: 2px; }} "
            f"QLineEdit {{ font-size: 16px; padding: 6px; "
            f"background-color: {Theme.DARK_PANEL}; color: {Theme.TEXT_PRIMARY}; "
            f"border: 1px solid {Theme.SECTION_BORDER}; border-radius: 4px; }} "
            f"QPushButton {{ font-size: 12px; padding: 6px 12px; }}"
        )

        layout.addWidget(self.chat_widget)

        # --- Hide redundant ChatWidget bottom controls ---
        # The ChatPanel header handles connection; ChatWidget's own
        # channel_input + CONNECT/DISCONNECT buttons waste space.
        # The SEND/TRANSLIT/AUTO buttons are replaced by:
        #   - Enter to send (already wired in ChatWidget)
        #   - Auto-translit always enabled
        self._hide_redundant_controls()

        # --- Enable auto-translit by default ---
        if hasattr(self.chat_widget, 'auto_translit_button'):
            if not self.chat_widget.auto_translit_button.isChecked():
                self.chat_widget.auto_translit_button.click()

    def _hide_redundant_controls(self):
        """Hide ChatWidget's redundant bottom controls to maximize chat area."""
        cw = self.chat_widget

        # Hide SEND button
        if hasattr(cw, 'send_button'):
            cw.send_button.hide()

        # Hide TRANSLIT button (translit is now always auto)
        if hasattr(cw, 'translit_button'):
            cw.translit_button.hide()

        # Hide AUTO button (always enabled, no toggle needed)
        if hasattr(cw, 'auto_translit_button'):
            cw.auto_translit_button.hide()

        # Hide channel input + CONNECT/DISCONNECT buttons
        # These are in the channel_controls layout
        if hasattr(cw, 'channel_input'):
            cw.channel_input.hide()
        if hasattr(cw, 'connect_button'):
            cw.connect_button.hide()
        if hasattr(cw, 'disconnect_button'):
            cw.disconnect_button.hide()

        # Hide the channel_controls layout widgets' parents if possible
        # The channel_controls QHBoxLayout contains the hidden widgets
        # so the layout itself collapses to zero height
        debug("[CHAT] Hidden redundant ChatWidget controls")

    def set_username(self, username):
        self.chat_widget.username = username

    def connect_chat(self, channel):
        debug(f"ChatPanel.connect_chat called with channel: {channel}")
        if not channel:
            return
        self.channel_info_label.setText(f"#{channel}")
        self.connection_dot.setText("CONNECTING...")
        self.connection_dot.setStyleSheet(Theme.connection_dot_style(Theme.ORANGE))

        # Set the channel input and trigger connect via ChatWidget
        self.chat_widget.channel_input.setText(channel)
        self.chat_widget.connect_to_channel()

        try:
            self.chat_widget.client.connected.connect(self._on_connected)
        except Exception:
            pass

    def _on_connected(self):
        self.connection_dot.setText("LIVE")
        self.connection_dot.setStyleSheet(Theme.connection_dot_style(Theme.GREEN))

    def show_platform_unavailable(self, platform):
        """Show a graceful 'chat unavailable' state for non-Twitch platforms."""
        debug(f"ChatPanel.show_platform_unavailable called for {platform}")
        self.channel_info_label.setText(f"{platform.upper()} chat unavailable")
        self.connection_dot.setText("N/A")
        self.connection_dot.setStyleSheet(Theme.connection_dot_style(Theme.DIM))
        try:
            self.chat_widget.disconnect()
        except Exception:
            pass

    def disconnect_chat(self):
        debug("ChatPanel.disconnect_chat called")
        self.connection_dot.setText("OFFLINE")
        self.connection_dot.setStyleSheet(Theme.connection_dot_style(Theme.RED_DARK))
        self.chat_widget.disconnect()