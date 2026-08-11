"""Chat Panel — integrates Twitch chat into the main interface."""

from logger import debug
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QWidget,
)
from chat import ChatWidget, TwitchChatClient
from PySide6.QtCore import QTimer
from ..theme import Theme


class ChatPanel(QGroupBox):
    """Wraps ChatWidget in a styled group box with channel info and
    connection status in the header.

    State machine for the connection dot:
        IDLE  →  CONNECTING  →  LIVE
                        ↘            ↘
                      FAILED       OFFLINE
    """

    # ---- Connection status constants --------------------------------
    _STATUS_IDLE       = ("IDLE",       Theme.DIM)
    _STATUS_CONNECTING = ("CONNECTING…", Theme.ORANGE)
    _STATUS_LIVE       = ("LIVE",       Theme.GREEN)
    _STATUS_FAILED     = ("FAILED",     Theme.RED_DARK)
    _STATUS_OFFLINE    = ("OFFLINE",    Theme.RED_DARK)
    _STATUS_NA         = ("N/A",        Theme.DIM)

    def __init__(self, access_token):
        debug("ChatPanel.__init__ called")
        super().__init__("TWITCH CHAT")
        self.setStyleSheet(Theme.group_box_style(Theme.CYAN))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Connection timeout timer
        self._connect_timeout = QTimer()
        self._connect_timeout.setSingleShot(True)
        self._connect_timeout.timeout.connect(self._on_connect_timeout)
        self._connect_timeout.setInterval(5000)  # 5 second timeout (shorter)

        # --- Channel info header ---
        header_row = QHBoxLayout()
        header_row.setSpacing(6)
        header_row.setContentsMargins(4, 0, 4, 0)

        self.channel_avatar = QLabel()
        self.channel_avatar.setFixedSize(24, 24)
        self.channel_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._reset_avatar()
        header_row.addWidget(self.channel_avatar)

        self.channel_info_label = QLabel("Not connected")
        self.channel_info_label.setFont(QFont(Theme.FAMILY, 11, QFont.Weight.Bold))
        self.channel_info_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        header_row.addWidget(self.channel_info_label, 1)

        self.connection_dot = QLabel()
        self._set_status(*self._STATUS_IDLE)
        header_row.addWidget(self.connection_dot)

        layout.addLayout(header_row)

        # --- Compact channel info strip (game + viewers + rewards) ---
        self.info_strip = QLabel("")
        self.info_strip.setStyleSheet(
            f"color: {Theme.MUTED}; font-size: 9px; padding: 0 4px;"
        )
        self.info_strip.setFixedHeight(14)
        layout.addWidget(self.info_strip)

        # --- Chat widget (16px font per user preference) ---
        # Create a container widget for the chat widget so we can replace it
        self.chat_container = QWidget()
        chat_container_layout = QVBoxLayout(self.chat_container)
        chat_container_layout.setContentsMargins(0, 0, 0, 0)
        chat_container_layout.setSpacing(0)
        
        self.chat_widget = ChatWidget(username="", access_token=access_token)
        self.chat_widget.setStyleSheet(f"""
            QTextEdit, QListWidget, QPlainTextEdit {{
                font-size: 16px;
                background-color: {Theme.DARK_PANEL};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                border-radius: 2px;
            }}
            QLineEdit {{
                font-size: 16px;
                padding: 4px;
            }}
            QPushButton {{
                font-size: 11px;
                padding: 4px 8px;
            }}
        """)
        chat_container_layout.addWidget(self.chat_widget)

        # Add chat container to main layout
        layout.addWidget(self.chat_container)
        
        # Hide the redundant internal widgets — the panel header replaces them.
        self._hide_redundant_widgets()

        # --- AI Metrics Widget (10 cells with descriptive labels) ---
        self.ai_metrics_widget = QWidget()
        self.ai_metrics_widget.setFixedHeight(110)
        metrics_layout = QHBoxLayout(self.ai_metrics_widget)
        metrics_layout.setContentsMargins(4, 4, 4, 4)
        metrics_layout.setSpacing(4)
        
        # Create 10 metric cells with descriptive labels and tooltips
        self.metric_cells = {}
        metric_defs = [
            ("SCORE", "Stream quality rating (0-100)"),
            ("MOMENTUM", "Viewer trend direction"),
            ("CONFIDENCE", "AI prediction confidence"),
            ("PEAK", "Predicted peak viewers"),
            ("GROWTH", "Viewer growth rate (%)"),
            ("CHAT ACTIVITY", "Chat engagement level"),
            ("RETENTION", "Viewer retention rate"),
            ("HEALTH", "Overall stream health score"),
            ("ENGAGE", "Engagement potential"),
            ("ACTION", "AI recommended action"),
        ]
        
        for name, tip in metric_defs:
            cell = QLabel("...")
            cell.setFixedSize(90, 40)
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.setStyleSheet(f"""
                background-color: {Theme.DARK_PANEL};
                color: {Theme.MUTED};
                border: 1px solid {Theme.SECTION_BORDER};
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            """)
            cell.setToolTip(tip)
            metrics_layout.addWidget(cell)
            self.metric_cells[name] = cell
        
        layout.addWidget(self.ai_metrics_widget)

        # Track the last channel we tried to connect to so we can
        # wire signals exactly once per connect attempt.
        self._connected_channel = None
        self._access_token = access_token

    # ---- Public API ------------------------------------------------

    def set_username(self, username):
        """Set the local user's username on the underlying ChatWidget."""
        self.chat_widget.username = username

    def connect_chat(self, channel):
        """Connect the embedded ChatWidget to *channel*."""
        debug(f"[CHAT PANEL] ========== connect_chat called with channel: {channel} ==========")
        if not channel:
            debug("[CHAT PANEL] No channel provided, returning")
            return

        # Disconnect any previous connection first.
        debug("[CHAT PANEL] Disconnecting previous connection")
        self._disconnect_internal()

        self.channel_info_label.setText(f"#{channel}")
        self._set_status(*self._STATUS_CONNECTING)
        debug(f"[CHAT PANEL] Status set to CONNECTING")

        # Start connection timeout
        self._connect_timeout.start()
        debug(f"[CHAT PANEL] Connection timeout started (5s)")

        # Create a FRESH ChatWidget for each connection to avoid signal issues
        debug("[CHAT PANEL] Creating fresh ChatWidget instance")
        old_chat = self.chat_widget
        self.chat_widget = ChatWidget(username="", access_token=self._access_token)
        self.chat_widget.setStyleSheet(old_chat.styleSheet())
        
        # Replace in layout
        layout = self.chat_container.layout()
        layout.replaceWidget(old_chat, self.chat_widget)
        old_chat.deleteLater()
        
        # Hide redundant widgets
        self._hide_redundant_widgets()
        
        # Connect to channel
        debug(f"[CHAT PANEL] Calling chat_widget.connect_to_channel()")
        try:
            self.chat_widget.connect_to_channel(channel)
            debug(f"[CHAT PANEL] connect_to_channel() returned without exception")
            
            # Check if client was created and has correct attributes
            client = getattr(self.chat_widget, "client", None)
            if client is not None:
                debug(f"[CHAT PANEL] Client created successfully")
                debug(f"[CHAT PANEL] Client state - running: {client.running}, channel: {client.channel}, username: {client.username}")
                debug(f"[CHAT PANEL] Client thread: {client._read_thread}")
                if client._read_thread:
                    debug(f"[CHAT PANEL] Thread alive: {client._read_thread.is_alive()}")
            else:
                debug("[CHAT PANEL] WARNING: Client exists but has no attributes!")
                
        except Exception as e:
            debug(f"[CHAT PANEL] Exception in connect_to_channel: {e}")
            import traceback
            traceback.print_exc()
            self._set_status(*self._STATUS_FAILED)
            self.chat_widget.display_system_message(f"Connection error: {e}")
            return
        
        # Wire panel signals to the client
        client = getattr(self.chat_widget, "client", None)
        debug(f"[CHAT PANEL] Client after connect_to_channel: {client is not None}")
        if client is not None:
            debug(f"[CHAT PANEL] Client state - running: {client.running}, channel: {client.channel}, username: {client.username}")
            try:
                client.connected.connect(self._on_connected)
                client.disconnected.connect(self._on_disconnected)
                client.authentication_failed.connect(self._on_auth_failed)
                debug(f"[CHAT PANEL] Panel signals wired successfully")
            except Exception as e:
                debug(f"[CHAT PANEL] Error wiring signals: {e}")
                self._set_status(*self._STATUS_FAILED)
                return
        else:
            debug("[CHAT PANEL] ERROR: Client is None after connect_to_channel!")
            self._set_status(*self._STATUS_FAILED)
            return

        self._connected_channel = channel
        debug(f"[CHAT PANEL] ========== Connection initiated for #{channel} ==========")

    def show_platform_unavailable(self, platform):
        """Show a graceful 'chat unavailable' state for non-Twitch platforms."""
        debug(f"ChatPanel.show_platform_unavailable called for {platform}")
        self._disconnect_internal()
        self.channel_info_label.setText(f"{platform.upper()} chat unavailable")
        self._set_status(*self._STATUS_NA)

    def disconnect_chat(self):
        """Public disconnect — called on shutdown / channel switch."""
        debug("ChatPanel.disconnect_chat called")
        self._disconnect_internal()
        self.channel_info_label.setText("Not connected")
        self._set_status(*self._STATUS_IDLE)
        self.info_strip.setText("")

    def set_avatar(self, avatar_url):
        """Load and display a channel avatar from a URL string."""
        if not avatar_url:
            self._reset_avatar()
            return
        try:
            import urllib.request
            data = urllib.request.urlopen(avatar_url, timeout=5).read()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    22, 22,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.channel_avatar.setPixmap(scaled)
                self.channel_avatar.setText("")
                self.channel_avatar.setStyleSheet(
                    f"border: 1px solid {Theme.SECTION_BORDER};"
                    f"border-radius: 11px;"
                    f"background-color: transparent;"
                )
            else:
                self._reset_avatar()
        except Exception as exc:
            debug(f"[CHAT PANEL] Failed to load avatar: {exc}")
            self._reset_avatar()

    def set_channel_info(self, game="", viewers=0, reward_count=0):
        """Update the compact info strip with channel data."""
        parts = []
        if game:
            parts.append(game)
        if viewers:
            parts.append(f"{viewers:,} viewers")
        if reward_count:
            parts.append(f"{reward_count} rewards")
        self.info_strip.setText("  |  ".join(parts))

    # ---- Internal helpers ------------------------------------------

    def _set_status(self, text, color):
        """Update the connection-dot label with *text* and *color*."""
        self.connection_dot.setText(text)
        self.connection_dot.setStyleSheet(f"""
            color: {color};
            font-size: 9px;
            font-weight: bold;
            padding: 1px 4px;
            border-radius: 3px;
            background-color: {Theme.DARK_PANEL};
        """)

    def _reset_avatar(self):
        """Reset the avatar label to the default '?' placeholder."""
        self.channel_avatar.setPixmap(QPixmap())
        self.channel_avatar.setText("?")
        self.channel_avatar.setStyleSheet(f"""
            background-color: {Theme.AVATAR_BG};
            border: 1px solid {Theme.SECTION_BORDER};
            border-radius: 11px;
            color: {Theme.DIM};
            font-size: 9px;
            min-width: 22px;
            min-height: 22px;
        """)

    def set_ai_loading(self, loading: bool = True):
        """Set AI metrics to loading state."""
        state = "LOADING" if loading else "..."
        color = Theme.ORANGE if loading else Theme.MUTED
        bg_color = Theme.DARK_PANEL
        for cell in self.metric_cells.values():
            cell.setText(state)
            cell.setStyleSheet(f"""
                background-color: {bg_color};
                color: {color};
                border: 1px solid {Theme.SECTION_BORDER};
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            """)
            cell.setToolTip("AI is analyzing stream data..." if loading else f"{cell.text()}: Waiting for data")

    def set_ai_error(self, error_msg: str = "AI unavailable"):
        """Set AI metrics to error state."""
        for name, cell in self.metric_cells.items():
            cell.setText("N/A")
            cell.setStyleSheet(f"""
                background-color: {Theme.DARK_PANEL};
                color: {Theme.RED_DARK};
                border: 1px solid {Theme.RED_DARK};
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            """)
            cell.setToolTip(f"{name}: {error_msg}")

    def _hide_redundant_widgets(self):
        """Hide ChatWidget elements that the panel header replaces."""
        w = self.chat_widget
        # Status label — panel header's connection_dot replaces this.
        if hasattr(w, "status"):
            w.status.setVisible(False)
        # Channel input row — connection is managed automatically.
        if hasattr(w, "channel_input"):
            w.channel_input.setVisible(False)
        if hasattr(w, "connect_button"):
            w.connect_button.setVisible(False)
        if hasattr(w, "disconnect_button"):
            w.disconnect_button.setVisible(False)

    def _disconnect_internal(self):
        """Disconnect the ChatWidget and unhook signals to avoid leaks."""
        # DO NOT call any ChatWidget methods - they break signal handlers
        # Just disconnect the panel's signals and let ChatWidget manage itself
        client = getattr(self.chat_widget, "client", None)
        if client is not None:
            # Disconnect only the signals we added in connect_chat()
            signals_to_disconnect = [
                (client.connected, self._on_connected),
                (client.disconnected, self._on_disconnected),
                (client.authentication_failed, self._on_auth_failed),
            ]
            for signal, slot in signals_to_disconnect:
                try:
                    signal.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
        
        # DO NOT call chat_widget.disconnect() - it removes internal signal handlers
        # ChatWidget will create a new client on next connect_to_channel() call
        self._connected_channel = None

    # ---- Signal handlers -------------------------------------------

    def _on_connected(self):
        debug("[CHAT PANEL] ========== IRC connected signal received - updating status to LIVE ==========")
        self._set_status(*self._STATUS_LIVE)
        self._connect_timeout.stop()
        # Update info strip with channel info
        if hasattr(self, 'chat_widget') and self.chat_widget and self.chat_widget.client:
            debug(f"[CHAT PANEL] Setting status text: Connected to #{self._connected_channel}")
            self.chat_widget.display_system_message(f"Connected to #{self._connected_channel}")

    def _on_disconnected(self):
        debug("[CHAT PANEL] IRC disconnected")
        self._connect_timeout.stop()
        current_text = self.connection_dot.text()
        if current_text in ("LIVE", "CONNECTING…"):
            self._set_status(*self._STATUS_OFFLINE)
            if hasattr(self, 'chat_widget') and self.chat_widget:
                debug("[CHAT PANEL] Setting status text: Chat disconnected")
                self.chat_widget.display_system_message("Chat disconnected")

    def _on_auth_failed(self, reason=""):
        debug(f"[CHAT PANEL] IRC auth failed: {reason}")
        self._set_status(*self._STATUS_FAILED)
        self._connect_timeout.stop()
        if hasattr(self, 'chat_widget') and self.chat_widget:
            debug("[CHAT PANEL] Setting status text: Authentication failed")
            self.chat_widget.display_system_message("Twitch authentication failed")
    
    def _on_connect_timeout(self):
        """Handle connection timeout - connection took too long."""
        debug("[CHAT PANEL] Connection timeout - switching to FAILED state")
        self._set_status(*self._STATUS_FAILED)
        if hasattr(self, 'chat_widget') and self.chat_widget:
            self.chat_widget.display_system_message("Connection timeout - failed to connect to chat")
    
    def update_ai_metrics(self, analysis: dict):
        """Update AI metrics widget with analysis data.
        
        Args:
            analysis: Dict from AI analytics engine with keys:
                - score: quality_score (0-100)
                - status: momentum (Rising/Stable/Declining)
                - percent: momentum_percent
                - confidence: AI confidence (0-1)
                - predicted_peak_viewers: int
                - ai_insight: str
        """
        if not analysis:
            self.set_ai_loading(False)
            return
        
        # Check if AI is unavailable (only show error for explicit unavailable message)
        ai_insight = analysis.get("ai_insight", "")
        if ai_insight == "AI analysis unavailable":
            self.set_ai_error("AI analysis unavailable")
            return
        
        # SCORE
        score = analysis.get("score", 0)
        self.metric_cells["SCORE"].setText(f"{score}")
        color = Theme.GREEN if score >= 70 else (Theme.CYAN if score >= 50 else Theme.RED_DARK)
        self.metric_cells["SCORE"].setStyleSheet(f"""
            background-color: {Theme.DARK_PANEL};
            color: {color};
            border: 1px solid {Theme.SECTION_BORDER};
            border-radius: 4px;
            font-size: 10px;
            font-weight: bold;
        """)
        self.metric_cells["SCORE"].setToolTip(f"SCORE: {score}/100 - Quality rating")
        
        # MOMENTUM
        status = analysis.get("status", "Stable")
        percent = analysis.get("percent", 0.0)
        self.metric_cells["MOMENTUM"].setText(f"{status[:6]}")
        color = Theme.GREEN if status == "Rising" else (Theme.RED_DARK if status == "Declining" else Theme.TEXT_SECONDARY)
        self.metric_cells["MOMENTUM"].setStyleSheet(f"""
            background-color: {Theme.DARK_PANEL};
            color: {color};
            border: 1px solid {Theme.SECTION_BORDER};
            border-radius: 4px;
            font-size: 10px;
            font-weight: bold;
        """)
        self.metric_cells["MOMENTUM"].setToolTip(f"Momentum: {status} ({percent:+.1f}%)")
        
        # CONFIDENCE
        confidence = int((analysis.get("confidence", 0.0) or 0.0) * 100)
        self.metric_cells["CONFIDENCE"].setText(f"{confidence}%")
        self.metric_cells["CONFIDENCE"].setToolTip(f"Confidence: {confidence}% - Data availability")
        
        # PEAK VIEWERS
        peak = analysis.get("predicted_peak_viewers", 0)
        self.metric_cells["PEAK"].setText(f"{peak:,}" if peak else "--")
        self.metric_cells["PEAK"].setToolTip(f"PEAK: {peak:,} viewers - Predicted peak")
        
        # GROWTH
        self.metric_cells["GROWTH"].setText(f"{percent:+.1f}%")
        color = Theme.GREEN if percent > 0 else (Theme.RED_DARK if percent < 0 else Theme.TEXT_SECONDARY)
        self.metric_cells["GROWTH"].setStyleSheet(f"""
            background-color: {Theme.DARK_PANEL};
            color: {color};
            border: 1px solid {Theme.SECTION_BORDER};
            border-radius: 4px;
            font-size: 10px;
            font-weight: bold;
        """)
        self.metric_cells["GROWTH"].setToolTip(f"GROWTH: {percent:+.1f}% - Momentum change")
        
        # CHAT ACTIVITY (from recommendations)
        chat = "HIGH" if analysis.get("recommendations") else "LOW"
        self.metric_cells["CHAT ACTIVITY"].setText(chat)
        self.metric_cells["CHAT ACTIVITY"].setToolTip(f"Chat activity: {chat}")
        
        # RETENTION (from analytics engine)
        retention = analysis.get("retention", 0) or 0
        self.metric_cells["RETENTION"].setText(f"{retention}%")
        self.metric_cells["RETENTION"].setToolTip(f"Retention: {retention}% - Viewer retention rate")
        
        # HEALTH (from analytics engine)
        health = analysis.get("health", 0) or 0
        self.metric_cells["HEALTH"].setText(f"{health}")
        self.metric_cells["HEALTH"].setToolTip(f"Health: {health}/100 - Overall stream health")
        
        # ENGAGE (from analytics engine)
        viral = analysis.get("viral_potential", 0.0) or 0.0
        engage = int(viral * 100)
        self.metric_cells["ENGAGE"].setText(f"{engage}%")
        self.metric_cells["ENGAGE"].setToolTip(f"Engagement: {engage}% - Engagement potential")
        
        # ACTION (first recommendation or "WATCH")
        recs = analysis.get("recommendations", [])
        action = recs[0][:10] if recs else "WATCH"
        self.metric_cells["ACTION"].setText(action)
        self.metric_cells["ACTION"].setToolTip(f"ACTION: {action}")