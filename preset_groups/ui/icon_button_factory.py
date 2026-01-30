"""Icon button factory functionality.

Provides mixin class for creating styled icon buttons used in the docker UI.
"""

import os
from krita import Krita  # type: ignore
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen, QIcon

from ..utils.styles import docker_btn_style, WindowColors, ButtonColors, OverlayColors, tint_icon_for_theme

# Path to custom icons in the ui folder
_UI_DIR = os.path.dirname(__file__)


def _get_icon_button_style():
    """Generate icon button stylesheet using theme colors."""
    return f"""
        QPushButton {{
            background-color: {WindowColors.BackgroundNormal};
            border: none;
            border-radius: 2px;
        }}
        QPushButton:hover {{
            background-color: {OverlayColors.HoverRgba};
        }}
    """


def _get_enhanced_button_style():
    """Generate enhanced button stylesheet using theme colors."""
    return f"""
        QPushButton {{
            background-color: {WindowColors.BackgroundNormal};
            border: 1px solid {ButtonColors.BorderNormal};
        }}
        QPushButton:hover {{
            background-color: {OverlayColors.HoverRgba};
        }}
    """


class IconButtonFactoryMixin:
    """Mixin class providing icon button creation functionality for the docker widget."""

    def _apply_button_style(self, button, icon_name):
        """Apply appropriate style to button based on icon name"""
        if icon_name in ("addbrushicon", "folder", "settings", "deletelayer"):
            button.setStyleSheet(_get_icon_button_style())
        else:
            base_style = docker_btn_style()
            enhanced_style = base_style + _get_enhanced_button_style()
            button.setStyleSheet(enhanced_style)

    def _calculate_button_size(self):
        """Calculate button size based on reference button height"""
        temp_button = QPushButton("Test")
        temp_button.setStyleSheet(docker_btn_style())
        temp_button.adjustSize()
        button_height = temp_button.sizeHint().height()
        temp_button.deleteLater()
        return button_height + 7

    def _calculate_icon_size(self, icon_name, button_size):
        """Calculate icon size with special adjustments for specific icons"""
        base_icon_size = button_size - 4
        if icon_name == "addbrushicon":
            return max(8, base_icon_size - 8)  # Smaller icon for Add Brush button
        if icon_name == "folder":
            return max(8, base_icon_size - 2)
        if icon_name == "deletelayer":
            return max(8, base_icon_size - 5)
        return base_icon_size

    def _load_custom_icon(self, icon_name):
        """Load a custom PNG icon from the ui folder"""
        icon_path = os.path.join(_UI_DIR, f"{icon_name}.png")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                return pixmap
        return None

    def _load_and_set_icon(self, button, icon_name, button_size, icon_size):
        """Load icon from custom file or Krita and set it on the button.

        Icons are automatically tinted to match the theme's font color
        when using a light theme (background > 50% brightness).
        """
        try:
            # Try loading custom icon first
            custom_pixmap = self._load_custom_icon(icon_name)
            if custom_pixmap:
                scaled_pixmap = custom_pixmap.scaled(
                    icon_size,
                    icon_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                # Apply theme-based tinting
                tinted_pixmap = tint_icon_for_theme(scaled_pixmap)
                button.setIcon(QIcon(tinted_pixmap))
                button.setIconSize(QSize(icon_size, icon_size))
                return

            # Fall back to Krita's built-in icons
            app = Krita.instance()
            icon = app.icon(icon_name)
            if not icon or icon.isNull():
                return

            high_res_size = icon_size * 2
            pixmap = icon.pixmap(high_res_size, high_res_size)
            if pixmap.isNull():
                button.setIcon(icon)
                button.setIconSize(QSize(icon_size, icon_size))
                return

            scaled_pixmap = pixmap.scaled(
                icon_size,
                icon_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            # Apply theme-based tinting
            tinted_pixmap = tint_icon_for_theme(scaled_pixmap)
            button.setIcon(QIcon(tinted_pixmap))
            button.setIconSize(QSize(icon_size, icon_size))
        except Exception as e:
            print(f"Error loading icon '{icon_name}': {e}")

    def create_icon_button(self, icon_name, callback):
        """Create an icon button with hover effects"""
        button = QPushButton()
        button.setText("")
        # Store icon name for later refresh (e.g., on theme change)
        button.setProperty("icon_name", icon_name)

        self._apply_button_style(button, icon_name)
        button_size = self._calculate_button_size()
        button.setFixedSize(QSize(button_size, button_size))

        icon_size = self._calculate_icon_size(icon_name, button_size)
        self._load_and_set_icon(button, icon_name, button_size, icon_size)

        button.clicked.connect(callback)
        return button

    def refresh_icon_button(self, button):
        """Refresh an icon button's icon (e.g., for theme changes).

        Re-applies the icon with current theme tinting.
        """
        icon_name = button.property("icon_name")
        if not icon_name:
            return

        button_size = button.width()
        icon_size = self._calculate_icon_size(icon_name, button_size)
        self._load_and_set_icon(button, icon_name, button_size, icon_size)
