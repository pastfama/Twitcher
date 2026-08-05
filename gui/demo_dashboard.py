"""Runnable full-dashboard demo with a mock provider.

Simulates all Watcher metrics live: viewer count sentiment, next stream,
live-followed list, dispatcher log lines, chat messages, SullyGoose
analytics, raid events — every second. No PySide6, no network.

Run:
    python -m gui.demo_dashboard        (from repo root)
or:
    python gui/demo_dashboard.py
"""

import os
import sys
import random
import time
from collections import deque
from datetime import datetime

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.dashboard import run_dashboard
from gui.demo_metrics import _analyze

NICKS = ["pogchamp", "keemstar", "ninja", "shroud", "xqc", "poke", "mizkif"]
MSGS = ["hello chat", "PogU", "wow", "LUL", "sheesh", "based", "omegalul", "raidTrain"]


class _DashboardProvider:
    CHANNEL = "xqc"

    def __init__(self):
        self.history = deque(maxlen=20)
        base = 1200
        for _ in range(3):
            base += random.randint(-40, 40)
            self.history.append({"time": datetime.now(), "viewers": max(0, base)})
        self._tick = 0
        self._log_lines = 0

    def __call__(self):
        self._tick += 1
        # --- current watching (full analyze) ---
        prev = self.history[-1]["viewers"]
        nxt = max(0, prev + random.randint(-160, 240))
        self.history.append({"time": datetime.now(), "viewers": nxt})
        analysis = _analyze(self.CHANNEL, self.history)
        history = [h["viewers"] for h in self.history]

        # --- next stream suggestion ---
        next_state = {
            "channel": random.choice(["ninja", "shroud", "pokimane", "moistcr1tikal"]),
            "viewers": random.randint(800, 4000),
            "category": random.choice(["Just Chatting", "Grand Theft Auto V"]),
            "reason": random.choice(["highest momentum", "raid chain", "predicted next"]),
        }

        # --- live followed (3-5 channels) ---
        live = []
        channels = random.sample(
            ["ninja", "shroud", "pokimane", "moistcr1tikal", "xqc", "hood296"],
            k=random.randint(3, 5))
        for ch in channels:
            live.append({
                "channel": ch,
                "viewers": random.randint(50, 2000),
                "status": random.choice(["🟢 Rising", "🟡 Stable", "🟢 Rising"]),
                "category": random.choice(["Just Chatting", "GTA V", "Pools"]),
                "growth": random.choice(["↑", "→", "↓"]),
                "score": random.randint(10, 95),
            })

        # --- SullyGoose analytics (wired to AnalyticsEngine) ---
        sully = {
            "streamer": self.CHANNEL,
            "me": self.CHANNEL,
            "uptime": f"{random.randint(1, 120)}m",
            "peak": f"{max(h['viewers'] for h in self.history):,}",
            "avg": f"{int(sum(h['viewers'] for h in self.history)/len(self.history)):,}",
            "cons": random.uniform(40, 95),
            "rel": random.uniform(50, 98),
            "disc": random.uniform(30, 90),
            "qual": random.uniform(60, 99),
        }

        # --- dispatcher log (append 1 line every 2 ticks) ---
        self._log_lines += 1
        logs = []
        if self._tick % 2 == 0:
            logs.append({"msg": f"dispatching to {next_state['channel'] or 'idle'}", "level": "info"})
        if self._tick % 7 == 0:
            logs.append({"msg": "stream switch succeeded", "level": "success"})
        if self._tick % 11 == 0:
            logs.append({"msg": "rate limit approaching", "level": "warn"})
        dispatch = {
            "status": random.choice(["running", "idle", "monitoring"]),
            "next": f"{next_state['channel']} @ {next_state['viewers']:,}v",
            "logs": logs,
        }

        # --- chat (1-2 messages this tick) ---
        msgs = []
        for _ in range(random.randint(0, 2)):
            msgs.append({"nick": random.choice(NICKS), "msg": random.choice(MSGS)})
        chat = {"channel": self.CHANNEL, "messages": msgs}

        conn = "● ONLINE — connected to Twitch"

        # --- raid (occasional) ---
        raid = None
        if self._tick % 13 == 0:
            target = random.choice(["ninja", "shroud", "pokimane"])
            raid = {"from": self.CHANNEL, "to": target}

        return {
            "current": (analysis, history),
            "next": next_state,
            "live": live,
            "sullygoose": sully,
            "dispatch": dispatch,
            "chat": chat,
            "connection": conn,
            "logs": logs,
            "raid": raid,
        }


def main():
    random.seed(time.time())
    run_dashboard(provider=_DashboardProvider(), tick_ms=1000)


if __name__ == "__main__":
    main()

