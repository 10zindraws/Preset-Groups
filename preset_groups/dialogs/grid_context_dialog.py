"""Context dialog for grid name right-click menu.

Provides rename and delete options for grids, appearing as a popup
near the cursor position.
"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QMouseEvent

from ..utils.styles import WindowColors, ButtonColors


def _get_grid_context_style():
    """Generate grid context dialog stylesheet using theme colors."""
    return f"""
        QDialog {{
            background-color: {WindowColors.BackgroundAlternate};
            border: 1px solid {ButtonColors.BorderNormal};
        }}
        QPushButton {{
            background-color: {ButtonColors.BackgroundAlt};
            color: {ButtonColors.ForegroundAlt};
            border: 1px solid {ButtonColors.BorderNormal};
            padding: 4px 8px;
            min-width: 100px;
        }}
        QPushButton:hover {{
            background-color: {ButtonColors.BackgroundHover};
            border: 1px solid {ButtonColors.BorderHover};
        }}
        QPushButton:pressed {{
            background-color: {ButtonColors.BackgroundPressed};
        }}
    """


class GridNameContextDialog(QDialog):
    """Dialog that appears on right-click of grid name with delete and rename options"""
    
    def __init__(self, parent, grid_info, rename_callback, delete_callback):
        super().__init__(parent)
        self.grid_info = grid_info
        self.rename_callback = rename_callback
        self.delete_callback = delete_callback
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup | Qt.WindowStaysOnTopHint)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        
        # Apply styling
        self.setStyleSheet(_get_grid_context_style())
        
        # Rename button
        rename_btn = QPushButton("Rename")
        rename_btn.clicked.connect(self.rename_grid)
        layout.addWidget(rename_btn)
        
        # Delete button
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self.delete_grid)
        layout.addWidget(delete_btn)
        
        self.setLayout(layout)
        self.adjustSize()
        
    def rename_grid(self):
        """Rename the grid and close dialog"""
        # Pass None if grid_info is None (indicates multiple grids selected)
        self.rename_callback(self.grid_info if self.grid_info else None)
        self.accept()
    
    def delete_grid(self):
        """Delete the grid and close dialog"""
        # Pass None if grid_info is None (indicates multiple grids selected)
        self.delete_callback(self.grid_info if self.grid_info else None)
        self.accept()
    
    def _is_click_outside_dialog(self, event):
        """Check if click is outside the dialog"""
        if not isinstance(event, QMouseEvent):
            return False
        return not self.rect().contains(event.pos())

    def event(self, event):
        """Handle events to close dialog when clicking outside"""
        if event.type() == QEvent.MouseButtonPress:
            if self._is_click_outside_dialog(event):
                self.reject()
                return True
        return super().event(event)
