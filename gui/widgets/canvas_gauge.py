"""Analog gauge — port of ``widgets/mom.AnalogGauge``.

A semicircular needle gauge showing viewer momentum percent, drawn on a
tkinter.Canvas (Qt's paintEngine equivalent).
"""

import math
import tkinter as tk

from gui.theme import Theme


class AnalogGauge(tk.Canvas):
    """Semicircle gauge. ``value`` is a percent 0..100 mapped to 0..180 deg."""

    def __init__(self, master=None, width=120, height=70, **kw):
        super().__init__(
            master, width=width, height=height,
            highlightthickness=0, bg=Theme.CARD, **kw,
        )
        self._value = 0.0
        self._draw_static()
        self._needle = None
        self._draw_needle()

    # ------------------------------------------------------------------ #
    def _draw_static(self) -> None:
        w, h = int(self.cget("width")), int(self.cget("height"))
        cx, r = w / 2, min(w, h) / 2 - 4
        # track arc (grey) spanning ~180deg
        self.create_arc(
            cx - r, h - r, cx + r, h + r,
            start=0, extent=180, style=tk.ARC,
            outline=Theme.LIGHT_INACTIVE, width=8,
        )

    def _draw_needle(self) -> None:
        w, h = int(self.cget("width")), int(self.cget("height"))
        cx, r = w / 2, min(w, h) / 2 - 4
        theta = math.radians(180 - self._value * 1.8)  # 0..100 -> 180..0
        nx = cx + (r - 6) * math.cos(theta)
        ny = h - (r - 6) * math.sin(theta)
        self._needle = self.create_line(cx, h, nx, ny, fill=Theme.CYAN, width=2)

    def set_value(self, value: float) -> None:
        """value in 0..100 (percent)."""
        v = max(0.0, min(100.0, float(value)))
        if v == self._value:
            return
        self._value = v
        # recompute needle endpoint
        w, h = int(self.cget("width")), int(self.cget("height"))
        cx, r = w / 2, min(w, h) / 2 - 4
        theta = math.radians(180 - v * 1.8)
        nx = cx + (r - 6) * math.cos(theta)
        ny = h - (r - 6) * math.sin(theta)
        if self._needle is not None:
            self.delete(self._needle)
        self._needle = self.create_line(cx, h, nx, ny, fill=Theme.CYAN, width=2)
