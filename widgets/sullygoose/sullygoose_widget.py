"""SullyGoose analytics widget for the Current Watching panel."""

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class ValueLabel(QWidget):
    """Small label with a title and large value."""

    def __init__(
        self,
        title="",
        value="",
        parent=None,
    ):

        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.title_label = QLabel(
            title
        )

        self.title_label.setStyleSheet(
            "color: #888899; font-size: 11px;"
        )

        self.value_label = QLabel(
            str(value)
        )

        self.value_label.setStyleSheet(
            "color: #f2f2f2; font-size: 18px; font-weight: bold;"
        )

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.value_label
        )

    def set_value(self, value):

        self.value_label.setText(
            str(value)
        )


class SullyGooseWidget(QFrame):

    def __init__(
        self,
        parent=None,
    ):

        super().__init__(parent)

        self.setObjectName(
            "sullygoosePanel"
        )

        self.setStyleSheet(
            """
            QFrame#sullygoosePanel {
                background-color: #0e0e18;
                border: 1px solid #29293d;
                border-radius: 10px;
            }
            """
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            12,
            12,
            12,
            12
        )
        main_layout.setSpacing(8)

        # Title

        title = QLabel(
            "📊 SullyGoose Analytics"
        )

        title.setStyleSheet(
            "color: #b7a7ff; font-size: 13px; font-weight: bold;"
        )

        main_layout.addWidget(title)

        # Metrics row

        metrics = QHBoxLayout()
        metrics.setSpacing(12)

        self.avg_label = ValueLabel(
            "Avg Viewers",
            "—"
        )

        self.peak_label = ValueLabel(
            "Peak Viewers",
            "—"
        )

        self.growth_label = ValueLabel(
            "Growth",
            "—"
        )

        self.followers_label = ValueLabel(
            "Followers",
            "—"
        )

        self.follower_growth_label = ValueLabel(
            "Follower Growth",
            "—"
        )

        metrics.addWidget(
            self.avg_label
        )

        metrics.addWidget(
            self.peak_label
        )

        metrics.addWidget(
            self.growth_label
        )

        metrics.addWidget(
            self.followers_label
        )

        metrics.addWidget(
            self.follower_growth_label
        )

        main_layout.addLayout(
            metrics
        )

    def update_metrics(self, sully, analysis=None):

        if not sully:
            self._clear()
            return

        avg = sully.get(
            "avg_viewers",
            0
        )

        peak = sully.get(
            "peak_viewers",
            0
        )

        growth = sully.get(
            "viewer_growth"
        )

        followers = sully.get(
            "followers",
            0
        )

        f_growth = sully.get(
            "follower_growth"
        )

        self.avg_label.set_value(
            f"{avg:,}"
        )

        self.peak_label.set_value(
            f"{peak:,}"
        )

        # Guard against None before formatting.
        safe_growth = (
            growth
            if growth is not None
            else 0.0
        )

        self.growth_label.set_value(
            f"{safe_growth:+.1f}%"
        )

        self._color_value(
            self.growth_label.value_label,
            safe_growth
        )

        self.followers_label.set_value(
            f"{followers:,}"
        )

        safe_f_growth = (
            f_growth
            if f_growth is not None
            else 0.0
        )

        self.follower_growth_label.set_value(
            f"{safe_f_growth:+.1f}%"
        )

        self._color_value(
            self.follower_growth_label.value_label,
            safe_f_growth
        )

    def _clear(self):

        self.avg_label.set_value(
            "—"
        )

        self.peak_label.set_value(
            "—"
        )

        self.growth_label.set_value(
            "—"
        )

        self.followers_label.set_value(
            "—"
        )

        self.follower_growth_label.set_value(
            "—"
        )

    @staticmethod
    def _color_value(label, value):

        try:

            if value > 0:

                color = "#72d6a0"

            elif value < 0:

                color = "#ff7777"

            else:

                color = "#f2f2f2"

            label.setStyleSheet(
                f"color: {color}; font-size: 18px; font-weight: bold;"
            )

        except Exception:
            pass