from PyQt6.QtCore import pyqtSlot, QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtGui import QPixmap

class CurrentWatchingPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.expected_url = ""
        self.image_cache = {}
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        self.avatar_label = QLabel()
        layout.addWidget(self.avatar_label)
        self.setLayout(layout)

    @pyqtSlot(dict)
    def on_stream_update(self, stream_data):
        """Handle updates to the current stream"""
        if not stream_data:
            return
        
        # Update avatar
        url = self._get_avatar_url(stream_data)
        normalized_url = url.split('?')[0]  # Remove query parameters
        if normalized_url != self.expected_url:
            self.image_cache.discard(normalized_url)
            self.expected_url = normalized_url
            self._load_image_async(url)

    def _get_avatar_url(self, stream_data):
        """Get avatar URL from stream data"""
        return stream_data.get("avatar_url", "")

    def _load_image_async(self, url):
        """Load image in background thread"""
        # Implementation details omitted for brevity
        pass