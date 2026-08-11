"""Periodic live-channel monitor.  All API calls run on the
QThreadPool so the GUI thread never blocks.

Supports all platforms (Twitch, Kick, YouTube) by routing each
channel through the platform manager based on its ``platform`` field.
"""

import time
import threading
from collections import deque
from typing import Dict, Any, Optional, Set

from PySide6.QtCore import QObject, QTimer

from core.workers import run_in_background
from logger import debug


class ChatMetricsTracker:
    """Tracks real-time chat metrics (rate, density, emote ratio, etc.)
    from incoming chat messages.  Thread-safe — the ChatPanel feeds
    messages in from the IRC thread while the ViewerMonitor reads
    snapshots from the GUI timer thread."""

    def __init__(self, window_seconds: int = 60):
        self._window = window_seconds
        self._lock = threading.Lock()
        self._messages: deque = deque()  # (timestamp, username, text, has_emote)
        self._seen_users: Set[str] = set()
        self._new_chatter_count = 0
        self._game_changes = 0
        self._last_game: Optional[str] = None
        self._last_game_change_time: float = time.time()
        self._stream_start: float = time.time()

    def record_message(self, username: str, text: str, has_emote: bool = False):
        """Called by the ChatPanel for every incoming chat message."""
        now = time.time()
        with self._lock:
            self._messages.append((now, username, text, has_emote))
            if username not in self._seen_users:
                self._seen_users.add(username)
                self._new_chatter_count += 1

    def record_game_change(self, new_game: str):
        """Called when stream category/game changes."""
        now = time.time()
        with self._lock:
            if self._last_game and new_game != self._last_game:
                self._game_changes += 1
                self._last_game_change_time = now
            self._last_game = new_game

    def reset(self):
        """Reset all tracking (e.g. on channel switch)."""
        with self._lock:
            self._messages.clear()
            self._seen_users.clear()
            self._new_chatter_count = 0
            self._game_changes = 0
            self._last_game = None
            self._last_game_change_time = time.time()
            self._stream_start = time.time()

    def snapshot(self, current_viewers: int = 0) -> Dict[str, Any]:
        """Return a snapshot of all computed chat metrics.  Called from
        the GUI timer thread."""
        now = time.time()
        cutoff = now - self._window

        with self._lock:
            # Prune old messages
            while self._messages and self._messages[0][0] < cutoff:
                self._messages.popleft()

            total = len(self._messages)
            window_minutes = self._window / 60.0
            chat_rate = total / window_minutes if window_minutes > 0 else 0.0

            # Chat density: messages per viewer
            chat_density = (chat_rate / max(current_viewers, 1)) * 100

            # Emote ratio
            emote_count = sum(1 for _, _, _, has_e in self._messages if has_e)
            emote_ratio = (emote_count / total * 100) if total > 0 else 0.0

            # Average message length
            if total > 0:
                avg_len = sum(len(txt) for _, _, txt, _ in self._messages) / total
            else:
                avg_len = 0.0

            new_chatters = self._new_chatter_count
            unique_chatters = len(self._seen_users)
            game_changes = self._game_changes
            freshness = int(now - self._last_game_change_time) // 60

        # Audience loyalty heuristic: ratio of unique chatters to new
        loyalty = 50
        if unique_chatters > 0 and new_chatters > 0:
            returning = max(0, unique_chatters - new_chatters)
            loyalty = max(10, min(95, int(returning / unique_chatters * 100)))

        return {
            "chat_rate": chat_rate,
            "chat_density": chat_density,
            "emote_ratio": emote_ratio,
            "avg_msg_length": avg_len,
            "new_chatters": new_chatters,
            "unique_chatters": unique_chatters,
            "game_changes": game_changes,
            "freshness_minutes": freshness,
            "audience_loyalty": loyalty,
        }


