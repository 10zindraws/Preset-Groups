"""Icon button factory functionality.

Provides mixin class for creating styled icon buttons used in the docker UI.
"""

from krita import Krita  # type: ignore
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen, QIcon

from ..utils.styles import docker_btn_style


class IconButtonFactoryMixin:
    """Mixin class providing icon button creation functionality for the docker widget."""
    
    def _apply_button_style(self, button, icon_name):
        """Apply appropriate style to button based on icon name"""
        if icon_name in ("addlayer", "folder", "settings-button", "deletelayer"):
            button.setStyleSheet(
                """
                QPushButton {
                    background-color: #474747;
                    border: none;
                    border-radius: 2px;
                }
                QPushButton:hover {
                    background-color: rgba(0, 0, 0, 0.3);
                }
            """
            )
        else:
            base_style = docker_btn_style()
            enhanced_style = base_style + """
                QPushButton {
                    background-color: #474747;
                    border: 1px solid #555;
                }
                QPushButton:hover {
                    background-color: rgba(0, 0, 0, 0.3);
                }
            """
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
        if icon_name == "addlayer":
            return max(8, base_icon_size - 7)
        if icon_name == "folder":
            return max(8, base_icon_size - 2)
        if icon_name == "deletelayer":
            return max(8, base_icon_size - 5)
        return base_icon_size

    def _create_addlayer_icon(self, scaled_pixmap, button_size):
        """Create composed icon for addlayer button with rectangle border"""
        composed = QPixmap(button_size, button_size)
        composed.fill(Qt.transparent)
        painter = QPainter(composed)
        painter.setRenderHint(QPainter.Antialiasing, True)

        target_rect = scaled_pixmap.rect()
        target_rect.moveCenter(composed.rect().center())
        target_rect.translate(2, 2)
        painter.drawPixmap(target_rect.topLeft(), scaled_pixmap)

        pen = QPen(QColor("#d2d2d2"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        margin = 6
        rect_size = button_size - 2 * margin - 1
        painter.drawRect(margin, margin, rect_size, rect_size)
        painter.end()

        return QIcon(composed)

    def _load_and_set_icon(self, button, icon_name, button_size, icon_size):
        """Load icon from Krita and set it on the button"""
        try:
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

            if icon_name == "addlayer":
                composed_icon = self._create_addlayer_icon(scaled_pixmap, button_size)
                button.setIcon(composed_icon)
                button.setIconSize(QSize(button_size, button_size))
            else:
                high_res_icon = QIcon(scaled_pixmap)
                button.setIcon(high_res_icon)
                button.setIconSize(QSize(icon_size, icon_size))
        except Exception as e:
            print(f"Error loading icon '{icon_name}': {e}")

    def create_icon_button(self, icon_name, callback):
        """Create an icon button with hover effects"""
        button = QPushButton()
        button.setText("")

        self._apply_button_style(button, icon_name)
        button_size = self._calculate_button_size()
        button.setFixedSize(QSize(button_size, button_size))

        icon_size = self._calculate_icon_size(icon_name, button_size)
        self._load_and_set_icon(button, icon_name, button_size, icon_size)

        button.clicked.connect(callback)
        return button
