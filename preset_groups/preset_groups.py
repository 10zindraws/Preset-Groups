"""Krita 'Preset Groups' docker.

Entry point for the docker widget that manages brush preset grids.
The docker inherits from multiple mixins to organize functionality:

- BrushManagerMixin: Brush size control and preset selection
- GridManagerMixin: Grid CRUD and reordering operations  
- SelectionManagerMixin: Button and grid selection handling
- ThumbnailManagerMixin: Thumbnail caching and change detection
- ShortcutHandlerMixin: Keyboard shortcut handling
- DragManagerMixin: Drag & drop and auto-scroll
- IconButtonFactoryMixin: Icon button creation
- GridUpdateMixin: Grid layout updates
- NameButtonEventsMixin: Grid name button events
"""

import os
import json
from krita import DockWidgetFactory, DockWidgetFactoryBase, Krita  # type: ignore
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QDockWidget,
    QHBoxLayout,
    QApplication,
    QScrollArea,
    QSlider,
    QLineEdit,
    QSizePolicy,
    QSpacerItem,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIntValidator

from .utils.data_manager import load_grids_data, save_grids_data
from .utils.config_utils import (
    get_spacing_between_grids,
    get_brush_icon_size,
    reload_config,
    get_spacing_between_buttons,
)
from .utils.styles import docker_btn_style
from .dialogs.settings_dialog import CommonConfigDialog

from .managers.brush_manager import BrushManagerMixin
from .managers.grid_manager import GridManagerMixin
from .managers.selection_manager import SelectionManagerMixin
from .managers.thumbnail_manager import ThumbnailManagerMixin
from .managers.shortcut_handler import ShortcutHandlerMixin
from .managers.drag_manager import DragManagerMixin
from .ui.icon_button_factory import IconButtonFactoryMixin
from .ui.grid_update_mixin import GridUpdateMixin
from .ui.name_button_events import NameButtonEventsMixin


# Timer intervals (ms)
_BRUSH_CHECK_INTERVAL = 500
_THUMBNAIL_CHECK_INTERVAL = 2000
_BRUSH_POLL_INTERVAL = 30
_RESIZE_DEBOUNCE = 50
_SAVE_DEBOUNCE = 100  # Debounce for save operations

# Slider stylesheet
_SLIDER_STYLE = """
    QSlider { margin-top: -2px; margin-bottom: 2px; }
    QSlider::groove:horizontal {
        border: none; height: 3px; background: #555; border-radius: 3px;
    }
    QSlider::sub-page:horizontal, QSlider::add-page:horizontal {
        background: #636363; border: none; border-radius: 3px;
    }
    QSlider::handle:horizontal {
        background: #ccc; width: 12px; border: none; border-radius: 2px; margin: -5px 0;
    }
"""


