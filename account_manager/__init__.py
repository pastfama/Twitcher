"""Account Manager — unified authentication for all streaming platforms.

Provides a single entry point for authenticating with Twitch, Kick, and YouTube.
Opens the browser for OAuth flows and stores credentials securely.

Usage:
    from account_manager import AccountManager
    am = AccountManager()
    am.login_twitch()
    am.login_kick()
    am.login_youtube()
"""

from .manager import AccountManager

__all__ = ["AccountManager"]