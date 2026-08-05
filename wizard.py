"""Installation wizard — multi-step first-run setup for Watcher.

Displayed once on first launch.  Uses QSettings to remember that the
wizard has already been shown, so it never blocks subsequent startups.

Steps:
    1. Welcome          — app poster, platform badges, feature list
    2. License          — scrollable license text, "I Accept" checkbox
    3. Data & Database  — data folder location, DB initialization
    4. Shortcuts        — optional desktop / start-menu shortcuts
    5. Complete         — "Launch Watcher" button
"""

import os
import sys

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QCheckBox,
    QScrollArea,
    QWidget,
    QStackedWidget,
)

from logger import debug
from paths import get_data_dir, get_db_path, get_license_path, migrate_legacy_data

APP_ORGANIZATION = "Watcher"
APP_NAME = "Watcher Control Center"

# Version-scoped flag so the wizard reliably shows for this release
# even if a stale flag exists from an earlier run or version.
WIZARD_FLAG_KEY = "first_run_wizard_shown_v08"

# Platform brand colors used in the poster.
PLATFORM_COLORS = {
    "Twitch": "#9146FF",
    "Kick": "#53FC18",
    "YouTube": "#FF0000",
}


def _install_dir():
    """Return the directory the app is running from."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _wizard_style():
    """Dark stylesheet for the installation wizard."""
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
    QLabel#stepTitle {
        color: #b7a7ff;
        font-size: 18px;
        font-weight: bold;
    }
    QLabel#stepBody {
        color: #d0d0e0;
        font-size: 12px;
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
    QLabel#licenseText {
        color: #c0c0d0;
        font-size: 11px;
        font-family: Consolas, monospace;
    }
    QLabel#statusOk {
        color: #75e6a5;
        font-size: 12px;
        font-weight: bold;
    }
    QLabel#statusWarn {
        color: #e6a575;
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
    QFrame#licenseCard {
        background-color: #0e0e16;
        border: 1px solid #2a2a40;
        border-radius: 8px;
    }
    QPushButton#navButton {
        background-color: #30275c;
        color: #ffffff;
        border: 1px solid #7166b3;
        border-radius: 6px;
        padding: 10px 24px;
        font-size: 13px;
        font-weight: bold;
    }
    QPushButton#navButton:hover {
        background-color: #45377e;
    }
    QPushButton#navButton:disabled {
        background-color: #1a1a2e;
        color: #555566;
        border: 1px solid #2a2a40;
    }
    QPushButton#backButton {
        background-color: #1a1a2e;
        color: #8888aa;
        border: 1px solid #2a2a40;
        border-radius: 6px;
        padding: 10px 24px;
        font-size: 13px;
    }
    QPushButton#backButton:hover {
        background-color: #252540;
    }
    QCheckBox {
        color: #d0d0e0;
        font-size: 12px;
    }
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
    }
    QScrollArea {
        background-color: #0e0e16;
        border: 1px solid #2a2a40;
        border-radius: 8px;
    }
    """


# ================================================================
# STEP PAGES
# ================================================================

