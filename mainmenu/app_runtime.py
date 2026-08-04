from PySide6.QtWidgets import QMessageBox

from core import run_in_background


class MainMenuRuntime:
    def load_twitch(self):
        self.dispatcher_panel.set_status("Connecting to Twitch...")
        self._run_background(self.api.get_current_user, self.handle_user_loaded, self.handle_user_failed)

    def handle_user_loaded(self, user):
        if self.is_closing:
            return
        self.user = user or {}
        self.connection_label.setText("● CONNECTED")
        self.connection_label.setStyleSheet("color: #72d6a0;")
        self.log(f"Logged in as {self.user.get('display_name', 'unknown')}")
        self.chat_panel.set_username(self.user.get("login", ""))
        self.dispatcher_panel.set_status("Connected to Twitch")
        self.load_live_channels()

    def handle_user_failed(self, message):
        if self.is_closing:
            return
        self.connection_label.setText("● ERROR")
        self.connection_label.setStyleSheet("color: #ff7777;")
        self.dispatcher_panel.set_status("Twitch connection error")
        self.log(f"ERROR: {message}")
        QMessageBox.critical(self, "Twitch Error", message)

    def _run_background(self, func, on_success, on_error):
        run_in_background(func, on_success, on_error)
