"""Central analytics engine — combines local + external intelligence.

Data sources:
- ViewerTracker (local realtime)
- Twitch API (live stream data)
- SullyGooseAPI (sullygnome.com analytics, tokenless)

IMPORTANT: All network I/O (sullygnome scraping) happens on daemon
background threads. The GUI thread only ever reads the cache, so
update_stream() never blocks the UI.
"""

import threading
import time

from logger import debug
from core.db import get_sg, store_sg, list_sg_channels

# Maximum number of failed-fetch entries to keep before pruning.
_MAX_FAILED_FETCHES = 200


class AnalyticsEngine:
    """Central intelligence layer for Watcher.

    Data sources:
    - ViewerTracker (local realtime)
    - Twitch API (live stream data)
    - SullyGooseAPI (sullygnome.com analytics, tokenless)

    IMPORTANT: All network I/O (sullygnome scraping) happens on daemon
    background threads. The GUI thread only ever reads the cache, so
    update_stream() never blocks the UI.
    """

    def __init__(
        self,
        viewer_tracker=None,
        sullygoose_api=None,
        fetch_failure_cooldown=60,
        on_analytics_updated=None
    ):

        self.viewer_tracker = viewer_tracker

        self.sources = []

        if viewer_tracker:
            self.sources.append(
                viewer_tracker
            )

        if sullygoose_api is None:
            from sullygoose_api import SullyGooseAPI
            sullygoose_api = SullyGooseAPI()

        self.sullygoose_api = sullygoose_api

        self._stream_lock = threading.Lock()
        self.current_stream = None
        self.last_analysis = {}
        self._sully_cache = {}
        self._cache_lock = threading.Lock()
        self._pending_fetches = set()
        self._fetch_failure_cooldown = fetch_failure_cooldown
        self._failed_fetches = {}  # login -> last failure timestamp
        self._on_analytics_updated = on_analytics_updated

        # Pre-load cached SG data from database.
        self._load_cached_data()



    def _load_cached_data(self):
        """Load cached SullyGoose data from the database into memory."""
        with self._cache_lock:
            cached_channels = list_sg_channels()
            for entry in cached_channels:
                login = entry.get("login")
                platform = entry.get("platform", "twitch")
                if login:
                    data = get_sg(login, platform=platform)
                    if data:
                        self._sully_cache[f"{platform}:{login}"] = data
            debug(f"[ANALYTICS] Loaded {len(cached_channels)} channels from DB")

    def update_stream(
        self,
        stream
    ):

        if not stream:

            with self._stream_lock:
                self.current_stream = None
                self.last_analysis = {}

            return None

        with self._stream_lock:
            self.current_stream = stream

        # Support field names from all platforms:
        # - Twitch: user_name, user_login, game_name, viewer_count
        # - Kick: channel, game, viewer_count
        # - YouTube: channel, game, viewer_count
        platform = stream.get("platform", "twitch")

        channel_name = (
            stream.get("user_name")
            or stream.get("user_login")
            or stream.get("channel")
            or "Unknown"
        )

        category = (
            stream.get("game_name")
            or stream.get("game")
            or "Unknown"
        )

        analysis = {
            "channel": channel_name,
            "platform": platform,
            "viewers": int(
                stream.get(
                    "viewer_count",
                    0
                )
            ),
            "category": category,
            "title": (
                stream.get(
                    "title",
                    ""
                )
            ),
        }

        # ------------------------------------------------
        # Local realtime intelligence
        # ------------------------------------------------

        if self.viewer_tracker:

            viewer_data = (
                self.viewer_tracker.update_stream(
                    stream
                )
            )

            if viewer_data:

                analysis.update(
                    viewer_data
                )

        # ------------------------------------------------
        # External intelligence
        # ------------------------------------------------

        external = self.collect_external_data()

        if external:

            analysis.update(
                external
            )

        # ------------------------------------------------
        # Derive momentum status from SullyGoose growth
        # ------------------------------------------------

        with self._stream_lock:
            sully = analysis.get("sullygoose", {}) or {}
        if sully:
            growth = sully.get("viewer_growth")
            if growth is None:
                growth = 0
            analysis["percent"] = growth
            if growth > 10:
                analysis["status"] = "Rising"
            elif growth < -5:
                analysis["status"] = "Declining"
            else:
                analysis["status"] = "Stable"

        # ------------------------------------------------
        # Final score
        # ------------------------------------------------

        analysis["score"] = (
            self.calculate_score(
                analysis
            )
        )

        with self._stream_lock:
            self.last_analysis = analysis

        return analysis

    # ========================================================
    # FUTURE INTEL SOURCES
    # ========================================================

    def collect_external_data(self):
        """Read-only SullyGoose analytics (cache-only, never network on GUI thread).

        Kicks off a background fetch if the channel is not cached yet, then
        returns whatever is cached right now (possibly nothing).
        """
        with self._stream_lock:
            current = self.current_stream

        if not current:
            return {}

        channel_name = (
            current.get("user_login")
            or current.get("user_name")
            or current.get("channel")
            or "unknown"
        ).lower()

        platform = current.get("platform", "twitch")
        sully = self.sullygoose_for(channel_name, platform=platform)
        if not sully:
            return {}

        return {
            "sullygoose": sully
        }

    def sullygoose_for(self, login, viewers=None, platform="twitch"):
        """Return cached SullyGoose analytics for *login*, or ``None``.

        NEVER performs network I/O. If the channel is not cached yet,
        schedules a background fetch and returns ``None`` immediately.
        """
        login = str(login or "").strip().lower()
        if not login:
            return None

        cache_key = f"{platform}:{login}"

        with self._cache_lock:
            cached = self._sully_cache.get(cache_key)
            if cached is not None:
                return cached

        self._ensure_async_fetch(login, platform=platform)
        return None

    def _ensure_async_fetch(self, login, platform="twitch"):
        """Start a daemon thread to fetch *login* stats if not already in-flight."""
        fetch_key = f"{platform}:{login}"
        with self._cache_lock:
            if fetch_key in self._pending_fetches:
                debug(f"[ANALYTICS] Fetch already pending for '{login}' ({platform})")
                return
            # Don't retry a recently-failed fetch on every tick.
            last_fail = self._failed_fetches.get(fetch_key)
            if last_fail is not None:
                if time.time() - last_fail < self._fetch_failure_cooldown:
                    debug(f"[ANALYTICS] Skipping '{login}' ({platform}) (recent failure, cooldown)")
                    return
            self._pending_fetches.add(fetch_key)

        debug(f"[ANALYTICS] Starting background sullygnome fetch for '{login}' ({platform})")

        def worker():
            try:
                stats = self.sullygoose_api.get_channel_stats(login, platform=platform)
                debug(f"[ANALYTICS] Background fetch complete for '{login}': {stats is not None}")
                if stats:
                    with self._cache_lock:
                        self._sully_cache[fetch_key] = stats
                    store_sg(login, stats, platform=platform)
                    debug(f"[ANALYTICS] Stored SullyGoose data for '{login}' ({platform}): {len(stats)} metrics")
                    if self._on_analytics_updated:
                        with self._stream_lock:
                            current = self.current_stream
                            last = dict(self.last_analysis)
                        if current is None:
                            current = {"user_login": login, "user_name": login}
                        current_login = (
                            (current.get("user_login") or current.get("user_name") or "")
                            .lower().strip()
                        )
                        if current_login and login.lower().strip() != current_login:
                            debug(f"[ANALYTICS] Fetch for '{login}' — current is '{current_login}', skipping UI update")
                        else:
                            debug(f"[ANALYTICS] Fetch for '{login}' — triggering UI update ({len(stats)} metrics)")
                            stream = current
                            analysis = dict(last) if last else {
                                "channel": stream.get("user_name") or stream.get("user_login") or login,
                                "viewers": int(stream.get("viewer_count", 0)),
                                "category": stream.get("game_name") or "Unknown",
                                "title": stream.get("title", ""),
                            }
                            analysis["sullygoose"] = stats
                            analysis["score"] = self.calculate_score(analysis)
                            growth = stats.get("viewer_growth") or 0
                            analysis["percent"] = growth
                            analysis["status"] = (
                                "Rising" if growth > 10
                                else ("Declining" if growth < -5 else "Stable")
                            )
                            debug(f"[ANALYTICS] Calling _on_analytics_updated for '{login}'")
                            self._on_analytics_updated(stream, analysis)
                            debug(f"[ANALYTICS] _on_analytics_updated returned for '{login}'")
                else:
                    debug(f"[ANALYTICS] Fetch returned no data for '{login}'")
                    with self._cache_lock:
                        self._failed_fetches[fetch_key] = time.time()
                        self._prune_failed_fetches()
            except Exception as exc:
                debug(f"[ANALYTICS] Background fetch error for '{login}' ({platform}): {exc}")
                with self._cache_lock:
                    self._failed_fetches[fetch_key] = time.time()
                    self._prune_failed_fetches()
            finally:
                with self._cache_lock:
                    self._pending_fetches.discard(fetch_key)

        thread = threading.Thread(
            target=worker,
            name=f"SullyGoose-{login}",
            daemon=True,
        )
        thread.start()

    def _prune_failed_fetches(self):
        """Remove oldest entries if _failed_fetches exceeds the cap."""
        if len(self._failed_fetches) <= _MAX_FAILED_FETCHES:
            return
        # Sort by failure time and keep the most recent half.
        sorted_logins = sorted(
            self._failed_fetches, key=self._failed_fetches.get
        )
        to_remove = sorted_logins[: len(sorted_logins) // 2]
        for login in to_remove:
            self._failed_fetches.pop(login, None)

    def fetch_all_live_channels(self, channels):
        """Fetch SullyGoose data for all live channels.

        This method does NOT block — it checks the cache first and
        starts background fetches for any uncached channels.
        """
        if not channels:
            return

        for stream in channels:
            login = (
                stream.get("user_login")
                or stream.get("user_name")
                or stream.get("channel")
                or ""
            ).lower()
            platform = stream.get("platform", "twitch")
            if login:
                self._ensure_async_fetch(login, platform=platform)

    # ========================================================
    # STREAM QUALITY SCORE
    # ========================================================

    def calculate_score(
        self,
        analysis
    ):

        score = 0

        viewers = analysis.get(
            "viewers",
            0
        )

        if viewers >= 10000:
            score += 40

        elif viewers >= 1000:
            score += 25

        elif viewers >= 100:
            score += 10

        momentum = analysis.get(
            "status",
            ""
        )

        if "Spike" in momentum:
            score += 20

        elif "Rising" in momentum:
            score += 10

        # SullyGoose Intelligence boost
        sullygoose = analysis.get("sullygoose", {}) or {}
        if sullygoose:
            growth = sullygoose.get("viewer_growth")
            if growth is None:
                growth = 0
            if growth > 50:
                score += 20
            elif growth > 10:
                score += 10

            rank = sullygoose.get("category_rank", 150) or 150
            if rank <= 10:
                score += 20
            elif rank <= 50:
                score += 10

        return min(
            score,
            100
        )

    # ========================================================
    # ADD EXTERNAL DATA
    # ========================================================

    def add_external_data(
        self,
        data
    ):

        if not data:
            return

        if self.last_analysis is None:

            self.last_analysis = {}

        self.last_analysis.update(
            data
        )

    # ========================================================
    # RESULT
    # ========================================================

    def get_analysis(self):

        with self._stream_lock:
            return dict(self.last_analysis) or {}
