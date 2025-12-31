"""Thumbnail management functionality.

Provides mixin class for monitoring brush preset thumbnails and refreshing 
UI when thumbnails are updated.

SIMPLIFIED DESIGN:
- Event-driven detection: monitors Brush Editor dialog open/close state
- Brush Editor close: refreshes only the currently selected preset thumbnail
- Startup: refreshes ALL thumbnails unconditionally
- Signal-driven refresh on preset save
- No hash comparison needed - always refresh directly
"""

from krita import Krita  # type: ignore
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QDialog, QWidget

# Brush Editor detection patterns - comprehensive list for Krita 4.x and 5.x
# Searches class names, object names, and window titles
_BRUSH_EDITOR_PATTERNS = [
    # Exact matches from Krita 5.x (discovered via debug)
    "kispopupbuttonframe",          # Object name of Brush Editor popup
    "brush editor",                 # Window title (exact match)
    # Class name patterns (Krita internal)
    "kispaintoppreseteditor",       # KisPaintOpPresetEditor
    "kispaintoppresetseditor",      # KisPaintOpPresetsEditor  
    "kispreseteditor",              # KisPresetEditor
    "kispaintopsettings",           # KisPaintOpSettings dialogs
    "kispaintoppreset",             # Any preset-related dialog
    "kispaintoppopup",              # Preset popup
    "paintop",                      # Generic paintop pattern
    # Object name / title patterns
    "brusheditor",
    "preset editor",
    "edit brush",
    "brush settings",
    "scratchpad",                   # Scratchpad is part of brush editor
]
# PERFORMANCE: Increased interval significantly to reduce stuttering during drawing
# The brush editor is typically open for extended periods, so checking every 750ms is sufficient
_BRUSH_EDITOR_CHECK_INTERVAL = 750  # ms - check brush editor state (was 300ms, increased to reduce overhead)
_REFRESH_DELAY = 200  # ms - delay after brush editor close before refresh


