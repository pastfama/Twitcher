"""SullyGoose API client — scrapes public SullyGnome website data.

No OAuth token required. Fetches channel analytics from
https://sullygnome.com/channel/{login} and parses the HTML.
"""

import re
import threading
import time

import requests
from logger import debug

SULLYGNOME_BASE = "https://sullygnome.com"
SULLYGNOME_CHANNEL_URL = f"{SULLYGNOME_BASE}/channel/{{login}}"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class SullyGooseAPIError(RuntimeError):
    """Raised when a SullyGnome scrape fails."""


class SullyGooseAPI:
    """Tokenless analytics client for sullygnome.com."""

    def __init__(self, timeout=8, cache_ttl=300):
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self._cache = {}
        self._lock = threading.Lock()

    def get_channel_stats(self, login):
        """Return analytics dict for *login*, or ``None`` if unavailable."""
        login = str(login or "").strip().lower()
        if not login:
            debug("[SULLYGOOSE] get_channel_stats called with empty login")
            return None

        with self._lock:
            cached = self._cache.get(login)
            if cached:
                timestamp, stats = cached
                if time.time() - timestamp < self.cache_ttl:
                    debug(f"[SULLYGOOSE] Cache hit for '{login}'")
                    return stats

        debug(f"[SULLYGOOSE] Fetching stats for '{login}' from sullygnome.com...")
        try:
            stats = self._scrape_channel(login)
        except Exception as exc:
            debug(f"[SULLYGOOSE] Fetch failed for '{login}': {exc}")
            return None

        if stats:
            with self._lock:
                self._cache[login] = (time.time(), stats)
            debug(f"[SULLYGOOSE] Cached stats for '{login}': {len(stats)} metrics")
        else:
            debug(f"[SULLYGOOSE] No usable stats parsed for '{login}'")
        return stats

    def _scrape_channel(self, login):
        url = SULLYGNOME_CHANNEL_URL.format(login=login)
        debug(f"[SULLYGOOSE] GET {url}")
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=self.timeout)
        debug(f"[SULLYGOOSE] HTTP {response.status_code} for '{login}'")
        if response.status_code != 200:
            raise SullyGooseAPIError(
                f"SullyGnome returned HTTP {response.status_code} for {login}"
            )
        parsed = self._parse_channel_html(response.text, login)
        debug(f"[SULLYGOOSE] Parsed metrics for '{login}': avg_viewers={parsed.get('avg_viewers')}, "
              f"rank={parsed.get('category_rank')}, followers={parsed.get('follower_count')}")
        return parsed

    def _parse_channel_html(self, html, login):
        """Parse the SullyGnome channel page into a stats dict."""
        stats = {
            "channel": login,
            "avg_viewers": self._extract_number(html, "Average Viewers"),
            "peak_viewers": self._extract_number(html, "Peak Viewers"),
            "viewer_growth": self._extract_percent(html, "Viewer Growth"),
            "category_rank": self._extract_rank(html),
            "stream_frequency": self._extract_hours_per_week(html),
            "avg_stream_duration": self._extract_duration(html),
            "typical_start_hour": self._extract_hour(html, "Start"),
            "typical_end_hour": self._extract_hour(html, "End"),
            "games_played_30d": self._extract_number(html, "Games Played"),
            "main_game_pct": self._extract_percent(html, "Main Game"),
            "raid_frequency": self._extract_percent(html, "Raid"),
            "trend_7d": "Stable",
            "trend_7d_pct": 0.0,
            "trend_30d": "Stable",
            "trend_30d_pct": 0.0,
            "best_day": "—",
            "follower_count": self._extract_number(html, "Followers"),
            "follower_growth_30d": self._extract_percent(html, "Follower Growth"),
            "chat_activity": self._extract_chat_activity(html),
            "consistency_score": self._extract_score(html, "Consistency"),
            "reliability_score": self._extract_score(html, "Reliability"),
            "discovery_score": self._extract_score(html, "Discovery"),
        }
        growth_7d = self._extract_percent(html, "7 Day")
        growth_30d = self._extract_percent(html, "30 Day")
        if growth_7d is not None:
            stats["trend_7d_pct"] = growth_7d
            stats["trend_7d"] = self._classify_trend(growth_7d)
        if growth_30d is not None:
            stats["trend_30d_pct"] = growth_30d
            stats["trend_30d"] = self._classify_trend(growth_30d)
        return stats

    @staticmethod
    def _extract_number(html, label):
        pattern = re.compile(re.escape(label) + r"[^0-9]*?([\d,]+)", re.IGNORECASE)
        match = pattern.search(html)
        if not match:
            return 0
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            return 0

    @staticmethod
    def _extract_percent(html, label):
        pattern = re.compile(re.escape(label) + r"[^0-9\-]*?([\-+]?[\d.]+)%", re.IGNORECASE)
        match = pattern.search(html)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    @staticmethod
    def _extract_rank(html):
        pattern = re.compile(r"#\s*(\d{1,4})")
        match = pattern.search(html)
        if not match:
            return 0
        try:
            return int(match.group(1))
        except ValueError:
            return 0

    @staticmethod
    def _extract_hours_per_week(html):
        pattern = re.compile(r"([\d.]+)\s*h(?:ours)?/w", re.IGNORECASE)
        match = pattern.search(html)
        if not match:
            return 0.0
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0

    @staticmethod
    def _extract_duration(html):
        pattern = re.compile(r"([\d.]+)\s*h(?:ours)?", re.IGNORECASE)
        match = pattern.search(html)
        if not match:
            return 0.0
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0

    @staticmethod
    def _extract_hour(html, label):
        pattern = re.compile(re.escape(label) + r"[^0-9]*?(\d{1,2}):(\d{2})", re.IGNORECASE)
        match = pattern.search(html)
        if not match:
            return 0
        try:
            return int(match.group(1))
        except ValueError:
            return 0

    @staticmethod
    def _extract_chat_activity(html):
        text = html.lower()
        if "high" in text and "chat" in text:
            return "High"
        if "medium" in text and "chat" in text:
            return "Medium"
        return "Low"

    @staticmethod
    def _extract_score(html, label):
        pattern = re.compile(re.escape(label) + r"[^0-9]*?(\d{1,3})", re.IGNORECASE)
        match = pattern.search(html)
        if not match:
            return 0
        try:
            return min(100, int(match.group(1)))
        except ValueError:
            return 0

    @staticmethod
    def _classify_trend(percent):
        if percent > 10:
            return "Rising"
        if percent < -5:
            return "Declining"
        return "Stable"