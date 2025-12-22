"""Dialogs package for the Preset Groups docker.

Contains dialog windows for various user interactions like settings
and context menus.
"""

from .settings_dialog import CommonConfigDialog
from .grid_context_dialog import GridNameContextDialog

__all__ = [
    "CommonConfigDialog",
    "GridNameContextDialog",
]
