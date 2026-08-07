"""Twitch token helpers for chat authentication.

Provides token normalization, loading, and identity validation
used by the chat panel.
"""

import requests

from logger import debug, info, warning, error
from twitch_token_manager import get_valid_token

TWITCH_VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"


def normalize_token(token) -> str:
    """Strip whitespace and the ``oauth:`` prefix from a token."""
    token = (token or "").strip()
    if token.lower().startswith("oauth:"):
        token = token[6:]
    return token


def load_twitch_token() -> str:
    """Load a valid Twitch access token for chat.

    Returns the normalized token, or ``""`` if none is available.
    """
    try:
        token = get_valid_token()
        if not token:
            debug("[CHAT] No valid Twitch access token available.")
            return ""
        return normalize_token(token)
    except Exception as exc:
        debug("[CHAT] Failed to obtain valid Twitch token:")
        debug(exc)
        return ""


def get_token_identity(access_token):
    """Validate a token and return ``(login, user_id)``.

    Raises ``RuntimeError`` if the token is invalid or the username
    cannot be determined.
    """
    access_token = normalize_token(access_token)
    if not access_token:
        raise RuntimeError("Twitch access token is empty.")

    response = requests.get(
        TWITCH_VALIDATE_URL,
        headers={"Authorization": f"OAuth {access_token}"},
        timeout=20,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "Twitch token validation failed.\n\n"
            f"HTTP {response.status_code}\n"
            f"{response.text}"
        )

    data = response.json()
    login = (data.get("login", "") or "").strip().lower()
    user_id = (data.get("user_id", "") or "").strip()

    if not login:
        raise RuntimeError(
            "Twitch did not return the username belonging to the access token."
        )

    debug("[CHAT] Twitch token identity:")
    debug(f"        Username: {login}")
    debug(f"        User ID:  {user_id}")
    debug("[CHAT] Twitch token scopes:")
    debug(f"        {data.get('scopes', [])}")

    return login, user_id