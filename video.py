# video.py

import os

import vlc
import qtawesome as qta

from PySide6.QtCore import (
    Qt,
    QEvent,
    QSettings,
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
    QMenu,
)


# ============================================================
# CONFIGURATION
# ============================================================

APP_ORGANIZATION = "Twitcher"
APP_NAME = "TwitcherVideoWindow"

DEFAULT_VOLUME = 38

SMALL_SIZE = (960, 540)
MEDIUM_SIZE = (1280, 720)
LARGE_SIZE = (1600, 900)


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

            "TWITCHER // STREAM MONITOR"

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
        # EVENT FILTERS
        # ====================================================

        self.installEventFilter(

            self

        )

        self.video_frame.installEventFilter(

            self

        )

        self.top_bar.installEventFilter(

            self

        )

        # ====================================================
        # RESTORE STATE
        # ====================================================

        self.restore_saved_state()

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

                background-color: #101019;

                border-top: 1px solid #29293d;

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

        main_layout = QVBoxLayout(

            self

        )

        main_layout.setContentsMargins(

            0,

            0,

            0,

            0

        )

        main_layout.setSpacing(

            0

        )

        # ====================================================
        # TOP BAR
        # ====================================================

        self.top_bar = QFrame()

        self.top_bar.setObjectName(

            "topBar"

        )

        top_layout = QHBoxLayout(

            self.top_bar

        )

        top_layout.setContentsMargins(

            14,

            8,

            14,

            8

        )

        self.title_label = QLabel(

            "TWITCHER // STREAM MONITOR"

        )

        self.title_label.setObjectName(

            "appTitle"

        )

        top_layout.addWidget(

            self.title_label

        )

        top_layout.addStretch()

        self.status_label = QLabel(

            "● READY"

        )

        self.status_label.setObjectName(

            "statusLabel"

        )

        top_layout.addWidget(

            self.status_label

        )

        main_layout.addWidget(

            self.top_bar

        )

        # ====================================================
        # VIDEO FRAME
        # ====================================================

        self.video_frame = QWidget()

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

        main_layout.addWidget(

            self.video_frame,

            1

        )

        # ====================================================
        # CONTROL BAR
        # ====================================================

        self.control_bar = QFrame()

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

        controls.setSpacing(

            6

        )

        # ====================================================
        # PLAY / PAUSE
        # ====================================================

        self.play_button = QPushButton()

        self.play_button.setObjectName(

            "mainButton"

        )

        self.play_button.setIcon(

            qta.icon(

                "fa5s.play"

            )

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

        # ====================================================
        # STOP
        # ====================================================

        self.stop_button = QPushButton()

        self.stop_button.setObjectName(

            "dangerButton"

        )

        self.stop_button.setIcon(

            qta.icon(

                "fa5s.stop"

            )

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

        # ====================================================
        # VOLUME DOWN
        # ====================================================

        self.volume_down_button = QPushButton()

        self.volume_down_button.setIcon(

            qta.icon(

                "fa5s.volume-down"

            )

        )

        self.volume_down_button.setToolTip(

            "Volume down"

        )

        self.volume_down_button.clicked.connect(

            self.volume_down

        )

        controls.addWidget(

            self.volume_down_button

        )

        # ====================================================
        # VOLUME SLIDER
        # ====================================================

        self.volume_slider = QSlider(

            Qt.Orientation.Horizontal

        )

        self.volume_slider.setRange(

            0,

            100

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

        # ====================================================
        # VOLUME LABEL
        # ====================================================

        self.volume_label = QLabel(

            f"{DEFAULT_VOLUME}%"

        )

        self.volume_label.setObjectName(

            "volumeLabel"

        )

        controls.addWidget(

            self.volume_label

        )

        # ====================================================
        # VOLUME UP
        # ====================================================

        self.volume_up_button = QPushButton()

        self.volume_up_button.setIcon(

            qta.icon(

                "fa5s.volume-up"

            )

        )

        self.volume_up_button.setToolTip(

            "Volume up"

        )

        self.volume_up_button.clicked.connect(

            self.volume_up

        )

        controls.addWidget(

            self.volume_up_button

        )

        # ====================================================
        # MUTE
        # ====================================================

        self.mute_button = QPushButton()

        self.mute_button.setIcon(

            qta.icon(

                "fa5s.volume-mute"

            )

        )

        self.mute_button.setToolTip(

            "Mute / Unmute (M)"

        )

        self.mute_button.clicked.connect(

            self.toggle_mute

        )

        controls.addWidget(

            self.mute_button

        )

        controls.addStretch()

        # ====================================================
        # SIZE MENU
        # ====================================================

        self.size_button = QPushButton(

            "SIZE"

        )

        self.size_button.setIcon(

            qta.icon(

                "fa5s.expand"

            )

        )

        self.size_button.setToolTip(

            "Window size"

        )

        self.size_button.clicked.connect(

            self.show_size_menu

        )

        controls.addWidget(

            self.size_button

        )

        # ====================================================
        # FIT
        # ====================================================

        self.fit_button = QPushButton()

        self.fit_button.setIcon(

            qta.icon(

                "fa5s.expand-arrows-alt"

            )

        )

        self.fit_button.setToolTip(

            "Fit to primary monitor"

        )

        self.fit_button.clicked.connect(

            self.fit_to_monitor

        )

        controls.addWidget(

            self.fit_button

        )

        # ====================================================
        # FULLSCREEN
        # ====================================================

        self.fullscreen_button = QPushButton()

        self.fullscreen_button.setIcon(

            qta.icon(

                "fa5s.expand-arrows-alt"

            )

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

        # ====================================================
        # MINIMIZE
        # ====================================================

        self.minimize_button = QPushButton()

        self.minimize_button.setIcon(

            qta.icon(

                "fa5s.window-minimize"

            )

        )

        self.minimize_button.setToolTip(

            "Minimize window"

        )

        self.minimize_button.clicked.connect(

            self.showMinimized

        )

        controls.addWidget(

            self.minimize_button

        )

        main_layout.addWidget(

            self.control_bar

        )

    # ========================================================
    # VLC
    # ========================================================

    def create_player(self):

        self.vlc_instance = vlc.Instance(

            "--no-video-title-show",

            "--quiet"

        )

        self.player = (

            self.vlc_instance

            .media_player_new()

        )

        self.player.audio_set_volume(

            DEFAULT_VOLUME

        )

    # ========================================================
    # START VIDEO
    # ========================================================

    def start_video(

        self,

        url

    ):

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

                self.vlc_instance

                .media_new(

                    url

                )

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

        if not self.video_frame:

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

    def set_status(

        self,

        text,

        color

    ):

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

            qta.icon(

                icon_name

            )

        )

    # ========================================================
    # STOP
    # ========================================================

    def stop_video(

        self,

        update_status=True

    ):

        if self.player:

            self.player.stop()

        self.media = None

        self.is_video_loaded = False

        self.is_paused = False

        self.is_muted = False

        self.play_button.setIcon(

            qta.icon(

                "fa5s.play"

            )

        )

        if update_status:

            self.set_status(

                "● STOPPED",

                "#e66f7a"

            )

    # ========================================================
    # VOLUME
    # ========================================================

    def set_volume(

        self,

        value

    ):

        value = max(

            0,

            min(

                100,

                int(value)

            )

        )

        self.volume_label.setText(

            f"{value}%"

        )

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

    # ========================================================
    # VOLUME ICON
    # ========================================================

    def update_volume_icon(

        self,

        value

    ):

        if self.is_muted or value == 0:

            icon_name = "fa5s.volume-mute"

        elif value < 40:

            icon_name = "fa5s.volume-down"

        else:

            icon_name = "fa5s.volume-up"

        self.mute_button.setIcon(

            qta.icon(

                icon_name

            )

        )

    # ========================================================
    # VOLUME UP
    # ========================================================

    def volume_up(self):

        self.volume_slider.setValue(

            min(

                100,

                self.volume_slider.value()

                + 5

            )

        )

    # ========================================================
    # VOLUME DOWN
    # ========================================================

    def volume_down(self):

        self.volume_slider.setValue(

            max(

                0,

                self.volume_slider.value()

                - 5

            )

        )

    # ========================================================
    # RESET VOLUME
    # ========================================================

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
    # SIZE MENU
    # ========================================================

    def show_size_menu(self):

        menu = QMenu(

            self

        )

        small_action = menu.addAction(

            "960 × 540   SMALL"

        )

        medium_action = menu.addAction(

            "1280 × 720   MEDIUM"

        )

        large_action = menu.addAction(

            "1600 × 900   LARGE"

        )

        action = menu.exec(

            self.size_button.mapToGlobal(

                self.size_button.rect().bottomLeft()

            )

        )

        if action == small_action:

            self.resize_small()

        elif action == medium_action:

            self.resize_medium()

        elif action == large_action:

            self.resize_large()

    # ========================================================
    # SHORTCUTS
    # ========================================================

    def create_shortcuts(self):

        QShortcut(

            QKeySequence(

                "Space"

            ),

            self,

            activated=self.toggle_pause

        )

        QShortcut(

            QKeySequence(

                "M"

            ),

            self,

            activated=self.toggle_mute

        )

        QShortcut(

            QKeySequence(

                "F"

            ),

            self,

            activated=self.toggle_fullscreen

        )

        QShortcut(

            QKeySequence(

                "F11"

            ),

            self,

            activated=self.toggle_fullscreen

        )

        QShortcut(

            QKeySequence(

                "Escape"

            ),

            self,

            activated=self.exit_fullscreen

        )

        QShortcut(

            QKeySequence(

                "Up"

            ),

            self,

            activated=self.volume_up

        )

        QShortcut(

            QKeySequence(

                "Down"

            ),

            self,

            activated=self.volume_down

        )

        QShortcut(

            QKeySequence(

                "Ctrl+0"

            ),

            self,

            activated=self.reset_volume

        )

    # ========================================================
    # RESIZE / CENTER
    # ========================================================

    def resize_and_center(

        self,

        width,

        height

    ):

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

    # ========================================================
    # PRESET SIZES
    # ========================================================

    def resize_small(self):

        self.resize_and_center(

            *SMALL_SIZE

        )

    def resize_medium(self):

        self.resize_and_center(

            *MEDIUM_SIZE

        )

    def resize_large(self):

        self.resize_and_center(

            *LARGE_SIZE

        )

    # ========================================================
    # FIT TO MONITOR
    # ========================================================

    def fit_to_monitor(self):

        screen = QApplication.primaryScreen()

        if not screen:

            return

        self.showNormal()

        self.setGeometry(

            screen.availableGeometry()

        )

        self.raise_()

        self.activateWindow()

    # ========================================================
    # PLACE ON PRIMARY MONITOR
    # ========================================================

    def place_on_primary_monitor(self):

        screen = QApplication.primaryScreen()

        if not screen:

            return

        geometry = screen.availableGeometry()

        width = int(

            geometry.width()

            * 0.90

        )

        height = int(

            geometry.height()

            * 0.90

        )

        self.resize_and_center(

            width,

            height

        )

    # ========================================================
    # FULLSCREEN
    # ========================================================

    def toggle_fullscreen(self):

        if self.isFullScreen():

            self.exit_fullscreen()

            return

        self.last_normal_geometry = (

            self.geometry()

        )

        self.showFullScreen()

        self.fullscreen_button.setIcon(

            qta.icon(

                "fa5s.compress-arrows-alt"

            )

        )

    # ========================================================
    # EXIT FULLSCREEN
    # ========================================================

    def exit_fullscreen(self):

        if not self.isFullScreen():

            return

        self.showNormal()

        self.fullscreen_button.setIcon(

            qta.icon(

                "fa5s.expand-arrows-alt"

            )

        )

        if self.last_normal_geometry:

            self.setGeometry(

                self.last_normal_geometry

            )

    # ========================================================
    # EVENT FILTER
    # ========================================================

    def eventFilter(

        self,

        watched,

        event

    ):

        if event.type() == QEvent.Type.MouseButtonDblClick:

            if (

                watched == self.top_bar

                or watched == self.video_frame

            ):

                self.toggle_fullscreen()

                return True

        if event.type() == QEvent.Type.KeyPress:

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

        if saved_geometry:

            restored = self.restoreGeometry(

                saved_geometry

            )

            if not restored:

                self.resize_and_center(

                    *MEDIUM_SIZE

                )

        else:

            self.resize_and_center(

                *MEDIUM_SIZE

            )

        saved_volume = self.settings.value(

            "volume"

        )

        if saved_volume is not None:

            try:

                volume = int(

                    saved_volume

                )

                volume = max(

                    0,

                    min(

                        100,

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

                pass

    # ========================================================
    # SAVE STATE
    # ========================================================

    def save_window_state(self):

        if not self.isFullScreen():

            self.settings.setValue(

                "geometry",

                self.saveGeometry()

            )

        self.settings.setValue(

            "volume",

            self.volume_slider.value()

        )

        self.settings.sync()

    # ========================================================
    # CLOSE
    # ========================================================

    def closeEvent(

        self,

        event

    ):

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