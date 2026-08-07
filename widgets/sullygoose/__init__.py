"""SullyGoose analytics panel module.

Provides a comprehensive analytics grid for displaying streamer metrics.

Exports:
- SullyGooseWidget: Main analytics grid widget
- Size constants: METRIC_CELL_HEIGHT, SCORE_BAR_WIDTH, SCORE_BAR_HEIGHT, PANEL_MIN_WIDTH
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