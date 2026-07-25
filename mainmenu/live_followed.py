from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton


class LiveFollowedPanel(QGroupBox):

    channel_selected = Signal(object)
    refresh_requested = Signal()
    watch_requested = Signal()
    stop_requested = Signal()

    def __init__(self):

        super().__init__("LIVE FOLLOWED CHANNELS")

        layout = QVBoxLayout(self)

        self.channel_list = QListWidget()
        self.channel_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.channel_list)

        self.refresh_button = QPushButton("⟳  REFRESH LIVE CHANNELS")
        self.refresh_button.clicked.connect(self.refresh_requested)
        layout.addWidget(self.refresh_button)

        self.watch_button = QPushButton("▶  WATCH SELECTED")
        self.watch_button.clicked.connect(self.watch_requested)
        layout.addWidget(self.watch_button)

        self.stop_button = QPushButton("■  STOP VIDEO")
        self.stop_button.clicked.connect(self.stop_requested)
        layout.addWidget(self.stop_button)

    def _on_item_clicked(self, item):

        stream = item.data(Qt.ItemDataRole.UserRole)

        if stream:
            self.channel_selected.emit(stream)

    def set_streams(self, streams):

        self.channel_list.clear()

        for stream in streams:
            channel_name = stream.get("user_name", "Unknown")
            viewers = stream.get("viewer_count", 0)
            category = stream.get("game_name") or "No category"

            item = QListWidgetItem(
                f"  {channel_name}\n"
                f"  👁 {viewers:,} viewers\n"
                f"  🎮 {category}"
            )
            item.setData(Qt.ItemDataRole.UserRole, stream)
            self.channel_list.addItem(item)

    def get_selected_stream(self):

        item = self.channel_list.currentItem()

        if not item:
            return None

        return item.data(Qt.ItemDataRole.UserRole)
