"""SullyGoose analytics widget — metric grid for stream panels.

Displays streamer performance data scraped from sullygnome.com by the
``SullyGooseAPI`` and delivered through the ``AnalyticsEngine``.

Supports two size variants via ``SizeVariant``:
    M (Medium) — 17 metric cells (3×6 grid) + 4 score bars
    S (Small)  — 5 metric cells (1 row)   + 2 score bars

Size Constants (M, exported for backward compat):
    METRIC_CELL_HEIGHT = 36
    SCORE_BAR_WIDTH    = 52
    SCORE_BAR_HEIGHT   = 32
    PANEL_MIN_WIDTH    = 280

Usage::

    # M size (default, for Current Watching panel)
    widget = SullyGooseWidget()

    # S size (for side panels, live-followed rows)
    widget = SullyGooseWidget(size=SizeVariant.S)

    widget.update_metrics(sully_data, analysis)
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
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

from widgets.base import (
    SizeVariant, WidgetMetrics, SizedWidget,
    SG_M_METRICS, SG_M_BARS, SG_S_METRICS, SG_S_BARS,
)

# Backward-compat exports (M size defaults)
METRIC_CELL_HEIGHT = 36
SCORE_BAR_WIDTH = 52
SCORE_BAR_HEIGHT = 32
PANEL_MIN_WIDTH = 280


class MetricCell(QWidget):
    """Compact metric cell with title and large value."""

    def __init__(self, title="", value="—", height=36, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(0)

        font_size = 8 if height < 30 else 9
        val_size = 10 if height < 30 else 11

        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Segoe UI", font_size, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #6b6b80;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.value_label = QLabel(str(value))
        self.value_label.setFont(QFont("Segoe UI", val_size, QFont.Weight.Bold))
        self.value_label.setStyleSheet("color: #00d4ff;")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value):
        self.value_label.setText(str(value))

    def set_color(self, color_hex):
        sz = self.value_label.font().pointSize()
        self.value_label.setStyleSheet(
            f"color: {color_hex}; font-size: {sz}px; font-weight: bold;"
        )


class ScoreBar(QWidget):
    """Labeled progress bar for SullyGoose scores."""

    def __init__(self, label_text="", width=52, height=32, parent=None):
        super().__init__(parent)
        self.setFixedWidth(width)
        self.setFixedHeight(height)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        bar_height = 10 if height < 28 else 12
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(True)
        self.bar.setFixedHeight(bar_height)
        self.bar.setStyleSheet(self._style())
        layout.addWidget(self.bar)

        lbl = QLabel(label_text)
        lbl.setFont(QFont("Segoe UI", 7 if height < 28 else 8, QFont.Weight.Bold))
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


class SullyGooseWidget(QFrame, SizedWidget):
    """SullyGoose analytics grid with score bars.

    Supports M (Medium) and S (Small) size variants:
        M: 17 metric cells + 4 score bars (full panel)
        S: 5 metric cells  + 2 score bars (compact sidebar)
    """

    def __init__(self, parent=None, size=SizeVariant.M):
        super().__init__(parent)
        self._init_metrics(size)
        m = self._metrics

        self.setObjectName("sullygoosePanel")
        self.setStyleSheet(
            "QFrame#sullygoosePanel {"
            "  background-color: #12121c;"
            "  border: 1px solid #29293d;"
            "  border-radius: 3px;"
            "}"
        )
        self.setMinimumWidth(m.sg_panel_min_width)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        main = QVBoxLayout(self)
        main.setContentsMargins(4, 3, 4, 3)
        main.setSpacing(2)

        # Title
        title = QLabel("◆ SULLYGOOSE ◆")
        title.setFont(QFont("Segoe UI", 8 if size == SizeVariant.S else 9, QFont.Weight.Bold))
        title.setStyleSheet("color: #00d4ff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main.addWidget(title)

        # Metric grid — dynamic rows based on variant
        if size == SizeVariant.M:
            metrics_list = SG_M_METRICS
            bars_list = SG_M_BARS
            cols = m.sg_grid_cols
        else:
            metrics_list = SG_S_METRICS
            bars_list = SG_S_BARS
            cols = m.sg_grid_cols

        grid = QGridLayout()
        grid.setSpacing(2)

        self._cells = {}
        for idx, (title_text, attr) in enumerate(metrics_list):
            cell = MetricCell(title_text, height=m.sg_cell_height)
            setattr(self, attr, cell)
            self._cells[attr] = cell
            grid.addWidget(cell, idx // cols, idx % cols)

        main.addLayout(grid)

        # Score bars
        bars = QHBoxLayout()
        bars.setSpacing(2)

        self._bars = {}
        for attr, text in bars_list:
            bar = ScoreBar(text, width=m.sg_score_bar_width, height=m.sg_score_bar_height)
            bars.addWidget(bar)
            setattr(self, attr, bar)
            self._bars[attr] = bar

        main.addLayout(bars)

    def update_metrics(self, sully, analysis=None):
        if not sully:
            self._clear()
            return

        # Viewers
        self._set_cell("sully_avg", f"{sully.get('avg_viewers', 0):,}")
        self._set_cell("sully_peak", f"{sully.get('peak_viewers', 0):,}")

        # Growth & Rank
        growth = sully.get("viewer_growth") or 0
        self._set_cell("sully_growth", f"{growth:+.1f}%")
        self._set_cell_color("sully_growth",
            "#72d6a0" if growth > 0 else ("#ff7777" if growth < 0 else "#f2f2f2"))

        rank = sully.get("category_rank") or 0
        self._set_cell("sully_rank", f"#{rank}")

        # Followers (always shown in both M and S)
        followers = sully.get("follower_count", 0)
        self._set_cell("sully_followers", f"{followers:,}")

        # --- M-only cells ---
        if self.size_variant == SizeVariant.M:
            freq = sully.get("stream_frequency") or 0
            self._set_cell("sully_freq", f"{freq:.0f}h/wk")

            dur = sully.get("avg_stream_duration", 0)
            self._set_cell("sully_duration", f"{dur:.1f}h")

            start_h = sully.get("typical_start_hour") or 0
            end_h = sully.get("typical_end_hour") or 0
            self._set_cell("sully_start", f"{start_h:02d}:00")
            self._set_cell("sully_end", f"{end_h:02d}:00")

            games = sully.get("games_played_30d", 0)
            self._set_cell("sully_games", str(games))

            main_pct = sully.get("main_game_pct")
            self._set_cell("sully_main", f"{main_pct}%" if main_pct is not None else "—")

            raid = sully.get("raid_frequency")
            self._set_cell("sully_raid", f"{raid}%" if raid is not None else "—")

            fg = sully.get("follower_growth_30d")
            self._set_cell("sully_follower_growth", f"{fg:+.1f}%" if fg is not None else "—")
            self._set_cell_color("sully_follower_growth",
                "#72d6a0" if (fg or 0) > 0 else ("#ff7777" if (fg or 0) < 0 else "#f2f2f2"))

            chat = sully.get("chat_activity", "—")
            self._set_cell("sully_chat", chat)
            chat_color = "#72d6a0" if chat == "High" else ("#ffaa00" if chat == "Medium" else "#6b6b80")
            self._set_cell_color("sully_chat", chat_color)

            # Trends
            t7d = sully.get("trend_7d", "Stable")
            t7d_pct = sully.get("trend_7d_pct", 0)
            arrow7 = "↗" if t7d == "Rising" else ("↘" if t7d == "Declining" else "→")
            self._set_cell("sully_trend_7d", f"{arrow7} {t7d_pct:+.1f}%")
            self._set_cell_color("sully_trend_7d",
                "#72d6a0" if t7d == "Rising" else ("#ff7777" if t7d == "Declining" else "#ffaa00"))

            t30d = sully.get("trend_30d", "Stable")
            t30d_pct = sully.get("trend_30d_pct", 0)
            arrow30 = "↗" if t30d == "Rising" else ("↘" if t30d == "Declining" else "→")
            self._set_cell("sully_trend_30d", f"{arrow30} {t30d_pct:+.1f}%")
            self._set_cell_color("sully_trend_30d",
                "#72d6a0" if t30d == "Rising" else ("#ff7777" if t30d == "Declining" else "#ffaa00"))

            best = sully.get("best_day", "—")
            self._set_cell("sully_best_day", best)

        # Score bars
        self._set_bar("sully_consistency_bar", sully.get("consistency_score", 0))
        self._set_bar("sully_reliability_bar", sully.get("reliability_score", 0))
        self._set_bar("sully_discovery_bar", sully.get("discovery_score", 0))

        score = analysis.get("score", 0) if analysis else 0
        self._set_bar("sully_score_bar", score)
        if "sully_score_bar" in self._bars:
            self._bars["sully_score_bar"].set_format(f"★ {int(score)} / 100")

    def _set_cell(self, attr, value):
        cell = self._cells.get(attr) or getattr(self, attr, None)
        if cell:
            cell.set_value(value)

    def _set_cell_color(self, attr, color_hex):
        cell = self._cells.get(attr) or getattr(self, attr, None)
        if cell:
            cell.set_color(color_hex)

    def _set_bar(self, attr, value):
        bar = self._bars.get(attr) or getattr(self, attr, None)
        if bar:
            bar.set_value(value)

    def _clear(self):
        for cell in self._cells.values():
            cell.set_value("—")
            cell.set_color("#f2f2f2")
        # Also clear any cells set via setattr (M-only)
        for attr in [
            "sully_avg", "sully_peak", "sully_growth", "sully_rank",
            "sully_freq", "sully_duration", "sully_start", "sully_end",
            "sully_games", "sully_main", "sully_raid", "sully_followers",
            "sully_follower_growth", "sully_chat",
            "sully_trend_7d", "sully_trend_30d", "sully_best_day",
        ]:
            cell = getattr(self, attr, None)
            if cell and hasattr(cell, "set_value"):
                cell.set_value("—")
                cell.set_color("#f2f2f2")

        for bar in self._bars.values():
            bar.set_value(0)
        for attr in [
            "sully_consistency_bar", "sully_reliability_bar",
            "sully_discovery_bar", "sully_score_bar",
        ]:
            bar = getattr(self, attr, None)
            if bar and hasattr(bar, "set_value"):
                bar.set_value(0)
                bar.set_format("—")