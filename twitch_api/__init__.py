"""Twitch API client package.

TwitchAPI is the main entry point.  It delegates to the
twitchAPI library via TwitchAPIAdapter when available, and falls
back to the legacy requests-based mixin methods when the library
is not installed.
"""

from .auth import AuthMixin
from .channels import ChannelsMixin
from .chat import ChatMixin
from .clips import ClipsMixin
from .client import TwitchAPIBase, TwitchAPIError
from .eventsub import EventSubMixin
from .games import GamesMixin
from .rewards import RewardsMixin
from .streams import StreamsMixin
from .users import UsersMixin

# Try to import the twitchAPI-backed adapter (optional)
try:
    from .adapter import TwitchAPIAdapter
    _HAS_TWITCHAPI = True
except ImportError:
    TwitchAPIAdapter = None
    _HAS_TWITCHAPI = False


class TwitchAPI(TwitchAPIBase):
    """Synchronous Twitch API client.

    When twitchAPI is installed, delegates core data methods to
    TwitchAPIAdapter.  Otherwise falls back to legacy mixin methods.
    """

    def __init__(self, access_token=None):
        super().__init__(access_token=access_token)
        if _HAS_TWITCHAPI:
            self._adapter = TwitchAPIAdapter(access_token=self.access_token)
        else:
            self._adapter = None

    # -- Adapter-delegated methods (with legacy fallback) -----------

    def get_current_user(self):
        if self._adapter:
            return self._adapter.get_current_user()
        return UsersMixin.get_current_user(self)

    def get_user(self, login):
        if self._adapter:
            return self._adapter.get_user(login)
        return UsersMixin.get_user(self, login)

    def get_user_profile(self, login):
        if self._adapter:
            return self._adapter.get_user_profile(login)
        return UsersMixin.get_user_profile(self, login)

    def get_followed_channels(self, user_id):
        if self._adapter:
            return self._adapter.get_followed_channels(user_id)
        return StreamsMixin.get_followed_channels(self, user_id)

    def get_live_streams(self, followed_channels):
        if self._adapter:
            return self._adapter.get_live_streams(followed_channels)
        return StreamsMixin.get_live_streams(self, followed_channels)

    def get_stream_info(self, channel):
        if self._adapter:
            return self._adapter.get_stream_info(channel)
        return StreamsMixin.get_stream_info(self, channel)

    def get_game_thumbnail(self, game_id):
        if self._adapter:
            return self._adapter.get_game_thumbnail(game_id)
        return GamesMixin.get_game_thumbnail(self, game_id)

    def get_channel_rewards(self, broadcaster_id):
        if self._adapter:
            return self._adapter.get_channel_rewards(broadcaster_id)
        return RewardsMixin.get_channel_rewards(self, broadcaster_id)

    def get_user_access_token(self, user_id="", force_verify=False):
        if self._adapter:
            return self._adapter.get_user_access_token(
                user_id=user_id, force_verify=force_verify
            )
        return AuthMixin.get_user_access_token(self)

    def refresh_user_token(self, refresh_token):
        if self._adapter:
            return self._adapter.refresh_user_token(refresh_token)
        return AuthMixin.refresh_user_token(self, refresh_token)

    # -- Legacy mixin methods (always available) --------------------

    get_app_access_token = AuthMixin.get_app_access_token
    get_eventsub_user_headers = AuthMixin.get_eventsub_user_headers
    subscribe_to_raid = EventSubMixin.subscribe_to_raid
    subscribe_to_stream = EventSubMixin.subscribe_to_stream

    def close(self):
        if self._adapter:
            self._adapter.close()


__all__ = ["TwitchAPI", "TwitchAPIError", "TwitchAPIBase"]
if _HAS_TWITCHAPI:
    __all__.append("TwitchAPIAdapter")
