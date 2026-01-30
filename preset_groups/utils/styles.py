"""UI styling utilities using Krita theme colors via QPalette.

This module provides theme-aware colors that adapt to any Krita color scheme
(dark, light, or custom) by using Qt's QPalette system.

Color Mappings from Krita .colors files to QPalette:
- Colors:Window → QPalette.Window, QPalette.WindowText
- Colors:View → QPalette.Base, QPalette.Text, QPalette.AlternateBase
- Colors:Button → QPalette.Button, QPalette.ButtonText
- Colors:Selection → QPalette.Highlight, QPalette.HighlightedText
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette, QPainter, QPixmap
from PyQt5.QtWidgets import QApplication

from .config_utils import get_common_config


# =============================================================================
# Palette Access
# =============================================================================
def get_palette() -> QPalette:
    """Get the current application palette."""
    app = QApplication.instance()
    return app.palette() if app else QPalette()


def palette_color(role: QPalette.ColorRole, group: QPalette.ColorGroup = QPalette.Normal) -> QColor:
    """Get a QColor from the palette for the given role and group."""
    return get_palette().color(group, role)


def palette_color_name(role: QPalette.ColorRole, group: QPalette.ColorGroup = QPalette.Normal) -> str:
    """Get a hex color string from the palette for the given role and group."""
    return palette_color(role, group).name()


def is_dark_theme() -> bool:
    """Check if the current theme is dark based on window background lightness."""
    return palette_color(QPalette.Window).lightness() < 128


def get_background_lightness() -> int:
    """Get the lightness value (0-255) of the theme's background color."""
    return palette_color(QPalette.Window).lightness()


def is_light_theme() -> bool:
    """Check if the current theme is light (background > 50% brightness)."""
    return get_background_lightness() >= 128


def get_icon_tint_color() -> QColor:
    """Get the color to use for tinting icons in light themes.

    Returns the theme's text color for light themes, None for dark themes.
    """
    if is_light_theme():
        return palette_color(QPalette.WindowText)
    return None


def tint_pixmap(pixmap: QPixmap, tint_color: QColor) -> QPixmap:
    """Tint a pixmap to a specific color while preserving alpha.

    Args:
        pixmap: The QPixmap to tint
        tint_color: The color to apply as tint

    Returns:
        A new tinted QPixmap
    """
    if pixmap.isNull() or tint_color is None:
        return pixmap

    # Create a copy to avoid modifying the original
    result = QPixmap(pixmap.size())
    result.fill(Qt.transparent)

    painter = QPainter(result)
    painter.setCompositionMode(QPainter.CompositionMode_Source)

    # Draw the original pixmap
    painter.drawPixmap(0, 0, pixmap)

    # Apply tint using SourceIn composition (preserves alpha from destination)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(result.rect(), tint_color)

    painter.end()
    return result


def tint_icon_for_theme(pixmap):
    """Tint an icon pixmap based on current theme.

    For light themes (background > 50% brightness), tints the icon to match
    the theme's font color for better visibility.

    Args:
        pixmap: The QPixmap to potentially tint

    Returns:
        The original pixmap for dark themes, or a tinted pixmap for light themes
    """
    tint_color = get_icon_tint_color()
    if tint_color is None:
        return pixmap
    return tint_pixmap(pixmap, tint_color)


def color_similarity(color1: QColor, color2: QColor) -> float:
    """Calculate the similarity between two colors as a percentage (0-100).

    Uses lightness difference as the primary metric since contrast is about
    distinguishing elements visually.
    """
    lightness_diff = abs(color1.lightness() - color2.lightness())
    # Convert to percentage (255 is max lightness difference)
    return 100 - (lightness_diff / 255 * 100)


