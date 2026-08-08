"""Central Analytics Engine - The Brain of the Application.

This is the unified data hub that:
- Creates and manages user profiles on first connect
- Fetches data from all platform sources (Twitch, Kick, YouTube)
- Processes and analyzes chat/social data
- Stores data in SQLite + memory cache
- Pushes updates to widgets via signals
- Provides single API for all data access

Replaces the old analytics_engine.py and sullygoose_api/ entirely.
"""

import threading
import time
import json
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from collections import deque

from logger import debug
from core.analytics_db import AnalyticsDB


@dataclass
class UserProfile:
    """Comprehensive user profile - the core data model."""
    user_id: str
    login: str
    display_name: str = ""
    platforms: List[str] = None
    profile_image_url: str = ""
    bio: str = ""
    account_created: int = 0
    account_type: str = ""
    
    # Streaming Stats
    first_stream_timestamp: int = 0
    total_view_time_minutes: float = 0.0
    total_streams_watched: int = 0
    peak_viewers_seen: int = 0
    avg_viewers_across_streams: float = 0.0
    
    # Engagement
    chat_messages_total: int = 0
    chat_messages_per_minute: float = 0.0
    chat_active_minutes: int = 0
    chat_peak_activity_hour: int = 0
    emotes_used: Dict[str, int] = None
    bits_cheered_total: int = 0
    subs_gifted_total: int = 0
    
    # Social Graph
    frequent_chat_partners: List[str] = None
    raid_chain: List[str] = None
    mutuals_list: List[str] = None
    clippers_list: List[str] = None
    
    # Content Analysis
    categories_watched: List[str] = None
    favorite_category: str = ""
    stream_language: str = ""
    stream_timezone: str = ""
    
    # Predictive
    churn_risk_score: float = 0.0
    next_stream_prediction: int = 0
    preferred_hours: List[int] = None
    predicted_viewer_curve: List[float] = None
    
    # Metadata
    profile_created_at: int = 0
    profile_updated_at: int = 0
    last_active: int = 0
    stale: bool = False
    data_sources: List[str] = None
    
    # Extensible JSON blobs
    preferences_json: Dict = None
    technical_telemetry_json: Dict = None
    achievement_data_json: Dict = None
    session_history_json: List[Dict] = None
    chat_analysis_json: Dict = None
    social_graph_json: Dict = None
    
    def __post_init__(self):
        if self.platforms is None:
            self.platforms = []
        if self.emotes_used is None:
            self.emotes_used = {}
        if self.frequent_chat_partners is None:
            self.frequent_chat_partners = []
        if self.raid_chain is None:
            self.raid_chain = []
        if self.mutuals_list is None:
            self.mutuals_list = []
        if self.clippers_list is None:
            self.clippers_list = []
        if self.categories_watched is None:
            self.categories_watched = []
        if self.preferred_hours is None:
            self.preferred_hours = []
        if self.predicted_viewer_curve is None:
            self.predicted_viewer_curve = []
        if self.data_sources is None:
            self.data_sources = []
        if self.preferences_json is None:
            self.preferences_json = {}
        if self.technical_telemetry_json is None:
            self.technical_telemetry_json = {}
        if self.achievement_data_json is None:
            self.achievement_data_json = {}
        if self.session_history_json is None:
            self.session_history_json = []
        if self.chat_analysis_json is None:
            self.chat_analysis_json = {}
        if self.social_graph_json is None:
            self.social_graph_json = {}


