"""Viewer history sparkline widget — mini graph showing recent viewer counts.

A reusable QWidget that displays a sparkline of the last ~30 viewer-count
samples with a filled gradient area, time-based X-axis, a fixed Y floor
(so steady streams show real wobble instead of flattening), subtle grid
lines, and current/max value overlays.
"""

import time

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import QWidget


class ViewerHistoryGraph(QWidget):
    """Sparkline showing the last ~30 viewer-count samples over time."""

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
        # Each entry: (timestamp_seconds, value)
        self.points: list[tuple[float, int]] = []
        self.setMinimumHeight(40)
        self.setMaximumHeight(70)

    # ============================================================
    # PUBLIC API
    # ============================================================

    def add_point(self, value: int):
        """Add a viewer-count sample with its timestamp and repaint.

        Duplicate consecutive values are kept — the time dimension is what
        matters for the sparkline — but if the *same value* arrives within
        2 seconds it is treated as a duplicate tick (e.g. double update on
        the same 4s cycle) and skipped so the X-axis stays honest.
        """
        now = time.time()
        if self.points and now - self.points[-1][0] < 2.0:
            # Suppress double-append from the same refresh cycle.
            self.points[-1] = (now, int(value))
            self.update()
            return

        self.points.append((now, int(value)))
        if len(self.points) > self.MAX_POINTS:
            self.points = self.points[-self.MAX_POINTS:]
        self.update()

    def clear(self):
        """Remove all points and trigger repaint."""
        self.points = []
        self.update()

    # ============================================================
    # PAINTING
    # ============================================================

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

            # Inner padding — extra left space for the min-label slot.
            pad = 4
            left_pad = 18
            gw = w - pad - left_pad - pad
            gh = h - pad * 2

            values = [v for _, v in self.points]
            t_min = self.points[0][0]
            t_max = self.points[-1][0]
            t_span = max(t_max - t_min, 1.0)

            # --- Y scale: fixed floor at 0, headroom above max ---
            v_max = max(values) or 1
            v_floor = 0
            # 10% headroom above the max so the line never kisses the top.
            v_top = v_max + max(1, int(v_max * 0.10))
            v_span = max(v_top - v_floor, 1)

            def map_x(ts):
                return left_pad + pad + (ts - t_min) / t_span * gw

            def map_y(v):
                return pad + gh - (v - v_floor) / v_span * gh

            # --- Y-axis grid lines (4 lines + min/max labels) ---
            grid_pen = QPen(QColor(self._GRID))
            grid_pen.setWidthF(0.5)
            grid_pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(grid_pen)

            text_pen = QPen(QColor(self._TEXT))
            painter.setFont(QFont("Segoe UI", 6))
            for i in range(1, 4):
                y = pad + gh - (i * gh / 4)
                painter.drawLine(int(left_pad + pad), int(y), int(left_pad + pad + gw), int(y))

            # Min label (always 0) bottom-left, max label top-left.
            painter.setPen(text_pen)
            min_text = str(v_floor)
            painter.drawText(
                QRectF(0, pad + gh - 8, left_pad - 2, 10),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                min_text,
            )
            painter.drawText(
                QRectF(0, pad - 4, left_pad - 2, 10),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                str(v_top),
            )

            # --- filled area (time-based X) ---
            path = QPainterPath()
            path.moveTo(map_x(t_min), pad + gh)
            n = len(self.points)
            for i in range(n):
                x = map_x(self.points[i][0])
                y = map_y(self.points[i][1])
                path.lineTo(x, y)
            path.lineTo(map_x(t_max), pad + gh)
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
                x1 = map_x(self.points[i][0])
                y1 = map_y(self.points[i][1])
                x2 = map_x(self.points[i + 1][0])
                y2 = map_y(self.points[i + 1][1])
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))

            # --- latest value dot + current/LIVE value ---
            lx = map_x(self.points[-1][0])
            ly = map_y(self.points[-1][1])
            painter.setBrush(QColor(self._LINE))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(lx - 3, ly - 3, 6, 6))

            # Current value label top-right (white/cyan, readable).
            painter.setPen(QColor("#c8cce0"))
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            cur_text = str(self.points[-1][1])
            cur_w = painter.fontMetrics().horizontalAdvance(cur_text)
            painter.drawText(
                QRectF(w - cur_w - pad - 2, pad - 4, cur_w + 4, 10),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                cur_text,
            )
        finally:
            painter.end()