"""Adapter that wraps the ``twitchAPI`` library with a synchronous interface.

The existing ``twitch_api/`` package exposes a synchronous, requests-based
``TwitchAPI`` class.  This adapter keeps that same public interface but
delegates to the officially supported ``twitchAPI`` library (async) via
the :mod:`core.async_bridge`.

The adapter is intentionally minimal — it exposes only the methods the
rest of the app actually calls, so the migration is low-risk.  Additional
methods can be added here as needed.
"""

import os
import time
from typing import Any, Optional

from twitchAPI.twitch import Twitch as TwitchLib
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope

from core.async_bridge import run_sync
from .client import TwitchAPIError

# Scopes the app needs (matches the existing hard-coded scopes)
APP_SCOPES = [
    AuthScope.CHANNEL_READ_REDEMPTIONS,
    AuthScope.CHANNEL_READ_SUBSCRIPTIONS,
    AuthScope.USER_READ_FOLLOWS,
    AuthScope.USER_READ_BROADCAST,
    AuthScope.CHANNEL_MANAGE_RAIDS,
    AuthScope.CHAT_READ,
    AuthScope.CHAT_EDIT,
]


class TwitchAPIAdapter:
    """Synchronous wrapper around ``twitchAPI.twitch.Twitch``.

    Usage is identical to the legacy ``TwitchAPI`` class::

        api = TwitchAPIAdapter(access_token="...")
        streams = api.get_live_streams(followed_channels)
    """

    def __init__(self, access_token: Optional[str] = None):
        self._client_id = (os.getenv("TWITCH_CLIENT_ID", "") or "").strip()
        self._client_secret = (os.getenv("TWITCH_CLIENT_SECRET", "") or "").strip()
        if not self._client_id or not self._client_secret:
            raise RuntimeError(
                "TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET are required in .env"
            )

        self._twitch = TwitchLib(self._client_id, self._client_secret)
        # App token (used for public endpoints)
        run_sync(self._twitch.authenticate_app([]))

        if access_token:
            self._set_user_token(access_token)

    # ------------------------------------------------------------------
    # Token handling
    # ------------------------------------------------------------------

    def _set_user_token(self, access_token: str, refresh_token: Optional[str] = None):
        """Set the user access token on the underlying client."""
        run_sync(
            self._twitch.set_user_authentication(
                access_token,
                APP_SCOPES,
                refresh_token=refresh_token,
            )
        )

    def get_user_access_token(self, user_id: str = "", force_verify: bool = False):
        """Run the OAuth device flow and return the user access token."""
        # Legacy callers pass user_id/force_verify; we ignore them and run a
        # fresh device auth flow.
        auth = UserAuthenticator(self._twitch, APP_SCOPES, force_verify=force_verify)
        token, refresh = run_sync(auth.authenticate())
        self._set_user_token(token, refresh)
        return token

    def refresh_user_token(self, refresh_token: str) -> str:
        """Refresh the user access token."""
        new_token, new_refresh = run_sync(
            self._twitch.refresh_used_token(refresh_token)
        )
        self._set_user_token(new_token, new_refresh)
        return new_token

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def get_current_user(self) -> Optional[dict]:
        """Return the authenticated user's profile."""
        users = run_sync(self._twitch.get_users())
        return users["data"][0] if users.get("data") else None

    def get_user(self, login: str) -> Optional[dict]:
        """Return a user by login name."""
        users = run_sync(self._twitch.get_users(logins=[login]))
        return users["data"][0] if users.get("data") else None

    def get_user_profile(self, login: str) -> Optional[dict]:
        """Return a user profile (alias of :meth:`get_user`)."""
        return self.get_user(login)

    # ------------------------------------------------------------------
    # Streams
    # ------------------------------------------------------------------

    def get_followed_channels(self, user_id: str) -> list:
        """Return all channels the user follows (paginated)."""
        channels = []
        cursor: Optional[str] = None
        while True:
            params = {"user_id": user_id, "first": 100}
            if cursor:
                params["after"] = cursor
            data = run_sync(self._twitch.get_followed_channels(**params))
            channels.extend(data.get("data", []))
            cursor = data.get("pagination", {}).get("cursor")
            if not cursor:
                break
        return channels

    def get_live_streams(self, followed_channels: list) -> list:
        """Return live streams for the given followed channels."""
        live_streams = []
        for start in range(0, len(followed_channels), 100):
            batch = followed_channels[start:start + 100]
            user_ids = []
            for channel in batch:
                broadcaster_id = (
                    channel.get("broadcaster_id")
                    or channel.get("broadcaster_user_id")
                )
                if broadcaster_id:
                    user_ids.append(broadcaster_id)
            if not user_ids:
                continue
            for attempt in range(1, 4):
                try:
                    data = run_sync(self._twitch.get_streams(user_id=user_ids, first=100))
                    live_streams.extend(data.get("data", []))
                    break
                except Exception as exc:
                    if attempt < 3:
                        time.sleep(2)
                    else:
                        raise TwitchAPIError(
                            f"Failed to retrieve live streams after 3 attempts.\n\n{exc}"
                        )
        return live_streams

    def get_stream_info(self, channel: str) -> Optional[dict]:
        """Return stream info for a single channel (by login)."""
        channel = str(channel).strip().lower().lstrip("#")
        data = run_sync(self._twitch.get_streams(user_login=[channel]))
        streams = data.get("data", [])
        return streams[0] if streams else None

    # ------------------------------------------------------------------
    # Games / Rewards
    # ------------------------------------------------------------------

    def get_game_thumbnail(self, game_id: str) -> Optional[str]:
        """Return the thumbnail URL for a game."""
        games = run_sync(self._twitch.get_games(game_ids=[game_id]))
        box = games["data"][0].get("box_art_url") if games.get("data") else None
        return box.replace("{width}x{height}", "300x400") if box else None

    def get_channel_rewards(self, broadcaster_id: str) -> list:
        """Return channel custom rewards for a broadcaster."""
        rewards = run_sync(
            self._twitch.get_custom_reward(broadcaster_id=broadcaster_id)
        )
        return rewards.get("data", [])

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self):
        """Close the underlying client."""
        run_sync(self._twitch.close())