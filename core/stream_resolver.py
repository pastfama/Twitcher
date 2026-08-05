"""Multi-platform stream URL resolver.

Uses Streamlink for Twitch/YouTube and platform APIs for Kick.
Supports: Twitch, Kick, YouTube
"""

import os
import subprocess

from platforms.base import PlatformError

STREAMLINK_PATH = r"C:\Program Files\Streamlink\bin\streamlink.exe"


class StreamResolverError(RuntimeError):
    """Raised when a stream URL could not be resolved."""


def normalize_channel(channel):
    return str(channel).strip().lower().lstrip("#")


def resolve_stream_url(channel, platform_name=None):
    """Return a playable URL for *channel* using the appropriate platform.

    Args:
        channel: Channel name or URL
        platform_name: Force a specific platform (twitch, kick, youtube),
                       or None for auto-detection
    """
    from platforms import detect_platform, get_platform

    if platform_name is None:
        platform_name = detect_platform(channel)

    platform_cls = get_platform(platform_name)
    if platform_cls is None:
        raise StreamResolverError(f"Unknown platform: {platform_name}")

    platform = platform_cls()

    try:
        stream_info = platform.resolve_stream(channel)
        return stream_info.url
    except PlatformError as exc:
        raise StreamResolverError(str(exc))


def try_resolve(channels):
    """Try each channel in order; return (channel, url) for the first that works."""
    for channel in channels:
        try:
            url = resolve_stream_url(channel)
            return channel, url
        except Exception:
            continue
    return None, None