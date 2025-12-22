"""Data persistence and configuration management.

Handles loading/saving of grid data and common configuration files.
"""

import os
import json
from typing import Any

# Path constants
_UTILS_DIR = os.path.dirname(__file__)
_CONFIG_DIR = os.path.join(_UTILS_DIR, "..", "config")
_CONFIG_PATH = os.path.join(_CONFIG_DIR, "common.json")

# Default configuration
DEFAULT_CONFIG = {
    "color": {
        "docker_button_font_color": "#000000",
        "docker_button_background_color": "#63666a",
        "shortcut_button_font_color": "#eaeaea",
        "shortcut_button_background_color": "#2a1c2a",
    },
    "font": {
        "docker_button_font_size": "10px",
        "shortcut_button_font_size": "14px",
    },
    "shortcut": {
        "add_brush_to_grid": "W",
        "choose_left_in_grid": ",",
        "choose_right_in_grid": ".",
        "wrap_around_navigation": True,
    },
    "layout": {
        "max_shortcut_per_row": 4,
        "max_brush_per_row": 8,
        "spacing_between_buttons": 1,
        "spacing_between_grids": 1,
        "brush_icon_size": 65,
        "display_brush_names": True,
    },
    "brush_slider": {
        "max_brush_size": 1000,
    },
}


def _read_json(path: str, default: Any = None) -> Any:
    """Safely read a JSON file, returning default on error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_json(path: str, data: Any) -> bool:
    """Safely write data to a JSON file."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error writing JSON to {path}: {e}")
        return False


def load_common_config() -> dict:
    """Load common configuration, falling back to defaults."""
    return _read_json(_CONFIG_PATH, DEFAULT_CONFIG.copy())


def save_common_config(config: dict) -> bool:
    """Save common configuration to file."""
    return _write_json(_CONFIG_PATH, config)


def check_common_config() -> dict:
    """Ensure config file exists and return its contents."""
    if not os.path.exists(_CONFIG_PATH):
        _write_json(_CONFIG_PATH, DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    return _read_json(_CONFIG_PATH, DEFAULT_CONFIG.copy())


def _create_empty_grid_info(name: str) -> dict:
    """Create an empty grid info dictionary."""
    return {
        "container": None,
        "widget": None,
        "layout": None,
        "name_label": None,
        "rename_button": None,
        "name": name,
        "brush_presets": [],
        "is_active": False,
    }


def load_grids_data(data_file: str, preset_dict: dict) -> tuple[list, int]:
    """Load grids data from file, resolving preset names to objects."""
    if not os.path.exists(data_file):
        return [], 0

    data = _read_json(data_file, {"grids": []})
    if not data:
        return [], 0

    grids = []
    for idx, grid_data in enumerate(data.get("grids", []), start=1):
        grid_name = grid_data.get("name", f"Group {idx}")
        brush_names = grid_data.get("brush_presets", [])
        
        # Resolve preset names to actual preset objects
        brush_presets = [
            preset_dict[name]
            for name in brush_names
            if name in preset_dict
        ]
        
        grid_info = _create_empty_grid_info(grid_name)
        grid_info["brush_presets"] = brush_presets
        grids.append(grid_info)

    return grids, len(grids)


def save_grids_data(data_file: str, grids: list) -> bool:
    """Save grids data to file."""
    data = {
        "grids": [
            {
                "name": grid["name"],
                "brush_presets": [p.name() for p in grid["brush_presets"]],
            }
            for grid in grids
        ]
    }
    return _write_json(data_file, data)
