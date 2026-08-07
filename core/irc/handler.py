"""Twitch IRC message parser — extracts tags, badges, emotes from IRC lines.

Twitch IRC uses IRCv3 message tags to carry metadata (badges, emotes,
display name, user color, etc.).  This module provides a pure-data
parser that converts a raw IRC line into a structured dict.
"""

import re
from typing import Optional


def parse_irc_line(line: str) -> Optional[dict]:
    """Parse a raw IRC line into a structured message dict.

    Returns ``None`` for non-PRIVMSG lines (PING, JOIN, etc.).

    The returned dict has these keys:
        - ``username``: sender login
        - ``display_name``: sender display name (may differ from login)
        - ``channel``: channel name without #
        - ``message``: message text
        - ``tags``: raw IRCv3 tags dict
        - ``badges``: list of badge strings (e.g. ["moderator/1"])
        - ``color``: user color hex (e.g. "#FF0000")
        - ``emotes``: list of emote tuples (id, start, end)
        - ``id``: message UUID (for reply chains)
    """
    if not line or "PRIVMSG" not in line:
        return None

    # --- extract tags (IRCv3) ---
    tags = {}
    if line.startswith("@"):
        tag_part, _, line = line.partition(" ")
        for pair in tag_part[1:].split(";"):
            if "=" in pair:
                key, _, val = pair.partition("=")
                tags[key] = val.replace("\\s", " ").replace("\\:", ";").replace("\\n", "\n")

    # --- extract prefix ---
    prefix = ""
    if line.startswith(":"):
        prefix, _, line = line.lstrip(":").partition(" ")

    # --- split command and params ---
    parts = line.split(" ", 2)
    if len(parts) < 3:
        return None

    command = parts[0]  # PRIVMSG
    target = parts[1]   # #channel
    message = parts[2]

    if message.startswith(":"):
        message = message[1:]

    # --- extract username from prefix ---
    username = prefix.split("!")[0] if "!" in prefix else prefix

    # --- channel without # ---
    channel = target.lstrip("#")

    # --- parse badges ---
    badges = []
    if "badges" in tags and tags["badges"]:
        badges = [b for b in tags["badges"].split(",") if b]

    # --- parse emotes ---
    emotes = []
    if "emotes" in tags and tags["emotes"]:
        for emote_str in tags["emotes"].split("/"):
            if not emote_str:
                continue
            emote_id, _, positions = emote_str.partition(":")
            for pos in positions.split(","):
                if "-" in pos:
                    start, _, end = pos.partition("-")
                    emotes.append((emote_id, int(start), int(end)))

    return {
        "username": username,
        "display_name": tags.get("display-name", username),
        "channel": channel,
        "message": message,
        "tags": tags,
        "badges": badges,
        "color": tags.get("color", ""),
        "emotes": emotes,
        "id": tags.get("id", ""),
        "user_id": tags.get("user-id", ""),
    }


def parse_join_part(line: str) -> Optional[dict]:
    """Parse JOIN/PART lines.

    Returns dict with ``username`` and ``channel`` and ``action``
    (``"join"`` or ``"part"``), or ``None``.
    """
    for action, cmd in [("join", "JOIN"), ("part", "PART")]:
        if cmd in line:
            prefix = ""
            if line.startswith(":"):
                prefix, _, line = line.lstrip(":").partition(" ")
            parts = line.split(" ")
            if len(parts) >= 2:
                username = prefix.split("!")[0] if "!" in prefix else prefix
                channel = parts[1].lstrip("#") if len(parts) > 1 else ""
                return {"username": username, "channel": channel, "action": action}
    return None