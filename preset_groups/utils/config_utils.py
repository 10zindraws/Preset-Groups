"""Configuration utilities for accessing common settings.

Provides cached access to configuration values with lazy loading.
"""

from .data_manager import check_common_config, invalidate_common_config_cache

# Module-level cache for configuration
_config_cache = None


def get_common_config() -> dict:
    """Get common configuration, cached for performance."""
    global _config_cache
    if _config_cache is None:
        _config_cache = check_common_config()
    return _config_cache


def reload_config() -> dict:
    """Clear cache and reload configuration from disk."""
    global _config_cache
    _config_cache = None
    # Also invalidate the data_manager cache
    invalidate_common_config_cache()
    return get_common_config()


def _get_layout_value(key: str, default):
    """Get a value from the layout section of config."""
    return get_common_config().get("layout", {}).get(key, default)


def _get_shortcut_value(key: str, default):
    """Get a value from the shortcut section of config."""
    return get_common_config().get("shortcut", {}).get(key, default)


def get_spacing_between_buttons() -> int:
    """Get spacing between buttons from config."""
    return _get_layout_value("spacing_between_buttons", 1)


def get_spacing_between_grids() -> int:
    """Get spacing between grids from config."""
    return _get_layout_value("spacing_between_grids", 1)


def get_brush_icon_size() -> int:
    """Get brush icon size from config."""
    return _get_layout_value("brush_icon_size", 65)


def get_display_brush_names() -> bool:
    """Get whether brush names should be displayed below icons."""
    return _get_layout_value("display_brush_names", True)


def get_choose_left_key() -> str:
    """Get the keyboard shortcut for choosing left brush in grid."""
    return _get_shortcut_value("choose_left_in_grid", ",")


def get_choose_right_key() -> str:
    """Get the keyboard shortcut for choosing right brush in grid."""
    return _get_shortcut_value("choose_right_in_grid", ".")


def get_wrap_around_navigation() -> bool:
    """Get whether wrap-around navigation is enabled."""
    return _get_shortcut_value("wrap_around_navigation", True)


def get_exclusive_uncollapse() -> bool:
    """Get whether exclusive uncollapse mode is enabled.
    
    When enabled, only one group can be uncollapsed at a time.
    The uncollapsed group becomes the active_grid.
    """
    return _get_layout_value("exclusive_uncollapse", False)


def get_font_px(font_size_str: str) -> int:
    """Convert font size string (e.g., '12px') to integer pixels."""
    try:
        return int(str(font_size_str).replace("px", ""))
    except (ValueError, TypeError):
        return 12


# Brush name label sizing constants
_BRUSH_NAME_MIN_FONT_SIZE = 6
_BRUSH_NAME_MAX_FONT_SIZE = 24
_BRUSH_NAME_DEFAULT_FONT_SIZE = 9

# Temporary font size override for live preview (None = use config)
_temp_brush_name_font_size = None


def get_brush_name_font_size_config() -> int:
    """Get the configured brush name font size from config.
    
    Returns:
        Font size in pixels from config, or default if not set.
    """
    return _get_layout_value("brush_name_font_size", _BRUSH_NAME_DEFAULT_FONT_SIZE)


def set_brush_name_font_size_temp(size: int) -> None:
    """Set a temporary font size override for live preview.
    
    Args:
        size: Font size in pixels, or None to clear the override.
    """
    global _temp_brush_name_font_size
    _temp_brush_name_font_size = size


def clear_brush_name_font_size_temp() -> None:
    """Clear the temporary font size override."""
    global _temp_brush_name_font_size
    _temp_brush_name_font_size = None


def get_brush_name_font_size() -> int:
    """Get font size for brush names.
    
    Returns the temporary preview size if set, otherwise the configured value.
    The value is clamped between min and max thresholds.
    """
    global _temp_brush_name_font_size
    if _temp_brush_name_font_size is not None:
        size = _temp_brush_name_font_size
    else:
        size = get_brush_name_font_size_config()
    # Clamp between min and max
    return max(_BRUSH_NAME_MIN_FONT_SIZE, min(_BRUSH_NAME_MAX_FONT_SIZE, size))


