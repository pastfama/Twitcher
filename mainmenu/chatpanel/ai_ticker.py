"""AI Insight Ticker — scrolling feed of AI-generated stream observations.

Sits below the metrics dashboard and shows brief, actionable insights
that update every refresh cycle. Uses Semantic Kernel (with fallback)
to generate sportscaster-style commentary on the stream's performance.
"""

from collections import deque
from typing import Dict, Any, Optional
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QFont, QColor, QPainter, QLinearGradient
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QGraphicsOpacityEffect
from logger import debug


class _TickerLabel(QLabel):
    """A label with fade-in animation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 0.0
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(400)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def fade_in(self, text: str, color: str = "#8b93ad"):
        """Show text with a fade-in animation."""
        self.setText(text)
        self.setStyleSheet(f"""
            color: {color};
            font-size: 10px;
            font-style: italic;
            font-family: 'Segoe UI';
            padding: 2px 8px;
            background: transparent;
        """)
        self._fade_anim.stop()
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def fade_out(self):
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()


class AIInsightTicker(QWidget):
    """A compact ticker that displays AI-generated insights.

    Features:
    - Rotates through queued insights every few seconds
    - Fades between insights with smooth animation
    - Colors insights based on mood (positive=green, negative=red)
    - Auto-generates new insights from metrics data
    - Azure AI connection status indicator
    - Prioritizes Azure insights over local ones
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)

        self._insights: deque = deque(maxlen=10)
        self._azure_insights: deque = deque(maxlen=5)  # Separate queue for Azure insights
        self._current_index = 0
        self._accent_color = "#00ffff"
        self._last_metrics: Dict[str, Any] = {}
        self._azure_status = "idle"  # idle, connecting, connected, error

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)

        # Azure status indicator (small dot)
        self._azure_dot = QLabel("●")
        self._azure_dot.setFixedWidth(12)
        self._azure_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._azure_dot.setStyleSheet("color: #445566; font-size: 8px; background: transparent;")
        layout.addWidget(self._azure_dot)

        # AI icon
        self._icon = QLabel("🤖")
        self._icon.setFixedWidth(20)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet("font-size: 12px; background: transparent;")
        layout.addWidget(self._icon)

        # Insight label (fades between insights)
        self._label = _TickerLabel(self)
        layout.addWidget(self._label, 1)

        # Rotate timer — cycles through insights
        self._rotate_timer = QTimer(self)
        self._rotate_timer.setInterval(5000)  # 5 seconds per insight
        self._rotate_timer.timeout.connect(self._rotate_insight)
        self._rotate_timer.start()

        # Generate timer — requests new AI insights periodically
        self._generate_timer = QTimer(self)
        self._generate_timer.setInterval(20000)  # every 20 seconds
        self._generate_timer.timeout.connect(self._request_insight)
        self._generate_timer.start()

        # Show initial placeholder
        self._label.fade_in("AI analyzing stream...", "#4a5a7a")

    def update_metrics(self, metrics: Dict[str, Any]):
        """Receive new metrics data and generate insights."""
        self._last_metrics = metrics
        # Only generate local insights if no Azure insights queued
        if not self._azure_insights:
            self._generate_local_insights(metrics)

    def set_accent_color(self, color: str):
        """Update accent color (called by mood engine)."""
        self._accent_color = color

    def add_insight(self, text: str, color: str = "", is_azure: bool = False):
        """Manually add an insight to the queue.
        
        Args:
            text: Insight text
            color: Text color
            is_azure: If True, prioritized over local insights
        """
        if not text:
            return
        c = color or self._accent_color
        
        if is_azure:
            self._azure_insights.append((text, c))
            self._update_azure_status("connected")
        else:
            self._insights.append((text, c))
        
        # Show Azure insights immediately (they take priority)
        if is_azure and len(self._azure_insights) == 1:
            self._show_azure_insight()

    def _rotate_insight(self):
        """Show the next insight, prioritizing Azure insights."""
        # Azure insights take priority
        if self._azure_insights:
            self._show_azure_insight()
            return
        
        if not self._insights:
            return
        self._current_index = (self._current_index + 1) % len(self._insights)
        self._show_insight(self._current_index)

    def _show_insight(self, index: int):
        """Fade in the insight at the given index."""
        if 0 <= index < len(self._insights):
            text, color = self._insights[index]
            self._label.fade_in(text, color)

    def _show_azure_insight(self):
        """Show the next Azure insight (takes priority)."""
        if self._azure_insights:
            text, color = self._azure_insights.popleft()
            self._label.fade_in(f"✨ {text}", color)

    def _generate_local_insights(self, m: Dict[str, Any]):
        """Generate quick local insights from metrics (no AI call)."""
        insights = []

        # Viewer velocity
        vel = m.get("velocity", 0)
        if vel > 20:
            insights.append(("📈 Viewers surging: +" + f"{vel:.0f}/min — momentum is real!", "#00ff88"))
        elif vel < -15:
            insights.append(("📉 Losing viewers: " + f"{vel:.0f}/min — consider switching content", "#ff7777"))

        # Chat activity
        rate = m.get("chat_rate", 0)
        if rate > 30:
            insights.append(("💬 Chat is flying: " + f"{rate:.0f} msgs/min — engagement is through the roof!", "#00ffff"))
        elif rate < 2 and m.get("viewers", 0) > 100:
            insights.append(("🔇 Chat is quiet for " + f"{m.get('viewers', 0):,} viewers — try asking a question", "#ffaa00"))

        # Sentiment
        sent = m.get("sentiment", 0)
        if sent > 50:
            insights.append(("🔥 Chat mood is HYPE — energy levels are off the charts!", "#ff3366"))
        elif sent < -30:
            insights.append(("⚠️ Chat sentiment is negative — might want to address the vibe", "#ffaa00"))

        # Bounce rate
        bounce = m.get("bounce_rate", 0)
        if bounce > 60:
            insights.append(("🚪 High bounce rate: " + f"{bounce}% — viewers aren't sticking around", "#ff7777"))

        # Title quality
        title = m.get("title_score", 50)
        if title < 40:
            insights.append(("📝 Title quality is low (" + f"{title}/100) — try adding excitement or keywords", "#ffaa00"))

        # Loyalty
        loyalty = m.get("loyalty", 50)
        if loyalty > 80:
            insights.append(("❤️ Audience loyalty at " + f"{loyalty}% — you've built a solid community!", "#00ff88"))

        # Monetization
        money = m.get("monetization", 30)
        if money > 70:
            insights.append(("💰 Monetization potential is HIGH (" + f"{money}/100) — great time for sub goals!", "#ffaa00"))

        # Add generated insights
        for text, color in insights:
            self.add_insight(text, color)

    def _request_insight(self):
        """Request a new AI-generated insight from Azure (runs in background)."""
        if not self._last_metrics:
            return

        # Prevent overlapping requests
        if getattr(self, '_ai_busy', False):
            return
        self._ai_busy = True
        self._update_azure_status("connecting")

        import threading
        metrics = dict(self._last_metrics)

        def bg_generate():
            try:
                from core.sk_engine import generate_insight
                insight = generate_insight(metrics)
                if insight:
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(0, lambda: self.add_insight(insight, self._accent_color, is_azure=True))
                else:
                    self._update_azure_status("error")
            except Exception as e:
                debug(f"[AI_TICKER] Azure insight error: {e}")
                self._update_azure_status("error")
            finally:
                self._ai_busy = False

        threading.Thread(target=bg_generate, daemon=True).start()

    def _update_azure_status(self, status: str):
        """Update the Azure connection status indicator."""
        self._azure_status = status
        colors = {
            "idle": "#445566",
            "connecting": "#ffaa00",
            "connected": "#00ff88",
            "error": "#ff4466",
        }
        color = colors.get(status, "#445566")
        # Update on GUI thread
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._azure_dot.setStyleSheet(
            f"color: {color}; font-size: 8px; background: transparent;"
        ))

    def _on_ai_insight_ready(self, insight: str):
        """Called on UI thread when AI insight is ready."""
        self.add_insight(insight, self._accent_color)