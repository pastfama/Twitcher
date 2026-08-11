"""Semantic Kernel engine for Twitcher AI analytics.

Uses Microsoft Semantic Kernel to orchestrate AI calls with
function calling, structured output, and prompt templates.
Falls back gracefully if semantic-kernel is not installed.
"""

import os
import json
import asyncio
import threading
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor
from logger import debug

# ── Semantic Kernel imports (graceful fallback) ─────────────────────────

try:
    import semantic_kernel as sk
    from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
    from semantic_kernel.functions import kernel_function
    from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
    HAS_SK = False  # Disabled — using direct AzureOpenAI client instead
    debug("[SK_ENGINE] Semantic Kernel available but disabled — using fallback")
except ImportError:
    HAS_SK = False
    debug("[SK_ENGINE] Semantic Kernel not installed — using fallback")

# ── Thread-safe async bridge ────────────────────────────────────────────

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="sk_ai")


def _run_async(coro):
    """Run an async coroutine from a sync context (GUI thread safe)."""
    future = _executor.submit(asyncio.run, coro)
    try:
        return future.result(timeout=15)
    except Exception as e:
        debug(f"[SK_ENGINE] Async call timed out or failed: {e}")
        return ""


# ── SK Engine singleton ─────────────────────────────────────────────────

_sk_kernel: Optional[Any] = None


def get_sk_kernel():
    """Get or create the Semantic Kernel instance."""
    global _sk_kernel
    if _sk_kernel is not None:
        return _sk_kernel

    if not HAS_SK:
        debug("[SK_ENGINE] Semantic Kernel not available")
        return None

    try:
        kernel = sk.Kernel()

        # Azure OpenAI service
        endpoint = os.getenv(
            "AZURE_OPENAI_ENDPOINT",
            "https://aoai-twitcher-80fcb.openai.azure.com/"
        )
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-vision")

        # Use Azure AD token auth (no API key needed)
        try:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(), "https://ai.azure.com/.default"
            )
            service = AzureChatCompletion(
                service_id="azure_openai",
                deployment_name=deployment,
                endpoint=endpoint,
                api_key=token_provider,
            )
        except Exception:
            # Fallback: try with env API key
            api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
            service = AzureChatCompletion(
                service_id="azure_openai",
                deployment_name=deployment,
                endpoint=endpoint,
                api_key=api_key,
            )

        kernel.add_service(service)

        _sk_kernel = kernel
        debug(f"[SK_ENGINE] Kernel initialized with deployment={deployment}")
        return kernel

    except Exception as e:
        debug(f"[SK_ENGINE] Failed to initialize: {e}")
        return None


# ── AI Insight Generator ────────────────────────────────────────────────

_INSIGHT_SYSTEM_PROMPT = """You are a sharp, concise streaming analytics commentator.
Given a set of stream metrics, generate a brief insightful observation (1-2 sentences max).
Be specific with numbers. Use a sportscaster tone — energetic but data-driven.

Examples:
- "Chat is on fire! 45 messages/min with 80% emote usage — pure hype energy 🔥"
- "Viewer velocity turned negative: losing ~12 viewers/min. Consider switching games."
- "Title quality score at 35 — adding an emoji or excitement word could boost discoverability by 20%"

Respond ONLY with the insight text, no quotes, no JSON."""

_COMPARISON_SYSTEM_PROMPT = """You are a streaming advisor AI. Compare two streams and give a clear recommendation.
Be direct and data-driven. 2-3 sentences max.

Respond ONLY with the recommendation text, no JSON."""

_PREDICTION_SYSTEM_PROMPT = """You are a streaming trend forecaster. Given current metrics and viewer history,
predict where this stream will be in 30 and 60 minutes.
Be specific with numbers but acknowledge uncertainty. 2-3 sentences max.

Respond ONLY with the prediction text, no JSON."""


def generate_insight(metrics: Dict[str, Any]) -> str:
    """Generate a brief AI insight from current metrics.

    Uses Semantic Kernel if available, otherwise falls back to
    direct Azure AI call.  Never blocks the caller for more than 15s.
    """
    summary = _format_metrics_summary(metrics)
    debug(f"[SK_ENGINE] generate_insight called, HAS_SK={HAS_SK}, summary_len={len(summary)}")

    # Try SK first
    kernel = get_sk_kernel()
    if kernel and HAS_SK:
        try:
            result = _run_async(_sk_generate_insight(kernel, summary))
            if result:
                debug(f"[SK_ENGINE] SK insight returned: {result[:80]}")
                return result
            debug("[SK_ENGINE] SK insight returned empty, trying fallback")
        except Exception as e:
            debug(f"[SK_ENGINE] SK insight failed: {e}")

    # Fallback: use the existing AI client (also with timeout)
    debug("[SK_ENGINE] Using fallback AI call")
    return _fallback_ai_call(_INSIGHT_SYSTEM_PROMPT, summary)


