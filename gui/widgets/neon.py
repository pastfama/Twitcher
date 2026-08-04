"""Neon indicator — port of ``widgets/indicators.NeonIndicator``.

A small coloured status badge whose "lit" colour reflects the current
stream-momentum sentiment (green / red / orange / muted).
"""

import tkinter as tk

from gui.theme import Theme, STATUS_COLORS


class NeonIndicator(tk.Canvas):
    """A 14px glowing dot whose fill tracks the sentiment of ``status``."""

    DIAMETER = 14

    def __init__(self, master=None, **kw):
        d = self.DIAMETER
        super().__init__(
            master, width=d, height=d,
            highlightthickness=0, bg=Theme.DARK_PANEL, **kw,
        )
        self._color = Theme.MUTED
        self._oid = self.create_oval(2, 2, d - 2, d - 2, fill=self._color, outline="")

    def set_status(self, status: str) -> None:
        self._color = STATUS_COLORS.get(status, Theme.MUTED)
        self.itemconfig(self._oid, fill=self._color)
