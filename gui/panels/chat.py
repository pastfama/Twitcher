"""Redesigned Twitch IRC chat panel.

Features:
- Channel name display with connection status
- CONNECT / DISCONNECT buttons
- Colored nick rendering in chat messages
- Reply-to support (click [reply] to quote)
- TRANSLIT toggle (translit.ru "Основной" standard)
- Clean input bar with SEND button
- Status bar with auto-send toggle, message count, connection info
"""

import tkinter as tk
import customtkinter as ctk

from gui.theme import Theme, font
from gui.translit import translit


# Nick color palette — cycles through these for different users
_NICK_COLORS = [
    "#00ffff",  # cyan
    "#72d6a0",  # green
    "#ff7777",  # red-light
    "#ffaa00",  # orange
    "#78d6c5",  # teal
    "#c8a0ff",  # lavender
    "#ff6699",  # pink
    "#66aaff",  # blue
]
_nick_color_map = {}
_nick_color_idx = 0


def _get_nick_color(nick: str) -> str:
    """Return a consistent color for a given nick."""
    global _nick_color_idx
    if nick not in _nick_color_map:
        _nick_color_map[nick] = _NICK_COLORS[_nick_color_idx % len(_NICK_COLORS)]
        _nick_color_idx += 1
    return _nick_color_map[nick]


