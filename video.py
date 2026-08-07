import os
import sys

import vlc
import qtawesome as qta

from PySide6.QtCore import (
    Qt,
    QEvent,
    QSettings,
    QTimer,
)

from PySide6.QtGui import (
    QKeySequence,
    QShortcut,
)

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSlider,
    QFrame,
    QSizePolicy,
)

from logger import debug, info, warning, error

from core.db import get_recent_channels as load_channels, store_channel_played as save_channel
from core.stream_resolver import resolve_stream_url, StreamResolverError


# ============================================================
# CONFIGURATION
# ============================================================

APP_ORGANIZATION = "Watcher"
APP_NAME = "WatcherVideoWindow"

DEFAULT_VOLUME = 38

SMALL_SIZE = (900, 550)
MEDIUM_SIZE = (1200, 720)


# ============================================================
# VIDEO WINDOW
# ============================================================


class VideoWindow(QWidget):

    def __init__(self):

        super().__init__()

        # ====================================================
        # STATE
        # ====================================================

        self.player = None
        self.media = None
        self.vlc_instance = None

        self.is_video_loaded = False
        self.is_paused = False
        self.is_muted = False

        self.previous_volume = DEFAULT_VOLUME

        self.last_normal_geometry = None
        self.is_closing = False

        # ====================================================
        # FULLSCREEN OVERLAY STATE
        # ====================================================

        self.fullscreen_controls_visible = False

        # ====================================================
        # SETTINGS
        # ====================================================

        self.settings = QSettings(
            APP_ORGANIZATION,
            APP_NAME
        )

        # ====================================================
        # WINDOW
        # ====================================================

        self.setWindowTitle(
            "WATCHER // STREAM MONITOR"
        )

        self.setMinimumSize(
            900,
            550
        )

        # ====================================================
        # UI
        # ====================================================

        self.build_ui()

        # ====================================================
        # VLC
        # ====================================================

        self.create_player()

        # ====================================================
        # SHORTCUTS
        # ====================================================

        self.create_shortcuts()

        # ====================================================
        # MOUSE TRACKING
        # ====================================================

        self.setMouseTracking(True)

        self.video_frame.setMouseTracking(True)

        self.installEventFilter(self)

        self.video_frame.installEventFilter(self)

        self.control_bar.installEventFilter(self)

        # ====================================================
        # FULLSCREEN HIDE TIMER
        # ====================================================

        self.fullscreen_hide_timer = QTimer(self)

        self.fullscreen_hide_timer.setSingleShot(True)

        self.fullscreen_hide_timer.timeout.connect(
            self.hide_fullscreen_controls
        )

        # ====================================================
        # RESTORE STATE
        # ====================================================

        self.restore_saved_state()

        # ====================================================
        # RECENT CHANNELS (auth-independent)
        # ====================================================

        self.current_channel = ""
        self.recent_channels = load_channels()

    # ========================================================
    # UI
    # ========================================================

    def build_ui(self):

        self.setStyleSheet(

            """

            QWidget {

                background-color: #08080d;

                color: #f2f2f2;

                font-family: "Segoe UI";

            }


            QFrame#topBar {

                background-color: #101019;

                border-bottom: 1px solid #29293d;

            }


            QFrame#controlBar {

                background-color: rgba(16, 16, 25, 180);

                border: 1px solid rgba(41, 41, 61, 150);

                border-radius: 10px;

            }


            QFrame#fullscreenOverlay {

                background-color: rgba(10, 10, 18, 235);

                border: 1px solid #353553;

                border-radius: 10px;

            }


            QLabel#appTitle {

                color: #b7a7ff;

                font-size: 15px;

                font-weight: bold;

            }


            QLabel#statusLabel {

                color: #75e6a5;

                font-size: 12px;

                font-weight: bold;

            }


            QLabel#volumeLabel {

                color: #aaaaaa;

                font-size: 12px;

                min-width: 42px;

            }


            QPushButton {

                background-color: #181827;

                border: 1px solid #32324d;

                border-radius: 6px;

                color: #eeeeee;

                padding: 7px 10px;

                font-size: 12px;

            }


            QPushButton:hover {

                background-color: #272741;

                border: 1px solid #625d9a;

            }


            QPushButton:pressed {

                background-color: #10101b;

            }


            QPushButton#mainButton {

                background-color: #30275c;

                border: 1px solid #7166b3;

            }


            QPushButton#mainButton:hover {

                background-color: #45377e;

            }


            QPushButton#dangerButton {

                background-color: #28171d;

                border: 1px solid #66333e;

            }


            QPushButton#dangerButton:hover {

                background-color: #45222c;

            }


            QSlider::groove:horizontal {

                height: 4px;

                background: #29293d;

                border-radius: 2px;

            }


            QSlider::handle:horizontal {

                width: 14px;

                height: 14px;

                margin: -5px 0;

                background: #9b8cff;

                border-radius: 7px;

            }


            QSlider::sub-page:horizontal {

                background: #7166b3;

                border-radius: 2px;

            }

            """

        )

        # ====================================================
        # MAIN LAYOUT
        # ====================================================

        # We use no main layout to allow manual positioning of overlays
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # ====================================================
        # VIDEO FRAME
        # ====================================================

        self.video_frame = QWidget(self)

        self.video_frame.setAttribute(
            Qt.WidgetAttribute.WA_NativeWindow
        )

        self.video_frame.setAttribute(
            Qt.WidgetAttribute.WA_OpaquePaintEvent
        )

        self.video_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        self.video_frame.setStyleSheet(
            "background-color: #000000;"
        )

        self.main_layout.addWidget(
            self.video_frame
        )

        # ====================================================
        # NORMAL CONTROL BAR (OVERLAY)
        # ====================================================

        self.control_bar = QFrame(self)

        self.control_bar.setObjectName(
            "controlBar"
        )

        controls = QHBoxLayout(
            self.control_bar
        )

        controls.setContentsMargins(
            10,
            8,
            10,
            8
        )

        controls.setSpacing(6)

        # PLAY / PAUSE

        self.play_button = QPushButton()

        self.play_button.setObjectName(
            "mainButton"
        )

        self.play_button.setIcon(
            qta.icon("fa5s.play")
        )

        self.play_button.setToolTip(
            "Play / Pause (Space)"
        )

        self.play_button.clicked.connect(
            self.toggle_pause
        )

        controls.addWidget(
            self.play_button
        )

        # STOP

        self.stop_button = QPushButton()

        self.stop_button.setObjectName(
            "dangerButton"
        )

        self.stop_button.setIcon(
            qta.icon("fa5s.stop")
        )

        self.stop_button.setToolTip(
            "Stop video"
        )

        self.stop_button.clicked.connect(
            self.stop_video
        )

        controls.addWidget(
            self.stop_button
        )

        # VOLUME DOWN

        self.volume_down_button = QPushButton()

        self.volume_down_button.setIcon(
            qta.icon("fa5s.volume-down")
        )

        self.volume_down_button.clicked.connect(
            self.volume_down
        )

        controls.addWidget(
            self.volume_down_button
        )

        # VOLUME SLIDER

        self.volume_slider = QSlider(
            Qt.Orientation.Horizontal
        )

        self.volume_slider.setRange(
            0,
            200
        )

        self.volume_slider.setValue(
            DEFAULT_VOLUME
        )

        self.volume_slider.setMinimumWidth(
            140
        )

        self.volume_slider.setMaximumWidth(
            260
        )

        self.volume_slider.valueChanged.connect(
            self.set_volume
        )

        controls.addWidget(
            self.volume_slider
        )

        # VOLUME LABEL

        self.volume_label = QLabel(
            f"{DEFAULT_VOLUME}%"
        )

        self.volume_label.setObjectName(
            "volumeLabel"
        )

        controls.addWidget(
            self.volume_label
        )

        # VOLUME UP

        self.volume_up_button = QPushButton()

        self.volume_up_button.setIcon(
            qta.icon("fa5s.volume-up")
        )

        self.volume_up_button.clicked.connect(
            self.volume_up
        )

        controls.addWidget(
            self.volume_up_button
        )

        # MUTE

        self.mute_button = QPushButton()

        self.mute_button.setIcon(
            qta.icon("fa5s.volume-mute")
        )

        self.mute_button.clicked.connect(
            self.toggle_mute
        )

        controls.addWidget(
            self.mute_button
        )

        controls.addStretch()

        # STATUS

        self.status_label = QLabel(
            "● IDLE"
        )

        self.status_label.setObjectName(
            "statusLabel"
        )

        controls.addWidget(
            self.status_label
        )

        controls.addStretch()

        # SMALL SIZE

        self.small_button = QPushButton(
            "S"
        )

        self.small_button.setToolTip(
            "Small window: 900 × 550"
        )

        self.small_button.clicked.connect(
            self.resize_small
        )

        controls.addWidget(
            self.small_button
        )

        # MEDIUM SIZE

        self.medium_button = QPushButton(
            "M"
        )

        self.medium_button.setToolTip(
            "Medium window: 1200 × 720"
        )

        self.medium_button.clicked.connect(
            self.resize_medium
        )

        controls.addWidget(
            self.medium_button
        )

        # FULLSCREEN

        self.fullscreen_button = QPushButton(
            "FS"
        )

        self.fullscreen_button.setToolTip(
            "Fullscreen (F11 / F)"
        )

        self.fullscreen_button.clicked.connect(
            self.toggle_fullscreen
        )

        controls.addWidget(
            self.fullscreen_button
        )

        # Do NOT add to layout, we will position it manually

        # ====================================================
        # FULLSCREEN FLOATING VOLUME CONTROLS
        # ====================================================

        self.fullscreen_overlay = QFrame(
            self
        )

        self.fullscreen_overlay.setObjectName(
            "fullscreenOverlay"
        )

        self.fullscreen_overlay.setWindowFlags(
            Qt.WindowType.Widget
        )

        overlay_layout = QHBoxLayout(
            self.fullscreen_overlay
        )

        overlay_layout.setContentsMargins(
            8,
            6,
            8,
            6
        )

        overlay_layout.setSpacing(5)

        self.fullscreen_mute_button = QPushButton()

        self.fullscreen_mute_button.setIcon(
            qta.icon("fa5s.volume-up")
        )

        self.fullscreen_mute_button.setToolTip(
            "Mute / Unmute"
        )

        self.fullscreen_mute_button.clicked.connect(
            self.toggle_mute
        )

        overlay_layout.addWidget(
            self.fullscreen_mute_button
        )

        self.fullscreen_volume_slider = QSlider(
            Qt.Orientation.Horizontal
        )

        self.fullscreen_volume_slider.setRange(
            0,
            200
        )

        self.fullscreen_volume_slider.setMinimumWidth(
            150
        )

        self.fullscreen_volume_slider.setMaximumWidth(
            220
        )

        self.fullscreen_volume_slider.setValue(
            DEFAULT_VOLUME
        )

        self.fullscreen_volume_slider.valueChanged.connect(
            self.set_volume_from_fullscreen
        )

        overlay_layout.addWidget(
            self.fullscreen_volume_slider
        )

        self.fullscreen_volume_label = QLabel(
            f"{DEFAULT_VOLUME}%"
        )

        self.fullscreen_volume_label.setObjectName(
            "volumeLabel"
        )

        overlay_layout.addWidget(
            self.fullscreen_volume_label
        )

        self.fullscreen_overlay.hide()

    # ========================================================
    # AUTH-INDEPENDENT CHANNEL PLAYBACK
    # ========================================================

    def get_player_state(self):
        """Return {'playing': bool} or None if unavailable."""
        try:
            if self.player:
                state = self.player.get_state()
                return {"playing": state == vlc.State.Playing}
        except Exception:
            pass
        return None

    def start_channel(self, channel, platform=None):
        """Resolve and play *channel* with no Twitch auth (streamlink).

        Records the channel in the last-10 history text file.

        Args:
            channel: Channel name, URL, or a dict with 'channel'/'platform'.
            platform: Optional platform name (twitch, kick, youtube).
        """
        if isinstance(channel, dict):
            platform = channel.get("platform") or platform
            channel = channel.get("channel") or channel.get("login") or ""

        channel = str(channel or "").strip().lstrip("#").lower()
        if not channel:
            debug("[VIDEO] start_channel called with empty channel")
            return False

        if not platform:
            from platforms import detect_platform
            platform = detect_platform(channel)

        # Strip explicit platform prefixes ("kick:xqc" -> "xqc").
        from platforms import strip_platform_prefix
        channel = strip_platform_prefix(channel).lstrip("#").lower()
        if not channel:
            debug("[VIDEO] start_channel called with empty channel after prefix strip")
            return False

        debug(f"[VIDEO] Resolving channel '{channel}' ({platform}) (auth-free)...")
        try:
            url = resolve_stream_url(channel, platform_name=platform)
        except StreamResolverError as exc:
            self.set_status("\u25cf NO STREAM", "#e66f7a")
            debug(f"[VIDEO] Could not resolve '{channel}': {exc}")
            return False

        ok = self.start_video(url)
        if ok:
            self.current_channel = channel
            self.recent_channels = load_channels()
            self.setWindowTitle(f"WATCHER // {channel}")
            debug(f"[VIDEO] Now playing '{channel}' ({platform}) (auth-free)")
        return ok

    def play_last_channels(self):
        """Try the last 10 played channels one-by-one until one plays.

        Returns True if a channel started, False if none were resolvable.
        """
        channels = load_channels()
        if not channels:
            debug("[VIDEO] No recent channels to try")
            self.set_status("\u25cf NO HISTORY", "#e6c875")
            return False

        debug(f"[VIDEO] Trying {len(channels)} recent channels: {channels}")
        for channel in channels:
            debug(f"[VIDEO] Trying last channel '{channel}'...")
            if self.start_channel(channel):
                return True
        debug("[VIDEO] None of the recent channels could be played")
        self.set_status("\u25cf ALL OFFLINE", "#e66f7a")
        return False

    # ========================================================
    # VLC
    # ========================================================

    def create_player(self):

        self.vlc_instance = vlc.Instance(
            "--no-video-title-show",
            "--quiet"
        )

        self.player = (
            self.vlc_instance.media_player_new()
        )

        self.player.audio_set_volume(
            DEFAULT_VOLUME
        )

    # ========================================================
    # START VIDEO
    # ========================================================

    def start_video(self, url):

        if not url:

            self.set_status(
                "● NO URL",
                "#e66f7a"
            )

            return False

        try:

            self.stop_video(
                update_status=False
            )

            self.set_status(
                "● LOADING",
                "#e6c875"
            )

            self.media = (
                self.vlc_instance.media_new(url)
            )

            self.player.set_media(
                self.media
            )

            self.attach_video()

            result = self.player.play()

            if result == -1:

                self.set_status(
                    "● PLAYBACK ERROR",
                    "#e66f7a"
                )

                return False

            self.player.audio_set_volume(
                self.volume_slider.value()
            )

            self.is_video_loaded = True

            self.is_paused = False

            self.is_muted = False

            self.update_play_button()

            self.update_volume_icon(
                self.volume_slider.value()
            )

            self.set_status(
                "● PLAYING",
                "#75e6a5"
            )

            self.show()

            self.raise_()

            self.activateWindow()

            return True

        except Exception as error:

            self.set_status(
                "● ERROR",
                "#e66f7a"
            )

            print(
                f"[VIDEO] Could not start video: {error}"
            )

            return False

    # ========================================================
    # ATTACH VIDEO
    # ========================================================

    def attach_video(self):

        if not self.player:

            return

        window_id = int(
            self.video_frame.winId()
        )

        if os.name == "nt":

            self.player.set_hwnd(
                window_id
            )

        elif sys.platform == "linux":

            self.player.set_xwindow(
                window_id
            )

        elif sys.platform == "darwin":

            self.player.set_nsobject(
                window_id
            )

    # ========================================================
    # STATUS
    # ========================================================

    def set_status(self, text, color):

        self.status_label.setText(
            text
        )

        self.status_label.setStyleSheet(
            f"color: {color};"
        )

    # ========================================================
    # PLAY / PAUSE
    # ========================================================

    def toggle_pause(self):

        if not self.player:
            return

        if not self.is_video_loaded:
            return

        if self.player.is_playing():

            self.player.pause()

            self.is_paused = True

            self.set_status(
                "● PAUSED",
                "#e6c875"
            )

        else:

            self.player.play()

            self.is_paused = False

            self.set_status(
                "● PLAYING",
                "#75e6a5"
            )

        self.update_play_button()

    # ========================================================
    # PLAY BUTTON
    # ========================================================

    def update_play_button(self):

        if self.is_paused:

            icon_name = "fa5s.play"

        else:

            icon_name = "fa5s.pause"

        self.play_button.setIcon(
            qta.icon(icon_name)
        )

    # ========================================================
    # STOP
    # ========================================================

    def stop_video(self, update_status=True):

        if self.player:

            self.player.stop()

        self.media = None

        self.is_video_loaded = False

        self.is_paused = False

        self.is_muted = False

        self.play_button.setIcon(
            qta.icon("fa5s.play")
        )

        if update_status:

            self.set_status(
                "● STOPPED",
                "#e66f7a"
            )

    # ========================================================
    # VOLUME
    # ========================================================

    def set_volume(self, value):

        value = max(
            0,
            min(
                200,
                int(value)
            )
        )

        self.volume_label.setText(
            f"{value}%"
        )

        self.fullscreen_volume_label.setText(
            f"{value}%"
        )

        self.fullscreen_volume_slider.blockSignals(True)

        self.fullscreen_volume_slider.setValue(
            value
        )

        self.fullscreen_volume_slider.blockSignals(False)

        if value > 0:

            self.previous_volume = value

        if self.player:

            self.player.audio_set_volume(
                value
            )

            if self.is_muted:

                self.player.audio_set_mute(
                    False
                )

                self.is_muted = False

        self.update_volume_icon(
            value
        )

    def set_volume_from_fullscreen(self, value):

        self.volume_slider.setValue(
            value
        )

    # ========================================================
    # VOLUME ICON
    # ========================================================

    def update_volume_icon(self, value):

        if self.is_muted or value == 0:

            icon_name = "fa5s.volume-mute"

        elif value < 40:

            icon_name = "fa5s.volume-down"

        else:

            icon_name = "fa5s.volume-up"

        icon = qta.icon(
            icon_name
        )

        self.mute_button.setIcon(
            icon
        )

        self.fullscreen_mute_button.setIcon(
            icon
        )

    # ========================================================
    # VOLUME UP / DOWN
    # ========================================================

    def volume_up(self):

        self.volume_slider.setValue(
            min(
                200,
                self.volume_slider.value() + 5
            )
        )

    def volume_down(self):

        self.volume_slider.setValue(
            max(
                0,
                self.volume_slider.value() - 5
            )
        )

    def reset_volume(self):

        self.volume_slider.setValue(
            DEFAULT_VOLUME
        )

    # ========================================================
    # MUTE
    # ========================================================

    def toggle_mute(self):

        if not self.player:

            return

        if self.is_muted:

            self.player.audio_set_mute(
                False
            )

            self.is_muted = False

            self.volume_slider.setValue(
                self.previous_volume
            )

        else:

            current_volume = (
                self.volume_slider.value()
            )

            if current_volume > 0:

                self.previous_volume = current_volume

            self.player.audio_set_mute(
                True
            )

            self.is_muted = True

        self.update_volume_icon(
            self.volume_slider.value()
        )

    # ========================================================
    # SHORTCUTS
    # ========================================================

    def create_shortcuts(self):

        QShortcut(
            QKeySequence("Space"),
            self,
            activated=self.toggle_pause
        )

        QShortcut(
            QKeySequence("M"),
            self,
            activated=self.toggle_mute
        )

        QShortcut(
            QKeySequence("F"),
            self,
            activated=self.toggle_fullscreen
        )

        QShortcut(
            QKeySequence("F11"),
            self,
            activated=self.toggle_fullscreen
        )

        QShortcut(
            QKeySequence("Escape"),
            self,
            activated=self.exit_fullscreen
        )

        QShortcut(
            QKeySequence("Up"),
            self,
            activated=self.volume_up
        )

        QShortcut(
            QKeySequence("Down"),
            self,
            activated=self.volume_down
        )

        QShortcut(
            QKeySequence("Ctrl+0"),
            self,
            activated=self.reset_volume
        )

    # ========================================================
    # RESIZE / CENTER
    # ========================================================

    def resize_and_center(self, width, height):

        screen = QApplication.primaryScreen()

        if not screen:

            return

        geometry = screen.availableGeometry()

        width = min(
            width,
            geometry.width()
        )

        height = min(
            height,
            geometry.height()
        )

        x = (
            geometry.x()
            + (
                geometry.width()
                - width
            )
            // 2
        )

        y = (
            geometry.y()
            + (
                geometry.height()
                - height
            )
            // 2
        )

        self.showNormal()

        self.setGeometry(
            x,
            y,
            width,
            height
        )

        self.raise_()

        self.activateWindow()


    def resize_preserve_position(self, width, height):

        screen = QApplication.primaryScreen()

        if not screen:

            return


        geometry = screen.availableGeometry()

        width = min(

            width,

            geometry.width()

        )

        height = min(

            height,

            geometry.height()

        )

        x = self.x()

        y = self.y()

        max_x = geometry.x() + geometry.width() - width

        max_y = geometry.y() + geometry.height() - height

        x = max(

            geometry.x(),

            min(x, max_x)

        )

        y = max(

            geometry.y(),

            min(y, max_y)

        )

        self.showNormal()

        self.setGeometry(

            x,

            y,

            width,

            height

        )

        self.raise_()

        self.activateWindow()

    # ========================================================
    # PRESET SIZES
    # ========================================================

    def resize_small(self):

        self.resize_preserve_position(
            *SMALL_SIZE
        )

    def resize_medium(self):

        self.resize_preserve_position(
            *MEDIUM_SIZE
        )

    # ========================================================
    # FULLSCREEN
    # ========================================================

    def toggle_fullscreen(self):

        if self.isFullScreen():

            self.exit_fullscreen()

            return

        self.last_normal_geometry = self.geometry()

        self.showFullScreen()

        self.control_bar.hide()

        self.show_fullscreen_controls()

    def exit_fullscreen(self):

        if not self.isFullScreen():

            return

        self.hide_fullscreen_controls()

        self.showNormal()

        self.control_bar.show()

        if self.last_normal_geometry:

            self.setGeometry(
                self.last_normal_geometry
            )

    # ========================================================
    # FULLSCREEN CONTROLS
    # ========================================================

    def show_fullscreen_controls(self):

        if not self.isFullScreen():

            return

        self.fullscreen_overlay.adjustSize()

        margin = 24

        self.fullscreen_overlay.move(

            self.width()
            - self.fullscreen_overlay.width()
            - margin,

            self.height()
            - self.fullscreen_overlay.height()
            - margin

        )

        self.fullscreen_overlay.show()

        self.fullscreen_overlay.raise_()

        self.fullscreen_controls_visible = True

        self.fullscreen_hide_timer.start(
            2500
        )

    def hide_fullscreen_controls(self):

        self.fullscreen_hide_timer.stop()

        self.fullscreen_overlay.hide()

        self.fullscreen_controls_visible = False

    # ========================================================
    # OVERLAY POSITIONING
    # ========================================================

    def resizeEvent(self, event):

        super().resizeEvent(event)

        # ----------------------------------------------------
        # POSITION CONTROL BAR
        # ----------------------------------------------------

        if self.control_bar:

            margin = 20

            self.control_bar.adjustSize()

            bar_width = min(
                self.width() - (margin * 2),
                800
            )

            bar_height = self.control_bar.height()

            self.control_bar.setGeometry(
                (self.width() - bar_width) // 2,
                self.height() - bar_height - margin,
                bar_width,
                bar_height
            )

            self.control_bar.raise_()

    # ========================================================
    # EVENT FILTER
    # ========================================================

    def eventFilter(self, watched, event):

        if event.type() == QEvent.Type.MouseMove:

            if self.isFullScreen():

                self.show_fullscreen_controls()

        elif event.type() == QEvent.Type.Resize:

            if self.isFullScreen():

                if self.fullscreen_controls_visible:

                    self.fullscreen_overlay.adjustSize()

                    margin = 24

                    self.fullscreen_overlay.move(

                        self.width()
                        - self.fullscreen_overlay.width()
                        - margin,

                        self.height()
                        - self.fullscreen_overlay.height()
                        - margin

                    )

        elif event.type() == QEvent.Type.KeyPress:

            if event.key() == Qt.Key.Key_Escape:

                if self.isFullScreen():

                    self.exit_fullscreen()

                    return True

        return super().eventFilter(
            watched,
            event
        )

    # ========================================================
    # RESTORE STATE
    # ========================================================

    def restore_saved_state(self):

        saved_geometry = self.settings.value(
            "geometry"
        )

        debug(f"Restoring video window state: geometry={saved_geometry}")

        if saved_geometry:

            restored = self.restoreGeometry(
                saved_geometry
            )

            debug(f"restoreGeometry returned {restored}")

            if not restored:

                self.resize_and_center(
                    *MEDIUM_SIZE
                )

        else:

            debug("No saved geometry found; using medium default")
            self.resize_and_center(
                *MEDIUM_SIZE
            )

        saved_volume = self.settings.value(
            "volume"
        )

        debug(f"Restoring video volume: {saved_volume}")

        if saved_volume is not None:

            try:

                volume = int(
                    saved_volume
                )

                volume = max(
                    0,
                    min(
                        200,
                        volume
                    )
                )

                self.volume_slider.setValue(
                    volume
                )

                self.previous_volume = volume

            except (
                ValueError,
                TypeError
            ):

                warning("Invalid saved volume; ignoring")


    # Alias for older restore method names.
    restore_saved_geometry = restore_saved_state

    # ========================================================
    # SAVE STATE
    # ========================================================

    def save_window_state(self):

        if not self.isFullScreen():
            geometry_value = self.saveGeometry()
            debug(f"Saving video window geometry: {geometry_value}")
            self.settings.setValue(
                "geometry",
                geometry_value
            )

        volume_value = self.volume_slider.value()
        debug(f"Saving video volume: {volume_value}")
        self.settings.setValue(
            "volume",
            volume_value
        )

        self.settings.sync()

    # ========================================================
    # CLOSE
    # ========================================================

    def closeEvent(self, event):

        if self.is_closing:

            event.accept()

            return

        self.is_closing = True

        self.save_window_state()

        self.stop_video()

        if self.player:

            self.player.release()

            self.player = None

        if self.vlc_instance:

            self.vlc_instance.release()

            self.vlc_instance = None

        event.accept()