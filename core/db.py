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
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login TEXT NOT NULL,
                platform TEXT NOT NULL CHECK(platform IN ('twitch','youtube')),
                is_followed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(login, platform)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sullygoose_scrapes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL,
                scraped_at TIMESTAMP NOT NULL,
                status TEXT CHECK(status IN ('success', 'partial', 'failed')) DEFAULT 'success',
                error TEXT,
                response_time_ms INTEGER,
                raw_html BLOB,
                metrics JSON NOT NULL,
                FOREIGN KEY(channel_id) REFERENCES channels(id) ON DELETE CASCADE
            )
        """)
        # Keep existing viewer_history table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS viewer_history (
                platform TEXT NOT NULL DEFAULT 'twitch',
                login TEXT NOT NULL,
                ts TEXT,
                viewers INTEGER,
                PRIMARY KEY (platform, login, ts)
            )
        """)
        # Keep existing channel_history table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS channel_history (
                platform TEXT NOT NULL DEFAULT 'twitch',
                login TEXT NOT NULL,
                last_played TEXT,
                play_count INTEGER DEFAULT 0,
                PRIMARY KEY (platform, login)
            )
        """)
        # Keep existing watchlist table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                platform TEXT NOT NULL,
                channel TEXT NOT NULL,
                added_at TEXT,
                PRIMARY KEY (platform, channel)
            )
        """)
        # Keep existing settings table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated TEXT
            )
        """)
        # Create indexes for new tables
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scrapes_channel ON sullygoose_scrapes(channel_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scrapes_time ON sullygoose_scrapes(scraped_at)")
        
        # Migrate existing data
        _migrate_legacy_schema(conn)
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

def get_channel_id(login, platform):
    """Get channel ID from channels table, create if needed"""
    with _db() as conn:
        row = conn.execute(
            "SELECT id FROM channels WHERE login = ? AND platform = ?",
            (login, platform)
        ).fetchone()
        if row:
            return row[0]
        # Create channel if not exists
        return conn.execute(
            "INSERT INTO channels (login, platform) VALUES (?, ?)",
            (login, platform)
        ).lastrowid

def store_sg(login, stats, platform="twitch", status="success", error=None, response_time_ms=None, raw_html=None):
    """Store SullyGoose analytics for a channel in the new schema"""
    channel_id = get_channel_id(login, platform)
    if not channel_id:
        return
        
    with _db() as conn:
        conn.execute(
            "INSERT INTO sullygoose_scrapes (channel_id, scraped_at, status, error, response_time_ms, raw_html, metrics) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (channel_id, _now_iso(), status, error, response_time_ms, raw_html, json.dumps(stats))
        )


def get_sg(login, platform="twitch"):
    """Return most recent SullyGoose analytics for a channel, or None."""
    platform = str(platform or "twitch").lower().strip()
    login = str(login or "").lower().strip()
    if not login:
        return None
    # Read from the new schema — join channels to find latest scrape.
    with _db() as conn:
        row = conn.execute(
            """
            SELECT s.metrics, s.scraped_at, s.status, s.response_time_ms
            FROM sullygoose_scrapes s
            JOIN channels c ON c.id = s.channel_id
            WHERE c.login = ? AND c.platform = ?
            ORDER BY s.scraped_at DESC
            LIMIT 1
            """,
            (login, platform),
        ).fetchone()
    if not row:
        return None
    try:
        stats = json.loads(row["metrics"])
    except Exception:
        return None
    # Merge in metadata fields the widget/client rely on.
    stats["scraped_at"] = row["scraped_at"]
    stats["status"] = row["status"]
    stats["response_time_ms"] = row["response_time_ms"]
    return stats


def list_sg_channels(platform=None):
    """Return all channels with cached SullyGoose data (from scraps with data)."""
    with _db() as conn:
        if platform:
            rows = conn.execute(
                """
                SELECT c.platform, c.login, MAX(s.scraped_at) AS last_updated
                FROM sullygoose_scrapes s
                JOIN channels c ON c.id = s.channel_id
                WHERE c.platform = ?
                GROUP BY c.platform, c.login
                """,
                (str(platform).lower().strip(),)
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT c.platform, c.login, MAX(s.scraped_at) AS last_updated
                FROM sullygoose_scrapes s
                JOIN channels c ON c.id = s.channel_id
                GROUP BY c.platform, c.login
                """
            ).fetchall()
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


def get_db_size():
    """Return current database size in bytes"""
    return os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0

def enforce_sullygoose_cap(new_data_size=0):
    """Ensure SullyGnome data never exceeds 50GB"""
    MAX_SIZE = 50 * 1024 * 1024 * 1024  # 50GB in bytes
    current_size = get_db_size()
    
    # Only check if we're near the limit
    if current_size + new_data_size < MAX_SIZE * 0.95:
        return
        
    # Calculate target size (leave 5% buffer)
    target_size = MAX_SIZE * 0.9
    
    # Delete oldest scrapes until under target
    with _db() as conn:
        while get_db_size() > target_size:
            result = conn.execute('''
                DELETE FROM sullygoose_scrapes
                WHERE id IN (
                    SELECT id FROM sullygoose_scrapes
                    ORDER BY scraped_at ASC
                    LIMIT 100
                )
            ''')
            if result.rowcount == 0:
                break

# Initialize the database on import.
init_db()
