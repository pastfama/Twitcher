from PySide6.QtWidgets import QMessageBox
from .theme import Theme


class MainMenuStreamState:

    def _fetch_live_channels(self):
        """Return current live channels list.

        Called by ViewerMonitor to get the list of
        channels to check. Returns self.live_channels
        which is populated asynchronously by load_twitch.
        """
        channels = self.live_channels or []
        # Safety net: always include current_stream so ViewerMonitor tracks it.
        current_login = None
        if self.current_stream:
            current_login = self.current_stream.get('user_login')
            if self.current_stream not in channels:
                channels = channels + [self.current_stream]
        from logger import debug
        debug(f"[CHANNEL STATE] _fetch_live_channels: live_channels={len(self.live_channels or [])}, current_stream={current_login}, returning={len(channels)}")
        return channels

    def load_twitch(self):

        self.dispatcher_panel.set_status(
            "Connecting to Twitch..."
        )

        self._run_background(
            self.api.get_current_user,
            self.handle_user_loaded,
            self.handle_user_failed
        )


    def handle_user_loaded(self, user):

        if self.is_closing:
            return

        self.user = user or {}

        self.log(
            f"Logged in as {self.user.get('display_name', 'unknown')}"
        )

        self.chat_panel.set_username(
            self.user.get("login", "")
        )

        self.dispatcher_panel.set_status(
            "Connected to Twitch"
        )

        self.load_live_channels()



    def handle_user_failed(self, message):

        if self.is_closing:
            return

        self.dispatcher_panel.set_status(
            "Twitch connection error"
        )

        self.log(
            f"ERROR: {message}"
        )

        QMessageBox.critical(
            self,
            "Twitch Error",
            message
        )



    def load_live_channels(self):

        if not self.user or self.is_loading_channels:

            if self.user is None:
                return

            self.log(
                "Live channel refresh already in progress."
            )

            return


        self.is_loading_channels = True

        self.dispatcher_panel.set_status(
            "Checking live channels..."
        )

        user_id = self.user.get(
            "id"
        )


        def fetch():
            # Fetch from all platforms
            all_live = []

            # Twitch (primary) — followed channels from the API
            try:
                followed = self.api.get_followed_channels(
                    user_id
                )
                twitch_live = self.api.get_live_streams(
                    followed
                )
                for stream in twitch_live:
                    stream["platform"] = "twitch"
                all_live.extend(twitch_live)
            except Exception as e:
                self.log(f"[LIVE] Twitch error: {e}")

            # Kick and YouTube have no public "followed channels"
            # endpoint, so we use the local watchlist instead.
            try:
                from core.db import get_watchlist
                watchlist = get_watchlist()
            except Exception as e:
                self.log(f"[LIVE] Watchlist error: {e}")
                watchlist = []

            # Use the unified platform manager for Kick/YouTube.
            try:
                from platforms import get_platform_manager
                pm = get_platform_manager()
                non_twitch_live = pm.get_live_streams(watchlist)
                all_live.extend(non_twitch_live)
            except Exception as e:
                self.log(f"[LIVE] Platform manager error: {e}")

            return all_live


        self._run_background(
            fetch,
            self.handle_live_channels_loaded,
            self.handle_live_channels_failed
        )



    def handle_live_channels_loaded(self, streams):

        self.is_loading_channels = False

        if self.is_closing:
            return


        streams = list(
            streams or []
        )


        streams.sort(
            key=lambda item: item.get(
                "viewer_count",
                0
            ),
            reverse=True
        )


        self.live_channels = streams


        self.live_followed_panel.set_streams(
            streams
        )


        # If nothing is currently playing, auto-start the top live channel.
        # This ensures the video window actually plays the stream the UI
        # is displaying, instead of staying blank until the user clicks.
        if not self.current_channel and streams:

            top = streams[0]

            channel = top.get(
                "user_login"
            )

            if channel:

                self.current_stream = top

                self.start_channel(
                    channel,
                    manual=False
                )


        self.update_next_stream()


        self.dispatcher_panel.set_status(
            f"{len(streams)} channels live"
        )


        self.log(
            f"Found {len(streams)} live channels."
        )


        self.try_resume_last_streamer()



    def handle_live_channels_failed(self, message):

        self.is_loading_channels = False

        if self.is_closing:
            return


        self.dispatcher_panel.set_status(
            "API error"
        )


        self.log(
            f"ERROR: {message}"
        )



    def try_resume_last_streamer(self):

        if self.resume_attempted:
            return


        self.resume_attempted = True


        last_streamer = self.load_last_streamer()


        if not last_streamer:

            self.log(
                "No previous streamer saved."
            )

            return


        matching_stream = None


        for stream in self.live_channels:

            login = str(
                stream.get(
                    "user_login",
                    ""
                )
            ).lower().strip()


            username = str(
                stream.get(
                    "user_name",
                    ""
                )
            ).lower().strip()


            if last_streamer in (
                login,
                username
            ):

                matching_stream = stream
                break


        if not matching_stream:

            self.log(
                f"Previous streamer #{last_streamer} is not currently live."
            )

            return


        self.current_stream = matching_stream

        # Set current_channel early so ViewerMonitor guard works.
        self.current_channel = last_streamer

        # Ensure the channel is in live_channels so ViewerMonitor tracks it.
        if matching_stream not in self.live_channels:
            self.live_channels.append(matching_stream)

        self.log(
            f"Resuming previous streamer: #{last_streamer}"
        )


        self.update_current_stream_view(
            matching_stream
        )


        self.start_channel(
            last_streamer,
            manual=False,
            resume=True
        )



    def update_next_stream(self):

        current = (
            self.current_channel or ""
        ).lower().strip()


        candidates = [
            stream
            for stream in self.live_channels
            if str(
                stream.get(
                    "user_login",
                    ""
                )
            ).lower().strip() != current
        ]


        if not candidates:

            self.next_stream = None

            self.next_panel.clear()

            self.dispatcher_panel.set_next_status(
                "Next: No available stream"
            )

            return


        candidates.sort(
            key=lambda item: item.get(
                "viewer_count",
                0
            ),
            reverse=True
        )


        self.next_stream = candidates[0]


        self.next_panel.set_stream(
            self.next_stream
        )


        channel = self.next_stream.get(
            "user_name",
            "Unknown"
        )


        viewers = self.next_stream.get(
            "viewer_count",
            0
        )


        self.dispatcher_panel.set_next_status(
            f"Next: #{channel} ({viewers:,} viewers)"
        )



    def get_live_stream_by_channel(self, channel):

        if not channel:
            return None


        target = str(
            channel
        ).strip().lower()


        for stream in self.live_channels:

            if target in (
                str(stream.get("user_login", "")).strip().lower(),
                str(stream.get("user_name", "")).strip().lower()
            ):

                return stream


        return None



    def update_current_stream_view(self, stream, analytics=None):
        """Update the Currently Watching panel with fresh stream data.

        Called by:
          - ViewerMonitor (every 2s) with pre-computed analytics
          - _on_analytics_signal when SullyGoose data arrives
          - channel_selected / handle_stream_url_resolved for immediate display
        """
        if not stream:
            self.current_panel.clear()
            return

        # Guard: ignore updates for channels the user is NOT watching.
        incoming_login = (
            stream.get("user_login")
            or stream.get("user_name")
            or ""
        ).lower().strip()
        if self.current_channel and incoming_login != self.current_channel:
            return

        enriched_stream = self.enrich_stream_with_avatar(stream)

        # ViewerMonitor already computed analytics on its background thread.
        # Only recompute when called directly (e.g. channel_selected) without
        # pre-computed analytics.  This eliminates a redundant update_stream()
        # call that would re-run viewer_tracker.update_stream + collect_external_data.
        if analytics is None:
            analysis = self.analytics_engine.update_stream(enriched_stream)
        else:
            analysis = analytics

        # Update cached stream for timer-based tick() refreshes.
        self.current_stream = enriched_stream

        # Emit fully-processed signal so panels can self-update.
        self.state.stream_ready.emit(enriched_stream, analysis)

        # Also call directly for backward compatibility.
        self.current_panel.set_stream(enriched_stream, analysis)



    def channel_selected(self, stream):

        if not stream:
            return

        # Set current_channel EARLY so ViewerMonitor's guard in
        # update_current_stream_view knows which channel to accept data for.
        channel_login = (
            stream.get("user_login")
            or stream.get("user_name")
            or ""
        ).lower().strip()
        if channel_login:
            self.current_channel = channel_login

        self.current_stream = stream


        # Ensure the channel is in live_channels so ViewerMonitor tracks it.
        if stream not in self.live_channels:
            self.live_channels.append(stream)


        self.update_current_stream_view(
            stream
        )


        self.log(
            f"Selected {stream.get('user_login')}"
        )


        # If nothing is currently playing, auto-start this channel.
        # This makes the video window actually show the stream that the
        # currwatching panel is displaying, instead of staying blank.
        if not self.current_channel:

            channel = stream.get(
                "user_login"
            )

            if channel:

                self.start_channel(
                    channel,
                    manual=False
                )



    def connect_chat(self, channel, platform="twitch"):

        if not channel:
            return


        # Only Twitch has IRC chat integration. Other platforms get a
        # graceful "chat unavailable" state instead of a broken IRC connect.
        if platform != "twitch":
            self.chat_panel.show_platform_unavailable(platform)
            self.log(
                f"Chat unavailable for {platform} channel #{channel}"
            )
            return


        self.chat_panel.connect_chat(
            channel
        )


        self.log(
            f"Chat connecting to #{channel}"
        )



    def watch_selected(self):

        if not self.current_stream:

            QMessageBox.warning(
                self,
                "No Channel Selected",
                "Select a live channel first."
            )

            return


        channel = self.current_stream.get(
            "user_login"
        )


        if channel:

            self.start_channel(
                channel,
                manual=True
            )



    def start_channel(self, channel, manual=False, resume=False):

        if not channel:
            return


        channel = str(
            channel
        ).lower().strip()


        if self.pending_channel:

            self.log(
                f"Still resolving #{self.pending_channel}; ignoring {channel}."
            )

            return


        # Determine the platform from the current stream if available,
        # otherwise fall back to URL auto-detection (bare names default
        # to Twitch for backward compatibility).
        platform = None
        if self.current_stream:
            platform = self.current_stream.get("platform")
        if not platform:
            from platforms import detect_platform
            platform = detect_platform(channel)

        # Strip explicit platform prefixes ("kick:xqc" -> "xqc") so the
        # stored channel name and history are clean.
        from platforms import strip_platform_prefix
        channel = strip_platform_prefix(channel).lstrip("#").lower()

        self.pending_channel = channel


        self.dispatcher_panel.set_status(
            f"Resolving {channel} ({platform})..."
        )


        def resolve():
            from core.stream_resolver import resolve_stream_url
            return resolve_stream_url(channel, platform_name=platform)

        self._run_background(
            resolve,
            lambda url: self.handle_stream_url_resolved(
                channel,
                url,
                manual,
                platform
            ),
            lambda message: self.handle_stream_url_failed(
                channel,
                message
            )
        )



    def handle_stream_url_resolved(self, channel, url, manual, platform="twitch"):

        self.pending_channel = None


        if self.is_closing:
            return


        if not url:

            self.handle_stream_url_failed(
                channel,
                f"Could not resolve stream URL for {channel}"
            )

            return


        switched = self.dispatcher.switch_stream(
            streamer=channel,
            url=url,
            announce=manual,
            platform=platform
        )


        if not switched:

            self.log(
                "Dispatcher rejected stream switch."
            )

            return


        self.current_channel = channel

        self.current_stream = (
            self.get_live_stream_by_channel(channel)
            or self.current_stream
        )

        # Ensure the channel is in live_channels so ViewerMonitor tracks it.
        if self.current_stream not in self.live_channels:
            self.live_channels.append(self.current_stream)

        self.save_last_streamer(
            channel
        )


        self.connect_chat(
            channel,
            platform=platform
        )


        # Only Twitch has a raid system; set the channel so the
        # EventSub websocket subscribes for incoming raids.
        if platform == "twitch":
            self.raid_monitor.set_channel(
                channel
            )

            self.raid_monitor.start()


        self.dispatcher_panel.set_status(
            f"▶ Watching {channel}"
        )


        self.update_current_stream_view(
            self.current_stream
        )


        self.update_next_stream()



    def handle_stream_url_failed(self, channel, message):

        self.pending_channel = None


        if self.is_closing:
            return


        self.dispatcher_panel.set_status(
            "Video error"
        )


        self.log(
            f"VIDEO ERROR: {message}"
        )


        QMessageBox.critical(
            self,
            "Video Error",
            message
        )



    def stop_video(self):

        try:
            self.raid_monitor.stop()

        except Exception:
            pass


        try:
            self.dispatcher.stop()

        except Exception as exc:

            self.log(
                f"Dispatcher stop error: {exc}"
            )


        self.current_channel = None

        self.current_stream = None


        self.update_current_stream_view(
            None
        )


        self.dispatcher_panel.set_status(
            "Video stopped"
        )


        self.log(
            "Video stopped."
        )


        self.update_next_stream()