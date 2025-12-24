"""Thumbnail management functionality.

Provides mixin class for caching and monitoring brush preset thumbnails,
detecting changes, and refreshing UI when thumbnails are updated.

HIGH-FIDELITY CHANGE DETECTION:
- Full pixel data hashing for subtle change detection
- Aggressive refresh after preset save
- Forced API re-fetch to bypass stale data
- Multiple retry attempts with escalating delays
- Immediate update propagation
"""

from krita import Krita  # type: ignore
from PyQt5.QtCore import QTimer, QByteArray, QBuffer, QIODevice
import hashlib

# Constants for high-fidelity thumbnail change detection
# Use dense sampling for detecting subtle pixel changes
_HASH_GRID_SIZE = 32  # 32x32 grid = 1024 sample points for accuracy
_MAX_PRESETS_PER_CYCLE = 50  # Check more presets per cycle for responsiveness

# Retry configuration for preset save detection
_SAVE_RETRY_DELAYS = [50, 150, 300, 500, 800, 1200]  # ms delays for retries
_FORCED_REFRESH_DELAY = 100  # ms delay for forced refresh after change


class ThumbnailManagerMixin:
    """Mixin class providing thumbnail management functionality for the docker widget."""
    
    def _compute_full_image_hash(self, image):
        """Compute a high-fidelity hash of the entire image using dense sampling.
        
        Uses a grid-based approach that captures subtle pixel changes
        across the entire image area with uniform distribution.
        """
        if image.isNull():
            return None
        
        width = image.width()
        height = image.height()
        
        if width <= 0 or height <= 0:
            return None
        
        # Use MD5 for fast, reliable hashing of pixel data
        hasher = hashlib.md5()
        
        # Add image dimensions
        hasher.update(f"{width}x{height}".encode())
        
        # Dense grid sampling - 32x32 = 1024 sample points
        # This catches subtle changes anywhere in the image
        step_x = max(1, width // _HASH_GRID_SIZE)
        step_y = max(1, height // _HASH_GRID_SIZE)
        
        for y in range(0, height, step_y):
            for x in range(0, width, step_x):
                pixel = image.pixel(x, y)
                # Pack all 4 channels (ARGB) into the hash
                hasher.update(pixel.to_bytes(4, 'big'))
        
        # Also sample the edges and corners for complete coverage
        edge_points = [
            (0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1),
            (width // 2, 0), (width // 2, height - 1),
            (0, height // 2), (width - 1, height // 2),
        ]
        for x, y in edge_points:
            if 0 <= x < width and 0 <= y < height:
                hasher.update(image.pixel(x, y).to_bytes(4, 'big'))
        
        return hasher.hexdigest()
    
    def _get_raw_image_bytes(self, image):
        """Get raw image bytes for exact comparison when needed."""
        try:
            buffer = QByteArray()
            qbuffer = QBuffer(buffer)
            qbuffer.open(QIODevice.WriteOnly)
            image.save(qbuffer, "PNG")
            qbuffer.close()
            return buffer.data()
        except Exception:
            return None

    def get_preset_thumbnail_hash(self, preset):
        """Generate a high-fidelity hash of the preset thumbnail for change detection.
        
        Uses dense pixel sampling to detect even subtle changes in brush thumbnails.
        """
        if not preset or not preset.image():
            return None
        
        image = preset.image()
        if image.isNull():
            return None
        
        try:
            return self._compute_full_image_hash(image)
        except Exception:
            return None
    
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
        """Handle brush preset save event with aggressive retry mechanism.
        
        Uses multiple retry attempts with escalating delays to ensure
        we catch the thumbnail update even if Krita is slow to process it.
        """
        current_preset = self._get_current_preset()
        if current_preset:
            preset_name = current_preset.name()
            # Store original hash for comparison
            original_hash = self.preset_thumbnail_cache.get(preset_name)
            self._schedule_aggressive_refresh(preset_name, original_hash, 0)
    
    def _schedule_aggressive_refresh(self, preset_name, original_hash, retry_index):
        """Schedule aggressive refresh attempts with escalating delays.
        
        Args:
            preset_name: Name of the preset to check
            original_hash: The hash before the save action
            retry_index: Current retry attempt index
        """
        if retry_index >= len(_SAVE_RETRY_DELAYS):
            # All retries exhausted - do one final forced refresh
            QTimer.singleShot(100, lambda: self._force_refresh_preset(preset_name))
            return
        
        delay = _SAVE_RETRY_DELAYS[retry_index]
        QTimer.singleShot(
            delay,
            lambda: self._check_and_maybe_retry(
                preset_name, original_hash, retry_index
            )
        )
    
    def _check_and_maybe_retry(self, preset_name, original_hash, retry_index):
        """Check if thumbnail changed, retry if not."""
        # Force fresh fetch from Krita
        fresh_preset = self._get_fresh_preset(preset_name)
        if not fresh_preset:
            return
        
        new_hash = self.get_preset_thumbnail_hash(fresh_preset)
        
        # Check if the hash actually changed
        if new_hash is not None and new_hash != original_hash:
            # Thumbnail changed! Update everything
            self.preset_thumbnail_cache[preset_name] = new_hash
            self._update_all_buttons_for_preset(preset_name, fresh_preset)
        else:
            # Hash unchanged, schedule another retry
            self._schedule_aggressive_refresh(
                preset_name, original_hash, retry_index + 1
            )
    
    def _force_refresh_preset(self, preset_name):
        """Force refresh a preset's thumbnail even if hash check fails.
        
        Used as a fallback when retry mechanism doesn't detect a change
        but user expects the thumbnail to update.
        """
        fresh_preset = self._get_fresh_preset(preset_name)
        if fresh_preset:
            new_hash = self.get_preset_thumbnail_hash(fresh_preset)
            if new_hash is not None:
                self.preset_thumbnail_cache[preset_name] = new_hash
            self._update_all_buttons_for_preset(preset_name, fresh_preset)
    
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
        
        if buttons_updated:
            self.save_grids_data()

    def _has_thumbnail_changed(self, preset_name, force_fresh=False):
        """Check if a preset's thumbnail has changed from cached version.
        
        Args:
            preset_name: Name of the preset to check
            force_fresh: If True, bypass cache and fetch fresh from Krita API
        
        Returns:
            Tuple of (has_changed: bool, new_hash: str or None)
        """
        # If not in cache, we haven't seen it yet - cache it now
        old_hash = self.preset_thumbnail_cache.get(preset_name)
        
        # Get the preset - force fresh fetch if requested
        if force_fresh:
            current_preset = self._get_fresh_preset(preset_name)
        else:
            if hasattr(self, '_get_preset_dict'):
                preset_dict = self._get_preset_dict()
            else:
                preset_dict = Krita.instance().resources("preset")
            current_preset = preset_dict.get(preset_name)
        
        if not current_preset:
            return False, None
        
        new_hash = self.get_preset_thumbnail_hash(current_preset)
        
        # If no old hash, cache it and report no change
        if old_hash is None:
            if new_hash is not None:
                self.preset_thumbnail_cache[preset_name] = new_hash
            return False, new_hash
        
        return (new_hash is not None and new_hash != old_hash), new_hash

    def check_and_refresh_preset(self, preset_name):
        """Check if preset thumbnail changed and refresh if needed."""
        changed, new_hash = self._has_thumbnail_changed(preset_name)
        if changed:
            # Update cache immediately
            if new_hash is not None:
                self.preset_thumbnail_cache[preset_name] = new_hash
            self.refresh_buttons_for_preset(preset_name)

    def check_thumbnail_changes(self):
        """Periodically check for thumbnail changes with high-fidelity detection.
        
        Uses dense pixel sampling to detect even subtle changes in brush thumbnails.
        Checks all visible presets each cycle for immediate responsiveness.
        """
        # Skip if no grids
        if not self.grids:
            return
        
        # Collect unique preset names across all grids
        presets_to_check = []
        seen_names = set()
        for grid_info in self.grids:
            for preset in grid_info.get("brush_presets", []):
                name = preset.name()
                if name not in seen_names:
                    seen_names.add(name)
                    presets_to_check.append(name)
        
        if not presets_to_check:
            return
        
        # For large numbers of presets, rotate through them
        if len(presets_to_check) > _MAX_PRESETS_PER_CYCLE:
            if not hasattr(self, '_thumbnail_check_offset'):
                self._thumbnail_check_offset = 0
            
            start = self._thumbnail_check_offset
            presets_to_check = presets_to_check[start:start + _MAX_PRESETS_PER_CYCLE]
            self._thumbnail_check_offset = (start + _MAX_PRESETS_PER_CYCLE) % len(seen_names)
        
        # Check each preset with force_fresh to bypass stale cache
        for preset_name in presets_to_check:
            changed, new_hash = self._has_thumbnail_changed(preset_name, force_fresh=True)
            if changed:
                # Update cache immediately to prevent duplicate refresh
                if new_hash is not None:
                    self.preset_thumbnail_cache[preset_name] = new_hash
                # Use fresh preset for the update
                fresh_preset = self._get_fresh_preset(preset_name)
                if fresh_preset:
                    self._update_all_buttons_for_preset(preset_name, fresh_preset)

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
        
        # Get updated preset from cache
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
        
        # Update cache
        new_hash = self.get_preset_thumbnail_hash(updated_preset)
        if new_hash is not None:
            self.preset_thumbnail_cache[preset_name] = new_hash
        
        self.save_grids_data()

    def refresh_buttons_with_same_thumbnail(self, preset):
        """Refresh buttons that have the same thumbnail as the given preset.
        
        Optimized to use cached hashes when available instead of recomputing.
        """
        if not preset:
            return

        preset_name = preset.name()
        
        # Use cached hash if available, otherwise compute
        target_hash = self.preset_thumbnail_cache.get(preset_name)
        if target_hash is None:
            target_hash = self.get_preset_thumbnail_hash(preset)
            if target_hash is None:
                return
            # Cache it for future use
            self.preset_thumbnail_cache[preset_name] = target_hash

        # Find buttons with matching hash and update in-place
        buttons_updated = False
        for grid_info in self.grids:
            layout = grid_info.get("layout")
            if not layout:
                continue
            
            for i, p in enumerate(grid_info["brush_presets"]):
                p_name = p.name()
                # Use cached hash if available
                p_hash = self.preset_thumbnail_cache.get(p_name)
                if p_hash is None:
                    p_hash = self.get_preset_thumbnail_hash(p)
                    if p_hash is not None:
                        self.preset_thumbnail_cache[p_name] = p_hash
                
                if p_hash == target_hash:
                    # Update preset reference
                    grid_info["brush_presets"][i] = preset
                    
                    # Try in-place button update
                    button = self._find_button_for_preset_in_grid(grid_info, i)
                    if button and hasattr(button, 'update_preset'):
                        button.update_preset(preset)
                        buttons_updated = True

        if buttons_updated:
            self.save_grids_data()
