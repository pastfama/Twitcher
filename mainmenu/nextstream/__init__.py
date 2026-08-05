"""Next Stream Panel — shows the next live channel in queue.

Provides a compact card with:
- Streamer name + avatar (async loaded via ImageCache)
- Platform badge (Twitch/Kick/YouTube color-coded)
- Viewer count + trend indicator
- Category
- Auto-switch reason
- SWITCH NOW button (emits watch_requested signal)

Usage in channel_state.py::

    self.next_panel = NextStreamPanel()
    self.next_panel.set_stream(stream_dict)   # show next channel
    self.next_panel.clear()                    # reset to empty

Data flow:
    load_live_channels() → handle_live_channels_loaded()
      → update_next_stream() → next_panel.set_stream(next_stream)
"""

from .panel import NextStreamPanel

__all__ = ["NextStreamPanel"]
