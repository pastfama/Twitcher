import os
import sys
import time
import json
import queue
import threading
import traceback
from datetime import datetime


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_SIZE = "small"

TARGET_DEVICE_NAME = (
    "Voicemeeter Input "
    "(VB-Audio Voicemeeter VAIO)"
)

# Your Voicemeeter device is 48 kHz
CAPTURE_RATE = 48000

# Whisper expects 16 kHz
WHISPER_RATE = 16000

CHANNELS = 2

# Capture in small pieces
AUDIO_CHUNK_SECONDS = 0.5

# Whisper analyzes this much at a time
TRANSCRIPTION_WINDOW_SECONDS = 3.0

# How often to send new audio to Whisper
TRANSCRIPTION_INTERVAL_SECONDS = 1.0

# Audio must be louder than this to be considered speech
VAD_THRESHOLD = 0.006

# Keep some audio overlap
OVERLAP_SECONDS = 0.5

# Output file
TRANSCRIPT_FILE = "transcript_live.jsonl"


# ============================================================
# GLOBAL STATE
# ============================================================

shutdown_event = threading.Event()

audio_queue = queue.Queue(

    maxsize=20

)

# IMPORTANT:
# Windows DLL directory handles must stay alive.
DLL_DIRECTORY_HANDLES = []


# ============================================================
# BASIC DEBUGGING
# ============================================================

def debug(message):

    print(

        f"[DEBUG] {message}",

        flush=True

    )


def error(message):

    print(

        f"[ERROR] {message}",

        flush=True

    )


# ============================================================
# CUDA DLL PATH SETUP
# ============================================================

def setup_cuda_dlls():

    print()

    print(

        "=" * 60

    )

    print(

        "SETTING UP CUDA DLL PATHS"

    )

    print(

        "=" * 60

    )

    print()

    base = os.path.dirname(

        sys.executable

    )

    site_packages = os.path.join(

        base,

        "Lib",

        "site-packages"

    )

    dll_directories = [

        os.path.join(

            site_packages,

            "nvidia",

            "cublas",

            "bin"

        ),

        os.path.join(

            site_packages,

            "nvidia",

            "cuda_nvrtc",

            "bin"

        ),

        os.path.join(

            site_packages,

            "nvidia",

            "cuda_runtime",

            "bin"

        ),

        os.path.join(

            site_packages,

            "nvidia",

            "cudnn",

            "bin"

        ),

        os.path.join(

            site_packages,

            "ctranslate2"

        )

    ]

    for directory in dll_directories:

        if os.path.isdir(

            directory

        ):

            try:

                handle = os.add_dll_directory(

                    directory

                )

                DLL_DIRECTORY_HANDLES.append(

                    handle

                )

                print(

                    "DLL DIRECTORY ADDED:",

                    directory

                )

            except Exception as exc:

                print(

                    "DLL DIRECTORY ERROR:",

                    exc

                )

        else:

            print(

                "DLL DIRECTORY NOT FOUND:",

                directory

            )


# ============================================================
# INITIALIZE DLLS BEFORE IMPORTING WHISPER
# ============================================================

setup_cuda_dlls()


# ============================================================
# IMPORT AUDIO
# ============================================================

print()

print(

    "=" * 60

)

print(

    "IMPORTING AUDIO LIBRARY"

)

print(

    "=" * 60

)

print()

try:

    import numpy as np

    print(

        "NumPy: OK"

    )

except Exception:

    traceback.print_exc()

    sys.exit(1)


try:

    import pyaudiowpatch as pyaudio

    print(

        "PyAudioWPatch: OK"

    )

except Exception:

    traceback.print_exc()

    sys.exit(1)


# ============================================================
# IMPORT WHISPER
# ============================================================

print()

print(

    "=" * 60

)

print(

    "IMPORTING FASTER-WHISPER"

)

print(

    "=" * 60

)

print()

try:

    from faster_whisper import WhisperModel

    print(

        "Faster-Whisper: OK"

    )

