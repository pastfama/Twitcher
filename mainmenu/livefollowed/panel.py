"""Live Followed Channels panel — displays live followed streams."""

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
)

from core import run_in_background
from ..theme import Theme


class LiveFollowedPanel(QGroupBox):

    channel_selected = Signal(object)
    watch_requested = Signal(str)

    def __init__(self, api=None, analytics_engine=None):
        debug("LiveFollowedPanel.__init__ called")
        super().__init__("LIVE FOLLOWED CHANNELS")
        self.setStyleSheet(Theme.group_box_style(Theme.GREEN))

        self.api = api
        self._tracker = None
        self._analytics = analytics_engine
        self._avatar_cache = {}
        self._pending_avatars = set()
        self._row_by_login = {}
        self._all_streams = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.setMinimumHeight(380)

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

        # --- Column headers ---
        headers_row = QHBoxLayout()
        headers_row.setContentsMargins(52, 0, 6, 0)
        headers_row.setSpacing(0)

        for text, width in [
            ("CHANNEL", None),
            ("VIEWERS", 60),
            ("CATEGORY", None),
            ("GROWTH", 55),
            ("SCORE", 40),
        ]:
            lbl = QLabel(text)
            lbl.setFont(QFont(Theme.FAMILY, 7, QFont.Weight.Bold))
            lbl.setStyleSheet(f"color: {Theme.GAME_DIM}; padding: 2px 0;")
            if width:
                lbl.setFixedWidth(width)
            headers_row.addWidget(lbl)

        layout.addLayout(headers_row)

        # --- Channel list ---
        self.channel_list = QListWidget()
        self.channel_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.channel_list.setSpacing(1)
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
        item.setSizeHint(QSize(0, 52))
        self.channel_list.addItem(item)

        row = self._build_row_widget(stream, name, viewers, category, login)
        self.channel_list.setItemWidget(item, row)

        if login:
            self._row_by_login[login] = row
            self._ensure_avatar(login, stream.get("avatar_url"))

    def _build_row_widget(self, stream, name, viewers, category, login):
        widget = QWidget()
        widget.setObjectName("FollowedRow")
        widget.setStyleSheet("QWidget#FollowedRow { background: transparent; }")

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 3, 6, 3)
        layout.setSpacing(8)

        # --- Avatar ---
        avatar_label = QLabel("?")
        avatar_label.setFixedSize(38, 38)
        avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_label.setStyleSheet(f"""
            background-color: {Theme.AVATAR_BG};
            border: 1px solid {Theme.SECTION_BORDER};
            border-radius: 19px;
            color: {Theme.DIM};
            font-size: 11px;
        """)
        layout.addWidget(avatar_label)

        # --- Channel name ---
        name_label = QLabel(str(name))
        name_label.setFont(QFont(Theme.FAMILY, 11, QFont.Weight.Bold))
        name_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        name_label.setFixedWidth(100)
        layout.addWidget(name_label)

        # --- Viewers ---
        viewers_label = QLabel(f"{viewers:,}")
        viewers_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px;")
        viewers_label.setFixedWidth(60)
        layout.addWidget(viewers_label)

        # --- Category ---
        cat_label = QLabel(category)
        cat_label.setStyleSheet(f"color: {Theme.MUTED}; font-size: 10px;")
        layout.addWidget(cat_label, 1)

        # --- Growth ---
        growth_parts = []
        if self._tracker and login:
            stats = self._tracker.get_channel_stats(login)
            if stats:
                percent = stats.get("percent") or 0
                growth_parts.append(f"{percent:+.1f}%")

        sully = {}
        platform = stream.get("platform", "twitch")
        if self._analytics and login:
            sully = self._analytics.sullygoose_for(login, viewers, platform=platform) or {}
        if sully:
            growth = sully.get("viewer_growth", 0)
            if growth is not None:
                growth_parts.append(f"{growth:+.1f}%")

        growth_text = growth_parts[0] if growth_parts else "--"
        growth_label = QLabel(growth_text)
        is_positive = growth_text.startswith("+") and growth_text != "+0.0%"
        is_negative = growth_text.startswith("-")
        if is_positive:
            growth_label.setStyleSheet(f"color: {Theme.GREEN}; font-size: 10px; font-weight: bold;")
        elif is_negative:
            growth_label.setStyleSheet(f"color: {Theme.RED_DARK}; font-size: 10px; font-weight: bold;")
        else:
            growth_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 10px;")
        growth_label.setFixedWidth(55)
        layout.addWidget(growth_label)

        # --- Score ---
        score_text = "--"
        if self._analytics and sully:
            score = self._analytics.calculate_score({"viewers": viewers, "sullygoose": sully})
            score_text = str(score)
        score_label = QLabel(score_text)
        score_label.setStyleSheet(f"color: {Theme.CYAN}; font-size: 10px; font-weight: bold;")
        score_label.setFixedWidth(40)
        layout.addWidget(score_label)

        widget.avatar_label = avatar_label
        widget.login = login
        widget.stream = stream
        return widget

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
            pixmap = pixmap.scaled(38, 38, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            self._avatar_cache[login] = pixmap
            self._apply_avatar(login, pixmap)

    def _apply_avatar(self, login, pixmap):
        row = self._row_by_login.get(login)
        if row is None:
            return
        row.avatar_label.setPixmap(pixmap)
        row.avatar_label.setText("")

    def _discard_pending(self, login):
        self._pending_avatars.discard(login)