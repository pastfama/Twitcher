"""YouTube API client package.

YouTubeAPI is the main entry point for YouTube integration.
Uses YouTube Data API v3 (requires API key for full features).
"""

from .client import YouTubeAPI, YouTubeAPIError

__all__ = ["YouTubeAPI", "YouTubeAPIError"]