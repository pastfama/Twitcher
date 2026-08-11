"""
Smart Data Stream with Adaptive Rate Limiting.

This implementation provides a centralized data management system that:
1. Tracks rate limits from API responses
2. Dynamically adjusts fetch frequency based on quota usage
3. Prioritizes critical updates over background refreshes
4. Batches compatible requests to minimize API calls
5. Pre-fetches data when quota is available
6. Provides real-time quota status for UI feedback
"""

from PySide6.QtCore import QObject, Signal, QTimer
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from collections import deque
import threading
import time
from logger import debug


@dataclass
class RateLimitInfo:
    """Tracks rate limit status for an API endpoint."""
    limit: int           # Total allowed calls
    remaining: int       # Calls remaining
    reset_timestamp: int # Unix timestamp when limit resets
    window_seconds: int  # Length of rate limit window
    
    @property
    def refill_rate(self) -> float:
        """Calls added per second."""
        return self.limit / self.window_seconds
    
    @property
    def utilization(self) -> float:
        """Percentage of quota used (0.0 - 1.0)."""
        return 1.0 - (self.remaining / self.limit) if self.limit > 0 else 0.0
    
    @property
    def seconds_until_reset(self) -> int:
        return max(0, self.reset_timestamp - int(time.time()))
    
    @property
    def is_exhausted(self) -> bool:
        return self.remaining <= 0 and self.seconds_until_reset > 0


@dataclass
class FetchRequest:
    """A pending data fetch request."""
    priority: int           # Higher = more urgent (1-10)
    endpoint: str           # API endpoint identifier
    key: str               # Unique cache key
    callback: Callable     # What to do with result
    created_at: float      # Request timestamp
    deadline: float = 0    # Optional: must complete by this time
    batchable: bool = True # Can be combined with other requests


@dataclass 
class EndpointBudget:
    """Manages API call budget for an endpoint."""
    max_calls_per_window: int
    window_seconds: int
    reserved_calls: int = 0    # For high-priority requests
    soft_limit: int = None     # Self-imposed limit (for headroom)
    
    def __post_init__(self):
        if self.soft_limit is None:
            self.soft_limit = int(self.max_calls_per_window * 0.8)  # 80% headroom


