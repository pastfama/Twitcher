"""Commentary Store — local client for the agent's commentary API.

Stores and retrieves AI commentary via the agent's PostgreSQL backend.
Falls back to local SQLite if the agent is unavailable.
"""

import json
import threading
from typing import Dict, Any, List, Optional
from logger import debug

AGENT_URL = "http://localhost:8000/api/mcp"
_agent_available = None  # None = unknown, True/False


def _check_agent():
    """Check if the agent is reachable."""
    global _agent_available
    if _agent_available is not None:
        return _agent_available
    try:
        import urllib.request
        req = urllib.request.Request(f"{AGENT_URL.replace('/api/mcp', '')}/health", method="GET")
        resp = urllib.request.urlopen(req, timeout=3)
        _agent_available = resp.status == 200
    except Exception:
        _agent_available = False
    return _agent_available


def store_commentary(entry: Dict[str, Any]) -> bool:
    """Store a commentary entry via the agent API."""
    if not _check_agent():
        return _store_local(entry)

    try:
        import urllib.request
        data = json.dumps(entry).encode("utf-8")
        req = urllib.request.Request(
            f"{AGENT_URL}/commentary/store",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=5)
        result = json.loads(resp.read().decode("utf-8"))
        debug(f"[COMMENTARY STORE] Stored via agent: id={result.get('id')}")
        return True
    except Exception as e:
        debug(f"[COMMENTARY STORE] Agent store failed: {e}, falling back to local")
        return _store_local(entry)


def get_history(channel: str, platform: str = "twitch",
                limit: int = 50, mood: str = None) -> List[Dict]:
    """Get commentary history for a channel."""
    if not _check_agent():
        return _get_local_history(channel, platform, limit)

    try:
        import urllib.request
        url = f"{AGENT_URL}/commentary/history/{channel}?platform={platform}&limit={limit}"
        if mood:
            url += f"&mood={mood}"
        req = urllib.request.Request(url, method="GET")
        resp = urllib.request.urlopen(req, timeout=5)
        result = json.loads(resp.read().decode("utf-8"))
        return result.get("entries", [])
    except Exception as e:
        debug(f"[COMMENTARY STORE] Agent history failed: {e}")
        return _get_local_history(channel, platform, limit)


def get_patterns(channel: str, platform: str = "twitch") -> Dict[str, Any]:
    """Get commentary patterns for a channel."""
    if not _check_agent():
        return {}

    try:
        import urllib.request
        url = f"{AGENT_URL}/commentary/patterns/{channel}?platform={platform}"
        req = urllib.request.Request(url, method="GET")
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        debug(f"[COMMENTARY STORE] Agent patterns failed: {e}")
        return {}


# ── Local SQLite fallback ───────────────────────────────────────────────

def _store_local(entry: Dict[str, Any]) -> bool:
    """Store commentary in local SQLite as fallback."""
    try:
        from core.db import _db, _now_iso
        with _db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS commentary_local (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    platform TEXT DEFAULT 'twitch',
                    commentary TEXT NOT NULL,
                    mood TEXT DEFAULT 'neutral',
                    vision_analysis TEXT DEFAULT '',
                    metrics_json TEXT DEFAULT '{}',
                    created_at TEXT
                )
            """)
            conn.execute("""
                INSERT INTO commentary_local
                    (channel, platform, commentary, mood, vision_analysis, metrics_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.get("channel", ""),
                entry.get("platform", "twitch"),
                entry.get("commentary", ""),
                entry.get("mood", "neutral"),
                entry.get("vision_analysis", ""),
                json.dumps(entry.get("metrics_snapshot", {})),
                _now_iso(),
            ))
        debug("[COMMENTARY STORE] Stored locally")
        return True
    except Exception as e:
        debug(f"[COMMENTARY STORE] Local store failed: {e}")
        return False


def _get_local_history(channel: str, platform: str, limit: int) -> List[Dict]:
    """Get commentary from local SQLite."""
    try:
        from core.db import _db
        with _db() as conn:
            cur = conn.execute("""
                SELECT commentary, mood, vision_analysis, metrics_json, created_at
                FROM commentary_local
                WHERE channel = ? AND platform = ?
                ORDER BY created_at DESC LIMIT ?
            """, (channel, platform, limit))
            rows = cur.fetchall()
            return [
                {
                    "commentary": r[0], "mood": r[1],
                    "vision_analysis": r[2],
                    "metrics_snapshot": json.loads(r[3] or '{}'),
                    "created_at": r[4],
                }
                for r in rows
            ]
    except Exception:
        return []