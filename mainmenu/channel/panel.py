"""Channel Rewards Panel - displays user's channel points balance and reward redemption options."""

from logger import debug
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QListWidget, QListWidgetItem, QTextEdit, QWidget, QMessageBox
)
from ..theme import Theme


class ChannelRewardsPanel(QGroupBox):
    
    """Panel showing channel points balance and available rewards for redemption."""
    
    def __init__(self, api=None):
        super().__init__("CHANNEL REWARDS")
        self.setStyleSheet(Theme.group_box_style(Theme.CYAN))
        self.api = api
        self.current_broadcaster_id = None
        self.current_broadcaster_login = None
        self.user_id = None
        self.user_display_name = None
        self.rewards_cache = {}
        
        # Signals
        self.reward_redeemed = Signal(str, str)  # reward_id, reward_title
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # User info and balance header
        self._setup_header()
        
        # Rewards list
        self._setup_rewards_section()
        
        # Redemption log
        self._setup_log_section()

    def _setup_header(self):
        """Setup header with user info and balance."""
        header_layout = QVBoxLayout()
        
        # Streamer info row
        streamer_row = QHBoxLayout()
        self.streamer_label = QLabel("No stream active")
        self.streamer_label.setStyleSheet(f"""
            color: {Theme.TEXT_PRIMARY};
            font-weight: bold;
            font-size: 12px;
            padding: 4px;
        """)
        streamer_row.addWidget(self.streamer_label)
        streamer_row.addStretch()
        header_layout.addLayout(streamer_row)
        
        # Status row
        status_row = QHBoxLayout()
        self.status_label = QLabel("Status: Not logged in")
        self.status_label.setStyleSheet(f"""
            color: {Theme.RED_DARK};
            font-weight: bold;
            font-size: 11px;
            padding: 2px;
        """)
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        header_layout.addLayout(status_row)
        
        # Balance display (simplified)
        balance_row = QHBoxLayout()
        self.balance_label = QLabel("Points: --")
        self.balance_label.setStyleSheet(f"""
            color: {Theme.ORANGE};
            font-weight: bold;
            font-size: 12px;
            padding: 2px;
        """)
        balance_row.addWidget(self.balance_label)
        balance_row.addStretch()
        header_layout.addLayout(balance_row)
        
        # Refresh button
        refresh_btn = QPushButton("🔄 REFRESH")
        refresh_btn.clicked.connect(self.refresh_rewards)
        refresh_btn.setStyleSheet(self._button_style(Theme.CYAN))
        header_layout.addWidget(refresh_btn)
        
        layout = self.layout()
        layout.addLayout(header_layout)

    def _setup_rewards_section(self):
        """Setup rewards list section."""
        # Title
        title = QLabel("AVAILABLE REWARDS:")
        title.setStyleSheet(f"""
            color: {Theme.TEXT_SECONDARY};
            font-weight: bold;
            margin-top: 8px;
        """)
        self.layout().addWidget(title)
        
        # Rewards list
        self.rewards_list = QListWidget()
        self.rewards_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {Theme.DARK_PANEL};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.SECTION_BORDER};
                border-radius: 4px;
                font-size: 10px;
            }}
            QListWidget::item {{
                padding: 6px;
            }}
            QListWidget::item:selected {{
                background-color: {Theme.AVATAR_BG};
            }}
            QListWidget::item:hover {{
                background-color: {Theme.SECTION_BORDER};
            }}
        """)
        self.rewards_list.itemDoubleClicked.connect(self._on_reward_clicked)
        self.layout().addWidget(self.rewards_list)
        
        # Info label
        self.info_label = QLabel("")
        self.info_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 9px;")
        self.layout().addWidget(self.info_label)

    def _setup_log_section(self):
        """Setup redemption log section."""
        log_title = QLabel("ACTIVITY LOG:")
        log_title.setStyleSheet(f"""
            color: {Theme.TEXT_SECONDARY};
            font-weight: bold;
            margin-top: 8px;
        """)
        self.layout().addWidget(log_title)
        
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(80)
        self.log_view.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Theme.DARK_PANEL};
                color: {Theme.TEXT_SECONDARY};
                border: 1px solid {Theme.SECTION_BORDER};
                border-radius: 2px;
                font-size: 9px;
            }}
        """)
        self.layout().addWidget(self.log_view)

    def _button_style(self, color):
        return f"""
            QPushButton {{
                background-color: {Theme.DARK_PANEL};
                color: {color};
                border: 1px solid {color};
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 10px;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: white;
            }}
        """

    def set_api(self, api):
        """Set the API client and load user info."""
        self.api = api
        if api:
            self._load_user_info()

    def _load_user_info(self):
        """Load authenticated user info from Twitch API."""
        try:
            user_data = self.api.get_current_user()
            self.user_id = user_data.get("id")
            self.user_display_name = user_data.get("display_name", "Unknown")
            
            # Update status display
            self.status_label.setText(f"Logged in as: {self.user_display_name}")
            self.status_label.setStyleSheet(f"""
                color: {Theme.GREEN};
                font-weight: bold;
                font-size: 11px;
                padding: 2px;
            """)
            self.append_log(f"✓ Logged in as: {self.user_display_name}")
        except Exception as e:
            debug(f"Failed to load user info: {e}")
            self.status_label.setText("Error loading user info")
            self.append_log(f"✗ Error: {str(e)}")

    def set_streamer(self, broadcaster_id, broadcaster_login):
        """Set the current streamer/broadcaster."""
        self.current_broadcaster_id = broadcaster_id
        self.current_broadcaster_login = broadcaster_login
        
        # Update display
        self.streamer_label.setText(f"Streamer: @{broadcaster_login}")
        self.status_label.setText(f"Watching: @{broadcaster_login}")
        self.status_label.setStyleSheet(f"""
            color: {Theme.CYAN};
            font-weight: bold;
            font-size: 11px;
            padding: 2px;
        """)
        self.info_label.setText("")
        
        # Load rewards for this channel
        self.refresh_rewards()
        
        # Update balance display
        self.balance_label.setText("Points: -- (logged in)")

    def clear_streamer(self):
        """Clear the current streamer."""
        self.current_broadcaster_id = None
        self.current_broadcaster_login = None
        self.streamer_label.setText("No stream active")
        self.balance_label.setText("Points: --")
        self.rewards_cache = {}
        self.rewards_list.clear()
        self.info_label.setText("")

    def refresh_rewards(self):
        """Fetch and display available rewards for the current channel."""
        if not self.api:
            self.info_label.setText("Not logged in to Twitch")
            self.status_label.setText("Status: Not logged in")
            self.status_label.setStyleSheet("color: #ff7777; font-weight: bold; font-size: 11px;")
            return
            
        if not self.current_broadcaster_id:
            self.info_label.setText("No stream active - select a channel first")
            return
        
        try:
            self.append_log(f"Fetching rewards for @{self.current_broadcaster_login}...")
            rewards = self.api.get_channel_rewards(self.current_broadcaster_id)
            
            self.rewards_cache = {reward["id"]: reward for reward in rewards}
            self._update_rewards_list(rewards)
            
            enabled_count = sum(1 for r in rewards if r.get("is_enabled", False))
            self.info_label.setText(f"{enabled_count}/{len(rewards)} rewards available")
            
            self.append_log(f"✓ Loaded {len(rewards)} rewards ({enabled_count} enabled)")
            
        except Exception as e:
            error_msg = str(e)
            self.append_log(f"✗ Error loading rewards: {error_msg}")
            
            # Check for OAuth scope error and provide helpful message
            if "channel:read:redemptions" in error_msg or "Unauthorized" in error_msg:
                self.info_label.setText("⚠️ OAuth scope missing! Re-auth with: channel:read:redemptions")
                self.append_log("⚠️ Your Twitch token needs additional scopes:")
                self.append_log("   - channel:read:redemptions")
                self.append_log("   Re-authenticate with this scope to view rewards.")
            elif hasattr(e, 'get_help_message'):
                # Handle TwitchScopeError with detailed help
                self.info_label.setText("⚠️ Missing OAuth scopes")
                self.append_log(e.get_help_message())
            else:
                self.info_label.setText(f"Error: {error_msg[:50]}")

    def _update_rewards_list(self, rewards):
        """Update the rewards list UI."""
        self.rewards_list.clear()
        
        for reward in rewards:
            if not reward.get("is_enabled", False):
                continue
                
            item = QListWidgetItem()
            title = reward.get("title", "Untitled")
            cost = reward.get("cost", 0)
            
            # Format display
            display_text = f"{title} • {cost:,} pts"
            if cost == 0:
                display_text = f"{title} • FREE"
                
            item.setText(display_text)
            item.setData(Qt.ItemDataRole.UserRole, reward["id"])
            self.rewards_list.addItem(item)

    def _on_reward_clicked(self, item):
        """Handle reward click for redemption."""
        reward_id = item.data(Qt.ItemDataRole.UserRole)
        reward = self.rewards_cache.get(reward_id)
        
        if not reward:
            return
            
        title = reward.get("title", "Unknown Reward")
        cost = reward.get("cost", 0)
        
        # Confirm redemption
        reply = QMessageBox.question(
            self,
            "Redeem Reward",
            f'Redeem "{title}" for {cost:,} channel points?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.redeem_reward(reward_id, title)

    def redeem_reward(self, reward_id, title=""):
        """Redeem a channel reward."""
        if not self.api:
            self.append_log("Cannot redeem: Not logged in to Twitch")
            return
            
        if not self.current_broadcaster_id:
            self.append_log("Cannot redeem: No stream active")
            return
            
        if not self.user_id:
            self.append_log("Cannot redeem: Not logged in")
            return
        
        # Get title if not provided
        if not title:
            reward = self.rewards_cache.get(reward_id)
            if reward:
                title = reward.get("title", "Unknown")
        
        try:
            result = self.api.redeem_channel_reward(
                self.current_broadcaster_id,
                reward_id,
                self.user_id
            )
            
            if result:
                self.append_log(f"✅ Redeemed: {title}")
                self.reward_redeemed.emit(reward_id, title)
            else:
                self.append_log(f"❌ Failed to redeem: {title}")
                
        except Exception as e:
            error_msg = str(e)
            self.append_log(f"Redemption error: {error_msg}")
            
            # Check for OAuth scope error for redemption
            if "channel:manage:redemptions" in error_msg or "Unauthorized" in error_msg:
                self.append_log("⚠️ Redemption requires 'channel:manage:redemptions' scope")
                self.append_log("   This scope requires special Twitch permissions.")
                self.append_log("   Contact Twitch support to request this permission.")
            elif hasattr(e, 'get_help_message'):
                # Handle TwitchScopeError with detailed help
                self.append_log(e.get_help_message())

    def append_log(self, message):
        """Add message to activity log."""
        debug(f"ChannelRewardsPanel: {message}")
        self.log_view.append(message)

    def set_status(self, message):
        """Set status message."""
        pass

    def set_next_status(self, message):
        """Set next status message."""
        pass