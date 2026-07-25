import os
import sys
import threading
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "twitcher_debug.log")

_lock = threading.Lock()


def _emit(level, message):
    timestamp = datetime.now().isoformat(sep=" ", timespec="milliseconds")
    line = f"{timestamp} [{level}] {message}"
    with _lock:
        try:
            print(line, file=sys.stderr)
        except Exception:
            pass
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except Exception:
            pass


def debug(message):
    _emit("DEBUG", str(message))


def info(message):
    _emit("INFO", str(message))


def warning(message):
    _emit("WARNING", str(message))


def error(message):
    _emit("ERROR", str(message))
