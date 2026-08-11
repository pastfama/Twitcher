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
