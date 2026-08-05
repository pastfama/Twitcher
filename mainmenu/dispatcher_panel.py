"""Dispatcher Panel — central status display and event log.

Aligned with v0.8.1 data signaling:
- Status bar: shows current system state (color-coded)
- Next stream: shows upcoming channel
- Event log: scrollable, color-coded (errors=red, warnings=orange, info=default)
- All init messages from widgets appear here
- Auto-scrolls to latest message
"""

from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit
from .theme import Theme


# --- Error/warning detection patterns ---
_ERROR_KEYWORDS = ("error", "failed", "exception", "ERROR", "FAILED")
_WARNING_KEYWORDS = ("warning", "warn", "timeout")


def _classify_message(text):
    """Return ('error', color) or ('warning', color) or ('info', color)."""
    lower = text.lower()
    for kw in _ERROR_KEYWORDS:
        if kw.lower() in lower:
            return "error", Theme.RED_DARK
    for kw in _WARNING_KEYWORDS:
        if kw.lower() in lower:
            return "warning", Theme.ORANGE
    return "info", Theme.TEXT_SECONDARY


class DispatcherPanel(QGroupBox):
    """Central status display and event log for the Watcher application.

    Layout:
        ┌─ AUTOMATION / DISPATCHER ─────────────┐
        │ Status: ▶ Watching xqc                 │
        │ Next: #channel (12,345 viewers)        │
        │ ┌─────────────────────────────────────┐│
        │ │ [12:30:01] System started.           ││
        │ │ [12:30:02] Logged in as user        ││
        │ │ [12:30:03] Found 5 live channels    ││
        │ │ [12:30:05] ▶ Watching xqc          ││
        │ │ [12:30:10] VIDEO ERROR: ...   (red) ││
        │ └─────────────────────────────────────┘│
        └────────────────────────────────────────┘
    """

    def __init__(self):
        super().__init__("AUTOMATION / DISPATCHER")
        self.setStyleSheet(Theme.group_box_style(Theme.TEAL))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # --- Status bar ---
        status_row = QHBoxLayout()
        status_row.setSpacing(6)

        self.status_icon = QLabel("●")
        self.status_icon.setStyleSheet(f"color: {Theme.DIM}; font-size: 10px;")
        self.status_icon.setFixedWidth(12)
        status_row.addWidget(self.status_icon)

        self.dispatcher_status = QLabel("Starting...")
        self.dispatcher_status.setWordWrap(True)
        self.dispatcher_status.setFont(QFont(Theme.FAMILY, 11, QFont.Weight.Bold))
        self.dispatcher_status.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        status_row.addWidget(self.dispatcher_status, 1)

        layout.addLayout(status_row)

        # --- Next stream ---
        next_row = QHBoxLayout()
        next_row.setSpacing(6)

        self.next_icon = QLabel("▶")
        self.next_icon.setStyleSheet(f"color: {Theme.TEAL}; font-size: 10px;")
        self.next_icon.setFixedWidth(12)
        next_row.addWidget(self.next_icon)

        self.next_status = QLabel("—")
        self.next_status.setWordWrap(True)
        self.next_status.setStyleSheet(f"color: {Theme.TEAL}; font-size: 10px;")
        next_row.addWidget(self.next_status, 1)

        layout.addLayout(next_row)

        # --- Event log (color-coded, auto-scroll, collapsible) ---
        self._log_collapsed = True
        self.event_log = QTextEdit()
        self.event_log.setReadOnly(True)
        self.event_log.setStyleSheet(
            f"QTextEdit {{ "
            f"background-color: {Theme.DARK_PANEL}; "
            f"color: {Theme.TEXT_SECONDARY}; "
            f"border: 1px solid {Theme.SECTION_BORDER}; "
            f"border-radius: 4px; "
            f"font-size: 10px; "
            f"font-family: 'Consolas', 'Segoe UI', monospace; "
            f"}}"
        )
        self.event_log.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.event_log.setVisible(False)  # collapsed by default
        layout.addWidget(self.event_log)

        # Collapse/expand toggle
        self._toggle_btn = QLabel("▶ Show Log")
        self._toggle_btn.setStyleSheet(
            f"color: {Theme.DIM}; font-size: 9px; padding: 2px 4px;"
        )
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.mousePressEvent = lambda e: self._toggle_log()
        layout.addWidget(self._toggle_btn)

    def set_status(self, message):
        """Update the status bar. Errors get red styling."""
        self.dispatcher_status.setText(message)

        # Color-code based on content
        _, color = _classify_message(message)
        if "error" in message.lower() or "failed" in message.lower():
            self.dispatcher_status.setStyleSheet(f"color: {Theme.RED_DARK};")
            self.status_icon.setStyleSheet(f"color: {Theme.RED_DARK}; font-size: 10px;")
        elif "watching" in message.lower() or "▶" in message:
            self.dispatcher_status.setStyleSheet(f"color: {Theme.GREEN};")
            self.status_icon.setStyleSheet(f"color: {Theme.GREEN}; font-size: 10px;")
        elif "connecting" in message.lower() or "resolving" in message.lower():
            self.dispatcher_status.setStyleSheet(f"color: {Theme.ORANGE};")
            self.status_icon.setStyleSheet(f"color: {Theme.ORANGE}; font-size: 10px;")
        else:
            self.dispatcher_status.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
            self.status_icon.setStyleSheet(f"color: {Theme.DIM}; font-size: 10px;")

    def set_next_status(self, message):
        """Update the next stream display."""
        self.next_status.setText(message)
        if "No available" in message or "—" in message:
            self.next_status.setStyleSheet(f"color: {Theme.DIM}; font-size: 10px;")
        else:
            self.next_status.setStyleSheet(f"color: {Theme.TEAL}; font-size: 10px;")

    def _toggle_log(self):
        """Toggle log area visibility."""
        self._log_collapsed = not self._log_collapsed
        self.event_log.setVisible(not self._log_collapsed)
        self._toggle_btn.setText("▼ Hide Log" if not self._log_collapsed else "▶ Show Log")

    def append_log(self, message):
        """Append a timestamped message to the event log with color coding."""
        # Auto-expand on first log message
        if self._log_collapsed:
            self._toggle_log()
        category, color = _classify_message(message)

        # Build colored HTML
        color_hex = color
        html_msg = (
            f'<span style="color: {Theme.DIM};">●</span> '
            f'<span style="color: {color_hex};">{_escape_html(message)}</span>'
        )

        self.event_log.append(html_msg)

        # Auto-scroll to bottom
        cursor = self.event_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.event_log.setTextCursor(cursor)
        self.event_log.ensureCursorVisible()


def _escape_html(text):
    """Escape HTML special characters for safe display in QTextEdit."""
    text = text.replace("&", chr(38) + "amp;")
    text = text.replace("<", chr(38) + "lt;")
    text = text.replace(">", chr(38) + "gt;")
    return text
