from .client import TwitchAPIError


class UsersMixin:
    def get_current_user(self):
        data = self.get("/users")
        users = data.get("data", [])
        if not users:
            raise TwitchAPIError("Could not identify Twitch user.")
        user = users[0]
        print()
        print(f"[TWITCH] Logged in as {user.get('display_name')}")
        return user

    def get_user(self, login):
        login = self.normalize_channel(login)
        data = self.get("/users", params={"login": login})
        users = data.get("data", [])
        if not users:
            raise TwitchAPIError(f"Twitch user not found: {login}")
        return users[0]

    def get_user_profile(self, channel):
        channel = self.normalize_channel(channel)
        user = self.get_user(channel)
        return {
            "login": user.get("login", channel),
            "display_name": user.get("display_name", channel),
            "profile_image_url": user.get("profile_image_url", ""),
        }
