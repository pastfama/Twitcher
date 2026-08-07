"""Third-party Twitch emote resolver.

Fetches and caches emote sets from FrankerFaceZ (FFZ), BetterTTV (BTTV),
and 7TV for a given channel.  Emote codes are mapped to image URLs so
that ``ChatWidget.display_message`` can render them inline.

Usage::

    resolver = EmoteResolver()
    resolver.update(channel_id)          # fetches emote sets (async-safe)
    url = resolver.resolve("PogChamp")   # returns CDN URL or None
"""

import time
import threading

import requests

from logger import debug


# Cache TTL in seconds — refresh emote sets every 10 minutes.
_CACHE_TTL = 600


class EmoteResolver:
    """Resolve third-party emote codes to image URLs for a channel."""

    def __init__(self):
        self._lock = threading.Lock()
        # code → url
        self._emotes = {}
        # channel_id → last fetch timestamp
        self._last_fetch = 0
        self._current_channel = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, channel_id):
        """Fetch emote sets for *channel_id* from all providers.

        This is a blocking call — run it in a background thread.
        If the channel hasn't changed and the cache is still fresh,
        the fetch is skipped.
        """
        channel_id = str(channel_id or "").strip().lower()
        if not channel_id:
            return

        now = time.time()
        with self._lock:
            if (
                self._current_channel == channel_id
                and (now - self._last_fetch) < _CACHE_TTL
            ):
                return  # Cache is still fresh.

        emotes = {}
        self._fetch_bttv(channel_id, emotes)
        self._fetch_ffz(channel_id, emotes)
        self._fetch_7tv(channel_id, emotes)

        with self._lock:
            self._emotes = emotes
            self._current_channel = channel_id
            self._last_fetch = time.time()

        debug(
            f"[EMOTES] Loaded {len(emotes)} third-party emotes "
            f"for #{channel_id}"
        )

    def resolve(self, code):
        """Return the image URL for *code*, or ``None`` if unknown."""
        with self._lock:
            return self._emotes.get(code)

    def clear(self):
        """Clear the emote cache."""
        with self._lock:
            self._emotes.clear()
            self._current_channel = None
            self._last_fetch = 0

    # ------------------------------------------------------------------
    # Provider fetchers
    # ------------------------------------------------------------------

    def _fetch_bttv(self, channel_id, emotes):
        """Fetch BetterTTV emotes (shared + channel)."""
        try:
            resp = requests.get(
                f"https://api.bttv.com/3/cached/channels/twitch/{channel_id}",
                timeout=5,
            )
            if resp.status_code != 200:
                return
            data = resp.json()
            for emote in data.get("sharedEmotes", []) + data.get("channelEmotes", []):
                code = emote.get("code", "")
                # BTTV CDN: https://cdn.bttv.net/emote/{id}/2x
                emote_id = emote.get("id", "")
                if code and emote_id:
                    emotes[code] = f"https://cdn.bttv.net/emote/{emote_id}/2x"
        except Exception as exc:
            debug(f"[EMOTES] BTTV fetch error: {exc}")

    def _fetch_ffz(self, channel_id, emotes):
        """Fetch FrankerFaceZ emotes for the channel."""
        try:
            # First resolve the FFZ room ID from the Twitch channel name.
            resp = requests.get(
                f"https://api.frankerfacez.com/v1/set/{channel_id}",
                timeout=5,
            )
            if resp.status_code != 200:
                return
            data = resp.json()
            for set_data in data.get("sets", {}).values():
                for emote in set_data.get("emoticons", []):
                    code = emote.get("name", "")
                    # FFZ CDN: use 2x variant if available.
                    urls = emote.get("urls", {})
                    url = urls.get("2") or urls.get("1") or ""
                    if code and url:
                        # FFZ URLs are relative; prepend the CDN host.
                        if url.startswith("//"):
                            url = "https:" + url
                        emotes[code] = url
        except Exception as exc:
            debug(f"[EMOTES] FFZ fetch error: {exc}")

    def _fetch_7tv(self, channel_id, emotes):
        """Fetch 7TV emotes for the channel."""
        try:
            resp = requests.get(
                f"https://7tv.io/v3/users/twitch/{channel_id}",
                timeout=5,
            )
            if resp.status_code != 200:
                return
            data = resp.json()
            for emote in data.get("emote_set", {}).get("emotes", []):
                code = emote.get("name", "")
                # 7TV CDN: https://cdn.7tv.app/emote/{id}/2x
                emote_id = emote.get("id", "")
                if code and emote_id:
                    emotes[code] = f"https://cdn.7tv.app/emote/{emote_id}/2x"
        except Exception as exc:
            debug(f"[EMOTES] 7TV fetch error: {exc}")