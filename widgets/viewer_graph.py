"""Viewer history sparkline widget — mini graph showing recent viewer counts.

A reusable QWidget that displays a sparkline of the last ~30 viewer-count
samples with a filled gradient area and grid lines.
"""

import math

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import QWidget


class ViewerHistoryGraph(QWidget):
    """Sparkline showing the last ~30 viewer-count samples."""

    MAX_POINTS = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points: list[int] = []
        self.setMinimumHeight(30)
        self.setMaximumHeight(50)

    def add_point(self, value: int):
        """Add a new viewer-count sample and trigger repaint."""
        self.points.append(value)
        if len(self.points) > self.MAX_POINTS:
            self.points = self.points[-self.MAX_POINTS:]
        self.update()

    def paintEvent(self, event):
        if not self.points:
            return

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            w = self.width()
            h = self.height()
            max_val = max(self.points) or 1

            # --- Y-axis labels and grid lines ---
            label_height = 15
            for i in range(5):
                y = h - (i * h / 4)
                value = int(max_val * (i / 4))
                painter.drawText(0, y, f"{value}")
                painter.drawLine(0, y, w, y)

            # --- filled area ---
            path = QPainterPath()
            path.moveTo(0, h)
            for i, v in enumerate(self.points):
                x = i * w / max(len(self.points) - 1, 1)
                y = h - (v / max_val) * h
                path.lineTo(x, y)
            path.lineTo(w, h)
            path.closeSubpath()

            gradient = QLinearGradient(0, 0, 0, h)
            gradient.setColorAt(0, QColor(0, 255, 255, 60))
            gradient.setColorAt(1, QColor(0, 255, 255, 0))
            painter.fillPath(path, gradient)

            # --- line ---
            pen = QPen(QColor(0, 255, 255))
            pen.setWidthF(1.5)
            painter.setPen(pen)

            for i in range(len(self.points) - 1):
                x1 = i * w / max(len(self.points) - 1, 1)
                y1 = h - (self.points[i] / max_val) * h
                x2 = (i + 1) * w / max(len(self.points) - 1, 1)
                y2 = h - (self.points[i + 1] / max_val) * h
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        finally:
            painter.end()