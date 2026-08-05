"""Abstract base class for streaming platforms."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StreamInfo:
    """Unified stream information across platforms."""
    platform: str
    channel: str
    url: str
    title: str = ""
    game: str = ""
    viewer_count: int = 0
    avatar_url: str = ""
    is_live: bool = False
    thumbnail_url: str = ""
    started_at: str = ""
    extra: dict = field(default_factory=dict)


class Platform(ABC):
    """Abstract base class for streaming platforms.

    Each platform implementation must provide:
    - resolve_stream(): Get a playable URL for a channel
    - get_stream_info(): Get current stream metadata
    - is_live(): Check if a channel is currently live
    """

    name: str = "unknown"
    display_name: str = "Unknown"

    @abstractmethod
    def resolve_stream(self, channel_or_url) -> StreamInfo:
        """Resolve a channel name or URL to a playable stream.

        Args:
            channel_or_url: Channel name or full URL

        Returns:
            StreamInfo with at least platform, channel, and url set

        Raises:
            PlatformError: If the stream cannot be resolved
        """

    @abstractmethod
    def get_stream_info(self, channel) -> Optional[StreamInfo]:
        """Get current stream metadata for a channel.

        Returns:
            StreamInfo with metadata, or None if not live
        """

    @abstractmethod
    def is_live(self, channel) -> bool:
        """Check if a channel is currently live."""

    def normalize_channel(self, channel_or_url) -> str:
        """Normalize a channel name or URL to a bare channel name."""
        return str(channel_or_url).strip().lower()

    def __repr__(self):
        return f"<{self.__class__.__name__}({self.name})>"


class PlatformError(RuntimeError):
    """Raised when a platform operation fails."""