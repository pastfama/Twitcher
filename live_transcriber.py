import subprocess
import threading
import time
import os
import sys
import signal

# ============================================================
# CONFIGURATION
# ============================================================

STREAM_URL = "https://www.twitch.tv/zdx_smiling"

BASE_DIR = r"C:\Tools\Twitcher"

MODEL_FILE = os.path.join(
    BASE_DIR,
    "models",
    "ggml-small.bin"
)

OUTPUT_FILE = os.path.join(
    BASE_DIR,
    "transcript.txt"
)

LANGUAGE = "ru"

# 10 = 10 seconds
QUEUE = "10"

# Your FFmpeg Whisper build does not support RTX 4050 GPU
USE_GPU = "false"

# ============================================================
# GLOBALS
# ============================================================

streamlink_process = None
ffmpeg_process = None
stop_requested = False

# ============================================================
# CLEANUP
# ============================================================

def cleanup():

    global streamlink_process
    global ffmpeg_process

    print("\nCleaning up...")

    if ffmpeg_process:

        try:
            ffmpeg_process.terminate()
            ffmpeg_process.wait(timeout=5)

        except:

            try:
                ffmpeg_process.kill()

            except:
                pass

    if streamlink_process:

        try:
            streamlink_process.terminate()
            streamlink_process.wait(timeout=5)

        except:

            try:
                streamlink_process.kill()

            except:
                pass

    print("Stopped.")


def signal_handler(sig, frame):

    global stop_requested

    stop_requested = True

    print("\nStopping...")

    cleanup()

    sys.exit(0)


signal.signal(
    signal.SIGINT,
    signal_handler
)

# ============================================================
# TRANSCRIPT MONITOR
# ============================================================

def monitor_transcript():

    last_position = 0

    while not stop_requested:

        if os.path.exists(OUTPUT_FILE):

            try:

                with open(
                    OUTPUT_FILE,
                    "r",
                    encoding="utf-8",
                    errors="replace"
                ) as file:

                    file.seek(last_position)

                    new_text = file.read()

                    last_position = file.tell()

                    if new_text.strip():

                        print()
                        print("=" * 60)
                        print("[TRANSCRIPT]")
                        print(new_text.strip())
                        print("=" * 60)
                        print()

            except Exception as error:

                print(
                    f"[MONITOR ERROR] {error}"
                )

        time.sleep(0.5)


# ============================================================
# MAIN
# ============================================================

print("=" * 60)
print("TWITCHER LIVE TRANSCRIBER")
print("=" * 60)

print(f"Stream: {STREAM_URL}")
print(f"Model:  {MODEL_FILE}")
print(f"Lang:   {LANGUAGE}")
print(f"Output: {OUTPUT_FILE}")
print(f"Queue:  {QUEUE} seconds")

# ============================================================
# CHECK FILES
# ============================================================

if not os.path.exists(MODEL_FILE):

    print()
    print("[ERROR] Model file not found:")
    print(MODEL_FILE)
    sys.exit(1)

# Delete old transcript

if os.path.exists(OUTPUT_FILE):

    try:

        os.remove(OUTPUT_FILE)

        print()
        print("[OK] Old transcript deleted")

    except Exception as error:

        print(
            f"[WARNING] Could not delete old transcript: {error}"
        )

# ============================================================
# START STREAMLINK
# ============================================================

print()
print("[1/2] Starting Streamlink...")

streamlink_command = [

    "streamlink",

    "--stdout",

    STREAM_URL,

    "best"
]

streamlink_process = subprocess.Popen(

    streamlink_command,

    stdout=subprocess.PIPE,

    stderr=subprocess.PIPE,

    bufsize=0
)

print("[OK] Streamlink started")

# ============================================================
# START FFMPEG + WHISPER
# ============================================================

print()
print("[2/2] Starting FFmpeg + Whisper...")

# IMPORTANT:
# FFmpeg filter options use ':' as separators.
# Windows paths like C:\... therefore break the filter.
#
# We run FFmpeg from C:\Tools\Twitcher and use relative paths.

model_relative = "models/ggml-small.bin"

output_relative = "transcript.txt"

whisper_filter = (

    "whisper="

    f"model={model_relative}:"

    f"language={LANGUAGE}:"

    f"use_gpu={USE_GPU}:"

    f"queue={QUEUE}:"

    "vad_threshold=0.35:"

    "vad_min_speech_duration=0.2:"

    "vad_min_silence_duration=0.4:"

    f"destination={output_relative}:"

    "format=text"
)

print()
print("Whisper filter:")
print(whisper_filter)
print()

ffmpeg_command = [

    "ffmpeg",

    "-hide_banner",

    "-loglevel",
    "info",

    "-i",
    "pipe:0",

    "-af",
    whisper_filter,

    "-f",
    "null",

    "-"
]

ffmpeg_process = subprocess.Popen(

    ffmpeg_command,

    stdin=streamlink_process.stdout,

    stdout=subprocess.PIPE,

    stderr=subprocess.PIPE,

    text=True,

    encoding="utf-8",

    errors="replace",

    bufsize=1,

    cwd=BASE_DIR
)

print("[OK] FFmpeg + Whisper started")

print()
print("Listening...")
print("Press CTRL+C to stop.")
print("=" * 60)
print()

# ============================================================
# START MONITOR
# ============================================================

monitor_thread = threading.Thread(

    target=monitor_transcript,

    daemon=True
)

monitor_thread.start()

# ============================================================
# SHOW FFMPEG LOGS
# ============================================================

try:

    while True:

        line = ffmpeg_process.stderr.readline()

        if not line:

            break

        line = line.rstrip()

        if line:

            print(
                f"[FFMPEG] {line}"
            )

except KeyboardInterrupt:

    signal_handler(
        None,
        None
    )

finally:

    cleanup()