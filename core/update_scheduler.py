"""Single-timer update scheduler with named subscribers.

Replaces multiple QTimers with one master clock.  Each subscriber
declares its own interval and callback.  The scheduler fires only
when a subscriber's interval has elapsed.

Usage::

    scheduler = UpdateScheduler()
    scheduler.register("viewer_monitor", 2000, check_viewer_counts)
    scheduler.register("sg_fetch", 30000, fetch_sullygoose)
    scheduler.register("lcd_tick", 1000, update_lcd)
    scheduler.start()
"""

from PySide6.QtCore import QTimer


class UpdateScheduler:
    """Master clock that dispatches ticks to named subscribers.

    Each subscriber has:
      - name: unique identifier
      - interval_ms: how often to fire (in milliseconds)
      - callback: function to call when interval elapses
      - _last_tick: timestamp of last fire (for interval tracking)
    """

    def __init__(self, parent=None):
        self._timer = QTimer(parent)
        self._timer.setInterval(1000)  # master clock: 1s resolution
        self._timer.timeout.connect(self._on_tick)

        self._subscribers = {}  # name → {"interval_ms", "callback", "_ticks"}
        self._started = False

    def register(self, name, interval_ms, callback):
        """Register a named subscriber with its own refresh interval.

        Args:
            name: unique subscriber name (e.g. "viewer_monitor")
            interval_ms: refresh interval in milliseconds
            callback: zero-argument callable to invoke
        """
        self._subscribers[name] = {
            "interval_ms": interval_ms,
            "callback": callback,
            "_ticks": 0,
        }

    def unregister(self, name):
        """Remove a subscriber."""
        self._subscribers.pop(name, None)

    def start(self):
        """Start the master clock."""
        if not self._started:
            self._timer.start()
            self._started = True

    def stop(self):
        """Stop the master clock."""
        self._timer.stop()
        self._started = False

    def _on_tick(self):
        """Master tick — check each subscriber's interval."""
        for sub in self._subscribers.values():
            sub["_ticks"] += 1
            elapsed_ms = sub["_ticks"] * 1000  # master clock is 1s
            if elapsed_ms >= sub["interval_ms"]:
                sub["_ticks"] = 0
                try:
                    sub["callback"]()
                except Exception as exc:
                    from logger import debug
                    debug(f"[SCHEDULER] Subscriber error: {exc}")