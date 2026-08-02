import requests

from .client import TwitchAPIError


class EventSubMixin:
    def subscribe_to_raid(self, broadcaster_user_id, session_id, direction="to"):
        broadcaster_user_id = str(broadcaster_user_id)
        if direction == "from":
            condition = {"from_broadcaster_user_id": broadcaster_user_id}
        else:
            condition = {"to_broadcaster_user_id": broadcaster_user_id}
        payload = {
            "type": "channel.raid",
            "version": "1",
            "condition": condition,
            "transport": {"method": "websocket", "session_id": session_id},
        }
        response = requests.post(
            "https://api.twitch.tv/helix/eventsub/subscriptions",
            headers=self.get_eventsub_user_headers(),
            json=payload,
            timeout=20,
        )
        if response.status_code not in (200, 202):
            raise TwitchAPIError(f"Twitch raid subscription failed:\nHTTP {response.status_code}\n{response.text}")
        print()
        print("[TWITCH] Raid EventSub subscription created successfully.")
        return response.json()

    def subscribe_to_stream(self, broadcaster_user_id, session_id):
        payload = {
            "type": "stream.online",
            "version": "1",
            "condition": {"broadcaster_user_id": str(broadcaster_user_id)},
            "transport": {"method": "websocket", "session_id": session_id},
        }
        response = requests.post(
            "https://api.twitch.tv/helix/eventsub/subscriptions",
            headers=self.get_eventsub_user_headers(),
            json=payload,
            timeout=20,
        )
        if response.status_code not in (200, 202):
            raise TwitchAPIError(f"Twitch stream subscription failed:\nHTTP {response.status_code}\n{response.text}")
        return response.json()
