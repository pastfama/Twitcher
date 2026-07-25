import http.server
import json
import os
import secrets
import threading
import urllib.parse
import webbrowser

import requests
from dotenv import load_dotenv


# ============================================================
#                    PATH CONFIGURATION
# ============================================================


BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


ENV_FILE = os.path.join(
    BASE_DIR,
    ".env"
)


TOKEN_FILE = os.path.join(
    BASE_DIR,
    "twitch_token.json"
)


# ============================================================
#                    LOAD ENVIRONMENT
# ============================================================


load_dotenv(
    ENV_FILE
)


# ============================================================
#                    TWITCH CONFIGURATION
# ============================================================


CLIENT_ID = os.getenv(
    "TWITCH_CLIENT_ID"
)


CLIENT_SECRET = os.getenv(
    "TWITCH_CLIENT_SECRET"
)


REDIRECT_URI = os.getenv(
    "TWITCH_REDIRECT_URI"
)


PORT = 3000


# ============================================================
#                    REQUIRED SCOPES
# ============================================================


SCOPES = [

    "user:read:follows",

    "user:read:email",

    "chat:read",

    "chat:edit",

    "channel:read:subscriptions",

    "channel:read:redemptions",

    "channel:manage:redemptions",

    "moderation:read",

    "moderation:manage",

    "bits:read",

]


# ============================================================
#                    AUTH STATE
# ============================================================


authorization_code = None


expected_state = None


callback_event = threading.Event()


# ============================================================
#                    CALLBACK SERVER
# ============================================================


class TwitchCallbackHandler(

    http.server.BaseHTTPRequestHandler

):


    def do_GET(

        self

    ):

        global authorization_code


        parsed_url = urllib.parse.urlparse(

            self.path

        )


        accepted_paths = (

            "",

            "/",

            "/callback",

            "/callback/"

        )


        if parsed_url.path not in accepted_paths:

            self.send_response(

                404

            )

            self.end_headers()


            self.wfile.write(

                b"Twitch callback not found."

            )


            return


        query = urllib.parse.parse_qs(

            parsed_url.query

        )


        # ----------------------------------------------------
        # OAUTH ERROR
        # ----------------------------------------------------


        error = query.get(

            "error",

            [None]

        )[0]


        if error:

            description = query.get(

                "error_description",

                ["Unknown error"]

            )[0]


            print()


            print(

                "[AUTH ERROR]"

            )


            print(

                f"{error}: "

                f"{description}"

            )


            self.send_response(

                400

            )


            self.send_header(

                "Content-Type",

                "text/html; charset=utf-8"

            )


            self.end_headers()


            self.wfile.write(

                b"Twitch authorization failed."

            )


            callback_event.set()


            return


        # ----------------------------------------------------
        # AUTHORIZATION CODE
        # ----------------------------------------------------


        authorization_code = query.get(

            "code",

            [None]

        )[0]


        received_state = query.get(

            "state",

            [None]

        )[0]


        if not authorization_code:

            print()


            print(

                "[AUTH ERROR]"

            )


            print(

                "No authorization code received."

            )


            self.send_response(

                400

            )


            self.end_headers()


            self.wfile.write(

                b"No authorization code received."

            )


            callback_event.set()


            return


        # ----------------------------------------------------
        # STATE VALIDATION
        # ----------------------------------------------------


        if received_state != expected_state:

            print()


            print(

                "[AUTH ERROR]"

            )


            print(

                "OAuth state validation failed."

            )


            self.send_response(

                400

            )


            self.end_headers()


            self.wfile.write(

                b"Invalid OAuth state."

            )


            callback_event.set()


            return


        # ----------------------------------------------------
        # SUCCESS RESPONSE
        # ----------------------------------------------------


        self.send_response(

            200

        )


        self.send_header(

            "Content-Type",

            "text/html; charset=utf-8"

        )


        self.end_headers()


        html = """

        <!DOCTYPE html>

        <html>

        <head>

            <title>Twitch Authentication</title>

        </head>

        <body style="

            background: #0e0e10;

            color: white;

            font-family: Arial;

            text-align: center;

            padding-top: 100px;

        ">

            <h1>

                Twitch Authentication Successful

            </h1>

            <p>

                You can close this browser window.

            </p>

        </body>

        </html>

        """


        self.wfile.write(

            html.encode(

                "utf-8"

            )

        )


        print()


        print(

            "[AUTH] Callback received successfully."

        )


        callback_event.set()


    def log_message(

        self,

        format,

        *args

    ):

        return