class ViewerMonitor(QObject):
    """Live-channel monitor with its own QTimer.

    Periodically checks live channels and dispatches per-channel checks
    to the thread pool. No network I/O happens on the GUI thread.
    """

    def __init__(
        self,
        api,
        tracker,
        get_live_channels,
        update_callback,
        analytics_engine=None,
        interval_ms=4000,
    ):

        super().__init__()

        self.api = api
        self.tracker = tracker
        self.get_live_channels = get_live_channels
        self.update_callback = update_callback
        self.analytics_engine = analytics_engine

        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.tick)

    def start(self):
        """Start the periodic monitoring."""
        self._timer.start()
        debug("[VIEWER MONITOR] Started")

    def stop(self):
        """Stop the periodic monitoring."""
        self._timer.stop()
        debug("[VIEWER MONITOR] Stopped")

    def tick(self):
        """Called on every timer tick.

        Dispatches per-channel checks to the thread pool and returns
        immediately.
        """

        try:

            channels = self.get_live_channels()
            debug(f"[VIEWER MONITOR] Got {len(channels)} channels from get_live_channels()")

            if not channels:
                debug("[VIEWER MONITOR] No live channels")
                return

            for channel in channels:

                try:

                    if isinstance(channel, str):

                        login = channel
                        platform = "twitch"

                    else:

                        login = (
                            channel.get("user_login")
                            or channel.get("user_name")
                            or channel.get("channel")
                            or channel.get("broadcaster_login")
                        )

                        platform = (
                            channel.get("platform")
                            or "twitch"
                        )

                    if not login:
                        continue

                    run_in_background(
                        lambda login=login, platform=platform: self._check_channel(login, platform),
                        lambda result, login=login: self._on_channel_checked(login, result),
                        lambda message, login=login: self._on_channel_error(login, message),
                    )

                except Exception as exc:

                    debug(f"[VIEWER MONITOR] {login} dispatch error: {exc}")

        except Exception as exc:

            debug(f"[VIEWER MONITOR ERROR] {exc}")

    def _check_channel(self, login, platform="twitch"):
        """Runs on a thread-pool thread.  Returns (stream, analytics)."""

        stream = self._get_stream_info(login, platform)

        if not stream:
            return None

        analytics = {}

        # Get real-time momentum from ViewerTracker (always available)
        viewer_data = None
        if self.tracker:
            viewer_data = self.tracker.update_stream(stream)

        # Get AI/SullyGoose analytics
        ai_data = None
        if self.analytics_engine:
            if hasattr(self.analytics_engine, 'analyze_stream'):
                ai_data = self.analytics_engine.analyze_stream(stream)
            elif hasattr(self.analytics_engine, 'update_stream'):
                ai_data = self.analytics_engine.update_stream(stream)

        # Merge: AI data as base, then overlay real-time viewer data
        if ai_data:
            analytics.update(ai_data)
        if viewer_data:
            # ViewerTracker provides real-time status/percent/change/current
            # These override AI defaults with actual live data
            analytics.update(viewer_data)

        return stream, analytics

    def _get_stream_info(self, login, platform):
        """Fetch stream info for the correct platform.

        Twitch uses the main Twitch API client; Kick and YouTube use
        the unified platform manager.
        """
        try:
            if platform == "twitch":
                return self.api.get_stream_info(login)

            from platforms import get_platform_manager
            pm = get_platform_manager()
            return pm.get_stream_info(platform, login)
        except Exception as exc:
            debug(f"[VIEWER MONITOR] {platform}/{login} fetch error: {exc}")
            return None

    def _on_channel_checked(self, login, result):
        """Delivered on the GUI thread with the worker's result."""

        try:

            if not result:
                debug(f"[VIEWER MONITOR] No result for {login}")
                return

            stream, analytics = result
            debug(f"[VIEWER MONITOR] Result for {login}: viewers={stream.get('viewer_count', 0)}")

            if self.update_callback:
                self.update_callback(stream, analytics)

        except Exception as exc:

            debug(f"[VIEWER MONITOR] {login} callback error: {exc}")

    def _on_channel_error(self, login, message):

        debug(f"[VIEWER MONITOR] {login} error: {message}")