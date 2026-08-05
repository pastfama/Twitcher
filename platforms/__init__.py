"""Multi-platform streaming support.

Provides a unified interface for Twitch, Kick, and YouTube.
"""

from .base import Platform, StreamInfo
from .twitch import TwitchPlatform
from .kick import KickPlatform
from .youtube import YouTubePlatform
from .manager import PlatformManager, get_platform_manager

# Platform registry - order matters for auto-detection
PLATFORMS = {
    "twitch": TwitchPlatform,
    "kick": KickPlatform,
    "youtube": YouTubePlatform,
}


def get_platform(name):
    """Get a platform class by name."""
    return PLATFORMS.get(name.lower())


def detect_platform(url_or_channel):
    """Detect which platform a URL or channel name belongs to."""
    url_lower = str(url_or_channel).lower()

    if "twitch.tv" in url_lower:
        return "twitch"
    elif "kick.com" in url_lower:
        return "kick"
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"

    # Default to Twitch for bare channel names (backward compatibility)
    return "twitch"


def resolve_stream(url_or_channel, platform_name=None):
    """Resolve a stream URL from any platform.

    Args:
        url_or_channel: URL or channel name
        platform_name: Force a specific platform, or auto-detect

    Returns:
        StreamInfo with the resolved URL and metadata
    """
    if platform_name is None:
        platform_name = detect_platform(url_or_channel)

    platform_cls = get_platform(platform_name)
    if platform_cls is None:
        raise ValueError(f"Unknown platform: {platform_name}")

    platform = platform_cls()
    return platform.resolve_stream(url_or_channel)


__all__ = [
    "Platform",
    "StreamInfo",
    "TwitchPlatform",
    "KickPlatform",
    "YouTubePlatform",
    "PlatformManager",
    "get_platform_manager",
    "PLATFORMS",
    "get_platform",
    "detect_platform",
    "resolve_stream",
]