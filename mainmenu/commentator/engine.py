"""Commentary Engine — generates AI commentary with personality.

Always produces output immediately (local first), then upgrades
to AI-generated commentary in background. Stores on Azure PostgreSQL.
"""

import threading
import time as _time
import random
from typing import Dict, Any, Optional, Callable
from logger import debug

INTRODUCTIONS = [
    "Hey there! I'm W.A.T.C.H.E.R. — your AI stream analyst! Let me take a look...",
    "W.A.T.C.H.E.R. online! Scanning the stream landscape...",
    "Hello! I'm W.A.T.C.H.E.R. — I watch streams so you don't have to blink!",
    "Booting up... W.A.T.C.H.E.R. here, ready to analyze some streams!",
]

CATCHPHRASES = [
    "Now THAT'S what I call a stream!",
    "My circuits are tingling!",
    "Let me zoom in on this...",
    "Interesting... very interesting...",
    "This is getting good!",
    "Hold on, I need to recalibrate my hype sensors!",
    "I've seen a lot of streams, but this...",
    "Data incoming! Processing...",
]

TRANSITIONS = [
    "Moving on...",
    "Let's see what else is happening...",
    "Switching gears...",
    "Here's what I'm seeing now...",
    "Update time!",
]


class CommentaryEngine:
    """Generates and stores AI commentary for the Watcher Bot."""

    def __init__(self):
        self._last_metrics = {}
        self._last_vision = ""
        self._last_chat = {}
        self._commentary_callback = None
        self._status_callback = None  # (status: str, detail: str) -> None
        self._busy = False
        self._channel = ""
        self._platform = "twitch"
        self._last_generate_time = 0.0
        self._cooldown_seconds = 8.0
        self._generation_count = 0
        self._intro_shown = False
        self._azure_connected = None  # None=unknown, True=connected, False=failed

    def set_callback(self, callback):
        self._commentary_callback = callback

    def set_status_callback(self, callback):
        """Set callback for status updates: (status, detail) -> None.
        Status values: 'idle', 'connecting', 'connected', 'error'."""
        self._status_callback = callback

    def set_channel(self, channel, platform="twitch"):
        self._channel = channel
        self._platform = platform

    def update_metrics(self, metrics):
        self._last_metrics = metrics

    def update_vision(self, vision_text):
        self._last_vision = vision_text

    def update_chat(self, chat_data):
        self._last_chat = chat_data

    def show_introduction(self):
        if self._intro_shown:
            return
        self._intro_shown = True
        intro = random.choice(INTRODUCTIONS)
        if self._commentary_callback:
            self._commentary_callback(intro, "happy", "#00ff88")

    def generate(self):
        now = _time.time()
        if self._busy:
            return
        if now - self._last_generate_time < self._cooldown_seconds:
            return

        self._busy = True
        self._last_generate_time = now
        self._generation_count += 1

        commentary, mood, color = self._generate_local()
        if commentary and self._commentary_callback:
            self._commentary_callback(commentary, mood, color)

        if self._generation_count > 2 and self._last_metrics:
            # Notify UI that we're attempting Azure AI connection
            if self._azure_connected is None and self._status_callback:
                self._status_callback("connecting", "Connecting to Azure AI...")

            def bg_ai():
                try:
                    from core.sk_engine import generate_insight
                    ctx = dict(self._last_metrics)
                    if self._last_vision:
                        ctx["vision_analysis"] = self._last_vision
                    ctx["channel"] = self._channel
                    # Notify UI that we're communicating with Azure (schedule on GUI thread)
                    if self._status_callback:
                        from PySide6.QtCore import QTimer
                        QTimer.singleShot(0, lambda: self._status_callback("communicating", "Generating AI insight..."))
                    ai_text = generate_insight(ctx)
                    if ai_text:
                        self._azure_connected = True
                        if self._status_callback:
                            QTimer.singleShot(0, lambda: self._status_callback("connected", "AI connected ✓"))
                        # Schedule commentary on GUI thread
                        QTimer.singleShot(0, lambda: self._commentary_callback(ai_text, mood, color))
                    else:
                        if self._azure_connected is not False and self._status_callback:
                            self._azure_connected = False
                            QTimer.singleShot(0, lambda: self._status_callback("error", "Azure AI returned empty response"))
                except Exception as e:
                    debug(f"[COMMENTARY ENGINE] AI error: {e}")
                    self._azure_connected = False
                    if self._status_callback:
                        from PySide6.QtCore import QTimer
                        QTimer.singleShot(0, lambda: self._status_callback("error", f"AI error: {str(e)[:60]}"))
                finally:
                    self._busy = False

            t = threading.Thread(target=bg_ai, daemon=True)
            t.start()
            # Safety: if thread hangs for >20s, reset busy flag
            def watchdog():
                t.join(timeout=20)
                if t.is_alive() and self._busy:
                    self._busy = False
                    if self._status_callback:
                        from PySide6.QtCore import QTimer
                        QTimer.singleShot(0, lambda: self._status_callback("error", "Azure AI timed out (20s)"))
            threading.Thread(target=watchdog, daemon=True).start()
        else:
            self._busy = False

        self._store(commentary, mood)

    def _generate_local(self):
        m = self._last_metrics
        lines = []
        viewers = m.get("viewers", 0)
        velocity = m.get("velocity", 0)
        sentiment = m.get("sentiment", 0)
        chat_rate = m.get("chat_rate", 0)
        rank = m.get("overall_rank", "")

        if sentiment > 50:
            mood, color = "hype", "#ff3366"
        elif sentiment > 20:
            mood, color = "positive", "#00ff88"
        elif sentiment > -20:
            mood, color = "neutral", "#00ffff"
        elif sentiment > -50:
            mood, color = "slow", "#aa44ff"
        else:
            mood, color = "tense", "#ffaa00"

        if velocity > 20:
            lines.append(f"Viewers surging! +{velocity:.0f}/min — {random.choice(CATCHPHRASES)}")
        elif velocity < -15:
            lines.append(f"Losing viewers at {velocity:.0f}/min... maybe switch things up?")
        elif viewers > 1000:
            lines.append(f"{viewers:,} viewers watching — solid crowd!")
        elif viewers > 0:
            lines.append(f"{viewers:,} viewers in the house")

        if chat_rate > 30:
            lines.append(f"Chat is ON FIRE! {chat_rate:.0f} msg/min!")
        elif chat_rate > 10:
            lines.append(f"Chat is active — {chat_rate:.0f} msg/min")

        if self._last_vision:
            lines.append(f"{self._last_vision[:80]}")

        if sentiment > 50:
            lines.append("Chat mood is HYPE! Energy levels off the charts!")
        elif sentiment < -30:
            lines.append("Chat sentiment dipping... might want to change the vibe")

        if rank in ("A+", "A"):
            lines.append(f"Grade: {rank} — this stream is killing it!")

        if not lines:
            if viewers > 0:
                lines.append(f"{viewers:,} viewers watching. {random.choice(CATCHPHRASES)}")
            else:
                lines.append(f"{random.choice(TRANSITIONS)} Looking for something interesting...")

        return " | ".join(lines[:2]), mood, color

    def _store(self, commentary, mood):
        try:
            from core.commentary_store import store_commentary
            store_commentary({
                "channel": self._channel,
                "platform": self._platform,
                "commentary": commentary,
                "mood": mood,
                "expression": mood,
                "viewers": self._last_metrics.get("viewers", 0),
                "velocity": self._last_metrics.get("velocity", 0),
                "sentiment": self._last_metrics.get("sentiment", 0),
                "chat_rate": self._last_metrics.get("chat_rate", 0),
                "vision_analysis": self._last_vision,
                "metrics_snapshot": self._last_metrics,
            })
        except Exception as e:
            debug(f"[COMMENTARY ENGINE] Store failed: {e}")