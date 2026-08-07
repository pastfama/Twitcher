"""Kick API client package.

KickAPI is the main entry point for Kick.com integration.
No OAuth required - uses public API endpoints.
"""

from .client import KickAPI, KickAPIError

__all__ = ["KickAPI", "KickAPIError"]