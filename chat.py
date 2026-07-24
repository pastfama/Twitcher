import html
import socket
import ssl
import threading

import requests

from PySide6.QtCore import QObject, Signal

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QLabel,
)

from twitch_token_manager import get_valid_token


# ============================================================
#                    CONFIGURATION
# ============================================================


TWITCH_IRC_HOST = (
    "irc.chat.twitch.tv"
)


TWITCH_IRC_PORT = 6697


TWITCH_VALIDATE_URL = (
    "https://id.twitch.tv/oauth2/validate"
)


# ============================================================
#                    TOKEN HELPERS
# ============================================================


def normalize_token(

    token

):

    token = (

        token

        or ""

    ).strip()


    if token.lower().startswith(

        "oauth:"

    ):

        token = token[6:]


    return token


def load_twitch_token():

    try:

        token = get_valid_token()


        if not token:

            print()

            print(

                "[CHAT] No valid Twitch access token available."

            )

            return ""


        return normalize_token(

            token

        )


    except Exception as error:

        print()

        print(

            "[CHAT] Failed to obtain valid Twitch token:"

        )

        print(

            error

        )

        return ""


def get_token_identity(

    access_token

):

    access_token = normalize_token(

        access_token

    )


    if not access_token:

        raise RuntimeError(

            "Twitch access token is empty."

        )


    response = requests.get(

        TWITCH_VALIDATE_URL,

        headers={

            "Authorization":

            f"OAuth {access_token}"

        },

        timeout=20,

    )


    if response.status_code != 200:

        raise RuntimeError(

            "Twitch token validation failed.\n\n"

            f"HTTP {response.status_code}\n"

            f"{response.text}"

        )


    data = response.json()


    login = (

        data.get(

            "login",

            ""

        )

        or ""

    ).strip().lower()


    user_id = (

        data.get(

            "user_id",

            ""

        )

        or ""

    )


    if not login:

        raise RuntimeError(

            "Twitch did not return the username belonging "

            "to the access token."

        )


    print()

    print(

        "[CHAT] Twitch token identity:"

    )

    print(

        f"        Username: {login}"

    )

    print(

        f"        User ID:  {user_id}"

    )


    print()

    print(

        "[CHAT] Twitch token scopes:"

    )

    print(

        f"        {data.get('scopes', [])}"

    )


    return login, user_id


# ============================================================
#                    TWITCH IRC CLIENT
# ============================================================


