"""Core application logic — monitors, dispatcher, and background workers.

All blocking Twitch/Twitch-Auth work happens off the GUI thread here.
The mainmenu layer only wires signals and UI.
"""

from .db import (
    get_recent_channels as load_channels,
    store_channel_played as save_channel,
    clear_channel_history as clear_channels,
    get_streamer,
    store_streamer as update_streamer,
    store_viewer_history as record_viewer_count,
)
from .dispatcher import StreamDispatcher, DispatcherSignals
from .raid_monitor import RaidMonitor, RaidSignals
from .stream_resolver import (
    StreamResolverError,
    normalize_channel as normalize_stream_channel,
    resolve_stream_url,
    try_resolve as try_resolve_streams,
)
from .analytics_engine import AnalyticsEngine
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
    "AnalyticsEngine",
    "update_streamer",
    "get_streamer",
    "record_viewer_count",
]