# ============================================================
#                    EXCHANGE CODE
# ============================================================


def exchange_code_for_token(

    code

):


    print()


    print(

        "[AUTH] Exchanging authorization code..."

    )


    response = requests.post(

        "https://id.twitch.tv/oauth2/token",

        params={

            "client_id":

            CLIENT_ID,


            "client_secret":

            CLIENT_SECRET,


            "code":

            code,


            "grant_type":

            "authorization_code",


            "redirect_uri":

            REDIRECT_URI,

        },


        timeout=30

    )


    if response.status_code != 200:

        raise RuntimeError(

            "Token exchange failed:\n\n"

            f"HTTP {response.status_code}\n\n"

            f"{response.text}"

        )


    token_data = response.json()


    with open(

        TOKEN_FILE,

        "w",

        encoding="utf-8"

    ) as file:

        json.dump(

            token_data,

            file,

            indent=4

        )


    print()


    print(

        "[AUTH] Twitch authentication successful."

    )


    print()


    print(

        "[AUTH] Token scopes received:"

    )


    for scope in token_data.get(

        "scope",

        []

    ):

        print(

            f"          {scope}"

        )


    print()


    print(

        "[AUTH] Token saved to:"

    )


    print(

        TOKEN_FILE

    )


    return token_data


# ============================================================
#                    AUTHENTICATE
# ============================================================


def authenticate():


    global expected_state


    global authorization_code


    callback_event.clear()


    authorization_code = None


    expected_state = secrets.token_urlsafe(

        32

    )


    # --------------------------------------------------------
    # VALIDATE CONFIGURATION
    # --------------------------------------------------------


    if not CLIENT_ID:

        raise RuntimeError(

            "TWITCH_CLIENT_ID is missing from .env."

        )


    if not CLIENT_SECRET:

        raise RuntimeError(

            "TWITCH_CLIENT_SECRET is missing from .env."

        )


    if not REDIRECT_URI:

        raise RuntimeError(

            "TWITCH_REDIRECT_URI is missing from .env."

        )


    # --------------------------------------------------------
    # START CALLBACK SERVER
    # --------------------------------------------------------


    print()


    print(

        "[AUTH] Starting local callback server..."

    )


    server = http.server.HTTPServer(

        (

            "127.0.0.1",

            PORT

        ),

        TwitchCallbackHandler

    )


    thread = threading.Thread(

        target=server.serve_forever,

        daemon=True

    )


    thread.start()


    # --------------------------------------------------------
    # OAUTH PARAMETERS
    # --------------------------------------------------------


    params = {

        "response_type":

        "code",


        "client_id":

        CLIENT_ID,


        "redirect_uri":

        REDIRECT_URI,


        "scope":

        " ".join(

            SCOPES

        ),


        "state":

        expected_state,

        "force_verify":

        "true",

    }


    authorization_url = (

        "https://id.twitch.tv/oauth2/authorize?"

        +

        urllib.parse.urlencode(

            params

        )

    )


    # --------------------------------------------------------
    # OPEN BROWSER
    # --------------------------------------------------------


    print()


    print(

        "[AUTH] Requested scopes:"

    )


    for scope in SCOPES:

        print(

            f"          {scope}"

        )


    print()


    print(

        "[AUTH] Opening Twitch authorization page..."

    )


    webbrowser.open(

        authorization_url

    )


    print()


    print(

        "[AUTH] Waiting for authorization..."

    )


    callback_received = callback_event.wait(

        timeout=300

    )


    # --------------------------------------------------------
    # SHUTDOWN CALLBACK SERVER
    # --------------------------------------------------------


    server.shutdown()


    server.server_close()


    if not callback_received:

        raise RuntimeError(

            "Twitch authorization timed out."

        )


    if not authorization_code:

        raise RuntimeError(

            "No Twitch authorization code received."

        )


    return exchange_code_for_token(

        authorization_code

    )


# ============================================================
#                    MAIN
# ============================================================


def main():


    print()


    print(

        "=========================================="

    )


    print(

        "       TWITCH AUTHENTICATION"

    )


    print(

        "=========================================="

    )


    print()


    try:

        authenticate()


    except Exception as error:

        print()


        print(

            "[AUTH ERROR]"

        )


        print(

            error

        )


        input(

            "\nPress Enter to exit..."

        )


# ============================================================
#                    ENTRY POINT
# ============================================================


if __name__ == "__main__":

    main()