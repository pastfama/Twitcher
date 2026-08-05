"""Circular analog gauge QWidget for displaying momentum values.

Modern dark-themed gauge with smooth arcs and clean typography.

Size Constants (exported from this module, used across the app):
---------------------------------------------------------------
MOM_WIDTH   = 280   Total horizontal width of the MOM section in the
                     Current Watching panel (left column).
GAUGE_SIZE  = 80    Diameter (px) of the circular AnalogGauge widget.
LCD_WIDTH   = 140   Width of the QLCDNumber viewer-count display.
LCD_HEIGHT  = 60    Height of the QLCDNumber viewer-count display.
GRAPH_HEIGHT= 30    Height of the ViewerHistoryGraph strip chart.

Architecture Notes:
--------------------
The gauge value range is 0-100.  In the currwatching panel, the raw
momentum percentage from AnalyticsEngine (typically -50 to +50) is
shifted by +50 before calling ``set_value()``, so that:
    -50 %  →  gauge 0   (red, strong decline)
      0 %  →  gauge 50  (yellow, stable)
    +50 %  →  gauge 100 (green, strong rise)

The gauge colour transitions automatically through five bands:
    0-20  →  #ff3366 (red)
    20-40 →  #ff8800 (orange)
    40-60 →  #ffdd00 (yellow)
    60-80 →  #00ccff (cyan)
    80-100→  #00ff88 (green)
"""

import math

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


# Top-level size constants (codewide)
MOM_WIDTH = 280
GAUGE_SIZE = 80
LCD_WIDTH = 140
LCD_HEIGHT = 60
GRAPH_HEIGHT = 30


class AnalogGauge(QWidget):
    """Circular analog gauge with smooth needle animation showing momentum value (0-100).

    The gauge smoothly transitions between values using a QPropertyAnimation
    instead of jumping instantly.  This makes momentum changes feel fluid
    and gives the user immediate visual feedback on trend direction.
    """

    # Class constants
    DEFAULT_SIZE = GAUGE_SIZE
    ANIMATION_DURATION_MS = 600  # smooth transition time

    def __init__(self, parent=None, size=None):
        super().__init__(parent)
        self._displayed_value = 50.0   # what is currently painted (animated)
        self._target_value = 50.0      # where the needle is heading
        self._label = "MOM"
        self._size = size if size is not None else self.DEFAULT_SIZE
        self.setFixedSize(self._size, self._size)

        # Smooth animation timer — ticks at ~60fps for fluid needle movement
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)  # ~60 fps
        self._anim_timer.timeout.connect(self._tick_animation)
        self._anim_timer.start()

    def sizeHint(self):
        return QSize(self._size, self._size)

    def set_value(self, value: int, label: str = None):
        """Set the target value. The needle animates smoothly to it."""
        self._target_value = max(0.0, min(100.0, float(value)))
        if label is not None:
            self._label = label
        # Start animation timer if not already running
        if not self._anim_timer.isActive():
            self._anim_timer.start()

    def _tick_animation(self):
        """Interpolate displayed value toward target for smooth needle movement."""
        diff = self._target_value - self._displayed_value
        if abs(diff) < 0.5:
            # Close enough — snap to target and stop animating
            self._displayed_value = self._target_value
            self._anim_timer.stop()
        else:
            # Ease toward target (exponential smoothing, ~15% per tick)
            self._displayed_value += diff * 0.15
        self.update()

    def get_value(self):
        return self._target_value

    def get_color(self):
        """Return gauge color based on the *displayed* (animated) value."""
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
        """Paint the gauge using the animated displayed value for smooth transitions."""
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

        # Value arc — uses _displayed_value for smooth animation
        start_angle = 135
        sweep = 270
        normalized = self._displayed_value / 100.0
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

        # Needle — animated position
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

        # Value text — show target value so user sees the actual number
        painter.setPen(color)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(
            QRectF(cx - 20, cy + 6, 40, 14),
            Qt.AlignmentFlag.AlignCenter,
            str(int(self._target_value)),
        )

        # Label
        painter.setPen(QColor(0, 200, 255))
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.drawText(
            QRectF(0, h - 13, w, 13),
            Qt.AlignmentFlag.AlignCenter,
            self._label,
        )
