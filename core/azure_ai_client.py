"""Azure OpenAI client for Twitcher AI features.

Uses direct HTTP requests instead of the OpenAI SDK to avoid
aggressive retry behavior that causes 429 rate limit floods.

Configuration via environment variables:
  AZURE_OPENAI_ENDPOINT     - Azure OpenAI endpoint
  AZURE_OPENAI_DEPLOYMENT   - Model deployment name (e.g., gpt-5-terra)
  AZURE_OPENAI_API_KEY      - API key
  AZURE_OPENAI_API_VERSION  - API version (default: 2025-01-01-preview)
"""

import os
import json
import threading
import time
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from logger import debug


class AzureAIClient:
    """Thread-safe Azure OpenAI client using direct HTTP requests."""
    
    def __init__(self):
        self.endpoint = os.getenv(
            "AZURE_OPENAI_ENDPOINT",
            "https://aoai-twitcher-80fcb.openai.azure.com/"
        ).rstrip("/")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-vision")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        
        self._lock = threading.RLock()
        self._cache = {}
        self._cache_ttl = 300
        self._last_call_time = 0
        self._min_interval = 2.0  # Minimum 2 seconds between calls
        
        self._stats = {
            "total_calls": 0, "cache_hits": 0, "api_calls": 0,
            "errors": 0, "total_tokens": 0, "total_latency_ms": 0,
            "last_call_time": None,
        }
        
        debug(f"[AZURE_AI] Initialized: deployment={self.deployment}, endpoint={self.endpoint[:40]}...")

    def _get_cache_key(self, method: str, **kwargs) -> str:
        return f"{method}:{json.dumps(kwargs, sort_keys=True)}"
    
    def _get_cached(self, cache_key: str) -> Optional[Dict[str, Any]]:
        if cache_key in self._cache:
            result, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return result
            else:
                del self._cache[cache_key]
        return None
    
    def get_agent_stats(self) -> Dict[str, Any]:
        with self._lock:
            stats = dict(self._stats)
            stats["avg_latency_ms"] = int(stats["total_latency_ms"] / max(stats["api_calls"], 1))
            return stats

    def call_ai(self, 
                system_prompt: str, 
                user_prompt: str,
                cache_key: Optional[str] = None,
                cache_ttl: int = 300,
                temperature: float = 0.7,
                max_tokens: int = 1000) -> Dict[str, Any]:
        """Make an AI call using direct HTTP requests."""
        if cache_key is None:
            cache_key = self._get_cache_key("call", system=system_prompt[:50], user=user_prompt[:50])
        
        with self._lock:
            self._stats["total_calls"] += 1

        cached = self._get_cached(cache_key)
        if cached:
            with self._lock:
                self._stats["cache_hits"] += 1
            return cached
        
        # Rate limit: wait minimum interval between calls
        elapsed = time.time() - self._last_call_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        
        _start = time.monotonic()
        try:
            url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "api-key": self.api_key,
            }
            
            # Build request body
            body = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
            }
            
            # GPT-5 uses max_completion_tokens, others use max_tokens
            if "gpt-5" in self.deployment:
                body["max_completion_tokens"] = max_tokens
            else:
                body["temperature"] = temperature
                body["max_tokens"] = max_tokens
            
            params = {"api-version": self.api_version}
            
            debug(f"[AZURE_AI] HTTP POST: model={self.deployment}")
            response = requests.post(url, json=body, headers=headers, params=params, timeout=30)
            self._last_call_time = time.time()
            
            if response.status_code == 429:
                # Rate limited — wait and retry once
                retry_after = int(response.headers.get("Retry-After", 5))
                debug(f"[AZURE_AI] Rate limited, waiting {retry_after}s")
                time.sleep(retry_after)
                response = requests.post(url, json=body, headers=headers, params=params, timeout=30)
                self._last_call_time = time.time()
            
            response.raise_for_status()
            
            data = response.json()
            result_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            _elapsed = int((time.monotonic() - _start) * 1000)
            _tokens = data.get("usage", {}).get("completion_tokens", 0) or len(result_text) // 4
            
            with self._lock:
                self._stats["api_calls"] += 1
                self._stats["total_latency_ms"] += _elapsed
                self._stats["total_tokens"] += _tokens
                self._stats["last_call_time"] = time.time()
            
            result = {
                "success": True, "content": result_text,
                "model": self.deployment,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "cached": False, "latency_ms": _elapsed, "tokens_est": _tokens,
            }
            
            self._cache[cache_key] = (result, time.time())
            debug(f"[AZURE_AI] Success ({_elapsed}ms): {result_text[:80]}")
            return result
            
        except Exception as e:
            _elapsed = int((time.monotonic() - _start) * 1000)
            with self._lock:
                self._stats["errors"] += 1
                self._stats["total_latency_ms"] += _elapsed
            debug(f"[AZURE_AI] Failed: {e}")
            return {"success": False, "error": str(e), "content": None,
                    "timestamp": datetime.now(timezone.utc).isoformat()}
    
    def call_ai_json(self, system_prompt: str, user_prompt: str,
                     cache_key: Optional[str] = None, cache_ttl: int = 300) -> Dict[str, Any]:
        system_prompt += "\n\nIMPORTANT: Respond ONLY with valid JSON, no markdown, no extra text."
        result = self.call_ai(system_prompt=system_prompt, user_prompt=user_prompt,
                              cache_key=cache_key, cache_ttl=cache_ttl,
                              temperature=0.3, max_tokens=2000)
        if not result["success"] or not result["content"]:
            return {"success": False, "error": result.get("error", "Unknown error")}
        try:
            content = result["content"]
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            data = json.loads(content.strip())
            return {"success": True, "data": data, "model": result["model"],
                    "timestamp": result["timestamp"], "cached": result.get("cached", False)}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"JSON parse error: {e}", "raw_content": result["content"]}
    
    def clear_cache(self):
        with self._lock:
            self._cache.clear()


_ai_client = None
_ai_client_initialized = False

def get_ai_client() -> Optional[AzureAIClient]:
    global _ai_client, _ai_client_initialized
    if _ai_client is None and not _ai_client_initialized:
        _ai_client_initialized = True
        try:
            _ai_client = AzureAIClient()
            debug("[AZURE_AI] Client initialized")
        except Exception as e:
            debug(f"[AZURE_AI] Failed to initialize: {e}")
    return _ai_client