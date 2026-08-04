"""Local persistent store for streamer metadata.

All streamer data (last seen, viewer counts, analytics, preferences)
lives in a single JSON file so the UI can render immediately without
waiting for Twitch API responses.
"""

import json
import os
import threading
from datetime import datetime, timezone


BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)


STREAMER_DB_FILE = os.path.join(
    BASE_DIR,
    "streamer_data.json"
)


# RLock because save() calls load() while holding the lock.
_lock = threading.RLock()


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_streamer_data():
    """Return the full streamer metadata dict."""
    with _lock:
        if not os.path.exists(STREAMER_DB_FILE):
            return {}
        try:
            with open(STREAMER_DB_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}


def save_streamer_data(data):
    """Atomically write the streamer metadata dict."""
    with _lock:
        tmp = STREAMER_DB_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)
        os.replace(tmp, STREAMER_DB_FILE)


def update_streamer(login, **fields):
    """Upsert fields for one streamer and persist."""
    login = str(login).lower().strip()
    if not login:
        return
    with _lock:
        data = load_streamer_data()
        entry = data.get(login, {})
        entry.update(fields)
        entry["last_updated"] = _now_iso()
        entry.setdefault("first_seen", _now_iso())
        data[login] = entry
        save_streamer_data(data)


def get_streamer(login):
    """Return metadata for one streamer, or {}."""
    login = str(login).lower().strip()
    with _lock:
        data = load_streamer_data()
        return data.get(login, {})


def record_viewer_count(login, viewer_count):
    """Append a viewer-count snapshot for history graphs."""
    login = str(login).lower().strip()
    with _lock:
        data = load_streamer_data()
        entry = data.get(login, {})
        history = entry.get("viewer_history", [])
        history.append({
            "ts": _now_iso(),
            "viewers": viewer_count
        })
        # Keep last 200 samples.
        if len(history) > 200:
            history = history[-200:]
        entry["viewer_history"] = history
        entry["last_viewers"] = viewer_count
        data[login] = entry
        save_streamer_data(data)