class TwitchChatClient(

    QObject

):


    message_received = Signal(

        str,

        str,

        str,

        dict

    )


    system_message = Signal(

        str

    )


    connected = Signal()


    disconnected = Signal()


    message_sent = Signal(

        str

    )


    authenticated = Signal()


    authentication_failed = Signal(

        str

    )


    def __init__(

        self,

        access_token,

        channel

    ):

        super().__init__()


        self.access_token = normalize_token(

            access_token

        )


        self.channel = (

            channel

            or ""

        ).strip().lower().lstrip("#")


        self.username = ""


        self.socket = None


        self.running = False


        self.authenticated_state = False


        self.joined = False


        self.thread = None


        self.socket_lock = threading.Lock()


        self._connected_emitted = False


    # ========================================================
    #                    CONNECT
    # ========================================================


    def connect_chat(

        self

    ):

        if self.running:

            return


        if not self.access_token:

            self.system_message.emit(

                "Twitch access token is missing."

            )

            return


        if not self.channel:

            self.system_message.emit(

                "Twitch channel is missing."

            )

            return


        # ----------------------------------------------------
        # GET USERNAME FROM TOKEN
        # ----------------------------------------------------


        try:

            self.username, _ = (

                get_token_identity(

                    self.access_token

                )

            )


        except Exception as error:

            self.authentication_failed.emit(

                str(error)

            )


            self.system_message.emit(

                str(error)

            )


            return


        self.running = True


        self.authenticated_state = False


        self.joined = False


        self._connected_emitted = False


        self.thread = threading.Thread(

            target=self._run,

            name="TwitchChat",

            daemon=True

        )


        self.thread.start()


    # ========================================================
    #                    MAIN CONNECTION THREAD
    # ========================================================


    def _run(

        self

    ):

        sock = None


        try:

            self.system_message.emit(

                f"Connecting to #{self.channel}..."

            )


            raw_socket = socket.socket(

                socket.AF_INET,

                socket.SOCK_STREAM

            )


            raw_socket.settimeout(

                1.0

            )


            context = ssl.create_default_context()


            sock = context.wrap_socket(

                raw_socket,

                server_hostname=TWITCH_IRC_HOST

            )


            sock.connect(

                (

                    TWITCH_IRC_HOST,

                    TWITCH_IRC_PORT

                )

            )


            with self.socket_lock:

                self.socket = sock


            self.system_message.emit(

                "Secure connection established."

            )


            # ------------------------------------------------
            # IRC AUTHENTICATION
            # ------------------------------------------------


            self._send(

                f"PASS oauth:{self.access_token}",

                sock

            )


            self._send(

                f"NICK {self.username}",

                sock

            )


            # ------------------------------------------------
            # IRC CAPABILITIES
            # ------------------------------------------------


            self._send(

                "CAP REQ :"

                "twitch.tv/tags "

                "twitch.tv/commands "

                "twitch.tv/membership",

                sock

            )


            buffer = ""


            while self.running:

                try:

                    data = sock.recv(

                        8192

                    )


                except socket.timeout:

                    continue


                except (

                    OSError,

                    ConnectionError

                ):

                    break


                if not data:

                    break


                buffer += data.decode(

                    "utf-8",

                    errors="ignore"

                )


                while "\r\n" in buffer:

                    line, buffer = (

                        buffer.split(

                            "\r\n",

                            1

                        )

                    )


                    if line:

                        self._handle_irc_line(

                            line,

                            sock

                        )


        except ssl.SSLError as error:

            if self.running:

                self.system_message.emit(

                    f"TLS connection error: {error}"

                )


        except Exception as error:

            if self.running:

                self.system_message.emit(

                    f"Chat connection error: {error}"

                )


        finally:

            self.running = False


            self.authenticated_state = False


            self.joined = False


            with self.socket_lock:

                current_socket = self.socket

                self.socket = None


            if current_socket:

                try:

                    current_socket.shutdown(

                        socket.SHUT_RDWR

                    )

                except Exception:

                    pass


                try:

                    current_socket.close()

                except Exception:

                    pass


            self.disconnected.emit()


            self.system_message.emit(

                "Disconnected from chat."

            )


    # ========================================================
    #                    IRC LINE HANDLER
    # ========================================================


    def _handle_irc_line(

        self,

        line,

        sock

    ):

        print(

            f"[IRC] {line}"

        )


        # ----------------------------------------------------
        # PING
        # ----------------------------------------------------


        if line.startswith(

            "PING"

        ):

            self._send(

                "PONG :tmi.twitch.tv",

                sock

            )

            return


        # ----------------------------------------------------
        # AUTHENTICATION SUCCESS
        # ----------------------------------------------------


        if " 001 " in line:

            self.authenticated_state = True


            self.authenticated.emit()


            self.system_message.emit(

                f"Authenticated as {self.username}."

            )


            self._send(

                f"JOIN #{self.channel}",

                sock

            )


            self.system_message.emit(

                f"Joining #{self.channel}..."

            )


            return


        # ----------------------------------------------------
        # AUTHENTICATION FAILURE
        # ----------------------------------------------------


        authentication_errors = (

            "Login authentication failed",

            "Login unsuccessful",

            "Improperly formatted auth",

            "Improperly formatted username",

            "Invalid NICK",

            "Login authentication failed",

        )


        if any(

            error_text in line

            for error_text in authentication_errors

        ):

            self.authenticated_state = False


            self.authentication_failed.emit(

                line

            )


            self.system_message.emit(

                "Twitch IRC authentication failed."

            )


            self.running = False


            return


        # ----------------------------------------------------
        # NOTICE
        # ----------------------------------------------------


        if " NOTICE " in line:

            self.system_message.emit(

                self._extract_notice(

                    line

                )

            )

            return


        # ----------------------------------------------------
        # JOIN CONFIRMATION
        # ----------------------------------------------------


        if (

            f" JOIN #{self.channel}"

            in line

        ):

            if not self._connected_emitted:

                self._connected_emitted = True


                self.joined = True


                self.system_message.emit(

                    f"Connected to #{self.channel}"

                )


                self.connected.emit()


            return


        # ----------------------------------------------------
        # CHAT MESSAGE
        # ----------------------------------------------------


        if " PRIVMSG " in line:

            self._handle_privmsg(

                line

            )


    # ========================================================
    #                    NOTICE EXTRACTION
    # ========================================================


    def _extract_notice(

        self,

        line

    ):

        if " :" in line:

            return (

                "[TWITCH] "

                + line.split(

                    " :",

                    1

                )[1]

            )


        return (

            "[TWITCH] "

            + line

        )


    # ========================================================
    #                    PRIVMSG PARSER
    # ========================================================


    def _handle_privmsg(

        self,

        line

    ):

        try:

            tags = {}


            # ------------------------------------------------
            # TAGS
            # ------------------------------------------------


            if line.startswith("@"):

                tag_part, line = (

                    line.split(

                        " ",

                        1

                    )

                )


                for tag in tag_part[1:].split(";"):

                    if "=" in tag:

                        key, value = (

                            tag.split(

                                "=",

                                1

                            )

                        )


                        tags[key] = (

                            self._unescape_tag(

                                value

                            )

                        )

                    else:

                        tags[tag] = ""


            # ------------------------------------------------
            # PREFIX
            # ------------------------------------------------


            prefix = ""


            if line.startswith(":"):

                prefix, line = (

                    line[1:].split(

                        " ",

                        1

                    )

                )


            # ------------------------------------------------
            # COMMAND
            # ------------------------------------------------


            parts = line.split(

                " ",

                1

            )


            if len(parts) < 2:

                return


            command, remainder = parts


            if command != "PRIVMSG":

                return


            # ------------------------------------------------
            # CHANNEL + MESSAGE
            # ------------------------------------------------


            if " :" not in remainder:

                return


            channel_part, message = (

                remainder.split(

                    " :",

                    1

                )

            )


            channel = (

                channel_part

                .lstrip("#")

            )


            # ------------------------------------------------
            # USERNAME
            # ------------------------------------------------


            username = (

                tags.get(

                    "display-name"

                )

                or prefix.split(

                    "!",

                    1

                )[0]

            )


            self.message_received.emit(

                username,

                channel,

                message,

                tags

            )


        except Exception as error:

            print(

                "[CHAT PARSE ERROR]",

                error

            )


    # ========================================================
    #                    TAG UNESCAPING
    # ========================================================


    def _unescape_tag(

        self,

        value

    ):

        return (

            value

            .replace(

                r"\s",

                " "

            )

            .replace(

                r"\:",

                ";"

            )

            .replace(

                r"\r",

                "\r"

            )

            .replace(

                r"\n",

                "\n"

            )

            .replace(

                r"\\",

                "\\"

            )

        )


    # ========================================================
    #                    SEND MESSAGE
    # ========================================================


    def send_message(

        self,

        message

    ):

        message = (

            message

            or ""

        ).strip()


        if not message:

            return False


        if not self.running:

            return False


        if not self.authenticated_state:

            return False


        with self.socket_lock:

            sock = self.socket


        if not sock:

            return False


        success = self._send(

            f"PRIVMSG #{self.channel} :{message}",

            sock

        )


        if success:

            self.message_sent.emit(

                message

            )


        return success


    # ========================================================
    #                    SEND IRC COMMAND
    # ========================================================


    def _send(

        self,

        message,

        sock=None

    ):

        if sock is None:

            with self.socket_lock:

                sock = self.socket


        if not sock:

            return False


        try:

            sock.sendall(

                (

                    message

                    + "\r\n"

                ).encode(

                    "utf-8"

                )

            )


            return True


        except (

            OSError,

            ConnectionError

        ):

            return False


    # ========================================================
    #                    DISCONNECT
    # ========================================================


    def disconnect_chat(

        self

    ):

        self.running = False


        with self.socket_lock:

            sock = self.socket

            self.socket = None


        if sock:

            try:

                sock.shutdown(

                    socket.SHUT_RDWR

                )

            except Exception:

                pass


            try:

                sock.close()

            except Exception:

                pass


