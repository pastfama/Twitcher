"""Multi-platform manager — unified interface for all streaming platforms.

Provides a single entry point to query streams from Twitch, Kick, and YouTube.

The manager wraps the :class:`~platforms.base.Platform` ABC classes so all
platforms share the same interface.  Stream data is returned as dicts with a
mandatory ``platform`` field so downstream consumers (UI, analytics, DB) can
treat every platform equally.
"""

from typing import List, Optional

from logger import debug

from .base import StreamInfo


def _stream_info_to_dict(info: StreamInfo) -> dict:
    """Convert a StreamInfo dataclass to the canonical stream dict."""
    if info is None:
        return None
    return {
        "platform": info.platform,
        "channel": info.channel,
        "url": info.url,
        "title": info.title,
        "game": info.game,
        "viewer_count": info.viewer_count,
        "avatar_url": info.avatar_url,
        "is_live": info.is_live,
        "thumbnail_url": info.thumbnail_url,
        "started_at": info.started_at,
        "extra": info.extra,
        # Aliases used by the UI (Twitch-style field names).
        "user_login": info.channel,
        "user_name": info.channel,
    }


class PlatformManager:
    """Manages connections to multiple streaming platforms."""

    def __init__(self):
        self._platforms = {}

    def _get_platform(self, name):
        """Lazily instantiate a Platform ABC class by name."""
        if name not in self._platforms:
            try:
                from . import get_platform
                cls = get_platform(name)
                if cls is None:
                    debug(f"[PLATFORMS] Unknown platform: {name}")
                    return None
                self._platforms[name] = cls()
            except Exception as e:
                debug(f"[PLATFORMS] Failed to init {name}: {e}")
                return None
        return self._platforms.get(name)

    @property
    def twitch(self):
        return self._get_platform("twitch")

    @property
    def kick(self):
        return self._get_platform("kick")

    @property
    def youtube(self):
        return self._get_platform("youtube")

    def get_stream_info(self, platform: str, channel: str) -> Optional[dict]:
        """Get stream info from the specified platform."""
        platform = str(platform or "twitch").lower().strip()
        p = self._get_platform(platform)
        if p is None:
            return None
        try:
            info = p.get_stream_info(channel)
            return _stream_info_to_dict(info)
        except Exception as e:
            debug(f"[PLATFORMS] Error checking {platform}/{channel}: {e}")
            return None

    def get_live_streams(self, channels: List[dict]) -> List[dict]:
        """Get live streams from all platforms.

        Args:
            channels: List of dicts with 'platform' and 'channel' keys
        """
        live = []
        for ch in channels:
            platform = ch.get("platform", "twitch")
            channel = ch.get("channel")
            if not channel:
                continue
            try:
                info = self.get_stream_info(platform, channel)
                if info and info.get("is_live"):
                    live.append(info)
            except Exception as e:
                debug(f"[PLATFORMS] Error checking {platform}/{channel}: {e}")
        return live

    def get_followed_channels(self, user_id: str, platform: str = "twitch") -> List[dict]:
        """Get followed channels from a platform.

        Twitch uses the API; Kick and YouTube have no public followed
        endpoint, so they return the local watchlist entries.
        """
        platform = str(platform or "twitch").lower().strip()
        if platform == "twitch":
            try:
                from twitch_api import TwitchAPI
                api = TwitchAPI()
                return api.get_followed_channels(user_id)
            except Exception as e:
                debug(f"[PLATFORMS] Error getting Twitch followed: {e}")
                return []
        # Kick/YouTube: use the local watchlist.
        try:
            from core.db import get_watchlist
            return [
                {"platform": platform, "channel": entry["channel"]}
                for entry in get_watchlist(platform=platform)
            ]
        except Exception as e:
            debug(f"[PLATFORMS] Error getting {platform} watchlist: {e}")
            return []

    def close(self):
        """Close all platform connections."""
        self._platforms.clear()


# Global singleton instance
_platform_manager = None


def get_platform_manager() -> PlatformManager:
    """Get the global platform manager instance."""
    global _platform_manager
    if _platform_manager is None:
        _platform_manager = PlatformManager()
    return _platform_manager