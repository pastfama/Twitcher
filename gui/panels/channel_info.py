from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QPixmap

class ChannelInfoPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.banner_label = QLabel()
        self.load_banner()

    def load_banner(self):
        # Fetch banner URL from Twitch API
        banner_url = "https://example.com/banner.jpg"
        pixmap = QPixmap()
        pixmap.loadFromData(requests.get(banner_url).content)
        self.banner_label.setPixmap(pixmap.scaledToWidth(400))