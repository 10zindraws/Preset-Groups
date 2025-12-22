"""UI styling utilities and color constants."""

from PyQt5.QtGui import QColor

from .config_utils import get_common_config


# Theme color constants
DOCKER_BUTTON_BG = "#63666a"
DOCKER_BUTTON_TEXT = "#000000"
DOCKER_BUTTON_FONT_SIZE = "10px"
GRID_NAME_COLOR = "#979797"
SELECTION_HIGHLIGHT = "#46aaff"
DARK_BG = "#2b2b2b"
PANEL_BG = "#474747"
BORDER_COLOR = "#555"
BORDER_HOVER = "#777"
BORDER_PRESSED = "#333"


def lighten_color(hex_color, amount):
    """Lighten a hex color by adjusting its HSV value."""
    try:
        color = QColor(hex_color)
        h, s, v, a = color.getHsv()
        color.setHsv(h, s, min(255, v + amount), a)
        return color.name()
    except Exception:
        return hex_color


def darken_color(hex_color, amount):
    """Darken a hex color by adjusting its HSV value."""
    try:
        color = QColor(hex_color)
        h, s, v, a = color.getHsv()
        color.setHsv(h, s, max(0, v - amount), a)
        return color.name()
    except Exception:
        return hex_color


def docker_btn_style():
    """Generate stylesheet for docker buttons."""
    return f"""
        QPushButton {{
            background-color: {DOCKER_BUTTON_BG}; 
            color: {DOCKER_BUTTON_TEXT}; 
            font-size: {DOCKER_BUTTON_FONT_SIZE};
            border-radius: 6px;
            border: 1px solid {BORDER_COLOR};
            padding: 3px 6px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {lighten_color(DOCKER_BUTTON_BG, 15)};
            border: 1px solid {BORDER_HOVER};
        }}
        QPushButton:pressed {{
            background-color: {darken_color(DOCKER_BUTTON_BG, 15)};
            border: 1px solid {BORDER_PRESSED};
        }}
    """


def shortcut_btn_style():
    """Generate stylesheet for shortcut buttons from config."""
    config = get_common_config()
    color = config["color"]["shortcut_button_background_color"]
    font_color = config["color"]["shortcut_button_font_color"]
    font_size = config["font"]["shortcut_button_font_size"]
    return f"background-color: {color}; color: {font_color}; font-size: {font_size};"