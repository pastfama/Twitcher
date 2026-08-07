"""Next-Stream card — port of mainmenu/nextstream/panel.py (expanded).

Thumbnail area, description text, SWITCH NOW button.
"""

import tkinter as tk
import customtkinter as ctk

from gui.theme import Theme, font


class NextStreamPanel(ctk.CTkFrame):
    def __init__(self, master=None, on_switch=None, **kw):
        super().__init__(master, fg_color=Theme.DARK_PANEL, corner_radius=10, **kw)
        self._on_switch = on_switch
        self._build()

    def _build(self):
        tk.Label(self, text="⏭  NEXT STREAM",
                 bg=Theme.DARK_PANEL, fg=Theme.TEAL,
                 font=(Theme.FAMILY, 11, "bold")).pack(anchor="w", padx=12, pady=(10, 6))

        # thumbnail placeholder
        self._thumb = tk.Canvas(self, width=120, height=68,
                                highlightthickness=0, bg=Theme.CARD)
        self._thumb.pack(anchor="w", padx=12, pady=2)
        self._thumb.create_text(60, 34, text="NO IMAGE", fill=Theme.DIM,
                                font=(Theme.FAMILY, 9))

        self.channel_var = tk.StringVar(value="No next stream selected")
        ctk.CTkLabel(self, textvariable=self.channel_var,
                     text_color=Theme.TEXT_PRIMARY,
                     font=font(13, "bold")).pack(anchor="w", padx=12, pady=2)

        self.viewers_var = tk.StringVar(value="👁 —")
        ctk.CTkLabel(self, textvariable=self.viewers_var,
                     text_color=Theme.TEXT_SECONDARY).pack(anchor="w", padx=12)

        self.category_var = tk.StringVar(value="🎮 —")
        ctk.CTkLabel(self, textvariable=self.category_var,
                     text_color=Theme.TEXT_SECONDARY).pack(anchor="w", padx=12)

        self.reason_var = tk.StringVar(
            value="When the current stream ends, Watcher will switch here.")
        ctk.CTkLabel(self, textvariable=self.reason_var,
                     text_color=Theme.MUTED, wraplength=240,
                     font=font(9)).pack(anchor="w", padx=12, pady=(6, 8))

        ctk.CTkButton(self, text="SWITCH NOW", width=140, height=32,
                      fg_color=Theme.CYAN, text_color=Theme.CARD,
                      font=font(11, "bold"), command=self._do_switch).pack(anchor="w", padx=12, pady=(0, 10))

    def _do_switch(self):
        ch = self.channel_var.get().replace("No next stream selected", "").strip()
        if ch and self._on_switch:
            self._on_switch(ch)

    def update(self, state: dict) -> None:
        if not state:
            return
        self.channel_var.set(state.get("channel", "No next stream selected"))
        v = state.get("viewers")
        self.viewers_var.set(f"👁 {v:,} viewers" if v is not None else "👁 —")
        c = state.get("category")
        self.category_var.set(f"🎮 {c}" if c else "🎮 —")
        self.reason_var.set(state.get("reason", self.reason_var.get()))

