"""MCP Server for Twitcher analytics data access."""

import sys
import os
import json
from typing import Dict, Any, List, Optional

# Add parent directory to path to import Twitcher modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# Import Twitcher modules
from core.db import get_viewer_history, get_streamer
from core.ai_analytics_engine import get_ai_analytics_engine

router = APIRouter()


class AnalyticsQuery(BaseModel):
    """Query model for analytics data."""
    login: str
    platform: str = "twitch"
    analysis_type: str = "stream"  # stream, profile, prediction


class ViewerTrendResponse(BaseModel):
    """Response model for viewer trends."""
    login: str
    platform: str
    trend_data: List[Dict[str, Any]]
    current_viewers: int
    peak_viewers: int
    average_viewers: float
    momentum: str
    momentum_percent: float


@router.get("/analytics/{login}/trends")
async def get_viewer_trends(
    login: str,
    platform: str = "twitch",
    limit: int = Query(50, ge=10, le=200)
) -> ViewerTrendResponse:
    """Get viewer count trends for a streamer."""
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
        
        # Get AI analysis for momentum
        momentum = "Stable"
        momentum_percent = 0.0
        try:
            ai_engine = get_ai_analytics_engine()
            if ai_engine:
                ai_analysis = ai_engine.get_ai_analysis(login, platform=platform)
                momentum = ai_analysis.get("momentum", "Stable")
                momentum_percent = ai_analysis.get("momentum_percent", 0.0)
        except Exception:
            pass
        
        return ViewerTrendResponse(
            login=login,
            platform=platform,
            trend_data=history,
            current_viewers=current_viewers,
            peak_viewers=peak_viewers,
            average_viewers=round(average_viewers, 2),
            momentum=momentum,
            momentum_percent=momentum_percent
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/{login}/quality")
async def get_quality_metrics(login: str, platform: str = "twitch"):
    """Get AI-generated quality metrics for a streamer."""
    try:
        ai_engine = get_ai_analytics_engine()
        if not ai_engine:
            raise HTTPException(status_code=503, detail="AI engine not available")
        
        analysis = ai_engine.get_ai_analysis(login, platform=platform)
        if not analysis:
            raise HTTPException(status_code=404, detail=f"No AI analysis for {login}")
        
        return {
            "login": login,
            "platform": platform,
            "quality_score": analysis.get("quality_score", 0),
            "momentum": analysis.get("momentum", "Stable"),
            "momentum_percent": analysis.get("momentum_percent", 0.0),
            "confidence": analysis.get("confidence", 0.0),
            "churn_risk": analysis.get("churn_risk", 0.0),
            "viral_potential": analysis.get("viral_potential", 0.0),
            "predicted_peak_viewers": analysis.get("predicted_peak_viewers", 0),
            "predicted_peak_time": analysis.get("predicted_peak_time", ""),
            "ai_insight": analysis.get("ai_insight", ""),
            "reasoning": analysis.get("reasoning", ""),
            "recommendations": analysis.get("recommendations", [])
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/{login}/profile")
async def get_streamer_profile(login: str, platform: str = "twitch"):
    """Get AI-generated profile for a streamer."""
    try:
        # Check if we have cached profile data
        streamer = get_streamer(login, platform=platform)
        if not streamer:
            raise HTTPException(status_code=404, detail=f"Streamer {login} not found")
        
        data = streamer.get("data", {})
        ai_profile = data.get("ai_profile", {})
        
        if not ai_profile:
            return {
                "login": login,
                "platform": platform,
                "profile": None,
                "message": "No profile generated yet. Use analyze_streamer_profile to generate one."
            }
        
        return {
            "login": login,
            "platform": platform,
            "profile": ai_profile,
            "last_updated": data.get("ai_profile_last_updated", "")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analytics/{login}/profile/generate")
async def generate_streamer_profile(login: str, platform: str = "twitch"):
    """Trigger AI profile generation for a streamer."""
    try:
        ai_engine = get_ai_analytics_engine()
        if not ai_engine:
            raise HTTPException(status_code=503, detail="AI engine not available")
        
        profile = ai_engine.analyze_streamer_profile(login, platform=platform)
        if not profile:
            raise HTTPException(status_code=500, detail="Failed to generate profile")
        
        return {
            "login": login,
            "platform": platform,
            "profile": profile,
            "status": "generated"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/{login}/sentiment")
async def get_sentiment(login: str, platform: str = "twitch"):
    """Analyze chat sentiment for a streamer and return mood classification."""
    try:
        from mainmenu.chatpanel.mood_engine import MoodEngine, classify_mood, MOODS

        # Get viewer history as proxy for sentiment data
        history = get_viewer_history(login, limit=20, platform=platform)
        
        # Compute a basic sentiment from viewer momentum
        sentiment = 0.0
        if history and len(history) >= 3:
            counts = [h.get("viewers", 0) for h in history]
            if len(counts) >= 2:
                recent_avg = sum(counts[:5]) / min(5, len(counts))
                older_avg = sum(counts[5:]) / max(1, len(counts) - 5)
                if older_avg > 0:
                    change = (recent_avg - older_avg) / older_avg
                    sentiment = max(-100, min(100, change * 100))

        mood_key = classify_mood(sentiment)
        pal = MOODS[mood_key]

        return {
            "login": login,
            "platform": platform,
            "sentiment_score": round(sentiment, 1),
            "mood": mood_key,
            "mood_name": pal.name,
            "mood_emoji": pal.emoji,
            "accent_color": pal.accent,
            "bg_gradient": [pal.bg_start, pal.bg_end],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/{login}/dashboard")
async def get_dashboard_metrics(login: str, platform: str = "twitch"):
    """Get all 36 dashboard metrics for a streamer."""
    try:
        ai_engine = get_ai_analytics_engine()
        if not ai_engine:
            raise HTTPException(status_code=503, detail="AI engine not available")

        streamer = get_streamer(login, platform=platform)
        if not streamer:
            raise HTTPException(status_code=404, detail=f"Streamer {login} not found")

        history = get_viewer_history(login, limit=50, platform=platform)
        viewers = streamer.get("last_viewers", 0)

        # Build a minimal stream dict for the engine
        stream = {
            "user_login": login,
            "platform": platform,
            "viewer_count": viewers,
            "game_name": streamer.get("data", {}).get("game", "Unknown"),
            "title": streamer.get("data", {}).get("title", ""),
            "started_at": streamer.get("data", {}).get("started_at", ""),
        }

        metrics = ai_engine.analyze_dashboard_metrics(
            stream=stream,
            viewer_history=history,
            chat_metrics=None,
        )

        return {
            "login": login,
            "platform": platform,
            "metrics": metrics,
            "history_samples": len(history) if history else 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/{login}/mood")
async def get_mood_status(login: str, platform: str = "twitch"):
    """Get current mood classification for a stream."""
    try:
        from mainmenu.chatpanel.mood_engine import MoodEngine, classify_mood, MOODS

        history = get_viewer_history(login, limit=20, platform=platform)

        sentiment = 0.0
        if history and len(history) >= 3:
            counts = [h.get("viewers", 0) for h in history]
            if len(counts) >= 2:
                recent_avg = sum(counts[:5]) / min(5, len(counts))
                older_avg = sum(counts[5:]) / max(1, len(counts) - 5)
                if older_avg > 0:
                    change = (recent_avg - older_avg) / older_avg
                    sentiment = max(-100, min(100, change * 100))

        mood_key = classify_mood(sentiment)
        pal = MOODS[mood_key]

        return {
            "login": login,
            "platform": platform,
            "mood": mood_key,
            "mood_name": pal.name,
            "mood_emoji": pal.emoji,
            "sentiment": round(sentiment, 1),
            "colors": {
                "accent": pal.accent,
                "bg_start": pal.bg_start,
                "bg_end": pal.bg_end,
                "lcd_digit": pal.lcd_digit,
                "progress_fill": pal.progress_fill,
                "glow": pal.glow,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/leaderboard")
async def get_leaderboard(
    metric: str = Query("quality_score", regex="^(quality_score|viewers|momentum_percent)$"),
    platform: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100)
):
    """Get leaderboard of streamers by various metrics."""
    try:
        streamers = list_streamers(platform=platform)
        
        scored_streamers = []
        for streamer in streamers:
            data = streamer.get("data", {})
            ai_analysis = data.get("ai_analysis", {})
            
            score = ai_analysis.get(metric, 0)
            if not score and metric == "viewers":
                score = streamer.get("last_viewers", 0)
            
            scored_streamers.append({
                "login": streamer.get("login"),
                "platform": streamer.get("platform", "twitch"),
                "name": streamer.get("name", streamer.get("login")),
                "score": score,
                "metric": metric
            })
        
        # Sort by score descending
        scored_streamers.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "metric": metric,
            "count": len(scored_streamers),
            "leaderboard": scored_streamers[:limit]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))