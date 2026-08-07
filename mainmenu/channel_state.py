from logger import debug
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


        self.update_next_stream()


        self.dispatcher_panel.set_status(
            f"{len(streams)} channels live"
        )


        self.log(
            f"Found {len(streams)} live channels."
        )


        # Resume the last-viewed streamer BEFORE auto-starting the top
        # channel.  This way the saved channel gets priority over the
        # auto-start fallback.
        self.try_resume_last_streamer()


        # If nothing is currently playing and no resume is in progress,
        # auto-start the top live channel.
        if not self.current_channel and not self.pending_channel and streams:

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

        if not stream:

            self.current_panel.clear()

            return

        # --------------------------------------------------------------
        # Channel guard — only update the panel for the channel that is
        # actually playing in the video window (self.current_channel).
        #
        # ViewerMonitor dispatches background checks for ALL live
        # channels every 4 s.  Without this guard every completed check
        # — even non-current channels — would overwrite the panel with
        # the wrong avatar, viewer count, graph points, etc.
        # --------------------------------------------------------------
        incoming_login = str(
            stream.get("user_login")
            or stream.get("user_name")
            or stream.get("channel")
            or ""
        ).strip().lower()

        # If a specific channel is playing, only accept updates for it.
        # When current_channel is None (first run, before any stream is
        # selected) we allow the first result through so the panel isn't
        # blank.
        if self.current_channel and incoming_login:
            if incoming_login != self.current_channel:
                return

        enriched_stream = self.enrich_stream_with_avatar(
            stream
        )


        # Use analytics from viewer monitor if provided; otherwise compute it.
        if analytics is None:
            analysis = self.analytics_engine.update_stream(
                enriched_stream
            )
        else:
            analysis = analytics

        # Ensure current_stream is set for analytics engine reference.
        self.current_stream = enriched_stream

        self.current_panel.set_stream(
            enriched_stream,
            analysis
        )



    def channel_selected(self, stream):

        if not stream:
            return


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


        # Resolve broadcaster ID from current stream data.
        broadcaster_id = None
        if self.current_stream:
            broadcaster_id = (
                self.current_stream.get("broadcaster_id")
                or self.current_stream.get("user_id")
            )

        # --- Load third-party emotes for the channel (background) ---
        self._ensure_emote_resolver()
        if self._emote_resolver is not None:
            from core import run_in_background
            ch = channel
            run_in_background(
                lambda: self._emote_resolver.update(ch),
                lambda _: None,
                lambda e: debug(f"[EMOTES] Background fetch error: {e}"),
            )
            self.chat_panel.chat_widget._emote_resolver = self._emote_resolver

        # --- Load channel avatar (background) ---
        avatar_url = self.avatar_cache.get(f"twitch:{channel}")
        if avatar_url:
            self.chat_panel.set_avatar(avatar_url)
        else:
            from core import run_in_background
            ch = channel
            run_in_background(
                lambda: self._fetch_chat_avatar(ch),
                lambda url: self.chat_panel.set_avatar(url),
                lambda e: debug(f"[CHAT AVATAR] Fetch error: {e}"),
            )

        # --- Fetch chat badges + channel info (background) ---
        if broadcaster_id:
            from core import run_in_background
            bid = broadcaster_id
            cw = self.chat_panel.chat_widget
            # Set broadcaster_id so badges can be fetched.
            cw._broadcaster_id = bid
            run_in_background(
                lambda: cw.fetch_channel_badges(bid),
                lambda _: None,
                lambda e: debug(f"[CHAT BADGES] Fetch error: {e}"),
            )
            # Fetch channel info for the info strip.
            run_in_background(
                lambda: self._fetch_channel_chat_info(channel, bid),
                lambda info: self.chat_panel.set_channel_info(**info),
                lambda e: debug(f"[CHAT INFO] Fetch error: {e}"),
            )

        self.chat_panel.connect_chat(
            channel
        )


        self.log(
            f"Chat connecting to #{channel}"
        )

    # ------------------------------------------------------------------
    # Emote resolver helper
    # ------------------------------------------------------------------

    def _ensure_emote_resolver(self):
        """Create the EmoteResolver singleton if it doesn't exist yet."""
        if getattr(self, "_emote_resolver", None) is not None:
            return
        try:
            from .chatpanel import EmoteResolver
            self._emote_resolver = EmoteResolver()
        except Exception as exc:
            debug(f"[EMOTES] Failed to create EmoteResolver: {exc}")
            self._emote_resolver = None

    def _fetch_chat_avatar(self, channel):
        """Fetch the avatar URL for a Twitch channel (blocking call)."""
        try:
            profile = self.api.get_user_profile(channel)
            url = profile.get("profile_image_url", "")
            if url:
                self.avatar_cache[f"twitch:{channel}"] = url
                return url
        except Exception as exc:
            debug(f"[CHAT AVATAR] Failed to fetch avatar for {channel}: {exc}")
        return ""

    def _fetch_channel_chat_info(self, channel, broadcaster_id):
        """Fetch stream info + reward count for the chat info strip (blocking).
        Returns a dict suitable for ``ChatPanel.set_channel_info()``."""
        info = {"game": "", "viewers": 0, "reward_count": 0}
        try:
            stream = self.api.get_stream_info(channel)
            if stream:
                info["game"] = stream.get("game_name", "")
                info["viewers"] = stream.get("viewer_count", 0)
        except Exception as exc:
            debug(f"[CHAT INFO] Stream info fetch error: {exc}")
        try:
            rewards = self.api.get_channel_rewards(broadcaster_id)
            info["reward_count"] = len(rewards)
        except Exception as exc:
            debug(f"[CHAT INFO] Rewards fetch error: {exc}")
        return info



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