class ThumbnailManagerMixin:
    """Mixin class providing thumbnail management functionality for the docker widget."""
    
    def _init_brush_editor_monitor(self):
        """Initialize the Brush Editor visibility monitor.
        
        Uses a presence-based detection approach: counts potential brush editor
        widgets each cycle. When count drops from >0 to 0, editor was closed.
        Timer is started/stopped by visibility-aware mechanism in preset_groups.py.
        """
        self._brush_editor_widget_count = 0
        self._brush_editor_check_timer = QTimer()
        self._brush_editor_check_timer.timeout.connect(self._check_brush_editor_state)
        # Don't start yet - will be started by _start_timers() when docker becomes visible
    
    def _count_brush_editor_widgets(self):
        """Count the number of visible brush editor related widgets.
        
        Returns the count of widgets that appear to be brush editor dialogs.
        PERFORMANCE OPTIMIZED: Early exit once we find at least one.
        """
        try:
            from PyQt5.QtWidgets import QApplication
            
            # Check all top-level widgets (dialogs, popups, windows)
            for widget in QApplication.topLevelWidgets():
                if widget.isVisible() and self._is_brush_editor_widget(widget):
                    return 1  # Early exit - we only care if count is 0 or >0
            
        except Exception:
            pass
        
        return 0
    
    def _is_brush_editor_widget(self, widget):
        """Check if a widget is the Brush Editor based on class name and title.
        
        Uses pattern matching against known Krita class names.
        PERFORMANCE: Avoids expensive findChildren traversal.
        """
        if not widget or not widget.isVisible():
            return False
        
        try:
            # Get identifiers to check (all lowercase for matching)
            class_name = widget.__class__.__name__.lower()
            obj_name = (widget.objectName() or "").lower()
            window_title = ""
            if hasattr(widget, 'windowTitle'):
                window_title = (widget.windowTitle() or "").lower()
            
            # Build combined string for easier matching
            combined = f"{class_name} {obj_name} {window_title}"
            
            # Check against known patterns
            for pattern in _BRUSH_EDITOR_PATTERNS:
                if pattern in combined:
                    return True
            
            return False
        except Exception:
            return False
    
    def _check_brush_editor_state(self):
        """Periodically check Brush Editor presence.
        
        Uses widget counting approach: when count transitions from >0 to 0,
        the brush editor was closed and we refresh the current preset thumbnail.
        
        PERFORMANCE: Skip expensive widget scanning if docker isn't visible.
        """
        # Skip if docker isn't visible - no need to track brush editor state
        if hasattr(self, '_is_docker_visible') and not self._is_docker_visible():
            return
        
        current_count = self._count_brush_editor_widgets()
        
        # Detect transition: had editor widgets -> now have none (closed)
        if self._brush_editor_widget_count > 0 and current_count == 0:
            # Brush Editor was just closed - refresh current preset thumbnail
            self._on_brush_editor_closed()
        
        self._brush_editor_widget_count = current_count
    
    def _on_brush_editor_closed(self):
        """Called when Brush Editor is closed.
        
        Refreshes only the currently selected preset's thumbnail since
        that's the one most likely to have been edited.
        """
        # Small delay to allow Krita to finalize any changes
        QTimer.singleShot(_REFRESH_DELAY, self._refresh_current_preset_thumbnail)
    
    def _refresh_current_preset_thumbnail(self):
        """Refresh only the currently selected preset's thumbnail.
        
        This is efficient since typically only the active preset is modified
        when using the Brush Editor.
        """
        if not self.grids:
            return
        
        # Get the currently selected preset from Krita
        current_preset = self._get_current_preset()
        if not current_preset:
            return
        
        preset_name = current_preset.name()
        
        # Check if this preset exists in any of our grids
        preset_in_grids = any(
            preset.name() == preset_name
            for grid_info in self.grids
            for preset in grid_info.get("brush_presets", [])
        )
        
        if not preset_in_grids:
            return
        
        # Refresh the preset directly (no hash comparison needed)
        fresh_preset = self._get_fresh_preset(preset_name)
        if fresh_preset:
            self._update_all_buttons_for_preset(preset_name, fresh_preset)
            self.save_grids_data()
    
    def _perform_startup_thumbnail_refresh(self):
        """Refresh all thumbnails on Krita startup.
        
        Unconditionally refreshes ALL preset thumbnails to ensure
        they are up-to-date with any external changes.
        """
        # Delay slightly to ensure Krita resources are fully loaded
        QTimer.singleShot(1000, self._refresh_all_thumbnails)
    
    def _refresh_all_thumbnails(self):
        """Refresh thumbnails for all presets in all grids."""
        if not self.grids:
            return
        
        # Collect ALL unique preset names across all grids
        seen_names = set()
        presets_to_refresh = []
        for grid_info in self.grids:
            for preset in grid_info.get("brush_presets", []):
                name = preset.name()
                if name not in seen_names:
                    seen_names.add(name)
                    presets_to_refresh.append(name)
        
        if not presets_to_refresh:
            return
        
        # Refresh ALL presets unconditionally
        any_updated = False
        for preset_name in presets_to_refresh:
            fresh_preset = self._get_fresh_preset(preset_name)
            if fresh_preset:
                self._update_all_buttons_for_preset(preset_name, fresh_preset)
                any_updated = True
        
        if any_updated:
            self.save_grids_data()
    
    def _get_fresh_preset(self, preset_name):
        """Force-fetch a fresh preset from Krita's resource system.
        
        Bypasses caching to ensure we get the latest thumbnail data.
        """
        # Invalidate our cache first
        if hasattr(self, '_invalidate_preset_cache'):
            self._invalidate_preset_cache()
        
        # Direct fetch from Krita API
        fresh_dict = Krita.instance().resources("preset")
        return fresh_dict.get(preset_name)

    def _try_connect_save_action(self, app):
        """Try to connect to a brush preset save action."""
        action_names = [
            "saveBrushPresetButton",
            "save_brush_preset",
            "SaveBrushPreset",
            "saveBrushPreset",
            "brushpreset_save",
        ]
        
        for action_name in action_names:
            save_action = app.action(action_name)
            if save_action:
                save_action.triggered.connect(self.on_brush_preset_saved)
                return True
        return False

    def setup_brush_preset_save_monitor(self):
        """Setup monitoring for brush preset save button."""
        def on_window_created():
            app = Krita.instance()
            if app.activeWindow():
                self._try_connect_save_action(app)
                self._try_connect_additional_save_signals(app)

        app = Krita.instance()
        if app.activeWindow():
            QTimer.singleShot(500, on_window_created)
        else:
            app.notifier().windowCreated.connect(
                lambda: QTimer.singleShot(500, on_window_created)
            )
    
    def _try_connect_additional_save_signals(self, app):
        """Try to connect to additional brush modification signals."""
        # Additional action names that might trigger brush changes
        action_names = [
            "overwrite_brush_preset",
            "reload_brush_preset", 
            "edit_brush_preset",
            "brusheditor_save",
            "brushpreset_save",
            "save_brush",
            "saveBrush",
        ]
        
        for action_name in action_names:
            action = app.action(action_name)
            if action:
                try:
                    action.triggered.connect(self.on_brush_preset_saved)
                except Exception:
                    pass

    def _get_current_preset(self):
        """Get the current brush preset from active view.
        
        Uses cached view reference when available.
        """
        # Try cached view first
        if hasattr(self, '_cached_view') and self._cached_view is not None:
            try:
                return self._cached_view.currentBrushPreset()
            except (RuntimeError, AttributeError):
                pass
        
        # Fallback
        app = Krita.instance()
        if not app.activeWindow() or not app.activeWindow().activeView():
            return None
        return app.activeWindow().activeView().currentBrushPreset()

    def on_brush_preset_saved(self):
        """Handle brush preset save event.
        
        Refreshes the currently selected preset's thumbnail after a short delay
        to allow Krita to finalize the save.
        """
        current_preset = self._get_current_preset()
        if current_preset:
            preset_name = current_preset.name()
            # Delay to allow Krita to complete the save operation
            QTimer.singleShot(_REFRESH_DELAY, lambda: self._refresh_preset_by_name(preset_name))
    
    def _refresh_preset_by_name(self, preset_name):
        """Refresh a specific preset's thumbnail by name."""
        fresh_preset = self._get_fresh_preset(preset_name)
        if fresh_preset:
            self._update_all_buttons_for_preset(preset_name, fresh_preset)
            self.save_grids_data()
    
    def _update_all_buttons_for_preset(self, preset_name, preset):
        """Update all buttons displaying this preset with the new thumbnail."""
        buttons_updated = False
        
        for grid_info in self.grids:
            presets = grid_info.get("brush_presets", [])
            for idx, p in enumerate(presets):
                if p.name() == preset_name:
                    # Update the preset reference
                    grid_info["brush_presets"][idx] = preset
                    
                    # Find and update the button
                    button = self._find_button_for_preset_in_grid(grid_info, idx)
                    if button:
                        if hasattr(button, 'force_refresh_thumbnail'):
                            button.force_refresh_thumbnail(preset)
                        elif hasattr(button, 'update_preset'):
                            button.update_preset(preset)
                        buttons_updated = True
        
        return buttons_updated

    def get_button_positions(self, preset_name):
        """Get positions of all buttons with the given preset name."""
        return [
            (grid_info, idx)
            for grid_info in self.grids
            for idx, preset in enumerate(grid_info["brush_presets"])
            if preset.name() == preset_name
        ]
    
    def _find_button_for_preset_in_grid(self, grid_info, preset_index):
        """Find the button widget for a preset at a given index in a grid.
        
        Returns the button widget or None if not found.
        """
        layout = grid_info.get("layout")
        if not layout:
            return None
        
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item:
                widget = item.widget()
                if widget and hasattr(widget, 'grid_index') and widget.grid_index == preset_index + 1:
                    return widget
        return None

    def refresh_buttons_for_preset(self, preset_name):
        """Update buttons for a preset with refreshed thumbnail.
        
        PERFORMANCE: Uses in-place button update instead of full grid rebuild
        when possible.
        """
        button_positions = self.get_button_positions(preset_name)
        if not button_positions:
            return
        
        # Get updated preset
        if hasattr(self, '_get_preset_dict'):
            preset_dict = self._get_preset_dict()
        else:
            preset_dict = Krita.instance().resources("preset")
        
        updated_preset = preset_dict.get(preset_name)
        if not updated_preset:
            return
        
        # Update buttons in-place when possible (avoids full grid rebuild)
        grids_needing_full_update = set()
        
        for grid_info, preset_index in button_positions:
            # Update the preset reference in the data
            if 0 <= preset_index < len(grid_info["brush_presets"]):
                grid_info["brush_presets"][preset_index] = updated_preset
            
            # Try to update button in-place
            button = self._find_button_for_preset_in_grid(grid_info, preset_index)
            if button and hasattr(button, 'update_preset'):
                # In-place update - much faster than rebuilding grid
                button.update_preset(updated_preset)
            else:
                # Button not found or doesn't support update - need full rebuild
                grids_needing_full_update.add(id(grid_info))
        
        # Only rebuild grids that need it
        for grid_info, _ in button_positions:
            if id(grid_info) in grids_needing_full_update:
                self.update_grid(grid_info)
                grids_needing_full_update.discard(id(grid_info))  # Don't rebuild twice
        
        self.save_grids_data()

    def refresh_buttons_for_preset_by_reference(self, preset):
        """Refresh all buttons that display the same preset (by name matching).
        
        Used when the current brush changes to update any buttons showing that preset.
        """
        if not preset:
            return

        preset_name = preset.name()
        
        # Find and update all buttons showing this preset
        buttons_updated = False
        for grid_info in self.grids:
            for i, p in enumerate(grid_info.get("brush_presets", [])):
                if p.name() == preset_name:
                    # Update preset reference
                    grid_info["brush_presets"][i] = preset
                    
                    # Try in-place button update
                    button = self._find_button_for_preset_in_grid(grid_info, i)
                    if button and hasattr(button, 'update_preset'):
                        button.update_preset(preset)
                        buttons_updated = True

        if buttons_updated:
            self.save_grids_data()
