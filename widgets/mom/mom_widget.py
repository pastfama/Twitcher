"""Circular analog gauge QWidget for displaying momentum values.

Modern dark-themed gauge with smooth arcs and clean typography.

Supports two size variants via ``SizeVariant``:
    M (Medium) — 80×80 gauge + LCD (140×60) + graph strip (30px) + indicators
    S (Small)  — 50×50 gauge only, no LCD/graph/indicators

Size Constants (M, exported for backward compat):
    MOM_WIDTH   = 280   Total width of MOM section
    GAUGE_SIZE  = 80    Diameter of circular gauge
    LCD_WIDTH   = 140   Width of QLCDNumber viewer-count
    LCD_HEIGHT  = 60    Height of QLCDNumber viewer-count
    GRAPH_HEIGHT= 30    Height of ViewerHistoryGraph strip

Architecture Notes:
    The gauge value range is 0-100.  Momentum percentage (-50 to +50)
    is shifted by +50 before calling ``set_value()``:
        -50% → gauge 0   (red, strong decline)
          0% → gauge 50  (yellow, stable)
        +50% → gauge 100 (green, strong rise)

    The gauge colour transitions automatically through five bands:
        0-20  → #ff3366 (red)
        20-40 → #ff8800 (orange)
        40-60 → #ffdd00 (yellow)
        60-80 → #00ccff (cyan)
        80-100→ #00ff88 (green)
"""

import math

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from widgets.base import SizeVariant, SizedWidget, WidgetMetrics


# Backward-compat exports (M size defaults)
MOM_WIDTH = 280
GAUGE_SIZE = 80
LCD_WIDTH = 140
LCD_HEIGHT = 60
GRAPH_HEIGHT = 30


class AnalogGauge(QWidget, SizedWidget):
    """Circular analog gauge with smooth needle animation showing momentum (0-100).

    Supports M (Medium) and S (Small) size variants:
        M: 80×80 gauge (full panel)
        S: 50×50 gauge (compact sidebar)
    """

    ANIMATION_DURATION_MS = 600

    def __init__(self, parent=None, size=None, variant=SizeVariant.M):
        super().__init__(parent)
        self._init_metrics(variant)

        # If legacy callers pass `size=80`, use that; otherwise use variant
        if size is not None:
            self._gauge_size = size
        else:
            self._gauge_size = self._metrics.mom_gauge_size

        self._displayed_value = 50.0
        self._target_value = 50.0
        self._label = "MOM"
        self.setFixedSize(self._gauge_size, self._gauge_size)

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._tick_animation)
        self._anim_timer.start()

    def sizeHint(self):
        return QSize(self._gauge_size, self._gauge_size)

    def set_value(self, value: int, label: str = None):
        """Set the target value. The needle animates smoothly to it."""
        self._target_value = max(0.0, min(100.0, float(value)))
        if label is not None:
            self._label = label
        if not self._anim_timer.isActive():
            self._anim_timer.start()

    def _tick_animation(self):
        diff = self._target_value - self._displayed_value
        if abs(diff) < 0.5:
            self._displayed_value = self._target_value
            self._anim_timer.stop()
        else:
            self._displayed_value += diff * 0.15
        self.update()

    def get_value(self):
        return self._target_value

    def get_color(self):
        v = self._displayed_value
        if v < 30:
            return QColor(255, 80, 80)
        elif v < 50:
            return QColor(255, 165, 0)
        elif v < 70:
            return QColor(200, 180, 0)
        elif v < 85:
            return QColor(0, 200, 255)
        else:
            return QColor(0, 255, 128)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2
        r = min(w, h) / 2 - 6

        # Scale font/pen sizes based on gauge size
        scale = self._gauge_size / 80.0
        pen_width = max(2, int(4 * scale))
        dot_radius = max(2, int(3 * scale))
        font_size = max(6, int(9 * scale))
        label_size = max(5, int(7 * scale))
        needle_margin = max(4, int(8 * scale))

        # Background
        bg_pen = QPen(QColor(30, 30, 45))
        bg_pen.setWidthF(pen_width)
        painter.setPen(bg_pen)
        painter.setBrush(QColor(20, 20, 35))
        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # Value arc
        start_angle = 135
        sweep = 270
        normalized = self._displayed_value / 100.0
        value_sweep = int(normalized * sweep)
        color = self.get_color()

        val_pen = QPen(color)
        val_pen.setWidthF(pen_width)
        painter.setPen(val_pen)
        painter.drawArc(
            QRectF(cx - r, cy - r, r * 2, r * 2),
            start_angle * 16,
            -value_sweep * 16
        )

        # Needle
        angle_deg = start_angle - normalized * sweep
        angle_rad = math.radians(angle_deg)
        needle_length = r - needle_margin
        nx = cx + needle_length * math.cos(angle_rad)
        ny = cy - needle_length * math.sin(angle_rad)

        needle_pen = QPen(color)
        needle_pen.setWidthF(max(1, int(2 * scale)))
        painter.setPen(needle_pen)
        painter.drawLine(int(cx), int(cy), int(nx), int(ny))

        # Center dot
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx - dot_radius, cy - dot_radius, dot_radius * 2, dot_radius * 2))

        # Value text
        painter.setPen(color)
        painter.setFont(QFont("Segoe UI", font_size, QFont.Weight.Bold))
        painter.drawText(
            QRectF(cx - 20, cy + 6, 40, 14),
            Qt.AlignmentFlag.AlignCenter,
            str(int(self._target_value)),
        )

        # Label
        painter.setPen(QColor(0, 200, 255))
        painter.setFont(QFont("Segoe UI", label_size, QFont.Weight.Bold))
        painter.drawText(
            QRectF(0, h - 13, w, 13),
            Qt.AlignmentFlag.AlignCenter,
            self._label,
        )