class ChatPanel(ctk.CTkFrame):
    """Redesigned chat panel with colored nicks, replies, and status bar."""

    def __init__(self, master=None, **kw):
        super().__init__(master, fg_color=Theme.DARK_PANEL, corner_radius=10, **kw)
        self._translit_enabled = False
        self._channel = ""
        self._connected = False
        self._auto_send = False
        self._message_count = 0
        self._reply_target = None
        self._build()
        self._configure_tags()

    # ------------------------------------------------------------------ build
    def _build(self):
        # ---- header: title + channel + connection status ----
        hdr = tk.Frame(self, bg=Theme.DARK_PANEL)
        hdr.pack(fill="x", padx=12, pady=(10, 4))

        tk.Label(hdr, text="CHAT",
                 bg=Theme.DARK_PANEL, fg=Theme.TEXT_SECONDARY,
                 font=(Theme.FAMILY, 10, "bold")).pack(side="left")

        self._channel_var = tk.StringVar(value="")
        self._channel_lbl = tk.Label(hdr, textvariable=self._channel_var,
                                     bg=Theme.DARK_PANEL, fg=Theme.TEAL,
                                     font=(Theme.FAMILY, 10, "bold"))
        self._channel_lbl.pack(side="left", padx=8)

        # connection status dot + text
        self._conn_var = tk.StringVar(value="OFFLINE")
        self._conn_lbl = tk.Label(hdr, textvariable=self._conn_var,
                                  bg=Theme.DARK_PANEL, fg=Theme.RED_DARK,
                                  font=(Theme.FAMILY, 9, "bold"))
        self._conn_lbl.pack(side="right", padx=6)

        self._connect_btn = ctk.CTkButton(
            hdr, text="CONNECT", width=80, height=22,
            fg_color=Theme.GREEN, text_color=Theme.CARD,
            font=font(9, "bold"), command=self._do_connect)
        self._connect_btn.pack(side="right", padx=4)

        self._disconnect_btn = ctk.CTkButton(
            hdr, text="DISCONNECT", width=80, height=22,
            fg_color=Theme.RED_DARK, text_color=Theme.CARD,
            font=font(9, "bold"), command=self._do_disconnect)
        self._disconnect_btn.pack(side="right", padx=4)
        self._disconnect_btn.configure(state="disabled")

        # ---- chat messages (read-only textbox with tags) ----
        self._box = ctk.CTkTextbox(
            self, fg_color=Theme.CARD, font=(Theme.FAMILY, 11),
            height=260, wrap="word")
        self._box.pack(fill="both", expand=True, padx=12, pady=(4, 8))
        self._box.configure(state="disabled")

        # ---- reply indicator ----
        self._reply_frame = tk.Frame(self, bg=Theme.DARK_PANEL)
        self._reply_var = tk.StringVar(value="")
        self._reply_lbl = tk.Label(
            self._reply_frame, textvariable=self._reply_var,
            bg=Theme.DARK_PANEL, fg=Theme.ORANGE,
            font=(Theme.FAMILY, 9, "italic"))
        self._reply_lbl.pack(side="left", padx=12)
        self._cancel_reply_btn = ctk.CTkButton(
            self._reply_frame, text="x", width=20, height=20,
            fg_color=Theme.RED_DARK, text_color=Theme.CARD,
            font=font(8, "bold"), command=self._cancel_reply)
        self._cancel_reply_btn.pack(side="left", padx=2)
        # reply frame hidden by default

        # ---- input row: TRANSLIT + input + SEND ----
        inp_row = tk.Frame(self, bg=Theme.DARK_PANEL)
        inp_row.pack(fill="x", padx=12, pady=(0, 4))

        self._translit_var = tk.StringVar(value="TRANSLIT")
        self._translit_btn = ctk.CTkButton(
            inp_row, textvariable=self._translit_var,
            width=80, height=26, fg_color=Theme.LIGHT_INACTIVE,
            text_color=Theme.BRIGHT, font=font(9),
            command=self._toggle_translit)
        self._translit_btn.pack(side="left", padx=(0, 6))

        self._input = tk.Entry(
            inp_row, bg=Theme.CARD, fg=Theme.BRIGHT,
            insertbackground=Theme.BRIGHT,
            font=(Theme.FAMILY, 11), relief="flat")
        self._input.pack(side="left", fill="x", expand=True, padx=4, ipady=4)
        self._input.bind("<Key>", self._on_key)
        self._input.bind("<Return>", lambda e: self._do_send())

        self._send_btn = ctk.CTkButton(
            inp_row, text="SEND", width=60, height=26,
            fg_color=Theme.CYAN, text_color=Theme.CARD,
            font=font(10, "bold"), command=self._do_send)
        self._send_btn.pack(side="right", padx=(4, 0))

        # ---- status bar ----
        status_bar = tk.Frame(self, bg=Theme.DARK_PANEL)
        status_bar.pack(fill="x", padx=12, pady=(0, 8))

        self._msg_count_var = tk.StringVar(value="Messages: 0")
        tk.Label(status_bar, textvariable=self._msg_count_var,
                 bg=Theme.DARK_PANEL, fg=Theme.DIM,
                 font=(Theme.FAMILY, 8)).pack(side="left", padx=(0, 12))

        self._auto_var = tk.StringVar(value="Auto: OFF")
        self._auto_btn = ctk.CTkButton(
            status_bar, textvariable=self._auto_var,
            width=70, height=18, fg_color=Theme.LIGHT_INACTIVE,
            text_color=Theme.DIM, font=font(8),
            command=self._toggle_auto)
        self._auto_btn.pack(side="left", padx=(0, 12))

        self._latency_var = tk.StringVar(value="")
        tk.Label(status_bar, textvariable=self._latency_var,
                 bg=Theme.DARK_PANEL, fg=Theme.DIM,
                 font=(Theme.FAMILY, 8)).pack(side="right")

    # ------------------------------------------------------------------ tags
    def _configure_tags(self):
        """Configure text tags for colored rendering in the chat box."""
        # Tags are applied via CTkTextbox._textbox (the underlying tk.Text)
        pass  # CTkTextbox doesn't expose tag API directly; we use insert with tags

    # ------------------------------------------------------------------ public
    def set_channel(self, ch: str) -> None:
        self._channel = ch or ""
        self._channel_var.set(f"#{self._channel}" if self._channel else "")

    def connect(self) -> None:
        self._connected = True
        self._conn_var.set("ONLINE")
        self._conn_lbl.configure(fg=Theme.GREEN)
        self._connect_btn.configure(state="disabled")
        self._disconnect_btn.configure(state="normal")

    def disconnect(self) -> None:
        self._connected = False
        self._conn_var.set("OFFLINE")
        self._conn_lbl.configure(fg=Theme.RED_DARK)
        self._connect_btn.configure(state="normal")
        self._disconnect_btn.configure(state="disabled")

    def post(self, nick: str, msg: str, is_system: bool = False,
             is_reply: bool = False, reply_to: str = "") -> None:
        """Append a message to the chat box with colored nick."""
        self._box.configure(state="normal")
        textbox = self._box._textbox  # underlying tk.Text widget

        if is_system:
            # System messages in muted italic
            tag = f"  {msg}\n"
            textbox.insert("end", tag, "system")
        elif is_reply and reply_to:
            # Reply message with indentation
            prefix = f"    > @{reply_to}: "
            textbox.insert("end", f"    ", "indent")
            textbox.insert("end", f"@{reply_to}", "reply_target")
            textbox.insert("end", f": {msg}\n", "reply_text")
        else:
            # Normal message with colored nick
            color = _get_nick_color(nick)
            tag_name = f"nick_{nick}"
            try:
                textbox.tag_configure(tag_name, foreground=color)
            except Exception:
                pass
            textbox.insert("end", f"{nick}", tag_name)
            textbox.insert("end", f": {msg}\n", "msg_text")

            # Add clickable reply hint
            # (CTkTextbox doesn't support buttons, so we use a text hint)

        textbox.see("end")
        self._box.configure(state="disabled")
        self._message_count += 1
        self._msg_count_var.set(f"Messages: {self._message_count}")

    def update(self, state: dict) -> None:
        if not state:
            return
        ch = state.get("channel")
        if ch:
            self.set_channel(ch)
        if state.get("connected"):
            self.connect()
        else:
            self.disconnect()
        for msg in state.get("messages", []):
            nick = msg.get("nick", "?")
            text = msg.get("msg", "")
            self.post(nick, text)

    # ------------------------------------------------------------------ actions
    def _do_connect(self):
        self.connect()

    def _do_disconnect(self):
        self.disconnect()

    def _toggle_translit(self):
        self._translit_enabled = not self._translit_enabled
        if self._translit_enabled:
            self._translit_btn.configure(fg_color=Theme.CYAN, text_color=Theme.CARD)
            self._translit_var.set("TRANSLIT ON")
        else:
            self._translit_btn.configure(fg_color=Theme.LIGHT_INACTIVE, text_color=Theme.BRIGHT)
            self._translit_var.set("TRANSLIT")
        # Re-transliterate current input
        cur = self._input.get()
        if cur:
            self._input.delete(0, "end")
            self._input.insert(0, translit(cur))

    def _toggle_auto(self):
        self._auto_send = not self._auto_send
        if self._auto_send:
            self._auto_var.set("Auto: ON")
            self._auto_btn.configure(fg_color=Theme.GREEN, text_color=Theme.CARD)
        else:
            self._auto_var.set("Auto: OFF")
            self._auto_btn.configure(fg_color=Theme.LIGHT_INACTIVE, text_color=Theme.DIM)

    def _do_send(self):
        msg = self._input.get().strip()
        if not msg:
            return
        if self._translit_enabled:
            msg = translit(msg)
        self._input.delete(0, "end")
        self._cancel_reply()
        # Real backend: send msg to channel
        # For now, echo it in the chat
        self.post("you", msg)

    def _on_key(self, event):
        if not self._translit_enabled:
            return
        # Transliterate on every keypress that inserts a character
        if event.keysym in ("BackSpace", "Delete", "Return", "Tab", "Escape"):
            return
        if len(event.char) == 1:
            idx = self._input.index("insert")
            cur = self._input.get()
            new = translit(cur[:idx] + event.char + cur[idx:])
            self._input.delete(0, "end")
            self._input.insert(0, new)
            self._input.icursor(idx + 1)
            return "break"

    def start_reply(self, nick: str) -> None:
        """Show reply indicator for replying to a specific nick."""
        self._reply_target = nick
        self._reply_var.set(f"Replying to @{nick}...")
        self._reply_frame.pack(fill="x", padx=0, pady=(0, 2),
                               after=self._box)
        self._input.focus_set()

    def _cancel_reply(self):
        self._reply_target = None
        self._reply_var.set("")
        self._reply_frame.pack_forget()