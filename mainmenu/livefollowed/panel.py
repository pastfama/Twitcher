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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # Make the panel almost same visual size as currwatching
        self.setMinimumHeight(380)

        self.channel_list = QListWidget()
        # Use standard list mode - items will be full width
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
                padding: 4px;
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
        selected_login = None
        current_item = self.channel_list.currentItem()
        if current_item:
            current_stream = current_item.data(Qt.ItemDataRole.UserRole)
            if current_stream:
                selected_login = str(current_stream.get("user_login") or current_stream.get("user_name") or "").strip().lower()

        self.channel_list.clear()
        self._row_by_login = {}
        restore_index = -1

        for index, stream in enumerate(streams or []):
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
        # Make each item taller so the list takes more vertical space
        item.setSizeHint(QSize(0, 80))
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
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(10)

        avatar_label = QLabel("?")
        avatar_label.setFixedSize(46, 46)
        avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_label.setStyleSheet(f"background-color: {Theme.AVATAR_BG}; border: 1px solid {Theme.SECTION_BORDER}; border-radius: 23px; color: {Theme.DIM};")
        layout.addWidget(avatar_label)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        name_label = QLabel(str(name))
        name_label.setFont(QFont(Theme.FAMILY, 11, QFont.Weight.Bold))
        name_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        text_col.addWidget(name_label)

        info_label = QLabel(f"👁 {viewers:,}   🎮 {category}")
        info_label.setStyleSheet(f"color: {Theme.MUTED};")
        text_col.addWidget(info_label)

        analytics_line_parts = []
        momentum_status = ""

        if self._tracker and login:
            stats = self._tracker.get_channel_stats(login)
            if stats:
                momentum_status = stats.get("status") or ""
                percent = stats.get("percent") or 0
                analytics_line_parts.append(f"📊 {momentum_status} {percent:+.1f}%")

        sully = {}
        if self._analytics and login:
            sully = self._analytics.sullygoose_for(login, viewers) or {}

        if sully:
            growth = sully.get("viewer_growth", 0)
            analytics_line_parts.append(f"↗ {growth:+.1f}%")
            rank = sully.get("category_rank", 0)
            analytics_line_parts.append(f"🏆 #{rank}")

        analytics_label = QLabel("   ".join(analytics_line_parts) if analytics_line_parts else "📊 Waiting...")
        analytics_label.setStyleSheet(f"color: {Theme.CYAN};")
        text_col.addWidget(analytics_label)

        metrics_parts = []
        if sully:
            avg = sully.get("avg_viewers", 0)
            freq = sully.get("stream_frequency", 0)
            metrics_parts.append(f"Avg {avg:,}")
            if freq:
                metrics_parts.append(f"{freq:.0f}h/wk")
            score = self._analytics.calculate_score({"viewers": viewers, "status": momentum_status, "sullygoose": sully})
            metrics_parts.append(f"★ {score}")

        metrics_label = QLabel("  •  ".join(metrics_parts) if metrics_parts else "")
        metrics_label.setStyleSheet(f"color: {Theme.DIM};")
        text_col.addWidget(metrics_label)

        layout.addLayout(text_col, 1)
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
            # If we don't have an avatar URL and no API available, we can't fetch it
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
            pixmap = pixmap.scaled(46, 46, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
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