"""Circular analog gauge QWidget for displaying momentum values.

This widget shows a circular gauge with a needle pointer that indicates
values from 0-100 with color-coded zones:
- 0-30: Red (declining)
- 30-50: Orange
- 50-70: Yellow (stable)
- 70-85: Cyan (rising)
- 85-100: Green (strong rise)
"""

import math

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


class AnalogGauge(QWidget):
    """Circular analog gauge with needle showing momentum value (0-100).

    Usage:
        gauge = AnalogGauge()
        gauge.set_value(75, "MOM")  # Set value and label, triggers repaint
    """

    def __init__(self, parent=None, size=90):
        super().__init__(parent)
        self._value = 50  # 0-100 scale
        self._label = "MOM"
        self._width = size
        self._height = size
        self.setFixedSize(size, size)

    def setFixedSize(self, width, height):
        """Set fixed dimensions for the gauge."""
        self._width = width
        self._height = height
        super().setFixedSize(width, height)

    def sizeHint(self):
        """Return recommended size."""
        return QSize(self._width, self._height)

    def set_value(self, value: int, label: str = None):
        """Set value from 0 to 100 and repaint.

        Args:
            value: Momentum value (0-100)
            label: Optional text label to display below gauge
        """
        self._value = max(0, min(100, int(value)))
        if label is not None:
            self._label = label
        self.update()

    def get_value(self):
        """Return current gauge value."""
        return self._value

    def get_color(self):
        """Return current color based on value."""
        if self._value < 30:
            return QColor(255, 80, 80)  # Red - declining
        elif self._value < 50:
            return QColor(255, 165, 0)  # Orange
        elif self._value < 70:
            return QColor(255, 200, 0)  # Yellow - stable
        elif self._value < 85:
            return QColor(0, 255, 255)  # Cyan - rising
        else:
            return QColor(0, 255, 128)  # Green - strong rise

    def paintEvent(self, event):
        """Paint the gauge."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2
        r = min(w, h) / 2 - 6

        # --- background circle ---
        bg_pen = QPen(QColor(40, 40, 40))
        bg_pen.setWidthF(4)
        painter.setPen(bg_pen)
        painter.setBrush(QColor(26, 26, 46))
        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # --- value arc (from 135deg, sweeping 270deg clockwise) ---
        start_angle = 135  # degrees, Qt measures counter-clockwise from 3 o'clock
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
            -value_sweep * 16  # negative = clockwise
        )

        # --- needle ---
        angle_deg = start_angle - normalized * sweep
        angle_rad = math.radians(angle_deg)
        needle_length = r - 8
        nx = cx + needle_length * math.cos(angle_rad)
        ny = cy - needle_length * math.sin(angle_rad)

        needle_pen = QPen(color)
        needle_pen.setWidthF(2)
        painter.setPen(needle_pen)
        painter.drawLine(int(cx), int(cy), int(nx), int(ny))

        # --- center dot ---
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx - 3, cy - 3, 6, 6))

        # --- value text (centered) ---
        painter.setPen(color)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(
            QRectF(cx - 20, cy + 6, 40, 14),
            Qt.AlignmentFlag.AlignCenter,
            str(self._value),
        )

        # --- label (bottom) ---
        painter.setPen(QColor(0, 255, 255))
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.drawText(
            QRectF(0, h - 13, w, 13),
            Qt.AlignmentFlag.AlignCenter,
            self._label,
        )