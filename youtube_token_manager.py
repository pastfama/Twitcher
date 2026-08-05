"""YouTube Token Manager — manages YouTube API credentials.

YouTube uses Google OAuth 2.0:
- API Key: For public data (no user auth needed)
- OAuth: For user-specific actions (subscriptions, chat)
- Client ID/Secret: For OAuth flow

Stores credentials in youtube_token.json and .env.
"""

import json
import os
import webbrowser

import requests
from dotenv import load_dotenv

from logger import debug


# ============================================================
#                    CONFIGURATION
# ============================================================

from paths import get_data_dir

_DATA_DIR = get_data_dir()
ENV_FILE = os.path.join(_DATA_DIR, ".env")
TOKEN_FILE = os.path.join(_DATA_DIR, "youtube_token.json")

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
GOOGLE_OAUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Required scopes for YouTube
REQUIRED_SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

load_dotenv(ENV_FILE)

API_KEY = (os.getenv("YOUTUBE_API_KEY", "") or "").strip()
CLIENT_ID = (os.getenv("YOUTUBE_CLIENT_ID", "") or "").strip()
CLIENT_SECRET = (os.getenv("YOUTUBE_CLIENT_SECRET", "") or "").strip()
REDIRECT_URI = (os.getenv("YOUTUBE_REDIRECT_URI", "http://localhost:3000/callback") or "").strip()


class YouTubeTokenManager:
    """Manages YouTube API keys and OAuth tokens."""

    @staticmethod
    def load_token():
        """Load stored YouTube token data."""
        if not os.path.exists(TOKEN_FILE):
            debug("[YOUTUBE AUTH] Token file not found.")
            return None

        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                token_data = json.load(f)
            if not isinstance(token_data, dict):
                debug("[YOUTUBE AUTH] Token file is invalid.")
                return None
            return token_data
        except Exception as e:
            debug(f"[YOUTUBE AUTH] Failed to read token file: {e}")
            return None

    @staticmethod
    def save_token(token_data):
        """Save YouTube token data to file."""
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=4)

    @staticmethod
    def validate_token(access_token):
        """Validate a YouTube access token."""
        access_token = (access_token or "").strip()
        if not access_token:
            return False

        try:
            response = requests.get(
                "https://www.googleapis.com/oauth2/v3/tokeninfo",
                params={"access_token": access_token},
                timeout=15,
            )

            debug(f"[YOUTUBE AUTH] Token validation: HTTP {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                debug(f"[YOUTUBE AUTH] Token belongs to: {data.get('email', 'unknown')}")
                debug(f"[YOUTUBE AUTH] Token scopes: {data.get('scope', '')}")
                return True

            debug(f"[YOUTUBE AUTH] Validation failed: {response.text}")
            return False

        except Exception as e:
            debug(f"[YOUTUBE AUTH] Validation error: {e}")
            return False

    @staticmethod
    def validate_api_key():
        """Validate the YouTube API key."""
        if not API_KEY:
            return False

        try:
            response = requests.get(
                f"{YOUTUBE_API_BASE}/videos",
                params={
                    "part": "snippet",
                    "chart": "mostPopular",
                    "maxResults": 1,
                    "key": API_KEY,
                },
                timeout=15,
            )

            debug(f"[YOUTUBE AUTH] API key validation: HTTP {response.status_code}")
            return response.status_code == 200

        except Exception as e:
            debug(f"[YOUTUBE AUTH] API key validation error: {e}")
            return False

    @classmethod
    def get_valid_token(cls):
        """Get a valid YouTube access token."""
        token_data = cls.load_token()
        if not token_data:
            return None

        access_token = (token_data.get("access_token") or "").strip()
        if not access_token:
            debug("[YOUTUBE AUTH] Access token missing.")
            return None

        if cls.validate_token(access_token):
            debug("[YOUTUBE AUTH] Existing token is valid.")
            return access_token

        # Try refresh if available
        refresh_token = (token_data.get("refresh_token") or "").strip()
        if refresh_token:
            new_data = cls.refresh_token(refresh_token)
            if new_data:
                return new_data.get("access_token")

        return None

    @classmethod
    def get_api_key(cls):
        """Get the YouTube API key."""
        if API_KEY and cls.validate_api_key():
            return API_KEY
        return None

    @classmethod
    def refresh_token(cls, refresh_token_value):
        """Refresh a YouTube access token."""
        if not CLIENT_ID or not CLIENT_SECRET:
            debug("[YOUTUBE AUTH] CLIENT_ID or CLIENT_SECRET missing.")
            return None

        if not refresh_token_value:
            debug("[YOUTUBE AUTH] Refresh token missing.")
            return None

        debug("[YOUTUBE AUTH] Refreshing token...")

        try:
            response = requests.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token_value,
                },
                timeout=30,
            )
        except Exception as e:
            debug(f"[YOUTUBE AUTH] Token refresh request failed: {e}")
            return None

        if response.status_code != 200:
            debug(f"[YOUTUBE AUTH] Token refresh failed: HTTP {response.status_code}")
            return None

        new_token_data = response.json()
        new_access_token = (new_token_data.get("access_token") or "").strip()

        if not new_access_token:
            debug("[YOUTUBE AUTH] Refresh response contains no access token.")
            return None

        # Preserve refresh token
        if not new_token_data.get("refresh_token"):
            new_token_data["refresh_token"] = refresh_token_value

        cls.save_token(new_token_data)
        debug("[YOUTUBE AUTH] Token refreshed successfully.")
        return new_token_data

    @classmethod
    def start_oauth_flow(cls):
        """Start YouTube OAuth flow in browser."""
        if not CLIENT_ID:
            debug("[YOUTUBE AUTH] YOUTUBE_CLIENT_ID not configured.")
            return False

        params = {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(REQUIRED_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        }

        url = f"{GOOGLE_OAUTH_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
        debug("[YOUTUBE AUTH] Opening YouTube OAuth in browser...")
        webbrowser.open(url)
        return True

    @classmethod
    def is_configured(cls):
        """Check if YouTube credentials are configured."""
        return bool(API_KEY or (CLIENT_ID and CLIENT_SECRET))


def get_valid_token():
    """Compatibility function."""
    return YouTubeTokenManager.get_valid_token()