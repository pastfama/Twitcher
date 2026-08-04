"""Test the full channel loading flow."""
from twitch_token_manager import get_valid_token
from twitch_api import TwitchAPI

token = get_valid_token()
api = TwitchAPI(access_token=token)

user = api.get_current_user()
print(f"User: {user.get('display_name')} (id={user.get('id')})")

# Test get_followed_channels
try:
    followed = api.get_followed_channels(user.get("id"))
    print(f"Followed: {len(followed) if followed else 0}")
    if followed:
        for ch in followed[:3]:
            print(f"  - {ch.get('broadcaster_login', '?')}: id={ch.get('broadcaster_id', ch.get('id', '?'))}")
except Exception as e:
    print(f"get_followed_channels error: {e}")

# Test get_live_streams
try:
    streams = api.get_live_streams(followed if followed else [])
    print(f"Live streams: {len(streams)}")
    for s in streams[:3]:
        print(f"  - {s.get('user_login')}: {s.get('viewer_count', 0)} viewers")
except Exception as e:
    print(f"get_live_streams error: {e}")

print("Done!")