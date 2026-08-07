import time
import requests

from .client import TWITCH_OAUTH_TOKEN_URL, TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET, TwitchAPIError

MAX_RETRIES = 3
RETRY_DELAY = 2


class AuthMixin:
    def get_app_access_token(self):
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.post(
                    TWITCH_OAUTH_TOKEN_URL,
                    params={
                        "client_id": TWITCH_CLIENT_ID,
                        "client_secret": TWITCH_CLIENT_SECRET,
                        "grant_type": "client_credentials",
                    },
                    timeout=20,
                )
                if response.status_code != 200:
                    raise TwitchAPIError(
                        f"Could not obtain Twitch app access token.\n\n"
                        f"HTTP {response.status_code}\n{response.text}"
                    )
                token = (response.json().get("access_token", "") or "").strip()
                if not token:
                    raise TwitchAPIError("Twitch did not return an app access token.")
                return token
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_error = exc
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
            except TwitchAPIError:
                raise
        raise TwitchAPIError(
            f"Failed to obtain Twitch app access token after {MAX_RETRIES} attempts.\n\n"
            f"Last error: {last_error}"
        )

    def get_user_access_token(self):
        from twitch_token_manager import get_valid_token
        return get_valid_token()

    def refresh_user_token(self):
        return self.get_user_access_token()

    def get_eventsub_user_headers(self):
        return {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
