"""Brush management functionality.

Provides mixin class for handling brush-related operations like adding
brushes, updating brush size, and tracking the current brush preset.

PERFORMANCE OPTIMIZATIONS:
- Cached active view reference (refreshed via signals)
- Debounced I/O operations
- Visibility-aware polling
"""

from krita import Krita  # type: ignore
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIntValidator

from ..utils.data_manager import check_common_config, save_common_config
from ..utils.config_utils import (
    reload_config,
    get_brush_icon_size,
    get_display_brush_names,
    get_brush_name_font_size,
    get_brush_name_label_height,
    get_spacing_between_buttons,
)


# Brush size constraints
_MIN_BRUSH_SIZE = 1
_DEFAULT_MAX_SIZE = 1000
_ABSOLUTE_MAX_SIZE = 10000

# Debounce delay for icon size slider (milliseconds)
_ICON_SIZE_DEBOUNCE_MS = 50


class BrushManagerMixin:
    """Mixin class providing brush management functionality for the docker widget."""
    
    def _get_active_view(self):
        """Get the active view from Krita, using cache when available.
        
        Uses cached reference when possible, falling back to direct lookup.
        The cache is updated via Krita signals (see _on_view_changed).
        """
        # Try cached view first (faster)
        if hasattr(self, '_cached_view') and self._cached_view is not None:
            try:
                # Verify cached view is still valid
                if self._cached_view.document() is not None or True:
                    return self._cached_view
            except (RuntimeError, AttributeError):
                # Cached view was deleted, clear it
                self._cached_view = None
        
        # Fallback to direct lookup
        app = Krita.instance()
        if app.activeWindow() and app.activeWindow().activeView():
            view = app.activeWindow().activeView()
            # Update cache
            if hasattr(self, '_cached_view'):
                self._cached_view = view
            return view
        return None

    def get_max_brush_size_from_config(self):
        """Get max brush size from config, defaulting to 1000."""
        config = check_common_config()
        return int(config.get("brush_slider", {}).get("max_brush_size", _DEFAULT_MAX_SIZE))

    def update_max_brush_size(self, new_max):
        """Update max brush size for slider and textbox."""
        new_max = max(100, min(_ABSOLUTE_MAX_SIZE, int(new_max)))
        self.max_brush_size = new_max
        
        if hasattr(self, 'brush_size_slider'):
            self.brush_size_slider.setMaximum(new_max)
        
        if hasattr(self, 'brush_size_number'):
            self.brush_size_number.setValidator(
                QIntValidator(_MIN_BRUSH_SIZE, new_max, self.brush_size_number)
            )

    def _update_grids_for_icon_size(self):
        """Update all grids after icon size change."""
        for grid_info in self.grids:
            self.update_grid(grid_info)

    def _resize_grids_live(self, icon_size):
        """Resize all existing buttons in-place for live slider feedback.
        
        This method resizes buttons AND re-layouts the grid when column count changes.
        """
        for grid_info in self.grids:
            layout = grid_info.get("layout")
            widget = grid_info.get("widget")
            presets = grid_info.get("brush_presets", [])
            
            if not layout or not widget:
                continue
            
            # Calculate new column count based on the new icon size
            new_columns = self._calculate_columns_for_size(icon_size)
            
            # Calculate name label height for this grid
            name_label_height = self._calculate_name_label_height_for_size(icon_size, presets)
            
            # Collect all buttons in order
            buttons = []
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget():
                    buttons.append(item.widget())
            
            # Remove all buttons from layout (but don't delete them)
            for button in buttons:
                layout.removeWidget(button)
            
            # Resize and re-add buttons in new grid positions
            for index, button in enumerate(buttons):
                if hasattr(button, 'resize_to_icon_size'):
                    button.resize_to_icon_size(icon_size, name_label_height)
                
                row = index // new_columns
                col = index % new_columns
                layout.addWidget(button, row, col)
            
            # Update grid container height
            preset_count = len(presets)
            button_height = icon_size + name_label_height
            spacing = get_spacing_between_buttons()
            required_rows = (preset_count + new_columns - 1) // new_columns if preset_count > 0 else 1
            new_height = required_rows * button_height + (required_rows - 1) * spacing + 4
            widget.setFixedHeight(new_height)
            widget.setMinimumHeight(new_height)

    def _calculate_columns_for_size(self, icon_size):
        """Calculate column count for a specific icon size."""
        if hasattr(self, 'scroll_area') and self.scroll_area:
            available_widget = self.scroll_area.viewport()
        else:
            available_widget = self.main_widget if hasattr(self, 'main_widget') and self.main_widget else None
        
        if not available_widget:
            return 8  # Default fallback
        
        available_width = available_widget.width()
        if available_width <= 0:
            return 8
        
        spacing = get_spacing_between_buttons()
        margin_buffer = 4
        usable_width = available_width - margin_buffer
        
        if icon_size + spacing <= 0:
            return 1
        
        return max(1, int((usable_width + spacing) / (icon_size + spacing)))

    def _calculate_name_label_height_for_size(self, icon_size, presets):
        """Calculate name label height for a specific icon size."""
        if not get_display_brush_names() or not presets:
            return 0
        
        # Calculate font size for this icon size
        reference_size = 65
        base_font = 9
        min_font = 7
        max_font = 12
        scale_factor = icon_size / reference_size
        font_size = max(min_font, min(max_font, int(base_font * scale_factor)))
        
        # Calculate chars per line
        avg_char_width = font_size * 0.55
        chars_per_line = max(1, int((icon_size - 4) / avg_char_width))
        
        # Determine max lines needed
        max_lines = 1
        for preset in presets:
            if len(preset.name()) > chars_per_line:
                max_lines = 2
                break
        
        # Calculate height
        line_height = int(font_size * 1.3)
        padding = 4
        return (line_height * max_lines) + padding

    def on_brush_size_changed(self, value):
        """Handle brush icon size slider change with live resize."""
        # Update config cache immediately for live feedback
        config = check_common_config()
        config["layout"]["brush_icon_size"] = value
        
        # Update the module-level cache directly for immediate effect
        from ..utils import config_utils
        if config_utils._config_cache:
            config_utils._config_cache["layout"]["brush_icon_size"] = value
        
        # Resize existing buttons in-place (fast, no recreation)
        self._resize_grids_live(value)
        
        # Debounce disk save to avoid I/O spam
        self._pending_icon_size = value
        if not hasattr(self, '_icon_size_save_timer'):
            self._icon_size_save_timer = QTimer()
            self._icon_size_save_timer.setSingleShot(True)
            self._icon_size_save_timer.timeout.connect(self._save_icon_size_to_disk)
        
        self._icon_size_save_timer.stop()
        self._icon_size_save_timer.start(_ICON_SIZE_DEBOUNCE_MS)

    def _save_icon_size_to_disk(self):
        """Save the icon size to disk after debounce delay."""
        if not hasattr(self, '_pending_icon_size'):
            return
        
        value = self._pending_icon_size
        config = check_common_config()
        config["layout"]["brush_icon_size"] = value
        save_common_config(config)
        reload_config()

    def on_brush_size_slider_changed(self, value):
        """Handle top row brush size slider change (live)."""
        self.brush_size_number.setText(f"{int(value)} px")
        self._apply_brush_size(value)

    def on_brush_size_number_changed(self):
        """Handle brush size number textbox change."""
        text = self.brush_size_number.text().strip().replace("px", "").strip()
        try:
            val = float(text)
        except ValueError:
            val = float(self.brush_size_slider.value())
        
        val = max(self.brush_size_slider.minimum(), min(self.brush_size_slider.maximum(), val))
        self.brush_size_number.setText(f"{int(val)} px")
        
        self.brush_size_slider.blockSignals(True)
        self.brush_size_slider.setValue(int(val))
        self.brush_size_slider.blockSignals(False)
        
        self._apply_brush_size(val)

    def _apply_brush_size(self, size):
        """Apply brush size to current view."""
        view = self._get_active_view()
        if view and hasattr(view, "setBrushSize"):
            view.setBrushSize(float(size))

    def _auto_expand_max_size(self, current_size):
        """Expand max brush size if current size exceeds it.
        
        Uses debouncing to avoid frequent config file writes.
        """
        if current_size <= self.max_brush_size:
            return
        
        new_max = min(_ABSOLUTE_MAX_SIZE, max(100, int(current_size)))
        if new_max <= self.max_brush_size:
            return
        
        # Debounce config file writes to avoid I/O overhead
        self._pending_max_size = new_max
        self.update_max_brush_size(new_max)  # Update UI immediately
        
        if not hasattr(self, '_max_size_save_timer'):
            from PyQt5.QtCore import QTimer
            self._max_size_save_timer = QTimer()
            self._max_size_save_timer.setSingleShot(True)
            self._max_size_save_timer.timeout.connect(self._save_max_size_to_disk)
        
        self._max_size_save_timer.stop()
        self._max_size_save_timer.start(500)  # Debounce for 500ms
    
    def _save_max_size_to_disk(self):
        """Save the max brush size to disk after debounce delay."""
        if not hasattr(self, '_pending_max_size'):
            return
        
        new_max = self._pending_max_size
        config = check_common_config()
        if "brush_slider" not in config:
            config["brush_slider"] = {}
        config["brush_slider"]["max_brush_size"] = new_max
        save_common_config(config)

    def poll_brush_size(self):
        """Poll the current brush size from Krita and update top controls.
        
        Includes visibility check to avoid unnecessary work when docker is hidden.
        """
        # Skip polling if docker isn't visible (performance optimization for Linux)
        if hasattr(self, '_is_docker_visible') and not self._is_docker_visible():
            return
        
        view = self._get_active_view()
        if not view:
            return
        
        size = view.brushSize()
        self._auto_expand_max_size(size)
        
        # Update slider (clamp for display)
        slider_val = max(self.brush_size_slider.minimum(), 
                         min(self.brush_size_slider.maximum(), size))
        self.brush_size_slider.blockSignals(True)
        self.brush_size_slider.setValue(int(slider_val))
        self.brush_size_slider.blockSignals(False)
        
        # Show actual size in textbox
        self.brush_size_number.setText(f"{int(size)} px")

    def _find_brush_in_any_grid(self, preset_name):
        """Find which grid contains a brush preset by name.
        
        Searches all grids in the plugin for a brush with the given name.
        A brush preset can only exist once across all grids.
        
        Args:
            preset_name: The name of the brush preset to find
            
        Returns:
            The grid_info dict containing the brush, or None if not found
        """
        for grid_info in self.grids:
            for existing_preset in grid_info.get("brush_presets", []):
                if existing_preset.name() == preset_name:
                    return grid_info
        return None

    def add_current_brush(self):
        """Add current brush preset to the active grid.
        
        Shows a warning dialog if the brush already exists anywhere in the plugin.
        Duplicate brushes are not allowed - each brush preset can only exist once
        across all grids.
        """
        view = self._get_active_view()
        if not view or not self.active_grid:
            return
        
        current_preset = view.currentBrushPreset()
        if not current_preset:
            return
        
        # Check for duplicate across ALL grids (plugin-wide)
        existing_grid = self._find_brush_in_any_grid(current_preset.name())
        if existing_grid is not None:
            from ..dialogs.duplicate_brush_dialog import DuplicateBrushDialog
            grid_name = existing_grid.get("name", "another grid")
            dialog = DuplicateBrushDialog(grid_name, self)
            dialog.exec_()
            return
        
        self.active_grid["brush_presets"].append(current_preset)
        self.update_grid(self.active_grid)
        self.save_grids_data()

    def initialize_current_brush(self):
        """Initialize the current brush preset from Krita on startup."""
        view = self._get_active_view()
        if not view:
            return
        
        current_preset = view.currentBrushPreset()
        if current_preset:
            self.current_selected_preset = current_preset
            self.current_selected_button = None
            self.update_all_button_highlights()

    def check_brush_change(self):
        """Check if the current brush preset has changed and update highlights.
        
        Optimized to skip expensive thumbnail refresh unless brush actually changed.
        """
        view = self._get_active_view()
        if not view:
            return
        
        current_preset = view.currentBrushPreset()
        if not current_preset:
            return
        
        current_name = current_preset.name()
        
        # Quick comparison - avoid string comparison if same object
        if self.current_selected_preset is not None:
            if self.current_selected_preset is current_preset:
                return  # Same object, no change
            if self.current_selected_preset.name() == current_name:
                return  # Same brush by name, no change
        
        # Brush has actually changed
        self.current_selected_preset = current_preset
        self.current_selected_button = None
        self.update_all_button_highlights()
        
        # Defer the expensive thumbnail refresh to avoid blocking
        # Use a debounced timer to handle rapid brush switching
        if not hasattr(self, '_brush_thumbnail_refresh_timer'):
            from PyQt5.QtCore import QTimer
            self._brush_thumbnail_refresh_timer = QTimer()
            self._brush_thumbnail_refresh_timer.setSingleShot(True)
            self._brush_thumbnail_refresh_timer.timeout.connect(self._do_deferred_thumbnail_refresh)
        
        self._pending_thumbnail_refresh_preset = current_preset
        self._brush_thumbnail_refresh_timer.stop()
        self._brush_thumbnail_refresh_timer.start(100)  # 100ms debounce

    def _do_deferred_thumbnail_refresh(self):
        """Perform the deferred thumbnail refresh."""
        if hasattr(self, '_pending_thumbnail_refresh_preset') and self._pending_thumbnail_refresh_preset:
            self.refresh_buttons_for_preset_by_reference(self._pending_thumbnail_refresh_preset)
            self._pending_thumbnail_refresh_preset = None

    def select_brush_preset(self, preset, source_button=None):
        """Set the selected brush preset as current."""
        view = self._get_active_view()
        if view:
            view.setCurrentBrushPreset(preset)
        
        self.current_selected_preset = preset
        self.current_selected_button = source_button
        
        # Set the source button's grid as active when a brush is selected
        if source_button is not None and hasattr(source_button, 'grid_info'):
            self.set_active_grid(source_button.grid_info)
        
        self.update_all_button_highlights()

    def update_all_button_highlights(self):
        """Update highlight state for all brush buttons."""
        for button in self.brush_buttons:
            if not hasattr(button, 'preset'):
                continue
            
            # Use specific button matching if available, else name-based
            if self.current_selected_button is not None:
                is_selected = button is self.current_selected_button
            else:
                is_selected = (
                    self.current_selected_preset is not None
                    and button.preset.name() == self.current_selected_preset.name()
                )
            button.update_highlight(is_selected)
