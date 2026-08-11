"""AI-powered analytics engine - replaces all manual analytics logic.

This engine uses Azure OpenAI to:
- Analyze streamer profiles and performance
- Generate quality scores and momentum predictions
- Provide intelligent recommendations
- Store AI insights in database
"""

import json
import threading
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

from logger import debug
from PySide6.QtCore import QObject, Signal
from core.azure_ai_client import get_ai_client
from core.db import (
    get_streamer, store_streamer, list_streamers,
    get_viewer_history, store_viewer_history,
    get_setting, set_setting
)


@dataclass
class AIAnalysis:
    """AI-generated analysis for a stream."""
    platform: str
    login: str
    analyzed_at: str
    analysis_type: str  # 'stream', 'profile', 'prediction'
    
    # Stream analysis
    quality_score: int = 0
    momentum: str = "Stable"
    momentum_percent: float = 0.0
    confidence: float = 0.0
    
    # AI insights
    ai_insight: str = ""
    reasoning: str = ""
    recommendations: List[str] = None
    
    # Predictions
    predicted_peak_viewers: int = 0
    predicted_peak_time: str = ""
    churn_risk: float = 0.0
    viral_potential: float = 0.0
    
    # Metadata
    data_sources: List[str] = None
    raw_response: str = ""
    
    def __post_init__(self):
        if self.recommendations is None:
            self.recommendations = []
        if self.data_sources is None:
            self.data_sources = []


