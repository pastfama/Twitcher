"""Base widget classes with size variant support.

Provides ``SizeVariant`` enum and ``SizedWidget`` mixin so all
mainmenu widgets can offer M (Medium) and S (Small) pixel forms
through a consistent API.

Usage::

    from widgets.base import SizeVariant, WidgetMetrics

    class MyWidget(QFrame, SizedWidget):
        def __init__(self, size=SizeVariant.M):
            super().__init__()
            self._init_metrics(size)

Size Variants
-------------
- **M** (Medium): Full-size widget for the main Current Watching panel.
  Rich data display, maximum information density.
- **S** (Small): Compact widget for side panels, live-followed rows,
  or anywhere space is limited.  Key metrics only.
"""

from enum import Enum


class SizeVariant(Enum):
    """Pixel-form size variants for all widgets."""
    M = "M"   # Medium — full panel (default)
    S = "S"   # Small  — compact / sidebar


# ====================================================================
# SULLYGOOSE METRICS — which fields each variant shows
# ====================================================================

# M size: 17 metric cells (3×6 grid) + 4 score bars
SG_M_METRICS = [
    # Row 0
    ("AVG", "sully_avg"), ("PEAK", "sully_peak"),
    ("GRW", "sully_growth"), ("RANK", "sully_rank"),
    ("FRQ", "sully_freq"), ("DUR", "sully_duration"),
    # Row 1
    ("START", "sully_start"), ("END", "sully_end"),
    ("GAMES", "sully_games"), ("MAIN", "sully_main"),
    ("RAID", "sully_raid"), ("FOL", "sully_followers"),
    # Row 2
    ("FGRW", "sully_follower_growth"),
    ("CHAT", "sully_chat"),
    ("7D", "sully_trend_7d"), ("30D", "sully_trend_30d"),
    ("BEST", "sully_best_day"),
]

SG_M_BARS = [
    ("sully_consistency_bar", "CONS"),
    ("sully_reliability_bar", "REL"),
    ("sully_discovery_bar", "DISC"),
    ("sully_score_bar", "QUAL"),
]

# S size: 5 metric cells (1 row) + 2 score bars
SG_S_METRICS = [
    ("AVG", "sully_avg"), ("PEAK", "sully_peak"),
    ("GRW", "sully_growth"), ("RANK", "sully_rank"),
    ("FOL", "sully_followers"),
]

SG_S_BARS = [
    ("sully_score_bar", "QUAL"),
    ("sully_reliability_bar", "REL"),
]

# ====================================================================
# PIXEL METRICS — dimensions for each variant
# ====================================================================

class WidgetMetrics:
    """Pixel dimensions for a specific size variant."""

    def __init__(self, variant: SizeVariant):
        self.variant = variant
        if variant == SizeVariant.M:
            # --- SG M ---
            self.sg_cell_height = 36
            self.sg_score_bar_width = 52
            self.sg_score_bar_height = 32
            self.sg_panel_min_width = 280
            self.sg_grid_cols = 6
            # --- MOM M ---
            self.mom_width = 280
            self.mom_gauge_size = 80
            self.mom_lcd_width = 140
            self.mom_lcd_height = 60
            self.mom_graph_height = 30
        else:  # SizeVariant.S
            # --- SG S ---
            self.sg_cell_height = 24
            self.sg_score_bar_width = 40
            self.sg_score_bar_height = 22
            self.sg_panel_min_width = 180
            self.sg_grid_cols = 5
            # --- MOM S ---
            self.mom_width = 120
            self.mom_gauge_size = 50
            self.mom_lcd_width = 0      # no LCD in S
            self.mom_lcd_height = 0
            self.mom_graph_height = 0   # no graph in S


class SizedWidget:
    """Mixin that provides metrics lookup for sized widgets."""

    def _init_metrics(self, variant: SizeVariant = SizeVariant.M):
        self._size_variant = variant
        self._metrics = WidgetMetrics(variant)

    @property
    def metrics(self) -> WidgetMetrics:
        return self._metrics

    @property
    def size_variant(self) -> SizeVariant:
        return self._size_variant