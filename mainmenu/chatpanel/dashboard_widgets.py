"""Dashboard Widgets — factory functions for the 36-metric dashboard.

Each factory creates a styled Qt widget (QLCDNumber, AnalogGauge,
QProgressBar, Sparkline, NeonIndicator, or styled QLabel) with a
small caption label beneath it.  All widgets accept a MoodPalette
via ``apply_palette()`` so the mood engine can recolour them at runtime.
"""

from typing import Optional, List
from PySide6.QtCore import Qt, QSize, QTimer, QPointF
from PySide6.QtGui import QFont, QColor, QPainter, QLinearGradient, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLCDNumber,
    QProgressBar, QFrame, QGraphicsDropShadowEffect,
)

from .mood_engine import MoodPalette, MOODS


# ── Helpers ─────────────────────────────────────────────────────────────

def _caption_label(text: str, color: str = "#8b93ad") -> QLabel:
    """Small centred label beneath a metric widget."""
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(f"""
        color: {color};
        font-size: 8px;
        font-weight: bold;
        font-family: 'Segoe UI';
        padding: 0;
        margin: 0;
    """)
    lbl.setFixedHeight(12)
    return lbl


def _apply_glow(widget: QWidget, color: str):
    """Attach or update a subtle drop-shadow glow on *widget*."""
    glow = QGraphicsDropShadowEffect(widget)
    glow.setBlurRadius(12)
    glow.setColor(QColor(color))
    glow.setOffset(0, 0)
    widget.setGraphicsEffect(glow)


# ── LCD Metric ──────────────────────────────────────────────────────────

class LCDMetric(QWidget):
    """A QLCDNumber with a caption label.  Displays integer or formatted
    numeric values."""

    def __init__(self, label: str, digits: int = 6,
                 palette: Optional[MoodPalette] = None, parent=None):
        super().__init__(parent)
        pal = palette or MOODS["neutral"]
        self._label_text = label

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 0)
        layout.setSpacing(1)

        self.lcd = QLCDNumber(digits)
        self.lcd.setSegmentStyle(QLCDNumber.SegmentStyle.Filled)
        self.lcd.setFixedHeight(36)
        self.lcd.setStyleSheet(self._lcd_style(pal.lcd_digit, pal.progress_bg))
        layout.addWidget(self.lcd)

        self.caption = _caption_label(label, pal.text_muted)
        layout.addWidget(self.caption)

        self._apply_palette(pal)

    def set_value(self, value, fmt: str = ""):
        """Update the displayed value.  *fmt* can be 'int', 'float1', etc."""
        if fmt == "int":
            self.lcd.display(int(value))
        elif fmt == "float1":
            self.lcd.display(float(f"{value:.1f}"))
        else:
            self.lcd.display(value)

    def apply_palette(self, pal: MoodPalette):
        self._apply_palette(pal)

    def _apply_palette(self, pal: MoodPalette):
        self.lcd.setStyleSheet(self._lcd_style(pal.lcd_digit, pal.progress_bg))
        self.caption.setStyleSheet(f"""
            color: {pal.text_muted};
            font-size: 8px; font-weight: bold;
            font-family: 'Segoe UI'; padding: 0; margin: 0;
        """)

    @staticmethod
    def _lcd_style(digit_color: str, bg: str) -> str:
        return f"""
            QLCDNumber {{
                background-color: {bg};
                color: {digit_color};
                border: 1px solid {digit_color}40;
                border-radius: 4px;
            }}
        """


# ── Gauge Metric ────────────────────────────────────────────────────────

class GaugeMetric(QWidget):
    """A custom-painted semicircular gauge (0-100) with a caption label."""

    def __init__(self, label: str, palette: Optional[MoodPalette] = None,
                 parent=None):
        super().__init__(parent)
        pal = palette or MOODS["neutral"]
        self._value = 0.0
        self._accent = pal.accent
        self._dim = pal.accent_dim
        self._bg = pal.progress_bg
        self._text_muted = pal.text_muted

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 0)
        layout.setSpacing(1)

        self._canvas = _GaugeCanvas(pal)
        self._canvas.setFixedHeight(38)
        layout.addWidget(self._canvas)

        self.caption = _caption_label(label, pal.text_muted)
        layout.addWidget(self.caption)

    def set_value(self, value: float):
        """Set gauge value 0-100."""
        self._value = max(0.0, min(100.0, value))
        self._canvas.set_value(self._value)

    def apply_palette(self, pal: MoodPalette):
        self._canvas.set_colors(pal.accent, pal.accent_dim, pal.progress_bg)
        self.caption.setStyleSheet(f"""
            color: {pal.text_muted};
            font-size: 8px; font-weight: bold;
            font-family: 'Segoe UI'; padding: 0; margin: 0;
        """)


