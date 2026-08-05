"""SullyGoose analytics panel module.

Displays streamer performance metrics scraped from sullygnome.com by the
``SullyGooseAPI`` and delivered through ``AnalyticsEngine``.

Module Layout:
    The SullyGoose section sits on the right side of the Current Watching
    panel and expands to fill remaining horizontal space.

    ┌──────────────────────────────────────────┐
    │          ◆ SULLYGOOSE ◆                  │
    │  ┌─────┬─────┬─────┬─────┬─────┬─────┐  │
    │  │ AVG │ PEAK│ GRW │RANK │ FRQ │ DUR │  │  ← MetricCell grid
    │  ├─────┼─────┼─────┼─────┼─────┼─────┤  │     (3 rows × 6 cols)
    │  │START│ END │GAMES│MAIN │ RAID│ FOL │  │
    │  ├─────┼─────┼─────┼─────┼─────┼─────┤  │
    │  │ FGRW│CHAT │ 7D  │ 30D │BEST │     │  │
    │  └─────┴─────┴─────┴─────┴─────┴─────┘  │
    │  [CONS] [REL]  [DISC]  [★ QUAL]         │  ← ScoreBar row
    └──────────────────────────────────────────┘

Data Flow:
    AnalyticsEngine._ensure_async_fetch()  →  daemon thread
      → SullyGooseAPI.get_channel_stats()  →  dict of metrics
      → cached in AnalyticsEngine._sully_cache
      → signal → MainMenu._on_analytics_signal
      → CurrentWatchingPanel.set_viewer_status(analysis)
      → panel.sully_widget.update_metrics(sully_data, analysis)

Exports:
    SullyGooseWidget      — Main analytics grid widget (QFrame)
    METRIC_CELL_HEIGHT    — Height of each metric cell (36 px)
    SCORE_BAR_WIDTH       — Width of each score bar (52 px)
    SCORE_BAR_HEIGHT      — Height of each score bar (32 px)
    PANEL_MIN_WIDTH       — Minimum panel width (280 px)
"""

from .sullygoose_widget import (
    SullyGooseWidget,
    METRIC_CELL_HEIGHT,
    SCORE_BAR_WIDTH,
    SCORE_BAR_HEIGHT,
    PANEL_MIN_WIDTH,
)

__all__ = [
    "SullyGooseWidget",
    "METRIC_CELL_HEIGHT",
    "SCORE_BAR_WIDTH",
    "SCORE_BAR_HEIGHT",
    "PANEL_MIN_WIDTH",
]

# Alias for backward compatibility
SullyGoosePanel = SullyGooseWidget