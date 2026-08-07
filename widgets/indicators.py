"""Neon indicator widget — glowing status light with a text label.

A reusable QWidget that displays a small glowing dot + label, used for
status indicators like LIVE / CHAT / VIEWERS.
"""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


class NeonIndicator(QWidget):
    """Glowing status light with a text label (LIVE / CHAT / VIEWERS)."""

    def __init__(self, label: str, color: str, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = QColor(color)
        self._active = False
        self.setFixedSize(60, 24)

    def set_active(self, active: bool):
        """Turn the indicator on (glowing) or off (dim)."""
        self._active = active
        self.update()

    def is_active(self):
        """Return whether the indicator is currently active."""
        return self._active

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # --- dot ---
            if self._active:
                painter.setBrush(self._color)
                painter.setPen(Qt.PenStyle.NoPen)
            else:
                painter.setBrush(QColor(40, 40, 40))
                painter.setPen(QPen(QColor(60, 60, 60)))

            painter.drawEllipse(2, 5, 12, 12)

            # --- label ---
            painter.setPen(
                self._color if self._active else QColor(100, 100, 100)
            )
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.drawText(
                QRectF(16, 0, self.width() - 16, self.height()),
                Qt.AlignmentFlag.AlignVCenter,
                self._label,
            )
        finally:
            painter.end()