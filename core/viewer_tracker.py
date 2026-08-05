from collections import deque
from datetime import datetime


class ViewerTracker:
    """
    Tracks viewer count changes for multiple channels
    and calculates stream momentum.

    Channels are keyed by ``(platform, channel)`` so the same
    channel name on different platforms does not collide.
    """

    def __init__(self, max_history=20):

        self.max_history = max_history

        self.channels = {}


    def _key(self, stream):
        """Return a (platform, channel) key for a stream dict."""
        platform = str(stream.get("platform") or "twitch").lower().strip()
        channel = (
            stream.get("user_login")
            or stream.get("user_name")
            or stream.get("channel")
            or ""
        ).lower().strip()
        return platform, channel


    def update_stream(self, stream):

        if not stream:
            return None


        platform, channel = self._key(stream)

        if not channel:
            return None


        viewers = int(
            stream.get(
                "viewer_count",
                0
            )
        )


        if (platform, channel) not in self.channels:

            self.channels[(platform, channel)] = deque(
                maxlen=self.max_history
            )


        self.channels[(platform, channel)].append(
            {
                "time": datetime.now(),
                "viewers": viewers
            }
        )


        return self.analyze(
            platform,
            channel
        )


    def analyze(self, platform, channel):

        history = self.channels.get(
            (platform, channel)
        )


        if not history:

            return None


        if len(history) < 2:

            return {
                "channel": channel,
                "platform": platform,
                "status": "warming up",
                "change": 0,
                "percent": 0,
                "current": history[-1]["viewers"]
            }


        old = history[0]["viewers"]
        new = history[-1]["viewers"]


        if old <= 0:

            return {
                "channel": channel,
                "platform": platform,
                "status": "stable",
                "change": 0,
                "percent": 0,
                "current": new
            }


        change = new - old

        percent = (
            change / old
        ) * 100


        if percent >= 15:

            status = "🚀 Spike"

        elif percent >= 3:

            status = "🟢 Rising"

        elif percent <= -15:

            status = "📉 Drop"

        elif percent <= -3:

            status = "🔴 Falling"

        else:

            status = "🟡 Stable"


        return {
            "channel": channel,
            "platform": platform,
            "status": status,
            "change": change,
            "percent": round(percent, 1),
            "current": new
        }


    def get_channel_stats(self, channel, platform="twitch"):

        channel = channel.lower()

        return self.analyze(
            platform,
            channel
        )


    def get_all_stats(self):

        stats = {}

        for (platform, channel) in self.channels:

            stats[f"{platform}:{channel}"] = self.analyze(
                platform,
                channel
            )

        return stats


    def get_top_channel(self):

        best = None
        best_viewers = 0


        for (platform, channel), history in self.channels.items():

            if not history:
                continue


            viewers = history[-1]["viewers"]


            if viewers > best_viewers:

                best_viewers = viewers
                best = (platform, channel)


        return best