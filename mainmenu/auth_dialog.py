"""Auth Dialog — popup window for platform login.

Shows a dialog asking the user to authenticate with Twitch/Kick/YouTube
when tokens are missing or expired.
"""

import os
import threading
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QSizePolicy,
)
from logger import debug


class AuthDialog(QDialog):
    """Popup dialog for platform authentication."""
    
    def __init__(self, platform="twitch", parent=None):
        super().__init__(parent)
        self.platform = platform
        self.token_result = None
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle(f"{self.platform.title()} Authentication")
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)
        self.setStyleSheet("""
            QDialog { background: #0e0e10; color: white; }
            QLabel { color: #efeff1; }
            QLineEdit { 
                background: #1f1f23; color: #efeff1; border: 1px solid #3a3a3d;
                padding: 8px; border-radius: 4px; font-size: 12px;
            }
            QPushButton {
                padding: 10px 20px; border-radius: 4px; font-weight: bold;
                font-size: 13px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title = QLabel(f"🔐 {self.platform.title()} Login Required")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #9147ff;")
        layout.addWidget(title)
        
        # Description
        desc = QLabel(
            f"Your {self.platform.title()} token is expired or missing. "
            f"Please authenticate to continue."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #adadb8; font-size: 12px;")
        layout.addWidget(desc)
        
        if self.platform == "twitch":
            self._setup_twitch_ui(layout)
        elif self.platform == "kick":
            self._setup_kick_ui(layout)
        elif self.platform == "youtube":
            self._setup_youtube_ui(layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        skip_btn = QPushButton("Skip for Now")
        skip_btn.setStyleSheet("background: #3a3a3d; color: #adadb8;")
        skip_btn.clicked.connect(self.reject)
        btn_layout.addWidget(skip_btn)
        
        login_btn = QPushButton(f"Login with {self.platform.title()}")
        login_btn.setStyleSheet("background: #9147ff; color: white;")
        login_btn.clicked.connect(self._do_login)
        btn_layout.addWidget(login_btn)
        
        layout.addLayout(btn_layout)
    
    def _setup_twitch_ui(self, layout):
        """Setup Twitch-specific UI fields."""
        # Client ID
        id_label = QLabel("Client ID:")
        id_label.setStyleSheet("color: #adadb8; font-size: 11px;")
        layout.addWidget(id_label)
        
        self.client_id_input = QLineEdit()
        self.client_id_input.setPlaceholderText("Enter your Twitch Client ID")
        # Pre-fill from env if available
        from dotenv import load_dotenv
        load_dotenv()
        self.client_id_input.setText(os.getenv("TWITCH_CLIENT_ID", ""))
        layout.addWidget(self.client_id_input)
        
        # Client Secret
        secret_label = QLabel("Client Secret:")
        secret_label.setStyleSheet("color: #adadb8; font-size: 11px;")
        layout.addWidget(secret_label)
        
        self.client_secret_input = QLineEdit()
        self.client_secret_input.setPlaceholderText("Enter your Twitch Client Secret")
        self.client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.client_secret_input)
        
        # Help text
        help_text = QLabel(
            "Get your credentials at: https://dev.twitch.tv/console/apps"
        )
        help_text.setStyleSheet("color: #6d6d7b; font-size: 10px;")
        help_text.setOpenExternalLinks(True)
        layout.addWidget(help_text)
    
    def _setup_kick_ui(self, layout):
        """Setup Kick-specific UI fields."""
        id_label = QLabel("Client ID:")
        id_label.setStyleSheet("color: #adadb8; font-size: 11px;")
        layout.addWidget(id_label)
        
        self.client_id_input = QLineEdit()
        self.client_id_input.setPlaceholderText("Enter your Kick Client ID")
        layout.addWidget(self.client_id_input)
        
        secret_label = QLabel("Client Secret:")
        secret_label.setStyleSheet("color: #adadb8; font-size: 11px;")
        layout.addWidget(secret_label)
        
        self.client_secret_input = QLineEdit()
        self.client_secret_input.setPlaceholderText("Enter your Kick Client Secret")
        self.client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.client_secret_input)
    
    def _setup_youtube_ui(self, layout):
        """Setup YouTube-specific UI fields."""
        id_label = QLabel("API Key:")
        id_label.setStyleSheet("color: #adadb8; font-size: 11px;")
        layout.addWidget(id_label)
        
        self.client_id_input = QLineEdit()
        self.client_id_input.setPlaceholderText("Enter your YouTube API Key")
        layout.addWidget(self.client_id_input)
    
    def _do_login(self):
        """Perform the login flow."""
        if self.platform == "twitch":
            self._do_twitch_login()
        elif self.platform == "kick":
            self._do_kick_login()
        elif self.platform == "youtube":
            self._do_youtube_login()
    
    def _do_twitch_login(self):
        """Perform Twitch OAuth login."""
        client_id = self.client_id_input.text().strip()
        client_secret = self.client_secret_input.text().strip()
        
        if not client_id:
            self._show_error("Please enter your Twitch Client ID")
            return
        
        # Save credentials to .env
        self._save_env("TWITCH_CLIENT_ID", client_id)
        if client_secret:
            self._save_env("TWITCH_CLIENT_SECRET", client_secret)
        
        # Start OAuth flow in background
        def do_oauth():
            try:
                from twitch_auth import authenticate
                success = authenticate()
                if success:
                    debug("[AUTH] Twitch login successful")
                    self.token_result = "success"
                else:
                    debug("[AUTH] Twitch login failed")
                    self.token_result = "failed"
            except Exception as e:
                debug(f"[AUTH] Twitch login error: {e}")
                self.token_result = "failed"
        
        # Show loading state
        self._show_loading("Opening browser for Twitch login...")
        threading.Thread(target=do_oauth, daemon=True).start()
    
    def _do_kick_login(self):
        """Perform Kick login."""
        client_id = self.client_id_input.text().strip()
        client_secret = self.client_secret_input.text().strip()
        
        if client_id:
            self._save_env("KICK_CLIENT_ID", client_id)
        if client_secret:
            self._save_env("KICK_CLIENT_SECRET", client_secret)
        
        self.token_result = "success"
        self.accept()
    
    def _do_youtube_login(self):
        """Perform YouTube login."""
        api_key = self.client_id_input.text().strip()
        
        if api_key:
            self._save_env("YOUTUBE_API_KEY", api_key)
        
        self.token_result = "success"
        self.accept()
    
    def _save_env(self, key, value):
        """Save a variable to .env file."""
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        lines = []
        if os.path.exists(env_file):
            with open(env_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        
        new_lines = []
        for line in lines:
            if line.strip().startswith(f"{key}="):
                continue
            new_lines.append(line)
        new_lines.append(f"{key}={value}\n")
        
        with open(env_file, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        
        os.environ[key] = value
        debug(f"[AUTH] Saved {key} to .env")
    
    def _show_loading(self, text):
        """Show loading state."""
        self._loading_label = QLabel(text)
        self._loading_label.setStyleSheet("color: #9147ff; font-size: 12px; font-weight: bold;")
        self.layout().insertWidget(2, self._loading_label)
    
    def _show_error(self, text):
        """Show error message."""
        error_label = QLabel(f"❌ {text}")
        error_label.setStyleSheet("color: #ff4444; font-size: 11px;")
        self.layout().insertWidget(2, error_label)
        QTimer.singleShot(3000, error_label.deleteLater)


def show_auth_dialog(platform="twitch", parent=None):
    """Show auth dialog and return True if authenticated."""
    dialog = AuthDialog(platform=platform, parent=parent)
    result = dialog.exec()
    return dialog.token_result == "success"