except Exception:

    traceback.print_exc()

    sys.exit(1)


# ============================================================
# HEADER
# ============================================================

print()

print(

    "=" * 60

)

print(

    "TWITCHER AUDIO TRANSCRIBER"

)

print(

    "=" * 60

)

print()

print(

    "Python:",

    sys.executable

)

print(

    "Python version:",

    sys.version

)

print()


# ============================================================
# LOAD WHISPER
# ============================================================

print(

    "=" * 60

)

print(

    "LOADING WHISPER MODEL"

)

print(

    "=" * 60

)

print()

print(

    "Model:",

    MODEL_SIZE

)

print(

    "Device: CPU"

)

print(

    "Compute type: int8"

)

print()

print(

    "This version intentionally uses CPU."

)

print(

    "We will restore CUDA after the full pipeline works."

)

print()

try:

    model = WhisperModel(

        MODEL_SIZE,

        device="cpu",

        compute_type="int8",

        cpu_threads=8,

        num_workers=1

    )

    print(

        "Whisper model loaded successfully."

    )

except Exception:

    print()

    print(

        "WHISPER MODEL ERROR"

    )

    traceback.print_exc()

    sys.exit(1)


# ============================================================
# AUDIO DEVICE SEARCH
# ============================================================

def find_loopback_device(

    audio

):

    print()

    print(

        "=" * 60

    )

    print(

        "AUDIO DEVICE SEARCH"

    )

    print(

        "=" * 60

    )

    print()

    print(

        "Searching for:",

        TARGET_DEVICE_NAME

    )

    print()

    print(

        "Available loopback devices:"

    )

    selected_index = None

    selected_info = None

    for index in range(

        audio.get_device_count()

    ):

        try:

            info = (

                audio

                .get_device_info_by_index(

                    index

                )

            )

            name = info.get(

                "name",

                ""

            )

            if (

                "[Loopback]"

                not in name

            ):

                continue

            print()

            print(

                f"[{index}] {name}"

            )

            print(

                "     Channels:",

                info.get(

                    "maxInputChannels"

                )

            )

            print(

                "     Default rate:",

                info.get(

                    "defaultSampleRate"

                )

            )

            clean_name = (

                name

                .replace(

                    " [Loopback]",

                    ""

                )

            )

            if (

                TARGET_DEVICE_NAME.lower()

                in clean_name.lower()

            ):

                selected_index = index

                selected_info = info

        except Exception:

            continue

    if selected_index is None:

        raise RuntimeError(

            "Target loopback device was not found."

        )

    print()

    print(

        "=" * 60

    )

    print(

        "SELECTED AUDIO DEVICE"

    )

    print(

        "=" * 60

    )

    print()

    print(

        "Index:",

        selected_index

    )

    print(

        "Name:",

        selected_info.get(

            "name"

        )

    )

    print(

        "Native sample rate:",

        selected_info.get(

            "defaultSampleRate"

        )

    )

    print(

        "Native channels:",

        selected_info.get(

            "maxInputChannels"

        )

    )

    print()

    return selected_index, selected_info


# ============================================================
# AUDIO LEVEL
# ============================================================

def get_audio_level(

    audio_data

):

    if len(

        audio_data

    ) == 0:

        return 0.0

    return float(

        np.sqrt(

            np.mean(

                audio_data ** 2

            )

        )

    )


# ============================================================
# RESAMPLING
# ============================================================

def resample_audio(

    audio_data,

    original_rate,

    target_rate

):

    if (

        original_rate

        == target_rate

    ):

        return audio_data

    original_length = len(

        audio_data

    )

    target_length = int(

        original_length

        * target_rate

        / original_rate

    )

    if target_length <= 0:

        return np.array(

            [],

            dtype=np.float32

        )

    old_positions = np.linspace(

        0,

        original_length - 1,

        original_length

    )

    new_positions = np.linspace(

        0,

        original_length - 1,

        target_length

    )

    return np.interp(

        new_positions,

        old_positions,

        audio_data

    ).astype(

        np.float32

    )