def ensure_contrast(color: QColor, background: QColor, min_contrast_percent: float = 10) -> QColor:
    """Ensure a color has at least min_contrast_percent difference from background.

    If the color is too similar to background, adjust it to be just past the threshold.

    Args:
        color: The color to check/adjust
        background: The background color to contrast against
        min_contrast_percent: Minimum required contrast (0-100)

    Returns:
        The original color if contrast is sufficient, otherwise an adjusted color
    """
    similarity = color_similarity(color, background)

    if similarity <= (100 - min_contrast_percent):
        # Contrast is sufficient
        return color

    # Need to adjust - determine direction based on theme
    bg_lightness = background.lightness()

    # Calculate the minimum lightness difference needed
    min_lightness_diff = int(255 * min_contrast_percent / 100) + 1

    if is_dark_theme():
        # Dark theme: make the color lighter (brighter)
        target_lightness = min(255, bg_lightness + min_lightness_diff)
    else:
        # Light theme: make the color darker
        target_lightness = max(0, bg_lightness - min_lightness_diff)

    # Create adjusted color maintaining hue and saturation
    h, s, _, a = color.getHsl()
    result = QColor()
    result.setHsl(h, s, target_lightness, a)
    return result
    
def get_vibrant_highlight() -> QColor:
    """Get the highlight color, specifically boosted for dark themes.
    
    In dark themes, the default QPalette.Highlight can be too dull or dark.
    This boosts Saturation and Value to ensure the accent color pops.
    """
    color = palette_color(QPalette.Highlight)
    
    if is_dark_theme():
        h, s, v, a = color.getHsv()
        
        # Boost Saturation (make it less "muted")
        # Increase by 25% + 20 flat to ensure greyish accents get some color
        s = min(255, int(s * 1.50) + 20)
        
        # Boost Value/Brightness (make it less "dark")
        # Ensure a minimum brightness of 180 (out of 255) for visibility
        v = max(180, min(255, int(v * 1.50) + 30))
        
        result = QColor()
        result.setHsv(h, s, v, a)
        return result
        
    return color


# =============================================================================
# Utility Functions
# =============================================================================
def lighten_color(hex_color: str, amount: int) -> str:
    """Lighten a hex color by adjusting its HSV value."""
    try:
        color = QColor(hex_color)
        h, s, v, a = color.getHsv()
        color.setHsv(h, s, min(255, v + amount), a)
        return color.name()
    except Exception:
        return hex_color


def darken_color(hex_color: str, amount: int) -> str:
    """Darken a hex color by adjusting its HSV value."""
    try:
        color = QColor(hex_color)
        h, s, v, a = color.getHsv()
        color.setHsv(h, s, max(0, v - amount), a)
        return color.name()
    except Exception:
        return hex_color


def lighten_qcolor(color: QColor, amount: int) -> QColor:
    """Lighten a QColor by adjusting its HSV value."""
    h, s, v, a = color.getHsv()
    result = QColor()
    result.setHsv(h, s, min(255, v + amount), a)
    return result


def darken_qcolor(color: QColor, amount: int) -> QColor:
    """Darken a QColor by adjusting its HSV value."""
    h, s, v, a = color.getHsv()
    result = QColor()
    result.setHsv(h, s, max(0, v - amount), a)
    return result


def adjust_color(hex_color: str, amount: int) -> str:
    """Lighten in dark theme, darken in light theme."""
    if is_dark_theme():
        return lighten_color(hex_color, amount)
    return darken_color(hex_color, amount)


def adjust_qcolor(color: QColor, amount: int) -> QColor:
    """Lighten in dark theme, darken in light theme."""
    if is_dark_theme():
        return lighten_qcolor(color, amount)
    return darken_qcolor(color, amount)


def blend_colors(color1: QColor, color2: QColor, ratio: float = 0.5) -> QColor:
    """Blend two colors together. ratio=0 returns color1, ratio=1 returns color2."""
    r = int(color1.red() + (color2.red() - color1.red()) * ratio)
    g = int(color1.green() + (color2.green() - color1.green()) * ratio)
    b = int(color1.blue() + (color2.blue() - color1.blue()) * ratio)
    a = int(color1.alpha() + (color2.alpha() - color1.alpha()) * ratio)
    return QColor(r, g, b, a)


