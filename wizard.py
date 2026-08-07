"""First-run wizard — shows an app poster and confirms the install folder.

Displayed once on first launch.  Uses QSettings to remember that the
wizard has already been shown, so it never blocks subsequent startups.
"""

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QApplication,
)

from logger import debug

APP_ORGANIZATION = "Watcher"
APP_NAME = "WatcherControlCenter"

# Platform brand colors used in the poster.
PLATFORM_COLORS = {
    "Twitch": "#9146FF",
    "Kick": "#53FC18",
    "YouTube": "#FF0000",
}


def _install_dir():
    """Return the directory the app is running from."""
    if getattr(sys, "frozen", False):
        # PyInstaller onefile: _MEIPASS is the temp extraction dir;
        # the real install location is the exe's directory.
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _poster_style():
    """Dark poster stylesheet for the wizard."""
    return """
    QDialog {
        background-color: #0a0a12;
    }
    QLabel#posterTitle {
        color: #b7a7ff;
        font-size: 28px;
        font-weight: bold;
    }
    QLabel#posterTagline {
        color: #75e6a5;
        font-size: 14px;
        font-weight: bold;
    }
    QLabel#posterBody {
        color: #d0d0e0;
        font-size: 12px;
    }
    QLabel#posterSection {
        color: #9b8cff;
        font-size: 11px;
        font-weight: bold;
    }
    QLabel#installLabel {
        color: #aaaaaa;
        font-size: 11px;
    }
    QLabel#installPath {
        color: #f2f2f2;
        font-size: 12px;
        font-weight: bold;
    }
    QFrame#posterCard {
        background-color: #14141f;
        border: 1px solid #2a2a40;
        border-radius: 10px;
    }
    QFrame#installCard {
        background-color: #10101a;
        border: 1px solid #2a2a40;
        border-radius: 8px;
    }
    QPushButton#startButton {
        background-color: #30275c;
        color: #ffffff;
        border: 1px solid #7166b3;
        border-radius: 6px;
        padding: 10px 24px;
        font-size: 13px;
        font-weight: bold;
    }
    QPushButton#startButton:hover {
        background-color: #45377e;
    }
    """


class FirstRunWizard(QDialog):
    """First-launch dialog: app poster + install folder confirmation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Watcher")
        self.setModal(True)
        self.setMinimumSize(560, 520)
        self.setStyleSheet(_poster_style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # ------------------------------------------------------------
        # POSTER
        # ------------------------------------------------------------
        poster = QFrame()
        poster.setObjectName("posterCard")
        poster_layout = QVBoxLayout(poster)
        poster_layout.setContentsMargins(20, 20, 20, 20)
        poster_layout.setSpacing(8)

        title = QLabel("🎮 WATCHER")
        title.setObjectName("posterTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        poster_layout.addWidget(title)

        tagline = QLabel("One control center for Twitch · Kick · YouTube")
        tagline.setObjectName("posterTagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        poster_layout.addWidget(tagline)

        # Platform badges row
        badges_row = QHBoxLayout()
        badges_row.setSpacing(8)
        badges_row.addStretch()
        for name, color in PLATFORM_COLORS.items():
            badge = QLabel(name)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"color: {color}; font-size: 10px; font-weight: bold; "
                f"border: 1px solid {color}; border-radius: 4px; padding: 3px 10px;"
            )
            badges_row.addWidget(badge)
        badges_row.addStretch()
        poster_layout.addLayout(badges_row)

        poster_layout.addSpacing(6)

        # Feature highlights
        features = [
            "▶ Auto-plays your last-watched stream on launch",
            "📺 Live followed channels from all three platforms",
            "📊 Real-time viewer momentum & SullyGnome analytics",
            "🎯 Next-stream prediction & smart switching",
            "💬 Built-in Twitch chat with transliteration",
        ]
        for feature in features:
            row = QLabel(feature)
            row.setObjectName("posterBody")
            poster_layout.addWidget(row)

        layout.addWidget(poster)

        # ------------------------------------------------------------
        # INSTALL FOLDER CONFIRMATION
        # ------------------------------------------------------------
        install_card = QFrame()
        install_card.setObjectName("installCard")
        install_layout = QVBoxLayout(install_card)
        install_layout.setContentsMargins(16, 12, 16, 12)
        install_layout.setSpacing(4)

        install_title = QLabel("📁 INSTALLATION FOLDER")
        install_title.setObjectName("posterSection")
        install_layout.addWidget(install_title)

        install_hint = QLabel(
            "Watcher is installed and will run from this folder:"
        )
        install_hint.setObjectName("installLabel")
        install_layout.addWidget(install_hint)

        self.install_path_label = QLabel(_install_dir())
        self.install_path_label.setObjectName("installPath")
        self.install_path_label.setWordWrap(True)
        install_layout.addWidget(self.install_path_label)

        layout.addWidget(install_card)

        layout.addStretch()

        # ------------------------------------------------------------
        # START BUTTON
        # ------------------------------------------------------------
        start_row = QHBoxLayout()
        start_row.addStretch()
        self.start_button = QPushButton("GET STARTED")
        self.start_button.setObjectName("startButton")
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.clicked.connect(self.accept)
        start_row.addWidget(self.start_button)
        start_row.addStretch()
        layout.addLayout(start_row)


def should_show_wizard():
    """Return True if the first-run wizard has not been shown yet."""
    from PySide6.QtCore import QSettings
    settings = QSettings(APP_ORGANIZATION, APP_NAME)
    return not settings.value("first_run_wizard_shown", False, type=bool)


def mark_wizard_shown():
    """Persist that the first-run wizard has been shown."""
    from PySide6.QtCore import QSettings
    settings = QSettings(APP_ORGANIZATION, APP_NAME)
    settings.setValue("first_run_wizard_shown", True)
    settings.sync()


def run_first_run_wizard(parent=None):
    """Show the first-run wizard if it hasn't been shown yet.

    Returns True if the wizard was shown (and dismissed), False otherwise.
    """
    if not should_show_wizard():
        return False
    debug("[WIZARD] Showing first-run wizard")
    wizard = FirstRunWizard(parent=parent)
    wizard.exec()
    mark_wizard_shown()
    debug("[WIZARD] First-run wizard dismissed")
    return True