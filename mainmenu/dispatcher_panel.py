from PySide6.QtGui import QFont
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QLabel, QTextEdit


class DispatcherPanel(QGroupBox):

    def __init__(self):

        super().__init__("AUTOMATION / DISPATCHER")

        layout = QVBoxLayout(self)

        self.dispatcher_status = QLabel("Status: Starting...")
        self.dispatcher_status.setWordWrap(True)
        self.dispatcher_status.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        layout.addWidget(self.dispatcher_status)

        self.next_status = QLabel("Next: —")
        self.next_status.setWordWrap(True)
        self.next_status.setStyleSheet("color: #78d6c5;")
        layout.addWidget(self.next_status)

        self.event_log = QTextEdit()
        self.event_log.setReadOnly(True)
        layout.addWidget(self.event_log)

    def set_status(self, message):

        self.dispatcher_status.setText(f"Status: {message}")

    def set_next_status(self, message):

        self.next_status.setText(message)

    def append_log(self, message):

        self.event_log.append(message)
