"""Async stream enrichment: avatar URL + game thumbnail URL resolution.

:class:`StreamEnricher` takes a raw Twitch stream dict and resolves two
pieces of metadata that the API response sometimes omits:

* ``avatar_url``        — the broadcaster's profile image.
* ``game_thumbnail``    — the box-art URL for the game/category.

Both resolutions are cached (avatar by login, game by ``game_id``) and
performed on a background thread so the GUI never stalls.
"""

from core import run_in_background


class StreamEnricher:
    """Resolve avatar and game-thumbnail URLs for a stream dict.

    All Twitch API calls happen on a background thread via
    :func:`workers.run_in_background`.  Results are delivered through
    the *on_complete* callback on the GUI thread.
    """

    #: Box-art width/height (px) — matches the 80×80 game-thumbnail QLabel.
    GAME_THUMBNAIL_SIZE = 80

    def __init__(self, api=None, log=None):
        self.api = api
        self._log = log or (lambda *a, **kw: None)
        self._avatar_cache = {}       # login -> avatar_url
        self._game_cache = {}         # game_id -> box_art_url

    # ---------------------------------------------------------- public

    def enrich(self, stream, on_complete):
        """Asynchronously enrich *stream* and call *on_complete* on the GUI thread.

        *on_complete* receives the enriched dict, or ``None`` if
        *stream* was falsy or enrichment raised an exception.
        """
        if not stream:
            on_complete(None)
            return

        run_in_background(
            lambda: self._enrich_sync(stream),
            on_complete,
            lambda msg: self._on_error(msg, on_complete),
        )

    # ---------------------------------------------------------- core logic

    def _enrich_sync(self, stream):
        """Synchronous enrichment — runs on a background thread.

        Returns a *copy* of *stream* with ``avatar_url`` and/or
        ``game_thumbnail`` populated.
        """
        enriched = dict(stream)

        self._resolve_avatar(enriched)
        self._resolve_game_thumbnail(enriched)

        return enriched

    def _resolve_avatar(self, enriched):
        login = self._extract_login(enriched)
        if not login:
            return

        # Already present in the stream data — nothing to do.
        if enriched.get("avatar_url"):
            return

        # Check URL cache first.
        avatar_url = self._avatar_cache.get(login)
        if avatar_url is None:
            avatar_url = self._fetch_avatar_url(login)
            if avatar_url:
                self._avatar_cache[login] = avatar_url

        if avatar_url:
            enriched["avatar_url"] = avatar_url

    def _resolve_game_thumbnail(self, enriched):
        game_id = enriched.get("game_id")
        if not game_id:
            return

        # Already present in the stream data — nothing to do.
        if enriched.get("game_thumbnail"):
            return

        game_id = str(game_id)
        box_art = self._game_cache.get(game_id)

        if box_art is None:
            box_art = self._fetch_game_thumbnail(game_id)
            if box_art:
                self._game_cache[game_id] = box_art

        if box_art:
            enriched["game_thumbnail"] = box_art

    # ---------------------------------------------------------- API calls

    def _fetch_avatar_url(self, login):
        """Return the profile image URL for *login*, or empty string."""
        if not self.api:
            return ""
        try:
            profile = self.api.get_user_profile(login)
            return str(
                profile.get("profile_image_url", "")
            ).strip()
        except Exception as exc:
            self._log(f"Could not fetch avatar for {login}: {exc}")
            return ""

    def _fetch_game_thumbnail(self, game_id):
        """Return a resized box-art URL for *game_id*, or empty string."""
        if not self.api:
            return ""
        try:
            return self.api.get_game_thumbnail(game_id, self.GAME_THUMBNAIL_SIZE)
        except Exception as exc:
            self._log(f"Could not fetch game thumbnail: {exc}")
            return ""

    # ---------------------------------------------------------- helpers

    @staticmethod
    def _extract_login(stream):
        return str(
            stream.get("user_login")
            or stream.get("user_name")
            or ""
        ).strip().lower()

    def _on_error(self, message, on_complete):
        self._log(f"Stream enrichment error: {message}")
        on_complete(None)
