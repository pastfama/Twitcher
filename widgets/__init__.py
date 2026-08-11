"""Reusable UI widgets for the Watcher application.

Provides standalone components that can be used across multiple panels:
- mom: Momentum gauge widget
- viewer_graph: Viewer history sparkline
- indicators: Neon status indicator lights
"""

from .mom import AnalogGauge
from .viewer_graph import ViewerHistoryGraph
from .indicators import NeonIndicator

__all__ = [
    "AnalogGauge",
    "ViewerHistoryGraph",
    "NeonIndicator",
]
