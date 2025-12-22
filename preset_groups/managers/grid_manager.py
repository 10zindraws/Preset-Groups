"""Grid management functionality.

Provides mixin class for handling grid-related operations like adding,
removing, renaming, collapsing, and reordering grids.
"""

import re
from krita import Krita  # type: ignore
from PyQt5.QtWidgets import (
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QInputDialog,
    QLineEdit,
)
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QIcon

from ..utils.config_utils import get_brush_icon_size, get_spacing_between_buttons
from ..utils.styles import GRID_NAME_COLOR
from ..widgets.grid_container import ClickableGridWidget, DraggableGridContainer
from ..widgets.draggable_grid_row import DraggableGridRow


# Pattern for auto-generated group names
_GROUP_NAME_PATTERN = re.compile(r"^Group\s+(\d+)$")

# Stylesheets
_COLLAPSE_BUTTON_STYLE = """
    QPushButton {
        background-color: #383838;
        border: none;
        border-radius: 2px;
    }
    QPushButton:hover { background-color: rgba(0, 0, 0, 0.3); }
    QPushButton:pressed { background-color: rgba(0, 0, 0, 0.5); }
"""

_NAME_BUTTON_STYLE = """
    QPushButton {
        background-color: #383838;
        color: #ffffff;
        font-weight: bold;
        font-size: 12px;
        border: none;
        border-radius: 2px;
        text-align: left;
        padding: 2px 4px;
    }
    QPushButton:hover { background-color: rgba(0, 0, 0, 0.3); }
    QPushButton:pressed { background-color: rgba(0, 0, 0, 0.5); }
"""


