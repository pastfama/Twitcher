"""Core application logic — monitors, dispatcher, and background workers.

All blocking Twitch/Twitch-Auth work happens off the GUI thread here.
The mainmenu layer only wires signals and UI.
"""

from .channel_history import clear_channels, load_channels, save_channel
from .dispatcher import StreamDispatcher, DispatcherSignals
from .raid_monitor import RaidMonitor, RaidSignals
from .stream_resolver import (
    StreamResolverError,
    normalize_channel as normalize_stream_channel,
    resolve_stream_url,
    try_resolve as try_resolve_streams,
)
from .streamer_history import (
    get_streamer,
    load_streamer_data,
    record_viewer_count,
    update_streamer,
)
from .analytics_engine import AnalyticsEngine
from .time_boss import TimeBoss
from .viewer_monitor import ViewerMonitor
from .viewer_tracker import ViewerTracker
from .workers import BackgroundTask, TaskSignals, run_in_background, wait_for_pending

__all__ = [
    "StreamDispatcher",
    "DispatcherSignals",
    "RaidMonitor",
    "RaidSignals",
    "ViewerMonitor",
    "ViewerTracker",
    "BackgroundTask",
    "TaskSignals",
    "run_in_background",
    "wait_for_pending",
    "load_channels",
    "save_channel",
    "clear_channels",
    "StreamResolverError",
    "normalize_stream_channel",
    "resolve_stream_url",
    "try_resolve_streams",
    "TimeBoss",
    "AnalyticsEngine",
    "load_streamer_data",
    "update_streamer",
    "get_streamer",
    "record_viewer_count",
]
