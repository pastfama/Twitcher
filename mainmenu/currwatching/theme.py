"""Centralized color and sizing constants for the Current Watching panel.

Extracting magic strings into named constants makes the on-screen palette
easy to audit and keeps the UI builder focused on layout rather than
colour choices.
"""


class Theme:
    """Color and sizing constants shared across the currwatching package."""

    # --- backgrounds ---
    CARD = "#141827"
    DARK_PANEL = "#0a0d18"
    METRIC_CELL = "#0a0d18"
    AVATAR_BG = "#1a2a4a"

    # --- borders ---
    CARD_BORDER = "#3c456b"
    SECTION_BORDER = "#1a2a4a"
    METRIC_BORDER = "#1a2a4a"
    PROGRESS_BORDER = "#00ffff"
    LIGHT_BORDER = "#3a3a5a"
    LIGHT_INACTIVE = "#2a2a3a"

    # --- text ---
    MUTED = "#8b93ad"
    DIM = "#6a7188"
    BRIGHT = "#c8cce0"
    GAME_DIM = "#4a5a7a"
    GRID_LINE = "#1a2a4b"

    # --- accents ---
    CYAN = "#00ffff"
    GREEN = "#72d6a0"
    RED_DARK = "#ff7777"
    RED = "#ff3366"
    ORANGE = "#ffaa00"

    # --- fonts ---
    FAMILY = "Segoe UI"

    # --- dimensions ---
    AVATAR_SIZE = 40
    THUMBNAIL_SIZE = 80

    # --- sullygoose score-bar gradient stops ---
    SCORE_GRADIENT = (
        "x1:0, y1:0, x2:1, y2:0, "
        "stop:0 #ff3366, "
        "stop:0.5 #ffaa00, "
        "stop:1 #00ffff"
    )