def get_mid_color() -> QColor:
    """Get a color between Button and Window backgrounds (for borders/separators)."""
    button_bg = palette_color(QPalette.Button)
    window_bg = palette_color(QPalette.Window)
    return blend_colors(button_bg, window_bg, 0.5)


def get_contrast_border() -> QColor:
    """Get a border color with good contrast against button backgrounds."""
    button_bg = palette_color(QPalette.Button)
    if is_dark_theme():
        return lighten_qcolor(button_bg, 30)
    return darken_qcolor(button_bg, 30)


# =============================================================================
# Metaclass for Dynamic Color Classes
# Allows accessing color methods as class attributes: WindowColors.BackgroundNormal
# =============================================================================
class _DynamicColorMeta(type):
    """Metaclass that redirects attribute access to getter methods."""

    def __getattribute__(cls, name):
        # First try to get from class dict directly (for methods, FontSize, etc.)
        try:
            value = super().__getattribute__(name)
            # If it's a _ColorProperty, call it
            if isinstance(value, _ColorProperty):
                return value.getter()
            return value
        except AttributeError:
            pass
        # Convert attribute name to getter method name
        getter_name = f"_get_{name.lower()}"
        if hasattr(cls, getter_name):
            return getattr(cls, getter_name)()
        raise AttributeError(f"'{cls.__name__}' has no attribute '{name}'")


class _ColorProperty:
    """Descriptor for lazy color evaluation at class level."""

    def __init__(self, getter):
        self.getter = getter

    def __get__(self, obj, objtype=None):
        return self.getter()


# =============================================================================
# [Colors:Window] - Main window and panel colors
# Maps to Krita's [Colors:Window] section
# =============================================================================
class WindowColors(metaclass=_DynamicColorMeta):
    @staticmethod
    def _get_backgroundnormal() -> str:
        """Window.BackgroundNormal - main panel background."""
        return palette_color_name(QPalette.Window)

    @staticmethod
    def _get_backgroundalternate() -> str:
        """Window.BackgroundAlternate - darker/lighter alternate background."""
        return palette_color_name(QPalette.AlternateBase)

    @staticmethod
    def _get_foregroundnormal() -> str:
        """Window.ForegroundNormal - main text color."""
        return palette_color_name(QPalette.WindowText)

    @staticmethod
    def _get_foregroundinactive() -> str:
        """Window.ForegroundInactive - disabled/inactive text."""
        return palette_color_name(QPalette.WindowText, QPalette.Disabled)

    @staticmethod
    def _get_foregroundlink() -> str:
        """Window.ForegroundLink - link text color."""
        return palette_color_name(QPalette.Link)


# =============================================================================
# [Colors:Button] - General button colors
# Maps to Krita's [Colors:Button] section
# =============================================================================
class ButtonColors(metaclass=_DynamicColorMeta):
    @staticmethod
    def _get_backgroundnormal() -> str:
        """Button.BackgroundNormal - standard button background."""
        return palette_color_name(QPalette.Button)

    @staticmethod
    def _get_backgroundhover() -> str:
        """Button background on hover - uses DecorationHover concept."""
        return adjust_color(palette_color_name(QPalette.Button), 20)

    @staticmethod
    def _get_backgroundpressed() -> str:
        """Button background when pressed."""
        base = palette_color_name(QPalette.Button)
        if is_dark_theme():
            return darken_color(base, 20)
        return lighten_color(base, 15)

    @staticmethod
    def _get_backgroundalt() -> str:
        """Alternative button background - slightly different from normal."""
        return adjust_color(palette_color_name(QPalette.Button), 8)

    @staticmethod
    def _get_foregroundnormal() -> str:
        """Button.ForegroundNormal - button text color."""
        return palette_color_name(QPalette.ButtonText)

    @staticmethod
    def _get_foregroundalt() -> str:
        """Alternative foreground - high contrast text."""
        return "#ffffff" if is_dark_theme() else "#000000"

    @staticmethod
    def _get_foregroundinactive() -> str:
        """Inactive button text color."""
        return palette_color_name(QPalette.ButtonText, QPalette.Disabled)

    @staticmethod
    def _get_bordernormal() -> str:
        """Normal border color - mid tone between elements."""
        return get_contrast_border().name()

    @staticmethod
    def _get_borderhover() -> str:
        """Hover border color - more prominent."""
        return adjust_color(get_contrast_border().name(), 25)

    @staticmethod
    def _get_borderpressed() -> str:
        """Pressed border color - subtle."""
        border = get_contrast_border().name()
        if is_dark_theme():
            return darken_color(border, 20)
        return lighten_color(border, 20)


