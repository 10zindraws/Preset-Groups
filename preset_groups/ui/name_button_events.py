"""Name button event handlers.

Provides mixin class for handling mouse events on grid name buttons.
Note: Drag behavior for reordering grids is handled by DraggableGridRow.
"""

from PyQt5.QtWidgets import QPushButton, QApplication
from PyQt5.QtCore import Qt

from ..dialogs.grid_context_dialog import GridNameContextDialog


class NameButtonEventsMixin:
    """Mixin class providing name button event handling for the docker widget."""
    
    def _handle_name_button_right_click(self, event, name_button, grid_info):
        """Handle right-click on grid name button"""
        mods = QApplication.keyboardModifiers()
        if mods == Qt.ShiftModifier:
            self.select_grid_range(grid_info)
            self.show_grid_name_context_dialog(name_button, grid_info, event.globalPos())
        elif mods == Qt.ControlModifier:
            self.toggle_grid_selection(grid_info)
            self.show_grid_name_context_dialog(name_button, grid_info, event.globalPos())
        elif mods == Qt.NoModifier:
            self.show_grid_name_context_dialog(name_button, grid_info, event.globalPos())
        elif mods == Qt.AltModifier:
            self.rename_grid(grid_info)
        elif (mods & (Qt.ControlModifier | Qt.AltModifier | Qt.ShiftModifier)) == (Qt.ControlModifier | Qt.AltModifier | Qt.ShiftModifier):
            self.remove_grid(grid_info)

    def _create_name_button_mousePressEvent(self, name_button, grid_info):
        """Create mousePressEvent handler for name button.
        
        Note: Drag initiation is handled by the parent DraggableGridRow widget.
        """
        def handler(event):
            if event.button() == Qt.RightButton:
                self._handle_name_button_right_click(event, name_button, grid_info)
            elif event.button() == Qt.LeftButton:
                # Track click start for detecting clicks vs. drags
                name_button.click_pos = event.globalPos()
                # Let the event propagate to the parent DraggableGridRow for drag handling
            QPushButton.mousePressEvent(name_button, event)
        return handler

    def _create_name_button_mouseReleaseEvent(self, name_button, grid_info):
        """Create mouseReleaseEvent handler for name button"""
        def handler(event):
            if event.button() == Qt.LeftButton:
                # Only handle click if it wasn't a drag
                click_pos = getattr(name_button, 'click_pos', None)
                if click_pos:
                    drag_distance = (event.globalPos() - click_pos).manhattanLength()
                    # If this was a click (not a drag), handle selection
                    if drag_distance < QApplication.startDragDistance():
                        mods = QApplication.keyboardModifiers()
                        if mods == Qt.ShiftModifier:
                            self.select_grid_range(grid_info)
                        elif mods == Qt.ControlModifier:
                            self.toggle_grid_selection(grid_info)
                        else:
                            self.select_single_grid(grid_info)
                name_button.click_pos = None
            QPushButton.mouseReleaseEvent(name_button, event)
        return handler

    def _create_name_button_mouseDoubleClickEvent(self, name_button, grid_info):
        """Create mouseDoubleClickEvent handler for name button"""
        def handler(event):
            if event.button() == Qt.LeftButton:
                self.start_inline_grid_rename(grid_info)
            QPushButton.mouseDoubleClickEvent(name_button, event)
        return handler

    def _setup_name_button_events(self, name_button, grid_info):
        """Setup all event handlers for the grid name button.
        
        Note: mouseMoveEvent is not overridden - drag handling is done by
        the parent DraggableGridRow widget.
        """
        name_button.mousePressEvent = self._create_name_button_mousePressEvent(name_button, grid_info)
        name_button.mouseReleaseEvent = self._create_name_button_mouseReleaseEvent(name_button, grid_info)
        name_button.mouseDoubleClickEvent = self._create_name_button_mouseDoubleClickEvent(name_button, grid_info)

    def show_grid_name_context_dialog(self, name_widget, grid_info, global_pos):
        """Show context dialog for grid name on right-click"""
        if grid_info in self.selected_grids and len(self.selected_grids) > 1:
            target_grid = None
        else:
            target_grid = grid_info
        dialog = GridNameContextDialog(
            self, 
            target_grid, 
            self.rename_grid, 
            self.remove_grid
        )
        dialog.move(global_pos)
        dialog.exec_()
