"""Runnable, self-contained demo of the new CustomTkinter metrics card.

It reproduces the *exact* metric shape that
``core/viewer_tracker.ViewerTracker.analyze()`` emits (channel/status/
change/percent/current) and feeds the card on a walking random-walk
viewer-count stream every second — so every metric updates live:
viewer count, sentiment status (🚀 Spike / 🟢 Rising / 📉 Drop / 🟡 Stable …),
delta, percent, the momentum sparkline, the analog gauge, and the neon
indicator. No PySide6, no network.

Run:
    python -m gui.demo_metrics        (from the repo root)
or:
    python gui/demo_metrics.py         (anywhere)
"""

import os
import sys
import random
import time
from collections import deque
from datetime import datetime

# allow "python gui/demo_metrics.py" as well as "python -m gui.demo_metrics"
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.app import run


# --------------------------------------------------------------------------- #
# A faithful, dependency-free re-implementation of ViewerTracker.analyze(),
# driven by an in-memory history deque. This is what the card consumes.
# --------------------------------------------------------------------------- #
def _analyze(channel: str, history: deque):
    if not history:
        return None
    viewers = int(history[-1]["viewers"])

    if len(history) < 2:
        return {
            "channel": channel,
            "status": "warming up",
            "change": 0,
            "percent": 0,
            "current": viewers,
        }

    old = int(history[0]["viewers"])
    new = int(history[-1]["viewers"])
    change = new - old

    if old <= 0:
        pct = 0.0
        status = "stable"
    else:
        pct = (change / old) * 100
        if pct >= 15:
            status = "🚀 Spike"
        elif pct >= 3:
            status = "🟢 Rising"
        elif pct <= -15:
            status = "📉 Drop"
        elif pct <= -3:
            status = "🔴 Falling"
        else:
            status = "🟡 Stable"

    return {
        "channel": channel,
        "status": status,
        "change": change,
        "percent": round(pct, 2),
        "current": new,
    }


class _MockProvider:
    """Walks a viewer count through Spike/Rising/Drop/Falling/Stable."""

    CHANNEL = "xqc"
    MAX_HISTORY = 20

    def __init__(self):
        base = 1200
        # seed with a couple of points so we skip "warming up" quickly
        self.history = deque(maxlen=self.MAX_HISTORY)
        for _ in range(3):
            base += random.randint(-40, 40)
            self.history.append({"time": datetime.now(), "viewers": max(0, base)})

    def __call__(self):
        prev = self.history[-1]["viewers"] if self.history else 1000
        # random walk with occasional big swings so we hit every status
        step = random.randint(-180, 220)
        nxt = max(0, prev + step)
        self.history.append({"time": datetime.now(), "viewers": nxt})
        analysis = _analyze(self.CHANNEL, self.history)
        history = [h["viewers"] for h in self.history]
        return analysis, history


def main():
    random.seed(time.time())
    run(metrics_provider=_MockProvider(), tick_ms=1000)


if __name__ == "__main__":
    main()
