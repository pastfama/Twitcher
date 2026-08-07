"""Full DashboardApp — 3-column Control Center layout.

Mirrors screenshot 2 (PySide6 original):
  top bar  -> WATCHER CONTROL CENTER + CONNECTED + LOGS + RE-AUTH
  left col -> CurrentWatching + SullyGoose + LiveFollowed (30%)
  center   -> Chat (40%)
  right     -> NextStream + Dispatcher (30%)

Collapsible log panel (instead of separate window).
"""

import tkinter as tk
import customtkinter as ctk

from gui.theme import Theme, font
from gui.metrics import CurrentWatchingMetricsPanel
from gui.panels.sullygoose import SullyGoosePanel
from gui.panels.live_followed import LiveFollowedPanel
from gui.panels.chat import ChatPanel
from gui.panels.next_stream import NextStreamPanel
from gui.panels.dispatcher import DispatcherPanel


class DashboardApp(ctk.CTk):
    def __init__(self, provider=None, tick_ms=1000, **kw):
        super().__init__(**kw)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("Watcher — dashboard")
        self._provider = provider
        self._tick_ms = tick_ms
        self._running = True
        self._log_visible = False
        self._build()
        self.after(self._tick_ms, self._loop)

    # ------------------------------------------------------------------ layout
    def _build(self):
        self.configure(fg_color=Theme.CARD)
        self.geometry(f"{Theme.DEFAULT_WIDTH}x{Theme.DEFAULT_HEIGHT}")

        # top bar
        top = tk.Frame(self, bg=Theme.CARD)
        top.pack(fill="x", padx=20, pady=(12, 8))
        tk.Label(top, text="WATCHER",
                 bg=Theme.CARD, fg=Theme.BRIGHT,
                 font=(Theme.FAMILY, 22, "bold")).pack(side="left")
        tk.Label(top, text="AUTOMATED STREAM CONTROL CENTER",
                 bg=Theme.CARD, fg=Theme.DIM,
                 font=(Theme.FAMILY, 10, "bold")).pack(side="left", padx=(10, 0))

        self._conn_var = tk.StringVar(value="● OFFLINE")
        self._conn_lbl = tk.Label(top, textvariable=self._conn_var,
                                  bg=Theme.CARD, fg=Theme.RED_DARK,
                                  font=(Theme.FAMILY, 11, "bold"))
        self._conn_lbl.pack(side="right", padx=8)

        self._logs_btn = ctk.CTkButton(top, text="LOGS", width=80, height=28,
                                       fg_color=Theme.LIGHT_INACTIVE, text_color=Theme.BRIGHT,
                                       command=self._toggle_log)
        self._logs_btn.pack(side="right", padx=6)

        ctk.CTkButton(top, text="RE-AUTH", width=90, height=28,
                      fg_color=Theme.LIGHT_INACTIVE, text_color=Theme.BRIGHT).pack(side="right", padx=6)

        # body: 3 columns
        body = tk.Frame(self, bg=Theme.CARD)
        body.pack(fill="both", expand=True, padx=20, pady=12)

        self._left = tk.Frame(body, bg=Theme.CARD)
        self._center = tk.Frame(body, bg=Theme.CARD)
        self._right = tk.Frame(body, bg=Theme.CARD)
        self._left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._center.pack(side="left", fill="both", expand=True, padx=8)
        self._right.pack(side="left", fill="both", expand=True, padx=(8, 0))

        # left column
        self.metrics = CurrentWatchingMetricsPanel(self._left)
        self.metrics.pack(fill="x", pady=(0, 10))

        self.sully = SullyGoosePanel(self._left)
        self.sully.pack(fill="x", pady=(0, 10))

        self.live = LiveFollowedPanel(self._left)
        self.live.pack(fill="both", expand=True)

        # center column (chat)
        self.chat = ChatPanel(self._center)
        self.chat.pack(fill="both", expand=True)

        # right column
        self.next = NextStreamPanel(self._right, on_switch=self._on_next_switch)
        self.next.pack(fill="x", pady=(0, 10))

        self.dispatch = DispatcherPanel(self._right)
        self.dispatch.pack(fill="both", expand=True)

        # collapsible log (hidden by default)
        self._log_container = tk.Frame(self, bg=Theme.CARD)
        self._log_box = ctk.CTkTextbox(self._log_container, fg_color=Theme.CARD,
                                       font=font(10), height=160)
        self._log_box.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        self._log_box.configure(state="disabled")

    # ------------------------------------------------------------------ tick
    def _loop(self):
        if not self._running:
            return
        if self._provider:
            try:
                state = self._provider()
                cur = state.get("current")
                if cur:
                    self.metrics.set_metrics(*cur)
                self.sully.update(state.get("sullygoose") or {})
                self.live.update(state.get("live") or [])
                self.next.update(state.get("next") or {})
                self.dispatch.update(state.get("dispatch") or {})
                self.chat.update(state.get("chat") or {})
                if "connection" in state:
                    self._conn_var.set(state["connection"])
                    self._conn_lbl.configure(
                        fg=Theme.GREEN if "ONLINE" in state["connection"] else Theme.RED_DARK)
                for entry in state.get("logs", []):
                    self._append_log(entry)
            except Exception as e:
                print("[gui]", e)
        self.after(self._tick_ms, self._loop)

    # ------------------------------------------------------------------ actions
    def _toggle_log(self):
        self._log_visible = not self._log_visible
        if self._log_visible:
            self._log_container.pack(fill="x", padx=20, pady=(0, 12))
        else:
            self._log_container.pack_forget()

    def _on_next_switch(self, channel: str):
        # dispatch to backend: switch stream to channel
        print(f"[gui] switch to {channel}")
        # would call real backend here

    def _append_log(self, entry) -> None:
        if isinstance(entry, str):
            msg, level = entry, "info"
        else:
            msg = entry.get("msg", "")
            level = entry.get("level", "info")
        self._log_box._textbox.configure(state="normal")
        self._log_box._textbox.insert("end", msg + "\n", level)
        self._log_box._textbox.see("end")
        self._log_box._textbox.configure(state="disabled")

    def destroy(self):
        self._running = False
        super().destroy()


def run_dashboard(provider=None, tick_ms=1000):
    app = DashboardApp(provider=provider, tick_ms=tick_ms)
    app.mainloop()

