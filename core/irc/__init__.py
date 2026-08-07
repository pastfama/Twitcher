try:
    from .client import IRCClient
    _HAS_IRC3 = True
except ImportError:
    IRCClient = None
    _HAS_IRC3 = False

__all__ = ["IRCClient"]
