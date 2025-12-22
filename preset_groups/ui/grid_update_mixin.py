"""Grid update functionality.

Provides mixin class for updating grid contents and layout calculations.
"""

from ..utils.config_utils import (
    get_brush_icon_size,
    get_spacing_between_buttons,
    get_display_brush_names,
    get_brush_name_label_height,
)
from ..utils.data_manager import check_common_config
from ..widgets.draggable_button import DraggableBrushButton


class GridUpdateMixin:
    """Mixin class providing grid update functionality for the docker widget."""
    
    def get_dynamic_columns(self):
        """Calculate max_brush_per_row dynamically based on available docker width"""
        if hasattr(self, 'scroll_area') and self.scroll_area:
            available_widget = self.scroll_area.viewport()
        else:
            available_widget = self.main_widget if self.main_widget else self.widget()
        
        if not available_widget:
            max_brush = check_common_config().get("layout", {}).get("max_brush_per_row", 8)
            return int(max_brush)
        
        available_width = available_widget.width()
        if available_width <= 0:
            max_brush = check_common_config().get("layout", {}).get("max_brush_per_row", 8)
            return int(max_brush)
        
        button_size = get_brush_icon_size()
        spacing = get_spacing_between_buttons()
        
        margin_buffer = 4
        usable_width = available_width - margin_buffer
        
        if button_size + spacing <= 0:
            return 1
        
        max_columns = max(1, int((usable_width + spacing) / (button_size + spacing)))
        return max_columns
    
    def _store_selected_indices(self, layout):
        """Store indices of selected buttons before clearing"""
        selected_indices = set()
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if not item:
                continue
            btn = item.widget()
            if btn and btn in self.selected_buttons:
                selected_indices.add(i)
        return selected_indices

    def _clear_grid_buttons(self, layout):
        """Clear all buttons from the grid layout"""
        for i in reversed(range(layout.count())):
            widget = layout.itemAt(i).widget()
            if not widget:
                continue
            if widget in self.brush_buttons:
                self.brush_buttons.remove(widget)
            if widget in self.selected_buttons:
                self.selected_buttons.remove(widget)
            layout.removeWidget(widget)
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()

    def _clear_last_selected_if_in_grid(self, grid_info):
        """Clear last_selected_button if it was in this grid"""
        if not self.last_selected_button:
            return
        if not hasattr(self.last_selected_button, 'grid_info'):
            return
        if self.last_selected_button.grid_info == grid_info:
            self.last_selected_button = None

    def _calculate_max_name_lines_for_grid(self, presets):
        """Calculate the maximum number of lines needed for brush names in a grid.
        
        Args:
            presets: List of brush presets in the grid
            
        Returns:
            1 or 2 based on the longest name in the grid
        """
        if not get_display_brush_names() or not presets:
            return 0
        
        max_lines = 1
        icon_size = get_brush_icon_size()
        
        # Import here to get font size calculation
        from ..utils.config_utils import get_brush_name_font_size
        font_size = get_brush_name_font_size()
        
        # Calculate chars per line
        avg_char_width = font_size * 0.55
        chars_per_line = max(1, int((icon_size - 4) / avg_char_width))
        
        for preset in presets:
            name_length = len(preset.name())
            if name_length > chars_per_line:
                max_lines = 2
                break  # No need to check further
        
        return max_lines

    def _calculate_grid_height(self, preset_count, columns, name_label_height=0):
        """Calculate required height for grid based on preset count and name labels"""
        required_rows = (preset_count + columns - 1) // columns if preset_count > 0 else 1
        icon_size = get_brush_icon_size()
        button_height = icon_size + name_label_height
        spacing = get_spacing_between_buttons()
        return required_rows * button_height + (required_rows - 1) * spacing + 4

    def _is_preset_selected(self, preset):
        """Check if preset matches currently selected preset"""
        if self.current_selected_preset is None:
            return False
        return preset.name() == self.current_selected_preset.name()

    def _cache_preset_thumbnail(self, preset):
        """Cache thumbnail hash for preset"""
        preset_name = preset.name()
        thumbnail_hash = self.get_preset_thumbnail_hash(preset)
        if thumbnail_hash is not None:
            self.preset_thumbnail_cache[preset_name] = thumbnail_hash

    def _restore_button_selection(self, brush_button, index, selected_indices):
        """Restore selection state for button if it was previously selected"""
        if index not in selected_indices:
            return
        if brush_button in self.selected_buttons:
            return
        self.selected_buttons.append(brush_button)
        if not self.last_selected_button:
            self.last_selected_button = brush_button

    def _add_preset_button(self, preset, grid_info, layout, columns, index, name_label_height):
        """Add a single preset button to the grid"""
        row = index // columns
        col = index % columns
        brush_button = DraggableBrushButton(preset, grid_info, self)
        # Store the 1-based visual index for keyboard navigation
        brush_button.grid_index = index + 1
        
        # Set the name label height for consistency across the grid
        brush_button.set_name_label_height(name_label_height)
        
        self.brush_buttons.append(brush_button)
        layout.addWidget(brush_button, row, col)
        
        self._cache_preset_thumbnail(preset)
        is_selected = self._is_preset_selected(preset)
        brush_button.update_highlight(is_selected)
        
        return brush_button

    def update_grid(self, grid_info):
        """Update grid with current brush presets"""
        layout = grid_info["layout"]
        selected_indices = self._store_selected_indices(layout)
        self._clear_grid_buttons(layout)
        self._clear_last_selected_if_in_grid(grid_info)
        
        columns = self.get_dynamic_columns()
        presets = grid_info["brush_presets"]
        preset_count = len(presets)
        
        # Calculate consistent name label height for all buttons in this grid
        max_lines = self._calculate_max_name_lines_for_grid(presets)
        name_label_height = get_brush_name_label_height(max_lines) if max_lines > 0 else 0
        
        new_height = self._calculate_grid_height(preset_count, columns, name_label_height)
        grid_info["widget"].setFixedHeight(new_height)
        
        for index, preset in enumerate(presets):
            brush_button = self._add_preset_button(
                preset, grid_info, layout, columns, index, name_label_height
            )
            self._restore_button_selection(brush_button, index, selected_indices)
        
        self.update_selection_highlights()
        self.update_grid_visibility(grid_info)

    def get_button_by_grid_index(self, grid_info, index):
        """Get a brush button by its 1-based grid index within a specific grid."""
        layout = grid_info.get("layout")
        if not layout:
            return None
        
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item:
                btn = item.widget()
                if btn and hasattr(btn, 'grid_index') and btn.grid_index == index:
                    return btn
        return None

    def get_button_count_in_grid(self, grid_info):
        """Get total count of brush buttons in a grid."""
        layout = grid_info.get("layout")
        if not layout:
            return 0
        
        count = 0
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item:
                btn = item.widget()
                if btn and hasattr(btn, 'grid_index'):
                    count += 1
        return count

    def get_current_button_index_in_active_grid(self):
        """Get the grid_index of the currently selected button in the active grid.
        Returns None if no button is selected in the active grid."""
        if not self.active_grid:
            return None
        
        # Check if current_selected_button is in active grid
        if (self.current_selected_button and 
            hasattr(self.current_selected_button, 'grid_info') and 
            self.current_selected_button.grid_info == self.active_grid and
            hasattr(self.current_selected_button, 'grid_index')):
            return self.current_selected_button.grid_index
        
        # Fallback: find button matching current_selected_preset in active grid
        if self.current_selected_preset:
            layout = self.active_grid.get("layout")
            if layout:
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if item:
                        btn = item.widget()
                        if (btn and hasattr(btn, 'preset') and 
                            btn.preset.name() == self.current_selected_preset.name() and
                            hasattr(btn, 'grid_index')):
                            return btn.grid_index
        return None
