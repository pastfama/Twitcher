"""MCP Server for AI commentary storage and retrieval.

Stores all AI-generated commentary in PostgreSQL with full metrics
snapshots, vision analysis, and mood data. The agent uses this
to learn patterns and generate better commentary over time.
"""

import sys
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()

# ── PostgreSQL connection ───────────────────────────────────────────────

import os

PG_HOST = os.getenv("PG_HOST", "twagent-db.postgres.database.azure.com")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB = os.getenv("PG_DB", "twitcher")
PG_USER = os.getenv("PG_USER", "azureuser")
PG_PASSWORD = os.getenv("PG_PASSWORD", "ChangeMe123!")


def _get_conn():
    """Get a PostgreSQL connection (lazy import to avoid hard dependency)."""
    try:
        import psycopg2
        return psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB,
            user=PG_USER, password=PG_PASSWORD,
            sslmode="require",
        )
    except ImportError:
        raise HTTPException(status_code=503, detail="psycopg2 not installed")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB connection failed: {e}")


def _ensure_table():
    """Create the commentary table if it doesn't exist."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS commentary (
                id SERIAL PRIMARY KEY,
                channel VARCHAR(100) NOT NULL,
                platform VARCHAR(20) DEFAULT 'twitch',
                timestamp TIMESTAMPTZ DEFAULT NOW(),
                commentary TEXT NOT NULL,
                mood VARCHAR(20) DEFAULT 'neutral',
                expression VARCHAR(20) DEFAULT 'neutral',
                viewers INTEGER DEFAULT 0,
                velocity FLOAT DEFAULT 0.0,
                sentiment FLOAT DEFAULT 0.0,
                chat_rate FLOAT DEFAULT 0.0,
                vision_analysis TEXT DEFAULT '',
                metrics_snapshot JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_commentary_channel
                ON commentary(channel, timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_commentary_mood
                ON commentary(mood, timestamp DESC);
        """)
        conn.commit()
        cur.close()
    finally:
        conn.close()


# ── Models ──────────────────────────────────────────────────────────────

class CommentaryEntry(BaseModel):
    channel: str
    platform: str = "twitch"
    commentary: str
    mood: str = "neutral"
    expression: str = "neutral"
    viewers: int = 0
    velocity: float = 0.0
    sentiment: float = 0.0
    chat_rate: float = 0.0
    vision_analysis: str = ""
    metrics_snapshot: Dict[str, Any] = {}


# ── Endpoints ───────────────────────────────────────────────────────────

@router.post("/commentary/store")
async def store_commentary(entry: CommentaryEntry):
    """Store a new commentary entry."""
    try:
        _ensure_table()
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO commentary
                (channel, platform, commentary, mood, expression,
                 viewers, velocity, sentiment, chat_rate,
                 vision_analysis, metrics_snapshot)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
        """, (
            entry.channel, entry.platform, entry.commentary,
            entry.mood, entry.expression,
            entry.viewers, entry.velocity, entry.sentiment,
            entry.chat_rate, entry.vision_analysis,
            json.dumps(entry.metrics_snapshot),
        ))
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return {
            "id": row[0],
            "created_at": row[1].isoformat(),
            "status": "stored"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/commentary/history/{channel}")
async def get_commentary_history(
    channel: str,
    platform: str = "twitch",
    limit: int = Query(50, ge=1, le=500),
    mood: Optional[str] = None,
):
    """Get commentary history for a channel."""
    try:
        _ensure_table()
        conn = _get_conn()
        cur = conn.cursor()

        if mood:
            cur.execute("""
                SELECT id, channel, platform, commentary, mood, expression,
                       viewers, velocity, sentiment, chat_rate,
                       vision_analysis, metrics_snapshot, created_at
                FROM commentary
                WHERE channel = %s AND platform = %s AND mood = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (channel, platform, mood, limit))
        else:
            cur.execute("""
                SELECT id, channel, platform, commentary, mood, expression,
                       viewers, velocity, sentiment, chat_rate,
                       vision_analysis, metrics_snapshot, created_at
                FROM commentary
                WHERE channel = %s AND platform = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (channel, platform, limit))

        rows = cur.fetchall()
        cur.close()
        conn.close()

        entries = []
        for r in rows:
            entries.append({
                "id": r[0], "channel": r[1], "platform": r[2],
                "commentary": r[3], "mood": r[4], "expression": r[5],
                "viewers": r[6], "velocity": r[7], "sentiment": r[8],
                "chat_rate": r[9], "vision_analysis": r[10],
                "metrics_snapshot": r[11] if isinstance(r[11], dict) else json.loads(r[11] or '{}'),
                "created_at": r[12].isoformat() if r[12] else None,
            })

        return {"channel": platform, "count": len(entries), "entries": entries}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/commentary/patterns/{channel}")
async def get_commentary_patterns(channel: str, platform: str = "twitch"):
    """Analyze commentary patterns for a channel (for agent learning)."""
    try:
        _ensure_table()
        conn = _get_conn()
        cur = conn.cursor()

        # Mood distribution
        cur.execute("""
            SELECT mood, COUNT(*) as count, AVG(viewers) as avg_viewers,
                   AVG(sentiment) as avg_sentiment
            FROM commentary
            WHERE channel = %s AND platform = %s
            GROUP BY mood
            ORDER BY count DESC
        """, (channel, platform))
        moods = [
            {"mood": r[0], "count": r[1],
             "avg_viewers": round(r[2] or 0, 0),
             "avg_sentiment": round(r[3] or 0, 1)}
            for r in cur.fetchall()
        ]

        # Peak hours
        cur.execute("""
            SELECT EXTRACT(HOUR FROM created_at) as hour,
                   COUNT(*) as count, AVG(viewers) as avg_viewers
            FROM commentary
            WHERE channel = %s AND platform = %s
            GROUP BY hour
            ORDER BY avg_viewers DESC
            LIMIT 5
        """, (channel, platform))
        peak_hours = [
            {"hour": int(r[0]), "count": r[1], "avg_viewers": round(r[2] or 0, 0)}
            for r in cur.fetchall()
        ]

        # Recent vision themes
        cur.execute("""
            SELECT vision_analysis, COUNT(*) as count
            FROM commentary
            WHERE channel = %s AND platform = %s AND vision_analysis != ''
            GROUP BY vision_analysis
            ORDER BY count DESC
            LIMIT 10
        """, (channel, platform))
        vision_themes = [
            {"theme": r[0][:100], "count": r[1]}
            for r in cur.fetchall()
        ]

        cur.close()
        conn.close()

        return {
            "channel": channel,
            "platform": platform,
            "mood_distribution": moods,
            "peak_hours": peak_hours,
            "vision_themes": vision_themes,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/commentary/stats")
async def get_commentary_stats():
    """Get overall commentary statistics."""
    try:
        _ensure_table()
        conn = _get_conn()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM commentary")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT channel) FROM commentary")
        channels = cur.fetchone()[0]

        cur.execute("""
            SELECT mood, COUNT(*) FROM commentary
            GROUP BY mood ORDER BY COUNT(*) DESC
        """)
        moods = {r[0]: r[1] for r in cur.fetchall()}

        cur.close()
        conn.close()

        return {
            "total_commentary": total,
            "channels_tracked": channels,
            "mood_breakdown": moods,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))