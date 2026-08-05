"""SQLite database layer for Watcher.

Single source of truth for all persistent data: streamer metadata,
SullyGoose analytics, viewer history, channel history, watchlist,
and app settings.

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


from paths import get_db_path

DB_PATH = get_db_path()

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
                platform TEXT NOT NULL DEFAULT 'twitch',
                login TEXT NOT NULL,
                name TEXT,
                avatar_url TEXT,
                last_seen TEXT,
                last_viewers INTEGER,
                data TEXT,
                PRIMARY KEY (platform, login)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sullygoose (
                platform TEXT NOT NULL DEFAULT 'twitch',
                login TEXT NOT NULL,
                stats TEXT,
                last_updated TEXT,
                PRIMARY KEY (platform, login)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS viewer_history (
                platform TEXT NOT NULL DEFAULT 'twitch',
                login TEXT NOT NULL,
                ts TEXT,
                viewers INTEGER,
                PRIMARY KEY (platform, login, ts)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS channel_history (
                platform TEXT NOT NULL DEFAULT 'twitch',
                login TEXT NOT NULL,
                last_played TEXT,
                play_count INTEGER DEFAULT 0,
                PRIMARY KEY (platform, login)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                platform TEXT NOT NULL,
                channel TEXT NOT NULL,
                added_at TEXT,
                PRIMARY KEY (platform, channel)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated TEXT
            )
        """)
        _migrate_legacy_schema(conn)


def _migrate_legacy_schema(conn):
    """Migrate pre-platform databases to the new composite-key schema.

    Old tables used ``login`` as the primary key.  New tables use
    ``(platform, login)``.  For existing databases, add the platform
    column and backfill existing rows with 'twitch' (the only platform
    that existed before the multi-platform release).
    """
    tables = {
        "streamers": "login",
        "sullygoose": "login",
        "viewer_history": "login",
        "channel_history": "login",
    }
    for table, old_pk in tables.items():
        cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if "platform" not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN platform TEXT NOT NULL DEFAULT 'twitch'")
        # Rebuild the table with the composite primary key if the old
        # single-column PK is still in place.
        pk_cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall() if r["pk"]]
        if pk_cols == [old_pk]:
            conn.execute(f"ALTER TABLE {table} RENAME TO {table}_legacy")
            if table == "streamers":
                conn.execute("""
                    CREATE TABLE streamers (
                        platform TEXT NOT NULL DEFAULT 'twitch',
                        login TEXT NOT NULL,
                        name TEXT,
                        avatar_url TEXT,
                        last_seen TEXT,
                        last_viewers INTEGER,
                        data TEXT,
                        PRIMARY KEY (platform, login)
                    )
                """)
                conn.execute("""
                    INSERT OR IGNORE INTO streamers
                        (platform, login, name, avatar_url, last_seen, last_viewers, data)
                    SELECT 'twitch', login, name, avatar_url, last_seen, last_viewers, data
                    FROM streamers_legacy
                """)
            elif table == "sullygoose":
                conn.execute("""
                    CREATE TABLE sullygoose (
                        platform TEXT NOT NULL DEFAULT 'twitch',
                        login TEXT NOT NULL,
                        stats TEXT,
                        last_updated TEXT,
                        PRIMARY KEY (platform, login)
                    )
                """)
                conn.execute("""
                    INSERT OR IGNORE INTO sullygoose
                        (platform, login, stats, last_updated)
                    SELECT 'twitch', login, stats, last_updated
                    FROM sullygoose_legacy
                """)
            elif table == "viewer_history":
                conn.execute("""
                    CREATE TABLE viewer_history (
                        platform TEXT NOT NULL DEFAULT 'twitch',
                        login TEXT NOT NULL,
                        ts TEXT,
                        viewers INTEGER,
                        PRIMARY KEY (platform, login, ts)
                    )
                """)
                conn.execute("""
                    INSERT OR IGNORE INTO viewer_history
                        (platform, login, ts, viewers)
                    SELECT 'twitch', login, ts, viewers
                    FROM viewer_history_legacy
                """)
            elif table == "channel_history":
                conn.execute("""
                    CREATE TABLE channel_history (
                        platform TEXT NOT NULL DEFAULT 'twitch',
                        login TEXT NOT NULL,
                        last_played TEXT,
                        play_count INTEGER DEFAULT 0,
                        PRIMARY KEY (platform, login)
                    )
                """)
                conn.execute("""
                    INSERT OR IGNORE INTO channel_history
                        (platform, login, last_played, play_count)
                    SELECT 'twitch', login, last_played, play_count
                    FROM channel_history_legacy
                """)
            conn.execute(f"DROP TABLE {table}_legacy")


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
# WATCHLIST (multi-platform followed channels)
# ================================================================

def add_to_watchlist(platform, channel):
    """Add a channel to the watchlist for a platform."""
    platform = str(platform or "twitch").lower().strip()
    channel = str(channel or "").lower().strip()
    if not channel:
        return
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO watchlist (platform, channel, added_at) VALUES (?, ?, ?)",
            (platform, channel, _now_iso())
        )


def remove_from_watchlist(platform, channel):
    """Remove a channel from the watchlist."""
    platform = str(platform or "twitch").lower().strip()
    channel = str(channel or "").lower().strip()
    with _db() as conn:
        conn.execute(
            "DELETE FROM watchlist WHERE platform = ? AND channel = ?",
            (platform, channel)
        )


def get_watchlist(platform=None):
    """Return watchlist entries, optionally filtered by platform."""
    with _db() as conn:
        if platform:
            rows = conn.execute(
                "SELECT platform, channel FROM watchlist WHERE platform = ? ORDER BY added_at",
                (str(platform).lower().strip(),)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT platform, channel FROM watchlist ORDER BY platform, added_at"
            ).fetchall()
    return [dict(r) for r in rows]


