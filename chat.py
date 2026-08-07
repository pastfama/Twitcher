import html
import socket
import ssl
import threading

import requests

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QAction

from logger import debug, info, warning, error

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextBrowser,
    QLineEdit,
    QPushButton,
    QLabel,
    QMenu,
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

            debug("")

            debug(

                "[CHAT] No valid Twitch access token available."

            )

            return ""


        return normalize_token(

            token

        )


    except Exception as error:

        debug("")

        debug(

            "[CHAT] Failed to obtain valid Twitch token:"

        )

        debug(

            error

        )

        return ""


# ============================================================
#                    TRANSLITERATION HELPERS
# ============================================================


def transliterate_to_russian(

    text

):

    if not text:

        return ""


    combos = [

        ("shch", "щ"),

        ("yo", "ё"),

        ("yu", "ю"),

        ("ya", "я"),

        ("zh", "ж"),

        ("kh", "х"),

        ("ts", "ц"),

        ("ch", "ч"),

        ("sh", "ш"),

        ("ye", "е"),

    ]


    letters = {

        "a": "а",

        "b": "б",

        "v": "в",

        "g": "г",

        "d": "д",

        "e": "е",

        "z": "з",

        "i": "и",

        "j": "й",

        "k": "к",

        "l": "л",

        "m": "м",

        "n": "н",

        "o": "о",

        "p": "п",

        "r": "р",

        "s": "с",

        "t": "т",

        "u": "у",

        "f": "ф",

        "h": "х",

        "c": "ц",

        "y": "ы",

        "q": "к",

        "w": "в",

        "x": "кс",

        "\"": "ь",

        "'": "ь",

        "`": "ъ",

    }


    def match_case(

        source,

        replacement

    ):

        if source.isupper():

            return replacement.upper()

        if source[0].isupper():

            return replacement.upper()

        return replacement


    result = ""

    index = 0

    length = len(text)


    while index < length:

        chunk = None

        for latin, cyrillic in combos:

            segment = text[index:index + len(latin)]

            if segment.lower() == latin:

                chunk = match_case(

                    segment,

                    cyrillic

                )

                index += len(latin)

                break

        if chunk is not None:

            result += chunk

            continue


        char = text[index]

        lower = char.lower()

        if lower in letters:

            result += match_case(

                char,

                letters[lower]

            )

        else:

            result += char

        index += 1


    return result



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


    debug("")

    debug(

        "[CHAT] Twitch token identity:"

    )

    debug(

        f"        Username: {login}"

    )

    debug(

        f"        User ID:  {user_id}"

    )


    debug("")

    debug(

        "[CHAT] Twitch token scopes:"

    )

    debug(

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

        debug(

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

            debug(

                f"[CHAT PARSE ERROR] {error}"

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


        # Third-party emote resolver (injected externally or created on demand).
        self._emote_resolver = None

        # Per-user avatar cache: username → avatar_url
        self._avatar_cache = {}

        # Channel badge cache: "type/version" → image_url
        self._badge_cache = {}

        # Broadcaster ID for the current channel (set on connect).
        self._broadcaster_id = None


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


        self.chat_display = QTextBrowser()


        self.chat_display.setReadOnly(

            True

        )

        self.chat_display.setOpenExternalLinks(

            False

        )

        self.chat_display.anchorClicked.connect(

            self.on_chat_anchor_clicked

        )

        self.chat_display.setContextMenuPolicy(

            Qt.CustomContextMenu

        )

        self.chat_display.customContextMenuRequested.connect(

            self.show_chat_context_menu

        )


        layout.addWidget(

            self.chat_display

        )


        controls = QHBoxLayout()
        controls.setSpacing(4)
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText(
            "Write a message..."
        )
        self.message_input.returnPressed.connect(
            self.send_message
        )
        controls.addWidget(
            self.message_input, 1
        )
        # Emoji picker button
        self.emoji_button = QPushButton("\U0001f600")
        self.emoji_button.setToolTip("Insert emoji")
        self.emoji_button.setFixedSize(32, 32)
        self.emoji_button.setStyleSheet(
            "font-size: 18px; padding: 2px; border: 1px solid #2a3a5a;"
            "border-radius: 4px; background-color: #0a0d18;"
        )
        self.emoji_button.clicked.connect(self._toggle_emoji_picker)
        controls.addWidget(
            self.emoji_button
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


        if not self.access_token:
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


    # ---- Twitch default color palette (for users without custom colors) ----
    _TWITCH_DEFAULT_COLORS = [
        "#FF0000", "#0000FF", "#008000", "#8B008B",
        "#FF6347", "#1E90FF", "#FF4500", "#9400D3",
        "#008080", "#DAA520", "#FF69B4", "#7B68EE",
    ]

    def _resolve_user_color(self, tags, username):
        """Return a hex colour for *username* from IRC tags or a
        deterministic fallback."""
        color = (tags or {}).get("color", "").strip()
        if color:
            return color
        # Deterministic fallback: hash the username to pick a palette colour.
        h = hash(username) & 0xFFFFFFFF
        return self._TWITCH_DEFAULT_COLORS[h % len(self._TWITCH_DEFAULT_COLORS)]

    def _replace_twitch_emotes(self, message, tags):
        """Replace emote placeholders with ``<img>`` tags.

        Twitch encodes emote positions in ``tags["emotes"]`` with the
        format ``id:start-end/id:start-end``.  We replace from right to
        left so that earlier character indices stay valid.
        """
        raw = (tags or {}).get("emotes", "")
        if not raw:
            return html.escape(message)

        # Parse emote positions.
        replacements = []  # [(start, end, emote_id), ...]
        for group in raw.split("/"):
            parts = group.split(":")
            if len(parts) != 2:
                continue
            emote_id = parts[0]
            for span in parts[1].split(","):
                pos = span.split("-")
                if len(pos) != 2:
                    continue
                start, end = int(pos[0]), int(pos[1])
                replacements.append((start, end, emote_id))

        # Sort by start position descending so we replace from right to left.
        replacements.sort(key=lambda r: r[0], reverse=True)

        result = message
        for start, end, emote_id in replacements:
            # The emote CDN URL — use animated variant if available,
            # otherwise static.  Both work; Twitch serves the right one.
            img_url = (
                f"https://static-cdn.jtvnw.net/emoticons/v2"
                f"/{emote_id}/default/dark/2.0"
            )
            alt_text = html.escape(message[start:end + 1])
            img_tag = (
                f'<img src="{img_url}" '
                f'alt="{alt_text}" '
                f'height="28" '
                f'style="vertical-align:middle;">'
            )
            result = result[:start] + img_tag + result[end + 1:]

        # Escape any remaining plain text (but NOT our <img> tags).
        # Strategy: split on <img ...>, escape the text parts, rejoin.
        segments = result.split("<img ")
        escaped_parts = []
        for i, seg in enumerate(segments):
            if i == 0:
                escaped_parts.append(html.escape(seg))
            else:
                # Re-add the "<img " prefix we stripped during split.
                escaped_parts.append("<img " + seg)
        return "".join(escaped_parts)

    def _replace_third_party_emotes(self, text_html):
        """Replace known third-party emote codes with ``<img>`` tags.

        This operates on *already-HTML-escaped* text.  Emote codes are
        matched as whole words (space / punctuation boundaries) against
        the ``_emote_resolver`` cache.  Replacements are done from
        right to left so that earlier character indices stay valid.
        """
        if self._emote_resolver is None:
            return text_html

        # Build a list of (start, end, url) for every match.
        import re
        replacements = []
        for match in re.finditer(r'(\S+)', text_html):
            code = match.group(1)
            url = self._emote_resolver.resolve(code)
            if url:
                replacements.append((match.start(), match.end(), url))

        if not replacements:
            return text_html

        # Replace right-to-left.
        replacements.sort(key=lambda r: r[0], reverse=True)
        result = text_html
        for start, end, url in replacements:
            alt = html.escape(text_html[start:end])
            img = (
                f'<img src="{url}" '
                f'alt="{alt}" '
                f'height="28" '
                f'style="vertical-align:middle;">'
            )
            result = result[:start] + img + result[end:]
        return result

    # ---- Avatar helpers -------------------------------------------

    def _get_avatar_html(self, username):
        """Return an ``<img>`` tag for *username*'s avatar, or ``""``
        if not yet cached.  Avatars are fetched asynchronously in the
        background; once fetched the cache is populated and subsequent
        messages will include the avatar immediately."""
        url = self._avatar_cache.get(username)
        if url is None:
            # Not fetched yet — kick off a background fetch.
            self._avatar_cache[username] = ""  # sentinel: "fetching"
            threading.Thread(
                target=self._fetch_avatar,
                args=(username,),
                daemon=True,
            ).start()
            return ""
        if not url:
            return ""  # fetch in progress or failed
        return (
            f'<img src="{url}" '
            f'height="22" '
            f'style="vertical-align:middle; border-radius:4px; margin-right:3px;">'
        )

    def _fetch_avatar(self, username):
        """Fetch a user's profile image from Twitch (blocking).
        Runs in a background thread.  Downloads the image to a temp
        file and caches the local file path so QTextBrowser can render it."""
        try:
            client_id = self._get_client_id()
            app_token = self._get_app_token()
            if not client_id or not app_token:
                debug(f"[CHAT] Cannot fetch avatar for {username}: missing credentials")
                self._avatar_cache[username] = ""
                return
            resp = requests.get(
                f"https://api.twitch.tv/helix/users?login={username}",
                headers={"Client-Id": client_id,
                          "Authorization": f"Bearer {app_token}"},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                if data:
                    img_url = data[0].get("profile_image_url", "")
                    if img_url:
                        img_resp = requests.get(img_url, timeout=5)
                        if img_resp.status_code == 200:
                            # Save to a local temp file for QTextBrowser.
                            import os
                            import tempfile
                            avatar_dir = os.path.join(
                                tempfile.gettempdir(), "twitcher_avatars"
                            )
                            os.makedirs(avatar_dir, exist_ok=True)
                            safe_name = "".join(
                                c if c.isalnum() else "_" for c in username
                            )
                            path = os.path.join(avatar_dir, f"{safe_name}.png")
                            with open(path, "wb") as f:
                                f.write(img_resp.content)
                            # Use file:/// URL for QTextBrowser compatibility.
                            file_url = "file:///" + path.replace("\\", "/")
                            self._avatar_cache[username] = file_url
                            debug(f"[CHAT] Avatar cached for {username} → {file_url}")
                            return
            debug(f"[CHAT] Avatar fetch for {username} returned HTTP {resp.status_code}")
            self._avatar_cache[username] = ""
        except Exception as exc:
            debug(f"[CHAT] Avatar fetch error for {username}: {exc}")
            self._avatar_cache[username] = ""

    def _get_client_id(self):
        """Return the Twitch Client-ID from the environment (same source as the API layer)."""
        try:
            from twitch_api.client import TWITCH_CLIENT_ID
            return TWITCH_CLIENT_ID
        except Exception:
            return ""

    def _get_app_token(self):
        """Return an App Access Token for Helix API calls.
        The user's OAuth token doesn't have the right scopes for
        lookups like /helix/users."""
        try:
            from twitch_api.client import TwitchAPIClient
            # Reuse the API layer's cached app token if available.
            from twitch_api.client import TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET
            import time as _time
            if not hasattr(self, '_app_token') or not self._app_token:
                resp = requests.post(
                    "https://id.twitch.tv/oauth2/token",
                    data={
                        "client_id": TWITCH_CLIENT_ID,
                        "client_secret": TWITCH_CLIENT_SECRET,
                        "grant_type": "client_credentials",
                    },
                    timeout=5,
                )
                if resp.status_code == 200:
                    self._app_token = resp.json().get("access_token", "")
            return getattr(self, '_app_token', '')
        except Exception:
            return ""

    # ---- Badge helpers --------------------------------------------

    def _get_badges_html(self, tags):
        """Return HTML ``<img>`` tags for the user's chat badges."""
        raw = (tags or {}).get("badges", "")
        if not raw:
            return ""
        parts = []
        for badge_entry in raw.split(","):
            badge_type, _, version = badge_entry.partition("/")
            key = f"{badge_type}/{version}"
            url = self._badge_cache.get(key)
            if url:
                parts.append(
                    f'<img src="{url}" height="16" '
                    f'style="vertical-align:middle; margin-right:2px;">'
                )
        return "".join(parts)

    def fetch_channel_badges(self, broadcaster_id):
        """Fetch the channel's badge set from the Helix API (blocking).
        Call this from a background thread after connecting."""
        if not broadcaster_id:
            return
        try:
            client_id = self._get_client_id()
            app_token = self._get_app_token()
            if not client_id or not app_token:
                return
            resp = requests.get(
                "https://api.twitch.tv/helix/chat/badges",
                params={"broadcaster_id": broadcaster_id},
                headers={"Client-Id": client_id,
                          "Authorization": f"Bearer {app_token}"},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                for badge in data:
                    badge_type = badge.get("set_id", "")
                    for img in badge.get("images", []):
                        ver = img.get("id", "")
                        url = img.get("dark_theme_1x", "") or img.get("image_url_1x", "")
                        if url:
                            self._badge_cache[f"{badge_type}/{ver}"] = url
                debug(f"[CHAT] Loaded {len(self._badge_cache)} badge images")
        except Exception as exc:
            debug(f"[CHAT] Badge fetch error: {exc}")

    # ---- Display message ------------------------------------------

    def display_message(

        self,

        username,

        channel,

        message,

        tags

    ):

        from PySide6.QtGui import QTextCursor, QTextCharFormat, QTextImageFormat

        safe_username = html.escape(

            username

        )


        # --- Per-user colour ---
        user_color = self._resolve_user_color(tags, username)


        debug(f"Displaying chat message from {username}: {message}")


        # Build the message using QTextCursor for reliable image embedding.
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)


        # --- Avatar (22x22) ---
        avatar_url = self._avatar_cache.get(username)
        if avatar_url and avatar_url.startswith("file:///"):
            local_path = avatar_url.replace("file:///", "").replace("/", "\\")
            avatar_fmt = QTextImageFormat()
            avatar_fmt.setWidth(22)
            avatar_fmt.setHeight(22)
            avatar_fmt.setName(avatar_url)
            # Register the image resource so QTextDocument can find it.
            from PySide6.QtCore import QUrl, QVariant
            from PySide6.QtGui import QPixmap
            pixmap = QPixmap(local_path)
            if not pixmap.isNull():
                self.chat_display.document().addResource(
                    1,  # QTextDocument.ImageResource
                    QUrl(avatar_url),
                    pixmap,
                )
                cursor.insertImage(avatar_fmt)
                # Add a small space after avatar.
                char_fmt = QTextCharFormat()
                char_fmt.setProperty(5, " ")  # Add a space.
                cursor.insertText(" ", char_fmt)


        # --- Badges ---
        raw_badges = (tags or {}).get("badges", "")
        if raw_badges:
            for badge_entry in raw_badges.split(","):
                badge_type, _, version = badge_entry.partition("/")
                badge_url = self._badge_cache.get(f"{badge_type}/{version}", "")
                if badge_url:
                    local_badge = self._ensure_local_image(badge_url)
                    if local_badge:
                        badge_fmt = QTextImageFormat()
                        badge_fmt.setWidth(16)
                        badge_fmt.setHeight(16)
                        badge_fmt.setName(local_badge)
                        cursor.insertImage(badge_fmt)


        # --- Username (colored + bold) ---
        user_fmt = QTextCharFormat()
        user_fmt.setForeground(
            self.chat_display.palette().color(
                self.chat_display.foregroundRole()
            )
        )
        from PySide6.QtGui import QColor
        user_fmt.setForeground(QColor(user_color))
        font = user_fmt.font()
        font.setBold(True)
        user_fmt.setFont(font)
        cursor.insertText(f"{safe_username}", user_fmt)


        # --- ": " separator ---
        sep_fmt = QTextCharFormat()
        cursor.insertText(": ", sep_fmt)


        # --- Message text (with emote images embedded) ---
        self._insert_message_with_emotes(cursor, message, tags)


        # --- Reply link ---
        reply_fmt = QTextCharFormat()
        reply_fmt.setForeground(QColor("#66b2ff"))
        cursor.insertText(" ", reply_fmt)


        # Add a newline to end the message.
        cursor.insertBlock()


        # Auto-scroll to bottom.
        sb = self.chat_display.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ---- Shared image cache (avatars, badges, emotes) ----

    def _ensure_local_image(self, url):
        """Download *url* to a temp file if not already cached.
        Returns a ``file:///`` URL suitable for QTextImageFormat."""
        if not url:
            return ""
        # Already a local file URL?
        if url.startswith("file:///"):
            return url
        # Check our temp-file cache.
        cache = getattr(self, "_img_file_cache", None)
        if cache is None:
            cache = {}
            self._img_file_cache = cache
        local = cache.get(url)
        if local:
            return local
        # Download to temp file.
        try:
            import os, tempfile
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                return ""
            ext = ".png"
            ct = resp.headers.get("content-type", "")
            if "gif" in ct:
                ext = ".gif"
            elif "jpeg" in ct or "jpg" in ct:
                ext = ".jpg"
            d = os.path.join(tempfile.gettempdir(), "twitcher_images")
            os.makedirs(d, exist_ok=True)
            # Use a hash of the URL as filename.
            import hashlib
            name = hashlib.md5(url.encode()).hexdigest() + ext
            path = os.path.join(d, name)
            if not os.path.exists(path):
                with open(path, "wb") as f:
                    f.write(resp.content)
            file_url = "file:///" + path.replace("\\", "/")
            cache[url] = file_url
            return file_url
        except Exception:
            return ""

    def _insert_message_with_emotes(self, cursor, message, tags):
        """Insert message text, replacing Twitch emotes with inline images."""
        from PySide6.QtGui import QTextImageFormat

        raw_emotes = (tags or {}).get("emotes", "")

        if not raw_emotes:
            cursor.insertText(html.escape(message))
            return

        # Parse emote positions.
        replacements = []
        for group in raw_emotes.split("/"):
            parts = group.split(":")
            if len(parts) != 2:
                continue
            emote_id = parts[0]
            for span in parts[1].split(","):
                pos = span.split("-")
                if len(pos) != 2:
                    continue
                start, end = int(pos[0]), int(pos[1])
                replacements.append((start, end, emote_id))

        replacements.sort(key=lambda r: r[0])

        last_end = 0
        for start, end, emote_id in replacements:
            if start > last_end:
                cursor.insertText(html.escape(message[last_end:start]))

            # Download emote image to temp file for reliable rendering.
            cdn_url = (
                f"https://static-cdn.jtvnw.net/emoticons/v2"
                f"/{emote_id}/default/dark/2.0"
            )
            local_url = self._ensure_local_image(cdn_url)
            if local_url:
                emote_fmt = QTextImageFormat()
                emote_fmt.setWidth(28)
                emote_fmt.setHeight(28)
                emote_fmt.setName(local_url)
                cursor.insertImage(emote_fmt)
            else:
                # Fallback: show emote text.
                cursor.insertText(html.escape(message[start:end + 1]))

            last_end = end + 1

        if last_end < len(message):
            cursor.insertText(html.escape(message[last_end:]))


    def show_chat_context_menu(

        self,

        point

    ):

        cursor = self.chat_display.cursorForPosition(

            point

        )

        username = self.get_username_from_cursor(

            cursor

        )

        menu = self.chat_display.createStandardContextMenu()

        if username:

            reply_action = QAction(

                f"Reply to {username}",

                self

            )

            reply_action.triggered.connect(

                lambda checked=False, u=username: self.reply_to_username(

                    u

                )

            )

            if menu.actions():

                menu.insertAction(

                    menu.actions()[0],

                    reply_action

                )

            else:

                menu.addAction(

                    reply_action

                )

        menu.exec(

            self.chat_display.mapToGlobal(

                point

            )

        )


    def get_username_from_cursor(

        self,

        cursor

    ):

        block_text = cursor.block().text().strip()

        if not block_text or block_text.startswith(

            "[SYSTEM]"

        ):

            return None


        if ":" not in block_text:

            return None


        username = block_text.split(":", 1)[0].strip()

        return username or None


    def reply_to_username(

        self,

        username

    ):

        if not username:

            return


        prefix = f"@{username} "

        current_text = self.message_input.text()

        if current_text.startswith(

            prefix

        ):

            self.message_input.setFocus()

            self.message_input.setCursorPosition(

                len(prefix)

            )

            return


        self.message_input.setText(

            prefix + current_text

        )

        self.message_input.setFocus()

        self.message_input.setCursorPosition(

            len(prefix)

        )


    def on_chat_anchor_clicked(

        self,

        url

    ):

        url_text = url.toString()

        debug(f"Chat anchor clicked: {url_text}")

        if url_text.startswith(

            "reply:"

        ):

            username = html.unescape(

                url_text.split(

                    ":",

                    1

                )[1]

            )

            debug(f"Replying to username: {username}")

            self.reply_to_username(

                username

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


        message = transliterate_to_russian(message)
        self.message_input.setText(message)


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


    # ========================================================
    #                    EMOJI PICKER
    # ========================================================

    def _toggle_emoji_picker(self):
        """Show or hide the emoji picker popup near the emoji button."""
        if hasattr(self, '_emoji_popup') and self._emoji_popup is not None:
            self._emoji_popup.close()
            self._emoji_popup = None
            return
        from PySide6.QtWidgets import QWidget, QGridLayout, QPushButton
        from PySide6.QtCore import Qt
        popup = QWidget(self, Qt.Popup)
        popup.setStyleSheet(
            "background-color: #1a1e2e; border: 1px solid #3c456b;"
            "border-radius: 6px; padding: 6px;"
        )
        grid = QGridLayout(popup)
        grid.setSpacing(2)
        emoji_sets = [
            list(range(0x1F600, 0x1F64F+1)),
            list(range(0x1F300, 0x1F5FF+1)),
            list(range(0x1F680, 0x1F6FF+1)),
            list(range(0x2600, 0x26FF+1)),
            list(range(0x2700, 0x27BF+1)),
        ]
        all_emoji = []
        for s in emoji_sets:
            all_emoji.extend(s)
        cols = 10
        for i, code in enumerate(all_emoji[:80]):
            em = chr(code)
            btn = QPushButton(em)
            btn.setFixedSize(32, 32)
            btn.setStyleSheet(
                "font-size: 18px; border: none; background: transparent;"
            )
            btn.clicked.connect(
                lambda checked=False, e=em: self._insert_emoji(e)
            )
            grid.addWidget(btn, i // cols, i % cols)
        self._emoji_popup = popup
        btn_pos = self.emoji_button.mapToGlobal(
            self.emoji_button.rect().bottomLeft()
        )
        popup.move(btn_pos)
        popup.show()

    def _insert_emoji(self, emoji):
        """Insert an emoji character at the cursor position."""
        self.message_input.insert(emoji)
        self.message_input.setFocus()
        if hasattr(self, '_emoji_popup') and self._emoji_popup is not None:
            self._emoji_popup.close()
            self._emoji_popup = None

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


        debug("")

        debug(

            "[IRC AUTH FAILURE]"

        )

        debug(

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