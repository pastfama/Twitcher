"""Azure OpenAI client for Twitcher AI features.

Provides a unified interface to Azure GPT models for all AI-powered analytics.
"""

import os
import json
import threading
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from logger import debug

try:
    from openai import OpenAI
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    HAS_AZURE_AI = True
except ImportError:
    HAS_AZURE_AI = False
    debug("[AZURE_AI] openai or azure-identity not installed - AI features disabled")


class AzureAIClient:
    """Thread-safe Azure OpenAI client with caching and retry logic."""
    
    def __init__(self):
        if not HAS_AZURE_AI:
            raise RuntimeError("Azure AI dependencies not installed. Run: pip install openai azure-identity")
        
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "https://malovsky99-6011-resource.services.ai.azure.com/openai/v1")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini-1")
        self.token_provider = get_bearer_token_provider(DefaultAzureCredential(), "https://ai.azure.com/.default")
        self.client = OpenAI(
            base_url=self.endpoint,
            api_key=self.token_provider
        )
        self._lock = threading.RLock()
        self._cache = {}  # Simple in-memory cache
        self._cache_ttl = 300  # 5 minutes default
        
    def _get_cache_key(self, method: str, **kwargs) -> str:
        """Generate cache key from method name and arguments."""
        return f"{method}:{json.dumps(kwargs, sort_keys=True)}"
    
    def _get_cached(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached result if not expired."""
        if cache_key in self._cache:
            result, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return result
            else:
                del self._cache[cache_key]
        return None
    
    def _set_cache(self, cache_key: str, result: Dict[str, Any]):
        """Cache result with timestamp."""
        with self._lock:
            self._cache[cache_key] = (result, time.time())
    
    def call_ai(self, 
                system_prompt: str, 
                user_prompt: str,
                cache_key: Optional[str] = None,
                cache_ttl: int = 300,
                temperature: float = 0.7,
                max_tokens: int = 1000) -> Dict[str, Any]:
        """Make an AI call with caching and error handling.
        
        Args:
            system_prompt: System instruction for the AI
            user_prompt: User message/data to analyze
            cache_key: Optional cache key (auto-generated if not provided)
            cache_ttl: Cache time-to-live in seconds
            temperature: AI creativity (0-1)
            max_tokens: Max response tokens
            
        Returns:
            Dict with AI response and metadata
        """
        # Check cache
        if cache_key is None:
            cache_key = self._get_cache_key("call", system=system_prompt[:50], user=user_prompt[:50])
        
        cached = self._get_cached(cache_key)
        if cached:
            debug(f"[AZURE_AI] Cache hit: {cache_key[:50]}")
            return cached
        
        # Make AI call
        try:
            with self._lock:
                response = self.client.responses.create(
                    model=self.deployment,
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            
            # Parse response
            result_text = response.output[0] if response.output else ""
            
            result = {
                "success": True,
                "content": result_text,
                "model": self.deployment,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "cached": False
            }
            
            # Cache result
            self._cache[cache_key] = (result, time.time())
            
            debug(f"[AZURE_AI] Call successful: {cache_key[:50]}")
            return result
            
        except Exception as e:
            debug(f"[AZURE_AI] Call failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "content": None,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def call_ai_json(self,
                     system_prompt: str,
                     user_prompt: str,
                     cache_key: Optional[str] = None,
                     cache_ttl: int = 300) -> Dict[str, Any]:
        """Make an AI call expecting JSON response.
        
        Automatically parses JSON from AI response.
        """
        # Add JSON instruction to system prompt
        system_prompt += "\n\nIMPORTANT: Respond ONLY with valid JSON, no markdown, no extra text."
        
        result = self.call_ai(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            cache_key=cache_key,
            cache_ttl=cache_ttl,
            temperature=0.3,  # Lower temperature for structured data
            max_tokens=2000
        )
        
        if not result["success"] or not result["content"]:
            return {"success": False, "error": result.get("error", "Unknown error")}
        
        # Try to parse JSON
        try:
            # Clean up response (remove markdown code blocks if present)
            content = result["content"]
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content.strip())
            return {
                "success": True,
                "data": data,
                "model": result["model"],
                "timestamp": result["timestamp"],
                "cached": result.get("cached", False)
            }
        except json.JSONDecodeError as e:
            debug(f"[AZURE_AI] JSON parse error: {e}, content: {result['content'][:200]}")
            return {
                "success": False,
                "error": f"JSON parse error: {e}",
                "raw_content": result["content"]
            }
    
    def clear_cache(self):
        """Clear the AI cache."""
        with self._lock:
            self._cache.clear()
            debug("[AZURE_AI] Cache cleared")


# Global singleton
_ai_client = None

def get_ai_client() -> Optional[AzureAIClient]:
    """Get the global AI client instance."""
    global _ai_client
    if _ai_client is None and HAS_AZURE_AI:
        try:
            _ai_client = AzureAIClient()
            debug("[AZURE_AI] Client initialized")
        except Exception as e:
            debug(f"[AZURE_AI] Failed to initialize: {e}")
    return _ai_client