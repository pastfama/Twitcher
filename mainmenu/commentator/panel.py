"""Commentator Panel — redesigned with VTuber avatar, streamer profile, and Azure stats.

Shows:
- VTuber avatar character with mood-reactive expressions
- Streamer profile section (avatar, name, game, viewers, duration)
- Speech bubble with AI commentary (typewriter animation)
- Azure AI connection status with full details
- Recent commentary history
"""

import time as _time
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QPixmap
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QWidget, QGridLayout,
)
from ..theme import Theme
from .character import VTuberAvatar
from .speech_bubble import SpeechBubble
from .engine import CommentaryEngine
from .avatar_generator import get_avatar_generator, MOOD_TO_EXPRESSION
from logger import debug


class CommentatorPanel(QFrame):
    """AI Commentator panel with VTuber avatar, streamer profile, and Azure stats."""

    watch_requested = Signal(str)

    def __init__(self, analytics_engine=None):
        super().__init__()
        self.setObjectName("CommentatorCard")
        self.setStyleSheet(Theme.frame_style())
        self._analytics = analytics_engine
        self._current_channel = None
        self._current_stream = None

        # Commentary engine
        self.engine = CommentaryEngine()
        self.engine.set_callback(self._on_commentary)
        self.engine.set_status_callback(self._on_status)

        # Generate avatars in background
        gen = get_avatar_generator()
        gen.generate_all_async()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # ── Title Row ──
        title_row = QHBoxLayout()
        title = QLabel("AI COMMENTATOR")
        title.setFont(QFont(Theme.FAMILY, 9, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Theme.TEAL}; letter-spacing: 1px;")
        title_row.addWidget(title)

        # Viewer count (right side)
        self._stream_info = QLabel("")
        self._stream_info.setStyleSheet(f"color: {Theme.MUTED}; font-size: 9px;")
        self._stream_info.setAlignment(Qt.AlignmentFlag.AlignRight)
        title_row.addWidget(self._stream_info, 1)
        layout.addLayout(title_row)

        # ── Azure Status ──
        self._status_label = QLabel("● IDLE")
        self._status_label.setFont(QFont(Theme.FAMILY, 7, QFont.Weight.Bold))
        self._status_label.setStyleSheet(
            f"color: {Theme.MUTED}; background: transparent; "
            f"padding: 1px 4px; font-size: 7px;"
        )
        layout.addWidget(self._status_label)

        # Blink timer
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(600)
        self._blink_timer.timeout.connect(self._blink_status)
        self._blink_visible = True

        # ── Streamer Profile Card ──
        self._profile_card = self._build_profile_card()
        layout.addWidget(self._profile_card)

        # ── Avatar + Speech Bubble ──
        char_row = QHBoxLayout()
        char_row.setSpacing(8)

        self.bot = VTuberAvatar()
        self.bot.setFixedWidth(150)
        char_row.addWidget(self.bot)

        self.bubble = SpeechBubble()
        char_row.addWidget(self.bubble, 1)
        layout.addLayout(char_row, 1)

        # ── Commentary History ──
        self._history_label = QLabel("")
        self._history_label.setWordWrap(True)
        self._history_label.setStyleSheet(
            f"color: {Theme.DIM}; font-size: 8px; padding: 2px; "
            f"border-top: 1px solid {Theme.SECTION_BORDER};"
        )
        self._history_label.setMaximumHeight(36)
        layout.addWidget(self._history_label)

        # ── Azure AI Details (expandable) ──
        self._azure_details = self._build_azure_details()
        layout.addWidget(self._azure_details)

        # Show intro after delay
        QTimer.singleShot(500, self._show_intro)

    def _build_profile_card(self) -> QWidget:
        """Build the streamer profile card."""
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: rgba(15, 21, 37, 0.8); border: 1px solid {Theme.SECTION_BORDER}; "
            f"border-radius: 6px; padding: 4px; }}"
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        # Streamer avatar (circular)
        self._streamer_avatar = QLabel()
        self._streamer_avatar.setFixedSize(48, 48)
        self._streamer_avatar.setStyleSheet(
            "border-radius: 24px; background: #1a2a4a; border: 2px solid #2a3a5a;"
        )
        self._streamer_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._streamer_avatar)

        # Streamer info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        self._streamer_name = QLabel("No streamer selected")
        self._streamer_name.setFont(QFont(Theme.FAMILY, 10, QFont.Weight.Bold))
        self._streamer_name.setStyleSheet(f"color: {Theme.TEAL};")
        info_layout.addWidget(self._streamer_name)

        self._streamer_game = QLabel("")
        self._streamer_game.setStyleSheet(f"color: {Theme.MUTED}; font-size: 9px;")
        info_layout.addWidget(self._streamer_game)

        self._streamer_stats = QLabel("")
        self._streamer_stats.setStyleSheet(f"color: {Theme.DIM}; font-size: 8px;")
        info_layout.addWidget(self._streamer_stats)

        layout.addLayout(info_layout, 1)
        return card

    def _build_azure_details(self) -> QWidget:
        """Build the Azure AI details section."""
        container = QFrame()
        container.setStyleSheet(
            f"QFrame {{ background: rgba(10, 13, 24, 0.6); border: 1px solid {Theme.SECTION_BORDER}; "
            f"border-radius: 4px; padding: 2px; }}"
        )
        layout = QGridLayout(container)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        details = [
            ("Endpoint:", "self._detail_endpoint"),
            ("Deployment:", "self._detail_deployment"),
            ("Auth:", "self._detail_auth"),
            ("Latency:", "self._detail_latency"),
            ("Calls:", "self._detail_calls"),
            ("Tokens:", "self._detail_tokens"),
        ]

        for i, (label_text, attr_name) in enumerate(details):
            row, col = divmod(i, 3)

            lbl = QLabel(label_text)
            lbl.setFont(QFont(Theme.FAMILY, 7))
            lbl.setStyleSheet(f"color: {Theme.MUTED}; font-size: 7px;")
            layout.addWidget(lbl, row * 2, col)

            val = QLabel("—")
            val.setFont(QFont(Theme.FAMILY, 7, QFont.Weight.Bold))
            val.setStyleSheet(f"color: {Theme.DIM}; font-size: 7px;")
            layout.addWidget(val, row * 2 + 1, col)
            setattr(self, attr_name.lstrip("self."), val)

        return container

    def _show_intro(self):
        self.engine.show_introduction()

    def set_analytics_engine(self, analytics):
        self._analytics = analytics

    def set_stream(self, stream):
        """Set the next stream candidate with full profile info."""
        if not stream:
            self.clear()
            return

        self._current_stream = stream
        channel = stream.get("user_login") or stream.get("user_name", "Unknown")
        viewers = int(stream.get("viewer_count", 0))
        platform = stream.get("platform", "twitch")
        self._current_channel = channel.lower()

        # Update stream info
        name = stream.get("user_name", channel)
        game = stream.get("game_name", "Unknown")
        self._stream_info.setText(f"👁 {viewers:,} viewers")

        # Update profile card
        self._update_profile(stream)

        # Update engine
        self.engine.set_channel(self._current_channel, platform)

        # Generate commentary
        self.bubble.show_loading(Theme.TEAL)
        self.engine.update_metrics({
            "viewers": viewers,
            "channel": self._current_channel,
        })
        self.engine.generate()

    def _update_profile(self, stream):
        """Update the streamer profile card with stream data."""
        try:
            name = stream.get("user_name") or stream.get("user_login") or stream.get("channel") or "Unknown"
            game = stream.get("game_name") or "Unknown"
            viewers = int(stream.get("viewer_count", 0))
            platform = stream.get("platform", "twitch")
            started_at = stream.get("started_at", "")

            debug(f"[PROFILE] Updating: {name}, {game}, {viewers} viewers, {platform}")

            # Platform badge
            platform_icons = {"twitch": "🟣", "kick": "🟢", "youtube": "🔴"}
            icon = platform_icons.get(platform, "⚪")

            self._streamer_name.setText(f"{icon} @{name}")
            self._streamer_game.setText(f"🎮 {game}")

            # Duration
            duration = ""
            if started_at:
                try:
                    from datetime import datetime, timezone
                    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    delta = now - start
                    hours = int(delta.total_seconds() // 3600)
                    minutes = int((delta.total_seconds() % 3600) // 60)
                    duration = f" · ⏱ {hours}h {minutes}m"
                except Exception:
                    pass

            self._streamer_stats.setText(f"👁 {viewers:,} viewers{duration}")

            # Try to load streamer avatar
            self._load_streamer_avatar(stream)

        except Exception as e:
            debug(f"[PROFILE] Update error: {e}")
            import traceback
            traceback.print_exc()

    def _load_streamer_avatar(self, stream):
        """Load and display the streamer's profile picture."""
        avatar_url = stream.get("avatar_url", "")
        if not avatar_url:
            # Try to get from cache
            try:
                from mainmenu.main import MainMenu
                # This is a fallback — we'll try to load asynchronously
                return
            except Exception:
                return

        # Load avatar asynchronously
        import threading

        def load():
            try:
                import urllib.request
                from PySide6.QtGui import QPixmap
                from PySide6.QtCore import QBuffer, QIODevice

                data = urllib.request.urlopen(avatar_url, timeout=5).read()
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                if not pixmap.isNull():
                    # Scale to 48x48 and make circular
                    scaled = pixmap.scaled(48, 48,
                                            Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
                    # Create circular mask
                    mask = QPixmap(48, 48)
                    mask.fill(Qt.GlobalColor.transparent)
                    from PySide6.QtGui import QPainter, QBrush
                    mask_p = QPainter(mask)
                    mask_p.setRenderHint(QPainter.RenderHint.Antialiasing)
                    mask_p.setBrush(QBrush(QColor(255, 255, 255)))
                    mask_p.setPen(Qt.PenStyle.NoPen)
                    mask_p.drawEllipse(0, 0, 48, 48)
                    mask_p.end()

                    # Apply mask
                    result = scaled.copy()
                    result.setMask(mask.mask())

                    # Update on GUI thread
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(0, lambda: self._set_streamer_avatar(result))
            except Exception as e:
                debug(f"[PROFILE] Avatar load error: {e}")

        threading.Thread(target=load, daemon=True).start()

    def _set_streamer_avatar(self, pixmap):
        """Set the streamer avatar on the GUI thread."""
        self._streamer_avatar.setPixmap(pixmap)
        self._streamer_avatar.setStyleSheet(
            "border-radius: 24px; background: transparent; border: 2px solid #2a3a5a;"
        )

    def update_commentary(self, metrics: dict, vision: str = ""):
        """Update with fresh metrics and vision data for commentary.
        
        Also updates the profile card if the stream data is available
        in the metrics dict.
        """
        if not metrics:
            return
        self.engine.update_metrics(metrics)
        if vision:
            self.engine.update_vision(vision)

        viewers = metrics.get("viewers", 0)
        channel = metrics.get("channel", self._current_channel or "")
        if viewers:
            self._stream_info.setText(f"👁 {viewers:,} viewers")

        if not self._current_channel and channel:
            self._current_channel = channel
            self.engine.set_channel(self._current_channel)

        # Update profile card from metrics if stream data is available
        # The metrics dict may contain the full stream data when called
        # from update_current_stream_view
        if hasattr(self, '_current_stream') and self._current_stream:
            self._update_profile(self._current_stream)
        elif channel:
            # Build a minimal profile from metrics
            self._streamer_name.setText(f"🟣 @{channel}")
            if viewers:
                self._streamer_stats.setText(f"👁 {viewers:,} viewers")

        self.engine.generate()

    def _on_commentary(self, text: str, mood: str, color: str):
        """Called when the engine generates new commentary."""
        self.bot.set_expression(mood)
        self.bot.set_talking(True)
        self.bubble.show_text(text, color)
        char_count = len(text)
        talk_duration = max(2000, char_count * 30)
        QTimer.singleShot(talk_duration, lambda: self.bot.set_talking(False))

    def _on_status(self, status: str, detail: str):
        """Called when the engine updates Azure AI connection status."""
        self._blink_timer.stop()
        self._blink_visible = True

        if status == "idle":
            self._status_label.setText("● IDLE")
            self._status_label.setStyleSheet(
                f"color: {Theme.MUTED}; background: transparent; "
                f"padding: 1px 4px; font-size: 7px;"
            )
        elif status == "connecting":
            self._status_label.setText("◌ CONNECTING TO AZURE...")
            self._status_label.setStyleSheet(
                "color: #ffaa00; background: rgba(255,170,0,0.08); "
                "padding: 1px 4px; font-size: 7px; border-radius: 3px;"
            )
            self._blink_timer.start()
            self.bubble.show_loading("#ffaa00", "Connecting to Azure AI")
            self._update_azure_details(status)
        elif status == "communicating":
            self._status_label.setText("◉ COMMUNICATING WITH AZURE...")
            self._status_label.setStyleSheet(
                "color: #00ccff; background: rgba(0,204,255,0.08); "
                "padding: 1px 4px; font-size: 7px; border-radius: 3px;"
            )
            self._blink_timer.start()
            self.bubble.show_loading("#00ccff", "Generating AI insight")
            self._update_azure_details(status)
        elif status == "connected":
            self._status_label.setText("● AI CONNECTED")
            self._status_label.setStyleSheet(
                f"color: #00ff88; background: transparent; "
                f"padding: 1px 4px; font-size: 7px;"
            )
            self._update_azure_details(status)
        elif status == "error":
            self._status_label.setText(f"✖ {detail}")
            self._status_label.setStyleSheet(
                "color: #ff4466; background: rgba(255,68,102,0.08); "
                "padding: 1px 4px; font-size: 7px; border-radius: 3px;"
            )
            self.bubble.show_text(f"⚠ {detail}", "#ff4466")
            self._update_azure_details(status)
        self._status_label.update()

    def _update_azure_details(self, status):
        """Update the Azure AI details section."""
        try:
            from core.azure_ai_client import get_ai_client
            client = get_ai_client()
            if client:
                stats = client.get_agent_stats()
                self._detail_endpoint.setText(client.endpoint[:30] + "...")
                self._detail_deployment.setText(client.deployment)
                self._detail_auth.setText("Azure AD Token")
                self._detail_latency.setText(f"{stats.get('avg_latency_ms', 0)}ms")
                self._detail_calls.setText(str(stats.get("total_calls", 0)))
                self._detail_tokens.setText(str(stats.get("total_tokens", 0)))
            else:
                self._detail_endpoint.setText("Not initialized")
                self._detail_deployment.setText("—")
                self._detail_auth.setText("—")
                self._detail_latency.setText("—")
                self._detail_calls.setText("—")
                self._detail_tokens.setText("—")
        except Exception as e:
            debug(f"[AZURE DETAILS] Error: {e}")

    def _blink_status(self):
        """Blink the status indicator during connecting/communicating states."""
        self._blink_visible = not self._blink_visible
        if self._blink_visible:
            current = self._status_label.text()
            if current.startswith("◌"):
                self._status_label.setStyleSheet(
                    "color: #ffaa00; background: rgba(255,170,0,0.08); "
                    "padding: 1px 4px; font-size: 7px; border-radius: 3px;"
                )
            elif current.startswith("◉"):
                self._status_label.setStyleSheet(
                    "color: #00ccff; background: rgba(0,204,255,0.08); "
                    "padding: 1px 4px; font-size: 7px; border-radius: 3px;"
                )
        else:
            self._status_label.setStyleSheet(
                "color: #445566; background: transparent; "
                "padding: 1px 4px; font-size: 7px;"
            )

    def clear(self):
        self._current_channel = None
        self._current_stream = None
        self._stream_info.setText("")
        self._streamer_name.setText("No streamer selected")
        self._streamer_game.setText("")
        self._streamer_stats.setText("")
        self.bot.set_expression("neutral")
        self.bubble.show_text("No other streams available right now.", "#6a7188")
        self._on_status("idle", "")