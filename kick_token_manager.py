"""Kick Token Manager — manages Kick API credentials.

Kick uses a simpler auth model than Twitch:
- Public API: No auth needed for public channel data
- OAuth: Required for user-specific actions (chat, follows)
- API Key: Optional for enhanced rate limits

Stores credentials in kick_token.json and .env.
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")
TOKEN_FILE = os.path.join(BASE_DIR, "kick_token.json")

KICK_API_BASE = "https://kick.com/api/v2"
KICK_OAUTH_URL = "https://kick.com/oauth/authorize"
KICK_TOKEN_URL = "https://kick.com/oauth/token"

# Required scopes for Kick
REQUIRED_SCOPES = [
    "user:read",
    "channel:read",
    "chat:write",
]

load_dotenv(ENV_FILE)

CLIENT_ID = (os.getenv("KICK_CLIENT_ID", "") or "").strip()
CLIENT_SECRET = (os.getenv("KICK_CLIENT_SECRET", "") or "").strip()
REDIRECT_URI = (os.getenv("KICK_REDIRECT_URI", "http://localhost:3000/callback") or "").strip()


class KickTokenManager:
    """Manages Kick OAuth tokens and API keys."""

    @staticmethod
    def load_token():
        """Load stored Kick token data."""
        if not os.path.exists(TOKEN_FILE):
            debug("[KICK AUTH] Token file not found.")
            return None

        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                token_data = json.load(f)
            if not isinstance(token_data, dict):
                debug("[KICK AUTH] Token file is invalid.")
                return None
            return token_data
        except Exception as e:
            debug(f"[KICK AUTH] Failed to read token file: {e}")
            return None

    @staticmethod
    def save_token(token_data):
        """Save Kick token data to file."""
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=4)

    @staticmethod
    def validate_token(access_token):
        """Validate a Kick access token."""
        access_token = (access_token or "").strip()
        if not access_token:
            return False

        try:
            response = requests.get(
                f"{KICK_API_BASE}/user",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15,
            )

            debug(f"[KICK AUTH] Token validation: HTTP {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                debug(f"[KICK AUTH] Token belongs to: {data.get('username', 'unknown')}")
                return True

            debug(f"[KICK AUTH] Validation failed: {response.text}")
            return False

        except Exception as e:
            debug(f"[KICK AUTH] Validation error: {e}")
            return False

    @classmethod
    def get_valid_token(cls):
        """Get a valid Kick access token."""
        token_data = cls.load_token()
        if not token_data:
            return None

        access_token = (token_data.get("access_token") or "").strip()
        if not access_token:
            debug("[KICK AUTH] Access token missing.")
            return None

        if cls.validate_token(access_token):
            debug("[KICK AUTH] Existing token is valid.")
            return access_token

        # Try refresh if available
        refresh_token = (token_data.get("refresh_token") or "").strip()
        if refresh_token:
            new_data = cls.refresh_token(refresh_token)
            if new_data:
                return new_data.get("access_token")

        return None

    @classmethod
    def refresh_token(cls, refresh_token_value):
        """Refresh a Kick access token."""
        if not CLIENT_ID or not CLIENT_SECRET:
            debug("[KICK AUTH] CLIENT_ID or CLIENT_SECRET missing.")
            return None

        if not refresh_token_value:
            debug("[KICK AUTH] Refresh token missing.")
            return None

        debug("[KICK AUTH] Refreshing token...")

        try:
            response = requests.post(
                KICK_TOKEN_URL,
                data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token_value,
                },
                timeout=30,
            )
        except Exception as e:
            debug(f"[KICK AUTH] Token refresh request failed: {e}")
            return None

        if response.status_code != 200:
            debug(f"[KICK AUTH] Token refresh failed: HTTP {response.status_code}")
            return None

        new_token_data = response.json()
        new_access_token = (new_token_data.get("access_token") or "").strip()

        if not new_access_token:
            debug("[KICK AUTH] Refresh response contains no access token.")
            return None

        # Preserve refresh token
        if not new_token_data.get("refresh_token"):
            new_token_data["refresh_token"] = refresh_token_value

        cls.save_token(new_token_data)
        debug("[KICK AUTH] Token refreshed successfully.")
        return new_token_data

    @classmethod
    def start_oauth_flow(cls):
        """Start Kick OAuth flow in browser."""
        if not CLIENT_ID:
            debug("[KICK AUTH] KICK_CLIENT_ID not configured.")
            return False

        params = {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(REQUIRED_SCOPES),
            "state": "watcher_kick_auth",
        }

        url = f"{KICK_OAUTH_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
        debug("[KICK AUTH] Opening Kick OAuth in browser...")
        webbrowser.open(url)
        return True


def get_valid_token():
    """Compatibility function."""
    return KickTokenManager.get_valid_token()