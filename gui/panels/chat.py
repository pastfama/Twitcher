"""Twitch IRC chat panel — port of mainmenu/chatpanel/panel.py + TRANSLIT.

Features: channel name, CONNECT/DISCONNECT, reply buttons, message input,
SEND/TRANSLIT/AUTO buttons, keystroke-by-keystroke Latin→Cyrillic when
TRANSLIT is active, connected-to display.
"""

import tkinter as tk
import customtkinter as ctk

from gui.theme import Theme, font
from gui.translit import translit


class ChatPanel(ctk.CTkFrame):
    def __init__(self, master=None, **kw):
        super().__init__(master, fg_color=Theme.DARK_PANEL, corner_radius=10, **kw)
        self._build()
        self._translit_enabled = False
        self._channel = ""
        self._connected = False

    def _build(self):
        # header row: TWITCH CHAT + CONNECT/DISCONNECT
        hdr = tk.Frame(self, bg=Theme.DARK_PANEL)
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(hdr, text="TWITCH CHAT",
                 bg=Theme.DARK_PANEL, fg=Theme.TEXT_SECONDARY,
                 font=(Theme.FAMILY, 10, "bold")).pack(side="left")

        self._conn_var = tk.StringVar(value="● DISCONNECTED")
        self._conn_lbl = tk.Label(hdr, textvariable=self._conn_var,
                                  bg=Theme.DARK_PANEL, fg=Theme.RED_DARK,
                                  font=(Theme.FAMILY, 9, "bold"))
        self._conn_lbl.pack(side="right", padx=6)

        self._connect_btn = ctk.CTkButton(hdr, text="CONNECT", width=90, height=24,
                                          fg_color=Theme.GREEN, text_color=Theme.CARD,
                                          command=self._do_connect)
        self._connect_btn.pack(side="right", padx=6)
        self._disconnect_btn = ctk.CTkButton(hdr, text="DISCONNECT", width=90, height=24,
                                             fg_color=Theme.RED_DARK, text_color=Theme.CARD,
                                             command=self._do_disconnect)
        self._disconnect_btn.pack(side="right", padx=6)

        # channel display
        self._channel_var = tk.StringVar(value="—")
        ctk.CTkLabel(self, textvariable=self._channel_var,
                     text_color=Theme.TEAL, font=font(10)).pack(anchor="w", padx=12, pady=2)

        # chat messages (read-only)
        self._box = ctk.CTkTextbox(self, fg_color=Theme.CARD, font=font(11), height=220)
        self._box.pack(fill="both", expand=True, padx=12, pady=8)
        self._box.configure(state="disabled")

        # bottom row: TRANSLIT toggle + message input + SEND/AUTO
        bottom = tk.Frame(self, bg=Theme.DARK_PANEL)
        bottom.pack(fill="x", padx=12, pady=(0, 10))

        self._translit_var = tk.StringVar(value="TRANSLIT")
        self._translit_btn = ctk.CTkButton(bottom, textvariable=self._translit_var,
                                            width=90, height=28, fg_color=Theme.LIGHT_INACTIVE,
                                            text_color=Theme.BRIGHT, command=self._toggle_translit)
        self._translit_btn.pack(side="left", padx=(0, 6))

        self._input = tk.Entry(bottom, bg=Theme.CARD, fg=Theme.BRIGHT,
                               insertbackground=Theme.BRIGHT, font=(Theme.FAMILY, 11))
        self._input.pack(side="left", fill="x", expand=True, padx=6)
        self._input.bind("<Key>", self._on_key)

        self._auto_var = tk.StringVar(value="AUTO")
        self._auto_btn = ctk.CTkButton(bottom, textvariable=self._auto_var,
                                        width=60, height=28, fg_color=Theme.LIGHT_INACTIVE,
                                        text_color=Theme.BRIGHT, command=self._toggle_auto)
        self._auto_btn.pack(side="right", padx=4)

        ctk.CTkButton(bottom, text="SEND", width=70, height=28, fg_color=Theme.CYAN,
                      text_color=Theme.CARD, font=font(10, "bold"), command=self._do_send).pack(side="right", padx=4)

    # ------------------------------------------------------------------ public
    def set_channel(self, ch: str) -> None:
        self._channel = ch or ""
        self._channel_var.set(f"#{self._channel}" if self._channel else "—")

    def connect(self) -> None:
        self._connected = True
        self._conn_var.set("● CONNECTED")
        self._conn_lbl.configure(fg=Theme.GREEN)
        self._connect_btn.configure(state="disabled")
        self._disconnect_btn.configure(state="normal")

    def disconnect(self) -> None:
        self._connected = False
        self._conn_var.set("● DISCONNECTED")
        self._conn_lbl.configure(fg=Theme.RED_DARK)
        self._connect_btn.configure(state="normal")
        self._disconnect_btn.configure(state="disabled")

    def post(self, nick: str, msg: str, show_reply: bool = True) -> None:
        self._box.configure(state="normal")
        tag = f"{nick}: {msg}"
        self._box.insert("end", tag + "\n")
        if show_reply:
            self._box.insert("end", "    [reply]\n", "reply")
        self._box.see("end")
        self._box.configure(state="disabled")

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
            self.post(nick, text, show_reply=False)

    # ------------------------------------------------------------------ actions
    def _do_connect(self):
        self.connect()
        # real backend call goes here

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
        # re-transliterate current input
        cur = self._input.get()
        if cur:
            self._input.delete(0, "end")
            self._input.insert(0, translit(cur))

    def _toggle_auto(self):
        # placeholder: AUTO mode would send messages automatically on conditions
        current = self._auto_var.get()
        self._auto_var.set("AUTO ON" if current == "AUTO" else "AUTO")
        self._auto_btn.configure(fg_color=Theme.GREEN if self._auto_var.get() == "AUTO ON" else Theme.LIGHT_INACTIVE)

    def _do_send(self):
        msg = self._input.get().strip()
        if not msg:
            return
        if self._translit_enabled:
            msg = translit(msg)
        self._input.delete(0, "end")
        # real backend: send msg to channel

    def _on_key(self, event):
        if not self._translit_enabled:
            return
        # transliterate on every keypress that inserts a character
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

