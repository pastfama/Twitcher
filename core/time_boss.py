"""Centralized 'time boss' — one QTimer drives ALL periodic work.

Priority order:
  1. Video window (highest — must stay responsive)
  2. MainMenu / widgets
  3. Background analytics / sullygoose (lowest)

All sub-systems register interest slots here. The time boss ticks on the
GUI thread but only *schedules* work to the QThreadPool; it never performs
blocking I/O itself.

The video window is managed directly: if nothing is playing and we have
cached channels, the TimeBoss tells the video window to try them one by
one.  This makes the video window completely independent of Twitch API
auth — it only needs a channel name and the local stream resolver.
"""

import logging
import time
from collections import defaultdict
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal

from core.workers import run_in_background


logger = logging.getLogger(__name__)


class TimeBoss(QObject):
    """One timer to rule them all."""

    ticked = Signal(int)

    DEFAULT_TICK_MS = 1000
    DEFAULT_REFRESH_S = 7

    # Slot execution order — lower number = higher priority.
    PRIORITY_VIDEO = 0
    PRIORITY_UI = 1
    PRIORITY_ANALYTICS = 2

    def __init__(self, parent=None):
        super().__init__(parent)

        self._tick_interval_ms = self.DEFAULT_TICK_MS
        self._refresh_interval_s = self.DEFAULT_REFRESH_S

        self._tick_count = 0
        self._slots: Dict[str, List[dict]] = defaultdict(list)
        self._pending: Dict[str, set] = defaultdict(set)
        self._lock_time = time.monotonic

        self.timer = QTimer(self)
        self.timer.setInterval(self._tick_interval_ms)
        self.timer.timeout.connect(self._on_tick)

        self._last_refresh = 0

        # Video window reference — TimeBoss manages playback directly.
        self._video_window = None
        self._video_retry_interval = 30
        self._video_retries: Dict[str, int] = {}

    # ================================================================
    # PUBLIC API
    # ================================================================

    def set_video_window(self, video_window):
        """Give TimeBoss direct control over the video window."""
        self._video_window = video_window

    def start(self):
        self.timer.start()
        logger.debug("[TIMEBOSS] Started")

    def stop(self):
        self.timer.stop()
        self._slots.clear()
        self._pending.clear()
        self._tick_count = 0
        logger.debug("[TIMEBOSS] Stopped")

    def register(self, slot_name: str, callback: Callable, priority: int = 1):
        """Register a callback that runs every refresh cycle.

        Priority: 0 = highest (video), 1 = UI, 2 = analytics.
        """
        self._slots[slot_name].append({
            "cb": callback,
            "priority": priority,
        })
        logger.debug("[TIMEBOSS] Registered '%s' (priority=%d)", slot_name, priority)

    def unregister(self, slot_name: str, callback: Callable = None):
        if callback is None:
            self._slots.pop(slot_name, None)
            self._pending.pop(slot_name, None)
        else:
            for entry in list(self._slots.get(slot_name, [])):
                if entry["cb"] is callback:
                    self._slots[slot_name].remove(entry)
            self._pending[slot_name].discard(id(callback))

    def set_refresh_interval(self, seconds: int):
        self._refresh_interval_s = max(1, int(seconds))

    def set_video_retry_interval(self, seconds: int):
        self._video_retry_interval = max(5, int(seconds))

    # ================================================================
    # INTERNALS
    # ================================================================

    def _on_tick(self):
        now = self._lock_time()
        do_refresh = (
            self._tick_count == 0
            or now - self._last_refresh >= self._refresh_interval_s
        )
        self._last_refresh = now

        if do_refresh:
            self._run_cycle()
            self.ticked.emit(self._tick_count)

        self._tick_count += 1

    def _run_cycle(self):
        """Run all registered slots, sorted by priority (video first)."""
        all_entries = []
        for name, entries in list(self._slots.items()):
            for entry in entries:
                all_entries.append((name, entry))

        all_entries.sort(key=lambda x: x[1]["priority"])

        for name, entry in all_entries:
            cb = entry["cb"]
            key = id(cb)
            if key in self._pending[name]:
                continue
            self._pending[name].add(key)
            run_in_background(
                cb,
                lambda result, n=name, k=key: self._on_done(n, k, result),
                lambda msg, n=name, k=key: self._on_done(n, k, None, msg),
            )

    def _on_done(self, slot_name, cb_key, result, error=None):
        self._pending[slot_name].discard(cb_key)
        if error:
            logger.debug("[TIMEBOSS] Slot '%s' error: %s", slot_name, error)

    # ================================================================
    # VIDEO WINDOW MANAGEMENT (highest priority)
    # ================================================================

    def ensure_video_playing(self, get_recent_channels):
        """If nothing is playing, try the most recent channels.

        This runs as a high-priority slot so the video window is always
        the first thing the TimeBoss tends to.  It does NOT require
        Twitch auth — it only uses local channel history + the auth-free
        stream resolver.
        """
        if not self._video_window:
            return

        try:
            state = self._video_window.get_player_state()
        except Exception:
            state = None

        if state and state.get("playing"):
            self._video_retries.clear()
            return

        channels = get_recent_channels()
        if not channels:
            return

        for channel in channels:
            retries = self._video_retries.get(channel, 0)
            if retries >= 3:
                continue
            try:
                self._video_window.start_channel(channel)
                self._video_retries[channel] = retries + 1
                if retries + 1 >= 3:
                    self._video_retries.pop(channel, None)
                return
            except Exception:
                self._video_retries[channel] = retries + 1
                continue