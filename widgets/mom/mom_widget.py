"""Circular analog gauge QWidget for displaying momentum values.

Modern dark-themed gauge with a gradient arc, scale ticks, a trend-aware
needle, and smooth value animation.

This gauge is the MOM (momentum) indicator — value 0 means "-50%" momentum,
50 means "0% (neutral)", and 100 means "+50%".  It receives a raw momentum
percent via :meth:`set_percent` and maps it onto the 0..100 dial.

Size constants (codewide):
- MOM_WIDTH: Total width of MOM section in panel
- GAUGE_SIZE: Diameter of circular gauge
- LCD_WIDTH/LCD_HEIGHT: Size of viewer count display
- GRAPH_HEIGHT: Height of viewer history graph strip
"""

import math

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


# Top-level size constants (codewide)
MOM_WIDTH = 280
GAUGE_SIZE = 80
LCD_WIDTH = 140
LCD_HEIGHT = 60
GRAPH_HEIGHT = 60


# --- palette (mirrors mainmenu.currwatching.theme.Theme) ---
_BG_OUTER = QColor(30, 30, 45)
_BG_INNER = QColor(20, 20, 35)
_CYAN = QColor(0, 200, 255)
_MUTED = QColor(139, 147, 173)
_DIM = QColor(106, 113, 136)
_FONT = "Segoe UI"

# --- momentum scale semantics ---
ARC_START = 135       # degrees (Qt coord; 0 = 3 o'clock, CCW positive)
ARC_SWEEP = 270       # total degrees of the dial
PERCENT_LOW = -5      # gauge value 0  -> momentum -5%
PERCENT_MID = 0       # gauge value 50 -> neutral
PERCENT_HIGH = 5      # gauge value 100-> +5%

# --- color ramp for the gradient arc (t in 0..1 -> QColor) ---
_RAMP = (
    (0.00, (255, 80, 80)),     # red
    (0.25, (255, 165, 0)),     # orange
    (0.50, (255, 220, 0)),     # amber
    (0.75, (0, 200, 255)),     # cyan
    (1.00, (0, 255, 128)),     # green
)


def _ramp_color(t: float) -> QColor:
    """Interpolate a color along the red->green momentum ramp."""
    t = max(0.0, min(1.0, t))
    for i in range(len(_RAMP) - 1):
        t0, c0 = _RAMP[i]
        t1, c1 = _RAMP[i + 1]
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0)
            return QColor(
                int(c0[0] + (c1[0] - c0[0]) * f),
                int(c0[1] + (c1[1] - c0[1]) * f),
                int(c0[2] + (c1[2] - c0[2]) * f),
            )
    r, g, b = _RAMP[-1][1]
    return QColor(r, g, b)