# =============================================================================
# [Colors:DockerButton] - Docker panel button colors
# Uses Window midlight for slightly prominent buttons
# =============================================================================
class DockerButtonColors(metaclass=_DynamicColorMeta):
    FontSize = "10px"

    @staticmethod
    def _get_backgroundnormal() -> str:
        """Docker button background - slightly lighter than window."""
        return palette_color_name(QPalette.Mid)

    @staticmethod
    def _get_foregroundnormal() -> str:
        """Docker button text - contrasts with mid background."""
        if is_dark_theme():
            return palette_color_name(QPalette.BrightText)
        return palette_color_name(QPalette.WindowText)


# =============================================================================
# [Colors:PrimaryButton] - Primary action button colors
# Uses Selection/Highlight colors for emphasis
# =============================================================================
class PrimaryButtonColors(metaclass=_DynamicColorMeta):
    @staticmethod
    def _get_backgroundnormal() -> str:
        """Primary button background - uses vibrant highlight."""
        return get_vibrant_highlight().name()

    @staticmethod
    def _get_backgroundhover() -> str:
        """Primary button hover - lighter version of vibrant highlight."""
        # Must use get_vibrant_highlight as base, otherwise hover might look duller than normal
        return lighten_color(get_vibrant_highlight().name(), 15)

    @staticmethod
    def _get_backgroundpressed() -> str:
        """Primary button pressed - darker version of vibrant highlight."""
        return darken_color(get_vibrant_highlight().name(), 15)

    @staticmethod
    def _get_foregroundnormal() -> str:
        """Primary button text - uses highlighted text color."""
        # Usually we keep HighlightedText as is (often white/black), 
        # but you can check contrast here if needed.
        return palette_color_name(QPalette.HighlightedText)


# =============================================================================
# [Colors:Toggle] - Toggle button colors
# On state uses a green tint derived from highlight, Off uses button colors
# =============================================================================
class ToggleColors(metaclass=_DynamicColorMeta):
    @staticmethod
    def _get_onbackgroundnormal() -> str:
        """Toggle ON background - green tinted from highlight base."""
        # Use vibrant highlight for the base so the green tint isn't muddy in dark themes
        highlight = get_vibrant_highlight()
        green_tint = QColor(74, 124, 89)  # Muted green that works in both themes
        return blend_colors(highlight, green_tint, 0.7).name()

    @staticmethod
    def _get_onbackgroundhover() -> str:
        """Toggle ON hover - lighter green."""
        return lighten_color(ToggleColors.OnBackgroundNormal, 15)

    @staticmethod
    def _get_offbackgroundnormal() -> str:
        """Toggle OFF background - uses mid color."""
        return palette_color_name(QPalette.Mid)

    @staticmethod
    def _get_offbackgroundhover() -> str:
        """Toggle OFF hover - adjust mid color."""
        return adjust_color(palette_color_name(QPalette.Mid), 15)

    @staticmethod
    def _get_offforeground() -> str:
        """Toggle OFF text - inactive appearance."""
        return palette_color_name(QPalette.ButtonText, QPalette.Disabled)


