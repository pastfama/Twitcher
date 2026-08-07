"""Twitch platform implementation."""

import os
import subprocess
from typing import Optional

from .base import Platform, StreamInfo, PlatformError

STREAMLINK_PATH = r"C:\Program Files\Streamlink\bin\streamlink.exe"


class TwitchPlatform(Platform):
    """Twitch streaming platform."""

    name = "twitch"
    display_name = "Twitch"

    def normalize_channel(self, channel_or_url) -> str:
        """Extract channel name from Twitch URL or return as-is."""
        url = str(channel_or_url).strip()
        if "twitch.tv/" in url.lower():
            parts = url.lower().split("twitch.tv/")
            if len(parts) > 1:
                return parts[1].split("/")[0].split("?")[0].strip("/")
        return url.lower().lstrip("#").strip()

    def resolve_stream(self, channel_or_url) -> StreamInfo:
        """Resolve a Twitch channel to a playable stream URL via Streamlink."""
        channel = self.normalize_channel(channel_or_url)
        if not channel:
            raise PlatformError("Empty channel name.")

        if not os.path.exists(STREAMLINK_PATH):
            raise PlatformError(
                f"Streamlink was not found.\n\nExpected:\n{STREAMLINK_PATH}"
            )

        result = subprocess.run(
            [STREAMLINK_PATH, f"twitch.tv/{channel}", "best", "--stream-url"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            raise PlatformError(
                f"Streamlink could not resolve {channel}:\n\n{result.stderr}"
            )

        url = result.stdout.strip()
        if not url:
            raise PlatformError(
                f"Streamlink returned an empty URL for {channel}."
            )

        return StreamInfo(
            platform=self.name,
            channel=channel,
            url=url,
            is_live=True,
        )

    def get_stream_info(self, channel) -> Optional[StreamInfo]:
        """Get Twitch stream info (requires API client - placeholder)."""
        # This would use the Twitch API client to get stream metadata
        # For now, return basic info if we can resolve the stream
        try:
            stream = self.resolve_stream(channel)
            return stream
        except PlatformError:
            return None

    def is_live(self, channel) -> bool:
        """Check if a Twitch channel is live."""
        try:
            self.resolve_stream(channel)
            return True
        except PlatformError:
            return False