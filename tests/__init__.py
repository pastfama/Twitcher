"""Test package for Watcher.

Adds the project root to sys.path so test scripts can import
root-level modules (api, chat, logger, etc.) when run from tests/.
"""

import os
import sys

# Add the project root (parent of tests/) to sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)