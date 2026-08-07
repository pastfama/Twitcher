"""Theme constants for the CustomTkinter GUI.

Ported 1:1 from ``mainmenu/currwatching/theme.py`` so the rebuilt
Current-Watching card is pixel-faithful to the original dark/neon look.
"""


class Theme:
    # --- backgrounds ---
    CARD = "#141827"
    DARK_PANEL = "#0a0d18"
    METRIC_CELL = "#0a0d18"
    AVATAR_BG = "#1a2a4a"

    # --- dashboard default ---
    DEFAULT_WIDTH = 1920
    DEFAULT_HEIGHT = 1080

    # --- borders ---
    CARD_BORDER = "#3c456b"
    SECTION_BORDER = "#1a2a4b"
    METRIC_BORDER = "#1a2a4b"
    PROGRESS_BORDER = "#00ffff"
    LIGHT_BORDER = "#3a3a5a"
    LIGHT_INACTIVE = "#2a2a3a"

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


# Map a ViewerTracker.status string to the accent colour used for the
# "live" sentiment label + neon indicator.

# Sentiment label for the status text.
STATUS_LABEL = {
    "🚀 Spike": "SPIKE",
    "🟢 Rising": "RISING",
    "📉 Drop": "DROP",
    "🔴 Falling": "FALLING",
    "🟡 Stable": "STABLE",
    "stable": "STABLE",
    "warming up": "WARMING",
}


try:
    from customtkinter import CTkFont

    def font(size=12, weight="normal"):
        """Convenience font loader (falls back to Tk default if needed)."""
        try:
            return CTkFont(family=Theme.FAMILY, size=size, weight=weight)
        except Exception:
            return CTkFont(size=size, weight=weight)
except Exception:  # customtkinter not installed yet
    font = None

# Status -> color map for the neon indicator and sentiment label.
STATUS_COLORS = {
    "\U0001f680 Spike": Theme.GREEN,
    "\U0001f7e2 Rising": Theme.GREEN,
    "\U0001f4c9 Drop": Theme.RED,
    "\U0001f534 Falling": Theme.RED,
    "\U0001f7e1 Stable": Theme.ORANGE,
    "stable": Theme.MUTED,
    "warming up": Theme.MUTED,
}
