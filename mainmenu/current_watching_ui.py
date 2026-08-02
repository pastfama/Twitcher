import requests

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout


class CurrentWatchingUIBuilder:
    def __init__(self, panel):
        self.panel = panel
        self.build()

    def build(self):
        self.panel.setObjectName("CurrentCard")
        self.panel.viewer_analysis = None
        self.panel.setMinimumHeight(220)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        title = QLabel("▶  CURRENTLY WATCHING")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #9daaff;")
        layout.addWidget(title)

        stream_layout = QHBoxLayout()
        stream_layout.setSpacing(14)

        self.panel.avatar_label = QLabel()
        self.panel.avatar_label.setFixedSize(80, 80)
        self.panel.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.panel.avatar_label.setStyleSheet(
            "background-color: #202333; border-radius: 40px; color: #777;"
        )
        self.panel.avatar_label.setText("?")
        stream_layout.addWidget(self.panel.avatar_label)

        details = QVBoxLayout()
        details.setSpacing(4)

        header = QHBoxLayout()
        self.panel.channel_label = QLabel("—")
        self.panel.channel_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.panel.live_label = QLabel("● LIVE")
        self.panel.live_label.setStyleSheet("color: #ff5555; font-weight: bold;")
        header.addWidget(self.panel.channel_label)
        header.addStretch()
        header.addWidget(self.panel.live_label)
        details.addLayout(header)

        self.panel.title_label = QLabel("—")
        self.panel.title_label.setWordWrap(True)
        self.panel.title_label.setStyleSheet("color: #a8adbd;")
        details.addWidget(self.panel.title_label)
        stream_layout.addLayout(details, 1)
        layout.addLayout(stream_layout)

        stats = QHBoxLayout()
        self.panel.viewers_label = QLabel("👁 — viewers")
        self.panel.momentum_label = QLabel("📊 Waiting...")
        self.panel.category_label = QLabel("🎮 —")
        self.panel.uptime_label = QLabel("⏱ —")
        stats.addWidget(self.panel.viewers_label)
        stats.addWidget(self.panel.momentum_label)
        stats.addWidget(self.panel.category_label)
        stats.addWidget(self.panel.uptime_label)
        stats.addStretch()
        layout.addLayout(stats)

        # SullyGoose Analytics Row
        sully_layout = QHBoxLayout()
        sully_layout.setSpacing(14)
        
        self.panel.sully_title = QLabel("🦆 SULLYGOOSE")
        self.panel.sully_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.panel.sully_title.setStyleSheet("color: #72d6a0;")
        
        self.panel.sully_avg_label = QLabel("Avg: —")
        self.panel.sully_growth_label = QLabel("Growth: —")
        self.panel.sully_rank_label = QLabel("Rank: —")
        
        sully_layout.addWidget(self.panel.sully_title)
        sully_layout.addWidget(self.panel.sully_avg_label)
        sully_layout.addWidget(self.panel.sully_growth_label)
        sully_layout.addWidget(self.panel.sully_rank_label)
        sully_layout.addStretch()
        
        layout.addLayout(sully_layout)

        self.panel.set_avatar_image = self.set_avatar_image

    def set_avatar_image(self, avatar_url):
        label = self.panel.avatar_label
        if not avatar_url:
            label.setText("?")
            return

        try:
            response = requests.get(avatar_url, timeout=10)
            response.raise_for_status()
            pixmap = QPixmap()
            pixmap.loadFromData(response.content)
            if not pixmap.isNull():
                label.setPixmap(pixmap.scaled(80, 80, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
                label.setText("")
                return
        except Exception:
            pass

        label.setText("?")
