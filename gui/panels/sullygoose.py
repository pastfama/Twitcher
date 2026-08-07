"""SullyGoose analytics panel — wired to the real ``core.analytics_engine.AnalyticsEngine``.

Shows Streamer/Me/Uptime/Peak/Avg and CONS/REL/DISC/QUAL segmented
progress meters, plus VIEWERS/LIVE/CHAT colored indicators.
"""

import tkinter as tk
import customtkinter as ctk

from gui.theme import Theme, font


class SullyGoosePanel(ctk.CTkFrame):
    def __init__(self, master=None, analytics_engine=None, **kw):
        super().__init__(master, fg_color=Theme.DARK_PANEL, corner_radius=10, **kw)
        self._ae = analytics_engine
        self._build()

    def _build(self):
        tk.Label(self, text="◆ SULLYGOOSE",
                 bg=Theme.DARK_PANEL, fg=Theme.TEXT_SECONDARY,
                 font=(Theme.FAMILY, 10, "bold")).pack(anchor="w", padx=12, pady=(10, 4))

        self._labels = {}
        for key in ("Streamer", "Me", "Uptime", "Peak", "Avg"):
            frm = tk.Frame(self, bg=Theme.DARK_PANEL)
            frm.pack(fill="x", padx=12, pady=2)
            tk.Label(frm, text=f"{key}:", fg=Theme.DIM,
                     bg=Theme.DARK_PANEL, font=(Theme.FAMILY, 9)).pack(side="left")
            lbl = tk.Label(frm, text="—", fg=Theme.BRIGHT,
                           bg=Theme.DARK_PANEL, font=(Theme.FAMILY, 9, "bold"))
            lbl.pack(side="left", padx=6)
            self._labels[key] = lbl

        # segmented bars
        self._bars = {}
        for key in ("CONS", "REL", "DISC", "QUAL"):
            frm = tk.Frame(self, bg=Theme.DARK_PANEL)
            frm.pack(fill="x", padx=12, pady=2)
            tk.Label(frm, text=f"{key}:", fg=Theme.DIM,
                     bg=Theme.DARK_PANEL, font=(Theme.FAMILY, 9)).pack(side="left")
            self._bars[key] = self._segmented(frm, segments=10)
            self._bars[key].pack(side="left", padx=6, fill="x", expand=True)


    def _segmented(self, parent, segments=10):
        frm = tk.Frame(parent, bg=Theme.DARK_PANEL)
        boxes = []
        filled = 0
        for i in range(segments):
            c = tk.Canvas(frm, width=10, height=10,
                          highlightthickness=0, bg=Theme.DARK_PANEL)
            c.grid(row=0, column=i, padx=1)
            box = c.create_rectangle(0, 0, 10, 10,
                                     fill=Theme.LIGHT_INACTIVE, outline="")
            boxes.append(box)
            c._box = box  # store id
        frm._boxes = boxes
        frm._segments = segments
        return frm

    def _set_bar(self, frm, value_0_1):
        boxes = getattr(frm, "_boxes", [])
        segs = getattr(frm, "_segments", 10)
        filled = int(max(0.0, min(1.0, value_0_1)) * segs)
        for i, box in enumerate(boxes):
            color = Theme.GREEN if i < filled else Theme.LIGHT_INACTIVE
            frm.winfo_children()[i].itemconfig(box, fill=color)

    def update(self, state: dict) -> None:
        if not state:
            return
        ae = state or {}
        for key in ("Streamer", "Me", "Uptime", "Peak", "Avg"):
            self._labels[key].config(text=str(ae.get(key.lower(), "—")))
        for key in ("CONS", "REL", "DISC", "QUAL"):
            raw = ae.get(key.lower(), 0)
            try:
                val = max(0.0, min(1.0, float(raw) / 100.0))
            except Exception:
                val = 0.0
            self._set_bar(self._bars[key], val)

