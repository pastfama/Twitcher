"""SullyGoose analytics widget — compact metric grid for the Current Watching panel.

Modern dark-themed widget with uniform metric cells and score bars.

Size constants (codewide):
- METRIC_CELL_HEIGHT: Height of each metric cell in the grid
- SCORE_BAR_WIDTH/SCORE_BAR_HEIGHT: Size of score progress bars
- PANEL_MIN_WIDTH: Minimum width for the SullyGoose panel
"""

import re
import logging

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# Set up logger for debugging
logger = logging.getLogger(__name__)

# Top-level size constants (codewide)
METRIC_CELL_HEIGHT = 36
SCORE_BAR_WIDTH = 52
SCORE_BAR_HEIGHT = 32
PANEL_MIN_WIDTH = 280


class MetricCell(QWidget):
    """Compact metric cell with title and large value."""

    # Class constant
    CELL_HEIGHT = METRIC_CELL_HEIGHT

    def __init__(self, title="", value="—", parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.CELL_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(0)

        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #6b6b80;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.value_label = QLabel(str(value))
        self.value_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.value_label.setStyleSheet("color: #00d4ff;")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value):
        self.value_label.setText(str(value))

    def set_color(self, color_hex):
        self.value_label.setStyleSheet(f"color: {color_hex}; font-size: 11px; font-weight: bold;")


