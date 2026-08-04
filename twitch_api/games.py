"""Twitch API games mixin — game/category metadata."""


class GamesMixin:
    def get_game_thumbnail(self, game_id, size=80):
        """Return a resized box-art URL for *game_id*, or empty string."""
        if not game_id:
            return ""
        try:
            games_data = self.get(
                "/games",
                params={"id": str(game_id)},
            )
            games = games_data.get("data", [])
            if not games:
                return ""
            raw = games[0].get("box_art_url", "")
            if not raw:
                return ""
            return raw.replace("{width}", str(size)).replace("{height}", str(size))
        except Exception:
            return ""