class AnalogGauge(QWidget):
    """Circular analog gauge with animated needle showing momentum (0-100)."""

    # Class constants
    DEFAULT_SIZE = GAUGE_SIZE
    ANIM_MS = 260

    def __init__(self, parent=None, size=None, label="MOM"):
        super().__init__(parent)
        self._value = 50
        self._display_value = 50.0
        self._label = label
        self._raw_percent = None
        self._status = None
        self._size = size if size is not None else self.DEFAULT_SIZE
        self.setFixedSize(self._size, self._size)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(self.ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_frame)

        self.setToolTip("Momentum gauge")
        self.setAccessibleName("Momentum gauge")

    # ============================================================
    # PUBLIC API
    # ============================================================

    def sizeHint(self):
        return QSize(self._size, self._size)

    def set_value(self, value: int, label: str = None):
        """Set gauge value on the 0..100 dial (50 = neutral).

        Animates smoothly from the current position.
        """
        target = max(0, min(100, int(value)))
        if label is not None:
            self._label = label
        self._value = target
        # Raw percent/status are cleared because the caller used raw 0-100.
        self._raw_percent = None
        self._status = None
        self._start_anim(target)
        self.update()

    def set_percent(self, percent, status=None):
        """Set momentum from a raw percent value (clamped to +/-50).

        Caller passes the analyzer's ``percent`` (a % change over the
        history window).  It is clamped to the dial's +/-50% semantics
        so a +150% spike pins at +50% instead of wrapping.
        """
        try:
            p = float(percent) if percent is not None else 0.0
        except (TypeError, ValueError):
            p = 0.0
        p = max(PERCENT_LOW, min(PERCENT_HIGH, p))
        self._raw_percent = p
        self._status = status or None
        target = round((p - PERCENT_LOW) / (PERCENT_HIGH - PERCENT_LOW) * 100)
        self._value = target
        self.setToolTip(self._build_tooltip())
        self._start_anim(target)
        self.update()

    def set_trend(self, status):
        """Set trend direction ("Rising"/"Declining"/"Stable") for the arrow."""
        self._status = status or None
        self.setToolTip(self._build_tooltip())
        self.update()

    def get_value(self):
        return self._value

    # ============================================================
    # INTERNALS
    # ============================================================

    def _build_tooltip(self):
        if self._raw_percent is None:
            return "Momentum gauge"
        delta = f"{self._raw_percent:+.1f}%"
        status = self._status or "Stable"
        return f"Momentum: {delta} ({status})"

    def _start_anim(self, target: int):
        self._anim.stop()
        self._anim.setStartValue(float(self._display_value))
        self._anim.setEndValue(float(target))
        self._anim.start()

    def _on_anim_frame(self, value):
        self._display_value = float(value)
        self.update()

    def _status_color(self):
        """Color used for the needle/delta based on trend status."""
        if not self._status:
            return _ramp_color(self._display_value / 100.0)
        s = str(self._status).lower()
        if "ris" in s or "spike" in s:
            return QColor(0, 255, 128)
        if "declin" in s or "fall" in s or "drop" in s:
            return QColor(255, 80, 80)
        return _CYAN

    def _percent_at(self, dial_value: float) -> float:
        """Convert a 0..100 dial position back to momentum percent."""
        return PERCENT_LOW + (dial_value / 100.0) * (PERCENT_HIGH - PERCENT_LOW)

    # ============================================================
    # PAINTING
    # ============================================================

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2
        r = min(w, h) / 2 - 6

        # --- background ---
        bg_pen = QPen(_BG_OUTER)
        bg_pen.setWidthF(4)
        painter.setPen(bg_pen)
        painter.setBrush(_BG_INNER)
        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # --- scale ticks + labels (0 / 25 / 50 / 75 / 100) ---
        self._draw_scale(painter, cx, cy, r)

        # --- gradient value arc ---
        self._draw_gradient_arc(painter, cx, cy, r)

        # --- needle + center dot ---
        color = self._status_color()
        normalized = self._display_value / 100.0
        self._draw_needle(painter, cx, cy, r, normalized, color)

        # --- delta / value text ---
        self._draw_center_text(painter, cx, cy, color)

        # --- label ---
        painter.setPen(_CYAN)
        painter.setFont(QFont(_FONT, 7, QFont.Weight.Bold))
        painter.drawText(
            QRectF(0, h - 12, w, 12),
            Qt.AlignmentFlag.AlignCenter,
            self._label,
        )
        painter.end()

    def _draw_scale(self, painter, cx, cy, r):
        """Draw ticks and percent labels around the fixed dial positions."""
        tick_pen = QPen(QColor(70, 80, 110))
        tick_pen.setWidthF(1)
        painter.setPen(tick_pen)
        painter.setFont(QFont(_FONT, 6))

        positions = (0, 25, 50, 75, 100)
        # Only label the three semantic anchors to avoid clutter at 80px.
        labels = {
            0: f"{PERCENT_LOW}",
            50: f"{PERCENT_MID}",
            100: f"{PERCENT_HIGH}",
        }

        for v in positions:
            angle_deg = ARC_START - (v / 100.0) * ARC_SWEEP
            if angle_deg < -180:
                angle_deg += 360
            angle_rad = math.radians(angle_deg)

            # major tick at 0/50/100, minor at 25/75
            tick_len = 4 if v in (0, 50, 100) else 2
            x1 = cx + (r - 1) * math.cos(angle_rad)
            y1 = cy - (r - 1) * math.sin(angle_rad)
            x2 = cx + (r - 1 - tick_len) * math.cos(angle_rad)
            y2 = cy - (r - 1 - tick_len) * math.sin(angle_rad)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

            if v in labels:
                lx = cx + (r - 6) * math.cos(angle_rad)
                ly = cy - (r - 6) * math.sin(angle_rad)
                painter.setPen(_MUTED)
                text = str(labels[v])
                text_w = painter.fontMetrics().horizontalAdvance(text)
                painter.drawText(
                    QRectF(lx - text_w / 2, ly - 3, text_w, 10),
                    Qt.AlignmentFlag.AlignCenter,
                    text,
                )

    def _draw_gradient_arc(self, painter, cx, cy, r):
        """Draw the filled arc as small segments using the momentum ramp."""
        value_sweep = (self._display_value / 100.0) * ARC_SWEEP
        segments = 48
        filled = value_sweep
        if filled <= 0:
            return

        for i in range(segments):
            t0 = i / segments
            t1 = (i + 1) / segments
            # Segment start/end in sweep degrees
            seg_start = t0 * filled
            seg_end = min(t1 * filled, filled)
            if seg_end - seg_start < 0.01:
                continue
            color = _ramp_color(t0)
            pen = QPen(color)
            pen.setWidthF(4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(
                QRectF(cx - r, cy - r, r * 2, r * 2),
                int((ARC_START - seg_start) * 16),
                int(-(seg_end - seg_start) * 16),
            )

    def _draw_needle(self, painter, cx, cy, r, normalized, color):
        angle_deg = ARC_START - normalized * ARC_SWEEP
        angle_rad = math.radians(angle_deg)
        needle_length = r - 9
        nx = cx + needle_length * math.cos(angle_rad)
        ny = cy - needle_length * math.sin(angle_rad)

        needle_pen = QPen(color)
        needle_pen.setWidthF(2)
        painter.setPen(needle_pen)
        painter.drawLine(int(cx), int(cy), int(nx), int(ny))

        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx - 3, cy - 3, 6, 6))

    def _draw_center_text(self, painter, cx, cy, color):
        """Show arrow + delta (preferred) or the raw dial value."""
        painter.setPen(color)
        painter.setFont(QFont(_FONT, 7, QFont.Weight.Bold))

        if self._raw_percent is not None:
            arrow = "▲" if (self._status and "ris" in str(self._status).lower()) else (
                "▼" if (self._status and ("declin" in str(self._status).lower() or "fall" in str(self._status).lower() or "drop" in str(self._status).lower())) else "•"
            )
            text = f"{arrow} {self._raw_percent:+.0f}%"
        else:
            text = str(int(round(self._display_value)))

        text_w = painter.fontMetrics().horizontalAdvance(text)
        painter.drawText(
            QRectF(cx - text_w / 2, cy + 5, text_w, 12),
            Qt.AlignmentFlag.AlignCenter,
            text,
        )