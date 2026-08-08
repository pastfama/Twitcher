"""SQLite database for persistent analytics storage.

Stores user profiles, streaming history, chat analytics, and
all persistent analytics data. Uses in-memory cache for fast access.
"""

import sqlite3
import json
import time
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from pathlib import Path
import threading
from logger import debug


SCHEMA_VERSION = 1

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY,
    login TEXT NOT NULL,
    display_name TEXT,
    platforms TEXT,  -- JSON array
    profile_image_url TEXT,
    bio TEXT,
    account_created INTEGER,
    account_type TEXT,
    
    -- Streaming Stats
    first_stream_timestamp INTEGER,
    total_view_time_minutes REAL DEFAULT 0,
    total_streams_watched INTEGER DEFAULT 0,
    peak_viewers_seen INTEGER DEFAULT 0,
    avg_viewers_across_streams REAL DEFAULT 0,
    
    -- Engagement
    chat_messages_total INTEGER DEFAULT 0,
    chat_messages_per_minute REAL DEFAULT 0,
    chat_active_minutes INTEGER DEFAULT 0,
    chat_peak_activity_hour INTEGER DEFAULT 0,
    emotes_used TEXT,  -- JSON {emote_id: count}
    bits_cheered_total INTEGER DEFAULT 0,
    subs_gifted_total INTEGER DEFAULT 0,
    
    -- Social Graph
    frequent_chat_partners TEXT,  -- JSON array
    raid_chain TEXT,  -- JSON array
    mutuals_list TEXT,  -- JSON array
    clippers_list TEXT,  -- JSON array
    
    -- Content Analysis
    categories_watched TEXT,  -- JSON array
    favorite_category TEXT,
    stream_language TEXT,
    stream_timezone TEXT,
    
    -- Predictive (updated on restart)
    churn_risk_score REAL DEFAULT 0,
    next_stream_prediction INTEGER,
    preferred_hours TEXT,  -- JSON array
    predicted_viewer_curve TEXT,  -- JSON array
    
    -- Metadata
    profile_created_at INTEGER NOT NULL,
    profile_updated_at INTEGER NOT NULL,
    last_active INTEGER,
    stale INTEGER DEFAULT 0,  -- Boolean flag for stale data
    data_sources TEXT,  -- JSON array
    
    -- Extensible JSON blobs
    preferences_json TEXT,
    technical_telemetry_json TEXT,
    achievement_data_json TEXT,
    session_history_json TEXT,
    chat_analysis_json TEXT,
    social_graph_json TEXT
);

CREATE TABLE IF NOT EXISTS channel_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT NOT NULL,
    platform TEXT NOT NULL,
    stats_json TEXT NOT NULL,  -- Full stats payload
    fetched_at INTEGER NOT NULL,
    source TEXT,  -- 'mock', 'sullygnome', 'twitch_api', etc.
    
    UNIQUE(login, platform, fetched_at)
);

CREATE TABLE IF NOT EXISTS viewer_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT NOT NULL,
    platform TEXT NOT NULL,
    viewer_count INTEGER NOT NULL,
    timestamp INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS session_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    session_start INTEGER NOT NULL,
    session_end INTEGER,
    duration_minutes INTEGER,
    streams_watched INTEGER DEFAULT 0,
    chat_messages_sent INTEGER DEFAULT 0,
    peak_viewers INTEGER DEFAULT 0,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS api_rate_limits (
    endpoint TEXT PRIMARY KEY,
    calls_remaining INTEGER DEFAULT 0,
    reset_timestamp INTEGER,
    last_call INTEGER
);

CREATE TABLE IF NOT EXISTS predictive_models (
    model_name TEXT PRIMARY KEY,
    model_data TEXT NOT NULL,  -- JSON serialized model
    trained_at INTEGER,
    accuracy REAL
);

