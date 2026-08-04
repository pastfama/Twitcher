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


class AnalyticsEngine:
    """
    Central intelligence layer for Twitcher.

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
        fetch_failure_cooldown=300
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

        self.current_stream = None
        self.last_analysis = {}
        self._sully_cache = {}
        self._cache_lock = threading.Lock()
        self._pending_fetches = set()
        self._fetch_failure_cooldown = fetch_failure_cooldown
        self._failed_fetches = {}  # login -> last failure timestamp



    # ========================================================
    # MAIN UPDATE
    # ========================================================

    def update_stream(
        self,
        stream
    ):

        if not stream:

            self.current_stream = None
            self.last_analysis = {}

            return None

        self.current_stream = stream

        analysis = {
            "channel": (
                stream.get("user_name")
                or stream.get("user_login")
                or "Unknown"
            ),

            "viewers": int(
                stream.get(
                    "viewer_count",
                    0
                )
            ),

            "category": (
                stream.get(
                    "game_name"
                )
                or "Unknown"
            ),

            "title": (
                stream.get(
                    "title",
                    ""
                )
            )
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

        self.last_analysis = analysis

        return analysis

    # ========================================================
    # FUTURE INTEL SOURCES
    # ========================================================

    def collect_external_data(self):
        """
        Read-only SullyGoose analytics (cache-only, never network on GUI thread).

        Kicks off a background fetch if the channel is not cached yet, then
        returns whatever is cached right now (possibly nothing).
        """
        if not self.current_stream:
            return {}

        channel_name = (
            self.current_stream.get("user_login")
            or self.current_stream.get("user_name")
            or "unknown"
        ).lower()

        sully = self.sullygoose_for(channel_name)
        if not sully:
            return {}

        return {
            "sullygoose": sully
        }

    def sullygoose_for(self, login, viewers=None):
        """Return cached SullyGoose analytics for *login*, or ``None``.

        NEVER performs network I/O. If the channel is not cached yet,
        schedules a background fetch and returns ``None`` immediately.
        """
        login = str(login or "").strip().lower()
        if not login:
            return None

        with self._cache_lock:
            cached = self._sully_cache.get(login)
            if cached is not None:
                return cached

        self._ensure_async_fetch(login)
        return None

    def _ensure_async_fetch(self, login):
        """Start a daemon thread to fetch *login* stats if not already in-flight."""
        with self._cache_lock:
            if login in self._pending_fetches:
                debug(f"[ANALYTICS] Fetch already pending for '{login}'")
                return
            # Don't retry a recently-failed fetch on every tick.
            last_fail = self._failed_fetches.get(login)
            if last_fail is not None:
                if time.time() - last_fail < self._fetch_failure_cooldown:
                    debug(f"[ANALYTICS] Skipping '{login}' (recent failure, cooldown)")
                    return
            self._pending_fetches.add(login)

        debug(f"[ANALYTICS] Starting background sullygnome fetch for '{login}'")

        def worker():
            try:
                stats = self.sullygoose_api.get_channel_stats(login)
                debug(f"[ANALYTICS] Background fetch complete for '{login}': {stats is not None}")
                if stats:
                    with self._cache_lock:
                        self._sully_cache[login] = stats
                else:
                    # Failed or empty — record failure timestamp for cooldown.
                    with self._cache_lock:
                        self._failed_fetches[login] = time.time()
            except Exception as exc:
                debug(f"[ANALYTICS] Background fetch error for '{login}': {exc}")
                with self._cache_lock:
                    self._failed_fetches[login] = time.time()
            finally:
                with self._cache_lock:
                    self._pending_fetches.discard(login)

        thread = threading.Thread(
            target=worker,
            name=f"SullyGoose-{login}",
            daemon=True,
        )
        thread.start()

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

        return self.last_analysis or {}