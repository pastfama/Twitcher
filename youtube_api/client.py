"""YouTube API client — YouTube Data API v3 integration.

Provides stream info, channel data, and live status for YouTube.
Requires a YouTube Data API key for full features.
"""

import os
import re
import subprocess
from typing import Optional

import requests
from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_FILE)

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
YOUTUBE_API_KEY = (os.getenv("YOUTUBE_API_KEY", "") or "").strip()
STREAMLINK_PATH = r"C:\Program Files\Streamlink\bin\streamlink.exe"


class YouTubeAPIError(RuntimeError):
    """Raised when a YouTube API call fails."""


class YouTubeAPI:
    """YouTube API client (no authentication required for public data)."""

    def __init__(self, api_key=None, timeout=15):
        self.timeout = timeout
        self.api_key = api_key or YOUTUBE_API_KEY
        self.session = requests.Session()

    def normalize_channel(self, channel_or_url) -> str:
        """Extract channel ID or handle from YouTube URL or return as-is."""
        url = str(channel_or_url).strip()

        if "youtube.com/channel/" in url:
            match = re.search(r"youtube\.com/channel/([^/?]+)", url)
            if match:
                return match.group(1)

        if "youtube.com/@" in url:
            match = re.search(r"youtube\.com/@([^/?]+)", url)
            if match:
                return f"@{match.group(1)}"

        if "youtube.com/live/" in url:
            match = re.search(r"youtube\.com/live/([^/?]+)", url)
            if match:
                return match.group(1)

        if "youtu.be/" in url:
            match = re.search(r"youtu\.be/([^/?]+)", url)
            if match:
                return match.group(1)

        return url

    def get(self, endpoint, params=None):
        """Make a GET request to the YouTube API."""
        url = f"{YOUTUBE_API_BASE}{endpoint}"
        if self.api_key:
            params = params or {}
            params["key"] = self.api_key
        response = self.session.get(url, params=params, timeout=self.timeout)
        if response.status_code != 200:
            raise YouTubeAPIError(f"YouTube API error {response.status_code}: {response.text}")
        return response.json()

    def get_channel_info(self, channel_id) -> Optional[dict]:
        """Get channel info by channel ID."""
        if not self.api_key:
            raise YouTubeAPIError("YouTube API key not configured.")
        try:
            data = self.get("/channels", {
                "part": "snippet,statistics",
                "id": channel_id,
            })
            items = data.get("items", [])
            if not items:
                return None
            item = items[0]
            snippet = item.get("snippet", {})
            return {
                "channel_id": channel_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "avatar_url": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                "subscriber_count": item.get("statistics", {}).get("subscriberCount", "0"),
            }
        except YouTubeAPIError:
            return None

    def get_stream_info(self, channel_or_url) -> Optional[dict]:
        """Get current stream info, or None if not live."""
        target = self.normalize_channel(channel_or_url)
        if not target:
            return None

        # Try Streamlink first
        if os.path.exists(STREAMLINK_PATH):
            try:
                url = self._build_url(target)
                result = subprocess.run(
                    [STREAMLINK_PATH, url, "best", "--stream-url"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return {
                        "platform": "youtube",
                        "channel": target,
                        "url": result.stdout.strip(),
                        "title": "",
                        "game": "",
                        "viewer_count": 0,
                        "avatar_url": "",
                        "is_live": True,
                    }
            except Exception:
                pass

        # Try API if key available
        if self.api_key:
            try:
                return self._get_stream_info_via_api(target)
            except YouTubeAPIError:
                pass

        return None

    def _build_url(self, target) -> str:
        """Build a YouTube URL from a channel or video ID."""
        if target.startswith("@"):
            return f"https://www.youtube.com/{target}/live"
        elif re.match(r'^[A-Za-z0-9_-]{11}$', target):
            return f"https://www.youtube.com/watch?v={target}"
        else:
            return f"https://www.youtube.com/watch?v={target}"

    def _get_stream_info_via_api(self, target) -> Optional[dict]:
        """Get stream info via YouTube Data API."""
        # Search for live streams
        data = self.get("/search", {
            "part": "snippet",
            "q": target,
            "type": "video",
            "eventType": "live",
            "maxResults": 1,
        })
        items = data.get("items", [])
        if not items:
            return None
        item = items[0]
        snippet = item.get("snippet", {})
        video_id = item.get("id", {}).get("videoId", "")
        return {
            "platform": "youtube",
            "channel": target,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "title": snippet.get("title", ""),
            "game": "",
            "viewer_count": 0,
            "avatar_url": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
            "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            "is_live": True,
            "started_at": snippet.get("publishedAt", ""),
        }

    def is_live(self, channel) -> bool:
        """Check if a channel is live."""
        info = self.get_stream_info(channel)
        return info is not None and info.get("is_live", False)

    def get_followed_channels(self, user_id=None) -> list:
        """Get followed channels (requires OAuth - not implemented)."""
        return []

    def get_live_streams(self, channels) -> list:
        """Get live streams for a list of channels."""
        live = []
        for channel in channels:
            info = self.get_stream_info(channel)
            if info and info.get("is_live"):
                live.append(info)
        return live

    def close(self):
        """Close the session."""
        self.session.close()