"""Chat Panel — integrates Twitch chat into the main interface."""

from logger import debug
from PySide6.QtWidgets import QGroupBox, QVBoxLayout
from chat import ChatWidget
from ..theme import Theme


class ChatPanel(QGroupBox):

    def __init__(self, access_token):
        debug("ChatPanel.__init__ called")
        super().__init__("TWITCH CHAT")
        self.setStyleSheet(Theme.group_box_style(Theme.CYAN))

        layout = QVBoxLayout(self)

        self.chat_widget = ChatWidget(username="", access_token=access_token)
        self.chat_widget.setStyleSheet(f"""
            QTextEdit, QListWidget, QPlainTextEdit {{
                font-size: 12px;
                background-color: {Theme.DARK_PANEL};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.SECTION_BORDER};
                border-radius: 2px;
            }}
        """)

        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        layout.addWidget(self.chat_widget)

    def set_username(self, username):
        self.chat_widget.username = username

    def connect_chat(self, channel):
        debug(f"ChatPanel.connect_chat called with channel: {channel}")
        if not channel:
            return
        self.chat_widget.channel_input.setText(channel)
        self.chat_widget.connect_to_channel()

    def disconnect_chat(self):
        debug("ChatPanel.disconnect_chat called")
        self.chat_widget.disconnect()