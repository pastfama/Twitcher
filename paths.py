"""Centralized path resolution for Watcher.

Handles the difference between running from source (development) and
running as a PyInstaller frozen executable.  All modules that need
filesystem paths should import from here instead of computing their own.

Path strategy:
    Frozen (PyInstaller onefile):
        - exe_dir   = directory containing Watcher.exe (where the user put it)
        - data_dir  = %APPDATA%\\Watcher\\  (persistent user data)
    Dev (running from source):
        - exe_dir   = project root
        - data_dir  = project root  (same as before, backward compatible)
"""

import os
import sys


def _is_frozen():
    """Return True if running as a PyInstaller frozen executable."""
    return getattr(sys, "frozen", False)


def get_exe_dir():
    """Return the directory containing the executable (or project root in dev)."""
    if _is_frozen():
        return os.path.dirname(sys.executable)
    # Dev mode: this file is in the project root
    return os.path.dirname(os.path.abspath(__file__))


def get_data_dir():
    """Return the directory for persistent user data (DB, logs, config).

    Frozen: %APPDATA%\\Watcher\\
    Dev:    project root
    """
    if _is_frozen():
        base = os.environ.get("APPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Roaming"
        )
        data_dir = os.path.join(base, "Watcher")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir
    return get_exe_dir()


def get_db_path():
    """Return the full path to the SQLite database file."""
    return os.path.join(get_data_dir(), "watcher.db")


def get_log_path():
    """Return the full path to the debug log file."""
    return os.path.join(get_data_dir(), "watcher_debug.log")


def get_config_path():
    """Return the full path to the Twitch API config file."""
    if _is_frozen():
        # config.yaml is bundled inside the exe's _MEIPASS extraction dir
        return os.path.join(sys._MEIPASS, "twitch_api", "config.yaml")
    return os.path.join(get_exe_dir(), "twitch_api", "config.yaml")


def get_license_path():
    """Return the full path to the LICENSE file."""
    if _is_frozen():
        # LICENSE is bundled inside the exe's _MEIPASS extraction dir
        candidate = os.path.join(sys._MEIPASS, "LICENSE")
        if os.path.exists(candidate):
            return candidate
        # Fallback: next to the exe
        return os.path.join(get_exe_dir(), "LICENSE")
    return os.path.join(get_exe_dir(), "LICENSE")


def migrate_legacy_data():
    """Move data files from the exe directory to the data directory.

    In dev mode or on first run of a frozen exe, data files (watcher.db,
    watcher_debug.log) may exist next to the exe.  This function copies
    them to the proper data directory if they exist there and not in the
    data dir.

    Returns a list of (filename, old_path, new_path) tuples for files moved.
    """
    if not _is_frozen():
        return []

    moved = []
    exe_dir = get_exe_dir()
    data_dir = get_data_dir()

    if exe_dir == data_dir:
        return []

    legacy_files = [
        "watcher.db",
        "watcher_debug.log",
        "watcher_errors.txt",
        "twitch_token.json",
        "kick_token.json",
        "youtube_token.json",
        ".env",
        "last_channel.txt",
    ]
    for filename in legacy_files:
        old_path = os.path.join(exe_dir, filename)
        new_path = os.path.join(data_dir, filename)
        if os.path.exists(old_path) and not os.path.exists(new_path):
            try:
                import shutil
                shutil.copy2(old_path, new_path)
                moved.append((filename, old_path, new_path))
            except Exception:
                pass  # Best effort — don't crash on migration failure

    return moved