def generate_comparison(current: Dict[str, Any], next_stream: Dict[str, Any]) -> str:
    """Generate an AI comparison between current and next stream."""
    kernel = get_sk_kernel()

    prompt = (
        f"CURRENT STREAM:\n{_format_metrics_summary(current)}\n\n"
        f"NEXT STREAM:\n{_format_metrics_summary(next_stream)}"
    )

    if kernel and HAS_SK:
        try:
            return _run_async(_sk_generate_text(kernel, _COMPARISON_SYSTEM_PROMPT, prompt))
        except Exception as e:
            debug(f"[SK_ENGINE] Comparison failed: {e}")

    return _fallback_ai_call(_COMPARISON_SYSTEM_PROMPT, prompt)


def generate_prediction(metrics: Dict[str, Any], history_summary: str = "") -> str:
    """Generate a 30/60 min prediction for the current stream."""
    kernel = get_sk_kernel()

    prompt = f"CURRENT METRICS:\n{_format_metrics_summary(metrics)}"
    if history_summary:
        prompt += f"\n\nVIEWER HISTORY:\n{history_summary}"

    if kernel and HAS_SK:
        try:
            return _run_async(_sk_generate_text(kernel, _PREDICTION_SYSTEM_PROMPT, prompt))
        except Exception as e:
            debug(f"[SK_ENGINE] Prediction failed: {e}")

    return _fallback_ai_call(_PREDICTION_SYSTEM_PROMPT, prompt)


# ── SK async helpers ────────────────────────────────────────────────────

async def _sk_generate_insight(kernel, summary: str) -> str:
    """Use SK to generate an insight with function calling."""
    settings = OpenAIChatPromptExecutionSettings(
        service_id="azure_openai",
        max_tokens=150,
        temperature=0.7,
    )
    from semantic_kernel.connectors.ai.chat_completion_client import ChatHistory
    history = ChatHistory()
    history.add_system_message(_INSIGHT_SYSTEM_PROMPT)
    history.add_user_message(summary)

    chat = kernel.get_service("azure_openai")
    result = await chat.get_chat_message_content(history, settings)
    if result:
        # Handle both string and complex content objects
        if hasattr(result, "content"):
            return str(result.content) if result.content else ""
        return str(result)
    return ""


async def _sk_generate_text(kernel, system_prompt: str, user_prompt: str) -> str:
    """Generic SK text generation."""
    settings = OpenAIChatPromptExecutionSettings(
        service_id="azure_openai",
        max_tokens=200,
        temperature=0.7,
    )
    from semantic_kernel.connectors.ai.chat_completion_client import ChatHistory
    history = ChatHistory()
    history.add_system_message(system_prompt)
    history.add_user_message(user_prompt)

    chat = kernel.get_service("azure_openai")
    result = await chat.get_chat_message_content(history, settings)
    if result:
        if hasattr(result, "content"):
            return str(result.content) if result.content else ""
        return str(result)
    return ""


# ── Fallback (direct Azure AI) ──────────────────────────────────────────

def _fallback_ai_call(system_prompt: str, user_prompt: str) -> str:
    """Fallback using the existing AzureAIClient."""
    try:
        from core.azure_ai_client import get_ai_client
        client = get_ai_client()
        if not client:
            return ""
        result = client.call_ai(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            cache_ttl=120,
            temperature=0.7,
            max_tokens=150,
        )
        if result.get("success"):
            content = result.get("content", "")
            # Handle response object types
            if hasattr(content, 'text'):
                return content.text
            return str(content)
        return ""
    except Exception as e:
        debug(f"[SK_ENGINE] Fallback AI call failed: {e}")
        return ""


# ── Helpers ─────────────────────────────────────────────────────────────

def _format_metrics_summary(m: Dict[str, Any]) -> str:
    """Format metrics dict into a readable summary for AI prompts."""
    lines = []
    if "viewers" in m:
        lines.append(f"Viewers: {m['viewers']:,}")
    if "session_peak" in m:
        lines.append(f"Session Peak: {m['session_peak']:,}")
    if "velocity" in m:
        lines.append(f"Viewer Velocity: {m['velocity']:+.1f}/min")
    if "chat_rate" in m:
        lines.append(f"Chat Rate: {m['chat_rate']:.1f} msg/min")
    if "sentiment" in m:
        lines.append(f"Chat Sentiment: {m['sentiment']:+.0f} (-100 to +100)")
    if "emote_ratio" in m:
        lines.append(f"Emote Usage: {m['emote_ratio']:.0f}%")
    if "loyalty" in m:
        lines.append(f"Audience Loyalty: {m['loyalty']}%")
    if "bounce_rate" in m:
        lines.append(f"Bounce Rate: {m['bounce_rate']}%")
    if "title_score" in m:
        lines.append(f"Title Quality: {m['title_score']}/100")
    if "stream_health" in m:
        lines.append(f"Stream Health: {m['stream_health']}/100")
    if "overall_rank" in m:
        lines.append(f"Overall Grade: {m['overall_rank']}")
    if "monetization" in m:
        lines.append(f"Monetization Potential: {m['monetization']}/100")
    if "discovery" in m:
        lines.append(f"Discoverability: {m['discovery']}/100")
    if "duration" in m:
        lines.append(f"Stream Duration: {m['duration']}")
    return "\n".join(lines) if lines else "No metrics available"