# ============================================================
# AUDIO CAPTURE THREAD
# ============================================================

def audio_capture_worker(

    stream,

    native_rate

):

    print()

    print(

        "AUDIO CAPTURE THREAD STARTED"

    )

    print()

    frames_per_chunk = int(

        native_rate

        * AUDIO_CHUNK_SECONDS

    )

    print(

        "Capture chunk:",

        AUDIO_CHUNK_SECONDS,

        "seconds"

    )

    print(

        "Frames per chunk:",

        frames_per_chunk

    )

    print()

    last_debug_time = time.time()

    try:

        while not shutdown_event.is_set():

            raw_data = stream.read(

                frames_per_chunk,

                exception_on_overflow=False

            )

            audio_data = np.frombuffer(

                raw_data,

                dtype=np.float32

            )

            if CHANNELS > 1:

                audio_data = audio_data.reshape(

                    -1,

                    CHANNELS

                )

                audio_data = np.mean(

                    audio_data,

                    axis=1

                )

            level = get_audio_level(

                audio_data

            )

            now = time.time()

            if (

                now

                - last_debug_time

                >= 2.0

            ):

                print(

                    f"Audio level: {level:.4f}",

                    flush=True

                )

                last_debug_time = now

            if level < VAD_THRESHOLD:

                continue

            audio_data = resample_audio(

                audio_data,

                native_rate,

                WHISPER_RATE

            )

            try:

                audio_queue.put(

                    (

                        time.time(),

                        audio_data

                    ),

                    timeout=1

                )

            except queue.Full:

                error(

                    "Audio queue full."

                )

    except Exception:

        print()

        print(

            "AUDIO CAPTURE ERROR"

        )

        traceback.print_exc()

        shutdown_event.set()


# ============================================================
# TRANSCRIPTION THREAD
# ============================================================

def transcription_worker():

    print()

    print(

        "TRANSCRIPTION WORKER STARTED"

    )

    print()

    rolling_audio = np.array(

        [],

        dtype=np.float32

    )

    last_transcription_time = 0

    last_text = ""

    while not shutdown_event.is_set():

        try:

            capture_time, audio_data = (

                audio_queue.get(

                    timeout=1

                )

            )

        except queue.Empty:

            continue

        rolling_audio = np.concatenate(

            (

                rolling_audio,

                audio_data

            )

        )

        max_samples = int(

            TRANSCRIPTION_WINDOW_SECONDS

            * WHISPER_RATE

        )

        if len(

            rolling_audio

        ) > max_samples:

            rolling_audio = rolling_audio[

                -max_samples:

            ]

        current_time = time.time()

        if (

            current_time

            - last_transcription_time

            < TRANSCRIPTION_INTERVAL_SECONDS

        ):

            continue

        if len(

            rolling_audio

        ) < int(

            1.0

            * WHISPER_RATE

        ):

            continue

        last_transcription_time = current_time

        try:

            print()

            print(

                "Transcribing...",

                flush=True

            )

            start_time = time.time()

            segments, info = model.transcribe(

                rolling_audio,

                beam_size=1,

                best_of=1,

                temperature=0,

                condition_on_previous_text=False,

                vad_filter=True,

                vad_parameters={

                    "min_silence_duration_ms": 300

                }

            )

            text_parts = []

            for segment in segments:

                text = segment.text.strip()

                if text:

                    text_parts.append(

                        text

                    )

            text = " ".join(

                text_parts

            ).strip()

            processing_time = (

                time.time()

                - start_time

            )

            if not text:

                print(

                    "No speech detected."

                )

                continue

            if text == last_text:

                print(

                    "Duplicate text skipped."

                )

                continue

            last_text = text

            language = info.language

            language_probability = (

                info.language_probability

            )

            latency = (

                time.time()

                - capture_time

            )

            timestamp = datetime.now().isoformat(

                timespec="seconds"

            )

            record = {

                "timestamp": timestamp,

                "unix_time": time.time(),

                "language": language,

                "language_probability": round(

                    language_probability,

                    3

                ),

                "text": text,

                "processing_seconds": round(

                    processing_time,

                    2

                ),

                "latency_seconds": round(

                    latency,

                    2

                )

            }

            print()

            print(

                "━" * 60

            )

            print(

                f"[{language}]"

            )

            print(

                text

            )

            print()

            print(

                f"Processing: {processing_time:.2f}s"

            )

            print(

                f"Latency: {latency:.2f}s"

            )

            print(

                "━" * 60

            )

            with open(

                TRANSCRIPT_FILE,

                "a",

                encoding="utf-8"

            ) as file:

                file.write(

                    json.dumps(

                        record,

                        ensure_ascii=False

                    )

                    + "\n"

                )

        except Exception:

            print()

            print(

                "TRANSCRIPTION ERROR"

            )

            traceback.print_exc()


