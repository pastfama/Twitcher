from PySide6.QtCore import QObject, QTimer


class ViewerMonitor(QObject):
    """
    Periodically refreshes live channel data
    and feeds it into ViewerTracker.
    """

    def __init__(
        self,
        api,
        tracker,
        get_live_channels,
        update_callback,
        interval=15000
    ):

        super().__init__()

        self.api = api
        self.tracker = tracker
        self.get_live_channels = get_live_channels
        self.update_callback = update_callback

        self.timer = QTimer()

        self.timer.timeout.connect(
            self.update
        )

        self.interval = interval


    def start(self):

        self.timer.start(
            self.interval
        )

        print(
            "[VIEWER MONITOR] Started"
        )


    def stop(self):

        self.timer.stop()


    def update(self):

        print(
            "[VIEWER MONITOR] Tick"
        )

        try:

            channels = self.get_live_channels()

            if not channels:
                print(
                    "[VIEWER MONITOR] No live channels"
                )
                return


            for channel in channels:

                try:

                    # Support both formats:
                    # "penta"
                    # {"user_login":"penta"}

                    if isinstance(channel, str):

                        login = channel

                    else:

                        login = (
                            channel.get("user_login")
                            or channel.get("user_name")
                            or channel.get("broadcaster_login")
                        )


                    if not login:
                        continue


                    streams = self.api.get_stream_info(
                        login
                    )


                    if not streams:

                        continue


                    stream = streams


                    analytics = None

                    if self.tracker:

                        analytics = self.tracker.update_stream(
                            stream
                        )


                    if self.update_callback:

                        self.update_callback(
                            stream
                        )


                    print(
                        f"[VIEWER MONITOR] "
                        f"{login}: "
                        f"{stream.get('viewer_count', 0)} viewers "
                        f"{analytics}"
                    )


                except Exception as exc:

                    print(
                        f"[VIEWER MONITOR] "
                        f"{login} error: {exc}"
                    )


        except Exception as exc:

            print(
                f"[VIEWER MONITOR ERROR] {exc}"
            )