class AnalyticsEngine:
    """Central brain for all analytics data.
    
    Responsibilities:
    - User profile creation and management
    - Data fetching from platform sources
    - Real-time statistics tracking
    - Chat and social graph analysis
    - Predictive analytics
    - Widget data provision
    - Signal-based UI updates
    """
    
    def __init__(self, db: Optional[AnalyticsDB] = None):
        self.db = db or AnalyticsDB()
        
        # In-memory caches for fast access
        self._profile_cache: Dict[str, UserProfile] = {}
        self._stats_cache: Dict[str, Dict[str, Any]] = {}
        self._external_cache: Dict[str, Dict[str, Any]] = {}
        
        # Cache settings
        self._cache_ttl = 300  # 5 minutes
        
        # Current state
        self.current_user_id: Optional[str] = None
        self.current_profile: Optional[UserProfile] = None
        
        # Signal system for UI updates
        self._listeners: List[Callable] = []
        self._profile_listeners: List[Callable] = []
        
        # Background tasks
        self._lock = threading.RLock()
        self._pending_fetches = set()
        self._failed_fetches: Dict[str, int] = {}
        self._fetch_cooldown = 300  # 5 minutes
        self._last_fetch_times: Dict[str, int] = {}  # Throttle: track last fetch time per channel
        self._fetch_interval = 120  # Minimum 2 minutes between fetches for same channel
        
        # Load existing profiles
        self._load_all_profiles()
    
    # ================================================================
    # PROFILE MANAGEMENT (First Connect)
    # ================================================================
    
    def create_user_profile(self, user_data: Dict[str, Any]) -> UserProfile:
        """Create comprehensive profile on first connect.
        
        Call this when user first connects their Twitch/Kick/YouTube account.
        Captures all available identity data at creation time.
        """
        user_id = user_data.get("id") or user_data.get("user_id")
        if not user_id:
            raise ValueError("user_id required for profile creation")
        
        # Check if profile already exists
        if user_id in self._profile_cache:
            profile = self._profile_cache[user_id]
            profile.last_active = int(time.time())
            profile.stale = False
            self.db.store_profile(asdict(profile))
            return profile
        
        # Create new profile
        now = int(time.time())
        profile = UserProfile(
            user_id=user_id,
            login=user_data.get("login", "").lower(),
            display_name=user_data.get("display_name", user_data.get("login", "")),
            platforms=[user_data.get("platform", "twitch")],
            profile_image_url=user_data.get("profile_image_url", ""),
            bio=user_data.get("bio", ""),
            account_created=user_data.get("account_created", 0),
            account_type=user_data.get("account_type", ""),
            
            # Streaming stats (empty initially)
            first_stream_timestamp=0,
            total_view_time_minutes=0.0,
            total_streams_watched=0,
            peak_viewers_seen=0,
            avg_viewers_across_streams=0.0,
            
            # Engagement (empty initially)
            chat_messages_total=0,
            chat_messages_per_minute=0.0,
            chat_active_minutes=0,
            chat_peak_activity_hour=0,
            emotes_used={},
            bits_cheered_total=0,
            subs_gifted_total=0,
            
            # Social graph (empty initially)
            frequent_chat_partners=[],
            raid_chain=[],
            mutuals_list=[],
            clippers_list=[],
            
            # Content analysis (empty initially)
            categories_watched=[],
            favorite_category="",
            stream_language=user_data.get("language", ""),
            stream_timezone="",
            
            # Predictive (defaults)
            churn_risk_score=0.0,
            next_stream_prediction=0,
            preferred_hours=[],
            predicted_viewer_curve=[],
            
            # Metadata
            profile_created_at=now,
            profile_updated_at=now,
            last_active=now,
            stale=False,
            data_sources=["first_connect"],
            
            # Extensible blobs
            preferences_json={},
            technical_telemetry_json={},
            achievement_data_json={},
            session_history_json=[],
            chat_analysis_json={},
            social_graph_json={},
        )
        
        # Store in cache and DB
        self._profile_cache[user_id] = profile
        self.db.store_profile(asdict(profile))
        
        debug(f"[ANALYTICS] Created profile for {profile.login} ({user_id})")
        
        # Notify listeners
        self._notify_profile_listeners(profile)
        
        return profile
    
    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get user profile from cache or DB."""
        # Check cache first
        if user_id in self._profile_cache:
            profile = self._profile_cache[user_id]
            if not profile.stale:
                return profile
        
        # Load from DB
        profile_data = self.db.load_profile(user_id)
        if profile_data:
            profile = UserProfile(**profile_data)
            self._profile_cache[user_id] = profile
            return profile
        
        return None
    
    def update_profile(self, user_id: str, updates: Dict[str, Any]):
        """Update specific fields of a user profile."""
        profile = self.get_profile(user_id)
        if not profile:
            debug(f"[ANALYTICS] Profile not found for {user_id}, cannot update")
            return
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        
        profile.profile_updated_at = int(time.time())
        profile.last_active = int(time.time())
        
        # Persist
        self.db.store_profile(asdict(profile))
        
        # Notify
        self._notify_profile_listeners(profile)
    
    def _load_all_profiles(self):
        """Load all profiles from DB into memory cache."""
        profiles = self.db.list_profiles()
        for profile_data in profiles:
            user_id = profile_data["user_id"]
            full_profile = self.db.load_profile(user_id)
            if full_profile:
                profile = UserProfile(**full_profile)
                self._profile_cache[user_id] = profile
        debug(f"[ANALYTICS] Loaded {len(self._profile_cache)} profiles from DB")
    
    # ================================================================
    # EXTERNAL DATA FETCHING (Platform Sources)
    # ================================================================
    
    def get_external_data(self, login: str, platform: str = "twitch") -> Optional[Dict[str, Any]]:
        """Get external analytics data (from Twitch/Kick/YouTube).
        
        This is the agnostic interface for data providers.
        Checks cache first, then triggers background fetch if needed.
        """
        cache_key = f"{platform}:{login}"
        
        # Check memory cache
        if cache_key in self._external_cache:
            cached = self._external_cache[cache_key]
            if time.time() - cached.get("timestamp", 0) < self._cache_ttl:
                debug(f"[ANALYTICS] Returning cached data for {login} ({platform})")
                return cached.get("data")
            else:
                # Cache is expired, remove it
                debug(f"[ANALYTICS] Memory cache expired for {login} ({platform}), checking DB")
                del self._external_cache[cache_key]
        
        # Check DB cache
        db_cached = self.db.load_channel_stats(login, platform, max_age_seconds=self._cache_ttl)
        if db_cached:
            debug(f"[ANALYTICS] Returning DB cached data for {login} ({platform})")
            self._external_cache[cache_key] = {
                "data": db_cached,
                "timestamp": time.time(),
            }
            return db_cached
        
        # Trigger background fetch
        debug(f"[ANALYTICS] No cached data for {login} ({platform}), triggering fetch")
        self._ensure_async_fetch(login, platform)
        return None
    
    def _ensure_async_fetch(self, login: str, platform: str = "twitch"):
        """Start background fetch if not already in flight and throttle allows."""
        fetch_key = f"{platform}:{login}"
        now = time.time()
        
        with self._lock:
            if fetch_key in self._pending_fetches:
                debug(f"[ANALYTICS] Fetch already pending for {login} ({platform})")
                return
            
            # Throttle: don't fetch same channel more than once per interval
            last_fetch = self._last_fetch_times.get(fetch_key, 0)
            if now - last_fetch < self._fetch_interval:
                debug(f"[ANALYTICS] Throttling {login} ({platform}) - fetched {int(now - last_fetch)}s ago")
                return
            
            last_fail = self._failed_fetches.get(fetch_key)
            if last_fail and (now - last_fail < self._fetch_cooldown):
                debug(f"[ANALYTICS] Skipping {login} ({platform}) - recent failure")
                return
            
            self._pending_fetches.add(fetch_key)
            self._last_fetch_times[fetch_key] = now
        
        debug(f"[ANALYTICS] Starting background fetch for {login} ({platform})")
        
        thread = threading.Thread(
            target=self._fetch_worker,
            args=(login, platform, fetch_key),
            name=f"AnalyticsFetch-{login}",
            daemon=True,
        )
        thread.start()
    
    def _fetch_worker(self, login: str, platform: str, fetch_key: str):
        """Background worker to fetch analytics data."""
        try:
            # Get data from platform provider
            data = self._fetch_data_for_platform(login, platform)
            
            if data:
                # Cache in memory
                with self._lock:
                    self._external_cache[fetch_key] = {
                        "data": data,
                        "timestamp": time.time(),
                    }
                
                # Persist to DB
                self.db.store_channel_stats(login, platform, data, source="mock")
                
                # Notify UI via signal
                self._notify_data_ready(login, platform, data)
                
                debug(f"[ANALYTICS] Fetched data for {login} ({platform}): {len(data)} fields")
            else:
                debug(f"[ANALYTICS] No data returned for {login} ({platform})")
                self._failed_fetches[fetch_key] = time.time()
        
        except Exception as exc:
            debug(f"[ANALYTICS] Fetch error for {login} ({platform}): {exc}")
            self._failed_fetches[fetch_key] = time.time()
        
        finally:
            with self._lock:
                self._pending_fetches.discard(fetch_key)
    
    def _fetch_data_for_platform(self, login: str, platform: str) -> Optional[Dict[str, Any]]:
        """Fetch data for a specific platform.
        
        This is the agnostic interface - platform-specific implementations
        will be added later. Currently returns mock data for testing.
        """
        if platform == "twitch":
            return {
                "login": login,
                "avg_viewers": 1234,
                "peak_viewers": 5678,
                "viewer_growth": 15.5,
                "category_rank": 42,
                "stream_frequency": 2.5,
                "avg_stream_duration": 3.5,
                "games_played_30d": 7,
                "main_game_pct": 35.5,
                "follower_count": 12345,
                "follower_growth_30d": 2.5,
                "chat_activity": "High",
                "consistency_score": 75,
                "reliability_score": 85,
                "discovery_score": 65,
            }
        return None
    
    def fetch_all_live_channels(self, channels: List[Dict[str, Any]]):
        """Fetch analytics data for all live channels.
        
        Non-blocking - checks cache first, triggers background fetches
        for uncached channels.
        """
        if not channels:
            return
        
        for stream in channels:
            login = (
                stream.get("user_login")
                or stream.get("user_name")
                or stream.get("channel")
                or ""
            ).lower().strip()
            platform = stream.get("platform", "twitch")
            
            if login:
                self.get_external_data(login, platform)
    
    # ================================================================
    # SIGNAL SYSTEM (Push data to widgets)
    # ================================================================
    
    def add_listener(self, callback: Callable[[str, str, Dict[str, Any]], None]):
        """Add listener for external data updates.
        
        Callback signature: (login, platform, data) -> None
        """
        self._listeners.append(callback)
    
    def add_profile_listener(self, callback: Callable[[UserProfile], None]):
        """Add listener for profile updates."""
        self._profile_listeners.append(callback)
    
    def _notify_data_ready(self, login: str, platform: str, data: Dict[str, Any]):
        """Notify all listeners that new data is available."""
        for callback in self._listeners:
            try:
                callback(login, platform, data)
            except Exception as exc:
                debug(f"[ANALYTICS] Listener error: {exc}")
    
    def _notify_profile_listeners(self, profile: UserProfile):
        """Notify all listeners that profile was updated."""
        for callback in self._profile_listeners:
            try:
                callback(profile)
            except Exception as exc:
                debug(f"[ANALYTICS] Profile listener error: {exc}")
    
    # ================================================================
    # VIEWER ANALYTICS (Real-time tracking)
    # ================================================================
    
    def update_viewer_count(self, login: str, platform: str, viewer_count: int):
        """Update viewer count analytics."""
        profile = self.get_profile(login)
        if not profile:
            # Create profile on first viewer count update
            profile_data = {
                "id": login,  # Use login as user_id for now
                "login": login,
                "platform": platform,
            }
            profile = self.create_user_profile(profile_data)
        
        # Update stats
        profile.peak_viewers_seen = max(profile.peak_viewers_seen, viewer_count)
        
        # Update average
        if profile.total_streams_watched > 0:
            profile.avg_viewers_across_streams = (
                (profile.avg_viewers_across_streams * profile.total_streams_watched + viewer_count)
                / (profile.total_streams_watched + 1)
            )
        else:
            profile.avg_viewers_across_streams = viewer_count
        
        profile.total_streams_watched += 1
        profile.last_active = int(time.time())
        
        # Persist
        self.db.store_profile(asdict(profile))
        
        # Store viewer count in history
        self.db.store_viewer_count(login, platform, viewer_count)
    
    def get_viewer_history(self, login: str, platform: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get viewer count history for a channel."""
        return self.db.get_viewer_history(login, platform, hours)
    
    # ================================================================
    # SESSION MANAGEMENT
    # ================================================================
    
    def start_viewing_session(self, user_id: str, metadata: Optional[Dict] = None) -> int:
        """Start a new viewing session."""
        return self.db.start_session(user_id, metadata)
    
    def end_viewing_session(self, session_id: int, duration_minutes: int, streams_watched: int = 0):
        """End a viewing session."""
        self.db.end_session(session_id, duration_minutes, streams_watched)
    
    # ================================================================
    # DATA ACCESS (For widgets and panels)
    # ================================================================
    
    def get_widget_data(self, login: str, widget_type: str = "sullygoose") -> Dict[str, Any]:
        """Get data formatted for a specific widget type.
        
        This is the unified API for widgets - they should only call this method.
        """
        # Get external data
        external = self.get_external_data(login)
        if not external:
            return {}
        
        # Format based on widget type
        if widget_type == "sullygoose":
            return self._format_sullygoose_data(login, external)
        elif widget_type == "viewer_graph":
            return self._format_viewer_graph_data(login)
        elif widget_type == "momentum":
            return self._format_momentum_data(login)
        
        return external
    
    def _format_sullygoose_data(self, login: str, external: Dict[str, Any]) -> Dict[str, Any]:
        """Format data for SullyGoose widget."""
        return {
            "login": login,
            "avg_viewers": external.get("avg_viewers", 0),
            "peak_viewers": external.get("peak_viewers", 0),
            "viewer_growth": external.get("viewer_growth", 0),
            "category_rank": external.get("category_rank", 0),
            "stream_frequency": external.get("stream_frequency", 0),
            "avg_stream_duration": external.get("avg_stream_duration", 0),
            "games_played_30d": external.get("games_played_30d", 0),
            "main_game_pct": external.get("main_game_pct"),
            "follower_count": external.get("follower_count", 0),
            "follower_growth_30d": external.get("follower_growth_30d"),
            "chat_activity": external.get("chat_activity", "Low"),
            "consistency_score": external.get("consistency_score", 0),
            "reliability_score": external.get("reliability_score", 0),
            "discovery_score": external.get("discovery_score", 0),
        }
    
    def _format_viewer_graph_data(self, login: str) -> List[Dict[str, Any]]:
        """Format data for viewer graph widget."""
        history = self.get_viewer_history(login, hours=24)
        return [
            {"viewer_count": h["viewer_count"], "timestamp": h["timestamp"]}
            for h in history
        ]
    
    def _format_momentum_data(self, login: str) -> Dict[str, Any]:
        """Format data for momentum gauge widget."""
        # Get recent viewer counts
        history = self.get_viewer_history(login, hours=1)
        if len(history) < 2:
            return {"percent": 0, "status": "Stable"}
        
        # Calculate momentum (percent change)
        recent = history[-1]["viewer_count"]
        older = history[0]["viewer_count"]
        
        if older == 0:
            percent = 0
        else:
            percent = ((recent - older) / older) * 100
        
        if percent > 10:
            status = "Rising"
        elif percent < -5:
            status = "Declining"
        else:
            status = "Stable"
        
        return {"percent": percent, "status": status}
    
    # ================================================================
    # CHAT & SOCIAL ANALYSIS
    # ================================================================
    
    def analyze_chat_message(self, login: str, message: str, author: str, timestamp: int):
        """Process a single chat message for analytics."""
        profile = self.get_profile(login)
        if not profile:
            return
        
        # Update message count
        profile.chat_messages_total += 1
        
        # Track emotes
        # TODO: Parse emotes from message and update profile.emotes_used
        
        # Track frequent chatters
        if author not in profile.frequent_chat_partners:
            profile.frequent_chat_partners.append(author)
        
        # Update chat activity
        hour = datetime.fromtimestamp(timestamp, tz=timezone.utc).hour
        if profile.chat_peak_activity_hour == 0:
            profile.chat_peak_activity_hour = hour
        
        # Persist periodically (not every message - too expensive)
        if profile.chat_messages_total % 100 == 0:
            self.db.store_profile(asdict(profile))
    
    def update_chat_analysis(self, login: str, analysis: Dict[str, Any]):
        """Update chat analysis data for a channel."""
        profile = self.get_profile(login)
        if not profile:
            return
        
        # Update chat analysis JSON
        profile.chat_analysis_json = {
            **(profile.chat_analysis_json or {}),
            **analysis,
            "last_updated": int(time.time()),
        }
        
        # Persist
        self.db.store_profile(asdict(profile))
    
    # ================================================================
    # RATE LIMIT MANAGEMENT
    # ================================================================
    
    def check_rate_limit(self, endpoint: str) -> bool:
        """Check if we can make an API call without hitting rate limits."""
        limit = self.db.get_rate_limit(endpoint)
        if not limit:
            return True
        
        if limit["calls_remaining"] <= 0:
            reset_time = limit["reset_timestamp"]
            if time.time() < reset_time:
                return False
        
        return True
    
    def record_api_call(self, endpoint: str, remaining: int, reset: int):
        """Record an API call for rate limit tracking."""
        self.db.update_rate_limit(endpoint, remaining, reset)
    
    # ================================================================
    # UTILITY
    # ================================================================
    
    def calculate_score(self, analysis: Dict[str, Any]) -> int:
        """Calculate stream quality score (0-100).
        
        Based on viewers, momentum, and external intelligence.
        """
        score = 0
        
        viewers = analysis.get("viewers", 0)
        if viewers >= 10000:
            score += 40
        elif viewers >= 1000:
            score += 25
        elif viewers >= 100:
            score += 10
        
        # Momentum boost
        momentum = analysis.get("status", "")
        if "Rising" in momentum or "Spike" in momentum:
            score += 20
        elif "Growing" in momentum:
            score += 10
        
        # External intelligence boost
        sullygoose = analysis.get("sullygoose", {}) or {}
        if sullygoose:
            growth = sullygoose.get("viewer_growth")
            if growth is None:
                growth = 0
            if growth > 50:
                score += 20
            elif growth > 10:
                score += 10
            
            rank = sullygoose.get("category_rank", 150) or 150
            if rank <= 10:
                score += 20
            elif rank <= 50:
                score += 10
        
        return min(score, 100)
    
    def update_stream(self, stream: Dict[str, Any], fetch_external: bool = False) -> Dict[str, Any]:
        """Update analytics for the current stream.
        
        This is the main entry point called by ViewerMonitor and other
        components. It updates profiles and returns the current analysis.
        
        Args:
            stream: Stream data dict
            fetch_external: If True, trigger external data fetch. 
                           Only use for the CURRENT channel to avoid lag.
        """
        if not stream:
            return {}
        
        platform = stream.get("platform", "twitch")
        channel_name = (
            stream.get("user_login")
            or stream.get("user_name")
            or stream.get("channel")
            or "Unknown"
        ).lower().strip()
        
        # Update viewer count analytics
        viewer_count = int(stream.get("viewer_count", 0))
        if channel_name and channel_name != "unknown":
            self.update_viewer_count(channel_name, platform, viewer_count)
        
        # Only fetch external data when explicitly requested (current channel only)
        external = {}
        if fetch_external:
            external = self.get_external_data(channel_name, platform) or {}
        
        # Build analysis
        analysis = {
            "channel": channel_name,
            "platform": platform,
            "viewers": viewer_count,
            "category": stream.get("game_name", stream.get("game", "Unknown")),
            "title": stream.get("title", ""),
            "sullygoose": external,
        }
        
        # Calculate score
        analysis["score"] = self.calculate_score(analysis)
        
        return analysis
    
    def close(self):
        """Clean shutdown."""
        self.db.close()
        debug("[ANALYTICS] Engine closed")
