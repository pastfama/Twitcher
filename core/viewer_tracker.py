from collections import deque
from datetime import datetime


class ViewerTracker:
    """Tracks viewer count changes for multiple channels and calculates stream momentum.

    Uses exponential moving average (EMA) for smooth, responsive momentum
    detection instead of crude first-vs-last comparison.

    Channels are keyed by ``(platform, channel)`` so the same
    channel name on different platforms does not collide.

    Momentum Calculation:
        The tracker maintains two EMA values per channel:
        - ``ema_fast``: short-term EMA (α=0.3, ~6s half-life) — reacts quickly
        - ``ema_slow``: long-term EMA (α=0.1, ~20s half-life) — smooth baseline

        Momentum percent = (ema_fast - ema_slow) / ema_slow * 100

        This gives a responsive yet stable signal that avoids noise while
        still detecting real viewer count changes within 2-3 samples.
    """

    def __init__(self, max_history=20):

        self.max_history = max_history

        self.channels = {}

        # Per-channel EMA state: {(platform, channel): {"fast": float, "slow": float}}
        self._ema = {}


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

    def _update_ema(self, key, viewers):
        """Update fast and slow exponential moving averages for a channel.

        Returns (ema_fast, ema_slow) after the update.
        """
        if key not in self._ema:
            # Initialize both EMAs to the first observed value
            self._ema[key] = {"fast": float(viewers), "slow": float(viewers)}
        else:
            ema = self._ema[key]
            # α=0.3 → fast EMA reacts in ~3 samples (~6s at 2s intervals)
            ema["fast"] = 0.3 * viewers + 0.7 * ema["fast"]
            # α=0.1 → slow EMA reacts in ~10 samples (~20s at 2s intervals)
            ema["slow"] = 0.1 * viewers + 0.9 * ema["slow"]
        return self._ema[key]["fast"], self._ema[key]["slow"]

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
        """Analyze momentum using EMA-based calculation for smooth, responsive detection.

        Returns a dict with status, percent change, and current viewer count.
        Uses exponential moving average instead of first-vs-last comparison.
        """
        history = self.channels.get(
            (platform, channel)
        )


        if not history:

            return None

        current_viewers = history[-1]["viewers"]

        if len(history) < 2:

            # Seed the EMA with the first value
            self._update_ema((platform, channel), current_viewers)
            return {
                "channel": channel,
                "platform": platform,
                "status": "warming up",
                "change": 0,
                "percent": 0,
                "current": current_viewers
            }


        # Update EMAs with latest observation
        ema_fast, ema_slow = self._update_ema(
            (platform, channel), current_viewers
        )


        if ema_slow <= 0:

            return {
                "channel": channel,
                "platform": platform,
                "status": "stable",
                "change": 0,
                "percent": 0,
                "current": current_viewers
            }


        # Momentum = how fast EMA_fast is pulling away from EMA_slow
        change = ema_fast - ema_slow
        percent = (change / ema_slow) * 100

        # Clamp to reasonable range for display
        percent = max(-50.0, min(50.0, percent))


        if percent >= 10:

            status = "Rising"

        elif percent <= -5:

            status = "Declining"

        else:

            status = "Stable"


        return {
            "channel": channel,
            "platform": platform,
            "status": status,
            "change": round(change, 1),
            "percent": round(percent, 1),
            "current": current_viewers
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