"""Mood Engine — AI-driven dynamic theming for the metrics dashboard.

Analyzes chat sentiment and stream data to produce a mood classification,
which drives background gradients, accent colors, gauge colors, and glow
effects across the entire dashboard.  Mood transitions are animated smoothly
via QPropertyAnimation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from PySide6.QtCore import QObject, Signal, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QColor
from logger import debug


# ── Mood colour palettes ────────────────────────────────────────────────

@dataclass
class MoodPalette:
    """A complete colour scheme for one mood."""
    name: str
    emoji: str
    bg_start: str        # gradient start (top-left)
    bg_end: str          # gradient end (bottom-right)
    accent: str          # primary accent (gauges, highlights)
    accent_dim: str      # dimmer version for borders / inactive
    lcd_digit: str       # QLCDNumber digit colour
    progress_fill: str   # QProgressBar chunk colour
    progress_bg: str     # QProgressBar track colour
    glow: str            # glow / shadow colour for neon effects
    text: str            # primary text
    text_muted: str      # secondary / muted text
    tab_active: str      # active tab underline
    tab_inactive: str    # inactive tab text


MOODS: Dict[str, MoodPalette] = {
    "hype": MoodPalette(
        name="Hype", emoji="🔥",
        bg_start="#1a0808", bg_end="#0a0d18",
        accent="#ff3366", accent_dim="#662233",
        lcd_digit="#ff3366", progress_fill="#ff0066",
        progress_bg="#1a0510", glow="#ff3366",
        text="#ffe0ea", text_muted="#aa6677",
        tab_active="#ff3366", tab_inactive="#663344",
    ),
    "positive": MoodPalette(
        name="Positive", emoji="😊",
        bg_start="#081a0e", bg_end="#0a0d18",
        accent="#00ff88", accent_dim="#226644",
        lcd_digit="#00ff88", progress_fill="#00cc66",
        progress_bg="#051a0a", glow="#00ff88",
        text="#d0ffe0", text_muted="#66aa88",
        tab_active="#00ff88", tab_inactive="#336644",
    ),
    "neutral": MoodPalette(
        name="Neutral", emoji="🎯",
        bg_start="#080c1a", bg_end="#0a0d18",
        accent="#00ffff", accent_dim="#1a3a5a",
        lcd_digit="#00ffff", progress_fill="#00aacc",
        progress_bg="#050a1a", glow="#00ffff",
        text="#e0e4f0", text_muted="#8b93ad",
        tab_active="#00ffff", tab_inactive="#2a4a6a",
    ),
    "slow": MoodPalette(
        name="Slow", emoji="😴",
        bg_start="#0e081a", bg_end="#0a0d18",
        accent="#aa44ff", accent_dim="#442266",
        lcd_digit="#bb66ff", progress_fill="#8833cc",
        progress_bg="#0a051a", glow="#aa44ff",
        text="#e0d0ff", text_muted="#8866aa",
        tab_active="#aa44ff", tab_inactive="#442266",
    ),
    "tense": MoodPalette(
        name="Tense", emoji="⚠️",
        bg_start="#1a1208", bg_end="#0a0d18",
        accent="#ffaa00", accent_dim="#665522",
        lcd_digit="#ffcc33", progress_fill="#dd8800",
        progress_bg="#1a1005", glow="#ffaa00",
        text="#fff0d0", text_muted="#aa9966",
        tab_active="#ffaa00", tab_inactive="#665522",
    ),
}

MOOD_ORDER = ["tense", "slow", "neutral", "positive", "hype"]

# Sentiment score thresholds (−100 … +100)
_MOOD_THRESHOLDS = [
    (-100, "tense"),
    (-50,  "slow"),
    (-20,  "neutral"),
    (40,   "positive"),
    (70,   "hype"),
]


def classify_mood(sentiment: float) -> str:
    """Map a sentiment score (−100 … +100) to a mood key."""
    mood = "neutral"
    for threshold, name in _MOOD_THRESHOLDS:
        if sentiment >= threshold:
            mood = name
    return mood


def interpolate_color(c1: str, c2: str, t: float) -> str:
    """Linearly interpolate between two hex colours (0.0 = c1, 1.0 = c2)."""
    q1 = QColor(c1)
    q2 = QColor(c2)
    r = int(q1.red()   + (q2.red()   - q1.red())   * t)
    g = int(q1.green() + (q2.green() - q1.green()) * t)
    b = int(q1.blue()  + (q2.blue()  - q1.blue())  * t)
    return f"#{r:02x}{g:02x}{b:02x}"


# ── MoodEngine ──────────────────────────────────────────────────────────

class MoodEngine(QObject):
    """Tracks sentiment over time, classifies mood, and emits animated
    colour palettes when the mood changes."""

    palette_changed = Signal(object)  # emits MoodPalette

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_mood = "neutral"
        self._current_palette = MOODS["neutral"]
        self._sentiment_history: List[float] = []
        self._smoothing_window = 5   # rolling window for sentiment averaging
        self._transition_timer = QTimer(self)
        self._transition_timer.setSingleShot(True)
        self._transition_timer.setInterval(2000)  # 2 s cooldown between mood shifts
        self._pending_mood: Optional[str] = None

    # ── public API ──

    @property
    def current_mood(self) -> str:
        return self._current_mood

    @property
    def current_palette(self) -> MoodPalette:
        return self._current_palette

    def update_sentiment(self, raw_score: float):
        """Feed a new sentiment score (−100 … +100).  The engine smooths it
        over a rolling window and transitions mood if the smoothed value
        crosses a threshold boundary."""
        self._sentiment_history.append(raw_score)
        if len(self._sentiment_history) > self._smoothing_window:
            self._sentiment_history = self._sentiment_history[-self._smoothing_window:]

        smoothed = sum(self._sentiment_history) / len(self._sentiment_history)
        new_mood = classify_mood(smoothed)

        if new_mood != self._current_mood:
            # Debounce — wait for cooldown before switching
            self._pending_mood = new_mood
            if not self._transition_timer.isActive():
                self._apply_mood(new_mood)
                self._transition_timer.start()

    def _apply_mood(self, mood: str):
        """Switch to a new mood and emit the palette."""
        debug(f"[MOOD ENGINE] Mood shift: {self._current_mood} → {mood}")
        self._current_mood = mood
        self._current_palette = MOODS[mood]
        self.palette_changed.emit(self._current_palette)

    def set_mood_direct(self, mood: str):
        """Force-set the mood (e.g. from a manual override)."""
        if mood in MOODS and mood != self._current_mood:
            self._apply_mood(mood)

    def get_palette_for_score(self, sentiment: float) -> MoodPalette:
        """Look up the palette for a given sentiment without changing state."""
        return MOODS[classify_mood(sentiment)]

    def reset(self):
        """Reset to neutral mood."""
        self._sentiment_history.clear()
        self._pending_mood = None
        self._transition_timer.stop()
        if self._current_mood != "neutral":
            self._apply_mood("neutral")