# =============================================================================
# [Colors:Selection] - Selection and highlight colors
# Maps to Krita's [Colors:Selection] section
# =============================================================================
class SelectionColors(metaclass=_DynamicColorMeta):
    @staticmethod
    def _get_highlightborder() -> str:
        """Selection border color - uses vibrant highlight."""
        return get_vibrant_highlight().name()

    @staticmethod
    def _get_highlightqcolor() -> QColor:
        """Selection highlight as QColor."""
        return get_vibrant_highlight()

    @staticmethod
    def _get_drophighlightqcolor() -> QColor:
        """Drop target highlight - brighter version of highlight."""
        return lighten_qcolor(get_vibrant_highlight(), 20)

    @staticmethod
    def _get_hoveroverlayqcolor() -> QColor:
        """Semi-transparent hover overlay."""
        base = palette_color(QPalette.Shadow)
        base.setAlpha(70)
        return base


# =============================================================================
# [Colors:Input] - Input field colors
# Maps to Krita's [Colors:View] section (input fields use View colors)
# =============================================================================
class InputColors(metaclass=_DynamicColorMeta):
    @staticmethod
    def _get_backgroundnormal() -> str:
        """Input background - uses Base (view background)."""
        return palette_color_name(QPalette.Base)

    @staticmethod
    def _get_foregroundnormal() -> str:
        """Input text color - uses Text."""
        return palette_color_name(QPalette.Text)

    @staticmethod
    def _get_spinnerhover() -> str:
        """Spinner button hover color."""
        return adjust_color(palette_color_name(QPalette.Button), 15)


# =============================================================================
# [Colors:Grid] - Grid and container colors
# Uses View colors for content areas
# =============================================================================
class GridColors(metaclass=_DynamicColorMeta):
    @staticmethod
    def _get_namecolor() -> str:
        """Grid item name color - slightly muted text."""
        text = palette_color(QPalette.Text)
        window = palette_color(QPalette.Window)
        return blend_colors(text, window, 0.3).name()

    @staticmethod
    def _get_containerbackground() -> str:
        """Grid container background - uses Base."""
        return palette_color_name(QPalette.Base)

    @staticmethod
    def _get_namelabelbackground() -> str:
        """Name label background - same as container."""
        return palette_color_name(QPalette.Base)

    @staticmethod
    def _get_namelabelbackgroundhover() -> str:
        """Name label hover background - darker/lighter variant."""
        base = palette_color_name(QPalette.Base)
        if is_dark_theme():
            return darken_color(base, 20)
        return lighten_color(base, 20)

    @staticmethod
    def _get_namelabeltext() -> str:
        """Name label text color."""
        return palette_color_name(QPalette.Text)


# =============================================================================
# [Colors:Drag] - Drag and drop colors
# =============================================================================
class DragColors(metaclass=_DynamicColorMeta):
    @staticmethod
    def _get_pixmapbackgroundqcolor() -> QColor:
        """Drag pixmap background."""
        return palette_color(QPalette.Mid)

    @staticmethod
    def _get_pixmaptextqcolor() -> QColor:
        """Drag pixmap text color."""
        return palette_color(QPalette.BrightText)


# =============================================================================
# [Colors:Overlay] - Overlay and transparency colors
# =============================================================================
class OverlayColors(metaclass=_DynamicColorMeta):
    @staticmethod
    def _get_hoverrgba() -> str:
        """Semi-transparent hover overlay."""
        shadow = palette_color(QPalette.Shadow)
        return f"rgba({shadow.red()}, {shadow.green()}, {shadow.blue()}, 0.3)"

    @staticmethod
    def _get_pressedrgba() -> str:
        """Semi-transparent pressed overlay."""
        shadow = palette_color(QPalette.Shadow)
        return f"rgba({shadow.red()}, {shadow.green()}, {shadow.blue()}, 0.5)"


# =============================================================================
# [Colors:Separator] - Separator and divider colors
# =============================================================================
class SeparatorColors(metaclass=_DynamicColorMeta):
    @staticmethod
    def _get_backgroundnormal() -> str:
        """Separator color - between window and button backgrounds."""
        return get_mid_color().name()


