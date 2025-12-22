"""Grid container and click surface for brush presets.

`ClickableGridWidget` represents the area that holds brush buttons for one
grid and handles drag & drop between grids. `DraggableGridContainer` wraps
the grid header (collapse + name row) and the `ClickableGridWidget`, and also
accepts drops on the header so brushes can be moved by dropping on the grid
name.
"""

from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, QPoint, QMimeData
from PyQt5.QtGui import QDrag
from ..utils.config_utils import (
    get_brush_icon_size,
    get_spacing_between_buttons,
    get_display_brush_names,
    get_brush_name_label_height,
)
from ..utils.drag_utils import decode_single, decode_multi


class ClickableGridWidget(QWidget):
    """A clickable and droppable grid widget for brush presets"""

    def __init__(self, grid_info, parent_docker):
        super().__init__()
        self.grid_info = grid_info
        self.parent_docker = parent_docker
        self.drag_start_position = QPoint()
        self.setAcceptDrops(True)

    def mousePressEvent(self, event):
        """Handle mouse press events"""
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
            # Check if clicking on empty space (not on a button)
            widget_under_mouse = self.childAt(event.pos())
            if not widget_under_mouse or not hasattr(widget_under_mouse, "preset"):
                # Clicked outside buttons - deselect all
                self.parent_docker.clear_selection()
        elif event.button() == Qt.RightButton:
            # Right-click outside buttons - deselect all
            widget_under_mouse = self.childAt(event.pos())
            if not widget_under_mouse or not hasattr(widget_under_mouse, "preset"):
                self.parent_docker.clear_selection()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move events for grid dragging"""
        if not (event.buttons() & Qt.LeftButton):
            return

        if (
            event.pos() - self.drag_start_position
        ).manhattanLength() < QApplication.startDragDistance():
            return

        # Only start grid drag if clicking on empty space (not on brush buttons)
        widget_under_mouse = self.childAt(event.pos())
        if widget_under_mouse and hasattr(widget_under_mouse, "preset"):
            return

        self.start_grid_drag()

    def start_grid_drag(self):
        """Start grid drag operation"""
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(f"grid:{self.grid_info['name']}")
        drag.setMimeData(mime_data)

        drop_action = drag.exec_(Qt.MoveAction)

    def dragEnterEvent(self, event):
        """Handle drag enter events"""
        if event.mimeData().hasText():
            text = event.mimeData().text()
            if text.startswith("brush_preset:") or text.startswith("brush_presets_multi:"):
                event.acceptProposedAction()

    def dropEvent(self, event):
        """Handle drop events"""
        if event.mimeData().hasText():
            text = event.mimeData().text()
            if text.startswith("brush_preset:"):
                self.handle_brush_drop(event, text)
            elif text.startswith("brush_presets_multi:"):
                self.handle_multi_brush_drop(event, text)

    def handle_brush_drop(self, event, text):
        """Handle brush preset drop"""
        preset_name = decode_single(text) or text.split(":", 1)[1]

        # Find the source preset and grid
        source_preset, source_grid, source_index = self.find_source_preset(preset_name)

        if source_preset and source_grid:
            drop_pos = event.pos()
            target_index = self.calculate_drop_position(drop_pos)

            # Remove from old position
            source_grid["brush_presets"].pop(source_index)

            if source_grid == self.grid_info:
                # Reorder within same grid
                target_index = min(target_index, len(source_grid["brush_presets"]))
                source_grid["brush_presets"].insert(target_index, source_preset)
                self.parent_docker.update_grid(source_grid)
            else:
                # Move between grids
                target_index = min(target_index, len(self.grid_info["brush_presets"]))
                self.grid_info["brush_presets"].insert(target_index, source_preset)
                self.parent_docker.update_grid(source_grid)
                self.parent_docker.update_grid(self.grid_info)

            self.parent_docker.save_grids_data()
            event.acceptProposedAction()

    def find_source_preset(self, preset_name):
        """Find source preset in grids"""
        for grid in self.parent_docker.grids:
            for i, preset in enumerate(grid["brush_presets"]):
                if preset.name() == preset_name:
                    return preset, grid, i
        return None, None, -1

    def _parse_preset_names(self, text):
        """Parse preset names from mime data text"""
        preset_names = decode_multi(text)
        if not preset_names:
            preset_names_str = text.split(":", 1)[1]
            preset_names = [p.strip() for p in preset_names_str.split(",") if p.strip()]
        return preset_names

    def _find_source_presets_data(self, preset_names):
        """Find all source presets and their positions"""
        source_presets_data = []
        for preset_name in preset_names:
            preset_name = preset_name.strip()
            source_preset, source_grid, source_index = self.find_source_preset(preset_name)
            if source_preset and source_grid is not None:
                source_presets_data.append({
                    "preset": source_preset,
                    "grid": source_grid,
                    "index": source_index
                })
        return source_presets_data

    def _group_presets_by_grid(self, source_presets_data):
        """Group presets by their source grid"""
        grids_to_update = {}
        for data in source_presets_data:
            grid = data["grid"]
            grid_name = grid.get("name", id(grid))
            if grid_name not in grids_to_update:
                grids_to_update[grid_name] = {"grid_info": grid, "presets_data": []}
            grids_to_update[grid_name]["presets_data"].append(data)
        return grids_to_update

    def _remove_presets_from_source_grids(self, grids_to_update):
        """Remove presets from source grids in reverse index order"""
        for grid_data in grids_to_update.values():
            grid_info = grid_data["grid_info"]
            presets_data = grid_data["presets_data"]
            for data in sorted(presets_data, key=lambda x: x["index"], reverse=True):
                grid_info["brush_presets"].pop(data["index"])

    def _calculate_adjusted_target_index(self, target_index, original_indices, target_grid):
        """Calculate adjusted target index for same-grid reordering"""
        if not original_indices:
            return target_index

        if target_index > original_indices[0] and target_index <= original_indices[-1] + 1:
            target_index = original_indices[0]

        removed_before_target = sum(1 for idx in original_indices if idx < target_index)
        target_index = max(0, target_index - removed_before_target)
        return min(target_index, len(target_grid["brush_presets"]))

    def _insert_presets_at_target(self, target_grid, presets_to_insert, target_index):
        """Insert presets at target position in grid"""
        for i, preset in enumerate(presets_to_insert):
            target_grid["brush_presets"].insert(target_index + i, preset)

    def _handle_same_grid_reorder(self, target_grid, presets_to_insert, source_presets_data, target_index):
        """Handle reordering within the same grid"""
        original_indices = sorted([data["index"] for data in source_presets_data])
        adjusted_index = self._calculate_adjusted_target_index(target_index, original_indices, target_grid)
        self._insert_presets_at_target(target_grid, presets_to_insert, adjusted_index)
        self.parent_docker.update_grid(target_grid)

    def _handle_cross_grid_move(self, target_grid, presets_to_insert, grids_to_update, target_index):
        """Handle moving presets between different grids"""
        target_index = min(target_index, len(target_grid["brush_presets"]))
        self._insert_presets_at_target(target_grid, presets_to_insert, target_index)
        self.parent_docker.update_grid(target_grid)
        for grid_name, grid_data in grids_to_update.items():
            if grid_data["grid_info"] != target_grid:
                self.parent_docker.update_grid(grid_data["grid_info"])

    def handle_multi_brush_drop(self, event, text):
        """Handle multiple brush preset drop"""
        preset_names = self._parse_preset_names(text)
        source_presets_data = self._find_source_presets_data(preset_names)
        if not source_presets_data:
            return

        grids_to_update = self._group_presets_by_grid(source_presets_data)
        self._remove_presets_from_source_grids(grids_to_update)

        drop_pos = event.pos()
        target_index = self.calculate_drop_position(drop_pos)
        presets_to_insert = [data["preset"] for data in source_presets_data]
        target_grid = self.grid_info

        all_from_target = all(data["grid"] == target_grid for data in source_presets_data)
        if all_from_target:
            self._handle_same_grid_reorder(target_grid, presets_to_insert, source_presets_data, target_index)
        else:
            self._handle_cross_grid_move(target_grid, presets_to_insert, grids_to_update, target_index)

        self.parent_docker.clear_selection()
        self.parent_docker.save_grids_data()
        event.acceptProposedAction()

    def calculate_drop_position(self, drop_pos):
        """Calculate target position for drop"""
        # Use dynamic columns from parent docker instead of config
        columns = self.parent_docker.get_dynamic_columns()
        button_size = get_brush_icon_size()
        spacing = get_spacing_between_buttons()
        
        # Account for name label height if brush names are displayed
        name_label_height = 0
        if get_display_brush_names():
            # Use 2-line height as max since we don't know exact grid state
            name_label_height = get_brush_name_label_height(2)
        
        total_button_height = button_size + name_label_height

        col = min(drop_pos.x() // (button_size + spacing), columns - 1)
        row = drop_pos.y() // (total_button_height + spacing)
        return row * columns + col


class DraggableGridContainer(QWidget):
    """Container for draggable grids"""

    def __init__(self, grid_info, parent_docker):
        super().__init__()
        self.grid_info = grid_info
        self.parent_docker = parent_docker
        # Allow drops on the header/container itself (grid name row area)
        # so users can drop brushes directly onto a grid header.
        self.setAcceptDrops(True)

    # --- Drag & Drop on header / container ---------------------------------

    def dragEnterEvent(self, event):
        """Accept brush drags when hovering over the grid header/container."""
        if event.mimeData().hasText():
            text = event.mimeData().text()
            if text.startswith("brush_preset:") or text.startswith("brush_presets_multi:"):
                event.acceptProposedAction()

    def dropEvent(self, event):
        """
        Handle drops on the grid header/container.

        Requirement: when one or more DraggableBrushButtons are dropped while
        hovering a gridname row, place them inside this grid and unhide it.
        """
        if not event.mimeData().hasText():
            return

        text = event.mimeData().text()

        # Ensure grid is un-collapsed / visible
        if self.grid_info.get("is_collapsed"):
            # Use existing toggle logic in the docker to update icon + visibility
            try:
                self.parent_docker.toggle_grid_collapse(self.grid_info)
            except Exception:
                # Fallback: force it visible if toggle is not available
                self.grid_info["is_collapsed"] = False
                self.parent_docker.update_grid_visibility(self.grid_info)

        if text.startswith("brush_preset:"):
            self._handle_header_brush_drop(event, text)
        elif text.startswith("brush_presets_multi:"):
            self._handle_header_multi_brush_drop(event, text)

    # --- Helper methods for header drops -----------------------------------

    def _find_source_preset(self, preset_name):
        """Find source preset in all grids (same logic as ClickableGridWidget)."""
        for grid in self.parent_docker.grids:
            for i, preset in enumerate(grid["brush_presets"]):
                if preset.name() == preset_name:
                    return preset, grid, i
        return None, None, -1

    def _handle_header_brush_drop(self, event, text):
        """Single preset dropped on grid header: append to this grid."""
        preset_name = text.split(":", 1)[1]

        source_preset, source_grid, source_index = self._find_source_preset(preset_name)

        if not (source_preset and source_grid):
            return

        # Remove from old position
        source_grid["brush_presets"].pop(source_index)

        target_grid = self.grid_info
        target_index = len(target_grid["brush_presets"])

        # Insert into target grid at the end
        target_grid["brush_presets"].insert(target_index, source_preset)

        # Update affected grids
        if source_grid is target_grid:
            self.parent_docker.update_grid(target_grid)
        else:
            self.parent_docker.update_grid(source_grid)
            self.parent_docker.update_grid(target_grid)

        self.parent_docker.save_grids_data()
        event.acceptProposedAction()

    def _handle_header_multi_brush_drop(self, event, text):
        """Multiple presets dropped on grid header: append all to this grid."""
        # Parse preset names from mime data
        preset_names_str = text.split(":", 1)[1]
        preset_names = [name.strip() for name in preset_names_str.split(",") if name.strip()]

        # Find all source presets and their positions
        source_presets_data = []
        for preset_name in preset_names:
            source_preset, source_grid, source_index = self._find_source_preset(preset_name)
            if source_preset and source_grid is not None:
                source_presets_data.append(
                    {"preset": source_preset, "grid": source_grid, "index": source_index}
                )

        if not source_presets_data:
            return

        # Group by grid first to safely remove from source positions
        grids_to_update = {}
        for data in source_presets_data:
            grid = data["grid"]
            grid_name = grid.get("name", id(grid))
            if grid_name not in grids_to_update:
                grids_to_update[grid_name] = {"grid_info": grid, "presets_data": []}
            grids_to_update[grid_name]["presets_data"].append(data)

        # Remove presets from their original grids (reverse index order per grid)
        for grid_data in grids_to_update.values():
            grid_info = grid_data["grid_info"]
            presets_data = grid_data["presets_data"]
            for data in sorted(presets_data, key=lambda x: x["index"], reverse=True):
                grid_info["brush_presets"].pop(data["index"])

        # Append all presets to this grid in the order they were dragged
        target_grid = self.grid_info
        for data in source_presets_data:
            target_grid["brush_presets"].append(data["preset"])

        # Update affected grids
        for grid_data in grids_to_update.values():
            grid_info = grid_data["grid_info"]
            self.parent_docker.update_grid(grid_info)
        if target_grid not in [g["grid_info"] for g in grids_to_update.values()]:
            self.parent_docker.update_grid(target_grid)

        # Clear selection and save
        self.parent_docker.clear_selection()
        self.parent_docker.save_grids_data()
        event.acceptProposedAction()
