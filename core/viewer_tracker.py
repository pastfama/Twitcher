from collections import deque
from datetime import datetime


class ViewerTracker:
    """
    Tracks viewer count changes for multiple channels
    and calculates stream momentum.
    """

    def __init__(self, max_history=20):

        self.max_history = max_history

        self.channels = {}


    def update_stream(self, stream):

        if not stream:
            return None


        channel = (
            stream.get("user_login")
            or stream.get("user_name")
            or ""
        ).lower()


        if not channel:
            return None


        viewers = int(
            stream.get(
                "viewer_count",
                0
            )
        )


        if channel not in self.channels:

            self.channels[channel] = deque(
                maxlen=self.max_history
            )


        self.channels[channel].append(
            {
                "time": datetime.now(),
                "viewers": viewers
            }
        )


        return self.analyze(
            channel
        )


    def analyze(self, channel):

        history = self.channels.get(
            channel
        )


        if not history:

            return None


        if len(history) < 2:

            return {
                "channel": channel,
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
            "status": status,
            "change": change,
            "percent": round(percent, 1),
            "current": new
        }


    def get_channel_stats(self, channel):

        channel = channel.lower()

        return self.analyze(
            channel
        )


    def get_all_stats(self):

        stats = {}

        for channel in self.channels:

            stats[channel] = self.analyze(
                channel
            )

        return stats


    def get_top_channel(self):

        best = None
        best_viewers = 0


        for channel, history in self.channels.items():

            if not history:
                continue


            viewers = history[-1]["viewers"]


            if viewers > best_viewers:

                best_viewers = viewers
                best = channel


        return best