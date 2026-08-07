"""Temporary script: find references to key methods across the codebase."""
import os

patterns = [
    "update_current_stream_view",
    "refresh_momsg",
    "_on_analytics_signal",
    "fetch_all_live_channels",
    "current_panel",
    "set_stream(",
    "update_next_stream",
    "_refresh_live_channels",
    "_load_cached_streamer_data",
    "enrich_stream_with_avatar",
    "viewer_analysis",
    "set_viewer_status",
    "sullygoose_for",
    "update_stream(",
    "get_channel_stats",
    "store_viewer_history",
]

for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
    for fname in files:
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(root, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    for pat in patterns:
                        if pat in line:
                            print(f"{fpath}:{i}: {line.rstrip()[:130]}")
                            break
        except Exception:
            pass