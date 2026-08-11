"""MCP Server for Twitcher viewer history data access."""

import sys
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

# Add parent directory to path to import Twitcher modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# Import Twitcher modules
from core.db import get_viewer_history, store_viewer_history, get_streamer, list_streamers

router = APIRouter()


class ViewerHistoryQuery(BaseModel):
    """Query model for viewer history."""
    login: str
    platform: str = "twitch"
    limit: int = 50
    hours: Optional[int] = None  # If specified, filter by hours back


class ViewerStatsResponse(BaseModel):
    """Response model for viewer statistics."""
    login: str
    platform: str
    current_viewers: int
    peak_viewers: int
    average_viewers: float
    total_samples: int
    trend: str  # increasing, decreasing, stable
    change_percent: float
    history: List[Dict[str, Any]]


@router.get("/viewers/{login}/history")
async def get_viewer_history_data(
    login: str,
    platform: str = "twitch",
    limit: int = Query(50, ge=1, le=500)
) -> ViewerStatsResponse:
    """Get viewer history for a streamer with statistics."""
    try:
        # Get viewer history
        history = get_viewer_history(login, limit=limit, platform=platform)
        
        if not history:
            raise HTTPException(status_code=404, detail=f"No viewer history for {login}")
        
        # Calculate statistics
        viewer_counts = [h.get("viewers", 0) for h in history]
        current_viewers = viewer_counts[0] if viewer_counts else 0
        peak_viewers = max(viewer_counts) if viewer_counts else 0
        average_viewers = sum(viewer_counts) / len(viewer_counts) if viewer_counts else 0
        
        # Calculate trend
        trend = "stable"
        change_percent = 0.0
        
        if len(viewer_counts) >= 2:
            # Compare first half to second half
            mid = len(viewer_counts) // 2
            first_half_avg = sum(viewer_counts[mid:]) / mid if mid > 0 else 0
            second_half_avg = sum(viewer_counts[:mid]) / mid if mid > 0 else 0
            
            if first_half_avg > 0:
                change_percent = ((second_half_avg - first_half_avg) / first_half_avg) * 100
            
            if change_percent > 10:
                trend = "increasing"
            elif change_percent < -10:
                trend = "decreasing"
            else:
                trend = "stable"
        
        return ViewerStatsResponse(
            login=login,
            platform=platform,
            current_viewers=current_viewers,
            peak_viewers=peak_viewers,
            average_viewers=round(average_viewers, 2),
            total_samples=len(history),
            trend=trend,
            change_percent=round(change_percent, 2),
            history=history
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/viewers/{login}/current")
async def get_current_viewers(login: str, platform: str = "twitch"):
    """Get current viewer count for a streamer."""
    try:
        # Get streamer data which includes last_viewers
        streamer = get_streamer(login, platform=platform)
        if not streamer:
            raise HTTPException(status_code=404, detail=f"Streamer {login} not found")
        
        return {
            "login": login,
            "platform": platform,
            "current_viewers": streamer.get("last_viewers", 0),
            "last_seen": streamer.get("last_seen", "")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/viewers/top")
async def get_top_streamers_by_viewers(
    platform: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100)
):
    """Get top streamers by current viewer count."""
    try:
        streamers = list_streamers(platform=platform)
        
        # Sort by last_viewers descending
        sorted_streamers = sorted(
            streamers,
            key=lambda s: s.get("last_viewers", 0),
            reverse=True
        )[:limit]
        
        return {
            "count": len(sorted_streamers),
            "platform": platform or "all",
            "top_streamers": [
                {
                    "login": s.get("login"),
                    "platform": s.get("platform", "twitch"),
                    "name": s.get("name", s.get("login")),
                    "viewers": s.get("last_viewers", 0),
                    "last_seen": s.get("last_seen", "")
                }
                for s in sorted_streamers
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/viewers/comparison")
async def compare_viewer_counts(
    login1: str,
    login2: str,
    platform1: str = "twitch",
    platform2: str = "twitch",
    limit: int = Query(50, ge=10, le=200)
):
    """Compare viewer counts between two streamers."""
    try:
        # Get history for both streamers
        history1 = get_viewer_history(login1, limit=limit, platform=platform1)
        history2 = get_viewer_history(login2, limit=limit, platform=platform2)
        
        if not history1 and not history2:
            raise HTTPException(status_code=404, detail="No viewer history for either streamer")
        
        # Calculate stats for streamer 1
        counts1 = [h.get("viewers", 0) for h in history1]
        avg1 = sum(counts1) / len(counts1) if counts1 else 0
        peak1 = max(counts1) if counts1 else 0
        
        # Calculate stats for streamer 2
        counts2 = [h.get("viewers", 0) for h in history2]
        avg2 = sum(counts2) / len(counts2) if counts2 else 0
        peak2 = max(counts2) if counts2 else 0
        
        return {
            "streamer1": {
                "login": login1,
                "platform": platform1,
                "average_viewers": round(avg1, 2),
                "peak_viewers": peak1,
                "samples": len(counts1)
            },
            "streamer2": {
                "login": login2,
                "platform": platform2,
                "average_viewers": round(avg2, 2),
                "peak_viewers": peak2,
                "samples": len(counts2)
            },
            "comparison": {
                "avg_difference": round(avg1 - avg2, 2),
                "peak_difference": peak1 - peak2
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))