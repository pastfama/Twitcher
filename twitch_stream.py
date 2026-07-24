"""
Twitcher - Twitch Stream Audio Ingestion

Pipeline:

Twitch channel
    ↓
Streamlink
    ↓
FFmpeg
    ↓
16 kHz / mono / signed 16-bit PCM
    ↓
Python audio chunks

This file does NOT transcribe anything yet.
It only gets clean audio from Twitch.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import threading
import time
from typing import Callable, Optional


# ============================================================
# CONFIGURATION
# ============================================================

SAMPLE_RATE = 16_000
CHANNELS = 1
SAMPLE_WIDTH_BYTES = 2  # signed 16-bit PCM


# ============================================================
# TWITCH STREAM
# ============================================================

class TwitchStream:
    """
    Gets audio directly from a Twitch stream.

    Twitch
        ↓
    Streamlink
        ↓
    FFmpeg
        ↓
    PCM audio bytes
    """

    def __init__(
        self,
        channel: str,
        quality: str = "best",
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        chunk_seconds: float = 0.5,
        on_audio: Optional[Callable[[bytes], None]] = None,
    ):
        self.channel = channel.strip()
        self.quality = quality
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_seconds = chunk_seconds
        self.on_audio = on_audio

        self.streamlink_process: Optional[subprocess.Popen] = None
        self.ffmpeg_process: Optional[subprocess.Popen] = None

        self.running = False
        self.reader_thread: Optional[threading.Thread] = None

        self.bytes_per_second = (
            self.sample_rate
            * self.channels
            * SAMPLE_WIDTH_BYTES
        )

        self.chunk_size = int(
            self.bytes_per_second * self.chunk_seconds
        )

    # ========================================================
    # CHECK DEPENDENCIES
    # ========================================================

    def check_dependencies(self) -> bool:
        """
        Check that Streamlink and FFmpeg are available.
        """

        print("\n" + "=" * 60)
        print("CHECKING STREAM DEPENDENCIES")
        print("=" * 60)

        streamlink_path = shutil.which("streamlink")
        ffmpeg_path = shutil.which("ffmpeg")

        if streamlink_path:
            print(f"Streamlink: {streamlink_path}")
        else:
            print("ERROR: Streamlink was not found in PATH.")
            print()
            print("Install it with:")
            print("  pip install streamlink")
            print()
            return False

        if ffmpeg_path:
            print(f"FFmpeg: {ffmpeg_path}")
        else:
            print("ERROR: FFmpeg was not found in PATH.")
            print()
            print("Install FFmpeg and add its bin folder to PATH.")
            print()
            return False

        return True

    # ========================================================
    # START
    # ========================================================

    def start(self) -> bool:
        """
        Start Streamlink and FFmpeg.
        """

        if self.running:
            print("Stream is already running.")
            return False

        if not self.check_dependencies():
            return False

        twitch_url = f"https://www.twitch.tv/{self.channel}"

        print("\n" + "=" * 60)
        print("STARTING TWITCH STREAM")
        print("=" * 60)

        print(f"Channel: {self.channel}")
        print(f"Quality: {self.quality}")
        print(f"Audio rate: {self.sample_rate} Hz")
        print(f"Channels: {self.channels}")
        print(f"Chunk size: {self.chunk_seconds:.2f} seconds")

        # ----------------------------------------------------
        # STREAMLINK
        #
        # Gets the Twitch stream and outputs the stream data
        # directly to stdout.
        # ----------------------------------------------------

        streamlink_command = [
            "streamlink",
            "--stdout",
            twitch_url,
            self.quality,
        ]

        print("\nStarting Streamlink...")

        try:
            self.streamlink_process = subprocess.Popen(
                streamlink_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )

        except Exception as error:
            print(f"Failed to start Streamlink: {error}")
            return False

        # ----------------------------------------------------
        # FFMPEG
        #
        # Reads the Twitch stream from Streamlink's stdout.
        #
        # Outputs:
        #   raw PCM
        #   signed 16-bit
        #   little-endian
        #   mono
        #   16,000 Hz
        #
        # This format is ideal for Whisper.
        # ----------------------------------------------------

        ffmpeg_command = [
            "ffmpeg",

            # Read input from stdin
            "-i",
            "pipe:0",

            # Audio only
            "-vn",

            # Mono
            "-ac",
            str(self.channels),

            # Sample rate
            "-ar",
            str(self.sample_rate),

            # Signed 16-bit little-endian PCM
            "-f",
            "s16le",

            # Output to stdout
            "pipe:1",
        ]

        print("Starting FFmpeg...")

        try:
            self.ffmpeg_process = subprocess.Popen(
                ffmpeg_command,
                stdin=self.streamlink_process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )

        except Exception as error:
            print(f"Failed to start FFmpeg: {error}")

            self.stop()
            return False

        # Allow FFmpeg to receive EOF properly if Streamlink stops.
        if self.streamlink_process.stdout:
            self.streamlink_process.stdout.close()

        self.running = True

        self.reader_thread = threading.Thread(
            target=self._read_audio_loop,
            daemon=True,
        )

        self.reader_thread.start()

        print("\n" + "=" * 60)
        print("TWITCH AUDIO CAPTURE ACTIVE")
        print("=" * 60)

        print(f"Channel: {self.channel}")
        print(f"Format: PCM s16le")
        print(f"Rate: {self.sample_rate} Hz")
        print(f"Channels: {self.channels}")
        print()
        print("Audio is now being received directly from Twitch.")
        print("Press CTRL+C to stop.")
        print()

        return True

    # ========================================================
    # AUDIO READER
    # ========================================================

    def _read_audio_loop(self):
        """
        Continuously read raw PCM audio from FFmpeg.
        """

        if not self.ffmpeg_process:
            return

        if not self.ffmpeg_process.stdout:
            return

        print("Audio reader thread started.")

        while self.running:

            try:
                audio_data = self.ffmpeg_process.stdout.read(
                    self.chunk_size
                )

            except Exception as error:
                print(f"\nAudio read error: {error}")
                break

            if not audio_data:
                print("\nNo more audio data received.")
                break

            # Send audio to callback
            if self.on_audio:
                try:
                    self.on_audio(audio_data)

                except Exception as error:
                    print(f"\nAudio callback error: {error}")

        print("Audio reader thread stopped.")

        self.running = False

    # ========================================================
    # STOP
    # ========================================================

    def stop(self):
        """
        Stop FFmpeg and Streamlink.
        """

        if not self.running and not self.streamlink_process:
            return

        print("\nStopping Twitch stream...")

        self.running = False

        # Stop FFmpeg first
        if self.ffmpeg_process:

            try:
                if self.ffmpeg_process.stdin:
                    self.ffmpeg_process.stdin.close()
            except Exception:
                pass

            try:
                self.ffmpeg_process.terminate()
            except Exception:
                pass

            try:
                self.ffmpeg_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    self.ffmpeg_process.kill()
                except Exception:
                    pass

            self.ffmpeg_process = None

        # Then stop Streamlink
        if self.streamlink_process:

            try:
                self.streamlink_process.terminate()
            except Exception:
                pass

            try:
                self.streamlink_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    self.streamlink_process.kill()
                except Exception:
                    pass

            self.streamlink_process = None

        print("Twitch stream stopped.")

    # ========================================================
    # STATUS
    # ========================================================

    def is_running(self) -> bool:
        return self.running


# ============================================================
# TEST CALLBACK
# ============================================================

def test_audio_callback(audio_data: bytes):
    """
    Temporary test callback.

    This will later be replaced by the Whisper engine.
    """

    sample_count = len(audio_data) // SAMPLE_WIDTH_BYTES

    duration = sample_count / SAMPLE_RATE

    print(
        f"Received audio: "
        f"{len(audio_data):,} bytes "
        f"({duration:.2f}s)"
    )


# ============================================================
# TEST MODE
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Twitcher Twitch audio ingestion test"
    )

    parser.add_argument(
        "channel",
        help="Twitch channel name",
    )

    parser.add_argument(
        "--quality",
        default="best",
        help="Stream quality: best, worst, 720p, etc.",
    )

    args = parser.parse_args()

    stream = TwitchStream(
        channel=args.channel,
        quality=args.quality,
        chunk_seconds=0.5,
        on_audio=test_audio_callback,
    )

    if not stream.start():
        sys.exit(1)

    try:

        while stream.is_running():
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nCTRL+C received.")

    finally:
        stream.stop()


if __name__ == "__main__":
    main()