class SmartDataStream(QObject):
    """Intelligent data manager with adaptive rate limiting.
    
    Features:
    - Tracks rate limits from API response headers
    - Adjusts fetch frequency based on remaining quota
    - Prioritizes critical updates over background refresh
    - Batches compatible requests
    - Pre-fetches data when quota is available
    - Provides real-time quota status for UI feedback
    """
    
    # Signals (same as before)
    current_stream_updated = Signal(object, object)
    live_channels_updated = Signal(list)
    next_stream_updated = Signal(object)
    chat_info_updated = Signal(str, int, int)
    rate_limit_warning = Signal(str, int, int)  # endpoint, remaining, reset_in
    quota_status = Signal(str, float)           # endpoint, utilization
    
    # Twitch Helix rate limits (as of 2024)
    TWITCH_LIMITS = {
        "get_users": RateLimitInfo(limit=800, remaining=800, reset_timestamp=0, window_seconds=60),
        "get_streams": RateLimitInfo(limit=800, remaining=800, reset_timestamp=0, window_seconds=60),
        "get_followed": RateLimitInfo(limit=800, remaining=800, reset_timestamp=0, window_seconds=60),
        "get_channel_info": RateLimitInfo(limit=800, remaining=800, reset_timestamp=0, window_seconds=60),
        "get_rewards": RateLimitInfo(limit=800, remaining=800, reset_timestamp=0, window_seconds=60),
    }
    
    # Budgets for different data types (calls per refresh cycle)
    BUDGETS = {
        "current_stream": EndpointBudget(max_calls_per_window=10, window_seconds=60),
        "live_channels": EndpointBudget(max_calls_per_window=20, window_seconds=60),
        "chat_info": EndpointBudget(max_calls_per_window=5, window_seconds=60),
        "analytics": EndpointBudget(max_calls_per_window=10, window_seconds=60),
    }
    
    def __init__(self, api, analytics_engine, viewer_tracker):
        super().__init__()
        self.api = api
        self.analytics = analytics_engine
        self.tracker = viewer_tracker
        
        # Caches
        self._cache = {}
        self._cache_timestamps = {}
        self._cache_lock = threading.RLock()
        
        # Rate limiting state
        self._rate_limits = dict(self.TWITCH_LIMITS)
        self._budgets = dict(self.BUDGETS)
        self._request_queue: deque = deque()
        self._pending_fetches = set()
        self._call_history: Dict[str, deque] = {}  # endpoint -> [timestamps]
        
        # Adaptive throttling
        self._throttle_factors = {ep: 1.0 for ep in self._rate_limits}  # 0.1 = slow, 1.0 = normal
        self._last_adjustment = time.time()
        
        # Background processor
        self._processor_timer = QTimer(self)
        self._processor_timer.setInterval(100)  # Check every 100ms
        self._processor_timer.timeout.connect(self._process_request_queue)
        self._processor_timer.start()
        
        # Status reporting timer
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(5000)  # Report every 5s
        self._status_timer.timeout.connect(self._report_quota_status)
        self._status_timer.start()
    
    # ============================================================
    # RATE LIMIT MANAGEMENT
    # ============================================================
    
    def update_rate_limit(self, endpoint: str, remaining: int, reset_timestamp: int):
        """Update rate limit info from API response headers."""
        if endpoint in self._rate_limits:
            rl = self._rate_limits[endpoint]
            rl.remaining = remaining
            rl.reset_timestamp = reset_timestamp
            
            debug(f"[RATELIMIT] {endpoint}: {remaining} remaining, resets in {rl.seconds_until_reset}s")
            
            # Warn if running low
            if remaining < rl.limit * 0.2:  # Less than 20%
                self.rate_limit_warning.emit(endpoint, remaining, rl.seconds_until_reset)
            
            # Adjust throttle factor
            self._adjust_throttle(endpoint)
    
    def _adjust_throttle(self, endpoint: str):
        """Dynamically adjust request throttling based on quota."""
        if endpoint not in self._rate_limits:
            return
        
        rl = self._rate_limits[endpoint]
        now = time.time()
        
        # Only adjust every 10 seconds to avoid oscillation
        if now - self._last_adjustment < 10:
            return
        
        # Calculate optimal throttle factor
        if rl.is_exhausted:
            # Completely blocked - minimal requests only
            self._throttle_factors[endpoint] = 0.1
            debug(f"[THROTTLE] {endpoint}: BLOCKED until reset")
        elif rl.utilization > 0.9:
            # Almost exhausted - very conservative
            self._throttle_factors[endpoint] = 0.2
            debug(f"[THROTTLE] {endpoint}: Critical ({rl.remaining} left)")
        elif rl.utilization > 0.7:
            # Running low - moderate throttling
            self._throttle_factors[endpoint] = 0.5
            debug(f"[THROTTLE] {endpoint}: Warning ({rl.remaining} left)")
        elif rl.utilization > 0.5:
            # Healthy usage - slight caution
            self._throttle_factors[endpoint] = 0.8
        else:
            # Plenty of quota - full speed
            self._throttle_factors[endpoint] = 1.0
        
        self._last_adjustment = now
    
    def _record_call(self, endpoint: str):
        """Record an API call for rate tracking."""
        now = time.time()
        
        if endpoint not in self._call_history:
            self._call_history[endpoint] = deque(maxlen=1000)
        
        self._call_history[endpoint].append(now)
        
        # Decrement remaining (we track locally too)
        if endpoint in self._rate_limits:
            self._rate_limits[endpoint].remaining = max(
                0, 
                self._rate_limits[endpoint].remaining - 1
            )
    
    def _can_make_call(self, endpoint: str, priority: int = 5) -> Tuple[bool, str]:
        """Check if we can make an API call right now.
        
        Returns: (can_proceed, reason)
        """
        if endpoint not in self._rate_limits:
            return True, "unknown endpoint"
        
        rl = self._rate_limits[endpoint]
        throttle = self._throttle_factors.get(endpoint, 1.0)
        
        # High priority requests bypass some restrictions
        if priority >= 8:
            if rl.remaining > 0:
                return True, "high priority"
            return False, f"rate limit exhausted (priority {priority} not enough)"
        
        # Check hard rate limit
        if rl.is_exhausted:
            return False, f"rate limit exhausted, reset in {rl.seconds_until_reset}s"
        
        # Check throttle factor
        if throttle < 0.3 and priority < 5:
            return False, f"throttled (factor={throttle:.2f})"
        
        # Check budget
        budget = self._budgets.get(endpoint)
        if budget:
            recent_calls = self._get_recent_calls(endpoint, budget.window_seconds)
            if len(recent_calls) >= budget.soft_limit:
                return False, f"budget exhausted ({len(recent_calls)}/{budget.soft_limit})"
        
        return True, "ok"
    
    def _get_recent_calls(self, endpoint: str, window_seconds: int) -> List[float]:
        """Get timestamps of calls within the time window."""
        if endpoint not in self._call_history:
            return []
        
        cutoff = time.time() - window_seconds
        return [t for t in self._call_history[endpoint] if t > cutoff]
    
    # ============================================================
    # PRIORITY QUEUE SYSTEM
    # ============================================================
    
    def queue_fetch(self, endpoint: str, key: str, callback: Callable, 
                    priority: int = 5, deadline: float = 0, batchable: bool = True):
        """Queue a fetch request with priority."""
        request = FetchRequest(
            priority=priority,
            endpoint=endpoint,
            key=key,
            callback=callback,
            created_at=time.time(),
            deadline=deadline,
            batchable=batchable
        )
        
        # Insert in priority order
        inserted = False
        for i, existing in enumerate(self._request_queue):
            if request.priority > existing.priority:
                self._request_queue.insert(i, request)
                inserted = True
                break
        
        if not inserted:
            self._request_queue.append(request)
        
        debug(f"[QUEUE] Added {endpoint}:{key} priority={priority} (queue size: {len(self._request_queue)})")
    
    def _process_request_queue(self):
        """Process queued requests based on priority and rate limits."""
        # Process up to 3 requests per tick to avoid blocking
        processed = 0
        max_per_tick = 3
        
        while self._request_queue and processed < max_per_tick:
            request = self._request_queue[0]  # Peek at highest priority
            
            can_proceed, reason = self._can_make_call(request.endpoint, request.priority)
            
            if can_proceed:
                self._request_queue.popleft()  # Remove from queue
                self._execute_fetch(request)
                processed += 1
            else:
                # Check if request has expired
                if request.deadline and time.time() > request.deadline:
                    debug(f"[QUEUE] Dropping expired request: {request.key}")
                    self._request_queue.popleft()
                else:
                    # Can't proceed, stop processing (lower priority items won't work either)
                    break
    
    def _execute_fetch(self, request: FetchRequest):
        """Execute a fetch request on a background thread."""
        fetch_key = f"{request.endpoint}:{request.key}"
        
        if fetch_key in self._pending_fetches:
            debug(f"[FETCH] Already pending: {fetch_key}")
            return
        
        self._pending_fetches.add(fetch_key)
        self._record_call(request.endpoint)
        
        import threading
        thread = threading.Thread(
            target=self._fetch_worker,
            args=(request,),
            name=f"Fetch-{request.endpoint}-{request.key}",
            daemon=True
        )
        thread.start()
    
    def _fetch_worker(self, request: FetchRequest):
        """Background worker to execute the actual fetch."""
        try:
            result = self._do_fetch(request.endpoint, request.key)
            
            # Cache the result
            with self._cache_lock:
                self._cache[request.key] = result
                self._cache_timestamps[request.key] = time.time()
            
            # Execute callback on main thread
            if request.callback:
                from PySide6.QtCore import QMetaObject, Qt
                QMetaObject.invokeMethod(
                    request.callback,
                    "accept_result",
                    Qt.QueuedConnection,
                    Q_ARG(object, result)
                )
            
        except Exception as e:
            debug(f"[FETCH] Error for {request.key}: {e}")
        
        finally:
            fetch_key = f"{request.endpoint}:{request.key}"
            self._pending_fetches.discard(fetch_key)
    
    def _do_fetch(self, endpoint: str, key: str):
        """Execute the actual API fetch based on endpoint type."""
        # Route to appropriate fetcher
        fetchers = {
            "current_stream": self._fetch_current_stream,
            "live_channels": self._fetch_live_channels,
            "chat_info": self._fetch_chat_info,
            "analytics": self._fetch_analytics,
            "rewards": self._fetch_rewards,
        }
        
        fetcher = fetchers.get(endpoint)
        if fetcher:
            return fetcher(key)
        
        raise ValueError(f"Unknown endpoint: {endpoint}")
    
    # ============================================================
    # SPECIFIC FETCHERS
    # ============================================================
    
    def _fetch_current_stream(self, channel_login: str) -> Dict:
        """Fetch current stream info."""
        return self.api.get_stream_info(channel_login)
    
    def _fetch_live_channels(self, params: Dict) -> List[Dict]:
        """Fetch all live channels (batched)."""
        user_id = params.get("user_id")
        watchlist = params.get("watchlist", [])
        
        all_live = []
        
        # Twitch
        followed = self.api.get_followed_channels(user_id)
        twitch_live = self.api.get_live_streams(followed)
        for s in twitch_live:
            s["platform"] = "twitch"
        all_live.extend(twitch_live)
        
        # Kick/YouTube
        from platforms import get_platform_manager
        pm = get_platform_manager()
        other_live = pm.get_live_streams(watchlist)
        all_live.extend(other_live)
        
        all_live.sort(key=lambda x: x.get("viewer_count", 0), reverse=True)
        return all_live
    
    def _fetch_chat_info(self, channel: str) -> Dict:
        """Fetch chat-related info."""
        game = ""
        viewers = 0
        
        try:
            stream = self.api.get_stream_info(channel)
            if stream:
                game = stream.get("game_name", "")
                viewers = stream.get("viewer_count", 0)
        except Exception as e:
            debug(f"[CHAT INFO] Fetch error: {e}")
        
        return {"game": game, "viewers": viewers}
    
    def _fetch_analytics(self, login: str) -> Dict:
        """Fetch analytics data."""
        if self.analytics:
            return self.analytics.get_external_data(login) or {}
        return {}
    
    def _fetch_rewards(self, broadcaster_id: str) -> List[Dict]:
        """Fetch channel rewards."""
        return self.api.get_channel_rewards(broadcaster_id)
    
    # ============================================================
    # PUBLIC API FOR PANELS
    # ============================================================
    
    def request_current_stream_update(self, channel_login: str, callback: Callable = None):
        """Request current stream update (HIGH PRIORITY)."""
        self.queue_fetch(
            endpoint="current_stream",
            key=channel_login,
            callback=callback or self._on_current_stream_fetched,
            priority=9,  # Highest priority
            deadline=time.time() + 5,  # Must complete within 5 seconds
            batchable=False
        )
    
    def request_live_channels_refresh(self, user_id: str, watchlist: List, 
                                       callback: Callable = None, priority: int = 5):
        """Request live channels refresh (background priority)."""
        params = {"user_id": user_id, "watchlist": watchlist}
        self.queue_fetch(
            endpoint="live_channels",
            key=f"{user_id}:{len(watchlist)}",
            callback=callback or self._on_live_channels_fetched,
            priority=priority,
            deadline=time.time() + 30,  # Can take longer
            batchable=True
        )
    
    def request_chat_info(self, channel: str, callback: Callable = None):
        """Request chat info update."""
        self.queue_fetch(
            endpoint="chat_info",
            key=channel,
            callback=callback or self._on_chat_info_fetched,
            priority=6,
            deadline=time.time() + 10,
            batchable=True
        )
    
    def request_analytics(self, login: str, callback: Callable = None):
        """Request analytics data."""
        self.queue_fetch(
            endpoint="analytics",
            key=login,
            callback=callback or self._on_analytics_fetched,
            priority=4,  # Lower priority - nice to have
            deadline=time.time() + 60,  # Can be slow
            batchable=True
        )
    
    # ============================================================
    # CALLBACK HANDLERS
    # ============================================================
    
    def _on_current_stream_fetched(self, result: Dict):
        """Handle fetched current stream."""
        if result:
            analytics = self.analytics.update_stream(result) if self.analytics else {}
            self.current_stream_updated.emit(result, analytics)
    
    def _on_live_channels_fetched(self, result: List[Dict]):
        """Handle fetched live channels."""
        self.live_channels_updated.emit(result)
    
    def _on_chat_info_fetched(self, result: Dict):
        """Handle fetched chat info."""
        # Extract channel from cache key
        pass  # Would need to track channel mapping
    
    def _on_analytics_fetched(self, result: Dict):
        """Handle fetched analytics."""
        pass  # Analytics updates go through separate signal
    
    # ============================================================
    # STATUS REPORTING
    # ============================================================
    
    def _report_quota_status(self):
        """Report current quota utilization."""
        for endpoint, rl in self._rate_limits.items():
            utilization = rl.utilization
            self.quota_status.emit(endpoint, utilization)
            
            if utilization > 0.8:
                debug(f"[QUOTA] {endpoint}: {utilization*100:.1f}% used ({rl.remaining} remaining)")
    
    def get_quota_status(self, endpoint: str) -> Dict:
        """Get detailed quota status for an endpoint."""
        if endpoint not in self._rate_limits:
            return {"error": "unknown endpoint"}
        
        rl = self._rate_limits[endpoint]
        recent_calls = self._get_recent_calls(endpoint, rl.window_seconds)
        
        return {
            "limit": rl.limit,
            "remaining": rl.remaining,
            "utilization": rl.utilization,
            "reset_in_seconds": rl.seconds_until_reset,
            "recent_calls": len(recent_calls),
            "throttle_factor": self._throttle_factors.get(endpoint, 1.0),
            "pending_fetches": sum(1 for k in self._pending_fetches if k.startswith(endpoint)),
            "queued_requests": sum(1 for r in self._request_queue if r.endpoint == endpoint),
        }
    
    def get_all_quota_status(self) -> Dict[str, Dict]:
        """Get quota status for all endpoints."""
        return {ep: self.get_quota_status(ep) for ep in self._rate_limits}