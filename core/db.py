"""SQLite database layer for Watcher.

Single source of truth for all persistent data: streamer metadata,
SullyGoose analytics, viewer history, channel history, and app settings.

Replaces: streamer_history.py, channel_history.py, sg_cache.py,
and QSettings for non-window-geometry data.

The database file lives at: C:\\Tools\\Twitcher\\watcher.db
"""

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "watcher.db")

_lock = threading.RLock()


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _db():
    """Context manager for a SQLite connection (thread-safe)."""
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


# ================================================================
# SCHEMA
# ================================================================

def init_db():
    """Create tables if they don't exist."""
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS streamers (
                login TEXT PRIMARY KEY,
                name TEXT,
                avatar_url TEXT,
                last_seen TEXT,
                last_viewers INTEGER,
                data TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sullygoose (
                login TEXT PRIMARY KEY,
                stats TEXT,
                last_updated TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS viewer_history (
                login TEXT,
                ts TEXT,
                viewers INTEGER,
                PRIMARY KEY (login, ts)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS channel_history (
                login TEXT PRIMARY KEY,
                last_played TEXT,
                play_count INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated TEXT
            )
        """)


# ================================================================
# SETTINGS (replaces QSettings)
# ================================================================

def get_setting(key, default=None):
    """Return a setting value, or *default* if not set."""
    with _db() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
    if not row:
        return default
    return row["value"]


def set_setting(key, value):
    """Store a setting value."""
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated) VALUES (?, ?, ?)",
            (key, str(value), _now_iso())
        )


def delete_setting(key):
    """Remove a setting."""
    with _db() as conn:
        conn.execute("DELETE FROM settings WHERE key = ?", (key,))


# ================================================================
# STREAMER DATA (replaces streamer_history.py)
# ================================================================

def store_streamer(login, name="", avatar_url="", viewers=0, data=None):
    """Store streamer metadata for a channel."""
    login = str(login or "").lower().strip()
    if not login:
        return
    with _db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO streamers (login, name, avatar_url, last_seen, last_viewers, data)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (login, name, avatar_url, _now_iso(), viewers, json.dumps(data or {}))
        )


def get_streamer(login):
    """Return streamer metadata for a channel, or {}."""
    login = str(login or "").lower().strip()
    if not login:
        return {}
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM streamers WHERE login = ?", (login,)
        ).fetchone()
    if not row:
        return {}
    result = dict(row)
    result["data"] = json.loads(result.get("data") or "{}")
    return result


def list_streamers():
    """Return all streamers in the database."""
    with _db() as conn:
        rows = conn.execute("SELECT login, name, last_viewers FROM streamers").fetchall()
    return [dict(r) for r in rows]


# ================================================================
# SULLYGOOSE ANALYTICS (replaces sg_cache.py)
# ================================================================

def store_sg(login, stats):
    """Store SullyGoose analytics for a channel."""
    login = str(login or "").lower().strip()
    if not login or not stats:
        return
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sullygoose (login, stats, last_updated) VALUES (?, ?, ?)",
            (login, json.dumps(stats), _now_iso())
        )


def get_sg(login):
    """Return SullyGoose analytics for a channel, or None."""
    login = str(login or "").lower().strip()
    if not login:
        return None
    with _db() as conn:
        row = conn.execute(
            "SELECT stats FROM sullygoose WHERE login = ?", (login,)
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["stats"])
    except Exception:
        return None


def list_sg_channels():
    """Return all channels with cached SullyGoose data."""
    with _db() as conn:
        rows = conn.execute("SELECT login, last_updated FROM sullygoose").fetchall()
    return [dict(r) for r in rows]


# ================================================================
# VIEWER HISTORY
# ================================================================

def store_viewer_history(login, viewers):
    """Append a viewer-count sample for a channel."""
    login = str(login or "").lower().strip()
    if not login:
        return
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO viewer_history (login, ts, viewers) VALUES (?, ?, ?)",
            (login, _now_iso(), viewers)
        )


def get_viewer_history(login, limit=50):
    """Return recent viewer-count samples for a channel."""
    login = str(login or "").lower().strip()
    if not login:
        return []
    with _db() as conn:
        rows = conn.execute(
            "SELECT ts, viewers FROM viewer_history WHERE login = ? ORDER BY ts DESC LIMIT ?",
            (login, limit)
        ).fetchall()
    return [dict(r) for r in rows]


def prune_viewer_history(login, keep=200):
    """Keep only the last *keep* samples for a channel."""
    login = str(login or "").lower().strip()
    if not login:
        return
    with _db() as conn:
        conn.execute(
            """
            DELETE FROM viewer_history
            WHERE login = ? AND ts NOT IN (
                SELECT ts FROM viewer_history WHERE login = ?
                ORDER BY ts DESC LIMIT ?
            )
            """,
            (login, login, keep)
        )


# ================================================================
# CHANNEL HISTORY (replaces channel_history.py)
# ================================================================

def store_channel_played(login):
    """Record that a channel was played."""
    login = str(login or "").lower().strip()
    if not login:
        return
    with _db() as conn:
        row = conn.execute(
            "SELECT play_count FROM channel_history WHERE login = ?", (login,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE channel_history SET last_played = ?, play_count = play_count + 1 WHERE login = ?",
                (_now_iso(), login)
            )
        else:
            conn.execute(
                "INSERT INTO channel_history (login, last_played, play_count) VALUES (?, ?, 1)",
                (login, _now_iso())
            )


def get_recent_channels(limit=10):
    """Return the last *limit* channels played, most recent first."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT login FROM channel_history ORDER BY last_played DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [r["login"] for r in rows]


def get_channel_history(login):
    """Return channel play history for a channel."""
    login = str(login or "").lower().strip()
    if not login:
        return {}
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM channel_history WHERE login = ?", (login,)
        ).fetchone()
    if not row:
        return {}
    return dict(row)


def clear_channel_history():
    """Clear all channel history."""
    with _db() as conn:
        conn.execute("DELETE FROM channel_history")


# Initialize the database on import.
init_db()