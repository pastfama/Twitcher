"""Reusable UI widgets for the Watcher application.

Provides standalone components that can be used across multiple panels:
- base: SizeVariant, WidgetMetrics, SizedWidget (size variant system)
- mom: Momentum gauge widget (M and S sizes)
- sullygoose: Analytics grid widget (M and S sizes)
- viewer_graph: Viewer history sparkline
- indicators: Neon status indicator lights
"""

from .base import SizeVariant, WidgetMetrics, SizedWidget
from .mom import AnalogGauge
from .sullygoose import SullyGooseWidget
from .viewer_graph import ViewerHistoryGraph
from .indicators import NeonIndicator

__all__ = [
    "SizeVariant",
    "WidgetMetrics",
    "SizedWidget",
    "AnalogGauge",
    "SullyGooseWidget",
    "ViewerHistoryGraph",
    "NeonIndicator",
]
