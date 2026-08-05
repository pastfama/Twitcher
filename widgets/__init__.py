"""Reusable UI widgets for the Watcher application.

Provides standalone components that can be used across multiple panels:
- mom: Momentum gauge widget
- sullygoose: Analytics grid widget
- viewer_graph: Viewer history sparkline
- indicators: Neon status indicator lights
"""

from .mom import AnalogGauge
from .sullygoose import SullyGoosePanel
from .viewer_graph import ViewerHistoryGraph
from .indicators import NeonIndicator

__all__ = [
    "AnalogGauge",
    "SullyGoosePanel",
    "ViewerHistoryGraph",
    "NeonIndicator",
]