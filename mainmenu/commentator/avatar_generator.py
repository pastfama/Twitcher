"""Avatar Generator — generates VTuber-style character images via Azure AI.

Generates and caches character expression images for the AI Commentator.
Uses Azure OpenAI to create high-quality avatar portraits, then displays
them with smooth crossfade transitions.
"""

import os
import json
import hashlib
import threading
from typing import Dict, Optional
from logger import debug

ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "commentator"
)

# Expression definitions with prompts
EXPRESSIONS = {
    "happy": {
        "prompt": (
            "A portrait of a professional male news anchor character in anime VTuber style. "
            "He has a warm, friendly smile, bright eyes, and is wearing a dark blue suit "
            "with a glowing teal tie. Studio background with soft neon lighting. "
            "Expression: happy and welcoming. High quality, detailed, suitable for a streaming app."
        ),
        "mood_color": "#00ff88",
    },
    "hyped": {
        "prompt": (
            "A portrait of a professional male news anchor character in anime VTuber style. "
            "He has an excited, energetic expression with wide eyes and a big grin. "
            "Wearing a dark blue suit with a glowing red tie. Studio background with dynamic lighting. "
            "Expression: hyped and energetic. High quality, detailed, suitable for a streaming app."
        ),
        "mood_color": "#ff3366",
    },
    "neutral": {
        "prompt": (
            "A portrait of a professional male news anchor character in anime VTuber style. "
            "He has a calm, composed expression with a slight professional smile. "
            "Wearing a dark blue suit with a glowing cyan tie. Studio background with neutral lighting. "
            "Expression: neutral and professional. High quality, detailed, suitable for a streaming app."
        ),
        "mood_color": "#00ffff",
    },
    "sleepy": {
        "prompt": (
            "A portrait of a professional male news anchor character in anime VTuber style. "
            "He has a tired, relaxed expression with half-closed eyes. "
            "Wearing a dark blue suit with a glowing purple tie. Studio background with dim lighting. "
            "Expression: sleepy and relaxed. High quality, detailed, suitable for a streaming app."
        ),
        "mood_color": "#aa44ff",
    },
    "concerned": {
        "prompt": (
            "A portrait of a professional male news anchor character in anime VTuber style. "
            "He has a worried, concerned expression with furrowed brows. "
            "Wearing a dark blue suit with a glowing amber tie. Studio background with warm lighting. "
            "Expression: concerned and attentive. High quality, detailed, suitable for a streaming app."
        ),
        "mood_color": "#ffaa00",
    },
    "mind_blown": {
        "prompt": (
            "A portrait of a professional male news anchor character in anime VTuber style. "
            "He has a shocked, amazed expression with wide eyes and open mouth. "
            "Wearing a dark blue suit with a glowing red tie. Studio background with dramatic lighting. "
            "Expression: mind blown and amazed. High quality, detailed, suitable for a streaming app."
        ),
        "mood_color": "#ff3366",
    },
}

MOOD_TO_EXPRESSION = {
    "hype": "hyped",
    "positive": "happy",
    "neutral": "neutral",
    "slow": "sleepy",
    "tense": "concerned",
    "mind_blown": "mind_blown",
}


