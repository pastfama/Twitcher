"""Account Manager — unified authentication for all streaming platforms.

Provides browser-based login flows for Twitch, Kick, and YouTube.
Stores credentials in the project's .env file for persistence.
"""

import os
import webbrowser
from typing import Optional

from logger import debug


class AccountManager:
    """Manages authentication for all streaming platforms.

    Provides a simple interface to log in to Twitch, Kick, and YouTube
    via browser-based OAuth flows. Credentials are stored in .env.
    """

    def __init__(self, env_file=None):
        if env_file is None:
            from paths import get_data_dir
            env_file = os.path.join(get_data_dir(), ".env")
        self.env_file = env_file
        self._load_env()

    def _load_env(self):
        """Load environment variables from .env file."""
        if os.path.exists(self.env_file):
            from dotenv import load_dotenv
            load_dotenv(self.env_file)

    def _save_env_var(self, key, value):
        """Save a variable to the .env file."""
        lines = []
        if os.path.exists(self.env_file):
            with open(self.env_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

        # Remove existing key if present
        new_lines = []
        for line in lines:
            if line.strip().startswith(f"{key}="):
                continue
            new_lines.append(line)

        # Add new value
        new_lines.append(f"{key}={value}\n")

        with open(self.env_file, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        debug(f"[ACCOUNT] Saved {key} to .env")

    # ================================================================
    # TWITCH
    # ================================================================

    def get_twitch_credentials(self) -> dict:
        """Get stored Twitch credentials."""
        return {
            "client_id": os.getenv("TWITCH_CLIENT_ID", ""),
            "client_secret": os.getenv("TWITCH_CLIENT_SECRET", ""),
            "redirect_uri": os.getenv("TWITCH_REDIRECT_URI", "http://localhost:3000/callback"),
        }

    def is_twitch_configured(self) -> bool:
        """Check if Twitch credentials are configured."""
        creds = self.get_twitch_credentials()
        return bool(creds["client_id"] and creds["client_secret"])

    def login_twitch(self):
        """Start Twitch OAuth flow in browser."""
        if not self.is_twitch_configured():
            debug("[ACCOUNT] Twitch not configured. Please set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET")
            return False

        try:
            from twitch_auth import authenticate
            authenticate()
            return True
        except Exception as e:
            debug(f"[ACCOUNT] Twitch login failed: {e}")
            return False

    def set_twitch_credentials(self, client_id: str, client_secret: str, redirect_uri: str = "http://localhost:3000/callback"):
        """Set Twitch API credentials."""
        self._save_env_var("TWITCH_CLIENT_ID", client_id)
        self._save_env_var("TWITCH_CLIENT_SECRET", client_secret)
        self._save_env_var("TWITCH_REDIRECT_URI", redirect_uri)

    # ================================================================
    # KICK
    # ================================================================

    def get_kick_credentials(self) -> dict:
        """Get stored Kick credentials (if any)."""
        return {
            "api_key": os.getenv("KICK_API_KEY", ""),
        }

    def is_kick_configured(self) -> bool:
        """Check if Kick is available.

        Kick's public API works without authentication, so this
        returns True when OAuth credentials exist, a valid token
        is stored, or the public API is reachable.
        """
        try:
            from kick_token_manager import KickTokenManager
            has_token = KickTokenManager.get_valid_token() is not None
        except Exception:
            has_token = False
        has_oauth_creds = bool(os.getenv("KICK_CLIENT_ID", "").strip())
        if has_token or has_oauth_creds:
            return True
        # Public API requires no auth — verify it is reachable.
        try:
            import requests
            response = requests.get(
                "https://kick.com/api/v2/channels/xqc",
                timeout=5,
            )
            return response.status_code == 200
        except Exception:
            return False

    def login_kick(self):
        """Start Kick OAuth flow in browser."""
        try:
            from kick_token_manager import KickTokenManager
            return KickTokenManager.start_oauth_flow()
        except Exception as e:
            debug(f"[ACCOUNT] Kick login failed: {e}")
            return False

    # ================================================================
    # YOUTUBE
    # ================================================================

    def get_youtube_credentials(self) -> dict:
        """Get stored YouTube credentials."""
        return {
            "api_key": os.getenv("YOUTUBE_API_KEY", ""),
            "client_id": os.getenv("YOUTUBE_CLIENT_ID", ""),
            "client_secret": os.getenv("YOUTUBE_CLIENT_SECRET", ""),
        }

    def is_youtube_configured(self) -> bool:
        """Check if YouTube credentials are configured."""
        try:
            from youtube_token_manager import YouTubeTokenManager
            return YouTubeTokenManager.is_configured()
        except Exception:
            return False

    def login_youtube(self):
        """Start YouTube OAuth flow in browser."""
        try:
            from youtube_token_manager import YouTubeTokenManager
            return YouTubeTokenManager.start_oauth_flow()
        except Exception as e:
            debug(f"[ACCOUNT] YouTube login failed: {e}")
            return False

    def set_youtube_credentials(self, api_key: str = "", client_id: str = "", client_secret: str = ""):
        """Set YouTube API credentials."""
        if api_key:
            self._save_env_var("YOUTUBE_API_KEY", api_key)
        if client_id:
            self._save_env_var("YOUTUBE_CLIENT_ID", client_id)
        if client_secret:
            self._save_env_var("YOUTUBE_CLIENT_SECRET", client_secret)

    def _youtube_oauth_flow(self):
        """Start YouTube OAuth flow."""
        creds = self.get_youtube_credentials()
        redirect_uri = "http://localhost:3000/callback"

        auth_url = (
            "https://accounts.google.com/o/oauth2/auth?"
            "client_id={client_id}&"
            "redirect_uri={redirect_uri}&"
            "response_type=code&"
            "scope=https://www.googleapis.com/auth/youtube.readonly&"
            "access_type=offline"
        ).format(
            client_id=creds["client_id"],
            redirect_uri=redirect_uri,
        )

        debug("[ACCOUNT] Opening YouTube OAuth in browser...")
        webbrowser.open(auth_url)

    # ================================================================
    # UNIFIED
    # ================================================================

    def get_all_status(self) -> dict:
        """Get authentication status for all platforms."""
        return {
            "twitch": {
                "configured": self.is_twitch_configured(),
                "credentials": self.get_twitch_credentials(),
            },
            "kick": {
                "configured": self.is_kick_configured(),
                "credentials": self.get_kick_credentials(),
            },
            "youtube": {
                "configured": self.is_youtube_configured(),
                "credentials": self.get_youtube_credentials(),
            },
        }

    def login_all(self) -> dict:
        """Attempt to log in to all platforms."""
        results = {}
        results["twitch"] = self.login_twitch()
        results["kick"] = self.login_kick()
        results["youtube"] = self.login_youtube()
        return results