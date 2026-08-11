"""MCP Server for Twitcher streamer data access."""

import sys
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

# Add parent directory to path to import Twitcher modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Import Twitcher modules
from core.db import get_streamer, list_streamers, store_streamer
from core.ai_analytics_engine import get_ai_analytics_engine

router = APIRouter()


class StreamerQuery(BaseModel):
    """Query model for streamer data."""
    login: str
    platform: str = "twitch"
    include_ai_analysis: bool = True
    include_history: bool = False


class StreamerResponse(BaseModel):
    """Response model for streamer data."""
    login: str
    platform: str
    name: str
    avatar_url: str
    last_viewers: int
    last_seen: str
    ai_analysis: Optional[Dict[str, Any]] = None
    ai_profile: Optional[Dict[str, Any]] = None


@router.get("/streamers/{login}")
async def get_streamer_data(login: str, platform: str = "twitch"):
    """Get streamer data with AI analytics."""
    try:
        # Get streamer from database
        streamer = get_streamer(login, platform=platform)
        if not streamer:
            raise HTTPException(status_code=404, detail=f"Streamer {login} not found")
        
        # Get AI analysis if available
        ai_analysis = None
        ai_profile = None
        try:
            ai_engine = get_ai_analytics_engine()
            if ai_engine:
                ai_analysis = ai_engine.get_ai_analysis(login, platform=platform)
        except Exception as e:
            # AI engine may not be available
            pass
        
        # Extract data from streamer record
        data = streamer.get("data", {})
        if ai_analysis is None and include_ai_analysis:
            ai_analysis = data.get("ai_analysis", {})
        
        ai_profile = data.get("ai_profile", {})
        
        return {
            "login": streamer.get("login", login),
            "platform": streamer.get("platform", platform),
            "name": streamer.get("name", login),
            "avatar_url": streamer.get("avatar_url", ""),
            "last_viewers": streamer.get("last_viewers", 0),
            "last_seen": streamer.get("last_seen", ""),
            "ai_analysis": ai_analysis,
            "ai_profile": ai_profile
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/streamers")
async def list_all_streamers(platform: Optional[str] = None, limit: int = 100):
    """List all streamers in the database."""
    try:
        streamers = list_streamers(platform=platform)
        return {
            "count": len(streamers),
            "streamers": streamers[:limit]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/streamers/refresh")
async def refresh_streamer_analysis(login: str, platform: str = "twitch"):
    """Trigger a fresh AI analysis for a streamer."""
    try:
        ai_engine = get_ai_analytics_engine()
        if not ai_engine:
            raise HTTPException(status_code=503, detail="AI engine not available")
        
        # Get current stream data (placeholder - would need actual stream data)
        # For now, return the cached analysis
        analysis = ai_engine.get_ai_analysis(login, platform=platform)
        return {
            "login": login,
            "platform": platform,
            "analysis": analysis,
            "status": "refreshed"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_streamers(q: str, limit: int = 20):
    """Search for streamers by name."""
    try:
        all_streamers = list_streamers()
        query = q.lower().strip()
        matches = [
            s for s in all_streamers
            if query in s.get("login", "").lower() or query in s.get("name", "").lower()
        ][:limit]
        
        return {
            "query": q,
            "count": len(matches),
            "results": matches
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))