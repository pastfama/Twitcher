from datetime import datetime, timezone

from PySide6.QtWidgets import QFrame

from .current_watching_ui import CurrentWatchingUIBuilder


class CurrentWatchingPanel(QFrame):

    def __init__(self):
        super().__init__()
        CurrentWatchingUIBuilder(self)


    # ========================================================
    # STREAM UPDATE
    # ========================================================

    def set_stream(
        self,
        stream,
        analysis=None
    ):

        if not stream:

            self.clear()
            return


        channel = stream.get(
            "user_name",
            "Unknown"
        )

        self.channel_label.setText(
            f"#{channel}"
        )


        self.viewers_label.setText(
            f"👁 {stream.get('viewer_count', 0):,} viewers"
        )


        self.category_label.setText(
            f"🎮 {stream.get('game_name') or 'No category'}"
        )


        self.title_label.setText(
            stream.get(
                "title",
                "—"
            )
        )

        avatar_url = stream.get("avatar_url")
        if hasattr(self, "set_avatar_image"):
            self.set_avatar_image(avatar_url)

        started_at = stream.get(
            "started_at"
        )


        if started_at:

            try:

                started = datetime.fromisoformat(
                    started_at.replace(
                        "Z",
                        "+00:00"
                    )
                )

                seconds = int(
                    (
                        datetime.now(timezone.utc)
                        -
                        started
                    ).total_seconds()
                )

                hours = seconds // 3600

                minutes = (
                    seconds % 3600
                ) // 60


                self.uptime_label.setText(
                    f"⏱ {hours}h {minutes}m"
                )

            except Exception:

                self.uptime_label.setText(
                    "⏱ —"
                )

        self.viewer_analysis = analysis
        if analysis:
            self.set_viewer_status(analysis)
        else:
            self.momentum_label.setText("📊 Waiting...")


    # ========================================================
    # VIEWER ANALYSIS UPDATE
    # ========================================================

    def set_viewer_status(
        self,
        analysis
    ):

        if not analysis:
            self.viewer_analysis = None
            self.momentum_label.setText("📊 Waiting...")
            return


        self.viewer_analysis = analysis

        status = analysis.get(
            "status",
            ""
        )

        percent = analysis.get(
            "percent",
            0
        )


        self.momentum_label.setText(
            f"{status} {percent:+}%"
        )

        # Update SullyGoose metrics
        sully = analysis.get("sullygoose", {})
        if sully:
            avg = sully.get("avg_viewers", 0)
            growth = sully.get("viewer_growth", 0)
            rank = sully.get("category_rank", 0)
            
            self.sully_avg_label.setText(f"Avg: {avg:,}")
            self.sully_growth_label.setText(f"Growth: {growth:+}%")
            self.sully_rank_label.setText(f"Rank: #{rank}")
            
            # Color coding growth
            if growth > 0:
                self.sully_growth_label.setStyleSheet("color: #72d6a0;")
            elif growth < 0:
                self.sully_growth_label.setStyleSheet("color: #ff7777;")
            else:
                self.sully_growth_label.setStyleSheet("")
        else:
            self.sully_avg_label.setText("Avg: —")
            self.sully_growth_label.setText("Growth: —")
            self.sully_rank_label.setText("Rank: —")
            self.sully_growth_label.setStyleSheet("")


    # ========================================================
    # CLEAR
    # ========================================================

    def clear(self):

        self.channel_label.setText(
            "—"
        )

        self.viewers_label.setText(
            "👁 — viewers"
        )

        self.category_label.setText(
            "🎮 —"
        )

        self.uptime_label.setText(
            "⏱ —"
        )

        self.title_label.setText(
            "—"
        )

        self.momentum_label.setText(
            "📊 Waiting..."
        )

        self.sully_avg_label.setText("Avg: —")
        self.sully_growth_label.setText("Growth: —")
        self.sully_rank_label.setText("Rank: —")
        self.sully_growth_label.setStyleSheet("")

        self.avatar_label.setText("?")
        if hasattr(self, "set_avatar_image"):
            self.set_avatar_image(None)