class AvatarGenerator:
    """Generates and caches VTuber avatar images via Azure AI."""

    def __init__(self):
        self._cache: Dict[str, str] = {}  # expression -> file path
        self._generating = False
        self._on_complete = None  # callback when generation finishes
        self._ensure_dir()

    def _ensure_dir(self):
        os.makedirs(ASSETS_DIR, exist_ok=True)

    def get_avatar_path(self, expression: str) -> Optional[str]:
        """Get the cached avatar image path for an expression.

        Returns the file path if it exists, None if not yet generated.
        """
        if expression in self._cache:
            return self._cache[expression]

        # Check disk cache
        path = os.path.join(ASSETS_DIR, f"{expression}.png")
        if os.path.exists(path):
            self._cache[expression] = path
            return path

        return None

    def get_all_avatars(self) -> Dict[str, Optional[str]]:
        """Get all cached avatar paths."""
        result = {}
        for expr in EXPRESSIONS:
            result[expr] = self.get_avatar_path(expr)
        return result

    def generate_all_async(self, on_complete=None):
        """Generate all expression avatars in a background thread.

        Args:
            on_complete: Callback called on completion: (success: bool, paths: dict)
        """
        if self._generating:
            debug("[AVATAR] Already generating, skipping")
            return

        self._generating = True
        self._on_complete = on_complete

        def bg():
            try:
                paths = {}
                for expr, config in EXPRESSIONS.items():
                    cached = self.get_avatar_path(expr)
                    if cached:
                        paths[expr] = cached
                        continue

                    path = self._generate_one(expr, config["prompt"])
                    if path:
                        paths[expr] = path
                    else:
                        paths[expr] = None

                if self._on_complete:
                    self._on_complete(True, paths)
            except Exception as e:
                debug(f"[AVATAR] Generation error: {e}")
                if self._on_complete:
                    self._on_complete(False, {})
            finally:
                self._generating = False

        threading.Thread(target=bg, daemon=True).start()

    def _generate_one(self, expression: str, prompt: str) -> Optional[str]:
        """Generate a single avatar image via Azure AI.

        Uses the Azure AI image generation endpoint to create a character portrait.
        Falls back to a placeholder if generation fails.
        """
        try:
            from openai import OpenAI
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider

            endpoint = os.getenv(
                "AZURE_OPENAI_ENDPOINT",
                "https://malovsky99-6011-resource.services.ai.azure.com/openai/v1"
            )
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(), "https://ai.azure.com/.default"
            )
            client = OpenAI(base_url=endpoint, api_key=token_provider)

            # Try to generate image using the Responses API with image generation
            # Note: This requires a deployment that supports image generation
            # If not available, we'll create a placeholder
            try:
                response = client.responses.create(
                    model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini-1"),
                    input=[
                        {
                            "role": "user",
                            "content": f"Generate an image: {prompt}",
                        },
                    ],
                    tools=[{"type": "image_generation"}],
                )

                # Extract image from response
                for item in response.output:
                    if hasattr(item, "content") and item.content:
                        for content_item in item.content:
                            if hasattr(content_item, "url"):
                                # Download the image
                                import urllib.request
                                path = os.path.join(ASSETS_DIR, f"{expression}.png")
                                urllib.request.urlretrieve(content_item.url, path)
                                debug(f"[AVATAR] Generated: {expression}")
                                return path
            except Exception as e:
                debug(f"[AVATAR] AI generation failed for {expression}: {e}")

            # Fallback: create a placeholder image
            return self._create_placeholder(expression)

        except Exception as e:
            debug(f"[AVATAR] Error: {e}")
            return self._create_placeholder(expression)

    def _create_placeholder(self, expression: str) -> str:
        """Create a placeholder avatar image using QPainter.

        Generates a simple but stylish avatar with the character's mood color.
        """
        try:
            from PySide6.QtGui import (
                QImage, QPainter, QColor, QRadialGradient, QBrush, QPen, QFont
            )
            from PySide6.QtCore import Qt, QPointF

            size = 256
            img = QImage(size, size, QImage.Format.Format_ARGB32)
            img.fill(QColor(0, 0, 0, 0))

            p = QPainter(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            mood_color = QColor(EXPRESSIONS[expression]["mood_color"])

            # Background circle with gradient
            grad = QRadialGradient(128, 128, 128)
            grad.setColorAt(0, QColor(mood_color.red(), mood_color.green(),
                                       mood_color.blue(), 60))
            grad.setColorAt(0.7, QColor(20, 25, 40, 200))
            grad.setColorAt(1, QColor(10, 13, 24, 255))
            p.setBrush(QBrush(grad))
            p.setPen(QPen(mood_color, 2))
            p.drawEllipse(10, 10, size - 20, size - 20)

            # Character silhouette (simple head + shoulders)
            head_color = QColor("#f0c8a0")
            suit_color = QColor("#1a2a4a")

            # Shoulders
            p.setBrush(QBrush(suit_color))
            p.setPen(Qt.PenStyle.NoPen)
            from PySide6.QtGui import QPainterPath
            shoulders = QPainterPath()
            shoulders.moveTo(40, 200)
            shoulders.quadTo(QPointF(128, 170), QPointF(216, 200))
            shoulders.lineTo(230, 260)
            shoulders.lineTo(26, 260)
            shoulders.closeSubpath()
            p.drawPath(shoulders)

            # Tie
            p.setBrush(QBrush(mood_color))
            tie = QPainterPath()
            tie.moveTo(124, 185)
            tie.lineTo(128, 220)
            tie.lineTo(132, 185)
            tie.closeSubpath()
            p.drawPath(tie)

            # Head
            p.setBrush(QBrush(head_color))
            p.setPen(QPen(QColor("#d4a880"), 1))
            p.drawEllipse(QPointF(128, 120), 55, 65)

            # Hair
            p.setBrush(QBrush(QColor("#2a1a0a")))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(128, 80), 50, 35)

            # Eyes
            for side in [-1, 1]:
                ex = 128 + side * 20
                ey = 115
                p.setBrush(QBrush(QColor("#ffffff")))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(ex, ey), 10, 8)
                p.setBrush(QBrush(mood_color))
                p.drawEllipse(QPointF(ex, ey), 5, 5)
                p.setBrush(QBrush(QColor("#000000")))
                p.drawEllipse(QPointF(ex, ey), 2, 2)

            # Mouth based on expression
            mouth_y = 140
            mouth_w = 15
            p.setPen(QPen(QColor("#8a4a3a"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            if expression == "happy":
                p.drawArc(int(128 - mouth_w), int(mouth_y - 8),
                          int(mouth_w * 2), int(16), 0, -180 * 16)
            elif expression == "hyped":
                p.drawEllipse(QPointF(128, mouth_y + 2), 8, 10)
            elif expression == "sleepy":
                p.drawLine(int(128 - mouth_w), int(mouth_y),
                           int(128 + mouth_w), int(mouth_y))
            elif expression == "concerned":
                p.drawArc(int(128 - mouth_w), int(mouth_y),
                          int(mouth_w * 2), int(12), 0, 180 * 16)
            elif expression == "mind_blown":
                p.drawEllipse(QPointF(128, mouth_y + 2), 10, 12)
            else:
                p.drawLine(int(128 - mouth_w), int(mouth_y),
                           int(128 + mouth_w), int(mouth_y))

            p.end()

            path = os.path.join(ASSETS_DIR, f"{expression}.png")
            img.save(path, "PNG")
            debug(f"[AVATAR] Created placeholder: {expression}")
            return path

        except Exception as e:
            debug(f"[AVATAR] Placeholder creation failed: {e}")
            return ""


# Singleton
_generator = None


def get_avatar_generator() -> AvatarGenerator:
    global _generator
    if _generator is None:
        _generator = AvatarGenerator()
    return _generator