class AIAnalyticsEngine(QObject):
    """AI-powered analytics engine.
    
    Replaces manual analytics calculations with AI-generated insights.
    Emits signals when analysis completes for UI updates.
    """
    
    # Signal emitted when AI analysis completes: (login, platform, analysis)
    analysis_complete = Signal(str, str, dict)
    
    def __init__(self):
        super().__init__()
        self.ai_client = get_ai_client()
        self._lock = threading.RLock()
        self._cache = {}  # login -> (analysis, timestamp)
        self._cache_ttl = 300  # 5 minutes
        
        # Feature flags
        self.enable_auto_pilot = get_setting("ai_auto_pilot", "false") == "true"
        self.enable_mood_detection = get_setting("ai_mood_detection", "false") == "true"
        
    def _get_cache_key(self, analysis_type: str, login: str, **kwargs) -> str:
        """Generate cache key."""
        return f"{analysis_type}:{login}:{json.dumps(kwargs, sort_keys=True)}"
    
    def _get_cached(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached analysis."""
        if cache_key in self._cache:
            analysis, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return analysis
            else:
                del self._cache[cache_key]
        return None
    
    def _set_cache(self, cache_key: str, analysis: Dict[str, Any]):
        """Cache analysis."""
        with self._lock:
            self._cache[cache_key] = (analysis, time.time())
    
    def analyze_stream(self, 
                       stream: Dict[str, Any], 
                       fetch_fresh: bool = False) -> Dict[str, Any]:
        """Analyze current stream using AI (non-blocking, returns cached or fallback).
        
        This replaces: update_stream() + calculate_score() + momentum calculations
        
        Args:
            stream: Stream data dict from API
            fetch_fresh: Force fresh AI analysis (skip cache)
            
        Returns:
            Analysis dict compatible with UI expectations
        """
        if not stream:
            return {}
        
        platform = stream.get("platform", "twitch")
        login = (
            stream.get("user_login")
            or stream.get("user_name")
            or stream.get("channel")
            or "unknown"
        ).lower().strip()
        
        if not self.ai_client:
            # Fallback to basic analysis without AI
            return self._fallback_analysis(stream)
        
        # Check cache first (fast path)
        cache_key = self._get_cache_key("stream", login, platform=platform)
        if not fetch_fresh:
            cached = self._get_cached(cache_key)
            if cached:
                debug(f"[AI_ANALYTICS] Cache hit for {login}")
                return cached
        
        # Return cached DB data or fallback immediately (don't block UI)
        # Background thread will update with fresh AI analysis
        streamer_data = get_streamer(login, platform=platform)
        if streamer_data:
            cached_ai = streamer_data.get("data", {}).get("ai_analysis", {})
            if cached_ai:
                debug(f"[AI_ANALYTICS] Returning cached DB data for {login}")
                return {
                    "channel": login,
                    "platform": platform,
                    "viewers": int(stream.get("viewer_count", 0)),
                    "category": stream.get("game_name", stream.get("game", "Unknown")),
                    "title": stream.get("title", ""),
                    "score": cached_ai.get("quality_score", 50),
                    "status": cached_ai.get("momentum", "Stable"),
                    "percent": cached_ai.get("momentum_percent", 0.0),
                    "confidence": cached_ai.get("confidence", 0.0),
                    "ai_insight": cached_ai.get("ai_insight", ""),
                    "sullygoose": {},
                }
        
        # Trigger background AI analysis (non-blocking)
        self._trigger_async_analysis(stream, login, platform, cache_key)
        
        # Return fallback immediately
        return self._fallback_analysis(stream)
    
    def _trigger_async_analysis(self, stream: Dict[str, Any], login: str, platform: str, cache_key: str):
        """Trigger AI analysis in background thread (non-blocking)."""
        def background_analysis():
            try:
                # Get historical data for context
                viewer_history = get_viewer_history(login, platform=platform, limit=50)
                streamer_data = get_streamer(login, platform=platform)
                
                # Prepare AI prompt
                system_prompt = """You are an expert streaming analytics AI. Analyze the provided stream data and viewer history to generate insights.
                
Respond ONLY with valid JSON in this exact format:
{
    "quality_score": 85,
    "momentum": "Rising",
    "momentum_percent": 12.5,
    "confidence": 0.92,
    "ai_insight": "Brief insight about the stream",
    "reasoning": "Why you gave this score",
    "recommendations": ["Recommendation 1", "Recommendation 2"],
    "predicted_peak_viewers": 25000,
    "predicted_peak_time": "in 45 minutes",
    "churn_risk": 0.15,
    "viral_potential": 0.72
}"""
                
                user_prompt = f"""Analyze this stream:
                
Current Stream Data:
- Channel: {login}
- Platform: {platform}
- Title: {stream.get('title', 'N/A')}
- Category: {stream.get('game_name', stream.get('game', 'N/A'))}
- Current Viewers: {stream.get('viewer_count', 0)}
- Started: {stream.get('started_at', 'N/A')}

Viewer History (last 50 samples):
{json.dumps(viewer_history[-10:], indent=2) if viewer_history else 'No history yet'}

Previous AI Analysis:
{json.dumps(streamer_data.get('data', {}).get('ai_analysis', {}), indent=2) if streamer_data else 'No previous analysis'}

Provide analysis in the exact JSON format specified."""
                
                # Call AI
                result = self.ai_client.call_ai_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    cache_key=cache_key,
                    cache_ttl=self._cache_ttl
                )
                
                if result["success"]:
                    ai_data = result.get("data", {})
                    
                    # Build analysis dict
                    analysis = {
                        "channel": login,
                        "platform": platform,
                        "viewers": int(stream.get("viewer_count", 0)),
                        "category": stream.get("game_name", stream.get("game", "Unknown")),
                        "title": stream.get("title", ""),
                        "score": ai_data.get("quality_score", 50),
                        "status": ai_data.get("momentum", "Stable"),
                        "percent": ai_data.get("momentum_percent", 0.0),
                        "confidence": ai_data.get("confidence", 0.0),
                        "ai_insight": ai_data.get("ai_insight", ""),
                        "reasoning": ai_data.get("reasoning", ""),
                        "recommendations": ai_data.get("recommendations", []),
                        "predicted_peak_viewers": ai_data.get("predicted_peak_viewers", 0),
                        "predicted_peak_time": ai_data.get("predicted_peak_time", ""),
                        "churn_risk": ai_data.get("churn_risk", 0.0),
                        "viral_potential": ai_data.get("viral_potential", 0.0),
                        "sullygoose": {},
                        "ai_timestamp": result.get("timestamp"),
                        "data_sources": ["viewer_history", "ai_analysis"]
                    }
                    
                    # Cache result
                    self._set_cache(cache_key, analysis)
                    
                    # Update streamer data
                    self._update_streamer_ai_data(login, platform, analysis, ai_data)
                    
                    # Emit signal for UI update (thread-safe via Qt)
                    self.analysis_complete.emit(login, platform, analysis)
                    
                    debug(f"[AI_ANALYTICS] Background analysis complete for {login}: score={analysis['score']}")
                else:
                    debug(f"[AI_ANALYTICS] Background AI call failed for {login}: {result.get('error')}")
                    
            except Exception as e:
                debug(f"[AI_ANALYTICS] Background analysis error for {login}: {e}")
        
        # Run in background thread to avoid blocking UI
        thread = threading.Thread(target=background_analysis, daemon=True)
        thread.start()
    
    def analyze_streamer_profile(self, login: str, platform: str = "twitch") -> Dict[str, Any]:
        """Generate comprehensive AI profile for a streamer.
        
        This replaces manual profile building with AI-generated insights.
        Called weekly or on-demand.
        """
        if not self.ai_client:
            return {}
        
        # Get comprehensive data
        viewer_history = get_viewer_history(login, platform=platform, limit=200)
        streamer_data = get_streamer(login, platform=platform)
        
        if not viewer_history and not streamer_data:
            return {}
        
        system_prompt = """You are an expert streaming analyst. Create a comprehensive psychological and performance profile for this streamer.
        
Respond ONLY with valid JSON:
{
    "psychographic_profile": {
        "personality": "Brief personality description",
        "streaming_style": "Content style",
        "strengths": ["Strength 1", "Strength 2"],
        "weaknesses": ["Weakness 1"],
        "unique_value": "What makes them special"
    },
    "optimal_strategy": {
        "best_stream_times": ["Day HH:MM-HH:MM"],
        "optimal_duration": "X hours",
        "best_categories": ["Category 1", "Category 2"],
        "recommended_tone": "Tone description"
    },
    "predictive_model": {
        "avg_viewers_by_time": {"morning": 5000, "afternoon": 8000, "evening": 15000},
        "growth_potential": 0.82,
        "churn_risk": 0.15,
        "viral_threshold": "25K viewers"
    },
    "audience_insights": {
        "demographic": "Target audience",
        "engagement_level": "High/Medium/Low",
        "retention_rate": "75%"
    }
}"""
        
        user_prompt = f"""Create a comprehensive profile for streamer: {login}
        
Platform: {platform}
Streamer Data: {json.dumps(streamer_data.get('data', {}), indent=2) if streamer_data else '{}'}

Viewer History (last 200 samples):
{json.dumps(viewer_history[:20], indent=2) if viewer_history else 'No history'}

Generate a detailed profile in the exact JSON format specified."""
        
        result = self.ai_client.call_ai_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            cache_key=f"profile:{login}:{platform}",
            cache_ttl=86400  # Cache for 24 hours
        )
        
        if not result["success"]:
            return {}
        
        profile_data = result.get("data", {})
        
        # Store in streamer data
        streamer = get_streamer(login, platform=platform)
        if streamer:
            current_data = streamer.get("data", {})
            current_data["ai_profile"] = profile_data
            current_data["ai_profile_last_updated"] = result.get("timestamp")
            store_streamer(
                login=login,
                name=streamer.get("name", login),
                avatar_url=streamer.get("avatar_url", ""),
                viewers=streamer.get("last_viewers", 0),
                data=current_data,
                platform=platform
            )
        
        debug(f"[AI_ANALYTICS] Generated profile for {login}")
        return profile_data
    
    def get_ai_analysis(self, login: str, platform: str = "twitch") -> Dict[str, Any]:
        """Get cached AI analysis for a streamer.
        
        This is the main method UI components should call.
        """
        streamer = get_streamer(login, platform=platform)
        if not streamer:
            return {}
        
        data = streamer.get("data", {})
        return data.get("ai_analysis", {})
    
    def _update_streamer_ai_data(self, 
                                 login: str, 
                                 platform: str, 
                                 analysis: Dict[str, Any],
                                 ai_data: Dict[str, Any]):
        """Update streamer record with AI analysis."""
        streamer = get_streamer(login, platform=platform)
        if not streamer:
            return
        
        current_data = streamer.get("data", {})
        current_data["ai_analysis"] = {
            "quality_score": analysis.get("score"),
            "momentum": analysis.get("status"),
            "momentum_percent": analysis.get("percent"),
            "confidence": analysis.get("confidence"),
            "ai_insight": analysis.get("ai_insight"),
            "reasoning": analysis.get("reasoning"),
            "recommendations": analysis.get("recommendations", []),
            "predicted_peak_viewers": analysis.get("predicted_peak_viewers"),
            "predicted_peak_time": analysis.get("predicted_peak_time"),
            "churn_risk": analysis.get("churn_risk"),
            "viral_potential": analysis.get("viral_potential"),
            "last_analyzed": analysis.get("ai_timestamp"),
            "raw_ai_response": ai_data
        }
        
        store_streamer(
            login=login,
            name=streamer.get("name", login),
            avatar_url=streamer.get("avatar_url", ""),
            viewers=analysis.get("viewers", 0),
            data=current_data,
            platform=platform
        )
    
    def _fallback_analysis(self, stream: Dict[str, Any]) -> Dict[str, Any]:
        """Basic analysis without AI (fallback). Includes derived metrics."""
        viewers = int(stream.get("viewer_count", 0))
        
        # Simple scoring
        if viewers >= 10000:
            score = 75
        elif viewers >= 1000:
            score = 50
        elif viewers >= 100:
            score = 25
        else:
            score = 10
        
        # Momentum from stream delta if available
        status = "Stable"
        percent = 0.0
        
        # Confidence based on data availability
        confidence = 0.3
        
        # Health: combined score
        health = min(100, int(score * 0.7 + confidence * 30))
        
        # Retention: estimate from viewer level
        if viewers > 10000:
            retention = 85
        elif viewers > 1000:
            retention = 70
        elif viewers > 100:
            retention = 55
        else:
            retention = 40
        
        # Engagement: estimate from viewer level
        if viewers > 10000:
            viral = 0.7
        elif viewers > 1000:
            viral = 0.4
        elif viewers > 100:
            viral = 0.2
        else:
            viral = 0.1
        
        return {
            "channel": stream.get("user_login", "unknown"),
            "platform": stream.get("platform", "twitch"),
            "viewers": viewers,
            "category": stream.get("game_name", stream.get("game", "Unknown")),
            "title": stream.get("title", ""),
            "score": score,
            "status": status,
            "percent": percent,
            "confidence": confidence,
            "health": health,
            "retention": retention,
            "churn_risk": round(1.0 - retention / 100.0, 2),
            "viral_potential": viral,
            "predicted_peak_viewers": viewers,
            "ai_insight": "",
            "sullygoose": {},
            "recommendations": [],
        }
    
    # ── 36-Metric Dashboard Analysis ─────────────────────────────────────

    def analyze_dashboard_metrics(
        self,
        stream: Dict[str, Any],
        viewer_history: Optional[List[Dict]] = None,
        chat_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Compute all 36 dashboard metrics from stream data + local metrics.

        Args:
            stream: Current stream data dict from API
            viewer_history: Recent viewer history samples from DB
            chat_metrics: Locally-tracked chat metrics from ViewerMonitor
                Expected keys: chat_rate, chat_density, emote_ratio,
                avg_msg_length, new_chatters, unique_chatters

        Returns:
            Dict with all 36 metric values keyed by short labels.
        """
        viewers = int(stream.get("viewer_count", 0))
        started_at = stream.get("started_at", "")
        game_name = stream.get("game_name", stream.get("game", "Unknown"))
        title = stream.get("title", "")

        # Viewer history stats
        vh = viewer_history or []
        vh_counts = [h.get("viewers", 0) for h in vh]

        session_peak = max(vh_counts) if vh_counts else viewers
        session_avg = int(sum(vh_counts) / len(vh_counts)) if vh_counts else viewers

        # Viewer velocity: avg change per sample over last 10 samples
        velocity = 0.0
        if len(vh_counts) >= 2:
            recent = vh_counts[:10]
            deltas = [recent[i] - recent[i + 1] for i in range(len(recent) - 1)]
            velocity = sum(deltas) / len(deltas) if deltas else 0.0

        # Viewer volatility: normalized std-dev (0-100)
        volatility = 0.0
        if len(vh_counts) >= 3:
            mean_v = sum(vh_counts) / len(vh_counts)
            variance = sum((v - mean_v) ** 2 for v in vh_counts) / len(vh_counts)
            stddev = variance ** 0.5
            volatility = min(100.0, (stddev / max(mean_v, 1)) * 100)

        # Unique viewer estimate (rough: based on churn rate)
        churn_risk_est = 0.3
        if vh_counts and len(vh_counts) >= 5:
            # Count distinct viewer levels as proxy for turnover
            distinct = len(set(vh_counts))
            churn_risk_est = min(0.8, distinct / max(len(vh_counts), 1))
        unique_est = int(viewers * (1.0 + churn_risk_est * 0.5))

        # Chat metrics (from local tracking or defaults)
        cm = chat_metrics or {}
        chat_rate = cm.get("chat_rate", 0.0)
        chat_density = cm.get("chat_density", 0.0)
        emote_ratio = cm.get("emote_ratio", 0.0)
        avg_msg_len = cm.get("avg_msg_length", 0.0)
        new_chatters = cm.get("new_chatters", 0)

        # Sentiment (from AI or neutral default)
        sentiment = cm.get("sentiment", 0.0)

        # Stream duration
        duration_str = "0h 0m"
        duration_minutes = 0
        if started_at:
            try:
                from datetime import datetime, timezone
                # Handle various ISO formats
                sa = started_at.replace("Z", "+00:00")
                start_dt = datetime.fromisoformat(sa)
                now = datetime.now(timezone.utc)
                delta = now - start_dt
                duration_minutes = int(delta.total_seconds() / 60)
                hours = duration_minutes // 60
                mins = duration_minutes % 60
                duration_str = f"{hours}h {mins}m"
            except Exception:
                pass

        # Game changes (tracked in viewer history metadata)
        game_changes = cm.get("game_changes", 0)

        # Title score (AI-computed or heuristic)
        title_score = self._heuristic_title_score(title)

        # Tag coverage (AI-computed or heuristic)
        tag_score = self._heuristic_tag_score(title, game_name)

        # Content freshness (minutes since last metadata change)
        freshness = cm.get("freshness_minutes", duration_minutes)

        # Growth metrics
        follow_rate = cm.get("follow_rate", 0.0)
        growth_trajectory = viewers  # fallback
        if len(vh_counts) >= 5:
            # Linear projection: fit trend to last N points
            n = min(len(vh_counts), 20)
            recent_counts = list(reversed(vh_counts[:n]))
            if n >= 2:
                x_mean = (n - 1) / 2.0
                y_mean = sum(recent_counts) / n
                num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(recent_counts))
                den = sum((i - x_mean) ** 2 for i in range(n))
                slope = num / den if den != 0 else 0
                # Project 1 hour forward (samples every ~4s → 900 samples/hr)
                growth_trajectory = max(0, int(viewers + slope * 900))

        loyalty = cm.get("audience_loyalty", max(30, min(95, 100 - int(volatility))))
        discovery = self._compute_discovery(viewers, title_score, tag_score)
        raid_potential = cm.get("raid_potential", max(10, min(80, int(viewers / 100))))
        network_effect = cm.get("network_effect", 50)

        # Performance metrics
        bounce_rate = self._compute_bounce_rate(velocity, viewers, volatility)
        session_depth = cm.get("session_depth", max(5, min(120, duration_minutes // max(1, len(vh_counts) or 1))))
        peak_efficiency = 0.0
        if duration_minutes > 0:
            peak_efficiency = round((viewers / (duration_minutes / 60.0)), 1) if duration_minutes >= 5 else 0.0
        consistency = cm.get("consistency_score", 60)
        uptime_score = cm.get("uptime_score", 95)
        stream_health = min(100, int(
            (100 - bounce_rate) * 0.3 +
            uptime_score * 0.3 +
            (100 - volatility) * 0.2 +
            loyalty * 0.2
        ))

        # AI Insights
        competitive = self._compute_competitive_index(viewers, session_avg)
        audience_match = cm.get("audience_match", 65)
        optimal_remaining = self._compute_optimal_remaining(duration_minutes, velocity, viewers)
        best_category = cm.get("best_category", game_name)
        monetization = self._compute_monetization_score(loyalty, viewers, chat_rate, sentiment)
        overall_rank = self._compute_rank(
            viewers, velocity, sentiment, loyalty, bounce_rate,
            stream_health, title_score, discovery
        )

        return {
            # Viewer Dynamics
            "viewers": viewers,
            "session_peak": session_peak,
            "session_avg": session_avg,
            "velocity": round(velocity, 1),
            "volatility": round(volatility, 1),
            "unique_est": unique_est,
            # Engagement
            "chat_rate": round(chat_rate, 1),
            "chat_density": round(chat_density, 1),
            "emote_ratio": round(emote_ratio, 1),
            "sentiment": round(sentiment, 1),
            "avg_msg_len": round(avg_msg_len, 1),
            "new_chatters": new_chatters,
            # Content
            "cat_rank": max(1, int(viewers / max(1, viewers // 50 + 1))),
            "duration": duration_str,
            "duration_minutes": duration_minutes,
            "game_changes": game_changes,
            "title_score": title_score,
            "tag_score": tag_score,
            "freshness": freshness,
            # Growth
            "follow_rate": round(follow_rate, 1),
            "growth_trajectory": growth_trajectory,
            "loyalty": loyalty,
            "discovery": discovery,
            "raid_potential": raid_potential,
            "network_effect": network_effect,
            # Performance
            "bounce_rate": bounce_rate,
            "session_depth": session_depth,
            "peak_efficiency": peak_efficiency,
            "consistency": consistency,
            "uptime_score": uptime_score,
            "stream_health": stream_health,
            # AI Insights
            "competitive_index": competitive,
            "audience_match": audience_match,
            "optimal_remaining": optimal_remaining,
            "best_category": best_category,
            "monetization": monetization,
            "overall_rank": overall_rank,
            # Metadata
            "sentiment_raw": sentiment,
        }

    # ── Helper computations for dashboard metrics ───────────────────────

    def _heuristic_title_score(self, title: str) -> int:
        """Quick heuristic score for a stream title (0-100)."""
        if not title:
            return 10
        score = 40
        length = len(title)
        if 20 <= length <= 80:
            score += 15
        if any(c in title for c in "!?🔥💀🎉🎊"):
            score += 10
        # Has caps words (excitement)
        words = title.split()
        caps = sum(1 for w in words if w.isupper() and len(w) > 1)
        if caps > 0:
            score += min(15, caps * 5)
        # Has hashtags or mentions
        if "#" in title:
            score += 5
        # Length penalty for very short/long
        if length < 5:
            score -= 20
        if length > 120:
            score -= 10
        return max(5, min(100, score))

    def _heuristic_tag_score(self, title: str, game: str) -> int:
        """Quick heuristic for tag-content alignment."""
        if not title or not game:
            return 30
        title_lower = title.lower()
        game_lower = game.lower()
        # Check if game name appears in title
        if game_lower in title_lower:
            return 80
        # Check for common genre words
        genre_words = ["fps", "moba", "rpg", "mmo", "horror", "speedrun",
                       "challenge", "ranked", "competitive", "casual", "variety"]
        matches = sum(1 for w in genre_words if w in title_lower)
        return max(30, min(100, 40 + matches * 10))

    def _compute_discovery(self, viewers: int, title_score: int, tag_score: int) -> int:
        """How discoverable the stream is."""
        # Higher viewers + better title + better tags = more discoverable
        viewer_component = min(40, int(viewers / 250))
        return max(5, min(100, viewer_component + title_score * 0.3 + tag_score * 0.3))

    def _compute_bounce_rate(self, velocity: float, viewers: int, volatility: float) -> int:
        """Estimate bounce rate from viewer velocity and volatility."""
        if viewers < 10:
            return 50
        # Negative velocity (losing viewers) = higher bounce
        vel_factor = max(0, min(40, int(-velocity / 10)))
        vol_factor = max(0, int(volatility * 0.3))
        base = 20
        return max(5, min(95, base + vel_factor + vol_factor))

    def _compute_competitive_index(self, viewers: int, avg: int) -> int:
        """How the stream compares to its own average."""
        if avg <= 0:
            return 50
        ratio = viewers / avg
        return max(5, min(100, int(ratio * 50)))

    def _compute_optimal_remaining(self, duration_min: int, velocity: float,
                                    viewers: int) -> str:
        """AI-suggested remaining stream time."""
        if duration_min < 30:
            return "2h+"
        if velocity > 10 and viewers > 500:
            return "1-2h"
        if velocity > 0:
            return "1h"
        if velocity < -5:
            return "30m"
        if duration_min > 240:  # 4+ hours
            return "30m"
        return "1h"

    def _compute_monetization_score(self, loyalty: int, viewers: int,
                                     chat_rate: float, sentiment: float) -> int:
        """Revenue potential index."""
        viewer_factor = min(40, int(viewers / 250))
        loyalty_factor = int(loyalty * 0.3)
        chat_factor = min(15, int(chat_rate * 3))
        sentiment_factor = max(0, int((sentiment + 100) / 200 * 15))
        return max(5, min(100, viewer_factor + loyalty_factor + chat_factor + sentiment_factor))

    def _compute_rank(self, viewers, velocity, sentiment, loyalty,
                       bounce, health, title, discovery) -> str:
        """Compute overall letter grade."""
        score = (
            min(25, viewers / 400) +
            min(15, max(0, velocity / 5 + 7.5)) +
            min(15, (sentiment + 100) / 200 * 15) +
            loyalty * 0.15 +
            (100 - bounce) * 0.1 +
            health * 0.1 +
            title * 0.05 +
            discovery * 0.05
        )
        if score >= 90:
            return "A+"
        elif score >= 80:
            return "A"
        elif score >= 70:
            return "B+"
        elif score >= 60:
            return "B"
        elif score >= 50:
            return "C+"
        elif score >= 40:
            return "C"
        elif score >= 30:
            return "D"
        else:
            return "F"

    def get_external_data(self, login, platform="twitch"):
        """Return SullyGoose data from database cache."""
        try:
            from core.db import get_sg
            return get_sg(login, platform=platform)
        except Exception:
            return None

    def get_quality_score(self, login: str, platform: str = "twitch") -> int:
        """Get AI-generated quality score for a streamer."""
        analysis = self.get_ai_analysis(login, platform)
        return analysis.get("quality_score", 0)
    
    def get_momentum(self, login: str, platform: str = "twitch") -> Dict[str, Any]:
        """Get AI-generated momentum for a streamer."""
        analysis = self.get_ai_analysis(login, platform)
        return {
            "status": analysis.get("momentum", "Stable"),
            "percent": analysis.get("momentum_percent", 0.0),
            "confidence": analysis.get("confidence", 0.0)
        }
    
    def should_switch_channel(self, 
                              current_stream: Dict[str, Any],
                              alternative_streams: List[Dict[str, Any]]) -> Dict[str, Any]:
        """AI Auto-Pilot: Determine if we should switch channels.
        
        Returns:
            {
                "action": "SWITCH"|"WAIT"|"STAY",
                "target_channel": "login" or None,
                "confidence": 0.95,
                "reasoning": "Why"
            }
        """
        if not self.ai_client or not self.enable_auto_pilot:
            return {"action": "STAY", "confidence": 0.0, "reasoning": "Auto-Pilot disabled"}
        
        current_login = current_stream.get("user_login", "unknown")
        current_analysis = self.get_ai_analysis(current_login, current_stream.get("platform", "twitch"))
        
        system_prompt = """You are an intelligent streaming assistant. Decide whether to switch channels based on current and alternative streams.
        
Respond ONLY with valid JSON:
{
    "action": "SWITCH" or "WAIT" or "STAY",
    "target_channel": "channel_login or null",
    "confidence": 0.95,
    "reasoning": "Brief explanation"
}"""
        
        user_prompt = f"""Current Stream:
- Channel: {current_login}
- Score: {current_analysis.get('quality_score', 0)}
- Momentum: {current_analysis.get('momentum', 'Unknown')}
- Viewers: {current_stream.get('viewer_count', 0)}
- AI Insight: {current_analysis.get('ai_insight', 'N/A')}

Alternative Live Channels:
{json.dumps([{k: s.get(k) for k in ['user_login', 'user_name', 'viewer_count', 'game_name', 'platform']} for s in alternative_streams[:5]], indent=2)}

User Preferences:
- Auto-Pilot enabled: {self.enable_auto_pilot}

Decide: SWITCH to better channel, WAIT (current may improve), or STAY (current is best)."""
        
        result = self.ai_client.call_ai_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            cache_key=f"autopilot:{current_login}:{int(time.time() / 120)}",  # Cache for 2 minutes
            cache_ttl=120
        )
        
        if not result["success"]:
            return {"action": "STAY", "confidence": 0.0, "reasoning": "AI unavailable"}
        
        decision = result.get("data", {})
        debug(f"[AI_AUTOPILOT] Decision for {current_login}: {decision.get('action')} (confidence: {decision.get('confidence')})")
        return decision
    
    def detect_user_mood(self) -> Dict[str, Any]:
        """Mood Detection: Analyze user engagement level.
        
        Returns:
            {
                "mood": "engaged"|"bored"|"neutral",
                "engagement_score": 0.85,
                "indicators": ["High chat activity", "Long watch session"]
            }
        """
        if not self.ai_client or not self.enable_mood_detection:
            return {"mood": "neutral", "engagement_score": 0.5}
        
        # This would integrate with chat activity and user behavior
        # Simplified for now
        return {
            "mood": "engaged",
            "engagement_score": 0.8,
            "indicators": ["Active watcher"]
        }
    
    def log_for_ai_analysis(self, level: str, message: str):
        """Send logs to Azure AI for analysis (non-blocking).
        
        This allows AI to analyze app behavior and suggest improvements.
        Runs in background thread to avoid blocking.
        """
        if not self.ai_client:
            return
        
        # Don't spam AI with logs - sample 1 in 10
        import random
        if random.random() > 0.1:
            return
        
        def analyze_log():
            try:
                system_prompt = """You are an expert at analyzing application logs. Identify patterns, anomalies, and potential issues.
                
Respond ONLY with valid JSON:
{
    "severity": "low|medium|high|critical",
    "category": "error|warning|info|performance|security",
    "suggested_action": "What should be done about this",
    "pattern_detected": "Any recurring patterns",
    "confidence": 0.0-1.0
}"""
                
                user_prompt = f"Analyze this log entry:\n[{level}] {message}"
                
                result = self.ai_client.call_ai_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    cache_key=f"log:{hash(message)}",
                    cache_ttl=3600  # Cache for 1 hour
                )
                
                if result["success"]:
                    analysis = result.get("data", {})
                    if analysis.get("severity") in ("high", "critical"):
                        debug(f"[AI_LOG] Critical issue detected: {analysis.get('suggested_action')}")
            except:
                pass
        
        thread = threading.Thread(target=analyze_log, daemon=True)
        thread.start()
    
    def close(self):
        """Clean shutdown."""
        debug("[AI_ANALYTICS] Engine closed")


# Global singleton
_ai_engine = None

def get_ai_analytics_engine() -> Optional[AIAnalyticsEngine]:
    """Get the global AI analytics engine instance."""
    global _ai_engine
    if _ai_engine is None:
        _ai_engine = AIAnalyticsEngine()
    return _ai_engine
