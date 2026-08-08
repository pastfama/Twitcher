"""SullyGoose API client — scrapes public SullyGnome website data.

No OAuth token required. Fetches channel analytics from
https://sullygnome.com/channel/{login} and parses the HTML.

Uses BeautifulSoup when available for reliable DOM-based extraction;
falls back to regex parsing if bs4 is not installed.
"""

import re
import threading
import time

import requests
from logger import debug

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    BeautifulSoup = None
    _HAS_BS4 = False

SULLYGNOME_BASE = "https://sullygnome.com"
SULLYGNOME_CHANNEL_URL = f"{SULLYGNOME_BASE}/channel/{{login}}"
SULLYGNOME_YOUTUBE_URL = f"{SULLYGNOME_BASE}/channel/{{login}}"

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

    def __init__(self, db, timeout=8, cache_ttl=300):
        self.db = db
        self.timeout = timeout
        self.cache_ttl = cache_ttl

    def get_channel_stats(self, login, platform="twitch"):
        """Return analytics dict for *login*, or ``None`` if unavailable.
        
        Args:
            login: Channel name or ID
            platform: "twitch" or "youtube" (SullyGnome supports both)
        """
        login = str(login or "").strip().lower()
        if not login:
            debug("[SULLYGOOSE] get_channel_stats called with empty login")
            return None
            
        # Kick is not supported by SullyGnome
        if platform == "kick":
            debug(f"[SULLYGOOSE] Kick not supported by SullyGnome")
            return None
            
        # Build URL based on platform
        if platform == "youtube":
            url = SULLYGNOME_YOUTUBE_URL.format(login=login)
        else:
            url = SULLYGNOME_CHANNEL_URL.format(login=login)
            
        debug(f"[SULLYGOOSE] GET {url}")
        try:
            response = requests.get(url, headers=DEFAULT_HEADERS, timeout=self.timeout)
            debug(f"[SULLYGOOSE] HTTP {response.status_code} for '{login}'")
            
            if response.status_code != 200:
                raise SullyGooseAPIError(
                    f"SullyGnome returned HTTP {response.status_code} for {login}"
                )
                
            html = response.text
            stats = self._parse_channel_html(html, login)
            
            if stats:
                stats["platform"] = platform
                # Store in database
                self.db.store_sg(
                    login=login,
                    stats=stats,
                    platform=platform,
                    status="success",
                    raw_html=html,
                    response_time_ms=self.timeout * 1000
                )
                debug(f"[SULLYGOOSE] Stored stats for '{login}' ({platform}) in DB: {len(stats)} metrics")
                return stats
            else:
                debug(f"[SULLYGOOSE] No usable stats parsed for '{login}' ({platform})")
                # Store empty stats with failure status
                self.db.store_sg(
                    login=login,
                    stats={},
                    platform=platform,
                    status="partial",
                    raw_html=html,
                    response_time_ms=self.timeout * 1000
                )
                return None
                
        except Exception as exc:
            debug(f"[SULLYGOOSE] Fetch failed for '{login}' ({platform}): {exc}")
            # Store error in DB
            self.db.store_sg(
                login=login,
                stats={},
                platform=platform,
                status="failed",
                error=str(exc),
                response_time_ms=self.timeout * 1000
            )
            return None

    def _scrape_channel(self, login, platform="twitch"):
        if platform == "youtube":
            url = SULLYGNOME_YOUTUBE_URL.format(login=login)
        else:
            url = SULLYGNOME_CHANNEL_URL.format(login=login)
        debug(f"[SULLYGOOSE] GET {url}")
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=self.timeout)
        debug(f"[SULLYGOOSE] HTTP {response.status_code} for '{login}'")
        if response.status_code != 200:
            raise SullyGooseAPIError(
                f"SullyGnome returned HTTP {response.status_code} for {login}"
            )
        parsed = self._parse_channel_html(response.text, login)
        debug(f"[SULLYGOOSE] Parsed metrics for '{login}': "
              f"avg_viewers={parsed.get('avg_viewers')}, "
              f"rank={parsed.get('category_rank')}, "
              f"followers={parsed.get('follower_count')}")
        return parsed

    # ================================================================
    # HTML PARSING (BeautifulSoup)
    # ================================================================

    def _parse_channel_html(self, html, login):
        """Parse the SullyGnome channel page into a stats dict.

        Dispatches to BeautifulSoup parser when available, otherwise
        falls back to regex-based extraction.
        """
        if _HAS_BS4:
            return self._parse_with_bs4(html, login)
        return self._parse_with_regex(html, login)

    def _parse_with_bs4(self, html, login):
        """BeautifulSoup-based parser (preferred)."""
        soup = BeautifulSoup(html, "html.parser")

        follower_count = self._parse_follower_count(soup)
        ranks = self._parse_ranks(soup)
        stats_blocks = self._parse_stat_blocks(soup)
        summary = self._parse_summary_paragraphs(soup)
        game_info = self._parse_game_info(soup)

        avg_viewers = stats_blocks.get("average_viewers")
        if avg_viewers is None:
            avg_viewers = summary.get("avg_viewers", 0)
        peak_viewers = stats_blocks.get("peak_viewers")
        if peak_viewers is None:
            peak_viewers = summary.get("peak_viewers", 0)

        stats = self._empty_stats(login)
        stats.update({
            "avg_viewers": avg_viewers,
            "peak_viewers": peak_viewers,
            "viewer_growth": stats_blocks.get("viewer_growth"),
            "category_rank": ranks.get("average_viewer_rank", 0),
            "stream_frequency": summary.get("streams_count", 0),
            "avg_stream_duration": summary.get("avg_stream_duration", 0.0),
            "games_played_30d": game_info.get("games_played", 0),
            "follower_count": follower_count,
            "follower_growth_30d": stats_blocks.get("follower_growth"),
        })

        hours_streamed = summary.get("hours_streamed", 0)
        streams_count = summary.get("streams_count", 0)
        if hours_streamed and streams_count:
            stats["stream_frequency"] = round(hours_streamed * 7 / 30, 1)

        return stats

    def _parse_with_regex(self, html, login):
        """Regex-based fallback parser (when bs4 is not installed)."""
        stats = self._empty_stats(login)

        # Follower count
        m = re.search(r"Followers:\s*([\d,]+)", html)
        if m:
            try:
                stats["follower_count"] = int(m.group(1).replace(",", ""))
            except ValueError:
                pass

        # Average viewers
        m = re.search(r"Average\s+Viewers[^0-9]*([\d,]+)", html, re.IGNORECASE)
        if m:
            try:
                stats["avg_viewers"] = int(m.group(1).replace(",", ""))
            except ValueError:
                pass

        # Peak viewers
        m = re.search(r"Peak\s+Viewers[^0-9]*([\d,]+)", html, re.IGNORECASE)
        if m:
            try:
                stats["peak_viewers"] = int(m.group(1).replace(",", ""))
            except ValueError:
                pass

        # Rank: "average viewer rank" followed by a number
        m = re.search(r"average viewer rank[^0-9]*([\d,]+)", html, re.IGNORECASE)
        if m:
            try:
                stats["category_rank"] = int(m.group(1).replace(",", ""))
            except ValueError:
                pass

        # Summary paragraphs
        m = re.search(r"streamed for (\d[\d,]*) hours", html)
        if m:
            try:
                stats["stream_frequency"] = int(m.group(1).replace(",", ""))
            except ValueError:
                pass

        m = re.search(r"streamed (\d+) times", html)
        if m:
            try:
                stats["stream_frequency"] = int(m.group(1))
            except ValueError:
                pass

        m = re.search(r"average of (\d+) hours?,?\s*(\d+)?\s*min", html)
        if m:
            try:
                h = int(m.group(1))
                mins = int(m.group(2)) if m.group(2) else 0
                stats["avg_stream_duration"] = round(h + mins / 60, 1)
            except ValueError:
                pass

        # Games played
        m = re.search(r"streamed (\d+) other game", html)
        if m:
            try:
                stats["games_played_30d"] = int(m.group(1)) + 1
            except ValueError:
                pass

        return stats

    @staticmethod
    def _empty_stats(login):
        """Return a stats dict with default values."""
        return {
            "channel": login,
            "avg_viewers": 0,
            "peak_viewers": 0,
            "viewer_growth": None,
            "category_rank": 0,
            "stream_frequency": 0,
            "avg_stream_duration": 0.0,
            "typical_start_hour": 0,
            "typical_end_hour": 0,
            "games_played_30d": 0,
            "main_game_pct": None,
            "raid_frequency": None,
            "trend_7d": "Stable",
            "trend_7d_pct": 0.0,
            "trend_30d": "Stable",
            "trend_30d_pct": 0.0,
            "best_day": "—",
            "follower_count": 0,
            "follower_growth_30d": None,
            "chat_activity": "Low",
            "consistency_score": 0,
            "reliability_score": 0,
            "discovery_score": 0,
        }

    # ------------------------------------------------------------
    # Sub-parsers
    # ------------------------------------------------------------

    @staticmethod
    def _parse_follower_count(soup):
        """Extract follower count from the profile header section.

        The HTML contains: <div>Followers:</div><div class='MiddleSubHeaderItemValue'>12,531,988
        """
        for div in soup.find_all("div"):
            text = div.get_text(strip=True)
            if text.startswith("Followers:"):
                # The number is in the next sibling div.
                value_div = div.find_next_sibling("div")
                if value_div:
                    num_text = value_div.get_text(strip=True).replace(",", "")
                    try:
                        return int(num_text)
                    except ValueError:
                        pass
                # Fallback: extract from the text itself.
                match = re.search(r"Followers:\s*([\d,]+)", text)
                if match:
                    try:
                        return int(match.group(1).replace(",", ""))
                    except ValueError:
                        pass
        return 0

    @staticmethod
    def _parse_ranks(soup):
        """Extract rank data from MiddleSubHeaderItemValue elements.

        The HTML contains patterns like:
          <div class='MiddleSubHeaderItem'>Peak viewer rank:</div>
          <div class='MiddleSubHeaderItemValue'>170th  <span ...>(60)</span>
        """
        ranks = {}
        label_map = {
            "peak viewer rank": "peak_viewer_rank",
            "average viewer rank": "average_viewer_rank",
            "follower rank": "follower_rank",
            "follower gain rank": "follower_gain_rank",
        }

        for div in soup.find_all("div", class_="MiddleSubHeaderItem"):
            label = div.get_text(strip=True).lower().rstrip(":")
            if label in label_map:
                value_div = div.find_next_sibling("div",
                    class_="MiddleSubHeaderItemValue")
                if value_div:
                    rank_text = value_div.get_text(strip=True)
                    # Extract the rank number: "170th" -> 170
                    match = re.match(r"([\d,]+)", rank_text)
                    if match:
                        try:
                            ranks[label_map[label]] = int(
                                match.group(1).replace(",", "")
                            )
                        except ValueError:
                            pass
        return ranks

    @staticmethod
    def _parse_stat_blocks(soup):
        """Extract summary statistics from the stat block divs.

        The HTML contains blocks like:
          <div>Average viewers18,538-7223.7%</div>
          <div>Peak viewers30,723-6.2K16.9%</div>
          <div>Followers gained6,575-75.4K92.0%</div>
        """
        result = {}

        # Map of label patterns to result keys.
        stat_map = {
            "average viewers": "average_viewers",
            "peak viewers": "peak_viewers",
            "hours watched": "hours_watched",
            "followers gained": "follower_growth",
            "hours streamed": "hours_streamed",
            "streams": "streams_count",
        }

        for div in soup.find_all("div"):
            text = div.get_text(strip=True)
            text_lower = text.lower()

            # Skip parent divs that contain multiple stat blocks.
            # Individual stat blocks are short (< 200 chars);
            # parent divs concatenate all stats and are much longer.
            if len(text) > 200:
                continue

            for label, key in stat_map.items():
                if text_lower.startswith(label) and key not in result:
                    # Extract the number right after the label.
                    remainder = text[len(label):]
                    # The first number is the main value.
                    match = re.match(r"\s*([\d,]+\.?\d*)", remainder)
                    if match:
                        try:
                            result[key] = int(match.group(1).replace(",", ""))
                        except ValueError:
                            try:
                                result[key] = float(
                                    match.group(1).replace(",", "")
                                )
                            except ValueError:
                                pass

                    # Try to extract a percentage (growth).
                    # The HTML format concatenates numbers:
                    #   "Average viewers18,538-72233.7%"
                    #   "Followers gained6,575-75.4K92.0%"
                    # Pattern: [main_value]-[change][pct]%
                    # We need to find the last number before % which
                    # is the percentage change.
                    pct_match = re.search(r"(\d+\.?\d*)%\s*$", remainder)
                    if pct_match and key in ("average_viewers", "follower_growth"):
                        try:
                            pct = float(pct_match.group(1))
                            result[f"{key}_pct"] = pct
                            if key == "average_viewers":
                                result["viewer_growth"] = pct
                            elif key == "follower_growth":
                                result["follower_growth_pct"] = pct
                        except ValueError:
                            pass

        debug(f"[SULLYGOOSE] _parse_stat_blocks result: {result}")
        return result

    @staticmethod
    def _parse_summary_paragraphs(soup):
        """Extract data from the summary <p> elements.

        Example paragraphs:
        - "In the past 30 days, xQc has streamed for 200 hours with
          an average of 18,538 viewers and a peak of 30,723."
        - "In the past 30 days, viewers watched xQc for 3,712,321
          hours."
        - "In the past 30 days, xQc has streamed 22 times with an
          average of 9 hours, 3 mins per stream."
        """
        result = {}

        for p in soup.find_all("p"):
            text = p.get_text(strip=True)

            # "streamed for 200 hours"
            m = re.search(r"streamed for (\d[\d,]*) hours", text)
            if m:
                try:
                    result["hours_streamed"] = int(m.group(1).replace(",", ""))
                except ValueError:
                    pass

            # "average of 18,538 viewers"
            m = re.search(r"average of ([\d,]+) viewers", text)
            if m:
                try:
                    result["avg_viewers"] = int(m.group(1).replace(",", ""))
                except ValueError:
                    pass

            # "peak of 30,723"
            m = re.search(r"peak of ([\d,]+)", text)
            if m:
                try:
                    result["peak_viewers"] = int(m.group(1).replace(",", ""))
                except ValueError:
                    pass

            # "streamed 22 times"
            m = re.search(r"streamed (\d+) times", text)
            if m:
                try:
                    result["streams_count"] = int(m.group(1))
                except ValueError:
                    pass

            # "average of 9 hours, 3 mins per stream"
            m = re.search(
                r"average of (\d+) hours?,?\s*(\d+)?\s*min", text
            )
            if m:
                hours = int(m.group(1))
                mins = int(m.group(2)) if m.group(2) else 0
                result["avg_stream_duration"] = round(hours + mins / 60, 1)

            # "watched xQc for 3,712,321 hours"
            m = re.search(r"watched .+? for ([\d,]+) hours", text)
            if m:
                try:
                    result["hours_watched"] = int(m.group(1).replace(",", ""))
                except ValueError:
                    pass

        debug(f"[SULLYGOOSE] _parse_summary_paragraphs result: {result}")
        return result

    @staticmethod
    def _parse_game_info(soup):
        """Extract game/category data from summary paragraphs.

        Example: "xQc's most streamed game/category in the past 30 days
        was Just Chatting for 70 hours, they also streamed 28 other
        game/category."
        """
        result = {}

        for p in soup.find_all("p"):
            text = p.get_text(strip=True)

            # "streamed 28 other game/category"
            m = re.search(r"streamed (\d+) other game", text)
            if m:
                try:
                    # +1 for the main game.
                    result["games_played"] = int(m.group(1)) + 1
                except ValueError:
                    pass

            # "was Just Chatting for 70 hours"
            m = re.search(
                r"was (.+?) for (\d+) hours", text
            )
            if m:
                result["main_game"] = m.group(1)
                try:
                    hours = int(m.group(2))
                    # Calculate percentage from hours_streamed if available.
                    result["_main_game_hours"] = hours
                except ValueError:
                    pass

        # Calculate main_game_pct if we have both values.
        if "_main_game_hours" in result:
            # We'll approximate this later if hours_streamed is known.
            del result["_main_game_hours"]

        return result

    # ================================================================
    # HELPERS
    # ================================================================

    @staticmethod
    def _classify_trend(percent):
        if percent > 10:
            return "Rising"
        if percent < -5:
            return "Declining"
        return "Stable"