class PresetGroupsDocker(
    QDockWidget,
    BrushManagerMixin,
    GridManagerMixin,
    SelectionManagerMixin,
    ThumbnailManagerMixin,
    ShortcutHandlerMixin,
    DragManagerMixin,
    IconButtonFactoryMixin,
    GridUpdateMixin,
    NameButtonEventsMixin,
):
    """Main docker for managing brush preset grids."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Preset Groups")
        self._init_state()
        self._init_config_paths()
        self._load_data()
        self._setup_timers()
        self.setup_brush_preset_save_monitor()
        self.max_brush_size = self.get_max_brush_size_from_config()
        self.init_ui()

    def _init_state(self):
        """Initialize all instance state variables."""
        self.grids = []
        self.active_grid = None
        self.main_widget = None
        self.main_grid_layout = None
        self.grid_counter = 0
        self.current_selected_preset = None
        self.current_selected_button = None
        self.brush_buttons = []
        self.selected_buttons = []
        self.last_selected_button = None
        self.selected_grids = []
        self.last_selected_grid = None
        self._add_brush_qt_key = Qt.Key_W
        self.preset_thumbnail_cache = {}
        self._save_pending = False
        self._grids_pending_update = set()

    def _init_config_paths(self):
        """Setup configuration file paths."""
        config_dir = os.path.join(os.path.dirname(__file__), "config")
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        self.data_file = os.path.join(config_dir, "grids_data.json")
        self.common_config_path = os.path.join(config_dir, "common.json")

    def _load_data(self):
        """Load preset resources and grid data."""
        self.preset_dict = Krita.instance().resources("preset")
        self.grids, self.grid_counter = load_grids_data(
            self.data_file, self.preset_dict
        )
        self.setup_add_brush_shortcut()
        QApplication.instance().installEventFilter(self)

    def _setup_timers(self):
        """Setup periodic timers for brush and thumbnail monitoring."""
        self.brush_check_timer = QTimer()
        self.brush_check_timer.timeout.connect(self.check_brush_change)
        self.brush_check_timer.start(_BRUSH_CHECK_INTERVAL)

        self.thumbnail_check_timer = QTimer()
        self.thumbnail_check_timer.timeout.connect(self.check_thumbnail_changes)
        self.thumbnail_check_timer.start(_THUMBNAIL_CHECK_INTERVAL)

    def save_grids_data(self):
        """Schedule grids data save with debouncing to avoid excessive file writes."""
        if self._save_pending:
            return
        self._save_pending = True
        QTimer.singleShot(_SAVE_DEBOUNCE, self._do_save_grids_data)
    
    def _do_save_grids_data(self):
        """Actually perform the save operation."""
        self._save_pending = False
        save_grids_data(self.data_file, self.grids)

    def init_ui(self):
        """Initialize the docker UI layout."""
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setAlignment(Qt.AlignTop)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self._create_top_row(main_layout)
        self._create_grids_section(main_layout)
        self._create_bottom_row(main_layout)
        self.init_drag_tracking()

        central_widget.setLayout(main_layout)
        self.setWidget(central_widget)
        self._initialize_grids()
        
        # Initialize brush state
        self.initialize_current_brush()
        self.poll_brush_size()
        self.cache_all_preset_thumbnails()
        
        # Schedule initial layout update
        QTimer.singleShot(100, self._update_all_grids_on_resize)

    def _create_top_row(self, main_layout):
        """Create top controls row with brush size slider and settings."""
        top_row_layout = QHBoxLayout()
        top_row_layout.setSpacing(4)
        top_row_layout.setContentsMargins(4, 2, 4, 2)

        self.brush_size_slider = QSlider(Qt.Horizontal)
        self.brush_size_slider.setMinimum(1)
        self.brush_size_slider.setMaximum(self.max_brush_size)
        self.brush_size_slider.setValue(100)
        self.brush_size_slider.setMinimumWidth(120)
        self.brush_size_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.brush_size_slider.setStyleSheet(_SLIDER_STYLE)
        self.brush_size_slider.valueChanged.connect(self.on_brush_size_slider_changed)
        top_row_layout.addWidget(self.brush_size_slider, 1)

        top_row_layout.addSpacerItem(QSpacerItem(27, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))

        self.brush_size_number = QLineEdit()
        self.brush_size_number.setFixedWidth(60)
        self.brush_size_number.setAlignment(Qt.AlignLeft)
        validator = QIntValidator(1, self.max_brush_size, self.brush_size_number)
        self.brush_size_number.setValidator(validator)
        self.brush_size_number.setText("100 px")
        self.brush_size_number.editingFinished.connect(self.on_brush_size_number_changed)
        top_row_layout.addWidget(self.brush_size_number)

        top_row_layout.addStretch()

        self.setting_btn = self.create_icon_button(
            "settings-button", self.show_settings_dialog
        )
        top_row_layout.addWidget(self.setting_btn, 0, Qt.AlignRight)

        top_row_widget = QWidget()
        top_row_widget.setLayout(top_row_layout)
        top_row_widget.setFixedHeight(self.setting_btn.sizeHint().height() + 6)
        main_layout.addWidget(top_row_widget)

        self.brush_size_poll_timer = QTimer()
        self.brush_size_poll_timer.timeout.connect(self.poll_brush_size)
        self.brush_size_poll_timer.start(_BRUSH_POLL_INTERVAL)

    def _create_grids_section(self, main_layout):
        """Create the scrollable grids section."""
        self.main_widget = QWidget()
        self.main_widget.mousePressEvent = self.main_widget_click_handler
        self.main_grid_layout = QVBoxLayout()
        self.main_grid_layout.setAlignment(Qt.AlignTop)
        self.main_grid_layout.setSpacing(get_spacing_between_grids())
        self.main_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.main_widget.setLayout(self.main_grid_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.main_widget)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        self.scroll_area.setContentsMargins(0, 0, 0, 0)
        self.scroll_area.mousePressEvent = self.scroll_area_click_handler

        main_layout.addWidget(self.scroll_area, 1)

    def _create_bottom_row(self, main_layout):
        """Create bottom button row with icon size slider and action buttons"""
        button_layout = QHBoxLayout()
        button_layout.setSpacing(1)

        # Icon size slider
        self.icon_size_slider = QSlider(Qt.Horizontal)
        self.icon_size_slider.setMinimum(30)
        self.icon_size_slider.setMaximum(170)
        self.icon_size_slider.setValue(get_brush_icon_size())
        self.icon_size_slider.setMinimumWidth(100)
        self.icon_size_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.icon_size_slider.setStyleSheet(_SLIDER_STYLE)
        self.icon_size_slider.valueChanged.connect(self.on_brush_size_changed)
        button_layout.addWidget(self.icon_size_slider, 1)

        # Spacer
        button_layout.addSpacerItem(QSpacerItem(45, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))

        # Add Brush button
        self.add_brush_button = self.create_icon_button("addbrushicon", self.add_current_brush)
        button_layout.addWidget(self.add_brush_button)
        button_layout.addSpacerItem(QSpacerItem(2, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))

        # Add Grid button
        add_grid_button = self.create_icon_button("folder", self.add_new_grid)
        button_layout.addWidget(add_grid_button)
        button_layout.addSpacerItem(QSpacerItem(2, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))

        # Delete button
        self.delete_button = self.create_icon_button("deletelayer", self.handle_delete_button_click)
        button_layout.addWidget(self.delete_button)
        button_layout.addSpacerItem(QSpacerItem(2, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))

        main_layout.addLayout(button_layout)

    def _initialize_grids(self):
        """Initialize grids from loaded data or create a default grid."""
        if not self.grids:
            self.add_new_grid()
            return
        for grid_info in self.grids:
            self._add_grid_ui(grid_info)
        if self.grids:
            self.set_active_grid(self.grids[0])

    def show_settings_dialog(self):
        """Show settings dialog and apply changes."""
        dlg = CommonConfigDialog(self.common_config_path, self)
        if not dlg.exec_():
            return
        reload_config()
        new_max = self.get_max_brush_size_from_config()
        self.update_max_brush_size(new_max)
        self.setup_add_brush_shortcut()
        self._apply_grid_spacing()
        self.refresh_styles()

    def _apply_grid_spacing(self):
        """Update grid spacing after settings change."""
        for grid_info in self.grids:
            container = grid_info.get("container")
            if container and container.layout():
                container.layout().setSpacing(1)
            layout = grid_info.get("layout")
            if layout:
                layout.setSpacing(get_spacing_between_buttons())
            self.update_grid(grid_info)

    def refresh_styles(self):
        """Reapply button and grid styles."""
        for grid in self.grids:
            self.update_grid_style(grid)
            self._refresh_grid_button_styles(grid)
        self._refresh_icon_button_styles()

    def _refresh_grid_button_styles(self, grid):
        """Refresh styles for buttons within a grid."""
        layout = grid.get("layout")
        if not layout:
            return
        for i in range(layout.count()):
            btn = layout.itemAt(i).widget()
            if btn:
                btn.setStyleSheet(docker_btn_style())

    def _refresh_icon_button_styles(self):
        """Refresh styles for icon buttons (settings, add, delete, etc.)."""
        icon_button_style = """
            QPushButton {
                background-color: #474747;
                border: none;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.3);
            }
        """
        for btn in self.findChildren(QPushButton):
            # Skip collapse buttons - they have their own style (#383838)
            if btn.objectName() == "collapse_button":
                continue
            if btn.text() == "" and btn.icon() and not btn.icon().isNull():
                btn.setStyleSheet(icon_button_style)

    def resizeEvent(self, event):
        """Handle docker resize with debouncing."""
        super().resizeEvent(event)
        if not hasattr(self, '_resize_timer'):
            self._resize_timer = QTimer()
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._on_resize_complete)
        self._resize_timer.stop()
        self._resize_timer.start(_RESIZE_DEBOUNCE)

    def _on_resize_complete(self):
        """Called after resize events have stopped."""
        self._update_all_grids_on_resize()


class PresetGroupsDockerFactory(DockWidgetFactoryBase):
    """Factory for creating the Preset Groups docker widget."""

    def __init__(self):
        super().__init__("preset_groups_docker", DockWidgetFactory.DockRight)

    def createDockWidget(self):
        return PresetGroupsDocker()
