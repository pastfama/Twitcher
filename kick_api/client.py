"""Kick API client — public API integration (no OAuth required).

Provides stream info, channel data, and live status for Kick.com.
"""

import re
from typing import Optional

import requests


KICK_API_BASE = "https://kick.com/api/v2"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


class KickAPIError(RuntimeError):
    """Raised when a Kick API call fails."""


class KickAPI:
    """Kick.com API client (no authentication required)."""

    def __init__(self, timeout=15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def normalize_channel(self, channel_or_url) -> str:
        """Extract channel name from Kick URL or return as-is."""
        url = str(channel_or_url).strip()
        if "kick.com/" in url.lower():
            parts = url.lower().split("kick.com/")
            if len(parts) > 1:
                return parts[1].split("/")[0].split("?")[0].strip("/")
        return url.lower().strip()

    def get(self, endpoint, params=None):
        """Make a GET request to the Kick API."""
        url = f"{KICK_API_BASE}{endpoint}"
        response = self.session.get(url, params=params, timeout=self.timeout)
        if response.status_code == 404:
            raise KickAPIError(f"Resource not found: {endpoint}")
        if response.status_code != 200:
            raise KickAPIError(f"Kick API error {response.status_code}: {response.text}")
        return response.json()

    def get_channel(self, channel) -> dict:
        """Get channel info."""
        channel = self.normalize_channel(channel)
        return self.get(f"/channels/{channel}")

    def get_stream_info(self, channel) -> Optional[dict]:
        """Get current stream info, or None if not live."""
        channel = self.normalize_channel(channel)
        if not channel:
            return None
        try:
            data = self.get_channel(channel)
            livestream = data.get("livestream")
            if not livestream:
                return None
            return {
                "platform": "kick",
                "channel": channel,
                "title": livestream.get("session_title", ""),
                "game": livestream.get("categories", [{}])[0].get("name", "")
                        if livestream.get("categories") else "",
                "viewer_count": livestream.get("viewer_count", 0),
                "avatar_url": data.get("profile", {}).get("avatar", ""),
                "thumbnail_url": livestream.get("thumbnail", {}).get("url", ""),
                "is_live": True,
                "started_at": livestream.get("created_at", ""),
                "url": livestream.get("playback_url", ""),
            }
        except KickAPIError:
            return None

    def is_live(self, channel) -> bool:
        """Check if a channel is live."""
        info = self.get_stream_info(channel)
        return info is not None and info.get("is_live", False)

    def get_followed_channels(self, user_id=None) -> list:
        """Get followed channels (Kick doesn't require auth for public profiles).

        Returns empty list - Kick doesn't have a public followed channels endpoint.
        """
        return []

    def get_live_streams(self, channels) -> list:
        """Get live streams for a list of channels."""
        live = []
        for channel in channels:
            login = self.normalize_channel(channel)
            info = self.get_stream_info(login)
            if info and info.get("is_live"):
                live.append(info)
        return live

    def close(self):
        """Close the session."""
        self.session.close()