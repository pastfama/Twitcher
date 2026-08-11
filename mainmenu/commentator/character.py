"""VTuber Avatar — displays AI-generated character images with smooth animation.

Features:
- Loads cached avatar images for each expression
- Smooth crossfade transitions between expressions
- Animated overlays: blinking glow, talking indicator, breathing effect
- Mood-colored glow ring around the avatar
- Falls back to placeholder if images aren't generated yet
"""

import math
import random
from PySide6.QtCore import Qt, QTimer, QPointF, QEasingCurve, QPropertyAnimation
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QRadialGradient,
    QLinearGradient, QPainterPath, QPixmap, QImage,
)
from PySide6.QtWidgets import QWidget
from logger import debug


class VTuberAvatar(QWidget):
    """Displays a VTuber-style avatar with crossfade animation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(160, 280)
        self.setMaximumWidth(180)

        # Avatar images
        self._current_pixmap = None
        self._target_pixmap = None
        self._avatar_cache = {}  # expression -> QPixmap

        # Animation state
        self._current_expression = "neutral"
        self._glow_color = QColor("#00ffff")
        self._glow_alpha = 40
        self._breath_phase = 0.0
        self._blink_timer = 0
        self._is_blinking = False
        self._is_talking = False
        self._talk_phase = 0.0
        self._crossfade_progress = 1.0  # 0.0 = old, 1.0 = new
        self._crossfading = False

        # Glow animation
        self._glow_pulse = 0.0

        # Animation timer (20fps)
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(50)
        self._anim_timer.timeout.connect(self._animate)
        self._anim_timer.start()

        # Load avatars lazily
        self._avatars_loaded = False

    def _load_avatars(self):
        """Load avatar images from the generator."""
        if self._avatars_loaded:
            return
        self._avatars_loaded = True

        try:
            from .avatar_generator import get_avatar_generator
            gen = get_avatar_generator()
            for expr in ["happy", "hyped", "neutral", "sleepy", "concerned", "mind_blown"]:
                path = gen.get_avatar_path(expr)
                if path:
                    pixmap = QPixmap(path)
                    if not pixmap.isNull():
                        self._avatar_cache[expr] = pixmap
                        debug(f"[AVATAR] Loaded: {expr}")

            # Set current to neutral
            if "neutral" in self._avatar_cache:
                self._current_pixmap = self._avatar_cache["neutral"]
        except Exception as e:
            debug(f"[AVATAR] Load error: {e}")

    def set_expression(self, mood: str):
        """Change the avatar expression with crossfade."""
        from .avatar_generator import MOOD_TO_EXPRESSION
        expr = MOOD_TO_EXPRESSION.get(mood, "neutral")

        if expr == self._current_expression:
            return

        self._current_expression = expr

        # Update glow color
        from .avatar_generator import EXPRESSIONS
        color_hex = EXPRESSIONS.get(expr, {}).get("mood_color", "#00ffff")
        self._glow_color = QColor(color_hex)

        # Start crossfade if we have the new image
        if expr in self._avatar_cache:
            self._target_pixmap = self._avatar_cache[expr]
            self._crossfade_progress = 0.0
            self._crossfading = True
        else:
            # Try to load it now
            try:
                from .avatar_generator import get_avatar_generator
                gen = get_avatar_generator()
                path = gen.get_avatar_path(expr)
                if path:
                    pixmap = QPixmap(path)
                    if not pixmap.isNull():
                        self._avatar_cache[expr] = pixmap
                        self._target_pixmap = pixmap
                        self._crossfade_progress = 0.0
                        self._crossfading = True
            except Exception:
                pass

    def set_talking(self, talking: bool):
        self._is_talking = talking

    def _animate(self):
        """Update animation state."""
        # Breathing
        self._breath_phase += 0.04

        # Blinking
        self._blink_timer += 1
        if self._blink_timer > 80 + random.randint(0, 40):
            self._is_blinking = True
            self._blink_timer = 0
        if self._is_blinking and self._blink_timer > 4:
            self._is_blinking = False

        # Talking
        if self._is_talking:
            self._talk_phase += 0.3
        else:
            self._talk_phase *= 0.9

        # Glow pulse
        self._glow_pulse += 0.05

        # Crossfade
        if self._crossfading:
            self._crossfade_progress += 0.05
            if self._crossfade_progress >= 1.0:
                self._crossfade_progress = 1.0
                self._current_pixmap = self._target_pixmap
                self._target_pixmap = None
                self._crossfading = False

        self.update()

    def paintEvent(self, event):
        self._load_avatars()

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        # ── Background ──
        self._draw_background(p, w, h)

        # ── Glow ring ──
        self._draw_glow_ring(p, cx, cy, w, h)

        # ── Avatar image ──
        self._draw_avatar(p, cx, cy, w, h)

        # ── Animated overlays ──
        self._draw_overlays(p, cx, cy, w, h)

        # ── Name tag ──
        self._draw_name_tag(p, w, h)

        p.end()

    def _draw_background(self, p, w, h):
        """Draw dark studio background."""
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor("#0a0d18"))
        grad.setColorAt(0.5, QColor("#0f1525"))
        grad.setColorAt(1, QColor("#141827"))
        p.fillRect(0, 0, int(w), int(h), grad)

    def _draw_glow_ring(self, p, cx, cy, w, h):
        """Draw a mood-colored glow ring around the avatar."""
        radius = min(w, h) * 0.38
        pulse = math.sin(self._glow_pulse) * 0.3 + 0.7
        alpha = int(self._glow_alpha * pulse)

        # Outer glow
        glow_grad = QRadialGradient(cx, cy, radius + 15)
        glow_grad.setColorAt(0, QColor(0, 0, 0, 0))
        glow_grad.setColorAt(0.8, QColor(self._glow_color.red(),
                                          self._glow_color.green(),
                                          self._glow_color.blue(), alpha))
        glow_grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(glow_grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), int(radius + 15), int(radius + 15))

        # Ring border
        ring_alpha = int(120 * pulse)
        p.setPen(QPen(QColor(self._glow_color.red(), self._glow_color.green(),
                              self._glow_color.blue(), ring_alpha), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), int(radius), int(radius))

    def _draw_avatar(self, p, cx, cy, w, h):
        """Draw the avatar image with crossfade."""
        radius = int(min(w, h) * 0.36)

        # Clip to circle
        clip_path = QPainterPath()
        clip_path.addEllipse(QPointF(cx, cy), radius, radius)
        p.setClipPath(clip_path)

        if self._crossfading and self._target_pixmap:
            # Draw old image (fading out)
            old_alpha = int(255 * (1.0 - self._crossfade_progress))
            if self._current_pixmap and old_alpha > 0:
                self._draw_pixmap_centered(p, self._current_pixmap, cx, cy, radius * 2)

            # Draw new image (fading in)
            new_alpha = int(255 * self._crossfade_progress)
            if new_alpha > 0:
                self._draw_pixmap_centered(p, self._target_pixmap, cx, cy, radius * 2)
        elif self._current_pixmap:
            self._draw_pixmap_centered(p, self._current_pixmap, cx, cy, radius * 2)
        else:
            # No image loaded — draw placeholder
            self._draw_placeholder(p, cx, cy, radius)

        p.setClipping(False)

    def _draw_pixmap_centered(self, p, pixmap, cx, cy, size):
        """Draw a pixmap centered and scaled to fit."""
        if pixmap.isNull():
            return
        scaled = pixmap.scaled(int(size), int(size),
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation)
        x = int(cx - scaled.width() / 2)
        y = int(cy - scaled.height() / 2)
        p.drawPixmap(x, y, scaled)

    def _draw_placeholder(self, p, cx, cy, radius):
        """Draw a simple placeholder when no avatar image is loaded."""
        # Head
        head_color = QColor("#f0c8a0")
        p.setBrush(QBrush(head_color))
        p.setPen(QPen(QColor("#d4a880"), 1))
        p.drawEllipse(QPointF(cx, cy - 10), 35, 42)

        # Hair
        p.setBrush(QBrush(QColor("#2a1a0a")))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy - 35), 32, 22)

        # Eyes
        for side in [-1, 1]:
            ex = cx + side * 14
            ey = cy - 15
            if self._is_blinking:
                p.setPen(QPen(QColor("#1a1a2a"), 2))
                p.drawLine(int(ex - 6), int(ey), int(ex + 6), int(ey))
            else:
                p.setBrush(QBrush(QColor("#ffffff")))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(ex, ey), 7, 6)
                p.setBrush(QBrush(self._glow_color))
                p.drawEllipse(QPointF(ex, ey), 4, 4)
                p.setBrush(QBrush(QColor("#000000")))
                p.drawEllipse(QPointF(ex, ey), 2, 2)

        # Mouth
        mouth_y = cy + 10
        mouth_w = 10
        talk_open = abs(math.sin(self._talk_phase)) * 5 if self._is_talking else 0
        p.setPen(QPen(QColor("#8a4a3a"), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        mouth_path = QPainterPath()
        mouth_path.moveTo(cx - mouth_w, mouth_y)
        mouth_path.quadTo(QPointF(cx, mouth_y + talk_open), QPointF(cx + mouth_w, mouth_y))
        p.drawPath(mouth_path)

    def _draw_overlays(self, p, cx, cy, w, h):
        """Draw animated overlays on top of the avatar."""
        radius = int(min(w, h) * 0.36)

        # Talking indicator (pulsing dots at bottom)
        if self._is_talking:
            dot_y = cy + radius + 12
            for i in range(3):
                dot_x = cx - 12 + i * 12
                phase = self._talk_phase + i * 0.5
                dot_alpha = int(200 * abs(math.sin(phase)))
                p.setBrush(QBrush(QColor(self._glow_color.red(),
                                          self._glow_color.green(),
                                          self._glow_color.blue(), dot_alpha)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(dot_x, dot_y), 3, 3)

        # Blink highlight (small white dot on eyes when blinking)
        if self._is_blinking:
            p.setBrush(QBrush(QColor(255, 255, 255, 180)))
            p.setPen(Qt.PenStyle.NoPen)
            for side in [-1, 1]:
                ex = cx + side * 14
                ey = cy - 15
                p.drawEllipse(QPointF(ex, ey), 2, 2)

    def _draw_name_tag(self, p, w, h):
        """Draw the 'WATCHER' name tag at the bottom."""
        tag_y = h - 20
        p.setPen(QPen(self._glow_color, 1))
        p.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        p.drawText(0, int(tag_y), int(w), 15,
                    Qt.AlignmentFlag.AlignHCenter, "WATCHER")