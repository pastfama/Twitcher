from PySide6.QtWidgets import QGroupBox, QVBoxLayout
from chat import ChatWidget


class ChatPanel(QGroupBox):

    def __init__(self, access_token):

        super().__init__("TWITCH CHAT")

        layout = QVBoxLayout(self)

        self.chat_widget = ChatWidget(
            username="",
            access_token=access_token
        )
        self.chat_widget.setStyleSheet(
            """
            QTextEdit,
            QListWidget,
            QPlainTextEdit {
                font-size: 18px;
            }
            """
        )

        layout.addWidget(self.chat_widget)

    def connect_chat(self, channel):

        if not channel:
            return

        self.chat_widget.channel_input.setText(channel)
        self.chat_widget.connect_to_channel()
