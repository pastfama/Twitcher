import os

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow, QTextEdit


class LogWindow(QMainWindow):

    def __init__(self, log_file):

        super().__init__()

        self.log_file = log_file

        self.setWindowTitle("Watcher Logs")
        self.resize(900, 600)

        self.text = QTextEdit()
        self.text.setReadOnly(True)

        self.setCentralWidget(self.text)

        self.load_logs()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_logs)
        self.timer.start(1000)

    def load_logs(self):

        try:

            if not os.path.exists(self.log_file):
                self.text.setPlainText("No logs yet.")
                return

            with open(self.log_file, "r", encoding="utf-8") as file:
                self.text.setPlainText(file.read())

            scrollbar = self.text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

        except Exception:
            pass
