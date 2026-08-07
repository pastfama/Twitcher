"""Test live streams API call."""
from twitch_token_manager import get_valid_token
from twitch_api import TwitchAPI

token = get_valid_token()
api = TwitchAPI(access_token=token)

print(f"Token: {token[:20]}...")

user = api.get_current_user()
print(f"User: {user.get('display_name')}")
print(f"User ID: {user.get('id')}")

followed = api.get_followed_channels(user.get("id"))
print(f"Followed channels: {len(followed)}")

# Print first few followed channels
for ch in followed[:5]:
    print(f"  - {ch.get('broadcaster_login', ch.get('login', '?'))} (broadcaster_id={ch.get('broadcaster_id', ch.get('id', '?'))})")

streams = api.get_live_streams(followed)
print(f"Live streams: {len(streams)}")

for s in streams[:5]:
    print(f"  - {s.get('user_login')}: {s.get('viewer_count', 0)} viewers")

print("Done!")