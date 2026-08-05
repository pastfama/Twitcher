import os
import subprocess

import requests
from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_FILE)

TWITCH_API = "https://api.twitch.tv/helix"
TWITCH_OAUTH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_CLIENT_ID = (os.getenv("TWITCH_CLIENT_ID", "") or "").strip()
TWITCH_CLIENT_SECRET = (os.getenv("TWITCH_CLIENT_SECRET", "") or "").strip()
STREAMLINK_PATH = r"C:\Program Files\Streamlink\bin\streamlink.exe"


class TwitchAPIError(RuntimeError):
    """Raised when a Twitch API call fails."""


class TwitchAPIBase:
    def __init__(self, access_token=None):
        self.validate_configuration()
        # Use pre-validated token if provided (avoids double validation)
        if access_token:
            self.access_token = access_token
        else:
            from twitch_token_manager import get_valid_token
            self.access_token = get_valid_token()
        if not self.access_token:
            raise RuntimeError("Could not obtain a valid Twitch user access token.")
        self.headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        self.app_access_token = self.get_app_access_token()

    @staticmethod
    def normalize_channel(channel):
        return str(channel).strip().lower().lstrip("#")

    def validate_configuration(self):
        if not TWITCH_CLIENT_ID:
            raise RuntimeError(f"TWITCH_CLIENT_ID is missing from {ENV_FILE}")
        if not TWITCH_CLIENT_SECRET:
            raise RuntimeError(f"TWITCH_CLIENT_SECRET is missing from {ENV_FILE}")

    def get(self, endpoint, params=None):
        response = requests.get(
            f"{TWITCH_API}{endpoint}",
            headers=self.headers,
            params=params,
            timeout=20,
        )
        if response.status_code == 401:
            raise TwitchAPIError("Twitch user OAuth token is invalid or expired.\n\n" f"{response.text}")
        if response.status_code != 200:
            raise TwitchAPIError(f"Twitch API error {response.status_code}:\n{response.text}")
        return response.json()

    def post(self, endpoint, json_data=None, headers=None):
        request_headers = headers if headers is not None else self.headers
        response = requests.post(
            f"{TWITCH_API}{endpoint}",
            headers=request_headers,
            json=json_data,
            timeout=20,
        )
        if response.status_code == 401:
            raise TwitchAPIError("Twitch OAuth token is invalid or expired.\n\n" f"{response.text}")
        if response.status_code not in (200, 202):
            raise TwitchAPIError(f"Twitch API POST error {response.status_code}:\n{response.text}")
        if response.text:
            return response.json()
        return {}

    def get_stream_url(self, channel):
        if not os.path.exists(STREAMLINK_PATH):
            raise RuntimeError(f"Streamlink was not found.\n\nExpected:\n{STREAMLINK_PATH}")
        channel = self.normalize_channel(channel)
        result = subprocess.run(
            [STREAMLINK_PATH, f"twitch.tv/{channel}", "best", "--stream-url"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Streamlink could not resolve the stream.\n\n{result.stderr}")
        url = result.stdout.strip()
        if not url:
            raise RuntimeError("Streamlink returned an empty URL.")
        return url
