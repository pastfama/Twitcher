"""MOM (Momentum) gauge widget module.

Provides a circular analog gauge and size constants used by the
``currwatching`` panel's left-side MOM section.

Module Layout:
    The MOM section of the Current Watching panel is a fixed-width column
    (MOM_WIDTH=280px) containing:

    ┌──────────────────────────────────┐
    │  ┌─────────┐  ┌──────────────┐  │  ← top_row (QHBoxLayout)
    │  │ Analog  │  │  QLCDNumber  │  │     Gauge (80×80) + LCD (140×60)
    │  │ Gauge   │  │  viewer cnt  │  │
    │  └─────────┘  └──────────────┘  │
    │        momentum label            │  ← "Rising +3.2%" etc.
    │  ┌──────────────────────────┐   │  ← ViewerHistoryGraph (30px high)
    │  │ ▁▂▃▅▇▆▅▃▂▁▁▃▅▇▆▅       │   │     mini strip chart
    │  └──────────────────────────┘   │
    │ [VIEWERS] [LIVE] [CHAT] [RAID] │  ← NeonIndicator row
    └──────────────────────────────────┘

Usage in currwatching/ui.py::

    from widgets.mom import AnalogGauge, GAUGE_SIZE, MOM_WIDTH, LCD_WIDTH, LCD_HEIGHT, GRAPH_HEIGHT

Exports:
    AnalogGauge   — Circular gauge widget (QWidget, custom-painted)
    MOM_WIDTH     — Total width of MOM section (280 px)
    GAUGE_SIZE    — Diameter of circular gauge (80 px)
    LCD_WIDTH     — Width of QLCDNumber viewer-count (140 px)
    LCD_HEIGHT    — Height of QLCDNumber viewer-count (60 px)
    GRAPH_HEIGHT  — Height of ViewerHistoryGraph strip (30 px)
"""

from .mom_widget import (
    AnalogGauge,
    MOM_WIDTH,
    GAUGE_SIZE,
    LCD_WIDTH,
    LCD_HEIGHT,
    GRAPH_HEIGHT,
)

__all__ = [
    "AnalogGauge",
    "MOM_WIDTH",
    "GAUGE_SIZE",
    "LCD_WIDTH",
    "LCD_HEIGHT",
    "GRAPH_HEIGHT",
]