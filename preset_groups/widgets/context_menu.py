"""Context menu widgets for brush buttons.

Provides popup menus for single and multi-selection brush actions.
"""

from PyQt5.QtWidgets import QFrame, QPushButton, QVBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor

from ..utils.styles import WindowColors, ButtonColors


def _get_context_menu_style():
    """Generate the context menu stylesheet using theme colors."""
    return f"""
        QFrame {{
            background-color: {WindowColors.BackgroundAlternate};
            border: 1px solid {ButtonColors.BorderNormal};
            border-radius: 4px;
        }}
        QPushButton {{
            background-color: {ButtonColors.BackgroundAlt};
            color: {WindowColors.ForegroundLink};
            border: none;
            border-radius: 2px;
            padding: 8px 16px;
            text-align: left;
            min-width: 100px;
        }}
        QPushButton:hover {{ background-color: {ButtonColors.BackgroundHover}; }}
        QPushButton:pressed {{ background-color: {ButtonColors.BackgroundPressed}; }}
    """


class _BaseContextMenu(QFrame):
    """Base class for context menus with common setup."""
    
    def __init__(self, on_remove):
        super().__init__()
        self._on_remove = on_remove
        self._setup_ui()
        
    def _setup_ui(self):
        """Configure the menu appearance and buttons."""
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setStyleSheet(_get_context_menu_style())
        
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(1)
        
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._handle_remove)
        layout.addWidget(remove_btn)
        
        self.setLayout(layout)
        self.adjustSize()
    
    def _handle_remove(self):
        """Execute remove callback and close menu."""
        self._on_remove()
        self.close()
    
    def show_at(self, position):
        """Display the menu at the given position."""
        self.move(position)
        self.show()
        self.raise_()
    
    def show_at_cursor(self):
        """Display the menu at the current cursor position."""
        self.show_at(QCursor.pos())


class BrushContextMenu(_BaseContextMenu):
    """Context menu for single brush button actions."""
    pass


class MultiSelectContextMenu(_BaseContextMenu):
    """Context menu for multiple selected brush buttons."""
    pass
