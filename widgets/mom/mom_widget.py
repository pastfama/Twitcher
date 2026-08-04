"""Circular analog gauge QWidget for displaying momentum values.

Modern dark-themed gauge with smooth arcs and clean typography.

Size constants (codewide):
- MOM_WIDTH: Total width of MOM section in panel
- GAUGE_SIZE: Diameter of circular gauge
- LCD_WIDTH/LCD_HEIGHT: Size of viewer count display
- GRAPH_HEIGHT: Height of viewer history graph strip
"""

import math

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


# Top-level size constants (codewide)
MOM_WIDTH = 280
GAUGE_SIZE = 80
LCD_WIDTH = 140
LCD_HEIGHT = 60
GRAPH_HEIGHT = 30


class AnalogGauge(QWidget):
    """Circular analog gauge with needle showing momentum value (0-100)."""

    # Class constants
    DEFAULT_SIZE = GAUGE_SIZE

    def __init__(self, parent=None, size=None):
        super().__init__(parent)
        self._value = 50
        self._label = "MOM"
        self._size = size if size is not None else self.DEFAULT_SIZE
        self.setFixedSize(self._size, self._size)

    def sizeHint(self):
        return QSize(self._size, self._size)

    def set_value(self, value: int, label: str = None):
        self._value = max(0, min(100, int(value)))
        if label is not None:
            self._label = label
        self.update()

    def get_value(self):
        return self._value

    def get_color(self):
        if self._value < 30:
            return QColor(255, 80, 80)
        elif self._value < 50:
            return QColor(255, 165, 0)
        elif self._value < 70:
            return QColor(200, 180, 0)
        elif self._value < 85:
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

        # Background
        bg_pen = QPen(QColor(30, 30, 45))
        bg_pen.setWidthF(4)
        painter.setPen(bg_pen)
        painter.setBrush(QColor(20, 20, 35))
        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # Value arc
        start_angle = 135
        sweep = 270
        normalized = self._value / 100.0
        value_sweep = int(normalized * sweep)
        color = self.get_color()

        val_pen = QPen(color)
        val_pen.setWidthF(4)
        painter.setPen(val_pen)
        painter.drawArc(
            QRectF(cx - r, cy - r, r * 2, r * 2),
            start_angle * 16,
            -value_sweep * 16
        )

        # Needle
        angle_deg = start_angle - normalized * sweep
        angle_rad = math.radians(angle_deg)
        needle_length = r - 8
        nx = cx + needle_length * math.cos(angle_rad)
        ny = cy - needle_length * math.sin(angle_rad)

        needle_pen = QPen(color)
        needle_pen.setWidthF(2)
        painter.setPen(needle_pen)
        painter.drawLine(int(cx), int(cy), int(nx), int(ny))

        # Center dot
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx - 3, cy - 3, 6, 6))

        # Value text
        painter.setPen(color)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(
            QRectF(cx - 20, cy + 6, 40, 14),
            Qt.AlignmentFlag.AlignCenter,
            str(self._value),
        )

        # Label
        painter.setPen(QColor(0, 200, 255))
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.drawText(
            QRectF(0, h - 13, w, 13),
            Qt.AlignmentFlag.AlignCenter,
            self._label,
        )