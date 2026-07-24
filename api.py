import os
import subprocess

import requests
from dotenv import load_dotenv

from twitch_token_manager import get_valid_token


# ============================================================
#                    PATHS
# ============================================================


BASE_DIR = os.path.dirname(
    os.path.abspath(
        __file__
    )
)


ENV_FILE = os.path.join(
    BASE_DIR,
    ".env"
)


# ============================================================
#                    LOAD ENVIRONMENT
# ============================================================


load_dotenv(
    ENV_FILE
)


# ============================================================
#                    CONFIGURATION
# ============================================================


TWITCH_API = (
    "https://api.twitch.tv/helix"
)


TWITCH_OAUTH_TOKEN_URL = (
    "https://id.twitch.tv/oauth2/token"
)


TWITCH_CLIENT_ID = (

    os.getenv(

        "TWITCH_CLIENT_ID",

        ""

    )

    or ""

).strip()


TWITCH_CLIENT_SECRET = (

    os.getenv(

        "TWITCH_CLIENT_SECRET",

        ""

    )

    or ""

).strip()


STREAMLINK_PATH = (

    r"C:\Program Files\Streamlink"

    r"\bin\streamlink.exe"

)


# ============================================================
#                    TWITCH API
# ============================================================


class TwitchAPI:


    # ========================================================
    #                    INITIALIZATION
    # ========================================================


    def __init__(

        self

    ):

        print()

        print(

            "[TWITCH] Initializing Twitch API..."

        )


        self.validate_configuration()


        # ----------------------------------------------------
        # GET VALID USER TOKEN
        #
        # This automatically:
        #
        # 1. Loads twitch_token.json
        # 2. Validates the access token
        # 3. Refreshes it if expired
        # 4. Saves the new token
        # ----------------------------------------------------

        self.access_token = (

            get_valid_token()

        )


        if not self.access_token:

            raise RuntimeError(

                "Could not obtain a valid Twitch user access token."

            )


        self.headers = {

            "Client-ID":

            TWITCH_CLIENT_ID,

            "Authorization":

            f"Bearer {self.access_token}",

            "Content-Type":

            "application/json",

        }


        print()

        print(

            "[TWITCH] Valid user access token loaded."

        )


        # ----------------------------------------------------
        # APP ACCESS TOKEN
        # ----------------------------------------------------

        self.app_access_token = (

            self.get_app_access_token()

        )


        print()

        print(

            "[TWITCH] App access token obtained."

        )


    # ========================================================
    #                    CONFIGURATION
    # ========================================================


    def validate_configuration(

        self

    ):


        if not TWITCH_CLIENT_ID:

            raise RuntimeError(

                "TWITCH_CLIENT_ID is missing "

                f"from {ENV_FILE}"

            )


        if not TWITCH_CLIENT_SECRET:

            raise RuntimeError(

                "TWITCH_CLIENT_SECRET is missing "

                f"from {ENV_FILE}"

            )


    # ========================================================
    #                    APP ACCESS TOKEN
    # ========================================================


    def get_app_access_token(

        self

    ):


        response = requests.post(

            TWITCH_OAUTH_TOKEN_URL,

            params={

                "client_id":

                TWITCH_CLIENT_ID,

                "client_secret":

                TWITCH_CLIENT_SECRET,

                "grant_type":

                "client_credentials",

            },

            timeout=20,

        )


        if response.status_code != 200:

            raise RuntimeError(

                "Could not obtain Twitch app access token.\n\n"

                f"HTTP {response.status_code}\n"

                f"{response.text}"

            )


        data = response.json()


        token = (

            data.get(

                "access_token",

                ""

            )

            or ""

        ).strip()


        if not token:

            raise RuntimeError(

                "Twitch did not return an app access token."

            )


        return token


    # ========================================================
    #                    NORMALIZE CHANNEL
    # ========================================================


    @staticmethod

    def normalize_channel(

        channel

    ):


        return (

            str(

                channel

            )

            .strip()

            .lower()

            .lstrip("#")

        )


    # ========================================================
    #                    GENERIC GET
    # ========================================================


    def get(

        self,

        endpoint,

        params=None

    ):


        response = requests.get(

            f"{TWITCH_API}{endpoint}",

            headers=self.headers,

            params=params,

            timeout=20,

        )


        if response.status_code == 401:

            raise RuntimeError(

                "Twitch user OAuth token is invalid "

                "or expired.\n\n"

                f"{response.text}"

            )


        if response.status_code != 200:

            raise RuntimeError(

                f"Twitch API error "

                f"{response.status_code}:\n"

                f"{response.text}"

            )


        return response.json()


    # ========================================================
    #                    GENERIC POST
    # ========================================================


    def post(

        self,

        endpoint,

        json_data=None,

        headers=None

    ):


        request_headers = (

            headers

            if headers is not None

            else self.headers

        )


        response = requests.post(

            f"{TWITCH_API}{endpoint}",

            headers=request_headers,

            json=json_data,

            timeout=20,

        )


        if response.status_code == 401:

            raise RuntimeError(

                "Twitch OAuth token is invalid "

                "or expired.\n\n"

                f"{response.text}"

            )


        if response.status_code not in (

            200,

            202

        ):

            raise RuntimeError(

                f"Twitch API POST error "

                f"{response.status_code}:\n"

                f"{response.text}"

            )


        if response.text:

            return response.json()


        return {}


    # ========================================================
    #                    CURRENT USER
    # ========================================================


    def get_current_user(

        self

    ):


        data = self.get(

            "/users"

        )


        users = data.get(

            "data",

            []

        )


        if not users:

            raise RuntimeError(

                "Could not identify Twitch user."

            )


        user = users[0]


        print()

        print(

            "[TWITCH] Logged in as "

            f"{user.get('display_name')}"

        )


        return user


    # ========================================================
    #                    GET USER
    # ========================================================


    def get_user(

        self,

        login

    ):


        login = self.normalize_channel(

            login

        )


        data = self.get(

            "/users",

            params={

                "login":

                login

            }

        )


        users = data.get(

            "data",

            []

        )


        if not users:

            raise RuntimeError(

                f"Twitch user not found: "

                f"{login}"

            )


        return users[0]


    # ========================================================
    #                    FOLLOWED CHANNELS
    # ========================================================


    def get_followed_channels(

        self,

        user_id

    ):


        channels = []


        cursor = None


        while True:


            params = {

                "user_id":

                str(

                    user_id

                ),

                "first":

                100,

            }


            if cursor:

                params["after"] = cursor


            data = self.get(

                "/channels/followed",

                params

            )


            channels.extend(

                data.get(

                    "data",

                    []

                )

            )


            cursor = (

                data.get(

                    "pagination",

                    {}

                )

                .get(

                    "cursor"

                )

            )


            if not cursor:

                break


        return channels


    # ========================================================
    #                    LIVE STREAMS
    # ========================================================


    def get_live_streams(

        self,

        followed_channels

    ):


        live_streams = []


        for start in range(

            0,

            len(

                followed_channels

            ),

            100

        ):


            batch = followed_channels[

                start:start + 100

            ]


            params = []


            for channel in batch:


                broadcaster_id = (

                    channel.get(

                        "broadcaster_id"

                    )

                    or

                    channel.get(

                        "broadcaster_user_id"

                    )

                )


                if broadcaster_id:

                    params.append(

                        (

                            "user_id",

                            broadcaster_id

                        )

                    )


            if not params:

                continue


            response = requests.get(

                f"{TWITCH_API}/streams",

                headers=self.headers,

                params=params,

                timeout=20,

            )


            if response.status_code != 200:

                raise RuntimeError(

                    "Could not retrieve live streams:\n"

                    f"HTTP {response.status_code}\n"

                    f"{response.text}"

                )


            data = response.json()


            live_streams.extend(

                data.get(

                    "data",

                    []

                )

            )


        return live_streams


    # ========================================================
    #                    STREAM URL
    # ========================================================


    def get_stream_url(

        self,

        channel

    ):


        if not os.path.exists(

            STREAMLINK_PATH

        ):

            raise RuntimeError(

                "Streamlink was not found.\n\n"

                f"Expected:\n{STREAMLINK_PATH}"

            )


        channel = self.normalize_channel(

            channel

        )


        command = [

            STREAMLINK_PATH,

            f"twitch.tv/{channel}",

            "best",

            "--stream-url",

        ]


        result = subprocess.run(

            command,

            capture_output=True,

            text=True,

            timeout=60,

        )


        if result.returncode != 0:

            raise RuntimeError(

                "Streamlink could not resolve "

                "the stream.\n\n"

                f"{result.stderr}"

            )


        url = result.stdout.strip()


        if not url:

            raise RuntimeError(

                "Streamlink returned an empty URL."

            )


        return url


    # ========================================================
    #                    EVENTSUB HEADERS
    # ========================================================


    def get_eventsub_user_headers(

        self

    ):


        return {

            "Client-ID":

            TWITCH_CLIENT_ID,

            "Authorization":

            f"Bearer {self.access_token}",

            "Content-Type":

            "application/json",

        }


    # ========================================================
    #                    EVENTSUB RAID
    # ========================================================


    def subscribe_to_raid(

        self,

        broadcaster_user_id,

        session_id,

        direction="to"

    ):


        broadcaster_user_id = str(

            broadcaster_user_id

        )


        if direction == "from":

            condition = {

                "from_broadcaster_user_id":

                broadcaster_user_id

            }


        else:

            condition = {

                "to_broadcaster_user_id":

                broadcaster_user_id

            }


        payload = {

            "type":

            "channel.raid",

            "version":

            "1",

            "condition":

            condition,

            "transport":

            {

                "method":

                "websocket",

                "session_id":

                session_id

            }

        }


        response = requests.post(

            f"{TWITCH_API}/eventsub/subscriptions",

            headers=(

                self.get_eventsub_user_headers()

            ),

            json=payload,

            timeout=20,

        )


        if response.status_code not in (

            200,

            202

        ):

            raise RuntimeError(

                "Twitch raid subscription failed:\n"

                f"HTTP {response.status_code}\n"

                f"{response.text}"

            )


        print()

        print(

            "[TWITCH] Raid EventSub subscription "

            "created successfully."

        )


        return response.json()


    # ========================================================
    #                    EVENTSUB STREAM ONLINE
    # ========================================================


    def subscribe_to_stream(

        self,

        broadcaster_user_id,

        session_id

    ):


        payload = {

            "type":

            "stream.online",

            "version":

            "1",

            "condition":

            {

                "broadcaster_user_id":

                str(

                    broadcaster_user_id

                )

            },

            "transport":

            {

                "method":

                "websocket",

                "session_id":

                session_id

            }

        }


        response = requests.post(

            f"{TWITCH_API}/eventsub/subscriptions",

            headers=(

                self.get_eventsub_user_headers()

            ),

            json=payload,

            timeout=20,

        )


        if response.status_code not in (

            200,

            202

        ):

            raise RuntimeError(

                "Twitch stream subscription failed:\n"

                f"HTTP {response.status_code}\n"

                f"{response.text}"

            )


        return response.json()