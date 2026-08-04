"""Last-played channels history (auth-independent).

Stores the last 10 channels the user watched in a plain text file
so the video window can try them one-by-one without any Twitch auth.
"""

import os
import threading

from logger import debug


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(BASE_DIR, "last_channels.txt")

MAX_CHANNELS = 10

# RLock because save_channel() calls load_channels() while holding the lock.
_lock = threading.RLock()


def load_channels():
    """Return the list of previously-watched channels (most recent first)."""
    with _lock:
        try:
            if not os.path.exists(HISTORY_FILE):
                return []
            with open(HISTORY_FILE, "r", encoding="utf-8") as handle:
                lines = [
                    line.strip().lstrip("#").lower()
                    for line in handle
                    if line.strip()
                ]
            return [line for line in lines if line]
        except Exception as exc:
            debug(f"[HISTORY] load error: {exc}")
            return []


def save_channel(channel):
    """Record *channel* as watched; keeps at most MAX_CHANNELS entries."""
    channel = str(channel or "").strip().lstrip("#").lower()
    if not channel:
        return

    with _lock:
        channels = load_channels()
        # Remove existing entry so it moves to the front.
        channels = [c for c in channels if c != channel]
        channels.insert(0, channel)
        channels = channels[:MAX_CHANNELS]
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as handle:
                for c in channels:
                    handle.write(c + "\n")
        except Exception:
            pass


def clear_channels():
    with _lock:
        try:
            if os.path.exists(HISTORY_FILE):
                os.remove(HISTORY_FILE)
        except Exception:
            pass