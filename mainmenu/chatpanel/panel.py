"""Chat Panel — integrates Twitch chat into the main interface."""

from logger import debug
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QLabel
from chat import ChatWidget
from ..theme import Theme
from .transliteration import transliterate_to_russian
from .token_helpers import normalize_token, get_token_identity


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
        self.channel_avatar.setStyleSheet(f"""
            background-color: {Theme.AVATAR_BG};
            border: 1px solid {Theme.SECTION_BORDER};
            border-radius: 14px;
            color: {Theme.DIM};
            font-size: 10px;
        """)
        self.channel_avatar.setText("?")
        header_row.addWidget(self.channel_avatar)

        self.channel_info_label = QLabel("Not connected")
        self.channel_info_label.setFont(QFont(Theme.FAMILY, 12, QFont.Weight.Bold))
        self.channel_info_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        header_row.addWidget(self.channel_info_label, 1)

        self.connection_dot = QLabel("OFFLINE")
        self.connection_dot.setStyleSheet(f"""
            color: {Theme.RED_DARK};
            font-size: 9px;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 3px;
            background-color: {Theme.DARK_PANEL};
        """)
        header_row.addWidget(self.connection_dot)

        layout.addLayout(header_row)

        # --- Chat widget (16px font per user preference) ---
        self.chat_widget = ChatWidget(username="", access_token=access_token)
        self.chat_widget.setStyleSheet(f"""
            QTextEdit, QListWidget, QPlainTextEdit {{
                font-size: 16px;
                background-color: {Theme.DARK_PANEL};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.SECTION_BORDER};
                border-radius: 2px;
            }}
            QLineEdit {{
                font-size: 16px;
                padding: 6px;
            }}
            QPushButton {{
                font-size: 12px;
                padding: 6px 12px;
            }}
        """)

        layout.addWidget(self.chat_widget)

    def set_username(self, username):
        self.chat_widget.username = username

    def connect_chat(self, channel):
        debug(f"ChatPanel.connect_chat called with channel: {channel}")
        if not channel:
            return
        self.channel_info_label.setText(f"#{channel}")
        self.connection_dot.setText("CONNECTING...")
        self.connection_dot.setStyleSheet(f"""
            color: {Theme.ORANGE};
            font-size: 9px;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 3px;
            background-color: {Theme.DARK_PANEL};
        """)
        self.chat_widget.channel_input.setText(channel)
        self.chat_widget.connect_to_channel()
        # Update connection dot when connected
        try:
            self.chat_widget.client.connected.connect(self._on_connected)
        except Exception:
            pass

    def _on_connected(self):
        self.connection_dot.setText("LIVE")
        self.connection_dot.setStyleSheet(f"""
            color: {Theme.GREEN};
            font-size: 9px;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 3px;
            background-color: {Theme.DARK_PANEL};
        """)

    def show_platform_unavailable(self, platform):
        """Show a graceful 'chat unavailable' state for non-Twitch platforms."""
        debug(f"ChatPanel.show_platform_unavailable called for {platform}")
        self.channel_info_label.setText(f"{platform.upper()} chat unavailable")
        self.connection_dot.setText("N/A")
        self.connection_dot.setStyleSheet(f"""
            color: {Theme.DIM};
            font-size: 9px;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 3px;
            background-color: {Theme.DARK_PANEL};
        """)
        try:
            self.chat_widget.disconnect()
        except Exception:
            pass

    def disconnect_chat(self):
        debug("ChatPanel.disconnect_chat called")
        self.connection_dot.setText("OFFLINE")
        self.connection_dot.setStyleSheet(f"""
            color: {Theme.RED_DARK};
            font-size: 9px;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 3px;
            background-color: {Theme.DARK_PANEL};
        """)
        self.chat_widget.disconnect()