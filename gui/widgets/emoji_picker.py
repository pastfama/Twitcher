from PyQt6.QtWidgets import QDialog, QTabWidget, QWidget, QVBoxLayout, QLineEdit, QListWidget
from PyQt6.QtGui import QIcon

class EmojiPicker(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Emoji Picker")
        self.tabs = QTabWidget()
        self.setup_tabs()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search emojis...")
        self.search_bar.textChanged.connect(self.filter_emotes)
        layout = QVBoxLayout()
        layout.addWidget(self.search_bar)
        layout.addWidget(self.tabs)
        self.setLayout(layout)

    def setup_tabs(self):
        recent_tab = QWidget()
        recent_layout = QVBoxLayout()
        recent_list = QListWidget()
        recent_list.addItem("Recent Emote 1")
        recent_layout.addWidget(recent_list)
        recent_tab.setLayout(recent_layout)
        self.tabs.addTab(recent_tab, "Recent")

        twitch_tab = QWidget()
        twitch_layout = QVBoxLayout()
        twitch_list = QListWidget()
        twitch_list.addItem("Twitch Emote 1")
        twitch_layout.addWidget(twitch_list)
        twitch_tab.setLayout(twitch_layout)
        self.tabs.addTab(twitch_tab, "Twitch")

    def filter_emotes(self, text):
        # Implement search filtering here
        pass