"""Kick.com platform implementation.

Uses Kick's public API (no auth required) to resolve streams.
Kick provides HLS streams that can be played directly.
"""

import re
from typing import Optional

import requests

from .base import Platform, StreamInfo, PlatformError

KICK_API_BASE = "https://kick.com/api/v2"
KICK_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
}


class KickPlatform(Platform):
    """Kick.com streaming platform."""

    name = "kick"
    display_name = "Kick"

    def normalize_channel(self, channel_or_url) -> str:
        """Extract channel name from Kick URL or return as-is."""
        url = str(channel_or_url).strip()
        if "kick.com/" in url.lower():
            parts = url.lower().split("kick.com/")
            if len(parts) > 1:
                return parts[1].split("/")[0].split("?")[0].strip("/")
        return url.lower().strip()

    def resolve_stream(self, channel_or_url) -> StreamInfo:
        """Resolve a Kick channel to a playable stream URL."""
        channel = self.normalize_channel(channel_or_url)
        if not channel:
            raise PlatformError("Empty channel name.")

        # Try the public API first
        try:
            return self._resolve_via_api(channel)
        except Exception as exc:
            raise PlatformError(
                f"Could not resolve Kick channel '{channel}': {exc}"
            )

    def _resolve_via_api(self, channel) -> StreamInfo:
        """Resolve via Kick's public API."""
        url = f"{KICK_API_BASE}/channels/{channel}"
        response = requests.get(url, headers=KICK_HEADERS, timeout=15)

        if response.status_code == 404:
            raise PlatformError(f"Kick channel '{channel}' not found.")

        if response.status_code != 200:
            raise PlatformError(
                f"Kick API returned HTTP {response.status_code}"
            )

        data = response.json()

        # Check if channel is live
        is_live = data.get("livestream") is not None
        if not is_live:
            raise PlatformError(f"Kick channel '{channel}' is not live.")

        livestream = data["livestream"]

        # Get the playback URL
        playback_url = livestream.get("playback_url", "")
        if not playback_url:
            # Try to construct from channel data
            raise PlatformError(
                f"No playback URL available for Kick channel '{channel}'."
            )

        return StreamInfo(
            platform=self.name,
            channel=channel,
            url=playback_url,
            title=livestream.get("session_title", ""),
            game=livestream.get("categories", [{}])[0].get("name", "")
                if livestream.get("categories") else "",
            viewer_count=livestream.get("viewer_count", 0),
            avatar_url=data.get("profile", {}).get("avatar", ""),
            is_live=True,
            thumbnail_url=livestream.get("thumbnail", {}).get("url", ""),
            started_at=livestream.get("created_at", ""),
            extra={
                "slug": data.get("slug", ""),
                "is_banned": data.get("user", {}).get("banned", False),
            },
        )

    def get_stream_info(self, channel) -> Optional[StreamInfo]:
        """Get Kick stream metadata."""
        channel = self.normalize_channel(channel)
        if not channel:
            return None

        try:
            url = f"{KICK_API_BASE}/channels/{channel}"
            response = requests.get(url, headers=KICK_HEADERS, timeout=15)

            if response.status_code != 200:
                return None

            data = response.json()
            is_live = data.get("livestream") is not None

            if not is_live:
                return StreamInfo(
                    platform=self.name,
                    channel=channel,
                    url="",
                    title="",
                    game="",
                    viewer_count=0,
                    avatar_url=data.get("profile", {}).get("avatar", ""),
                    is_live=False,
                )

            livestream = data["livestream"]
            return StreamInfo(
                platform=self.name,
                channel=channel,
                url=livestream.get("playback_url", ""),
                title=livestream.get("session_title", ""),
                game=livestream.get("categories", [{}])[0].get("name", "")
                    if livestream.get("categories") else "",
                viewer_count=livestream.get("viewer_count", 0),
                avatar_url=data.get("profile", {}).get("avatar", ""),
                is_live=True,
                thumbnail_url=livestream.get("thumbnail", {}).get("url", ""),
                started_at=livestream.get("created_at", ""),
            )

        except Exception:
            return None

    def is_live(self, channel) -> bool:
        """Check if a Kick channel is live."""
        info = self.get_stream_info(channel)
        return info is not None and info.is_live