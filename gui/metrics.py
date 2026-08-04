"""Current Watching metrics card (CustomTkinter port of
``mainmenu/currwatching`` CurrentWatchingPanel + UI builder).

Renders *all* the live Twitcher metrics produced by
``core/viewer_tracker.ViewerTracker.analyze``:

    {
      "channel",          # str  e.g. "xqc"
      "status",           # str  "🚀 Spike" | "🟢 Rising" | "📉 Drop" | "🔴 Falling" | "🟡 Stable" | "warming up" | "stable"
      "change",           # int  +/- delta vs first sample in window
      "percent",          # float percent delta
      "current",          # int  live viewer count
    }

plus the viewer-count history (deque) for the momentum sparkline.
"""

import tkinter as tk

import customtkinter as ctk

from gui.theme import Theme, STATUS_COLORS, STATUS_LABEL, font
from gui.widgets.sparkline import MomentumSparkline
from gui.widgets.neon import NeonIndicator
from gui.widgets.canvas_gauge import AnalogGauge


class CurrentWatchingMetricsPanel(ctk.CTkFrame):
    """The dark neon 'Current Watching' card, rebuilt without PySide6."""

    def __init__(self, master=None):
        super().__init__(master, fg_color=Theme.CARD, corner_radius=14)
        self._build()

    # ------------------------------------------------------------------ build
    def _build(self):
        pad = {"padx": 12, "pady": 10}

        # ---- header: avatar | channel | LIVE badge | status ----------
        header = tk.Frame(self, bg=Theme.CARD)
        header.pack(fill="x", **pad)

        self.avatar = tk.Canvas(header, width=Theme.AVATAR_SIZE,
                                height=Theme.AVATAR_SIZE,
                                highlightthickness=0, bg=Theme.AVATAR_BG)
        self.avatar.pack(side="left")
        self._avatar_letter = self.avatar.create_text(
            Theme.AVATAR_SIZE / 2, Theme.AVATAR_SIZE / 2,
            text="?", fill=Theme.TEXT_SECONDARY,
            font=(Theme.FAMILY, 16, "bold"))

        self.channel_var = tk.StringVar(value="—")
        self.channel = ctk.CTkLabel(header, textvariable=self.channel_var,
                                    text_color=Theme.BRIGHT,
                                    font=font(13, "bold"))
        self.channel.pack(side="left", padx=8)

        self.live_dot = NeonIndicator(header)
        self.live_dot.pack(side="left", padx=6)
        self.live_label = ctk.CTkLabel(header, text="LIVE",
                                       text_color=Theme.RED,
                                       font=font(11, "bold"))
        self.live_label.pack(side="left", padx=(4, 0))

        self.status_var = tk.StringVar(value="—")
        self.status = ctk.CTkLabel(header, textvariable=self.status_var,
                                   text_color=Theme.MUTED,
                                   font=font(12, "bold"))
        self.status.pack(side="right")

        # ---- viewer count (big) --------------------------------------
        self.viewers_var = tk.StringVar(value="—")
        self.viewers = ctk.CTkLabel(self, textvariable=self.viewers_var,
                                    text_color=Theme.BRIGHT,
                                    font=("Segoe UI", 32, "bold"))
        self.viewers.pack(**pad)

        # ---- stats row: delta, %, momentum ---------------------------
        stats = tk.Frame(self, bg=Theme.CARD)
        stats.pack(fill="x", **pad)

        self.delta_var = tk.StringVar(value="+0")
        self.percent_var = tk.StringVar(value="0%")

        ctk.CTkLabel(stats, text="Δ", text_color=Theme.DIM,
                     font=font(11)).pack(side="left", padx=4)
        self.delta = ctk.CTkLabel(stats, textvariable=self.delta_var,
                                  text_color=Theme.CYAN, font=font(13, "bold"))
        self.delta.pack(side="left", padx=4)

        ctk.CTkLabel(stats, text="·", text_color=Theme.DIM,
                     font=font(11)).pack(side="left", padx=4)
        self.percent = ctk.CTkLabel(stats, textvariable=self.percent_var,
                                    text_color=Theme.TEAL, font=font(13, "bold"))
        self.percent.pack(side="left", padx=4)

        self.meter = AnalogGauge(stats, width=120, height=70)
        self.meter.pack(side="right")

        # ---- momentum sparkline --------------------------------------
        self.spark = MomentumSparkline(self, width=220, height=55)
        self.spark.pack(**pad)

        # ---- SullyGoose analytics placeholder -------------------------
        self.sully = ctk.CTkFrame(self, fg_color=Theme.DARK_PANEL,
                                  corner_radius=10)
        self.sully.pack(fill="x", **pad)
        s_top = tk.Frame(self.sully, bg=Theme.DARK_PANEL)
        s_top.pack(anchor="w")
        ctk.CTkLabel(self.sully, text="SULLYGOOSE",
                     text_color=Theme.TEXT_SECONDARY,
                     font=font(10, "bold")).pack(anchor="w", **pad)
        self.sully_var = tk.StringVar(value="analytics warming up…")
        self.sully_label = ctk.CTkLabel(self.sully,
                                        textvariable=self.sully_var,
                                        text_color=Theme.MUTED)
        self.sully_label.pack(anchor="w", **pad)

    # ------------------------------------------------------------------ update
    def set_metrics(self, analysis: dict, history=None) -> None:
        """Push a fresh ``ViewerTracker.analyze()`` result + history list."""
        if not analysis:
            return

        channel = analysis.get("channel", "")
        self.channel_var.set(f"#{channel}")
        self.avatar.itemconfig(self._avatar_letter,
                               text=(channel[:1] or "?").upper())

        # Show the emoji sentiment (🟢 Rising / 🔴 Falling / 🟡 Stable …) as Twitcher does.
        status = analysis.get("status", "warming up")
        self.status_var.set(status)
        color = STATUS_COLORS.get(status, Theme.MUTED)
        self.status.configure(text_color=color)
        self.live_dot.set_status(status)

        current = analysis.get("current", 0)
        self.viewers_var.set(f"{current:,}")

        change = int(analysis.get("change", 0))
        sign = "+" if change >= 0 else ""
        self.delta_var.set(f"{sign}{change:,}")

        percent = float(analysis.get("percent", 0))
        self.percent_var.set(f"{percent:+.1f}%")
        self.meter.set_value(max(0.0, min(100.0, abs(percent) / 2.0)))

        # momentum sparkline (oldest -> newest)
        if history:
            self.spark.set_points(history)
        else:
            self.spark.set_points([current])
