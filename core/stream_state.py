"""Single source of truth for all stream-related state.

Every piece of mutable state that panels, timers, and services need
lives here.  Qt signals notify subscribers when state changes — no
direct method calls between components.

Usage::

    state = StreamState()

    # Read
    channel = state.current_channel
    streams = state.live_channels

    # Write (emits signals automatically)
    state.set_current_stream(stream_dict)
    state.set_live_channels(list_of_streams)

    # Subscribe
    state.current_stream_changed.connect(my_panel.on_stream_update)
    state.live_channels_changed.connect(my_panel.on_channels_update)
"""

from PySide6.QtCore import QObject, Signal


class StreamState(QObject):
    """Observable container for all application stream state.

    Signals:
        current_stream_changed(dict)  — emitted when the watched stream updates
        current_channel_changed(str)  — emitted when the active channel name changes
        live_channels_changed(list)   — emitted when the live channels list refreshes
        next_stream_changed(dict)     — emitted when the next-in-queue stream changes
        user_changed(dict)            — emitted when the logged-in user loads
    """

    # Raw state change signals
    current_stream_changed = Signal(dict)
    current_channel_changed = Signal(str)
    live_channels_changed = Signal(list)
    next_stream_changed = Signal(dict)
    user_changed = Signal(dict)

    # Processed signal — emitted by update_current_stream_view after
    # enrichment + analytics.  Panels subscribe to this for full updates.
    # Carries (stream_dict, analysis_dict_or_None).
    stream_ready = Signal(dict, object)

    def __init__(self):
        super().__init__()

        # --- Current stream being watched ---
        self._current_stream = None
        self._current_channel = None

        # --- All live channels (sorted by viewer count desc) ---
        self._live_channels = []

        # --- Next stream in queue ---
        self._next_stream = None

        # --- Logged-in user ---
        self._user = None

        # --- UI flags ---
        self.is_closing = False
        self.is_loading_channels = False
        self.pending_channel = None
        self.resume_attempted = False

    # ================================================================
    # CURRENT STREAM
    # ================================================================

    @property
    def current_stream(self):
        return self._current_stream

    def set_current_stream(self, stream):
        """Update the current stream.  Emits current_stream_changed."""
        self._current_stream = stream
        if stream:
            self.current_stream_changed.emit(stream)

    @property
    def current_channel(self):
        return self._current_channel

    def set_current_channel(self, channel):
        """Update the current channel name.  Emits current_channel_changed."""
        channel = (channel or "").lower().strip()
        if channel != self._current_channel:
            self._current_channel = channel
            self.current_channel_changed.emit(channel)

    # ================================================================
    # LIVE CHANNELS
    # ================================================================

    @property
    def live_channels(self):
        return self._live_channels

    def set_live_channels(self, channels):
        """Update the live channels list.  Emits live_channels_changed."""
        self._live_channels = list(channels or [])
        self.live_channels_changed.emit(self._live_channels)

    def add_to_live_channels(self, stream):
        """Add a stream if not already present."""
        if stream and stream not in self._live_channels:
            self._live_channels.append(stream)
            self.live_channels_changed.emit(self._live_channels)

    # ================================================================
    # NEXT STREAM
    # ================================================================

    @property
    def next_stream(self):
        return self._next_stream

    def set_next_stream(self, stream):
        """Update the next stream in queue.  Emits next_stream_changed."""
        self._next_stream = stream
        if stream:
            self.next_stream_changed.emit(stream)

    # ================================================================
    # USER
    # ================================================================

    @property
    def user(self):
        return self._user

    def set_user(self, user):
        """Update the logged-in user.  Emits user_changed."""
        self._user = user or {}
        if self._user:
            self.user_changed.emit(self._user)