"""YouTube platform implementation.

Uses YouTube's public oEmbed API and page scraping for live streams.
No API key required for basic stream resolution.
"""

import os
import re
import subprocess
from typing import Optional

import requests

from .base import Platform, StreamInfo, PlatformError

STREAMLINK_PATH = r"C:\Program Files\Streamlink\bin\streamlink.exe"
YOUTUBE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
}


class YouTubePlatform(Platform):
    """YouTube streaming platform."""

    name = "youtube"
    display_name = "YouTube"

    def normalize_channel(self, channel_or_url) -> str:
        """Normalize YouTube URL to channel ID or handle."""
        url = str(channel_or_url).strip()

        # Already a channel URL
        if "youtube.com/channel/" in url:
            match = re.search(r"youtube\.com/channel/([^/?]+)", url)
            if match:
                return match.group(1)

        if "youtube.com/@handle" in url or "youtube.com/@" in url:
            match = re.search(r"youtube\.com/@([^/?]+)", url)
            if match:
                return f"@{match.group(1)}"

        # Live stream URL
        if "youtube.com/live/" in url:
            match = re.search(r"youtube\.com/live/([^/?]+)", url)
            if match:
                return match.group(1)

        # Short URL
        if "youtu.be/" in url:
            match = re.search(r"youtu\.be/([^/?]+)", url)
            if match:
                return match.group(1)

        # Already a video ID (11 chars)
        if re.match(r'^[A-Za-z0-9_-]{11}$', url):
            return url

        return url

    def resolve_stream(self, channel_or_url) -> StreamInfo:
        """Resolve a YouTube channel or video URL to a playable stream."""
        target = self.normalize_channel(channel_or_url)
        if not target:
            raise PlatformError("Empty YouTube channel/video.")

        # Try Streamlink first (works for live streams)
        if os.path.exists(STREAMLINK_PATH):
            try:
                return self._resolve_via_streamlink(target)
            except Exception:
                pass

        # Try direct URL resolution
        try:
            return self._resolve_via_url(target)
        except Exception as exc:
            raise PlatformError(
                f"Could not resolve YouTube stream '{target}': {exc}"
            )

    def _resolve_via_streamlink(self, target) -> StreamInfo:
        """Resolve via Streamlink (for live streams)."""
        # Determine the URL to pass to Streamlink
        if target.startswith("@") or target.startswith("channel/"):
            url = f"https://www.youtube.com/{target}"
        elif re.match(r'^[A-Za-z0-9_-]{11}$', target):
            url = f"https://www.youtube.com/watch?v={target}"
        else:
            url = f"https://www.youtube.com/watch?v={target}"

        result = subprocess.run(
            [STREAMLINK_PATH, url, "best", "--stream-url"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            raise PlatformError(
                f"Streamlink could not resolve YouTube: {result.stderr}"
            )

        stream_url = result.stdout.strip()
        if not stream_url:
            raise PlatformError("Streamlink returned empty URL.")

        return StreamInfo(
            platform=self.name,
            channel=target,
            url=stream_url,
            is_live=True,
        )

    def _resolve_via_url(self, target) -> StreamInfo:
        """Resolve by constructing a direct YouTube URL."""
        if target.startswith("@"):
            url = f"https://www.youtube.com/{target}/live"
        elif re.match(r'^[A-Za-z0-9_-]{11}$', target):
            url = f"https://www.youtube.com/watch?v={target}"
        else:
            url = f"https://www.youtube.com/watch?v={target}"

        # Verify the URL is accessible
        try:
            response = requests.head(url, headers=YOUTUBE_HEADERS, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                return StreamInfo(
                    platform=self.name,
                    channel=target,
                    url=url,
                    is_live=True,
                )
        except Exception:
            pass

        raise PlatformError(f"Could not verify YouTube URL for '{target}'.")

    def get_stream_info(self, channel) -> Optional[StreamInfo]:
        """Get YouTube stream metadata."""
        target = self.normalize_channel(channel)
        if not target:
            return None

        try:
            # Try to get basic info via oEmbed
            if re.match(r'^[A-Za-z0-9_-]{11}$', target):
                oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={target}&format=json"
                response = requests.get(oembed_url, headers=YOUTUBE_HEADERS, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    return StreamInfo(
                        platform=self.name,
                        channel=target,
                        url=f"https://www.youtube.com/watch?v={target}",
                        title=data.get("title", ""),
                        author_name=data.get("author_name", ""),
                        is_live=True,
                    )
        except Exception:
            pass

        return None

    def is_live(self, channel) -> bool:
        """Check if a YouTube channel is live."""
        info = self.get_stream_info(channel)
        return info is not None and info.is_live