def get_brush_name_label_height(lines: int = 1) -> int:
    """Calculate height for brush name label based on number of lines.
    
    Args:
        lines: Number of text lines (1 or 2)
    
    Returns:
        Height in pixels for the name label area
    """
    font_size = get_brush_name_font_size()
    line_height = int(font_size * 1.3)  # Line height multiplier
    padding = 4  # Top + bottom padding
    return (line_height * lines) + padding


# Group name font sizing constants
_GROUP_NAME_MIN_FONT_SIZE = 8
_GROUP_NAME_MAX_FONT_SIZE = 24
_GROUP_NAME_DEFAULT_FONT_SIZE = 12

# Default padding for group name row (when font size is at default)
_GROUP_NAME_DEFAULT_PADDING = 2

# Temporary font size override for live preview (None = use config)
_temp_group_name_font_size = None


def get_group_name_font_size_config() -> int:
    """Get the configured group name font size from config.
    
    Returns:
        Font size in pixels from config, or default if not set.
    """
    return _get_layout_value("group_name_font_size", _GROUP_NAME_DEFAULT_FONT_SIZE)


def set_group_name_font_size_temp(size: int) -> None:
    """Set a temporary font size override for live preview.
    
    Args:
        size: Font size in pixels, or None to clear the override.
    """
    global _temp_group_name_font_size
    _temp_group_name_font_size = size


def clear_group_name_font_size_temp() -> None:
    """Clear the temporary group name font size override."""
    global _temp_group_name_font_size
    _temp_group_name_font_size = None


def get_group_name_font_size() -> int:
    """Get font size for group names.
    
    Returns the temporary preview size if set, otherwise the configured value.
    The value is clamped between min and max thresholds.
    """
    global _temp_group_name_font_size
    if _temp_group_name_font_size is not None:
        size = _temp_group_name_font_size
    else:
        size = get_group_name_font_size_config()
    # Clamp between min and max
    return max(_GROUP_NAME_MIN_FONT_SIZE, min(_GROUP_NAME_MAX_FONT_SIZE, size))


def get_group_name_padding() -> int:
    """Calculate padding for group name row based on font size.
    
    Padding scales proportionally with font size to maintain visual balance.
    
    Returns:
        Padding in pixels (applied to top and bottom).
    """
    font_size = get_group_name_font_size()
    # Scale padding proportionally: at default size (12px), use default padding (2px)
    # For each px above/below default, adjust padding proportionally
    scale_factor = font_size / _GROUP_NAME_DEFAULT_FONT_SIZE
    padding = int(_GROUP_NAME_DEFAULT_PADDING * scale_factor)
    return max(4, padding)  # Ensure at least 4px padding for grid names


def get_collapse_button_size(name_button_height: int) -> tuple:
    """Calculate collapse button dimensions based on group font size.
    
    Sizing behavior:
    - At font size 12 (default): Square button matching name button height
    - At font size > 12: Height matches name button, width stays at base size (tall rectangle)
    - At font size < 12: Both dimensions scale proportionally (stays square, just smaller)
    
    Args:
        name_button_height: The current height of the name button in pixels.
    
    Returns:
        Tuple of (width, height) in pixels for the collapse button.
    """
    font_size = get_group_name_font_size()
    
    if font_size >= _GROUP_NAME_DEFAULT_FONT_SIZE:
        # Font size >= 12: height scales with name button, width stays at base
        # Calculate what the base width would be at font size 12
        scale_factor = font_size / _GROUP_NAME_DEFAULT_FONT_SIZE
        base_width = int(name_button_height / scale_factor)
        return (base_width, name_button_height)
    else:
        # Font size < 12: both dimensions scale proportionally (stays square)
        # The name_button_height already reflects the smaller size
        return (name_button_height, name_button_height)
