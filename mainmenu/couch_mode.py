"""Couch Mode — toggle between normal and large-font distance-viewing layouts.

When activated:
- All fonts roughly double in size
- Layout rearranges to 2 columns (video + big metrics)
- Chat, Live Followed, Dispatcher panels are hidden
- Dashboard shows top 3 metrics as huge widgets
- Window auto-maximizes
- Mood colors get brighter/more saturated
"""

from PySide6.QtCore import (
    QObject, Signal, QPropertyAnimation, QEasingCurve, QTimer, Qt, Property
)
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGridLayout, QGraphicsDropShadowEffect,
)
from PySide6.QtGui import QColor
from logger import debug


# ── Stylesheets ─────────────────────────────────────────────────────────

_NORMAL_FONT_BASE = 10
_COUCH_FONT_BASE = 20

_COUCH_GLOBAL_STYLE = """
QGroupBox {{
    font-size: {base}px;
}}
QGroupBox::title {{
    font-size: {base}px;
}}
QLabel {{
    font-size: {base}px;
}}
QPushButton {{
    font-size: {base}px;
    padding: {pad}px {pad2}px;
}}
QLineEdit {{
    font-size: {base}px;
    padding: {pad}px;
}}
QTextEdit, QListWidget, QPlainTextEdit {{
    font-size: {base}px;
}}
QProgressBar {{
    font-size: {base}px;
    min-height: {bar_h}px;
}}
QLCDNumber {{
    min-height: {lcd_h}px;
}}
""".format


def _couch_style():
    return _COUCH_GLOBAL_STYLE(
        base=_COUCH_FONT_BASE,
        pad=8,
        pad2=16,
        bar_h=28,
        lcd_h=48,
    )


def _normal_style():
    """Returns empty string — panels revert to their own styles."""
    return ""


# ── Couch Mode Button ───────────────────────────────────────────────────

