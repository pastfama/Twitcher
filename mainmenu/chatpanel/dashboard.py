"""Metrics Dashboard — 36-metric tabbed dashboard with mood-reactive theming.

Replaces the old 10-cell metric row in the ChatPanel with a rich,
tabbed dashboard featuring gauges, LCD numbers, sparklines, progress
bars, neon indicators, and styled labels.
"""

from typing import Dict, List, Optional, Any
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QStackedWidget, QGraphicsDropShadowEffect,
)

from logger import debug
from .mood_engine import MoodEngine, MoodPalette, MOODS
from .dashboard_widgets import (
    LCDMetric, GaugeMetric, ProgressMetric, SparklineMetric,
    NeonMetric, LabelMetric, TabButton,
)
from .ai_ticker import AIInsightTicker


# ── Category definitions ────────────────────────────────────────────────
# Each category: (tab_id, emoji_label, list of (metric_key, widget_type, caption))

CATEGORIES = [
    ("viewers", "👁 VIEWERS", [
        ("viewers",      "lcd",       "Watching Now",
         "Current number of people watching this stream right now"),
        ("session_peak", "lcd",       "Peak Viewers",
         "Highest viewer count reached during this stream session"),
        ("session_avg",  "lcd",       "Average Viewers",
         "Average viewer count across this entire stream session"),
        ("velocity",     "sparkline", "Viewer Trend",
         "Are viewers arriving (+) or leaving (−)? Trend over last few minutes"),
        ("volatility",   "gauge",     "Stability",
         "How stable the viewer count is — high = lots of coming and going"),
        ("unique_est",   "lcd",       "Unique Viewers",
         "Estimated total unique people who have watched this stream"),
    ]),
    ("engage", "💬 CHAT & ENGAGEMENT", [
        ("chat_rate",    "sparkline", "Messages/Min",
         "How many chat messages are being sent per minute — higher = more active chat"),
        ("chat_density", "gauge",     "Chat Activity",
         "Chat messages relative to viewer count — 100% means very active for the audience size"),
        ("emote_ratio",  "progress",  "Emote Usage",
         "Percentage of messages that contain emotes — higher = more expressive chat"),
        ("sentiment",    "gauge",     "Chat Mood",
         "Overall mood of the chat — green/positive, red/negative, based on message content"),
        ("avg_msg_len",  "lcd",       "Msg Length",
         "Average character length of chat messages — longer = more thoughtful discussion"),
        ("new_chatters", "lcd",       "New Voices",
         "Number of people chatting for the first time this session"),
    ]),
    ("content", "📺 STREAM CONTENT", [
        ("cat_rank",     "lcd",       "Category Rank",
         "Estimated ranking position within the current game/category"),
        ("duration",     "label",     "Stream Length",
         "How long this stream has been running (hours and minutes)"),
        ("game_changes", "lcd",       "Game Switches",
         "How many times the streamer changed game/category this session"),
        ("title_score",  "gauge",     "Title Quality",
         "How engaging the stream title is (length, excitement, keywords) — 0 to 100"),
        ("tag_score",    "progress",  "Tag Match",
         "How well the stream tags match the actual content — better tags = more discoverable"),
        ("freshness",    "lcd",       "Last Change",
         "Minutes since the streamer last switched game or category"),
    ]),
    ("growth", "📈 GROWTH & REACH", [
        ("follow_rate",       "lcd",       "Follows/Hr",
         "Estimated new followers per hour — higher means the stream is attracting new fans"),
        ("growth_trajectory", "sparkline", "1hr Forecast",
         "Projected viewer count in 1 hour based on current growth trend"),
        ("loyalty",           "progress",  "Loyalty",
         "Percentage of viewers who are returning regulars vs first-time visitors"),
        ("discovery",         "gauge",     "Discoverability",
         "How easy it is for new viewers to find this stream (title + tags + viewers)"),
        ("raid_potential",    "neon",      "Raid Ready",
         "Likelihood of receiving a raid from another streamer — based on timing and audience"),
        ("network_effect",    "gauge",     "Network",
         "Cross-platform presence and community connections — higher = broader reach"),
    ]),
    ("perform", "⚡ PERFORMANCE", [
        ("bounce_rate",   "gauge",     "Bounce Rate",
         "Estimated percentage of viewers who leave within 5 minutes — lower is better"),
        ("session_depth", "progress",  "Watch Time",
         "Average estimated watch time per viewer in minutes — deeper = more engaged"),
        ("peak_efficiency","sparkline", "Viewers/Hr",
         "Viewers gained per hour of streaming — measures growth efficiency"),
        ("consistency",   "progress",  "Consistency",
         "How consistent this stream's schedule is compared to past streams"),
        ("uptime_score",  "gauge",     "Stream Health",
         "Technical stream stability — drops, buffering, connection quality"),
        ("stream_health", "gauge",     "Overall Health",
         "Combined score of all performance factors — the big picture number"),
    ]),
    ("ai", "🤖 AI INSIGHTS", [
        ("competitive_index", "gauge",  "Competitive",
         "How this stream compares to its own average — above 50 means outperforming"),
        ("audience_match",    "gauge",  "Audience Fit",
         "How well the current content matches what the audience expects (0-100)"),
        ("monetization",      "gauge",  "$ Potential",
         "Revenue potential score based on audience loyalty, engagement, and sentiment"),
        ("overall_rank",      "label",  "Grade",
         "Overall stream grade from A+ (exceptional) to F (needs work)"),
        ("agent_calls",       "lcd",    "AI Calls",
         "Total Azure AI API calls made this session — shows how busy the agent is"),
        ("agent_latency",     "lcd",    "AI Latency",
         "Average Azure AI response time in milliseconds — lower is better"),
    ]),
]