# ================================================================
# STREAMER DATA (replaces streamer_history.py)
# ================================================================

def store_streamer(login, name="", avatar_url="", viewers=0, data=None, platform="twitch"):
    """Store streamer metadata for a channel."""
    platform = str(platform or "twitch").lower().strip()
    login = str(login or "").lower().strip()
    if not login:
        return
    with _db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO streamers (platform, login, name, avatar_url, last_seen, last_viewers, data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (platform, login, name, avatar_url, _now_iso(), viewers, json.dumps(data or {}))
        )


def get_streamer(login, platform="twitch"):
    """Return streamer metadata for a channel, or {}."""
    platform = str(platform or "twitch").lower().strip()
    login = str(login or "").lower().strip()
    if not login:
        return {}
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM streamers WHERE platform = ? AND login = ?", (platform, login)
        ).fetchone()
    if not row:
        return {}
    result = dict(row)
    result["data"] = json.loads(result.get("data") or "{}")
    return result


def list_streamers(platform=None):
    """Return all streamers in the database."""
    with _db() as conn:
        if platform:
            rows = conn.execute(
                "SELECT platform, login, name, last_viewers FROM streamers WHERE platform = ?",
                (str(platform).lower().strip(),)
            ).fetchall()
        else:
            rows = conn.execute("SELECT platform, login, name, last_viewers FROM streamers").fetchall()
    return [dict(r) for r in rows]


# ================================================================
# SULLYGOOSE ANALYTICS (replaces sg_cache.py)
# ================================================================

def store_sg(login, stats, platform="twitch"):
    """Store SullyGoose analytics for a channel."""
    platform = str(platform or "twitch").lower().strip()
    login = str(login or "").lower().strip()
    if not login or not stats:
        return
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sullygoose (platform, login, stats, last_updated) VALUES (?, ?, ?, ?)",
            (platform, login, json.dumps(stats), _now_iso())
        )


def get_sg(login, platform="twitch"):
    """Return SullyGoose analytics for a channel, or None."""
    platform = str(platform or "twitch").lower().strip()
    login = str(login or "").lower().strip()
    if not login:
        return None
    with _db() as conn:
        row = conn.execute(
            "SELECT stats FROM sullygoose WHERE platform = ? AND login = ?", (platform, login)
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["stats"])
    except Exception:
        return None


def list_sg_channels(platform=None):
    """Return all channels with cached SullyGoose data."""
    with _db() as conn:
        if platform:
            rows = conn.execute(
                "SELECT platform, login, last_updated FROM sullygoose WHERE platform = ?",
                (str(platform).lower().strip(),)
            ).fetchall()
        else:
            rows = conn.execute("SELECT platform, login, last_updated FROM sullygoose").fetchall()
    return [dict(r) for r in rows]


# ================================================================
# VIEWER HISTORY
# ================================================================

def store_viewer_history(login, viewers, platform="twitch"):
    """Append a viewer-count sample for a channel."""
    platform = str(platform or "twitch").lower().strip()
    login = str(login or "").lower().strip()
    if not login:
        return
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO viewer_history (platform, login, ts, viewers) VALUES (?, ?, ?, ?)",
            (platform, login, _now_iso(), viewers)
        )


def get_viewer_history(login, limit=50, platform="twitch"):
    """Return recent viewer-count samples for a channel."""
    platform = str(platform or "twitch").lower().strip()
    login = str(login or "").lower().strip()
    if not login:
        return []
    with _db() as conn:
        rows = conn.execute(
            "SELECT ts, viewers FROM viewer_history WHERE platform = ? AND login = ? ORDER BY ts DESC LIMIT ?",
            (platform, login, limit)
        ).fetchall()
    return [dict(r) for r in rows]


def prune_viewer_history(login, keep=200, platform="twitch"):
    """Keep only the last *keep* samples for a channel."""
    platform = str(platform or "twitch").lower().strip()
    login = str(login or "").lower().strip()
    if not login:
        return
    with _db() as conn:
        conn.execute(
            """
            DELETE FROM viewer_history
            WHERE platform = ? AND login = ? AND ts NOT IN (
                SELECT ts FROM viewer_history WHERE platform = ? AND login = ?
                ORDER BY ts DESC LIMIT ?
            )
            """,
            (platform, login, platform, login, keep)
        )


# ================================================================
# CHANNEL HISTORY (replaces channel_history.py)
# ================================================================

def store_channel_played(login, platform="twitch"):
    """Record that a channel was played."""
    platform = str(platform or "twitch").lower().strip()
    login = str(login or "").lower().strip()
    if not login:
        return
    with _db() as conn:
        row = conn.execute(
            "SELECT play_count FROM channel_history WHERE platform = ? AND login = ?", (platform, login)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE channel_history SET last_played = ?, play_count = play_count + 1 WHERE platform = ? AND login = ?",
                (_now_iso(), platform, login)
            )
        else:
            conn.execute(
                "INSERT INTO channel_history (platform, login, last_played, play_count) VALUES (?, ?, ?, 1)",
                (platform, login, _now_iso())
            )


def get_recent_channels(limit=10):
    """Return the last *limit* (platform, channel) pairs played, most recent first."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT platform, login FROM channel_history ORDER BY last_played DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [{"platform": r["platform"], "channel": r["login"]} for r in rows]


def get_channel_history(login, platform="twitch"):
    """Return channel play history for a channel."""
    platform = str(platform or "twitch").lower().strip()
    login = str(login or "").lower().strip()
    if not login:
        return {}
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM channel_history WHERE platform = ? AND login = ?", (platform, login)
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