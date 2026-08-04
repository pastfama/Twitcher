"""Auth-free Twitch stream URL resolver.

Uses Streamlink's public stream API — NO Twitch OAuth token required.
Playback of public Twitch streams works for anyone; only chat/API
features need a token.
"""

import os
import subprocess

STREAMLINK_PATH = r"C:\Program Files\Streamlink\bin\streamlink.exe"


class StreamResolverError(RuntimeError):
    """Raised when a stream URL could not be resolved."""


def normalize_channel(channel):
    return str(channel).strip().lower().lstrip("#")


def resolve_stream_url(channel):
    """Return a playable URL for *channel* using Streamlink (no auth)."""
    channel = normalize_channel(channel)
    if not channel:
        raise StreamResolverError("Empty channel name.")
    if not os.path.exists(STREAMLINK_PATH):
        raise StreamResolverError(
            f"Streamlink was not found.\n\nExpected:\n{STREAMLINK_PATH}"
        )
    result = subprocess.run(
        [STREAMLINK_PATH, f"twitch.tv/{channel}", "best", "--stream-url"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise StreamResolverError(
            f"Streamlink could not resolve {channel}:\n\n{result.stderr}"
        )
    url = result.stdout.strip()
    if not url:
        raise StreamResolverError(f"Streamlink returned an empty URL for {channel}.")
    return url


def try_resolve(channels):
    """Try each channel in order; return (channel, url) for the first that works."""
    for channel in channels:
        try:
            url = resolve_stream_url(channel)
            return channel, url
        except Exception:
            continue
    return None, None