class WelcomePage(QWidget):
    """Step 1: Welcome poster with app description."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

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

        features = [
            "▶ Auto-plays your last-watched stream on launch",
            "📺 Live followed channels from all three platforms",
            "📊 Real-time viewer momentum & SullyGnome analytics",
            "🎯 Next-stream prediction & raid chain following",
            "💬 Built-in Twitch chat with transliteration",
        ]
        for feature in features:
            row = QLabel(feature)
            row.setObjectName("posterBody")
            poster_layout.addWidget(row)

        layout.addWidget(poster)

        # Install folder info
        install_card = QFrame()
        install_card.setObjectName("installCard")
        install_layout = QVBoxLayout(install_card)
        install_layout.setContentsMargins(16, 12, 16, 12)
        install_layout.setSpacing(4)

        install_title = QLabel("📁 INSTALLATION FOLDER")
        install_title.setObjectName("posterSection")
        install_layout.addWidget(install_title)

        install_hint = QLabel("Watcher is installed and will run from this folder:")
        install_hint.setObjectName("installLabel")
        install_layout.addWidget(install_hint)

        install_path = QLabel(_install_dir())
        install_path.setObjectName("installPath")
        install_path.setWordWrap(True)
        install_layout.addWidget(install_path)

        layout.addWidget(install_card)
        layout.addStretch()


class LicensePage(QWidget):
    """Step 2: License agreement with scrollable text and accept checkbox."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("📜 LICENSE AGREEMENT")
        title.setObjectName("stepTitle")
        layout.addWidget(title)

        # Scrollable license text
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(220)

        license_widget = QWidget()
        license_layout = QVBoxLayout(license_widget)
        license_layout.setContentsMargins(12, 12, 12, 12)

        license_text = self._load_license_text()
        license_label = QLabel(license_text)
        license_label.setObjectName("licenseText")
        license_label.setWordWrap(True)
        license_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        license_layout.addWidget(license_label)

        scroll.setWidget(license_widget)
        layout.addWidget(scroll)

        # Accept checkbox
        self.accept_checkbox = QCheckBox(
            "I have read and accept the license agreement.\n"
            "I understand this software is for personal use only, "
            "is not distributed, and is not affiliated with Twitch, Kick, or YouTube."
        )
        layout.addWidget(self.accept_checkbox)

    def _load_license_text(self):
        """Load the LICENSE file text, or return a fallback."""
        license_path = get_license_path()
        try:
            with open(license_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return (
                "MIT License\n\n"
                "Copyright (c) 2026 Watcher Contributors\n\n"
                "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
                "of this software and associated documentation files (the \"Software\"), to deal\n"
                "in the Software without restriction, including without limitation the rights\n"
                "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n"
                "copies of the Software, and to permit persons to whom the Software is\n"
                "furnished to do so, subject to the following conditions:\n\n"
                "The above copyright notice and this permission notice shall be included in all\n"
                "copies or substantial portions of the Software.\n\n"
                "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n"
                "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n"
                "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.\n\n"
                "PERSONAL USE ADDENDUM:\n"
                "This software is designed for one person's personal use only.\n"
                "It is not distributed, shared, or affiliated with Twitch, Kick, or YouTube."
            )


class DatabasePage(QWidget):
    """Step 3: Data folder and database initialization."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("💾 DATA & DATABASE SETUP")
        title.setObjectName("stepTitle")
        layout.addWidget(title)

        # Explanation
        info_card = QFrame()
        info_card.setObjectName("installCard")
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(16, 12, 16, 12)
        info_layout.setSpacing(6)

        info_text = QLabel(
            "Watcher uses an embedded SQLite database — no separate database\n"
            "software installation is required. Your data is stored locally\n"
            "on this computer and never leaves your machine."
        )
        info_text.setObjectName("stepBody")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)

        layout.addWidget(info_card)

        # Data folder
        data_card = QFrame()
        data_card.setObjectName("installCard")
        data_layout = QVBoxLayout(data_card)
        data_layout.setContentsMargins(16, 12, 16, 12)
        data_layout.setSpacing(4)

        data_title = QLabel("📂 DATA FOLDER")
        data_title.setObjectName("posterSection")
        data_layout.addWidget(data_title)

        data_hint = QLabel("Your database, logs, and settings will be stored in:")
        data_hint.setObjectName("installLabel")
        data_layout.addWidget(data_hint)

        data_path = QLabel(get_data_dir())
        data_path.setObjectName("installPath")
        data_path.setWordWrap(True)
        data_layout.addWidget(data_path)

        layout.addWidget(data_card)

        # DB status
        self.db_status = QLabel("Initializing database...")
        self.db_status.setObjectName("installLabel")
        layout.addWidget(self.db_status)

        # Migration status
        self.migration_status = QLabel("")
        self.migration_status.setObjectName("installLabel")
        self.migration_status.setWordWrap(True)
        layout.addWidget(self.migration_status)

        layout.addStretch()

    def initialize_database(self):
        """Initialize the database and update the status label."""
        try:
            # Migrate any legacy data files first
            moved = migrate_legacy_data()
            if moved:
                names = ", ".join(m[0] for m in moved)
                self.migration_status.setText(f"📦 Migrated existing data: {names}")
                self.migration_status.setObjectName("statusOk")
            else:
                self.migration_status.setText("")

            # Initialize the database (creates tables if needed)
            from core.db import init_db
            init_db()

            db_path = get_db_path()
            if os.path.exists(db_path):
                size = os.path.getsize(db_path)
                self.db_status.setText(
                    f"✅ Database ready: {db_path} ({size:,} bytes)"
                )
                self.db_status.setObjectName("statusOk")
            else:
                self.db_status.setText(f"⚠️ Database file not found at {db_path}")
                self.db_status.setObjectName("statusWarn")
        except Exception as exc:
            self.db_status.setText(f"⚠️ Database initialization: {exc}")
            self.db_status.setObjectName("statusWarn")


class ShortcutsPage(QWidget):
    """Step 4: Optional shortcut creation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("🔗 SHORTCUTS")
        title.setObjectName("stepTitle")
        layout.addWidget(title)

        info = QLabel(
            "Optionally create shortcuts to launch Watcher more easily.\n"
            "You can always run Watcher.exe directly from its folder."
        )
        info.setObjectName("stepBody")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.desktop_checkbox = QCheckBox("Create Desktop shortcut")
        self.desktop_checkbox.setChecked(True)
        layout.addWidget(self.desktop_checkbox)

        self.startmenu_checkbox = QCheckBox("Add to Start Menu")
        self.startmenu_checkbox.setChecked(True)
        layout.addWidget(self.startmenu_checkbox)

        self.shortcut_status = QLabel("")
        self.shortcut_status.setObjectName("installLabel")
        self.shortcut_status.setWordWrap(True)
        layout.addWidget(self.shortcut_status)

        layout.addStretch()

    def create_shortcuts(self):
        """Create the requested shortcuts. Returns status message."""
        results = []
        exe_path = sys.executable if getattr(sys, "frozen", False) else None

        if not exe_path:
            self.shortcut_status.setText(
                "⚠️ Shortcuts are only available when running the packaged Watcher.exe"
            )
            self.shortcut_status.setObjectName("statusWarn")
            return

        if self.desktop_checkbox.isChecked():
            ok = self._create_shortcut(
                os.path.join(os.path.expanduser("~"), "Desktop", "Watcher.lnk"),
                exe_path,
            )
            results.append(("Desktop", ok))

        if self.startmenu_checkbox.isChecked():
            start_menu = os.path.join(
                os.environ.get("APPDATA", ""),
                "Microsoft", "Windows", "Start Menu", "Programs",
            )
            ok = self._create_shortcut(
                os.path.join(start_menu, "Watcher.lnk"),
                exe_path,
            )
            results.append(("Start Menu", ok))

        if results:
            lines = []
            for name, ok in results:
                icon = "✅" if ok else "⚠️"
                lines.append(f"{icon} {name} shortcut {'created' if ok else 'failed'}")
            self.shortcut_status.setText("\n".join(lines))
            self.shortcut_status.setObjectName("statusOk" if all(r[1] for r in results) else "statusWarn")
        else:
            self.shortcut_status.setText("No shortcuts requested.")
            self.shortcut_status.setObjectName("installLabel")

    def _create_shortcut(self, lnk_path, target_path):
        """Create a Windows .lnk shortcut using PowerShell."""
        try:
            import subprocess
            ps_script = (
                f'$ws = New-Object -ComObject WScript.Shell; '
                f'$s = $ws.CreateShortcut("{lnk_path}"); '
                f'$s.TargetPath = "{target_path}"; '
                f'$s.WorkingDirectory = "{os.path.dirname(target_path)}"; '
                f'$s.Description = "Watcher Control Center"; '
                f'$s.Save()'
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0 and os.path.exists(lnk_path)
        except Exception:
            return False


class CompletePage(QWidget):
    """Step 5: Installation complete."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addStretch()

        title = QLabel("✅ INSTALLATION COMPLETE")
        title.setObjectName("stepTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        body = QLabel(
            "Watcher is ready to use.\n\n"
            "• Open source (MIT License) — personal use only\n"
            "• Not affiliated with Twitch, Kick, or YouTube\n"
            "• All data stored locally on this computer\n\n"
            "Click LAUNCH WATCHER to get started."
        )
        body.setObjectName("stepBody")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)
        layout.addWidget(body)

        layout.addStretch()


# ================================================================
# MAIN WIZARD DIALOG
# ================================================================

class InstallWizard(QDialog):
    """Multi-step installation wizard for first-run setup."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Watcher — Installation Wizard")
        self.setModal(True)
        self.setMinimumSize(620, 580)
        self.setStyleSheet(_wizard_style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # Step indicator
        self.step_label = QLabel("Step 1 of 5 — Welcome")
        self.step_label.setObjectName("posterSection")
        self.step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.step_label)

        # Stacked pages
        self.stack = QStackedWidget()
        self.welcome_page = WelcomePage()
        self.license_page = LicensePage()
        self.database_page = DatabasePage()
        self.shortcuts_page = ShortcutsPage()
        self.complete_page = CompletePage()

        self.stack.addWidget(self.welcome_page)    # 0
        self.stack.addWidget(self.license_page)    # 1
        self.stack.addWidget(self.database_page)   # 2
        self.stack.addWidget(self.shortcuts_page)  # 3
        self.stack.addWidget(self.complete_page)   # 4

        layout.addWidget(self.stack)

        # Navigation buttons
        nav_row = QHBoxLayout()
        nav_row.setSpacing(8)

        self.back_button = QPushButton("← BACK")
        self.back_button.setObjectName("backButton")
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.clicked.connect(self._go_back)
        self.back_button.setVisible(False)
        nav_row.addWidget(self.back_button)

        nav_row.addStretch()

        self.next_button = QPushButton("NEXT →")
        self.next_button.setObjectName("navButton")
        self.next_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_button.clicked.connect(self._go_next)
        nav_row.addWidget(self.next_button)

        layout.addLayout(nav_row)

        # Connect license checkbox to enable/disable next button
        self.license_page.accept_checkbox.toggled.connect(self._on_license_toggled)

        self._update_nav()

    def _on_license_toggled(self, checked):
        self._update_nav()

    def _update_nav(self):
        """Update button states based on current step."""
        step = self.stack.currentIndex()
        step_names = ["Welcome", "License Agreement", "Data & Database", "Shortcuts", "Complete"]
        self.step_label.setText(f"Step {step + 1} of 5 — {step_names[step]}")

        self.back_button.setVisible(step > 0 and step < 4)

        if step == 0:
            self.next_button.setText("NEXT →")
            self.next_button.setEnabled(True)
        elif step == 1:
            self.next_button.setText("NEXT →")
            self.next_button.setEnabled(self.license_page.accept_checkbox.isChecked())
        elif step == 2:
            self.next_button.setText("NEXT →")
            self.next_button.setEnabled(True)
        elif step == 3:
            self.next_button.setText("NEXT →")
            self.next_button.setEnabled(True)
        elif step == 4:
            self.next_button.setText("🚀 LAUNCH WATCHER")
            self.next_button.setEnabled(True)

    def _go_next(self):
        step = self.stack.currentIndex()

        if step == 1:
            # Moving from license to database — initialize DB
            self.database_page.initialize_database()

        if step == 3:
            # Moving from shortcuts to complete — create shortcuts
            self.shortcuts_page.create_shortcuts()

        if step < 4:
            self.stack.setCurrentIndex(step + 1)
            self._update_nav()
        else:
            # Final step — launch
            self.accept()

    def _go_back(self):
        step = self.stack.currentIndex()
        if step > 0:
            self.stack.setCurrentIndex(step - 1)
            self._update_nav()


# ================================================================
# PUBLIC API (same interface as before)
# ================================================================

def should_show_wizard():
    """Return True if the first-run wizard has not been shown yet."""
    settings = QSettings(APP_ORGANIZATION, APP_NAME)
    return not settings.value(WIZARD_FLAG_KEY, False, type=bool)


def mark_wizard_shown():
    """Persist that the first-run wizard has been shown."""
    settings = QSettings(APP_ORGANIZATION, APP_NAME)
    settings.setValue(WIZARD_FLAG_KEY, True)
    settings.sync()


def run_first_run_wizard(parent=None):
    """Show the installation wizard if it hasn't been shown yet.

    Returns True if the wizard was shown (and completed), False otherwise.
    The wizard is only marked as shown when the user completes all steps —
    closing it early (e.g. via the X button) will show it again on next launch.
    """
    if not should_show_wizard():
        return False
    debug("[WIZARD] Showing installation wizard")
    wizard = InstallWizard(parent=parent)
    result = wizard.exec()
    if result == QDialog.DialogCode.Accepted:
        mark_wizard_shown()
        debug("[WIZARD] Installation wizard completed")
        return True
    debug("[WIZARD] Installation wizard dismissed without completing")
    return False
