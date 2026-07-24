import asyncio
import os
import tempfile
import threading
import time

import edge_tts
import vlc


# ============================================================
# EASY SETTINGS
# ============================================================

VOICE_NAME = "en-US-AriaNeural"

VOICE_VOLUME = 40

VOICE_RATE = "+8%"

VOICE_VOLUME_TEXT = "+0%"


# ============================================================
# VOICE ENGINE
# ============================================================

class VoiceEngine:

    def __init__(self):

        self.voice = VOICE_NAME

        self.rate = VOICE_RATE

        self.volume = VOICE_VOLUME_TEXT

        self.player = None

        self.current_file = None

        self.lock = threading.Lock()

    # ========================================================
    # SPEAK
    # ========================================================

    def speak(self, text):

        thread = threading.Thread(

            target=self._speak_thread,

            args=(text,),

            daemon=True

        )

        thread.start()

    # ========================================================
    # BACKGROUND VOICE THREAD
    # ========================================================

    def _speak_thread(self, text):

        filename = None

        try:

            print()

            print(

                "[VOICE]",

                text

            )

            # -----------------------------------------------
            # Create temporary MP3 file
            # -----------------------------------------------

            fd, filename = tempfile.mkstemp(

                suffix=".mp3",

                prefix="twitcher_voice_"

            )

            os.close(fd)

            # -----------------------------------------------
            # Generate speech
            # -----------------------------------------------

            asyncio.run(

                self._generate_audio(

                    text,

                    filename

                )

            )

            # -----------------------------------------------
            # Play speech
            # -----------------------------------------------

            self._play_audio(

                filename

            )

        except Exception as error:

            print(

                "[VOICE ERROR]",

                error

            )

            if filename:

                try:

                    os.remove(

                        filename

                    )

                except Exception:

                    pass

    # ========================================================
    # GENERATE EDGE TTS AUDIO
    # ========================================================

    async def _generate_audio(

        self,

        text,

        filename

    ):

        communicate = edge_tts.Communicate(

            text,

            self.voice,

            rate=self.rate,

            volume=self.volume

        )

        await communicate.save(

            filename

        )

    # ========================================================
    # PLAY AUDIO WITH VLC
    # ========================================================

    def _play_audio(

        self,

        filename

    ):

        with self.lock:

            self.current_file = filename

            instance = vlc.Instance(

                "--no-video"

            )

            self.player = (

                instance

                .media_player_new()

            )

            media = instance.media_new(

                filename

            )

            self.player.set_media(

                media

            )

            # ================================================
            # VOLUME
            # ================================================

            self.player.audio_set_volume(

                VOICE_VOLUME

            )

            self.player.play()

        # ----------------------------------------------------
        # Wait for VLC to start
        # ----------------------------------------------------

        time.sleep(

            0.5

        )

        # ----------------------------------------------------
        # Wait for playback to finish
        # ----------------------------------------------------

        while True:

            with self.lock:

                player = self.player

            if not player:

                break

            state = player.get_state()

            if state in (

                vlc.State.Ended,

                vlc.State.Error,

                vlc.State.Stopped

            ):

                break

            time.sleep(

                0.2

            )

        # ----------------------------------------------------
        # Cleanup VLC
        # ----------------------------------------------------

        with self.lock:

            if self.player:

                self.player.stop()

            self.player = None

        # ----------------------------------------------------
        # Delete temporary MP3
        # ----------------------------------------------------

        try:

            os.remove(

                filename

            )

        except Exception:

            pass

        self.current_file = None

    # ========================================================
    # STOP CURRENT ANNOUNCEMENT
    # ========================================================

    def stop(self):

        with self.lock:

            if self.player:

                self.player.stop()

            self.player = None

        if self.current_file:

            try:

                os.remove(

                    self.current_file

                )

            except Exception:

                pass

            self.current_file = None