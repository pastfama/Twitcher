"""Viewer history sparkline widget — mini graph showing recent viewer counts.

A reusable QWidget that displays a sparkline of the last ~30 viewer-count
samples with a filled gradient area and subtle grid lines.
"""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import QWidget


class ViewerHistoryGraph(QWidget):
    """Sparkline showing the last ~30 viewer-count samples."""

    MAX_POINTS = 30

    # --- theme colors ---
    _BG = "#0a0d18"
    _BORDER = "#3a3a5a"
    _LINE = "#00ffff"
    _FILL_TOP = "#00ffff"
    _GRID = "#1a2a4b"
    _TEXT = "#6a7188"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points: list[int] = []
        self.setMinimumHeight(40)
        self.setMaximumHeight(70)

    def add_point(self, value: int):
        """Add a new viewer-count sample and trigger repaint."""
        self.points.append(value)
        if len(self.points) > self.MAX_POINTS:
            self.points = self.points[-self.MAX_POINTS:]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            w = self.width()
            h = self.height()

            # --- background + border ---
            painter.fillRect(0, 0, w, h, QColor(self._BG))
            border_pen = QPen(QColor(self._BORDER))
            border_pen.setWidthF(1)
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(0, 0, w - 1, h - 1)

            if not self.points:
                painter.setPen(QColor(self._TEXT))
                painter.setFont(QFont("Segoe UI", 8))
                painter.drawText(
                    QRectF(0, 0, w, h),
                    Qt.AlignmentFlag.AlignCenter,
                    "No data",
                )
                return

            # Inner padding
            pad = 4
            gw = w - pad * 2
            gh = h - pad * 2

            max_val = max(self.points) or 1

            # --- Y-axis grid lines (4 lines) ---
            grid_pen = QPen(QColor(self._GRID))
            grid_pen.setWidthF(0.5)
            grid_pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(grid_pen)

            text_pen = QPen(QColor(self._TEXT))
            painter.setFont(QFont("Segoe UI", 7))
            for i in range(1, 4):
                y = pad + gh - (i * gh / 4)
                painter.drawLine(int(pad), int(y), int(pad + gw), int(y))

            # --- filled area ---
            path = QPainterPath()
            path.moveTo(pad, pad + gh)
            n = len(self.points)
            for i, v in enumerate(self.points):
                x = pad + (i * gw / max(n - 1, 1))
                y = pad + gh - (v / max_val) * gh
                path.lineTo(x, y)
            path.lineTo(pad + gw, pad + gh)
            path.closeSubpath()

            gradient = QLinearGradient(0, pad, 0, pad + gh)
            fill_color = QColor(self._FILL_TOP)
            fill_color.setAlpha(50)
            gradient.setColorAt(0, fill_color)
            fill_color.setAlpha(0)
            gradient.setColorAt(1, fill_color)
            painter.fillPath(path, gradient)

            # --- line ---
            pen = QPen(QColor(self._LINE))
            pen.setWidthF(1.5)
            painter.setPen(pen)

            for i in range(n - 1):
                x1 = pad + (i * gw / max(n - 1, 1))
                y1 = pad + gh - (self.points[i] / max_val) * gh
                x2 = pad + ((i + 1) * gw / max(n - 1, 1))
                y2 = pad + gh - (self.points[i + 1] / max_val) * gh
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))

            # --- latest value dot ---
            if n > 0:
                lx = pad + ((n - 1) * gw / max(n - 1, 1))
                ly = pad + gh - (self.points[-1] / max_val) * gh
                painter.setBrush(QColor(self._LINE))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(lx - 3, ly - 3, 6, 6))
        finally:
            painter.end()
