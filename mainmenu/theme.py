"""Shared theme constants for all mainmenu panels.

This module provides a centralized location for color and styling constants
used across all panels in the mainmenu package, ensuring visual consistency.
"""


class Theme:
    """Color and sizing constants shared across all mainmenu panels."""

    # --- backgrounds ---
    CARD = "#141827"
    DARK_PANEL = "#0a0d18"
    METRIC_CELL = "#0a0d18"
    AVATAR_BG = "#1a2a4a"
    GROUP_BOX_BG = "#0f1320"

    # --- borders ---
    CARD_BORDER = "#3c456b"
    SECTION_BORDER = "#1a2a4a"
    METRIC_BORDER = "#1a2a4a"
    PROGRESS_BORDER = "#00ffff"
    LIGHT_BORDER = "#3a3a5a"
    LIGHT_INACTIVE = "#2a2a3a"
    GROUP_BOX_BORDER = "#2a3a5a"

    # --- text ---
    MUTED = "#8b93ad"
    DIM = "#6a7188"
    BRIGHT = "#c8cce0"
    GAME_DIM = "#4a5a7a"
    GRID_LINE = "#1a2a4b"
    TEXT_PRIMARY = "#e0e4f0"
    TEXT_SECONDARY = "#a0a8c0"

    # --- accents ---
    CYAN = "#00ffff"
    GREEN = "#72d6a0"
    RED_DARK = "#ff7777"
    RED = "#ff3366"
    ORANGE = "#ffaa00"
    TEAL = "#78d6c5"

    # --- fonts ---
    FAMILY = "Segoe UI"

    # --- dimensions ---
    AVATAR_SIZE = 40
    THUMBNAIL_SIZE = 80

    # --- score-bar gradient ---
    SCORE_GRADIENT = (
        "x1:0, y1:0, x2:1, y2:0, "
        "stop:0 #ff3366, "
        "stop:0.5 #ffaa00, "
        "stop:1 #00ffff"
    )

    # --- common styles ---
    @staticmethod
    def group_box_style(title_color=None):
        """Return a consistent QGroupBox stylesheet."""
        if title_color is None:
            title_color = Theme.CYAN
        return f"""
            QGroupBox {{
                background-color: {Theme.GROUP_BOX_BG};
                border: 1px solid {Theme.GROUP_BOX_BORDER};
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 16px;
                font-weight: bold;
            }}
            QGroupBox::title {{
                color: {title_color};
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                font-size: 11px;
            }}
        """

    @staticmethod
    def frame_style():
        """Return a consistent QFrame stylesheet."""
        return f"""
            QFrame {{
                background-color: {Theme.CARD};
                border: 1px solid {Theme.CARD_BORDER};
                border-radius: 4px;
            }}
        """