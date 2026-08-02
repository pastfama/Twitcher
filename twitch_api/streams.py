import requests

from .client import TWITCH_API, TwitchAPIError


class StreamsMixin:
    def get_followed_channels(self, user_id):
        channels = []
        cursor = None
        while True:
            params = {"user_id": str(user_id), "first": 100}
            if cursor:
                params["after"] = cursor
            data = self.get("/channels/followed", params=params)
            channels.extend(data.get("data", []))
            cursor = data.get("pagination", {}).get("cursor")
            if not cursor:
                break
        return channels

    def get_live_streams(self, followed_channels):
        live_streams = []
        for start in range(0, len(followed_channels), 100):
            batch = followed_channels[start:start + 100]
            params = []
            for channel in batch:
                broadcaster_id = channel.get("broadcaster_id") or channel.get("broadcaster_user_id")
                if broadcaster_id:
                    params.append(("user_id", broadcaster_id))
            if not params:
                continue
            response = requests.get(
                f"{TWITCH_API}/streams",
                headers=self.headers,
                params=params,
                timeout=20,
            )
            if response.status_code != 200:
                raise TwitchAPIError(f"Could not retrieve live streams:\nHTTP {response.status_code}\n{response.text}")
            live_streams.extend(response.json().get("data", []))
        return live_streams

    def get_stream_info(self, channel):
        channel = self.normalize_channel(channel)
        data = self.get("/streams", params={"user_login": channel})
        streams = data.get("data", [])
        return streams[0] if streams else None
