"""Live Followed Channels panel — displays live followed streams with thumbnails."""

import requests
from logger import debug

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QGridLayout,
    QScrollArea,
    QFrame,
    QSizePolicy,
)

from core import run_in_background
from ..theme import Theme


class LiveFollowedPanel(QGroupBox):

    channel_selected = Signal(object)
    watch_requested = Signal(str)
    watchlist_changed = Signal()

    # Thumbnail dimensions (16:9 aspect ratio)
    THUMB_WIDTH = 200
    THUMB_HEIGHT = 112
    CARD_MIN_WIDTH = 220

    def __init__(self, api=None, analytics_engine=None):
        debug("LiveFollowedPanel.__init__ called")
        super().__init__("LIVE FOLLOWED CHANNELS")
        self.setStyleSheet(Theme.group_box_style(Theme.GREEN))

        self.api = api
        self._tracker = None
        self._analytics = analytics_engine
        self._avatar_cache = {}
        self._thumb_cache = {}
        self._pending_avatars = set()
        self._pending_thumbs = set()
        self._row_by_login = {}
        self._all_streams = []
        self._card_widgets = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.setMinimumHeight(380)

        # --- Add-to-watchlist bar (platform equality) ---
        add_row = QHBoxLayout()
        add_row.setSpacing(4)

        self.add_platform_combo = QComboBox()
        self.add_platform_combo.addItem("Twitch", "twitch")
        self.add_platform_combo.addItem("Kick", "kick")
        self.add_platform_combo.addItem("YouTube", "youtube")
        self.add_platform_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {Theme.DARK_PANEL};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.SECTION_BORDER};
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 11px;
            }}
        """)
        self.add_platform_combo.setFixedWidth(80)
        add_row.addWidget(self.add_platform_combo)

        self.add_channel_input = QLineEdit()
        self.add_channel_input.setPlaceholderText("Add channel (e.g. xqc, @handle)...")
        self.add_channel_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.DARK_PANEL};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.SECTION_BORDER};
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border: 1px solid {Theme.CYAN};
            }}
        """)
        self.add_channel_input.returnPressed.connect(self._on_add_channel)
        add_row.addWidget(self.add_channel_input, 1)

        self.add_button = QPushButton("+")
        self.add_button.setToolTip("Add channel to watchlist")
        self.add_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.AVATAR_BG};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.SECTION_BORDER};
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Theme.CYAN};
                color: #000000;
            }}
        """)
        self.add_button.clicked.connect(self._on_add_channel)
        add_row.addWidget(self.add_button)

        layout.addLayout(add_row)

        # --- Search/filter bar ---
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search channels...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.DARK_PANEL};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.SECTION_BORDER};
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border: 1px solid {Theme.CYAN};
            }}
        """)
        self.search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_input)

        # --- Channel list (thumbnail card style) ---
        self.channel_list = QListWidget()
        self.channel_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.channel_list.setSpacing(2)
        self.channel_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {Theme.DARK_PANEL};
                border: 1px solid {Theme.SECTION_BORDER};
                border-radius: 4px;
            }}
            QListWidget::item {{
                border-bottom: 1px solid {Theme.SECTION_BORDER};
                padding: 2px;
            }}
            QListWidget::item:selected {{
                background-color: {Theme.AVATAR_BG};
            }}
        """)
        self.channel_list.itemClicked.connect(self._on_item_clicked)
        self.channel_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.channel_list)

    def set_api(self, api):
        self.api = api

    def set_viewer_tracker(self, tracker):
        self._tracker = tracker

    def set_analytics_engine(self, analytics):
        self._analytics = analytics

    def _on_add_channel(self):
        """Add a channel to the watchlist for the selected platform."""
        from platforms import strip_platform_prefix, detect_platform
        from core.db import add_to_watchlist

        platform = self.add_platform_combo.currentData() or "twitch"
        raw = self.add_channel_input.text().strip()
        if not raw:
            return

        # Support explicit prefix syntax too: "kick:xqc", "yt:@handle"
        detected = detect_platform(raw)
        if detected != "twitch" or ":" in raw:
            platform = detected
        channel = strip_platform_prefix(raw).lstrip("#").lower()

        if not channel:
            return

        add_to_watchlist(platform, channel)
        debug(f"[WATCHLIST] Added {platform}:{channel}")
        self.add_channel_input.clear()

        # Notify the main window so it can refresh live channels.
        self.watchlist_changed.emit()

    def _on_search_changed(self, text):
        text = text.strip().lower()
        if not text:
            self._rebuild_list(self._all_streams)
        else:
            filtered = [
                s for s in self._all_streams
                if text in str(s.get("user_login", "")).lower()
                or text in str(s.get("user_name", "")).lower()
            ]
            self._rebuild_list(filtered)

    def _on_item_clicked(self, item):
        stream = item.data(Qt.ItemDataRole.UserRole)
        if stream:
            self.channel_selected.emit(stream)

    def _on_item_double_clicked(self, item):
        stream = item.data(Qt.ItemDataRole.UserRole)
        if not stream:
            return
        login = stream.get("user_login") or stream.get("user_name") or ""
        self.channel_selected.emit(stream)
        if login:
            self.watch_requested.emit(str(login))

    def set_streams(self, streams):
        debug(f"LiveFollowedPanel.set_streams called with {len(streams) if streams else 0} streams")
        self._all_streams = list(streams or [])
        self._rebuild_list(self._all_streams)

    def _rebuild_list(self, streams):
        selected_login = None
        current_item = self.channel_list.currentItem()
        if current_item:
            current_stream = current_item.data(Qt.ItemDataRole.UserRole)
            if current_stream:
                selected_login = str(current_stream.get("user_login") or current_stream.get("user_name") or "").strip().lower()

        self.channel_list.clear()
        self._row_by_login = {}
        restore_index = -1

        for index, stream in enumerate(streams):
            self._add_row(stream)
            if selected_login:
                login = str(stream.get("user_login") or stream.get("user_name") or "").strip().lower()
                if login == selected_login:
                    restore_index = index

        if restore_index >= 0:
            self.channel_list.setCurrentRow(restore_index)

    def _add_row(self, stream):
        login = str(stream.get("user_login") or stream.get("user_name") or "").strip()
        name = stream.get("user_name") or stream.get("user_login") or "Unknown"
        viewers = int(stream.get("viewer_count", 0))
        category = stream.get("game_name") or "No category"

        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, stream)
        # Taller rows for thumbnail cards
        item.setSizeHint(QSize(0, self.THUMB_HEIGHT + 20))
        self.channel_list.addItem(item)

        card = self._build_card_widget(stream, name, viewers, category, login)
        self.channel_list.setItemWidget(item, card)

        if login:
            self._row_by_login[login] = card
            self._ensure_avatar(login, stream.get("avatar_url"))
            # Fetch stream thumbnail
            thumb_url = stream.get("thumbnail_url") or stream.get("thumbnail", "")
            if thumb_url:
                self._ensure_thumbnail(login, thumb_url)

    def _build_card_widget(self, stream, name, viewers, category, login):
        """Build a card-style row with thumbnail on the left and info on the right."""
        widget = QWidget()
        widget.setObjectName("FollowedRow")
        widget.setStyleSheet(f"""
            QWidget#FollowedRow {{
                background: transparent;
                border-bottom: 1px solid {Theme.SECTION_BORDER};
            }}
            QWidget#FollowedRow:hover {{
                background-color: rgba(26, 42, 74, 0.3);
            }}
        """)

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 4, 8, 4)
        layout.setSpacing(10)

        # --- Thumbnail container (with avatar overlay) ---
        thumb_container = QWidget()
        thumb_container.setFixedSize(self.THUMB_WIDTH, self.THUMB_HEIGHT)
        thumb_layout = QVBoxLayout(thumb_container)
        thumb_layout.setContentsMargins(0, 0, 0, 0)

        thumb_label = QLabel()
        thumb_label.setFixedSize(self.THUMB_WIDTH, self.THUMB_HEIGHT)
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_label.setStyleSheet(f"""
            background-color: {Theme.DARK_PANEL};
            border: 1px solid {Theme.SECTION_BORDER};
            border-radius: 6px;
            color: {Theme.DIM};
            font-size: 10px;
        """)
        thumb_label.setText("📺")
        thumb_layout.addWidget(thumb_label)

        # Small avatar overlaid in bottom-left of thumbnail
        avatar_label = QLabel("?")
        avatar_label.setFixedSize(28, 28)
        avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_label.setStyleSheet(f"""
            background-color: {Theme.AVATAR_BG};
            border: 2px solid {Theme.DARK_PANEL};
            border-radius: 14px;
            color: {Theme.DIM};
            font-size: 9px;
        """)
        avatar_label.setParent(thumb_container)
        avatar_label.move(4, self.THUMB_HEIGHT - 32)

        layout.addWidget(thumb_container)

        # --- Info panel (right side) ---
        info = QVBoxLayout()
        info.setSpacing(3)

        # Top row: platform badge + channel name
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        platform = stream.get("platform", "twitch")
        badge_colors = {
            "twitch": "#9146FF",
            "kick": "#53FC18",
            "youtube": "#FF0000",
        }
        badge_color = badge_colors.get(platform, "#888888")
        badge_label = QLabel(platform.upper())
        badge_label.setStyleSheet(f"""
            color: {badge_color};
            font-size: 8px;
            font-weight: bold;
            border: 1px solid {badge_color};
            border-radius: 3px;
            padding: 1px 5px;
        """)
        badge_label.setFixedWidth(52)
        top_row.addWidget(badge_label)

        name_label = QLabel(str(name))
        name_label.setFont(QFont(Theme.FAMILY, 12, QFont.Weight.Bold))
        name_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        top_row.addWidget(name_label, 1)

        info.addLayout(top_row)

        # Viewers row
        viewers_label = QLabel(f"👁 {viewers:,} viewers")
        viewers_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px; font-weight: bold;")
        info.addWidget(viewers_label)

        # Category
        cat_label = QLabel(f"🎮 {category}")
        cat_label.setStyleSheet(f"color: {Theme.MUTED}; font-size: 10px;")
        info.addWidget(cat_label)

        # Bottom row: growth + score
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        # Growth
        growth_text = self._get_growth_text(login, stream)
        growth_label = QLabel(f"📈 {growth_text}")
        is_positive = growth_text.startswith("+") and growth_text != "+0.0%"
        is_negative = growth_text.startswith("-")
        if is_positive:
            growth_label.setStyleSheet(f"color: {Theme.GREEN}; font-size: 10px; font-weight: bold;")
        elif is_negative:
            growth_label.setStyleSheet(f"color: {Theme.RED_DARK}; font-size: 10px; font-weight: bold;")
        else:
            growth_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 10px;")
        bottom_row.addWidget(growth_label)

        # Score
        score_text = self._get_score_text(login, stream, viewers)
        score_label = QLabel(f"⭐ {score_text}")
        score_label.setStyleSheet(f"color: {Theme.CYAN}; font-size: 10px; font-weight: bold;")
        bottom_row.addWidget(score_label)

        bottom_row.addStretch()
        info.addLayout(bottom_row)

        info.addStretch()
        layout.addLayout(info, 1)

        widget.avatar_label = avatar_label
        widget.thumb_label = thumb_label
        widget.login = login
        widget.stream = stream
        return widget

    def _get_growth_text(self, login, stream):
        """Get growth percentage from AI analysis or viewer tracker."""
        ai_analysis = {}
        platform = stream.get("platform", "twitch")
        if self._analytics and login:
            ai_analysis = self._analytics.get_ai_analysis(login, platform=platform)
        if ai_analysis:
            momentum_percent = ai_analysis.get("momentum_percent", 0)
            return f"{momentum_percent:+.1f}%"
        if self._tracker:
            tracker_data = self._tracker.get_channel_stats(login, platform=platform)
            if tracker_data:
                pct = tracker_data.get("percent", 0)
                return f"{pct:+.1f}%"
        return "--"

    def _get_score_text(self, login, stream, viewers):
        """Get quality score from AI analysis or estimate from viewers."""
        ai_analysis = {}
        platform = stream.get("platform", "twitch")
        if self._analytics and login:
            ai_analysis = self._analytics.get_ai_analysis(login, platform=platform)
        if ai_analysis:
            return str(ai_analysis.get("quality_score", 0))
        if viewers >= 10000:
            return "75"
        elif viewers >= 1000:
            return "50"
        elif viewers >= 100:
            return "25"
        return "10"

    # ---- Thumbnail loading ----

    def _ensure_thumbnail(self, login, thumb_url):
        """Load stream thumbnail asynchronously."""
        # Replace template URL dimensions with our size
        url = thumb_url.replace("{width}", str(self.THUMB_WIDTH)).replace("{height}", str(self.THUMB_HEIGHT))
        if login in self._thumb_cache:
            self._apply_thumbnail(login, self._thumb_cache[login])
            return
        if login in self._pending_thumbs:
            return
        self._pending_thumbs.add(login)
        run_in_background(
            lambda: self._fetch_thumbnail(login, url),
            lambda result: self._on_thumbnail_fetched(result),
            lambda _error: self._pending_thumbs.discard(login),
        )

    def _fetch_thumbnail(self, login, url):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return login, response.content
        except Exception:
            return login, None

    def _on_thumbnail_fetched(self, result):
        login, data = result
        self._pending_thumbs.discard(login)
        if not data:
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            pixmap = pixmap.scaled(
                self.THUMB_WIDTH, self.THUMB_HEIGHT,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._thumb_cache[login] = pixmap
            self._apply_thumbnail(login, pixmap)

    def _apply_thumbnail(self, login, pixmap):
        card = self._row_by_login.get(login)
        if card is None:
            return
        card.thumb_label.setPixmap(pixmap)
        card.thumb_label.setText("")

    # ---- Avatar loading ----

    def _ensure_avatar(self, login, avatar_url):
        if login in self._avatar_cache:
            self._apply_avatar(login, self._avatar_cache[login])
            return
        if login in self._pending_avatars:
            return
        if not avatar_url and self.api is None:
            return
        self._pending_avatars.add(login)
        run_in_background(
            lambda: self._fetch_avatar(login, avatar_url),
            lambda result: self._on_avatar_fetched(result),
            lambda _error: self._discard_pending(login),
        )

    def _fetch_avatar(self, login, avatar_url):
        try:
            url = avatar_url
            if not url and self.api is not None:
                profile = self.api.get_user_profile(login)
                url = str(profile.get("profile_image_url", "")) or ""
            if not url:
                return login, None
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return login, response.content
        except Exception:
            return login, None

    def _on_avatar_fetched(self, result):
        login, data = result
        self._discard_pending(login)
        if not data:
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            pixmap = pixmap.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            self._avatar_cache[login] = pixmap
            self._apply_avatar(login, pixmap)

    def _apply_avatar(self, login, pixmap):
        card = self._row_by_login.get(login)
        if card is None:
            return
        card.avatar_label.setPixmap(pixmap)
        card.avatar_label.setText("")

    def _discard_pending(self, login):
        self._pending_avatars.discard(login)