# ============================================================
# MAIN
# ============================================================

def main():

    audio = None

    stream = None

    capture_thread = None

    transcription_thread = None

    try:

        print()

        print(

            "=" * 60

        )

        print(

            "INITIALIZING AUDIO SYSTEM"

        )

        print(

            "=" * 60

        )

        print()

        audio = pyaudio.PyAudio()

        device_index, device_info = (

            find_loopback_device(

                audio

            )

        )

        native_rate = int(

            device_info.get(

                "defaultSampleRate",

                CAPTURE_RATE

            )

        )

        native_channels = int(

            device_info.get(

                "maxInputChannels",

                CHANNELS

            )

        )

        if native_channels < 1:

            native_channels = CHANNELS

        capture_channels = min(

            CHANNELS,

            native_channels

        )

        print()

        print(

            "=" * 60

        )

        print(

            "STARTING AUDIO CAPTURE"

        )

        print(

            "=" * 60

        )

        print()

        print(

            "Audio device:",

            device_info.get(

                "name"

            )

        )

        print(

            "Capture rate:",

            native_rate,

            "Hz"

        )

        print(

            "Whisper rate:",

            WHISPER_RATE,

            "Hz"

        )

        print(

            "Channels:",

            capture_channels

        )

        print()

        print(

            "Opening WASAPI loopback stream..."

        )

        print()

        stream = audio.open(

            format=pyaudio.paFloat32,

            channels=capture_channels,

            rate=native_rate,

            input=True,

            input_device_index=device_index,

            frames_per_buffer=int(

                native_rate

                * AUDIO_CHUNK_SECONDS

            )

        )

        print(

            "Audio capture active."

        )

        print()

        print(

            "Listening to Windows audio..."

        )

        print()

        print(

            "Play a Twitch stream."

        )

        print()

        print(

            "Press CTRL+C to stop."

        )

        print()

        capture_thread = threading.Thread(

            target=audio_capture_worker,

            args=(

                stream,

                native_rate

            ),

            daemon=True

        )

        transcription_thread = threading.Thread(

            target=transcription_worker,

            daemon=True

        )

        capture_thread.start()

        transcription_thread.start()

        while not shutdown_event.is_set():

            time.sleep(

                0.5

            )

    except KeyboardInterrupt:

        print()

        print(

            "CTRL+C received."

        )

        shutdown_event.set()

    except Exception:

        print()

        print(

            "FATAL ERROR"

        )

        traceback.print_exc()

        shutdown_event.set()

    finally:

        print()

        print(

            "Cleaning up..."

        )

        shutdown_event.set()

        if stream is not None:

            try:

                stream.stop_stream()

            except Exception:

                pass

            try:

                stream.close()

            except Exception:

                pass

        if audio is not None:

            try:

                audio.terminate()

            except Exception:

                pass

        print(

            "Cleanup complete."

        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()