"""


class AnalyticsDB:
    """SQLite database for analytics persistence."""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Store in user data directory
            base = Path.home() / ".watcher" / "data"
            base.mkdir(parents=True, exist_ok=True)
            db_path = base / "analytics.db"
        
        self.db_path = str(db_path)
        # Enable WAL mode for better concurrent read/write performance
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._init_schema()
        self._write_lock = threading.Lock()
    
    def _init_schema(self):
        """Create tables if they don't exist."""
        with self._conn:
            self._conn.executescript(CREATE_TABLES_SQL)
        debug(f"[ANALYTICS DB] Initialized at {self.db_path}")
    
    # ============================================================
    # USER PROFILES
    # ============================================================
    
    def store_profile(self, profile: Dict[str, Any]) -> bool:
        """Create or update a user profile."""
        now = int(time.time())
        profile["profile_updated_at"] = now
        if "profile_created_at" not in profile:
            profile["profile_created_at"] = now
        
        sql = """
        INSERT OR REPLACE INTO user_profiles (
            user_id, login, display_name, platforms, profile_image_url,
            bio, account_created, account_type,
            first_stream_timestamp, total_view_time_minutes,
            total_streams_watched, peak_viewers_seen, avg_viewers_across_streams,
            chat_messages_total, chat_messages_per_minute, chat_active_minutes,
            chat_peak_activity_hour, emotes_used, bits_cheered_total,
            subs_gifted_total, frequent_chat_partners, raid_chain,
            mutuals_list, clippers_list, categories_watched,
            favorite_category, stream_language, stream_timezone,
            churn_risk_score, next_stream_prediction, preferred_hours,
            predicted_viewer_curve, profile_created_at, profile_updated_at,
            last_active, stale, data_sources,
            preferences_json, technical_telemetry_json, achievement_data_json,
            session_history_json, chat_analysis_json, social_graph_json
        ) VALUES (
            :user_id, :login, :display_name, :platforms, :profile_image_url,
            :bio, :account_created, :account_type,
            :first_stream_timestamp, :total_view_time_minutes,
            :total_streams_watched, :peak_viewers_seen, :avg_viewers_across_streams,
            :chat_messages_total, :chat_messages_per_minute, :chat_active_minutes,
            :chat_peak_activity_hour, :emotes_used, :bits_cheered_total,
            :subs_gifted_total, :frequent_chat_partners, :raid_chain,
            :mutuals_list, :clippers_list, :categories_watched,
            :favorite_category, :stream_language, :stream_timezone,
            :churn_risk_score, :next_stream_prediction, :preferred_hours,
            :predicted_viewer_curve, :profile_created_at, :profile_updated_at,
            :last_active, :stale, :data_sources,
            :preferences_json, :technical_telemetry_json, :achievement_data_json,
            :session_history_json, :chat_analysis_json, :social_graph_json
        )
        """
        
        # Serialize JSON fields
        profile = dict(profile)
        for json_field in ["platforms", "emotes_used", "frequent_chat_partners",
                           "raid_chain", "mutuals_list", "clippers_list",
                           "categories_watched", "preferred_hours", "predicted_viewer_curve",
                           "data_sources", "preferences_json", "technical_telemetry_json",
                           "achievement_data_json", "session_history_json",
                           "chat_analysis_json", "social_graph_json"]:
            if json_field in profile and not isinstance(profile[json_field], str):
                profile[json_field] = json.dumps(profile.get(json_field) or [])
        
        # Convert booleans to integers
        profile["stale"] = 1 if profile.get("stale", False) else 0
        
        try:
            with self._write_lock:
                with self._conn:
                    self._conn.execute(sql, profile)
            return True
        except Exception as e:
            debug(f"[ANALYTICS DB] Error storing profile: {e}")
            return False
    
    def load_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Load a user profile by ID."""
        sql = "SELECT * FROM user_profiles WHERE user_id = ?"
        try:
            cursor = self._conn.execute(sql, (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            profile = dict(row)
            # Deserialize JSON fields
            for json_field in ["platforms", "emotes_used", "frequent_chat_partners",
                               "raid_chain", "mutuals_list", "clippers_list",
                               "categories_watched", "preferred_hours", "predicted_viewer_curve",
                               "data_sources", "preferences_json", "technical_telemetry_json",
                               "achievement_data_json", "session_history_json",
                               "chat_analysis_json", "social_graph_json"]:
                if profile.get(json_field):
                    try:
                        profile[json_field] = json.loads(profile[json_field])
                    except json.JSONDecodeError:
                        profile[json_field] = []
                else:
                    profile[json_field] = []
            
            profile["stale"] = bool(profile.get("stale", 0))
            return profile
        except Exception as e:
            debug(f"[ANALYTICS DB] Error loading profile: {e}")
            return None
    
    def list_profiles(self) -> List[Dict[str, Any]]:
        """List all stored profiles."""
        sql = "SELECT user_id, login, display_name, last_active, stale FROM user_profiles"
        try:
            cursor = self._conn.execute(sql)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            debug(f"[ANALYTICS DB] Error listing profiles: {e}")
            return []
    
    def mark_profile_stale(self, user_id: str, is_stale: bool = True):
        """Mark a profile as stale (data may be outdated)."""
        sql = "UPDATE user_profiles SET stale = ?, profile_updated_at = ? WHERE user_id = ?"
        try:
            with self._conn:
                self._conn.execute(sql, (1 if is_stale else 0, int(time.time()), user_id))
        except Exception as e:
            debug(f"[ANALYTICS DB] Error marking profile stale: {e}")
    
    # ============================================================
    # CHANNEL STATS CACHE
    # ============================================================
    
    def store_channel_stats(self, login: str, platform: str, stats: Dict[str, Any], source: str = "unknown") -> bool:
        """Store channel stats with timestamp."""
        sql = """
        INSERT OR REPLACE INTO channel_stats (login, platform, stats_json, fetched_at, source)
        VALUES (?, ?, ?, ?, ?)
        """
        now = int(time.time())
        try:
            with self._write_lock:
                with self._conn:
                    self._conn.execute(sql, (login, platform, json.dumps(stats), now, source))
            return True
        except Exception as e:
            debug(f"[ANALYTICS DB] Error storing channel stats: {e}")
            return False
    
    def load_channel_stats(self, login: str, platform: str, max_age_seconds: int = 300) -> Optional[Dict[str, Any]]:
        """Load channel stats if not expired."""
        cutoff = int(time.time()) - max_age_seconds
        sql = """
        SELECT stats_json, fetched_at FROM channel_stats
        WHERE login = ? AND platform = ? AND fetched_at > ?
        ORDER BY fetched_at DESC LIMIT 1
        """
        try:
            cursor = self._conn.execute(sql, (login, platform, cutoff))
            row = cursor.fetchone()
            if not row:
                return None
            
            stats = json.loads(row["stats_json"])
            stats["_cached_at"] = row["fetched_at"]
            stats["_cache_age"] = int(time.time()) - row["fetched_at"]
            return stats
        except Exception as e:
            debug(f"[ANALYTICS DB] Error loading channel stats: {e}")
            return None
    
    # ============================================================
    # VIEWER HISTORY
    # ============================================================
    
    def store_viewer_count(self, login: str, platform: str, viewer_count: int):
        """Store a single viewer count snapshot."""
        sql = """
        INSERT INTO viewer_history (login, platform, viewer_count, timestamp)
        VALUES (?, ?, ?, ?)
        """
        now = int(time.time())
        try:
            with self._write_lock:
                with self._conn:
                    self._conn.execute(sql, (login, platform, viewer_count, now))
        except Exception as e:
            debug(f"[ANALYTICS DB] Error storing viewer count: {e}")
    
    def get_viewer_history(self, login: str, platform: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get viewer history for the last N hours."""
        cutoff = int(time.time()) - (hours * 3600)
        sql = """
        SELECT viewer_count, timestamp FROM viewer_history
        WHERE login = ? AND platform = ? AND timestamp > ?
        ORDER BY timestamp ASC
        """
        try:
            cursor = self._conn.execute(sql, (login, platform, cutoff))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            debug(f"[ANALYTICS DB] Error getting viewer history: {e}")
            return []
    
    # ============================================================
    # SESSION HISTORY
    # ============================================================
    
    def start_session(self, user_id: str, metadata: Optional[Dict] = None) -> int:
        """Start a new viewing session."""
        sql = """
        INSERT INTO session_history (user_id, session_start, metadata_json)
        VALUES (?, ?, ?)
        """
        now = int(time.time())
        try:
            with self._write_lock:
                with self._conn:
                    cursor = self._conn.execute(sql, (user_id, now, json.dumps(metadata or {})))
                    return cursor.lastrowid
        except Exception as e:
            debug(f"[ANALYTICS DB] Error starting session: {e}")
            return -1
    
    def end_session(self, session_id: int, duration_minutes: int, streams_watched: int = 0):
        """End a viewing session."""
        sql = """
        UPDATE session_history
        SET session_end = ?, duration_minutes = ?, streams_watched = ?
        WHERE id = ?
        """
        now = int(time.time())
        try:
            with self._write_lock:
                with self._conn:
                    self._conn.execute(sql, (now, duration_minutes, streams_watched, session_id))
        except Exception as e:
            debug(f"[ANALYTICS DB] Error ending session: {e}")
    
    # ============================================================
    # API RATE LIMIT TRACKING
    # ============================================================
    
    def get_rate_limit(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Get current rate limit status for an endpoint."""
        sql = "SELECT * FROM api_rate_limits WHERE endpoint = ?"
        try:
            cursor = self._conn.execute(sql, (endpoint,))
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)
        except Exception as e:
            debug(f"[ANALYTICS DB] Error getting rate limit: {e}")
            return None
    
    def update_rate_limit(self, endpoint: str, remaining: int, reset: int):
        """Update rate limit after an API call."""
        sql = """
        INSERT OR REPLACE INTO api_rate_limits (endpoint, calls_remaining, reset_timestamp, last_call)
        VALUES (?, ?, ?, ?)
        """
        now = int(time.time())
        try:
            with self._write_lock:
                with self._conn:
                    self._conn.execute(sql, (endpoint, remaining, reset, now))
        except Exception as e:
            debug(f"[ANALYTICS DB] Error updating rate limit: {e}")
    
    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()