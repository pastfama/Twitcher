from PyQt6.QtWidgets import QWidget, QLabel, QLineEdit, QMenu, QAction
from PyQt6.QtCore import pyqtSlot

class ChatPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.subs_only_mode = False
        self.subs_indicator = QLabel(self)
        self.subs_indicator.setStyleSheet("color: red; font-weight: bold;")
        self.subs_indicator.hide()
        self.reply_box = QLineEdit()
        self.reply_box.setPlaceholderText("Type your reply...")
        self.reply_box.setVisible(False)
        self.setup_ui()

    @pyqtSlot(dict)
    def on_roomstate(self, tags):
        if 'subs-only' in tags:
            self.subs_only_mode = (tags['subs-only'] == '1')
            self.update_subs_indicator()

    def update_subs_indicator(self):
        if self.subs_only_mode:
            self.subs_indicator.setText("SUBS ONLY")
            self.subs_indicator.show()
        else:
            self.subs_indicator.hide()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(self.subs_indicator)
        layout.addWidget(self.reply_box)
        self.setLayout(layout)

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if item:
            menu = QMenu()
            reply_action = QAction("Reply")
            reply_action.triggered.connect(lambda: self.show_reply(item))
            menu.addAction(reply_action)
            menu.exec_(event.globalPos())

    def show_reply(self, item):
        username = item.text().split(":")[0].strip()
        self.reply_box.setText(f"@{username}: ")
        self.reply_box.setVisible(True)
        self.reply_box.setFocus()