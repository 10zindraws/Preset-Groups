"""Logging utilities.

Currently a no-op stub. Can be enabled for debugging by setting
_DEBUG_ENABLED = True.
"""

import os

_DEBUG_ENABLED = False
_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "log.txt")


def write_log(message: str) -> None:
    """Write a debug message to the log file (no-op if debugging disabled)."""
    if not _DEBUG_ENABLED:
        return
    
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except OSError:
        pass