class _GaugeCanvas(QWidget):
    """Custom-painted semicircular gauge arc."""

    def __init__(self, pal: MoodPalette, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self._accent = pal.accent
        self._dim = pal.accent_dim
        self._bg = pal.progress_bg

    def set_value(self, v: float):
        self._value = v
        self.update()

    def set_colors(self, accent: str, dim: str, bg: str):
        self._accent = accent
        self._dim = dim
        self._bg = bg
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h - 4
        radius = min(w // 2 - 4, h - 8)

        # background arc
        pen = QPen(QColor(self._dim), 4, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(cx - radius, cy - radius, radius * 2, radius * 2,
                  180 * 16, -180 * 16)

        # value arc
        span = int(-self._value / 100.0 * 180 * 16)
        pen.setColor(QColor(self._accent))
        pen.setWidth(4)
        p.setPen(pen)
        p.drawArc(cx - radius, cy - radius, radius * 2, radius * 2,
                  180 * 16, span)

        # needle
        import math
        angle = math.radians(180 - self._value / 100.0 * 180)
        nx = cx + int(radius * 0.8 * math.cos(angle))
        ny = cy - int(radius * 0.8 * math.sin(angle))
        needle_pen = QPen(QColor(self._accent), 2)
        p.setPen(needle_pen)
        p.drawLine(cx, cy, nx, ny)

        # centre dot
        p.setBrush(QColor(self._accent))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), 3, 3)

        # value text
        p.setPen(QColor(self._accent))
        font = QFont("Segoe UI", 7, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(0, 0, w, cy - radius - 2,
                   Qt.AlignmentFlag.AlignCenter, f"{self._value:.0f}")
        p.end()


# ── Progress Metric ─────────────────────────────────────────────────────

class ProgressMetric(QWidget):
    """A horizontal progress bar with a caption label."""

    def __init__(self, label: str, palette: Optional[MoodPalette] = None,
                 parent=None):
        super().__init__(parent)
        pal = palette or MOODS["neutral"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 0)
        layout.setSpacing(1)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(True)
        self.bar.setFixedHeight(18)
        self._apply_bar_style(pal)
        layout.addWidget(self.bar)

        self.caption = _caption_label(label, pal.text_muted)
        layout.addWidget(self.caption)

    def set_value(self, value: int):
        self.bar.setValue(max(0, min(100, value)))

    def apply_palette(self, pal: MoodPalette):
        self._apply_bar_style(pal)
        self.caption.setStyleSheet(f"""
            color: {pal.text_muted};
            font-size: 8px; font-weight: bold;
            font-family: 'Segoe UI'; padding: 0; margin: 0;
        """)

    def _apply_bar_style(self, pal: MoodPalette):
        self.bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {pal.progress_bg};
                border: 1px solid {pal.accent_dim};
                border-radius: 3px;
                text-align: center;
                color: {pal.text};
                font-size: 8px;
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background-color: {pal.progress_fill};
                border-radius: 2px;
            }}
        """)


# ── Sparkline Metric ────────────────────────────────────────────────────

class SparklineMetric(QWidget):
    """A mini line chart showing a rolling history of values."""

    def __init__(self, label: str, max_points: int = 40,
                 palette: Optional[MoodPalette] = None, parent=None):
        super().__init__(parent)
        pal = palette or MOODS["neutral"]
        self._points: List[float] = []
        self._max_points = max_points
        self._accent = pal.accent
        self._fill = pal.accent_dim
        self._bg = pal.progress_bg

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 0)
        layout.setSpacing(1)

        self._canvas = _SparklineCanvas(pal, max_points)
        self._canvas.setFixedHeight(38)
        layout.addWidget(self._canvas)

        self.caption = _caption_label(label, pal.text_muted)
        layout.addWidget(self.caption)

    def add_point(self, value: float):
        self._points.append(value)
        if len(self._points) > self._max_points:
            self._points = self._points[-self._max_points:]
        self._canvas.set_points(self._points)

    def set_points(self, points: List[float]):
        self._points = list(points)[-self._max_points:]
        self._canvas.set_points(self._points)

    def apply_palette(self, pal: MoodPalette):
        self._canvas.set_colors(pal.accent, pal.accent_dim, pal.progress_bg)
        self.caption.setStyleSheet(f"""
            color: {pal.text_muted};
            font-size: 8px; font-weight: bold;
            font-family: 'Segoe UI'; padding: 0; margin: 0;
        """)


class _SparklineCanvas(QWidget):
    """Custom-painted sparkline."""

    def __init__(self, pal: MoodPalette, max_points: int = 40, parent=None):
        super().__init__(parent)
        self._points: List[float] = []
        self._max_points = max_points
        self._accent = pal.accent
        self._fill = pal.accent_dim
        self._bg = pal.progress_bg

    def set_points(self, pts: List[float]):
        self._points = list(pts)
        self.update()

    def set_colors(self, accent: str, fill: str, bg: str):
        self._accent = accent
        self._fill = fill
        self._bg = bg
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # background
        p.fillRect(0, 0, w, h, QColor(self._bg))

        pts = self._points
        if len(pts) < 2:
            p.end()
            return

        lo = min(pts)
        hi = max(pts)
        rng = hi - lo if hi != lo else 1.0
        margin = 4

        # build polyline
        points = []
        for i, v in enumerate(pts):
            x = margin + i * (w - 2 * margin) / max(1, self._max_points - 1)
            y = h - margin - (v - lo) / rng * (h - 2 * margin)
            points.append(QPointF(x, y))

        # fill polygon
        fill_pts = list(points)
        fill_pts.append(QPointF(points[-1].x(), h))
        fill_pts.append(QPointF(points[0].x(), h))
        from PySide6.QtGui import QPolygonF
        p.setBrush(QColor(self._fill + "40"))  # 25% alpha
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygonF(fill_pts))

        # line
        pen = QPen(QColor(self._accent), 2, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawPolyline(QPolygonF(points))

        # glow dot at last point
        if points:
            lp = points[-1]
            p.setBrush(QColor(self._accent))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(lp, 3, 3)

        p.end()


# ── Neon Metric ─────────────────────────────────────────────────────────

class NeonMetric(QWidget):
    """A glowing neon indicator (dot + label) with an on/off state."""

    def __init__(self, label: str, palette: Optional[MoodPalette] = None,
                 parent=None):
        super().__init__(parent)
        pal = palette or MOODS["neutral"]
        self._active = False
        self._color = pal.accent
        self._dim = pal.accent_dim

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 0)
        layout.setSpacing(1)

        self._indicator = QLabel("● OFF")
        self._indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._indicator.setFixedHeight(36)
        self._update_visual()
        layout.addWidget(self._indicator)

        self.caption = _caption_label(label, pal.text_muted)
        layout.addWidget(self.caption)

    def set_active(self, active: bool, text: str = ""):
        self._active = active
        if text:
            self._indicator.setText(text)
        else:
            self._indicator.setText("● ON" if active else "● OFF")
        self._update_visual()

    def apply_palette(self, pal: MoodPalette):
        self._color = pal.accent
        self._dim = pal.accent_dim
        self._update_visual()
        self.caption.setStyleSheet(f"""
            color: {pal.text_muted};
            font-size: 8px; font-weight: bold;
            font-family: 'Segoe UI'; padding: 0; margin: 0;
        """)

    def _update_visual(self):
        c = self._color if self._active else self._dim
        text_color = self._color if self._active else "#6a7188"
        self._indicator.setStyleSheet(f"""
            color: {text_color};
            font-size: 12px;
            font-weight: bold;
            font-family: 'Segoe UI';
            background-color: #0a0d18;
            border: 1px solid {c};
            border-radius: 4px;
        """)


# ── Styled Label Metric ────────────────────────────────────────────────

class LabelMetric(QWidget):
    """A large styled text label for qualitative metrics (e.g. category
    names, letter grades)."""

    def __init__(self, label: str, palette: Optional[MoodPalette] = None,
                 parent=None):
        super().__init__(parent)
        pal = palette or MOODS["neutral"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 0)
        layout.setSpacing(1)

        self.value_label = QLabel("—")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setFixedHeight(36)
        self.value_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._apply_style(pal)
        layout.addWidget(self.value_label)

        self.caption = _caption_label(label, pal.text_muted)
        layout.addWidget(self.caption)

    def set_text(self, text: str):
        self.value_label.setText(text)

    def apply_palette(self, pal: MoodPalette):
        self._apply_style(pal)
        self.caption.setStyleSheet(f"""
            color: {pal.text_muted};
            font-size: 8px; font-weight: bold;
            font-family: 'Segoe UI'; padding: 0; margin: 0;
        """)

    def _apply_style(self, pal: MoodPalette):
        self.value_label.setStyleSheet(f"""
            color: {pal.accent};
            font-size: 14px;
            font-weight: bold;
            font-family: 'Segoe UI';
            background-color: {pal.progress_bg};
            border: 1px solid {pal.accent_dim};
            border-radius: 4px;
        """)


# ── Tab Button ──────────────────────────────────────────────────────────

class TabButton(QLabel):
    """A clickable tab label with mood-reactive styling."""

    def __init__(self, text: str, tab_id: str, palette: Optional[MoodPalette] = None,
                 parent=None):
        super().__init__(text, parent)
        self.tab_id = tab_id
        self._active = False
        self._pal = palette or MOODS["neutral"]
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(26)
        self._update_style()

    def set_active(self, active: bool):
        self._active = active
        self._update_style()

    def apply_palette(self, pal: MoodPalette):
        self._pal = pal
        self._update_style()

    def _update_style(self):
        if self._active:
            self.setStyleSheet(f"""
                color: {self._pal.text};
                font-size: 10px;
                font-weight: bold;
                font-family: 'Segoe UI';
                border-bottom: 2px solid {self._pal.tab_active};
                padding: 2px 8px;
                background-color: {self._pal.progress_bg};
            """)
        else:
            self.setStyleSheet(f"""
                color: {self._pal.tab_inactive};
                font-size: 10px;
                font-weight: bold;
                font-family: 'Segoe UI';
                border-bottom: 2px solid transparent;
                padding: 2px 8px;
                background-color: transparent;
            """)

    def mousePressEvent(self, event):
        # Emit via parent dashboard's switch_tab
        parent = self.parent()
        while parent:
            if hasattr(parent, 'switch_tab'):
                parent.switch_tab(self.tab_id)
                return
            parent = parent.parent()
        super().mousePressEvent(event)