"""Selection management functionality.

Provides mixin class for handling selection of brush buttons and grids,
including multi-selection and range selection.
"""

from PyQt5.QtWidgets import QWidget, QScrollArea
from PyQt5.QtCore import Qt

from ..utils.styles import (
    SelectionColors, GridColors, WindowColors, ButtonColors, OverlayColors
)
from ..utils.config_utils import get_group_name_font_size, get_group_name_padding


def _get_button_states():
    """Generate common hover/pressed states using theme colors."""
    return f"""
        QPushButton:hover {{ background-color: {OverlayColors.HoverRgba}; }}
        QPushButton:pressed {{ background-color: {OverlayColors.PressedRgba}; }}
    """


def _make_name_button_style(bg_color, text_color, border="none"):
    """Generate a name button stylesheet with dynamic font size and padding."""
    font_size = get_group_name_font_size()
    padding = get_group_name_padding()
    return f"""
        QPushButton {{
            background-color: {bg_color};
            color: {text_color};
            font-weight: bold;
            font-size: {font_size}px;
            border: {border};
            border-radius: 2px;
            text-align: left;
            padding: {padding}px 4px;
        }}
    """ + _get_button_states()


def _make_collapse_button_style(bg_color):
    """Generate a collapse button stylesheet."""
    return f"""
        QPushButton {{
            background-color: {bg_color};
            border: none;
            border-radius: 2px;
        }}
    """ + _get_button_states()


def get_selected_name_button_style():
    """Generate the selected name button style with dynamic font/padding."""
    return _make_name_button_style(
        WindowColors.BackgroundAlternate,
        SelectionColors.HighlightBorder,
        f"2px solid {SelectionColors.HighlightBorder}"
    )


def get_active_name_button_style():
    """Generate the active name button style with dynamic font/padding."""
    return _make_name_button_style(
        WindowColors.BackgroundAlternate,
        SelectionColors.HighlightBorder
    )


def get_inactive_name_button_style():
    """Generate the inactive name button style with dynamic font/padding."""
    return _make_name_button_style(
        GridColors.ContainerBackground,
        GridColors.NameColor
    )


def _get_selected_collapse_button_style():
    """Generate selected collapse button style."""
    return _make_collapse_button_style(WindowColors.BackgroundAlternate)


def _get_selected_widget_style():
    """Generate selected widget style."""
    return f"""
        QWidget {{
            border: 2px solid {SelectionColors.HighlightBorder};
            background-color: {WindowColors.BackgroundNormal};
        }}
    """


def _get_active_collapse_button_style():
    """Generate active collapse button style."""
    return _make_collapse_button_style(WindowColors.BackgroundAlternate)


def _get_inactive_collapse_button_style():
    """Generate inactive collapse button style."""
    return _make_collapse_button_style(GridColors.ContainerBackground)