class GridManagerMixin:
    """Mixin class providing grid management functionality for the docker widget."""
    
    def _create_collapse_button(self, grid_info, name_button_height):
        """Create and configure the collapse button for a grid."""
        collapse_button = QPushButton()
        collapse_button.setObjectName("collapse_button")
        collapse_button.setFixedSize(name_button_height, name_button_height)
        collapse_button.setStyleSheet(_COLLAPSE_BUTTON_STYLE)
        collapse_button.clicked.connect(lambda: self.toggle_grid_collapse(grid_info))
        
        icon_size = name_button_height - 8
        collapse_button.setIconSize(QSize(icon_size, icon_size))
        self._set_collapse_button_icon(
            collapse_button, 
            grid_info.get("is_collapsed", False), 
            icon_size
        )
        
        return collapse_button

    def _create_name_button(self, grid_info):
        """Create and configure the name button for a grid."""
        name_button = QPushButton(grid_info["name"])
        name_button.setStyleSheet(_NAME_BUTTON_STYLE)
        name_button.drag_start_pos = None
        name_button.is_dragging_grid = False
        self._setup_name_button_events(name_button, grid_info)
        return name_button

    def _add_grid_ui(self, grid_info):
        """Add UI elements for a grid."""
        grid_container = DraggableGridContainer(grid_info, self)
        container_layout = QVBoxLayout()
        container_layout.setAlignment(Qt.AlignTop)
        container_layout.setSpacing(1)
        container_layout.setContentsMargins(0, 0, 0, 0)

        # Create draggable header row containing collapse button and name button
        header_row = DraggableGridRow(grid_info, self)
        grid_info["header_row"] = header_row
        grid_info["is_collapsed"] = grid_info.get("is_collapsed", False)
        
        # Create name button first to get its height
        name_button = self._create_name_button(grid_info)
        name_button.adjustSize()
        name_button_height = name_button.sizeHint().height()
        
        # Create collapse button sized to match
        collapse_button = self._create_collapse_button(grid_info, name_button_height)
        grid_info["collapse_button"] = collapse_button
        
        # Add buttons to the draggable header row
        header_row.add_collapse_button(collapse_button)
        header_row.add_name_button(name_button)
        container_layout.addWidget(header_row)
        
        grid_info["container"] = grid_container
        grid_info["name_label"] = name_button
        grid_info["name_button"] = name_button
        # Keep header_layout reference for compatibility with inline rename
        grid_info["header_layout"] = header_row.layout()

        # Create grid widget for brush buttons
        grid_widget = ClickableGridWidget(grid_info, self)
        initial_height = get_brush_icon_size() + 4
        grid_widget.setFixedHeight(initial_height)
        grid_widget.setMinimumHeight(initial_height)

        grid_layout = QGridLayout()
        grid_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        grid_layout.setSpacing(get_spacing_between_buttons())
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_widget.setLayout(grid_layout)
        container_layout.addWidget(grid_widget)

        grid_container.setLayout(container_layout)
        grid_info["widget"] = grid_widget
        grid_info["layout"] = grid_layout
        self.main_grid_layout.addWidget(grid_container)
        self.update_grid(grid_info)

    def _set_collapse_button_icon(self, collapse_button, is_collapsed, icon_size):
        """Set the collapse button icon based on collapse state."""
        icon_name = "arrow-right" if is_collapsed else "arrow-down"
        icon = Krita.instance().icon(icon_name)
        
        if not icon or icon.isNull():
            return
        
        # Use high-res then scale down for quality
        pixmap = icon.pixmap(icon_size * 2, icon_size * 2)
        if not pixmap.isNull():
            scaled = pixmap.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            collapse_button.setIcon(QIcon(scaled))
        else:
            collapse_button.setIcon(icon)
        collapse_button.setIconSize(QSize(icon_size, icon_size))

    def update_grid_visibility(self, grid_info):
        """Show/hide the brush grid area based on collapse state and contents."""
        grid_widget = grid_info.get("widget")
        if not grid_widget:
            return
        has_brushes = len(grid_info.get("brush_presets", [])) > 0
        is_collapsed = grid_info.get("is_collapsed", False)
        grid_widget.setVisible(has_brushes and not is_collapsed)

    def toggle_grid_collapse(self, grid_info):
        """Toggle collapse state of a grid.
        
        In exclusive uncollapse mode, only one grid can be uncollapsed at a time.
        The uncollapsed grid becomes the active_grid.
        """
        from ..utils.config_utils import get_exclusive_uncollapse
        
        is_currently_collapsed = grid_info.get("is_collapsed", False)
        new_collapsed_state = not is_currently_collapsed
        
        if get_exclusive_uncollapse():
            if new_collapsed_state:
                # Collapsing this grid
                grid_info["is_collapsed"] = True
                self._update_collapse_button_icon(grid_info)
                self.update_grid_visibility(grid_info)
                
                # Check if all grids are now collapsed
                all_collapsed = all(g.get("is_collapsed", False) for g in self.grids)
                if all_collapsed:
                    # Deselect active_grid when all are collapsed
                    self._clear_active_grid_highlight()
            else:
                # Uncollapsing this grid - collapse all others first
                for other_grid in self.grids:
                    if other_grid != grid_info and not other_grid.get("is_collapsed", False):
                        other_grid["is_collapsed"] = True
                        self._update_collapse_button_icon(other_grid)
                        self.update_grid_visibility(other_grid)
                
                # Now uncollapse the target grid
                grid_info["is_collapsed"] = False
                self._update_collapse_button_icon(grid_info)
                self.update_grid_visibility(grid_info)
                
                # Set this grid as active
                self.set_active_grid(grid_info)
        else:
            # Normal mode - just toggle
            grid_info["is_collapsed"] = new_collapsed_state
            self._update_collapse_button_icon(grid_info)
            self.update_grid_visibility(grid_info)
    
    def _update_collapse_button_icon(self, grid_info):
        """Update the collapse button icon for a grid."""
        collapse_button = grid_info.get("collapse_button")
        if collapse_button:
            button_height = collapse_button.height()
            icon_size = button_height - 8
            self._set_collapse_button_icon(collapse_button, grid_info["is_collapsed"], icon_size)

    def _get_next_group_number(self):
        """Calculate the next available group number."""
        existing_numbers = []
        for grid in self.grids:
            name = str(grid.get("name", "")).strip()
            match = _GROUP_NAME_PATTERN.match(name)
            if match:
                existing_numbers.append(int(match.group(1)))
        return max(existing_numbers, default=0) + 1

    def _create_empty_grid_info(self, name):
        """Create a new empty grid info dictionary."""
        return {
            "container": None,
            "widget": None,
            "layout": None,
            "name_label": None,
            "name_button": None,
            "collapse_button": None,
            "is_collapsed": False,
            "name": name,
            "brush_presets": [],
            "is_active": False,
        }

    def add_new_grid(self):
        """Add a new grid with auto-generated name."""
        next_num = self._get_next_group_number()
        self.grid_counter = max(self.grid_counter, next_num)
        
        grid_info = self._create_empty_grid_info(f"Group {next_num}")
        self.grids.append(grid_info)
        self._add_grid_ui(grid_info)
        
        if len(self.grids) == 1:
            self.set_active_grid(grid_info)
        self.save_grids_data()

    def remove_grid(self, grid_info=None):
        """Remove grid(s) - handles both single and multiple selection."""
        if grid_info is None and self.selected_grids:
            for grid in self.selected_grids.copy():
                self._remove_single_grid(grid)
            self.selected_grids = []
            self.last_selected_grid = None
            self.update_grid_selection_highlights()
            return
        
        if grid_info:
            self._remove_single_grid(grid_info)
    
    def _cleanup_grid_buttons(self, layout):
        """Remove all buttons from a grid layout."""
        for i in reversed(range(layout.count())):
            widget = layout.itemAt(i).widget()
            if widget:
                if widget in self.brush_buttons:
                    self.brush_buttons.remove(widget)
                layout.removeWidget(widget)
                widget.setParent(None)
                widget.deleteLater()

    def _remove_single_grid(self, grid_info):
        """Remove a single grid and its UI elements."""
        if grid_info not in self.grids:
            return
        
        # Cleanup buttons
        layout = grid_info.get("layout")
        if layout:
            self._cleanup_grid_buttons(layout)
        
        # Update selection state
        if grid_info in self.selected_grids:
            self.selected_grids.remove(grid_info)
        if self.last_selected_grid == grid_info:
            self.last_selected_grid = None
        
        # Remove container widget
        container = grid_info.get("container")
        if container:
            self.main_grid_layout.removeWidget(container)
            container.setParent(None)
            container.deleteLater()
        
        self.grids.remove(grid_info)
        
        # Update active grid
        self.active_grid = self.grids[0] if self.grids else None
        if self.active_grid:
            self.set_active_grid(self.active_grid)
        
        self.save_grids_data()

    def move_grid(self, grid_info, direction):
        """Move a grid up or down in the list"""
        idx = self.grids.index(grid_info)
        new_idx = idx + direction
        if 0 <= new_idx < len(self.grids):
            self.grids.pop(idx)
            self.grids.insert(new_idx, grid_info)
            self.rebuild_grid_layout()
            self.save_grids_data()

    def _update_grid_name_ui(self, grid_info, new_name):
        """Update grid name in UI elements."""
        grid_info["name"] = new_name
        if grid_info.get("name_label"):
            grid_info["name_label"].setText(new_name)
        if grid_info.get("name_button"):
            grid_info["name_button"].setText(new_name)

    def rename_grid(self, grid_info=None):
        """Rename grid(s) - handles both single and multiple selection."""
        if grid_info is None and self.selected_grids:
            self._rename_grids_sequentially(self.selected_grids.copy())
            return
        
        if grid_info is None:
            return
        
        new_name, ok = QInputDialog.getText(
            self, "Rename Group", "Enter new grid name:", text=grid_info["name"]
        )
        if ok and new_name.strip():
            self._update_grid_name_ui(grid_info, new_name.strip())
            self.save_grids_data()
    
    def _rename_grids_sequentially(self, grids_to_rename):
        """Rename multiple grids sequentially, one dialog at a time.
        
        Grids are sorted by their visual order (top to bottom) before renaming.
        """
        if not grids_to_rename:
            self.selected_grids = []
            self.last_selected_grid = None
            self.update_grid_selection_highlights()
            return
        
        # Sort grids by their visual order (top to bottom)
        sorted_grids = sorted(
            grids_to_rename,
            key=lambda g: self.grids.index(g) if g in self.grids else float('inf')
        )
        
        self._rename_next_grid(sorted_grids)
    
    def _rename_next_grid(self, grids_remaining):
        """Rename the next grid in the sequence."""
        if not grids_remaining:
            self.selected_grids = []
            self.last_selected_grid = None
            self.update_grid_selection_highlights()
            return
        
        grid_info = grids_remaining[0]
        new_name, ok = QInputDialog.getText(
            self, "Rename Grid", "Enter new grid name:", text=grid_info["name"]
        )
        
        if ok and new_name.strip():
            self._update_grid_name_ui(grid_info, new_name.strip())
            self.save_grids_data()
        
        remaining = grids_remaining[1:]
        if remaining:
            QTimer.singleShot(100, lambda: self._rename_next_grid(remaining))
        else:
            self.selected_grids = []
            self.last_selected_grid = None
            self.update_grid_selection_highlights()

    def start_inline_grid_rename(self, grid_info):
        """Turn the grid name button into an inline editable textbox."""
        if grid_info.get("name_editor"):
            return

        container = grid_info.get("container")
        header_layout = grid_info.get("header_layout")
        name_button = grid_info.get("name_button") or grid_info.get("name_label")

        if not all([container, header_layout, name_button]):
            return

        original_name = grid_info.get("name", "")
        editor = self._create_inline_editor(container, original_name)
        editor._grid_info = grid_info
        editor._original_name = original_name

        header_layout.replaceWidget(name_button, editor)
        name_button.hide()
        grid_info["name_editor"] = editor

        editor.setFocus()
        editor.selectAll()
        editor.returnPressed.connect(lambda: self._finish_inline_grid_rename(editor, True))
        editor.installEventFilter(self)

    def _create_inline_editor(self, parent, text):
        """Create a styled line editor for inline renaming."""
        editor = QLineEdit(parent)
        editor.setObjectName("grid_name_editor")
        editor.setText(text)
        editor.setStyleSheet(f"""
            QLineEdit {{
                background-color: #383838;
                color: {GRID_NAME_COLOR};
                font-weight: bold;
                font-size: 12px;
                border: none;
                border-radius: 2px;
                padding: 2px 4px;
            }}
        """)
        return editor

    def _finish_inline_grid_rename(self, editor, apply_change):
        """Finalize inline rename: apply or discard, then restore the button."""
        grid_info = getattr(editor, "_grid_info", None)
        original_name = getattr(editor, "_original_name", None)

        if not grid_info or original_name is None:
            return

        header_layout = grid_info.get("header_layout")
        name_button = grid_info.get("name_button") or grid_info.get("name_label")

        if not header_layout or not name_button:
            return

        if apply_change:
            new_name = editor.text().strip()
            if new_name and new_name != original_name:
                self._update_grid_name_ui(grid_info, new_name)
                self.save_grids_data()

        header_layout.replaceWidget(editor, name_button)
        name_button.show()
        grid_info["name_editor"] = None
        editor.deleteLater()

    def rebuild_grid_layout(self):
        """Rebuild the grid layout after reordering"""
        for i in reversed(range(self.main_grid_layout.count())):
            item = self.main_grid_layout.itemAt(i)
            if item:
                widget = item.widget()
                if widget:
                    self.main_grid_layout.removeWidget(widget)

        for grid_info in self.grids:
            self.main_grid_layout.addWidget(grid_info["container"])

        for grid_info in self.grids:
            self.update_grid_style(grid_info)
        self.save_grids_data()

    def _update_all_grids_on_resize(self):
        """Update all grids with recalculated column count"""
        for grid_info in self.grids:
            if grid_info.get("layout") and grid_info.get("brush_presets"):
                self.update_grid(grid_info)

    # --- Grid Drag & Drop Support ---
    
    def _init_grid_drag_state(self):
        """Initialize grid drag tracking state."""
        if not hasattr(self, '_grids_being_dragged'):
            self._grids_being_dragged = []
    
    def on_grid_drag_started(self, grids):
        """Called when a grid drag operation starts."""
        self._init_grid_drag_state()
        self._grids_being_dragged = list(grids)
    
    def on_grid_drag_ended(self):
        """Called when a grid drag operation ends."""
        self._init_grid_drag_state()
        self._grids_being_dragged = []
        
        # Stop drag tracking for autoscroll
        if hasattr(self, 'stop_drag_tracking'):
            self.stop_drag_tracking()
        
        # Clear any remaining drop indicators
        for grid in self.grids:
            header_row = grid.get("header_row")
            if header_row and hasattr(header_row, 'drop_position'):
                header_row.drop_position = None
                header_row.update()
    
    def get_grids_being_dragged(self):
        """Get the list of grids currently being dragged."""
        self._init_grid_drag_state()
        return self._grids_being_dragged
    
    def move_grids_to_position(self, source_grids, target_grid, insert_after=False):
        """Move source grids to a new position relative to target grid.
        
        Args:
            source_grids: List of grids to move
            target_grid: The grid to position relative to
            insert_after: If True, insert after target; if False, insert before
        """
        if not source_grids or not target_grid:
            return
        
        # Don't move if target is one of the source grids
        if target_grid in source_grids:
            return
        
        # Remove source grids from their current positions
        for grid in source_grids:
            if grid in self.grids:
                self.grids.remove(grid)
        
        # Find target position
        try:
            target_idx = self.grids.index(target_grid)
        except ValueError:
            # Target grid not found, append to end
            target_idx = len(self.grids)
        
        # Adjust position if inserting after
        if insert_after:
            target_idx += 1
        
        # Insert source grids at the target position
        for i, grid in enumerate(source_grids):
            self.grids.insert(target_idx + i, grid)
        
        # Clear selection after move
        self.selected_grids = []
        self.last_selected_grid = None
        
        # Rebuild the layout and save
        self.rebuild_grid_layout()
        self.update_grid_selection_highlights()
