"""Duplicate brush warning dialog.

Displays a warning when user tries to add a brush that already exists
in the target grid.
"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt


class DuplicateBrushDialog(QDialog):
    """Dialog shown when user attempts to add a duplicate brush to a grid."""
    
    def __init__(self, grid_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Duplicate Brush")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._setup_ui(grid_name)
    
    def _setup_ui(self, grid_name):
        """Setup the dialog UI elements."""
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Warning message
        message = QLabel(f"You already have this brush in {grid_name}!")
        message.setAlignment(Qt.AlignCenter)
        message.setWordWrap(True)
        message.setStyleSheet("""
            QLabel {
                color: #d2d2d2;
                font-size: 12px;
                padding: 10px;
            }
        """)
        layout.addWidget(message)
        
        # Ok button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_button = QPushButton("Ok")
        ok_button.setFixedWidth(80)
        ok_button.clicked.connect(self.accept)
        ok_button.setDefault(True)
        ok_button.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                color: #d2d2d2;
                border: 1px solid #5a5a5a;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
        """)
        button_layout.addWidget(ok_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # Apply dialog styling
        self.setStyleSheet("""
            QDialog {
                background-color: #474747;
            }
        """)
        
        self.setLayout(layout)
        self.setFixedSize(300, 120)
    
    def keyPressEvent(self, event):
        """Handle key press events - close on Escape."""
        if event.key() == Qt.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)
