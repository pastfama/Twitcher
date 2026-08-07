"""Root app window + TimeBoss-style tick loop (tkinter .after()).

This is the PySide6-free replacement for ``mainmenu/main.py``'s
QMainWindow host. Once the real ``core/*`` is on disk, pass a
*metrics_provider* that returns ``(analysis, history)`` and the card
updates on every tick — mirroring how TimeBoss drove ViewerMonitor.
"""

import customtkinter as ctk

from gui.theme import Theme, font
from gui.metrics import CurrentWatchingMetricsPanel


class WatcherApp(ctk.CTk):
    """Root CTk window hosting the Current-Watching metrics card."""

    def __init__(self, metrics_provider=None, tick_ms=1000, **kw):
        super().__init__(**kw)
        ctk.set_appearance_mode("dark")
        self.title("Watcher — metrics demo")
        self._set_window_size(720, 560)

        # dark neon background (port of mainmenu/style.py QMainWindow bg)
        self.configure(fg_color=Theme.CARD)

        header = ctk.CTkLabel(self, text="WATCHER",
                              text_color=Theme.BRIGHT,
                              font=font(16, "bold"))
        header.pack(anchor="w", padx=24, pady=(18, 6))

        self.metrics = CurrentWatchingMetricsPanel(self)
        self.metrics.pack(padx=24, pady=12, fill="both")

        self._provider = metrics_provider
        self._tick_ms = tick_ms
        self._running = True
        self.after(self._tick_ms, self._loop)

    # ------------------------------------------------------------------ helpers
    def _set_window_size(self, w, h):
        try:
            from gui._platform import center_geometry
            center_geometry(self, w, h)
        except Exception:
            self.geometry(f"{w}x{h}")

    def _loop(self):
        if not self._running:
            return
        if self._provider:
            try:
                analysis, history = self._provider()
                if analysis:
                    self.metrics.set_metrics(analysis, history)
            except Exception as e:
                # never let a bad tick kill the UI thread
                print("[gui]", e)
        self.after(self._tick_ms, self._loop)

    def destroy(self):
        self._running = False
        super().destroy()


def run(metrics_provider=None, tick_ms=1000):
    """Entrypoint used by the demo and, later, the real app."""
    app = WatcherApp(metrics_provider=metrics_provider, tick_ms=tick_ms)
    app.mainloop()
