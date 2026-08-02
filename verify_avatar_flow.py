import io
import requests
from PIL import Image

from mainmenu.current_watching import CurrentWatchingPanel
from mainmenu.main import MainMenu


class FakeResponse:
    def __init__(self, data, status_code=200):
        self.content = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeAPI:
    def __init__(self):
        self.calls = []

    def get_user_profile(self, login):
        self.calls.append(login)
        return {"profile_image_url": "https://example.com/avatar.png"}


menu = object.__new__(MainMenu)
menu.avatar_cache = {}
menu.log = lambda *args, **kwargs: None
menu.api = FakeAPI()
enriched = menu.enrich_stream_with_avatar({"user_login": "MyStreamer"})
assert enriched["avatar_url"] == "https://example.com/avatar.png"

img = Image.new('RGB', (10, 10), color='red')
buf = io.BytesIO()
img.save(buf, format='PNG')
data = buf.getvalue()

orig_get = requests.get
requests.get = lambda url, timeout=10: FakeResponse(data)

panel = CurrentWatchingPanel()
panel.set_stream({"user_name": "Example", "viewer_count": 123, "game_name": "Test", "title": "Stream title", "started_at": "2024-01-01T00:00:00Z", "avatar_url": "https://example.com/avatar.png"})
pixmap = panel.avatar_label.pixmap()
assert pixmap is not None and not pixmap.isNull()
print('avatar-flow-ok')
requests.get = orig_get