# ============================================================
#                    CHAT WIDGET
# ============================================================


class ChatWidget(

    QWidget

):


    def __init__(

        self,

        username=None,

        access_token=None,

        parent=None

    ):

        super().__init__(

            parent

        )


        self.access_token = (

            access_token

            or load_twitch_token()

        )


        self.client = None


        self.current_channel = None


        self.build_ui()


    # ========================================================
    #                    UI
    # ========================================================


    def build_ui(

        self

    ):

        layout = QVBoxLayout(

            self

        )


        self.status = QLabel(

            "Chat disconnected"

        )


        layout.addWidget(

            self.status

        )


        self.chat_display = QTextEdit()


        self.chat_display.setReadOnly(

            True

        )


        layout.addWidget(

            self.chat_display

        )


        controls = QHBoxLayout()


        self.message_input = QLineEdit()


        self.message_input.setPlaceholderText(

            "Write a message..."

        )


        self.message_input.returnPressed.connect(

            self.send_message

        )


        controls.addWidget(

            self.message_input

        )


        self.send_button = QPushButton(

            "SEND"

        )


        self.send_button.clicked.connect(

            self.send_message

        )


        controls.addWidget(

            self.send_button

        )


        layout.addLayout(

            controls

        )


        channel_controls = QHBoxLayout()


        self.channel_input = QLineEdit()


        self.channel_input.setPlaceholderText(

            "Channel name..."

        )


        channel_controls.addWidget(

            self.channel_input

        )


        self.connect_button = QPushButton(

            "CONNECT"

        )


        self.connect_button.clicked.connect(

            self.connect_to_channel

        )


        channel_controls.addWidget(

            self.connect_button

        )


        self.disconnect_button = QPushButton(

            "DISCONNECT"

        )


        self.disconnect_button.clicked.connect(

            self.disconnect

        )


        channel_controls.addWidget(

            self.disconnect_button

        )


        layout.addLayout(

            channel_controls

        )


    # ========================================================
    #                    CONNECT
    # ========================================================


    def connect_to_channel(

        self

    ):

        channel = (

            self.channel_input

            .text()

            .strip()

            .lower()

            .lstrip("#")

        )


        if not channel:

            self.display_system_message(

                "Enter a Twitch channel name."

            )

            return


        self.disconnect()


        self.current_channel = channel


        self.chat_display.clear()


        self.status.setText(

            f"Connecting to #{channel}..."

        )


        # ----------------------------------------------------
        # GET FRESH VALID TOKEN
        # ----------------------------------------------------


        self.access_token = (

            load_twitch_token()

        )


        if not self.access_token:

            self.display_system_message(

                "No valid Twitch access token is available."

            )


            self.status.setText(

                "🔴 No valid Twitch token"

            )


            return


        self.client = TwitchChatClient(

            access_token=self.access_token,

            channel=channel

        )


        self.client.message_received.connect(

            self.display_message

        )


        self.client.system_message.connect(

            self.display_system_message

        )


        self.client.connected.connect(

            self.chat_connected

        )


        self.client.disconnected.connect(

            self.chat_disconnected

        )


        self.client.authentication_failed.connect(

            self.chat_authentication_failed

        )


        self.client.connect_chat()


    # ========================================================
    #                    DISPLAY MESSAGE
    # ========================================================


    def display_message(

        self,

        username,

        channel,

        message,

        tags

    ):

        safe_username = html.escape(

            username

        )


        safe_message = html.escape(

            message

        )


        self.chat_display.append(

            f"<b>{safe_username}</b>: "

            f"{safe_message}"

        )


    # ========================================================
    #                    SYSTEM MESSAGE
    # ========================================================


    def display_system_message(

        self,

        message

    ):

        self.chat_display.append(

            "<i style='color:#9999bb'>"

            "[SYSTEM] "

            + html.escape(

                message

            )

            + "</i>"

        )


    # ========================================================
    #                    SEND MESSAGE
    # ========================================================


    def send_message(

        self

    ):

        message = (

            self.message_input

            .text()

            .strip()

        )


        if not message:

            return


        if not self.client:

            self.display_system_message(

                "You are not connected to Twitch chat."

            )

            return


        if not self.client.running:

            self.display_system_message(

                "Chat connection is not active."

            )

            return


        if self.client.send_message(

            message

        ):

            self.message_input.clear()


            self.display_message(

                self.client.username,

                self.current_channel,

                message,

                {}

            )


        else:

            self.display_system_message(

                "Failed to send message."

            )


    # ========================================================
    #                    CONNECTED
    # ========================================================


    def chat_connected(

        self

    ):

        self.status.setText(

            f"🟢 Connected to #{self.current_channel}"

        )


    # ========================================================
    #                    AUTHENTICATION FAILURE
    # ========================================================


    def chat_authentication_failed(

        self,

        message

    ):

        self.status.setText(

            "🔴 Twitch authentication failed"

        )


        self.display_system_message(

            "Twitch IRC authentication failed."

        )


        print()

        print(

            "[IRC AUTH FAILURE]"

        )

        print(

            message

        )


    # ========================================================
    #                    DISCONNECTED
    # ========================================================


    def chat_disconnected(

        self

    ):

        self.status.setText(

            "Chat disconnected"

        )


    # ========================================================
    #                    DISCONNECT
    # ========================================================


    def disconnect(

        self

    ):

        if self.client:

            self.client.disconnect_chat()

            self.client = None


        self.status.setText(

            "Chat disconnected"

        )


    # ========================================================
    #                    CLOSE
    # ========================================================


    def closeEvent(

        self,

        event

    ):

        self.disconnect()


        event.accept()