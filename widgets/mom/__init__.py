"""MOM (Momentum) gauge widget module.

Provides a circular analog gauge for displaying momentum values.

Exports:
- AnalogGauge: Circular gauge widget
- Size constants: MOM_WIDTH, GAUGE_SIZE, LCD_WIDTH, LCD_HEIGHT, GRAPH_HEIGHT
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