from PySide6.QtWidgets import QMessageBox


class MainMenuRaidRuntime:
    def handle_raid(self, from_channel, to_channel):
        if self.raid_transition_active:
            return
        self.raid_transition_active = True
        self.log("================================")
        self.log(f"RAID DETECTED: {from_channel} → {to_channel}")
        self.dispatcher_panel.set_status(f"RAID {from_channel} → {to_channel}")
        self._run_background(lambda: self.api.get_stream_url(to_channel), lambda url: self.handle_raid_url_resolved(from_channel, to_channel, url), self.handle_raid_switch_failed)

    def handle_raid_url_resolved(self, from_channel, to_channel, url):
        if self.is_closing:
            self.raid_transition_active = False
            return
        try:
            switched = self.dispatcher.handle_raid(from_streamer=from_channel, to_streamer=to_channel, url=url)
            if not switched:
                self.log("Raid switch failed.")
                return
            self.current_channel = to_channel.lower().strip()
            self.save_last_streamer(self.current_channel)
            self.connect_chat(self.current_channel)
            self.raid_monitor.start(self.current_channel)
            self.log(f"Now monitoring raids from {self.current_channel}")
            self.update_next_stream()
        except Exception as exc:
            self.log(f"RAID SWITCH ERROR: {exc}")
            self.dispatcher_panel.set_status("Raid switch error")
        finally:
            self.raid_transition_active = False

    def handle_raid_switch_failed(self, message):
        self.raid_transition_active = False
        if self.is_closing:
            return
        self.log(f"RAID SWITCH ERROR: {message}")
        self.dispatcher_panel.set_status("Raid switch error")

    def handle_raid_status(self, message):
        self.log(f"[RAID] {message}")

    def handle_raid_error(self, message):
        self.log(f"[RAID ERROR] {message}")

    def _run_background(self, func, on_success, on_error):
        from .workers import run_in_background

        run_in_background(func, on_success, on_error)
