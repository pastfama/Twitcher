"""AI Commentator — VTuber avatar with speech bubble and commentary engine."""
from .character import VTuberAvatar
from .speech_bubble import SpeechBubble
from .engine import CommentaryEngine
from .panel import CommentatorPanel
from .avatar_generator import AvatarGenerator, get_avatar_generator

__all__ = ["VTuberAvatar", "SpeechBubble", "CommentaryEngine", "CommentatorPanel", "AvatarGenerator", "get_avatar_generator"]