class ScoreBar(QWidget):
    """Labeled progress bar for SullyGoose scores."""

    # Class constants
    BAR_WIDTH = SCORE_BAR_WIDTH
    BAR_HEIGHT = SCORE_BAR_HEIGHT

    def __init__(self, label_text="", parent=None):
        super().__init__(parent)
        self.setFixedWidth(self.BAR_WIDTH)
        self.setFixedHeight(self.BAR_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(True)
        self.bar.setFixedHeight(12)
        self.bar.setStyleSheet(self._style())
        layout.addWidget(self.bar)

        lbl = QLabel(label_text)
        lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #6b6b80;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

    def set_value(self, value):
        self.bar.setValue(int(value))
        self.bar.setFormat(f"{int(value)}")

    def set_format(self, text):
        self.bar.setFormat(text)

    @staticmethod
    def _style():
        return (
            "QProgressBar {"
            "  background-color: #1a1a2e;"
            "  border: 1px solid #2a2a40;"
            "  border-radius: 2px;"
            "  text-align: center;"
            "  font-size: 6px;"
            "  font-weight: bold;"
            "  color: #00d4ff;"
            "}"
            "QProgressBar::chunk {"
            "  background-color: qlineargradient("
            "    x1:0, y1:0, x2:1, y2:0,"
            "    stop:0 #ff4444,"
            "    stop:0.5 #ffaa00,"
            "    stop:1 #00d4ff"
            "  );"
            "  border-radius: 1px;"
            "}"
        )


class SullyGooseWidget(QFrame):
    """Compact SullyGoose analytics grid with score bars."""

    # Class constant
    MIN_WIDTH = PANEL_MIN_WIDTH

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sullygoosePanel")
        self.setStyleSheet(
            "QFrame#sullygoosePanel {"
            "  background-color: #12121c;"
            "  border: 1px solid #29293d;"
            "  border-radius: 3px;"
            "}"
        )
        self.setMinimumWidth(self.MIN_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        main = QVBoxLayout(self)
        main.setContentsMargins(4, 3, 4, 3)
        main.setSpacing(2)

        # Title row with trend indicator
        self.title_layout = QHBoxLayout()
        self.title_layout.setContentsMargins(0, 0, 0, 0)
        self.title_layout.setSpacing(4)

        self.trend_indicator = QLabel("")
        self.trend_indicator.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.trend_indicator.setStyleSheet("color: #00d4ff;")
        self.title_layout.addWidget(self.trend_indicator)

        self.title = QLabel("◆ SULLYGOOSE ◆")
        self.title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.title.setStyleSheet("color: #00d4ff;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_layout.addWidget(self.title)

        main.addLayout(self.title_layout)
        
        # 6-column metric grid
        grid = QGridLayout()
        grid.setSpacing(2)
        
        metrics = [
            ("AVG", "sully_avg"), ("PEAK", "sully_peak"),
            ("GRW", "sully_growth"), ("RANK", "sully_rank"),
            ("FRQ", "sully_freq"), ("DUR", "sully_duration"),
            ("START", "sully_start"), ("END", "sully_end"),
            ("GAMES", "sully_games"), ("MAIN", "sully_main"),
            ("FOL", "sully_followers"),
            ("FGRW", "sully_follower_growth"),
            ("CHAT", "sully_chat"),
            ("7D", "sully_trend_7d"), ("30D", "sully_trend_30d"),
            ("BEST", "sully_best_day"),
        ]
        
        for idx, (title, attr) in enumerate(metrics):
            cell = MetricCell(title)
            setattr(self, attr, cell)
            grid.addWidget(cell, idx // 6, idx % 6)
        
        main.addLayout(grid)
        
        # ADD: Trend score meter (reuses existing space)
        self.trend_meter = QProgressBar()
        self.trend_meter.setFixedHeight(6)
        self.trend_meter.setTextVisible(False)
        grid.addWidget(self.trend_meter, 6, 0, 1, 6)  # Below metric grid
        
        # Score bars
        bars = QHBoxLayout()
        bars.setSpacing(2)
        
        for name, text in [
            ("sully_consistency_bar", "CONS"),
            ("sully_reliability_bar", "REL"),
            ("sully_discovery_bar", "DISC"),
            ("sully_score_bar", "QUAL"),
        ]:
            bars.addWidget(ScoreBar(text))
            setattr(self, name, bars.itemAt(bars.count() - 1).widget())
        
        main.addLayout(bars)
        
    def update_metrics(self, sully, analysis=None, trend_data=None, current_channel=None):
        """Update with SullyGnome data and optional Twitch trend data
        
        Note: current_channel guard removed - widget receives data via signal
        which already ensures only current channel data is delivered.
        """
        # 1. First update with SullyGnome data (existing functionality)
        if not sully:
            self._clear()
            return
                
        # Log all received metrics for debugging
        logger.debug(f"Received SullyGoose data: {sully}")
        
        # Viewers
        avg_viewers = sully.get('avg_viewers', 0)
        self.sully_avg.set_value(f"{avg_viewers:,}")
        logger.debug(f"AVG metric: {avg_viewers}")
        
        peak_viewers = sully.get('peak_viewers', 0)
        self.sully_peak.set_value(f"{peak_viewers:,}")
        logger.debug(f"PEAK metric: {peak_viewers}")
        
        # Growth & Rank
        growth = sully.get("viewer_growth") or 0
        self.sully_growth.set_value(f"{growth:+.1f}%")
        self.sully_growth.set_color("#72d6a0" if growth > 0 else ("#ff7777" if growth < 0 else "#f2f2f2"))
        logger.debug(f"GROWTH metric: {growth}")
        
        rank = sully.get("category_rank", 0) or 0
        self.sully_rank.set_value(f"#{rank}")
        logger.debug(f"RANK metric: {rank}")
        
        freq = sully.get("stream_frequency", 0) or 0
        self.sully_freq.set_value(f"{freq:.0f}h/wk")
        logger.debug(f"FREQUENCY metric: {freq}")
        
        # Schedule
        dur = sully.get("avg_stream_duration", 0) or 0
        self.sully_duration.set_value(f"{dur:.1f}h")
        logger.debug(f"DURATION metric: {dur}")
        
        start_h = sully.get("typical_start_hour", 0) or 0
        end_h = sully.get("typical_end_hour", 0) or 0
        self.sully_start.set_value(f"{start_h:02d}:00")
        self.sully_end.set_value(f"{end_h:02d}:00")
        logger.debug(f"SCHEDULE: {start_h}:{end_h}")
        
        # Content
        games = sully.get("games_played_30d", 0) or 0
        self.sully_games.set_value(str(games))
        logger.debug(f"GAMES metric: {games}")
        
        main_pct = sully.get("main_game_pct")
        self.sully_main.set_value(f"{main_pct}%" if main_pct is not None else "—")
        logger.debug(f"MAIN metric: {main_pct}")
        
        # Trends
        t7d = sully.get("trend_7d", "Stable") or "Stable"
        t7d_pct = sully.get("trend_7d_pct", 0) or 0
        arrow7 = "↗" if t7d == "Rising" else ("↘" if t7d == "Declining" else "→")
        self.sully_trend_7d.set_value(f"{arrow7} {t7d_pct:+.1f}%")
        self.sully_trend_7d.set_color("#72d6a0" if t7d == "Rising" else ("#ff7777" if t7d == "Declining" else "#ffaa00"))
        logger.debug(f"TREND_7D metric: {t7d}, {t7d_pct}")
        
        t30d = sully.get("trend_30d", "Stable") or "Stable"
        t30d_pct = sully.get("trend_30d_pct", 0) or 0
        arrow30 = "↗" if t30d == "Rising" else ("↘" if t30d == "Declining" else "→")
        self.sully_trend_30d.set_value(f"{arrow30} {t30d_pct:+.1f}%")
        self.sully_trend_30d.set_color("#72d6a0" if t30d == "Rising" else ("#ff7777" if t30d == "Declining" else "#ffaa00"))
        logger.debug(f"TREND_30D metric: {t30d}, {t30d_pct}")
        
        best = sully.get("best_day", "—") or "—"
        self.sully_best_day.set_value(best)
        logger.debug(f"BEST metric: {best}")
        
        # Followers & Chat
        followers = sully.get("follower_count", 0) or 0
        self.sully_followers.set_value(f"{followers:,}")
        logger.debug(f"FOLLOWERS metric: {followers}")
        
        fg = sully.get("follower_growth_30d")
        self.sully_follower_growth.set_value(f"{fg:+.1f}%" if fg is not None else "—")
        self.sully_follower_growth.set_color("#72d6a0" if (fg or 0) > 0 else ("#ff7777" if (fg or 0) < 0 else "#f2f2f2"))
        logger.debug(f"FOLLOWER_GROWTH metric: {fg}")
        
        chat = sully.get("chat_activity", "—")
        self.sully_chat.set_value(chat)
        chat_color = "#72d6a0" if chat == "High" else ("#ffaa00" if chat == "Medium" else "#6b6b80")
        self.sully_chat.set_color(chat_color)
        logger.debug(f"CHAT metric: {chat}")
        
        # Score bars
        cons = sully.get("consistency_score", 0)
        self.sully_consistency_bar.set_value(cons)
        logger.debug(f"CONSISTENCY metric: {cons}")
        
        rel = sully.get("reliability_score", 0)
        self.sully_reliability_bar.set_value(rel)
        logger.debug(f"RELIABILITY metric: {rel}")
        
        disc = sully.get("discovery_score", 0)
        self.sully_discovery_bar.set_value(disc)
        logger.debug(f"DISCOVERY metric: {disc}")
        
        score = analysis.get("score", 0) if analysis else 0
        self.sully_score_bar.set_value(score)
        self.sully_score_bar.set_format(f"★ {int(score)} / 100")
        logger.debug(f"SCORE metric: {score}")
        
        # 2. Then enhance with trend data if available
        if trend_data:
            self._apply_trend_visualization(trend_data)
    
    def _apply_trend_visualization(self, trend_data):
        """Apply visual enhancements based on trend status"""
        status = trend_data.get('status', 'STABLE')
        score = trend_data.get('score', 50)
        
        # Color coding scheme
        COLORS = {
            'EXPLODING': ('#00ff00', '🚀'),   # Bright green + rocket
            'RISING': ('#72d6a0', '📈'),     # Light green + chart
            'STABLE': ('#00d4ff', ''),        # Cyan (no icon)
            'DECLINING': ('#ffaa00', '📉'),   # Orange + down chart
            'DROPPING': ('#ff7777', '⚠️')     # Red + warning
        }
        
        color, icon = COLORS.get(status, COLORS['STABLE'])
        
        # Update title with trend indicator
        self.title.setStyleSheet(f"color: {color};")
        self.trend_indicator.setText(icon)
        self.trend_indicator.setStyleSheet(f"color: {color};")
        
        # Update trend meter
        self.trend_meter.setValue(int(score))
        self.trend_meter.setStyleSheet(f"""
            QProgressBar {{
                background-color: #1a1a2e;
                border: 0px;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """)
        
        # Enhance key metrics with trend signals
        self._enhance_metric_with_trend("sully_avg", trend_data)
        self._enhance_metric_with_trend("sully_growth", trend_data)
        self._enhance_metric_with_trend("sully_trend_7d", trend_data)
    
    def _enhance_metric_with_trend(self, attr_name, trend_data):
        """Add subtle trend indicators to existing metrics"""
        cell = getattr(self, attr_name, None)
        if not cell:
            return
            
        status = trend_data.get('status', 'STABLE')
        
        # Viewer count gets special treatment
        if attr_name == "sully_avg":
            current_text = cell.value_label.text()
            # Add rocket to exploding channels
            if status == "EXPLODING" and "🚀" not in current_text:
                cell.value_label.setText(f"🚀 {current_text}")
            cell.value_label.setStyleSheet(
                f"color: {self._get_trend_color(status)}; font-size: 11px; font-weight: bold;"
            )
        
        # Growth metric color adjustment
        elif attr_name == "sully_growth":
            growth = trend_data.get('viewer_growth', 0)
            color = "#72d6a0" if growth > 0 else ("#ff7777" if growth < 0 else "#f2f2f2")
            cell.set_color(color)
            
        # 7-day trend gets double enhancement
        elif attr_name == "sully_trend_7d":
            current_text = cell.value_label.text()
            # Replace arrow with more expressive icon
            if status in ["EXPLODING", "DROPPING"]:
                new_arrow = "🚀" if status == "EXPLODING" else "⚠️"
                cell.value_label.setText(
                    re.sub(r'[↑→↓]', new_arrow, current_text)
                )
    
    def _get_trend_color(self, status):
        """Get appropriate color for trend status"""
        COLORS = {
            'EXPLODING': '#00ff00',
            'RISING': '#72d6a0',
            'STABLE': '#00d4ff',
            'DECLINING': '#ffaa00',
            'DROPPING': '#ff7777'
        }
        return COLORS.get(status, '#00d4ff')
    
    def _clear(self):
        for attr in [
            "sully_avg", "sully_peak", "sully_growth", "sully_rank",
            "sully_freq", "sully_duration", "sully_start", "sully_end",
            "sully_games", "sully_main", "sully_followers",
            "sully_follower_growth", "sully_chat",
            "sully_trend_7d", "sully_trend_30d", "sully_best_day",
        ]:
            cell = getattr(self, attr, None)
            if cell:
                cell.set_value("—")
                cell.set_color("#f2f2f2")
        
        for attr in [
            "sully_consistency_bar", "sully_reliability_bar",
            "sully_discovery_bar", "sully_score_bar",
        ]:
            bar = getattr(self, attr, None)
            if bar:
                bar.set_value(0)
                bar.set_format("—")
        
        # Clear trend indicators
        self.trend_indicator.setText("")
        self.trend_meter.setValue(0)