class SelectionManagerMixin:
    """Mixin class providing selection management functionality for the docker widget."""
    
    def clear_selection(self):
        """Clear selection of both brush buttons and grids"""
        self.selected_buttons = []
        self.last_selected_button = None
        self.selected_grids = []
        self.last_selected_grid = None
        self.update_selection_highlights()
        self.update_grid_selection_highlights()
        # Clear the active grid highlight as well when clicking outside
        self._clear_active_grid_highlight()
    
    def _clear_active_grid_highlight(self):
        """Clear the active grid highlight state.
        
        If only one grid exists, keep it as the active grid instead of clearing.
        """
        # When only one grid exists, it should always remain active
        if len(self.grids) == 1:
            if not self.active_grid or self.active_grid != self.grids[0]:
                self.set_active_grid(self.grids[0])
            return
        
        if self.active_grid:
            # Reset the active grid's highlight to inactive style
            self.active_grid["is_active"] = False
            self.update_grid_style(self.active_grid)
        self.active_grid = None
    
    def update_selection_highlights(self):
        """Update highlight state for all buttons based on selection"""
        for button in self.brush_buttons:
            if hasattr(button, 'preset'):
                is_selected = button in self.selected_buttons
                button.update_selection_highlight(is_selected)
    
    def get_buttons_in_range(self, button1, button2, grid_info):
        """Get all buttons between button1 and button2 in the grid"""
        if button1 == button2:
            return [button1]
        
        layout = grid_info.get("layout")
        if not layout:
            return []
        
        buttons = []
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item:
                btn = item.widget()
                if btn and hasattr(btn, 'preset'):
                    buttons.append(btn)
        
        try:
            idx1 = buttons.index(button1)
            idx2 = buttons.index(button2)
        except ValueError:
            return []
        
        start_idx = min(idx1, idx2)
        end_idx = max(idx1, idx2)
        return buttons[start_idx:end_idx + 1]
    
    def select_button(self, button, add_to_selection=False, range_selection=False):
        """Select a button with optional modifiers"""
        if not hasattr(button, 'preset'):
            return
        
        if range_selection and self.last_selected_button:
            grid_info = button.grid_info
            buttons_to_select = self.get_buttons_in_range(self.last_selected_button, button, grid_info)
            self.selected_buttons = list(set(self.selected_buttons + buttons_to_select))
            self.last_selected_button = button
        elif add_to_selection:
            if button in self.selected_buttons:
                self.selected_buttons.remove(button)
                if self.last_selected_button == button:
                    self.last_selected_button = None
            else:
                self.selected_buttons.append(button)
                self.last_selected_button = button
        else:
            self.selected_buttons = [button]
            self.last_selected_button = button
        
        self.update_selection_highlights()
    
    def remove_selected_brushes(self):
        """Remove all selected brushes from their grids"""
        if not self.selected_buttons:
            return
        
        grids_to_update = {}
        for button in self.selected_buttons:
            if hasattr(button, 'grid_info') and hasattr(button, 'preset'):
                grid_info = button.grid_info
                grid_name = grid_info.get("name", id(grid_info))
                if grid_name not in grids_to_update:
                    grids_to_update[grid_name] = {"grid_info": grid_info, "presets": []}
                grids_to_update[grid_name]["presets"].append(button.preset)
        
        for grid_data in grids_to_update.values():
            grid_info = grid_data["grid_info"]
            presets_to_remove = grid_data["presets"]
            for preset in presets_to_remove:
                for i, p in enumerate(grid_info["brush_presets"]):
                    if p.name() == preset.name():
                        grid_info["brush_presets"].pop(i)
                        break
            self.update_grid(grid_info)
        
        self.clear_selection()
        self.save_grids_data()
    
    def handle_delete_button_click(self):
        """Handle click on the delete button (deletelayer icon)"""
        if self.selected_buttons:
            self.remove_selected_brushes()
        elif self.selected_grids:
            self.remove_grid()
    
    def main_widget_click_handler(self, event):
        """Handle clicks on main widget to deselect"""
        from PyQt5.QtCore import Qt
        if event.button() == Qt.LeftButton or event.button() == Qt.RightButton:
            widget_under_mouse = self.main_widget.childAt(event.pos())
            if not widget_under_mouse or not hasattr(widget_under_mouse, "preset"):
                self.clear_selection()
        QWidget.mousePressEvent(self.main_widget, event)
    
    def scroll_area_click_handler(self, event):
        """Handle clicks on scroll area to deselect"""
        from PyQt5.QtCore import Qt
        if event.button() == Qt.LeftButton or event.button() == Qt.RightButton:
            if event.pos().x() < self.scroll_area.viewport().width():
                self.clear_selection()
        QScrollArea.mousePressEvent(self.scroll_area, event)

    # Grid selection methods
    def set_active_grid(self, grid_info):
        """Set a grid as active"""
        for grid in self.grids:
            grid["is_active"] = False
            self.update_grid_style(grid)
        grid_info["is_active"] = True
        self.active_grid = grid_info
        self.update_grid_style(grid_info)
        self.update_grid_selection_highlights()
    
    def select_single_grid(self, grid_info):
        """Select a single grid, deselecting all others"""
        self.selected_grids = [grid_info]
        self.last_selected_grid = grid_info
        self.set_active_grid(grid_info)
        self.update_grid_selection_highlights()
    
    def toggle_grid_selection(self, grid_info):
        """Toggle selection of a grid"""
        if grid_info in self.selected_grids:
            self.selected_grids.remove(grid_info)
            if self.last_selected_grid == grid_info:
                self.last_selected_grid = None
        else:
            self.selected_grids.append(grid_info)
            self.last_selected_grid = grid_info
        self.update_grid_selection_highlights()
    
    def select_grid_range(self, grid_info):
        """Select a range of grids from last_selected_grid to grid_info"""
        if not self.last_selected_grid or self.last_selected_grid == grid_info:
            self.selected_grids = [grid_info]
            self.last_selected_grid = grid_info
        else:
            try:
                start_idx = self.grids.index(self.last_selected_grid)
                end_idx = self.grids.index(grid_info)
                
                if start_idx < end_idx:
                    grids_to_select = self.grids[start_idx:end_idx + 1]
                else:
                    grids_to_select = self.grids[end_idx:start_idx + 1]
                
                for grid in grids_to_select:
                    if grid not in self.selected_grids:
                        self.selected_grids.append(grid)
                
                self.last_selected_grid = grid_info
            except ValueError:
                self.selected_grids = [grid_info]
                self.last_selected_grid = grid_info
        
        self.update_grid_selection_highlights()
    
    def _apply_grid_widget_styles(self, grid_info, name_style, collapse_style, widget_style):
        """Apply styles to grid widget components."""
        name_button = grid_info.get("name_button") or grid_info.get("name_label")
        collapse_button = grid_info.get("collapse_button")
        
        if name_button:
            name_button.setStyleSheet(name_style)
        if collapse_button:
            collapse_button.setStyleSheet(collapse_style)
        grid_info["widget"].setStyleSheet(widget_style)
    
    def update_grid_selection_highlights(self):
        """Update visual highlights for selected grids."""
        for grid in self.grids:
            if grid in self.selected_grids:
                self._apply_grid_widget_styles(
                    grid,
                    get_selected_name_button_style(),
                    _get_selected_collapse_button_style(),
                    _get_selected_widget_style()
                )
            else:
                self.update_grid_style(grid)

    def update_grid_style(self, grid_info):
        """Update visual style based on active status and selection."""
        if grid_info in self.selected_grids:
            return  # Already handled by update_grid_selection_highlights

        is_active = grid_info["is_active"]

        widget_style = f"""
            QWidget {{
                border: 1px solid {ButtonColors.BorderNormal};
                background-color: {WindowColors.BackgroundNormal};
            }}
        """ if is_active else f"""
            QWidget {{
                border: 1px solid {ButtonColors.BorderNormal};
                background-color: {WindowColors.BackgroundNormal};
            }}
        """

        if is_active:
            self._apply_grid_widget_styles(
                grid_info,
                get_active_name_button_style(),
                _get_active_collapse_button_style(),
                widget_style
            )
        else:
            self._apply_grid_widget_styles(
                grid_info,
                get_inactive_name_button_style(),
                _get_inactive_collapse_button_style(),
                widget_style
            )
