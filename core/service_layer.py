"""Service layer — isolates all API calls from UI code.

Every network call goes through this layer.  UI code never touches
``self.api`` directly.  This makes the API surface testable and
the data flow traceable.

Usage::

    services = ServiceLayer(api, platform_manager)

    # Fetch live channels (returns list of stream dicts)
    channels = await services.fetch_live_channels(user_id)

    # Fetch stream info for a single channel
    stream = await services.fetch_stream_info(channel, platform)

    # Fetch SullyGoose analytics
    stats = await services.fetch_sg_analytics(channel, platform)
"""

from logger import debug


class ServiceLayer:
    """Centralized API access for all data fetching.

    Wraps the Twitch API, platform manager, and SullyGoose API
    behind a clean interface.  All methods are synchronous (they
    block on I/O) and should be called from background threads
    via ``run_in_background()``.
    """

    def __init__(self, api, platform_manager=None, analytics_engine=None):
        self.api = api
        self.platforms = platform_manager
        self.analytics_engine = analytics_engine

    def fetch_live_channels(self, user_id, watchlist=None):
        """Fetch all live channels from all platforms.

        Returns a list of stream dicts sorted by viewer_count descending.
        Each dict has at minimum: user_login, user_name, viewer_count, platform.
        """
        all_live = []

        # Twitch — followed channels
        try:
            followed = self.api.get_followed_channels(user_id)
            twitch_live = self.api.get_live_streams(followed)
            for stream in twitch_live:
                stream["platform"] = "twitch"
            all_live.extend(twitch_live)
        except Exception as e:
            debug(f"[SERVICE] Twitch fetch error: {e}")

        # Kick + YouTube — from watchlist
        if watchlist and self.platforms:
            try:
                non_twitch = self.platforms.get_live_streams(watchlist)
                all_live.extend(non_twitch)
            except Exception as e:
                debug(f"[SERVICE] Platform manager error: {e}")

        # Sort by viewer count descending
        all_live.sort(key=lambda s: s.get("viewer_count", 0), reverse=True)
        return all_live

    def fetch_stream_info(self, channel, platform="twitch"):
        """Fetch live stream info for a single channel.

        Returns a stream dict with viewer_count, title, game_name, etc.
        Returns None if the channel is not live or the fetch fails.
        """
        try:
            if platform == "twitch":
                return self.api.get_stream_info(channel)
            if self.platforms:
                return self.platforms.get_stream_info(platform, channel)
        except Exception as e:
            debug(f"[SERVICE] Stream info error for {channel}: {e}")
        return None

    def fetch_user_profile(self, login):
        """Fetch a user's profile (avatar URL, display name).

        Returns a dict with at least 'profile_image_url'.
        """
        try:
            return self.api.get_user_profile(login)
        except Exception as e:
            debug(f"[SERVICE] Profile fetch error for {login}: {e}")
            return {}

    def fetch_sg_analytics(self, channel, platform="twitch"):
        """Fetch SullyGoose analytics for a channel.

        Returns a stats dict or None.  The analytics engine maintains
        its own cache — this method triggers a background fetch if needed.
        """
        if not self.analytics_engine:
            return None
        try:
            return self.analytics_engine.sullygoose_for(channel, platform=platform)
        except Exception as e:
            debug(f"[SERVICE] SG fetch error for {channel}: {e}")
            return None