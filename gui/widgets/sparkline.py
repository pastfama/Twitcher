"""Momentum sparkline — port of ``widgets/viewer_graph.ViewerHistoryGraph``.

Draws the live viewer-count history as a smooth canvas polyline with an
area fill, like the Qt custom widget's paintEvent.
"""

import tkinter as tk

from gui.theme import Theme


class MomentumSparkline(tk.Canvas):
    """A tiny canvas that draws a moving viewer-count sparkline.

    Feed it with :meth:`set_points` using a list of integer viewer counts
    (oldest -> newest).
    """

    def __init__(self, master=None, width=160, height=50, **kw):
        super().__init__(
            master,
            width=width,
            height=height,
            highlightthickness=0,
            bg=Theme.DARK_PANEL,
            **kw,
        )
        self._points: list[float] = []
        self._pad = 4

    def set_points(self, viewers) -> None:
        self._points = [float(v) for v in (viewers or [])]
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")
        pts = self._points
        if len(pts) < 2:
            return
        w = int(self.cget("width"))
        h = int(self.cget("height"))
        pad = self._pad
        iw = max(w - 2 * pad, 2)
        ih = max(h - 2 * pad, 2)

        hi = max(pts)
        lo = min(pts)
        rng = (hi - lo) or 1.0
        n = len(pts)

        coords = []
        for i, v in enumerate(pts):
            x = pad + (i / (n - 1)) * iw
            y = pad + ih - ((v - lo) / rng) * ih
            coords.extend([x, y])

        # smooth polyline (the "graph")
        self.create_line(
            coords, fill=Theme.CYAN, width=2,
            smooth=True, capstyle=tk.ROUND, joinstyle=tk.ROUND,
        )

        # area fill: bottom edge -> points -> bottom-right
        poly = [pad, pad + ih] + coords + [pad + iw, pad + ih]
        self.create_polygon(
            poly, fill=Theme.SECTION_BORDER, outline="",
        )
