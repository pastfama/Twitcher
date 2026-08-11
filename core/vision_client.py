"""Vision Client — captures screenshots and sends to Azure for analysis.

Uses direct HTTP requests instead of the OpenAI SDK.
"""

import os
import base64
import threading
import time
import requests
from typing import Optional
from logger import debug


_vision_client = None
_vision_lock = threading.Lock()

VISION_SYSTEM_PROMPT = """You are a sharp streaming analyst examining a screenshot from a live stream.
Analyze the image and respond with a brief, specific observation (2-3 sentences max).
Focus on: game/content, UI elements, visual quality, notable moments.
Be specific and data-driven. Use a sportscaster tone.
Respond ONLY with the observation text."""


def get_vision_config():
    """Get vision configuration from environment."""
    return {
        "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", "https://aoai-twitcher-80fcb.openai.azure.com/").rstrip("/"),
        "deployment": os.getenv("AZURE_VISION_DEPLOYMENT", "gpt-4o-vision"),
        "api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        "api_key": os.getenv("AZURE_OPENAI_API_KEY", ""),
    }


def analyze_frame(image_bytes: bytes, deployment: str = "") -> str:
    """Analyze a screenshot using GPT-4o Vision via direct HTTP."""
    config = get_vision_config()
    if not config["api_key"]:
        return ""
    
    if not deployment:
        deployment = config["deployment"]

    try:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        mime = "image/jpeg" if image_bytes[:2] == b'\xff\xd8' else "image/png"
        data_url = f"data:{mime};base64,{b64}"

        url = f"{config['endpoint']}/openai/deployments/{deployment}/chat/completions"
        headers = {"Content-Type": "application/json", "api-key": config["api_key"]}
        params = {"api-version": config["api_version"]}
        
        body = {
            "messages": [
                {"role": "system", "content": VISION_SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": "Analyze this stream screenshot."},
                ]},
            ],
            "max_tokens": 200,
        }

        response = requests.post(url, json=body, headers=headers, params=params, timeout=30)
        
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            debug(f"[VISION] Rate limited, waiting {retry_after}s")
            time.sleep(retry_after)
            response = requests.post(url, json=body, headers=headers, params=params, timeout=30)
        
        response.raise_for_status()
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    except Exception as e:
        debug(f"[VISION] Analysis failed: {e}")
        return ""


def capture_widget_screenshot(widget, max_width: int = 768, fmt: str = "JPEG", quality: int = 70) -> Optional[bytes]:
    """Capture a screenshot of a Qt widget as image bytes."""
    try:
        from PySide6.QtCore import QBuffer, QIODevice
        from PySide6.QtGui import QPixmap

        pixmap = widget.grab()
        if pixmap.isNull():
            return None

        if pixmap.width() > max_width:
            pixmap = pixmap.scaledToWidth(max_width, Qt.TransformationMode.SmoothTransformation)

        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, fmt, quality=quality if fmt == "JPEG" else -1)
        return bytes(buffer.data())
    except Exception as e:
        debug(f"[VISION] Screenshot capture failed: {e}")
        return None