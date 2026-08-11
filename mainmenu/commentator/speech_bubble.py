"""Speech Bubble — animated text bubble for the Watcher Bot character.

Features:
- Typewriter animation (characters appear one by one)
- Mood-colored border
- "..." loading state
- Auto-size based on text length
"""

from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath
from PySide6.QtWidgets import QWidget


class SpeechBubble(QWidget):
    """A speech bubble with typewriter text animation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60)
        self._full_text = ""
        _displayed_chars = 0
        self._displayed_chars = 0
        self._color = QColor("#00ffff")
        self._bg_color = QColor("#0a0d18")
        self._border_color = QColor("#1a2a4a")
        self._loading = False
        self._loading_dots = 0

        # Typewriter timer
        self._type_timer = QTimer(self)
        self._type_timer.setInterval(30)  # 30ms per character
        self._type_timer.timeout.connect(self._type_next)

        # Loading dots timer
        self._dots_timer = QTimer(self)
        self._dots_timer.setInterval(400)
        self._dots_timer.timeout.connect(self._animate_dots)
        self._loading_text = "Analyzing"  # default loading message

    def show_text(self, text: str, color: str = "#00ffff"):
        """Show text with typewriter animation."""
        self._full_text = text
        self._displayed_chars = 0
        self._color = QColor(color)
        self._border_color = QColor(color).darker(200)
        self._loading = False
        self._dots_timer.stop()
        self._type_timer.start()
        self.update()

    def show_loading(self, color: str = "#00ffff", text: str = ""):
        """Show loading dots animation.
        
        Args:
            color: Border/text color during loading.
            text: Custom loading message (e.g., "Connecting to Azure").
                  Defaults to "Analyzing" if empty.
        """
        self._loading = True
        self._loading_text = text or "Analyzing"
        self._full_text = ""
        self._displayed_chars = 0
        self._color = QColor(color)
        self._type_timer.stop()
        self._dots_timer.start()
        self.update()

    def set_color(self, color: str):
        """Update the bubble color."""
        self._color = QColor(color)
        self._border_color = QColor(color).darker(200)
        self.update()

    def _type_next(self):
        """Advance typewriter by one character."""
        if self._displayed_chars < len(self._full_text):
            self._displayed_chars += 1
            self.update()
        else:
            self._type_timer.stop()

    def _animate_dots(self):
        """Animate loading dots."""
        self._loading_dots = (self._loading_dots + 1) % 4
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        margin = 8
        bubble_x = margin
        bubble_y = margin
        bubble_w = w - 2 * margin
        bubble_h = h - 2 * margin - 10  # leave room for tail

        # ── Bubble background ──
        p.setBrush(QBrush(self._bg_color))
        p.setPen(QPen(self._border_color, 1.5))
        p.drawRoundedRect(bubble_x, bubble_y, bubble_w, bubble_h, 8, 8)

        # ── Tail (triangle pointing left toward the character) ──
        tail_path = QPainterPath()
        tail_path.moveTo(bubble_x + 15, bubble_y + bubble_h)
        tail_path.lineTo(bubble_x, bubble_y + bubble_h + 10)
        tail_path.lineTo(bubble_x + 25, bubble_y + bubble_h)
        p.setBrush(QBrush(self._bg_color))
        p.setPen(QPen(self._border_color, 1.5))
        p.drawPath(tail_path)
        # Cover the top line of the tail
        p.setPen(QPen(self._bg_color, 2))
        p.drawLine(bubble_x + 14, bubble_y + bubble_h,
                   bubble_x + 26, bubble_y + bubble_h)

        # ── Text ──
        if self._loading:
            dots = "." * self._loading_dots
            display = f"{self._loading_text}{dots}"
            p.setPen(QPen(QColor("#8b93ad")))
        else:
            display = self._full_text[:self._displayed_chars]
            # Fade color based on completion
            alpha = 255 if self._displayed_chars >= len(self._full_text) else 200
            p.setPen(QPen(QColor(self._color.red(), self._color.green(),
                                  self._color.blue(), alpha)))

        font = QFont("Segoe UI", 9)
        font.setItalic(True)
        p.setFont(font)

        # Word wrap text
        text_rect = bubble_x + 10
        text_top = bubble_y + 6
        text_w = bubble_w - 20
        text_h = bubble_h - 12
        p.drawText(
            text_rect, text_top, text_w, text_h,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            display
        )

        # ── Cursor blink (during typing) ──
        if self._type_timer.isActive() and self._displayed_chars < len(self._full_text):
            # Simple cursor at end of text
            fm = p.fontMetrics()
            cursor_x = text_rect + fm.horizontalAdvance(display.split('\n')[-1]) + 2
            cursor_y = text_top + (display.count('\n')) * fm.height()
            if int(self._displayed_chars / 3) % 2 == 0:  # blink
                p.setPen(QPen(self._color, 1))
                p.drawLine(cursor_x, cursor_y, cursor_x, cursor_y + fm.height())

        p.end()