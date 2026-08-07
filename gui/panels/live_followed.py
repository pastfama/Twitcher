"""Live Followed channels list (port of mainmenu/livefollowed/panel.py).

Search bar + table headers (CHANNEL/VIEWERS/CATEGORY/GROWTH/SCORE) +
letter avatars + SullyGoose score column.
"""

import tkinter as tk
import customtkinter as ctk

from gui.theme import Theme, font


class LiveFollowedPanel(ctk.CTkFrame):
    def __init__(self, master=None, **kw):
        super().__init__(master, fg_color=Theme.DARK_PANEL, corner_radius=10, **kw)
        self._build()
        self._rows = []

    def _build(self):
        tk.Label(self, text="LIVE FOLLOWED CHANNELS",
                 bg=Theme.DARK_PANEL, fg=Theme.TEXT_SECONDARY,
                 font=(Theme.FAMILY, 10, "bold")).pack(anchor="w", padx=12, pady=(10, 4))

        # search bar
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *a: None)
        search = ctk.CTkEntry(self, textvariable=self._search_var,
                              placeholder_text="Search channels...")
        search.pack(fill="x", padx=12, pady=(0, 8))

        # table headers
        hdr = tk.Frame(self, bg=Theme.DARK_PANEL)
        hdr.pack(fill="x", padx=12, pady=(0, 4))
        for text, w in [("CHANNEL", 16), ("VIEWERS", 10), ("CATEGORY", 14), ("GROWTH", 10), ("SCORE", 8)]:
            tk.Label(hdr, text=text, fg=Theme.DIM, bg=Theme.DARK_PANEL,
                     font=(Theme.FAMILY, 9, "bold"), width=w, anchor="w").pack(side="left")

        # scrollable list
        self._list = tk.Frame(self, bg=Theme.DARK_PANEL)
        self._list.pack(fill="both", expand=True, padx=8, pady=(0, 10))

    def _avatar(self, parent, letter):
        c = tk.Canvas(parent, width=24, height=24,
                      highlightthickness=0, bg=Theme.AVATAR_BG)
        c.create_text(12, 12, text=letter, fill=Theme.TEXT_SECONDARY,
                      font=(Theme.FAMILY, 10, "bold"))
        return c

    def update(self, state) -> None:
        query = (self._search_var.get() or "").strip().lower()
        for row in self._rows:
            row.destroy()
        self._rows.clear()
        for item in state or []:
            ch = item.get("channel", "?")
            if query and query not in ch.lower():
                continue
            row = tk.Frame(self._list, bg=Theme.DARK_PANEL)
            row.pack(fill="x", pady=1)

            self._avatar(row, (ch[:1] or "?").upper()).pack(side="left", padx=4)

            tk.Label(row, text=f"#{ch}", fg=Theme.BRIGHT,
                     bg=Theme.DARK_PANEL, font=(Theme.FAMILY, 9, "bold"),
                     width=16, anchor="w").pack(side="left")
            tk.Label(row, text=f"{item.get('viewers',0):,}",
                     fg=Theme.TEXT_SECONDARY, bg=Theme.DARK_PANEL,
                     font=(Theme.FAMILY, 9), width=10, anchor="w").pack(side="left")
            tk.Label(row, text=item.get("category", "—"),
                     fg=Theme.TEXT_SECONDARY, bg=Theme.DARK_PANEL,
                     font=(Theme.FAMILY, 9), width=14, anchor="w").pack(side="left")
            tk.Label(row, text=item.get("growth", "—"),
                     fg=Theme.TEXT_SECONDARY, bg=Theme.DARK_PANEL,
                     font=(Theme.FAMILY, 9), width=10, anchor="w").pack(side="left")
            tk.Label(row, text=str(item.get("score", "—")),
                     fg=Theme.CYAN, bg=Theme.DARK_PANEL,
                     font=(Theme.FAMILY, 9, "bold"), width=8, anchor="w").pack(side="left")
            self._rows.append(row)

