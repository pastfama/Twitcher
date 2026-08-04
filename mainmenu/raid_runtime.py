from PySide6.QtWidgets import QMessageBox


class MainMenuRaidRuntime:

    def handle_raid(self, from_streamer, to_streamer):

        self.dispatcher_panel.set_status(
            f"Raid: {from_streamer} → {to_streamer}"
        )

        self.log(
            f"RAID: {from_streamer} → {to_streamer}"
        )

        if self.current_channel:

            switched = self.dispatcher.switch_stream(
                streamer=self.current_channel,
                url=None,
                announce=False,
                raid={
                    "from": from_streamer,
                    "to": to_streamer,
                }
            )

            if switched:

                self.dispatcher_panel.set_status(
                    "Raid handled."
                )

            else:

                QMessageBox.warning(
                    self,
                    "Raid Error",
                    "Could not handle raid."
                )

        else:

            QMessageBox.information(
                self,
                "Raid Detected",
                f"Raid from {from_streamer} to {to_streamer}"
            )



    def handle_raid_status(self, message):

        self.dispatcher_panel.set_status(
            f"Raid monitor: {message}"
        )



    def handle_raid_error(self, message):

        self.log(
            f"RAID ERROR: {message}"
        )

        QMessageBox.critical(
            self,
            "Raid Error",
            message
        )