class CouchButton(QPushButton):
    """A floating toggle button that activates couch mode."""

    def __init__(self, parent=None):
        super().__init__("🛋", parent)
        self.setFixedSize(36, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Couch Mode (Ctrl+L)\nDoubles fonts & simplifies layout for distance viewing")
        self._active = False
        self._update_style()

    def set_active(self, active: bool):
        self._active = active
        self._update_style()

    def _update_style(self):
        if self._active:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #00ffff;
                    color: #000000;
                    border: 2px solid #00cccc;
                    border-radius: 18px;
                    font-size: 18px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #33ffff;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #141827;
                    color: #8b93ad;
                    border: 1px solid #2a3a5a;
                    border-radius: 18px;
                    font-size: 18px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1a2a4a;
                    color: #00ffff;
                    border: 1px solid #00ffff;
                }
            """)


# ── Couch Mode Manager ──────────────────────────────────────────────────

class CouchModeManager(QObject):
    """Manages the couch mode toggle for the main window.

    Usage::

        couch = CouchModeManager(main_window)
        couch.toggle()  # or press Ctrl+L
    """

    mode_changed = Signal(bool)  # True = couch mode active

    def __init__(self, main_window):
        super().__init__(main_window)
        self._win = main_window
        self._active = False
        self._original_geometry = None
        self._original_min_size = None

        # Create the toggle button
        self.button = CouchButton(main_window)
        self.button.clicked.connect(self.toggle)

        # Keyboard shortcut: Ctrl+L
        self._shortcut = QShortcut(QKeySequence("Ctrl+L"), main_window)
        self._shortcut.activated.connect(self.toggle)

    @property
    def is_active(self) -> bool:
        return self._active

    def toggle(self):
        """Toggle between normal and couch mode."""
        if self._active:
            self._deactivate()
        else:
            self._activate()

    def _activate(self):
        """Switch to couch mode."""
        debug("[COUCH MODE] Activating")
        self._active = True
        self.button.set_active(True)

        # Save current geometry
        self._original_geometry = self._win.saveGeometry()
        self._original_min_size = self._win.minimumSize()

        # Apply large-font stylesheet
        self._win.setStyleSheet(
            self._win.styleSheet() + "\n" + _couch_style()
        )

        # Re-arrange layout: hide non-essential panels
        self._set_panels_visible(False)

        # Maximize window
        self._win.showMaximized()

        # Notify
        self.mode_changed.emit(True)
        debug("[COUCH MODE] Active — fonts doubled, layout simplified")

    def _deactivate(self):
        """Switch back to normal mode."""
        debug("[COUCH MODE] Deactivating")
        self._active = False
        self.button.set_active(False)

        # Remove couch stylesheet (re-apply base)
        from mainmenu.style import MAIN_WINDOW_STYLESHEET
        self._win.setStyleSheet(MAIN_WINDOW_STYLESHEET)

        # Re-show all panels
        self._set_panels_visible(True)

        # Restore geometry
        if self._original_geometry:
            self._win.restoreGeometry(self._original_geometry)
        if self._original_min_size:
            self._win.setMinimumSize(self._original_min_size)

        # Notify
        self.mode_changed.emit(False)
        debug("[COUCH MODE] Deactive — normal layout restored")

    def _set_panels_visible(self, visible: bool):
        """Show or hide panels that are not needed in couch mode."""
        panels_to_hide = [
            'chat_panel',          # Chat text — too small to read from distance
            'live_followed_panel', # Channel list — not critical from couch
            'dispatcher_panel',    # Log/dispatch — not needed from couch
        ]
        panels_to_show_always = [
            'current_panel',       # Currently watching — essential
            'next_panel',          # Next stream — essential
        ]

        for name in panels_to_hide:
            panel = getattr(self._win, name, None)
            if panel:
                panel.setVisible(visible)

        # In couch mode, expand the dashboard to fill the extra space
        if hasattr(self._win, 'chat_panel') and self._win.chat_panel:
            dashboard = getattr(self._win.chat_panel, 'dashboard', None)
            if dashboard:
                dashboard.setFixedHeight(300 if not visible else 140)

        # Make current and next panels bigger in couch mode
        if not visible:
            # Re-do grid layout for couch mode
            self._apply_couch_layout()
        else:
            self._apply_normal_layout()

    def _apply_couch_layout(self):
        """Apply 2-column couch layout."""
        central = self._win.centralWidget()
        if not central:
            return

        # Find the grid layout
        main_layout = central.layout()
        if not main_layout:
            return

        # Remove existing grid
        grid = None
        for i in range(main_layout.count()):
            item = main_layout.itemAt(i)
            if item and isinstance(item, QGridLayout):
                grid = item
                break

        if grid is None:
            return

        # Remove all widgets from grid
        while grid.count():
            item = grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        # Re-add in couch layout: 2 columns
        current_panel = getattr(self._win, 'current_panel', None)
        next_panel = getattr(self._win, 'next_panel', None)
        dashboard = None
        if hasattr(self._win, 'chat_panel') and self._win.chat_panel:
            dashboard = getattr(self._win.chat_panel, 'dashboard', None)

        if current_panel:
            grid.addWidget(current_panel, 0, 0, 2, 1)  # spans 2 rows
        if dashboard:
            grid.addWidget(dashboard, 0, 1)
        if next_panel:
            grid.addWidget(next_panel, 1, 1)

        grid.setColumnStretch(0, 5)  # video side bigger
        grid.setColumnStretch(1, 5)
        grid.setRowStretch(0, 3)     # dashboard gets more
        grid.setRowStretch(1, 2)     # next stream gets less

    def _apply_normal_layout(self):
        """Restore the normal 3-column layout."""
        central = self._win.centralWidget()
        if not central:
            return

        main_layout = central.layout()
        if not main_layout:
            return

        # Find the grid layout
        grid = None
        for i in range(main_layout.count()):
            item = main_layout.itemAt(i)
            if item and isinstance(item, QGridLayout):
                grid = item
                break

        if grid is None:
            return

        # Remove all widgets from grid
        while grid.count():
            item = grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        # Restore original 3-column layout
        current_panel = getattr(self._win, 'current_panel', None)
        chat_panel = getattr(self._win, 'chat_panel', None)
        next_panel = getattr(self._win, 'next_panel', None)
        live_panel = getattr(self._win, 'live_followed_panel', None)
        dispatch_panel = getattr(self._win, 'dispatcher_panel', None)

        if current_panel:
            grid.addWidget(current_panel, 0, 0)
        if chat_panel:
            grid.addWidget(chat_panel, 0, 1, 2, 1)
        if next_panel:
            grid.addWidget(next_panel, 0, 2)
        if live_panel:
            grid.addWidget(live_panel, 1, 0)
        if dispatch_panel:
            grid.addWidget(dispatch_panel, 1, 2)

        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 4)
        grid.setColumnStretch(2, 3)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)