from PyQt6.QtCore import pyqtSignal, QObject

class TwitchIRC(QObject):
    on_privmsg = pyqtSignal(object)
    on_usernotice = pyqtSignal(object)
    on_clearchat = pyqtSignal(object)
    on_roomstate = pyqtSignal(dict)  # New signal for ROOMSTATE

    def handle_message(self, message):
        """Process incoming IRC messages"""
        if message.command == "PRIVMSG":
            self.on_privmsg.emit(message)
        elif message.command == "USERNOTICE":
            self.on_usernotice.emit(message)
        elif message.command == "CLEARCHAT":
            self.on_clearchat.emit(message)
        elif message.command == "ROOMSTATE":
            # Extract tags and emit signal
            tags = {k: v for k, v in message.tags.items()}
            self.on_roomstate.emit(tags)