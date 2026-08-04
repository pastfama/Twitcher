from api import TwitchAPI
from mainmenu.main import MainMenu


class FakeAPI:
    def __init__(self):
        self.calls = []

    def get_user_profile(self, login):
        self.calls.append(login)
        return {"profile_image_url": "https://example.com/avatar.png"}


def test_get_user_profile_returns_profile_image_url():
    api = object.__new__(TwitchAPI)
    api.normalize_channel = staticmethod(TwitchAPI.normalize_channel)
    api.get_user = lambda channel: {
        "login": channel,
        "display_name": channel.capitalize(),
        "profile_image_url": "https://example.com/avatar.png",
    }

    profile = api.get_user_profile("MyStreamer")

    assert profile["login"] == "mystreamer"
    assert profile["profile_image_url"] == "https://example.com/avatar.png"


def test_main_menu_enriches_stream_with_avatar_url():
    menu = object.__new__(MainMenu)
    menu.avatar_cache = {}
    menu.log = lambda *args, **kwargs: None
    menu.api = FakeAPI()

    enriched = menu.enrich_stream_with_avatar({"user_login": "MyStreamer"})

    assert enriched["avatar_url"] == "https://example.com/avatar.png"
    assert menu.avatar_cache["mystreamer"] == "https://example.com/avatar.png"
    assert menu.api.calls == ["mystreamer"]
