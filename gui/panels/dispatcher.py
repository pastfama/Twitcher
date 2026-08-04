"""Dispatcher / automation log panel — dim timestamp + colored message.

Port of mainmenu/dispatcher_panel.py with color-coded log levels.
"""

import tkinter as tk
import customtkinter as ctk

from gui.theme import Theme, font


class DispatcherPanel(ctk.CTkFrame):
    def __init__(self, master=None, **kw):
        super().__init__(master, fg_color=Theme.DARK_PANEL, corner_radius=10, **kw)
        self._build()
        self._log_lines = 0

    def _build(self):
        tk.Label(self, text="AUTOMATION / DISPATCHER",
                 bg=Theme.DARK_PANEL, fg=Theme.TEXT_SECONDARY,
                 font=(Theme.FAMILY, 10, "bold")).pack(anchor="w", padx=12, pady=(10, 4))

        self.status_var = tk.StringVar(value="Status: Starting…")
        ctk.CTkLabel(self, textvariable=self.status_var,
                     text_color=Theme.TEXT_PRIMARY,
                     font=font(12, "bold")).pack(anchor="w", padx=12, pady=2)

        self.next_var = tk.StringVar(value="Next: —")
        ctk.CTkLabel(self, textvariable=self.next_var,
                     text_color=Theme.TEAL).pack(anchor="w", padx=12, pady=2)

        self.log = ctk.CTkTextbox(self, fg_color=Theme.CARD,
                                  font=font(10), height=180)
        self.log.pack(fill="both", expand=True, padx=12, pady=8)
        self.log.configure(state="disabled")

        # configure color tags
        self.log._textbox.tag_configure("info", foreground=Theme.DIM)
        self.log._textbox.tag_configure("success", foreground=Theme.GREEN)
        self.log._textbox.tag_configure("warn", foreground=Theme.ORANGE)
        self.log._textbox.tag_configure("error", foreground=Theme.RED)

    def set_status(self, msg: str) -> None:
        self.status_var.set(f"Status: {msg}")

    def set_next(self, msg: str) -> None:
        self.next_var.set(f"Next: {msg}")

    def append_log(self, msg: str, level: str = "info") -> None:
        self._log_lines += 1
        ts = f"[{self._log_lines:03d}]"
        self.log._textbox.configure(state="normal")
        self.log._textbox.insert("end", ts + " ", "info")
        self.log._textbox.insert("end", msg + "\n", level)
        self.log._textbox.see("end")
        self.log._textbox.configure(state="disabled")

    def update(self, state: dict) -> None:
        if not state:
            return
        self.set_status(state.get("status", ""))
        self.set_next(state.get("next", "—"))
        for line in state.get("logs", []):
            if isinstance(line, dict):
                self.append_log(line.get("msg", ""), line.get("level", "info"))
            else:
                self.append_log(str(line), "info")

