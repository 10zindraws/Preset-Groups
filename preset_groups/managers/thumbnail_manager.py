"""Thumbnail management functionality.

Provides mixin class for caching and monitoring brush preset thumbnails,
detecting changes, and refreshing UI when thumbnails are updated.
"""

from krita import Krita  # type: ignore
from PyQt5.QtCore import QTimer

# Constants for thumbnail sampling
_MAX_SAMPLE_POINTS = 50
_SAMPLE_GRID_DIVISIONS = 5


class ThumbnailManagerMixin:
    """Mixin class providing thumbnail management functionality for the docker widget."""
    
    def _sample_image_pixels(self, image):
        """Sample pixels from image for hash generation."""
        size = image.size()
        sample_data = []
        step_y = max(1, size.height() // _SAMPLE_GRID_DIVISIONS)
        step_x = max(1, size.width() // _SAMPLE_GRID_DIVISIONS)
        
        for y in range(0, size.height(), step_y):
            for x in range(0, size.width(), step_x):
                sample_data.append(image.pixel(x, y))
                if len(sample_data) >= _MAX_SAMPLE_POINTS:
                    return sample_data
        return sample_data

    def get_preset_thumbnail_hash(self, preset):
        """Generate a hash of the preset thumbnail for change detection."""
        if not preset or not preset.image():
            return None
        
        image = preset.image()
        if image.isNull():
            return None
        
        try:
            sample_data = self._sample_image_pixels(image)
            size = image.size()
            return hash((size.width(), size.height(), tuple(sample_data)))
        except Exception:
            return None

    def cache_all_preset_thumbnails(self):
        """Cache thumbnail hashes for all presets in all grids."""
        for grid_info in self.grids:
            for preset in grid_info.get("brush_presets", []):
                thumbnail_hash = self.get_preset_thumbnail_hash(preset)
                if thumbnail_hash is not None:
                    self.preset_thumbnail_cache[preset.name()] = thumbnail_hash

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

        app = Krita.instance()
        if app.activeWindow():
            QTimer.singleShot(500, on_window_created)
        else:
            app.notifier().windowCreated.connect(
                lambda: QTimer.singleShot(500, on_window_created)
            )

    def _get_current_preset(self):
        """Get the current brush preset from active view."""
        app = Krita.instance()
        if not app.activeWindow() or not app.activeWindow().activeView():
            return None
        return app.activeWindow().activeView().currentBrushPreset()

    def on_brush_preset_saved(self):
        """Handle brush preset save event."""
        current_preset = self._get_current_preset()
        if current_preset:
            preset_name = current_preset.name()
            QTimer.singleShot(200, lambda: self.check_and_refresh_preset(preset_name))

    def _has_thumbnail_changed(self, preset_name):
        """Check if a preset's thumbnail has changed from cached version."""
        preset_dict = Krita.instance().resources("preset")
        current_preset = preset_dict.get(preset_name)
        
        if not current_preset:
            return False, None
        
        new_hash = self.get_preset_thumbnail_hash(current_preset)
        old_hash = self.preset_thumbnail_cache.get(preset_name)
        
        return (new_hash is not None and new_hash != old_hash), new_hash

    def check_and_refresh_preset(self, preset_name):
        """Check if preset thumbnail changed and refresh if needed."""
        changed, _ = self._has_thumbnail_changed(preset_name)
        if changed:
            self.refresh_buttons_for_preset(preset_name)

    def check_thumbnail_changes(self):
        """Periodically check for thumbnail changes (fallback method).
        
        Uses a set comprehension for efficient deduplication and early exit
        on first change to avoid redundant processing.
        """
        # Collect unique preset names across all grids
        presets_to_check = {
            preset.name()
            for grid_info in self.grids
            for preset in grid_info.get("brush_presets", [])
        }
        
        # Check each preset, updating on first change found
        for preset_name in presets_to_check:
            changed, _ = self._has_thumbnail_changed(preset_name)
            if changed:
                self.refresh_buttons_for_preset(preset_name)

    def get_button_positions(self, preset_name):
        """Get positions of all buttons with the given preset name."""
        return [
            (grid_info, idx)
            for grid_info in self.grids
            for idx, preset in enumerate(grid_info["brush_presets"])
            if preset.name() == preset_name
        ]

    def refresh_buttons_for_preset(self, preset_name):
        """Update buttons for a preset with refreshed thumbnail."""
        button_positions = self.get_button_positions(preset_name)
        if not button_positions:
            return
        
        preset_dict = Krita.instance().resources("preset")
        updated_preset = preset_dict.get(preset_name)
        if not updated_preset:
            return
        
        # Group by grid for batch updates
        grids_to_refresh = {}
        for grid_info, preset_index in button_positions:
            grid_id = id(grid_info)
            if grid_id not in grids_to_refresh:
                grids_to_refresh[grid_id] = {"grid_info": grid_info, "indices": []}
            grids_to_refresh[grid_id]["indices"].append(preset_index)
        
        # Update presets and refresh grids
        for grid_data in grids_to_refresh.values():
            grid_info = grid_data["grid_info"]
            for idx in grid_data["indices"]:
                if 0 <= idx < len(grid_info["brush_presets"]):
                    grid_info["brush_presets"][idx] = updated_preset
            self.update_grid(grid_info)
        
        # Update cache
        new_hash = self.get_preset_thumbnail_hash(updated_preset)
        if new_hash is not None:
            self.preset_thumbnail_cache[preset_name] = new_hash
        
        self.save_grids_data()

    def refresh_buttons_with_same_thumbnail(self, preset):
        """Refresh buttons that have the same thumbnail as the given preset."""
        if not preset:
            return

        target_hash = self.get_preset_thumbnail_hash(preset)
        if target_hash is None:
            return

        grids_to_update = []
        for grid_info in self.grids:
            indices_to_refresh = [
                i for i, p in enumerate(grid_info["brush_presets"])
                if self.get_preset_thumbnail_hash(p) == target_hash
            ]
            
            for i in indices_to_refresh:
                grid_info["brush_presets"][i] = preset
            
            if indices_to_refresh:
                grids_to_update.append(grid_info)

        for grid_info in grids_to_update:
            self.update_grid(grid_info)

        if grids_to_update:
            self.save_grids_data()
