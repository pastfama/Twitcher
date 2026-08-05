"""UI construction for the Current Watching panel.

Exact pixel-based split using module constants:
- Left (red box): MOM widget with gauge, LCD, momentum label, neon indicators
- Right (green box): SG widget with metrics grid and score bars
"""

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLCDNumber,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
import logging

from .theme import Theme
from widgets.mom import AnalogGauge, GAUGE_SIZE, MOM_WIDTH, LCD_WIDTH, LCD_HEIGHT, GRAPH_HEIGHT
from widgets.sullygoose import SullyGooseWidget
from widgets.viewer_graph import ViewerHistoryGraph
from widgets.indicators import NeonIndicator

logger = logging.getLogger(__name__)


class CurrentWatchingUIBuilder:
    """Constructs all child widgets using module-defined size constants."""

    def __init__(self, panel):
        logger.debug("CurrentWatchingUIBuilder initializing...")
        self.panel = panel
        self._build()
        logger.debug("CurrentWatchingUIBuilder build complete")

    def _build(self):
        self._setup_panel()

        main_layout = QVBoxLayout(self.panel)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # Header (avatar + channel + title)
        self._build_header(main_layout)

        # Pixel-based split: MOM (fixed width) | SG (expanding)
        split = QHBoxLayout()
        split.setSpacing(4)
        split.setContentsMargins(0, 0, 0, 0)

        # Left: MOM widget (red box area) - uses MOM_WIDTH constant
        left_container = QWidget()
        left_container.setFixedWidth(MOM_WIDTH)
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        self._build_mom_section(left_layout)

        # Right: SG widget (green box area) - expands to fill remaining space
        right_container = QWidget()
        right_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)
        self._build_sg_section(right_layout)

        split.addWidget(left_container)
        split.addWidget(right_container, 1)

        main_layout.addLayout(split, 1)

    def _setup_panel(self):
        self.panel.setObjectName("CurrentCard")
        self.panel.viewer_analysis = None
        self.panel.setMinimumHeight(140)
        self.panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _build_header(self, layout):
        """Avatar + channel name + LIVE badge + title."""
        header = QHBoxLayout()
        header.setSpacing(6)

        # Avatar
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

        # Channel info
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

        # Uptime and time labels
        self.panel.uptime_label = QLabel("⏱ —")
        self.panel.uptime_label.setStyleSheet(
            f"color: {Theme.MUTED}; font-size: 9px;"
        )
        info_layout.addWidget(self.panel.uptime_label)

        self.panel.streamer_time_label = QLabel("⏰ Streamer: —")
        self.panel.streamer_time_label.setStyleSheet(
            f"color: {Theme.MUTED}; font-size: 8px;"
        )
        info_layout.addWidget(self.panel.streamer_time_label)

        self.panel.my_time_label = QLabel("⏰ Me: —")
        self.panel.my_time_label.setStyleSheet(
            f"color: {Theme.MUTED}; font-size: 8px;"
        )
        info_layout.addWidget(self.panel.my_time_label)

        header.addLayout(info_layout, 1)
        layout.addLayout(header)

    def _build_mom_section(self, layout):
        """MOM widget for left side (red box): gauge + LCD + momentum + indicators.
        
        Uses constants from widgets.mom module:
        - GAUGE_SIZE: 80x80 circular gauge
        - LCD_WIDTH/LCD_HEIGHT: 140x60 viewer count display
        - GRAPH_HEIGHT: 30px viewer history graph strip
        """
        # Top row: Gauge + LCD side by side
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        # MOM gauge - uses GAUGE_SIZE constant
        self.panel.mini_gauge = AnalogGauge(size=GAUGE_SIZE)
        self.panel.mini_gauge.set_value(50, "MOM")
        top_row.addWidget(self.panel.mini_gauge)

        # LCD counter - uses LCD_WIDTH/LCD_HEIGHT constants
        lcd_container = QWidget()
        lcd_layout = QVBoxLayout(lcd_container)
        lcd_layout.setContentsMargins(0, 0, 0, 0)
        lcd_layout.setSpacing(2)

        self.panel.enlarged_lcd_counter = QLCDNumber()
        self.panel.enlarged_lcd_counter.setDigitCount(6)
        self.panel.enlarged_lcd_counter.setSegmentStyle(
            QLCDNumber.SegmentStyle.Flat
        )
        self.panel.enlarged_lcd_counter.setFixedSize(LCD_WIDTH, LCD_HEIGHT)
        self.panel.enlarged_lcd_counter.setStyleSheet(
            f"QLCDNumber {{ "
            f"background-color: {Theme.DARK_PANEL}; "
            f"color: {Theme.CYAN}; "
            f"border: 2px solid {Theme.CYAN}; "
            f"border-radius: 6px; font-size: 32px; }}"
        )
        self.panel.enlarged_lcd_counter.display(0)
        lcd_layout.addWidget(self.panel.enlarged_lcd_counter)

        # Momentum label below LCD
        self.panel.momentum_label = QLabel("📊 Waiting...")
        self.panel.momentum_label.setStyleSheet(
            f"color: {Theme.CYAN}; font-size: 11px; font-weight: bold;"
        )
        self.panel.momentum_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lcd_layout.addWidget(self.panel.momentum_label)

        top_row.addWidget(lcd_container, 1)
        layout.addLayout(top_row)

        # Viewer history graph - uses GRAPH_HEIGHT constant
        self.panel.viewer_history_graph = ViewerHistoryGraph()
        self.panel.viewer_history_graph.setFixedHeight(GRAPH_HEIGHT)
        layout.addWidget(self.panel.viewer_history_graph)

        # Neon indicators at bottom
        indicators_row = QHBoxLayout()
        indicators_row.setSpacing(4)
        indicators_row.addStretch()

        self.panel.neon_viewer_counter = NeonIndicator("VIEWERS", Theme.CYAN)
        self.panel.light_live = NeonIndicator("LIVE", Theme.RED)
        self.panel.light_chat = NeonIndicator("CHAT", Theme.CYAN)
        self.panel.light_raid = NeonIndicator("RAID", Theme.ORANGE)

        indicators_row.addWidget(self.panel.neon_viewer_counter)
        indicators_row.addWidget(self.panel.light_live)
        indicators_row.addWidget(self.panel.light_chat)
        indicators_row.addWidget(self.panel.light_raid)
        indicators_row.addStretch()

        layout.addLayout(indicators_row)

    def _build_sg_section(self, layout):
        """SG widget for right side (green box): SullyGoose analytics grid.
        
        Uses SullyGooseWidget which has its own size constants defined in
        widgets.sullygoose module (METRIC_CELL_HEIGHT, SCORE_BAR_WIDTH, etc.)
        """
        self.panel.sully_widget = SullyGooseWidget()
        layout.addWidget(self.panel.sully_widget)