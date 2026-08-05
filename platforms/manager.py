"""Multi-platform manager — unified interface for all streaming platforms.

Provides a single entry point to query streams from Twitch, Kick, and YouTube.
"""

from typing import List, Optional

from logger import debug


class PlatformManager:
    """Manages connections to multiple streaming platforms."""

    def __init__(self):
        self._twitch = None
        self._kick = None
        self._youtube = None

    @property
    def twitch(self):
        if self._twitch is None:
            try:
                from twitch_api import TwitchAPI
                self._twitch = TwitchAPI()
            except Exception as e:
                debug(f"[PLATFORMS] Failed to init Twitch API: {e}")
        return self._twitch

    @property
    def kick(self):
        if self._kick is None:
            try:
                from kick_api import KickAPI
                self._kick = KickAPI()
            except Exception as e:
                debug(f"[PLATFORMS] Failed to init Kick API: {e}")
        return self._kick

    @property
    def youtube(self):
        if self._youtube is None:
            try:
                from youtube_api import YouTubeAPI
                self._youtube = YouTubeAPI()
            except Exception as e:
                debug(f"[PLATFORMS] Failed to init YouTube API: {e}")
        return self._youtube

    def get_stream_info(self, platform: str, channel: str) -> Optional[dict]:
        """Get stream info from the specified platform."""
        if platform == "twitch":
            if self.twitch:
                return self.twitch.get_stream_info(channel)
        elif platform == "kick":
            if self.kick:
                return self.kick.get_stream_info(channel)
        elif platform == "youtube":
            if self.youtube:
                return self.youtube.get_stream_info(channel)
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
        """Get followed channels from a platform."""
        if platform == "twitch" and self.twitch:
            try:
                return self.twitch.get_followed_channels(user_id)
            except Exception as e:
                debug(f"[PLATFORMS] Error getting Twitch followed: {e}")
        elif platform == "kick" and self.kick:
            return self.kick.get_followed_channels()
        elif platform == "youtube" and self.youtube:
            return self.youtube.get_followed_channels()
        return []

    def close(self):
        """Close all platform connections."""
        if self._twitch:
            try:
                self._twitch.close()
            except Exception:
                pass
        if self._kick:
            try:
                self._kick.close()
            except Exception:
                pass
        if self._youtube:
            try:
                self._youtube.close()
            except Exception:
                pass


# Global singleton instance
_platform_manager = None


def get_platform_manager() -> PlatformManager:
    """Get the global platform manager instance."""
    global _platform_manager
    if _platform_manager is None:
        _platform_manager = PlatformManager()
    return _platform_manager