class _GradientBackground(QWidget):
    """Widget that paints a vertical gradient background."""

    def __init__(self, start: str = "#080c1a", end: str = "#0a0d18",
                 parent=None):
        super().__init__(parent)
        self._start = QColor(start)
        self._end = QColor(end)

    def set_gradient(self, start: str, end: str):
        self._start = QColor(start)
        self._end = QColor(end)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, self._start)
        grad.setColorAt(1.0, self._end)
        p.fillRect(self.rect(), grad)
        p.end()


class MetricsDashboard(QWidget):
    """Tabbed 36-metric dashboard with mood-reactive theming.

    Usage::

        dashboard = MetricsDashboard()
        dashboard.update_metrics(metrics_dict)
        # mood engine drives palette changes automatically
    """

    def __init__(self, mood_engine: Optional[MoodEngine] = None,
                 parent=None):
        super().__init__(parent)
        self._mood_engine = mood_engine or MoodEngine()
        self._pal = self._mood_engine.current_palette
        self._widgets: Dict[str, Any] = {}  # metric_key → widget
        self._sparklines: Dict[str, SparklineMetric] = {}
        self._tabs: Dict[str, TabButton] = {}
        self._current_tab = "viewers"
        self._sentiment_history: List[float] = []

        self._build_ui()
        self._connect_mood()

    # ── UI construction ─────────────────────────────────────────────────

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Gradient background container
        self._bg = _GradientBackground(
            self._pal.bg_start, self._pal.bg_end
        )
        bg_layout = QVBoxLayout(self._bg)
        bg_layout.setContentsMargins(4, 4, 4, 4)
        bg_layout.setSpacing(2)

        # Tab bar
        tab_bar = QHBoxLayout()
        tab_bar.setSpacing(0)
        tab_bar.setContentsMargins(0, 0, 0, 2)

        for cat_id, label, _ in CATEGORIES:
            btn = TabButton(label, cat_id, self._pal, self)
            btn.set_active(cat_id == self._current_tab)
            self._tabs[cat_id] = btn
            tab_bar.addWidget(btn)

        # Mood indicator (right-aligned)
        self._mood_label = QLabel(f"{self._pal.emoji} {self._pal.name}")
        self._mood_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._mood_label.setStyleSheet(self._mood_style())
        tab_bar.addWidget(self._mood_label, 1)

        bg_layout.addLayout(tab_bar)

        # Stacked widget for category pages
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")

        for cat_id, label, metrics in CATEGORIES:
            page = self._build_category_page(cat_id, metrics)
            self._stack.addWidget(page)

        bg_layout.addWidget(self._stack)

        # AI Insight Ticker
        self.ticker = AIInsightTicker(self)
        bg_layout.addWidget(self.ticker)

        # Set the background widget as the sole child
        main.addWidget(self._bg)

        # Set fixed height for dashboard
        self.setFixedHeight(164)

    def _build_category_page(self, cat_id: str,
                              metrics: list) -> QWidget:
        """Build a 3×2 grid page for one category."""
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        grid = QGridLayout(page)
        grid.setContentsMargins(2, 2, 2, 2)
        grid.setSpacing(4)

        for idx, entry in enumerate(metrics):
            row, col = divmod(idx, 3)
            metric_key = entry[0]
            wtype = entry[1]
            caption = entry[2]
            tooltip = entry[3] if len(entry) > 3 else ""
            widget = self._create_metric_widget(metric_key, wtype, caption)
            if tooltip:
                widget.setToolTip(tooltip)
            self._widgets[metric_key] = widget
            if wtype == "sparkline":
                self._sparklines[metric_key] = widget
            grid.addWidget(widget, row, col)

        return page

    def _create_metric_widget(self, key: str, wtype: str,
                               caption: str) -> QWidget:
        """Factory dispatch."""
        if wtype == "lcd":
            return LCDMetric(caption, palette=self._pal)
        elif wtype == "gauge":
            return GaugeMetric(caption, palette=self._pal)
        elif wtype == "progress":
            return ProgressMetric(caption, palette=self._pal)
        elif wtype == "sparkline":
            return SparklineMetric(caption, palette=self._pal)
        elif wtype == "neon":
            return NeonMetric(caption, palette=self._pal)
        elif wtype == "label":
            return LabelMetric(caption, palette=self._pal)
        else:
            return LCDMetric(caption, palette=self._pal)

    # ── Tab switching ───────────────────────────────────────────────────

    def switch_tab(self, tab_id: str):
        """Switch to a different category tab and generate AI commentary."""
        if tab_id not in self._tabs:
            return
        # Deactivate old tab
        if self._current_tab in self._tabs:
            self._tabs[self._current_tab].set_active(False)
        # Activate new tab
        self._current_tab = tab_id
        self._tabs[tab_id].set_active(True)
        # Switch stacked page
        cat_ids = [c[0] for c in CATEGORIES]
        idx = cat_ids.index(tab_id) if tab_id in cat_ids else 0
        self._stack.setCurrentIndex(idx)

        # Generate AI commentary for this tab's metrics
        self._generate_tab_commentary(tab_id)

    # ── Data update ─────────────────────────────────────────────────────

    def update_metrics(self, data: Dict[str, Any]):
        """Update all 36 metric widgets with new data.

        Args:
            data: Dict from ``AIAnalyticsEngine.analyze_dashboard_metrics()``
        """
        if not data:
            return

        # Cache for tab commentary
        self._cached_metrics = data

        # Update mood from sentiment
        sentiment = data.get("sentiment", data.get("sentiment_raw", 0.0))
        self._mood_engine.update_sentiment(sentiment)

        # Feed metrics to AI ticker for insights
        self.ticker.update_metrics(data)
        self.ticker.set_accent_color(self._pal.accent)

        # Viewer dynamics
        self._set_lcd("viewers", data.get("viewers", 0), "int")
        self._set_lcd("session_peak", data.get("session_peak", 0), "int")
        self._set_lcd("session_avg", data.get("session_avg", 0), "int")
        self._add_sparkle("velocity", data.get("velocity", 0.0))
        self._set_gauge("volatility", data.get("volatility", 0.0))
        self._set_lcd("unique_est", data.get("unique_est", 0), "int")

        # Engagement
        self._add_sparkle("chat_rate", data.get("chat_rate", 0.0))
        self._set_gauge("chat_density", min(100, data.get("chat_density", 0.0)))
        self._set_progress("emote_ratio", int(data.get("emote_ratio", 0)))
        self._set_gauge_from_sentiment("sentiment", data.get("sentiment", 0.0))
        self._set_lcd("avg_msg_len", data.get("avg_msg_len", 0.0), "float1")
        self._set_lcd("new_chatters", data.get("new_chatters", 0), "int")

        # Content
        self._set_lcd("cat_rank", data.get("cat_rank", 1), "int")
        self._set_label("duration", str(data.get("duration", "0h 0m")))
        self._set_lcd("game_changes", data.get("game_changes", 0), "int")
        self._set_gauge("title_score", data.get("title_score", 0))
        self._set_progress("tag_score", int(data.get("tag_score", 0)))
        self._set_lcd("freshness", data.get("freshness", 0), "int")

        # Growth
        self._set_lcd("follow_rate", data.get("follow_rate", 0.0), "float1")
        self._add_sparkle("growth_trajectory", data.get("growth_trajectory", 0))
        self._set_progress("loyalty", int(data.get("loyalty", 50)))
        self._set_gauge("discovery", data.get("discovery", 0))
        self._set_neon("raid_potential", data.get("raid_potential", 0) > 50,
                        f"{'● HIGH' if data.get('raid_potential', 0) > 50 else '● LOW'}")
        self._set_gauge("network_effect", data.get("network_effect", 50))

        # Performance
        self._set_gauge("bounce_rate", data.get("bounce_rate", 50))
        self._set_progress("session_depth", min(100, int(data.get("session_depth", 0))))
        self._add_sparkle("peak_efficiency", data.get("peak_efficiency", 0.0))
        self._set_progress("consistency", int(data.get("consistency", 60)))
        self._set_gauge("uptime_score", data.get("uptime_score", 95))
        self._set_gauge("stream_health", data.get("stream_health", 50))

        # AI Insights
        self._set_gauge("competitive_index", data.get("competitive_index", 50))
        self._set_gauge("audience_match", data.get("audience_match", 65))
        self._set_gauge("monetization", data.get("monetization", 30))
        self._set_label("overall_rank", str(data.get("overall_rank", "—")))

        # Agent activity stats
        self._update_agent_stats()

        # Generate AI commentary for current tab (throttled)
        self._maybe_generate_periodic_commentary()

    # ── Widget helpers ──────────────────────────────────────────────────

    def _set_lcd(self, key: str, value, fmt: str = ""):
        w = self._widgets.get(key)
        if isinstance(w, LCDMetric):
            w.set_value(value, fmt)

    def _set_gauge(self, key: str, value: float):
        w = self._widgets.get(key)
        if isinstance(w, GaugeMetric):
            w.set_value(float(value))

    def _set_gauge_from_sentiment(self, key: str, sentiment: float):
        """Map sentiment −100…+100 to gauge 0…100."""
        normalized = max(0.0, min(100.0, (sentiment + 100) / 2.0))
        self._set_gauge(key, normalized)

    def _set_progress(self, key: str, value: int):
        w = self._widgets.get(key)
        if isinstance(w, ProgressMetric):
            w.set_value(value)

    def _add_sparkle(self, key: str, value: float):
        w = self._widgets.get(key)
        if isinstance(w, SparklineMetric):
            w.add_point(value)

    def _set_neon(self, key: str, active: bool, text: str = ""):
        w = self._widgets.get(key)
        if isinstance(w, NeonMetric):
            w.set_active(active, text)

    def _set_label(self, key: str, text: str):
        w = self._widgets.get(key)
        if isinstance(w, LabelMetric):
            w.set_text(text)

    # ── Mood integration ────────────────────────────────────────────────

    def _connect_mood(self):
        """Connect mood engine palette changes to recolour all widgets."""
        self._mood_engine.palette_changed.connect(self._on_palette_changed)

    def _on_palette_changed(self, pal: MoodPalette):
        """Recolour every widget and the background gradient."""
        self._pal = pal

        # Background gradient
        self._bg.set_gradient(pal.bg_start, pal.bg_end)

        # Mood label
        self._mood_label.setText(f"{pal.emoji} {pal.name}")
        self._mood_label.setStyleSheet(self._mood_style())

        # Tab buttons
        for btn in self._tabs.values():
            btn.apply_palette(pal)

        # All metric widgets
        for w in self._widgets.values():
            if hasattr(w, 'apply_palette'):
                w.apply_palette(pal)

    def _mood_style(self) -> str:
        return f"""
            color: {self._pal.accent};
            font-size: 10px;
            font-weight: bold;
            font-family: 'Segoe UI';
            padding: 2px 8px;
        """

    # ── Public API ──────────────────────────────────────────────────────

    def set_mood_engine(self, engine: MoodEngine):
        """Replace the mood engine (e.g. on channel switch)."""
        if self._mood_engine:
            try:
                self._mood_engine.palette_changed.disconnect(self._on_palette_changed)
            except Exception:
                pass
        self._mood_engine = engine
        self._connect_mood()
        # Apply current palette
        self._on_palette_changed(engine.current_palette)

    def get_mood_engine(self) -> MoodEngine:
        return self._mood_engine

    # ── Agent activity stats ────────────────────────────────────────────

    def _update_agent_stats(self):
        """Update Azure AI agent activity metrics."""
        try:
            from core.azure_ai_client import get_ai_client
            client = get_ai_client()
            if client:
                stats = client.get_agent_stats()
                self._set_lcd("agent_calls", stats.get("total_calls", 0), "int")
                self._set_lcd("agent_latency", stats.get("avg_latency_ms", 0), "int")
        except Exception:
            pass

    # ── AI Tab Commentary ───────────────────────────────────────────────

    def _generate_tab_commentary(self, tab_id: str):
        """Generate an AI comment for the current tab's metrics."""
        if not self._last_metrics:
            return

        # Prevent overlapping requests
        if getattr(self, '_tab_ai_busy', False):
            return
        self._tab_ai_busy = True

        tab_metrics = self._get_tab_metrics(tab_id)
        if not tab_metrics:
            self._tab_ai_busy = False
            return

        import threading
        metrics = dict(self._last_metrics)
        tab_label = tab_id.upper()

        def bg():
            try:
                from core.sk_engine import generate_insight
                focused = {k: v for k, v in metrics.items() if k in tab_metrics}
                insight = generate_insight(focused)
                if insight:
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(0, lambda: self.ticker.add_insight(f"[{tab_label}] {insight}", self._pal.accent))
            except Exception as e:
                debug(f"[DASHBOARD] Tab commentary error: {e}")
            finally:
                self._tab_ai_busy = False

        threading.Thread(target=bg, daemon=True).start()

    def _maybe_generate_periodic_commentary(self):
        """Periodically generate AI commentary for the active tab's metrics.
        
        Throttled to once every 30 seconds to avoid excessive API calls.
        """
        import time as _time
        now = _time.time()
        last = getattr(self, '_last_periodic_commentary', 0)
        if now - last < 30:
            return
        self._last_periodic_commentary = now
        self._generate_tab_commentary(self._current_tab)

    def _get_tab_metrics(self, tab_id: str) -> list:
        """Get the metric keys for a given tab."""
        for cat_id, _, metrics in CATEGORIES:
            if cat_id == tab_id:
                return [entry[0] for entry in metrics]
        return []

    @property
    def _last_metrics(self) -> Dict[str, Any]:
        """Return the last metrics dict that was passed to update_metrics."""
        return getattr(self, '_cached_metrics', {})
