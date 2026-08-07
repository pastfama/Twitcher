"""Account Manager UI Panel — login buttons for all platforms."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from logger import debug
from .manager import AccountManager


class AccountPanel(QGroupBox):
    """Panel showing authentication status and login buttons for all platforms."""

    login_completed = Signal(str, bool)  # platform, success

    def __init__(self, parent=None):
        super().__init__("ACCOUNTS", parent)
        self.setStyleSheet("""
            QGroupBox {
                background-color: #12121c;
                border: 1px solid #29293d;
                border-radius: 4px;
                color: #b7a7ff;
                font-size: 10px;
                font-weight: bold;
            }
        """)

        self.manager = AccountManager()
        self._build_ui()
        self._update_status()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Twitch
        self.twitch_row = self._build_platform_row(
            "Twitch",
            "#9146ff",
            self._on_twitch_login
        )
        layout.addWidget(self.twitch_row)

        # Kick
        self.kick_row = self._build_platform_row(
            "Kick",
            "#53fc18",
            self._on_kick_login
        )
        layout.addWidget(self.kick_row)

        # YouTube
        self.youtube_row = self._build_platform_row(
            "YouTube",
            "#ff0000",
            self._on_youtube_login
        )
        layout.addWidget(self.youtube_row)

    def _build_platform_row(self, name, color, on_click):
        row = QWidget()
        row.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        # Platform icon/status
        status_label = QLabel("●")
        status_label.setFixedWidth(16)
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_label.setStyleSheet(f"color: #666; font-size: 14px;")
        layout.addWidget(status_label)

        # Platform name
        name_label = QLabel(name)
        name_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        name_label.setStyleSheet(f"color: {color};")
        layout.addWidget(name_label)

        # Status text
        status_text = QLabel("Not configured")
        status_text.setStyleSheet("color: #666; font-size: 9px;")
        layout.addWidget(status_text, 1)

        # Login button
        login_btn = QPushButton("Login")
        login_btn.setFixedWidth(60)
        login_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #181827;
                border: 1px solid {color};
                border-radius: 4px;
                color: {color};
                padding: 4px 8px;
                font-size: 9px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {color}33;
            }}
        """)
        login_btn.clicked.connect(on_click)
        layout.addWidget(login_btn)

        row.status_label = status_label
        row.status_text = status_text
        row.login_btn = login_btn
        row.platform_name = name.lower()

        return row

    def _update_status(self):
        """Update status indicators for all platforms."""
        status = self.manager.get_all_status()

        for platform, row in [
            ("twitch", self.twitch_row),
            ("kick", self.kick_row),
            ("youtube", self.youtube_row),
        ]:
            info = status.get(platform, {})
            configured = info.get("configured", False)

            if configured:
                row.status_label.setStyleSheet("color: #72d6a0; font-size: 14px;")
                row.status_text.setText("Configured")
                row.status_text.setStyleSheet("color: #72d6a0; font-size: 9px;")
                row.login_btn.setText("Login")
            else:
                row.status_label.setStyleSheet("color: #666; font-size: 14px;")
                row.status_text.setText("Not configured")
                row.status_text.setStyleSheet("color: #666; font-size: 9px;")
                row.login_btn.setText("Setup")

    def _on_twitch_login(self):
        debug("[ACCOUNT] Twitch login requested")
        success = self.manager.login_twitch()
        self._update_status()
        self.login_completed.emit("twitch", success)

    def _on_kick_login(self):
        debug("[ACCOUNT] Kick login requested")
        success = self.manager.login_kick()
        self._update_status()
        self.login_completed.emit("kick", success)

    def _on_youtube_login(self):
        debug("[ACCOUNT] YouTube login requested")
        success = self.manager.login_youtube()
        self._update_status()
        self.login_completed.emit("youtube", success)

    def get_manager(self) -> AccountManager:
        return self.manager