# =============================================================================
# [Colors:Slider] - Slider control colors
# Ensures slider elements have at least 10% contrast with background
# =============================================================================
class SliderColors(metaclass=_DynamicColorMeta):
    @staticmethod
    def _get_groovebackground() -> str:
        """Slider groove background with guaranteed contrast."""
        groove_color = palette_color(QPalette.Mid)
        bg_color = palette_color(QPalette.Window)
        adjusted = ensure_contrast(groove_color, bg_color, min_contrast_percent=10)
        return adjusted.name()

    @staticmethod
    def _get_pagebackground() -> str:
        """Slider page (filled portion) background with guaranteed contrast."""
        page_color = palette_color(QPalette.Midlight)
        bg_color = palette_color(QPalette.Window)
        adjusted = ensure_contrast(page_color, bg_color, min_contrast_percent=10)
        return adjusted.name()

    @staticmethod
    def _get_handlebackground() -> str:
        """Slider handle color with guaranteed contrast."""
        if is_dark_theme():
            handle_color = palette_color(QPalette.Light)
        else:
            handle_color = palette_color(QPalette.Dark)
        bg_color = palette_color(QPalette.Window)
        adjusted = ensure_contrast(handle_color, bg_color, min_contrast_percent=10)
        return adjusted.name()


# =============================================================================
# Stylesheet Generator Functions
# =============================================================================
def docker_btn_style():
    """Generate stylesheet for docker buttons."""
    bg = DockerButtonColors.BackgroundNormal
    fg = DockerButtonColors.ForegroundNormal
    border = ButtonColors.BorderNormal
    border_hover = ButtonColors.BorderHover
    border_pressed = ButtonColors.BorderPressed

    return f"""
        QPushButton {{
            background-color: {bg};
            color: {fg};
            font-size: {DockerButtonColors.FontSize};
            border-radius: 6px;
            border: 1px solid {border};
            padding: 3px 6px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {adjust_color(bg, 15)};
            border: 1px solid {border_hover};
        }}
        QPushButton:pressed {{
            background-color: {darken_color(bg, 15)};
            border: 1px solid {border_pressed};
        }}
    """


def shortcut_btn_style():
    """Generate stylesheet for shortcut buttons from config."""
    config = get_common_config()
    color = config["color"]["shortcut_button_background_color"]
    font_color = config["color"]["shortcut_button_font_color"]
    font_size = config["font"]["shortcut_button_font_size"]
    return f"background-color: {color}; color: {font_color}; font-size: {font_size};"


# =============================================================================
# Legacy Compatibility - Module-level color getters
# These provide backward compatibility for code using the old constant names.
# They are now functions that return dynamic theme-aware colors.
# =============================================================================
def get_docker_button_bg():
    """Get docker button background color."""
    return DockerButtonColors.BackgroundNormal


def get_docker_button_text():
    """Get docker button text color."""
    return DockerButtonColors.ForegroundNormal


def get_grid_name_color():
    """Get grid name text color."""
    return GridColors.NameColor


def get_selection_highlight():
    """Get selection highlight border color."""
    return SelectionColors.HighlightBorder


def get_dark_bg():
    """Get dark/alternate background color."""
    return WindowColors.BackgroundAlternate


def get_panel_bg():
    """Get panel/window background color."""
    return WindowColors.BackgroundNormal


def get_border_color():
    """Get normal border color."""
    return ButtonColors.BorderNormal


def get_border_hover():
    """Get hover border color."""
    return ButtonColors.BorderHover


def get_border_pressed():
    """Get pressed border color."""
    return ButtonColors.BorderPressed


# Legacy constant aliases - these call the getter functions
# For backward compatibility with code using: from styles import DOCKER_BUTTON_BG
DOCKER_BUTTON_FONT_SIZE = DockerButtonColors.FontSize
