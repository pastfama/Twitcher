"""UI construction for the Current Watching panel.

:class:`CurrentWatchingUIBuilder` is a pure-UI builder: it creates every
widget on a :class:`~currwatching.panel.CurrentWatchingPanel` instance and
registers them as attributes.  It contains **no** business logic or
network calls — those live on the panel itself so the builder stays
focused on layout.

The monolithic ``build()`` from the previous flat file is split into
small, focused ``_build_*`` helpers that each construct one visual
section of the card.
"""

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLCDNumber,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
import logging

from .theme import Theme
from widgets.mom import AnalogGauge
from widgets.viewer_graph import ViewerHistoryGraph
from widgets.indicators import NeonIndicator

# Logging for debugging
logger = logging.getLogger(__name__)


class CurrentWatchingUIBuilder:
    """Constructs all child widgets and attaches them to *panel*."""

    def __init__(self, panel):
        logger.debug("CurrentWatchingUIBuilder initializing...")
        self.panel = panel
        self._build()
        logger.debug("CurrentWatchingUIBuilder build complete")

    # ============================================================ ENTRY

    def _build(self):
        self._setup_panel()

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(3)

        self._build_header(layout)
        self._build_game_section(layout)
        self._build_stats_row(layout)
        self._build_sullygoose(layout)
        self._build_indicators(layout)

    # ============================================================ SETUP

    def _setup_panel(self):
        self.panel.setObjectName("CurrentCard")
        self.panel.viewer_analysis = None
        self.panel.setMinimumHeight(100)

    # ============================================================ HEADER

    def _build_header(self, layout):
        """Avatar + channel name + LIVE badge + title."""
        header = QHBoxLayout()
        header.setSpacing(6)

        # --- Avatar ---
        self.panel.avatar_label = QLabel()
        self.panel.avatar_label.setFixedSize(Theme.AVATAR_SIZE, Theme.AVATAR_SIZE)
        self.panel.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.panel.avatar_label.setStyleSheet(
            f"background-color: {Theme.AVATAR_BG}; "
            f"border: 1px solid {Theme.CYAN}; border-radius: 20px; "
            f"color: {Theme.CYAN}; font-size: 12px;"
        )
        self.panel.avatar_label.setText("?")
        header.addWidget(self.panel.avatar_label)


        # --- Channel info column ---
        info_layout = QVBoxLayout()
        info_layout.setSpacing(1)

        name_row = QHBoxLayout()
        name_row.setSpacing(4)
        self.panel.channel_label = QLabel("—")
        self.panel.channel_label.setFont(
            QFont(Theme.FAMILY, 10, QFont.Weight.Bold)
        )
        self.panel.live_label = QLabel("● LIVE")
        self.panel.live_label.setStyleSheet(
            f"color: {Theme.RED}; font-weight: bold; font-size: 8px;"
        )
        name_row.addWidget(self.panel.channel_label)
        name_row.addWidget(self.panel.live_label)
        info_layout.addLayout(name_row)

        self.panel.title_label = QLabel("—")
        self.panel.title_label.setWordWrap(True)
        self.panel.title_label.setStyleSheet(
            f"color: {Theme.MUTED}; font-size: 8px;"
        )
        info_layout.addWidget(self.panel.title_label)

        header.addLayout(info_layout, 1)
        layout.addLayout(header)

    # ============================================================ GAME

    def _build_game_section(self, layout):
        """Game thumbnail + category label + status indicators."""
        game_section = QHBoxLayout()
        game_section.setSpacing(8)

        # --- Thumbnail (80×80 to match Theme.THUMBNAIL_SIZE) ---
        self.panel.game_thumbnail = QLabel()
        self.panel.game_thumbnail.setFixedSize(
            Theme.THUMBNAIL_SIZE, Theme.THUMBNAIL_SIZE
        )
        self.panel.game_thumbnail.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.panel.game_thumbnail.setStyleSheet(
            f"background-color: {Theme.DARK_PANEL}; "
            f"border: 2px solid {Theme.CYAN}; border-radius: 8px; "
            f"color: {Theme.GAME_DIM}; font-size: 12px;"
        )
        self.panel.game_thumbnail.setText("🎮")
        game_section.addWidget(self.panel.game_thumbnail)

        # --- Game category label ---
        self.panel.category_label = QLabel("No Game")
        self.panel.category_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.panel.category_label.setStyleSheet(f"""
            QLabel {{
                color: {Theme.BRIGHT};
                font-size: 14px;
                font-weight: bold;
                background-color: {Theme.DARK_PANEL};
                padding: 8px;
                border-radius: 4px;
            }}
        """)
        self.panel.category_label.setWordWrap(True)
        self.panel.category_label.setMaximumHeight(40)
        game_section.addWidget(self.panel.category_label, 1)

        # --- Status indicators (stable, uptime) ---
        status_layout = QVBoxLayout()
        status_layout.setSpacing(2)
        self.panel.stability_label = QLabel("● Stable +0.0%")
        self.panel.stability_label.setStyleSheet(f"color: {Theme.GREEN}; font-size: 9px;")
        self.panel.uptime_display = QLabel(" 0h 0m")
        self.panel.uptime_display.setStyleSheet(f"color: {Theme.CYAN}; font-size: 9px;")
        status_layout.addWidget(self.panel.stability_label)
        status_layout.addWidget(self.panel.uptime_display)
        game_section.addLayout(status_layout)

        layout.addLayout(game_section)

    # ============================================================ STATS ROW

    def _build_stats_row(self, layout):
        """Redesigned stats section: MOM gauge + viewer graph + LCD display + momentum label."""
        stats_container = QFrame()
        stats_container.setStyleSheet(f"background-color: {Theme.DARK_PANEL}; border: 1px solid {Theme.LIGHT_BORDER}; border-radius: 4px;")
        stats_layout = QHBoxLayout(stats_container)
        stats_layout.setContentsMargins(8, 6, 8, 6)
        stats_layout.setSpacing(12)

        # --- MOM gauge (circular with needle) ---
        self.panel.mini_gauge = AnalogGauge()
        self.panel.mini_gauge.setFixedSize(80, 80)
        self.panel.mini_gauge.set_value(50, "MOM")
        stats_layout.addWidget(self.panel.mini_gauge)

        # --- Viewer history graph (takes majority of space) ---
        self.panel.viewer_history_graph = ViewerHistoryGraph()
        self.panel.viewer_history_graph.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.panel.viewer_history_graph.setMinimumHeight(60)
        stats_layout.addWidget(self.panel.viewer_history_graph, 3)

        # --- Large LCD viewer counter ---
        self.panel.enlarged_lcd_counter = QLCDNumber()
        self.panel.enlarged_lcd_counter.setDigitCount(6)
        self.panel.enlarged_lcd_counter.setSegmentStyle(
            QLCDNumber.SegmentStyle.Flat
        )
        self.panel.enlarged_lcd_counter.setFixedSize(180, 70)
        self.panel.enlarged_lcd_counter.setStyleSheet(
            f"QLCDNumber {{ "
            f"background-color: {Theme.DARK_PANEL}; "
            f"color: {Theme.CYAN}; "
            f"border: 2px solid {Theme.CYAN}; "
            f"border-radius: 6px; font-size: 42px; }}"
        )
        self.panel.enlarged_lcd_counter.display(0)
        stats_layout.addWidget(self.panel.enlarged_lcd_counter)

        # --- Momentum label (status text like "Rising +5%") ---
        self.panel.momentum_label = QLabel("📊 Waiting...")
        self.panel.momentum_label.setStyleSheet(
            f"color: {Theme.CYAN}; font-size: 11px; font-weight: bold;"
        )
        stats_layout.addWidget(self.panel.momentum_label)

        layout.addWidget(stats_container)

    # ============================================================ SULLY

    def _build_sullygoose(self, layout):
        """SullyGoose analytics grid + score bars."""
        # Create a container that takes more vertical space
        sully_container = QWidget()
        sully_container_layout = QVBoxLayout(sully_container)
        sully_container_layout.setContentsMargins(0, 0, 0, 0)
        sully_container_layout.setSpacing(2)
        
        # SullyGoose frame - expanded to take more space
        sully_frame = QFrame()
        sully_frame.setStyleSheet(self._sully_frame_style())
        sully_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        sully_layout = QVBoxLayout(sully_frame)
        sully_layout.setContentsMargins(4, 3, 4, 3)
        sully_layout.setSpacing(2)

        # --- Title ---
        sully_title = QLabel("◆ SULLYGOOSE ◆")
        sully_title.setFont(
            QFont(Theme.FAMILY, 7, QFont.Weight.Bold)
        )
        sully_title.setStyleSheet(f"color: {Theme.CYAN};")
        sully_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sully_layout.addWidget(sully_title)

        # --- Time section: Streamer time + My time + Uptime ---
        time_row = QHBoxLayout()
        time_row.setSpacing(4)

        self.panel.streamer_time_label = QLabel("⏰ Streamer: —")
        self.panel.streamer_time_label.setStyleSheet(f"color: {Theme.CYAN}; font-size: 9px; font-weight: bold;")
        time_row.addWidget(self.panel.streamer_time_label)

        self.panel.my_time_label = QLabel("⏰ Me: —")
        self.panel.my_time_label.setStyleSheet(f"color: {Theme.CYAN}; font-size: 9px; font-weight: bold;")
        time_row.addWidget(self.panel.my_time_label)

        self.panel.uptime_label = QLabel("⏱ Uptime: —")
        self.panel.uptime_label.setStyleSheet(f"color: {Theme.CYAN}; font-size: 9px; font-weight: bold;")
        time_row.addWidget(self.panel.uptime_label)

        # --- Additional metrics label ---
        self.panel.additional_metrics_label = QLabel("📈 Peak: — | Avg: —")
        self.panel.additional_metrics_label.setStyleSheet(f"color: {Theme.CYAN}; font-size: 9px; font-weight: bold;")
        time_row.addWidget(self.panel.additional_metrics_label)

        time_row.addStretch()
        sully_layout.addLayout(time_row)

        # --- 6-column compact metric grid ---
        grid = QGridLayout()
        grid.setSpacing(2)

        metrics = [
            ("AVG", "sully_avg_label"), ("PEAK", "sully_peak_label"),
            ("GRW", "sully_growth_label"), ("RANK", "sully_rank_label"),
            ("FRQ", "sully_freq_label"), ("DUR", "sully_duration_label"),
            ("START", "sully_start_label"), ("END", "sully_end_label"),
            ("GAMES", "sully_games_label"), ("MAIN", "sully_main_game_label"),
            ("RAID", "sully_raid_freq_label"), ("FOL", "sully_followers_label"),
            ("FGRW", "sully_follower_growth_label"),
            ("CHAT", "sully_chat_label"),
            ("7D", "sully_trend_7d_label"),
            ("30D", "sully_trend_30d_label"),
            ("BEST", "sully_best_day_label"),
        ]

        for idx, (title, attr_name) in enumerate(metrics):
            label = self._make_compact_metric(title)
            setattr(self.panel, attr_name, label)
            grid.addWidget(label, idx // 6, idx % 6)

        sully_layout.addLayout(grid)

        # --- Score bars ---
        bars_row = QHBoxLayout()
        bars_row.setSpacing(3)

        for name, label_text in [
            ("sully_consistency_bar", "CONS"),
            ("sully_reliability_bar", "REL"),
            ("sully_discovery_bar", "DISC"),
            ("sully_score_bar", "QUAL"),
        ]:
            bars_row.addLayout(self._make_score_bar(name, label_text))

        sully_layout.addLayout(bars_row)
        sully_container_layout.addWidget(sully_frame)
        layout.addWidget(sully_container, 1)  # Give it more stretch factor

    # ============================================================ INDICATORS

    def _build_indicators(self, layout):
        """Neon indicator lights: VIEWERS / LIVE / CHAT / RAID."""
        lights_row = QHBoxLayout()
        lights_row.setSpacing(4)
        lights_row.addStretch()

        self.panel.neon_viewer_counter = NeonIndicator("VIEWERS", Theme.CYAN)
        self.panel.light_live = NeonIndicator("LIVE", Theme.RED)
        self.panel.light_chat = NeonIndicator("CHAT", Theme.CYAN)
        self.panel.light_raid = NeonIndicator("RAID", Theme.ORANGE)

        lights_row.addWidget(self.panel.neon_viewer_counter)
        lights_row.addWidget(self.panel.light_live)
        lights_row.addWidget(self.panel.light_chat)
        lights_row.addWidget(self.panel.light_raid)
        lights_row.addStretch()

        layout.addLayout(lights_row)

    # ============================================================ HELPERS

    def _make_compact_metric(self, title):
        """Create a compact metric cell with large readable text."""
        container = QFrame()
        container.setStyleSheet(self._metric_cell_style())

        v = QVBoxLayout(container)
        v.setContentsMargins(1, 0, 1, 0)
        v.setSpacing(0)

        t = QLabel(title)
        t.setFont(QFont(Theme.FAMILY, 11, QFont.Weight.Bold))
        t.setStyleSheet(f"color: {Theme.GAME_DIM};")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)

        val = QLabel("—")
        val.setFont(QFont(Theme.FAMILY, 15, QFont.Weight.Bold))
        val.setStyleSheet(f"color: {Theme.CYAN};")
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)

        v.addWidget(t)
        v.addWidget(val)

        container.value_label = val
        container.title_label = t
        return container

    def _make_score_bar(self, attr_name, label_text):
        """Create a labeled QProgressBar and register it on the panel."""
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setTextVisible(True)
        bar.setFixedHeight(10)
        bar.setFixedWidth(50)
        bar.setStyleSheet(self._score_bar_style())
        setattr(self.panel, attr_name, bar)

        v = QVBoxLayout()
        v.setSpacing(0)
        lbl = QLabel(label_text)
        lbl.setFont(QFont(Theme.FAMILY, 5))
        lbl.setStyleSheet(f"color: {Theme.GAME_DIM};")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(lbl)
        v.addWidget(bar)
        return v

    # -- style helpers -------------------------------------------------

    @staticmethod
    def _sully_frame_style():
        return (
            f"QFrame {{\n"
            f"    background-color: {Theme.DARK_PANEL};\n"
            f"    border: 1px solid {Theme.SECTION_BORDER};\n"
            f"    border-radius: 3px;\n"
            f"}}"
        )

    @staticmethod
    def _metric_cell_style():
        return (
            f"QFrame {{\n"
            f"    background-color: {Theme.METRIC_CELL};\n"
            f"    border: 1px solid {Theme.METRIC_BORDER};\n"
            f"    border-radius: 2px;\n"
            f"}}"
        )

    @staticmethod
    def _score_bar_style():
        return (
            f"QProgressBar {{\n"
            f"    background-color: {Theme.DARK_PANEL};\n"
            f"    border: 1px solid {Theme.PROGRESS_BORDER};\n"
            f"    border-radius: 2px;\n"
            f"    text-align: center;\n"
            f"    font-size: 6px;\n"
            f"    font-weight: bold;\n"
            f"    color: {Theme.CYAN};\n"
            f"}}\n"
            f"QProgressBar::chunk {{\n"
            f"    background-color: qlineargradient(\n"
            f"        x1:0, y1:0, x2:1, y2:0,\n"
            f"        stop:0 {Theme.RED},\n"
            f"        stop:0.5 {Theme.ORANGE},\n"
            f"        stop:1 {Theme.CYAN}\n"
            f"    );\n"
            f"    border-radius: 1px;\n"
            f"}}"
        )