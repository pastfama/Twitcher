"""SullyGoose API — tokenless analytics from sullygnome.com.

Scrapes public SullyGnome website data for channel analytics.
No OAuth token required.
"""

from .client import SullyGooseAPI

__all__ = ["SullyGooseAPI"]