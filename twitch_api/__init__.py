from .auth import AuthMixin
from .channels import ChannelsMixin
from .chat import ChatMixin
from .clips import ClipsMixin
from .client import TwitchAPIBase, TwitchAPIError
from .eventsub import EventSubMixin
from .rewards import RewardsMixin
from .streams import StreamsMixin
from .users import UsersMixin


class TwitchAPI(TwitchAPIBase):
    def __init__(self):
        super().__init__()

    get_app_access_token = AuthMixin.get_app_access_token
    get_user_access_token = AuthMixin.get_user_access_token
    refresh_user_token = AuthMixin.refresh_user_token
    get_eventsub_user_headers = AuthMixin.get_eventsub_user_headers

    get_current_user = UsersMixin.get_current_user
    get_user = UsersMixin.get_user
    get_user_profile = UsersMixin.get_user_profile

    get_followed_channels = StreamsMixin.get_followed_channels
    get_live_streams = StreamsMixin.get_live_streams
    get_stream_info = StreamsMixin.get_stream_info

    get_channel_rewards = RewardsMixin.get_channel_rewards

    subscribe_to_raid = EventSubMixin.subscribe_to_raid
    subscribe_to_stream = EventSubMixin.subscribe_to_stream


__all__ = ["TwitchAPI", "TwitchAPIError", "TwitchAPIBase"]
