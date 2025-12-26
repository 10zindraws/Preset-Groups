"""Krita 'Preset Groups' docker.

Entry point for the docker widget that manages brush preset grids.
The docker inherits from multiple mixins to organize functionality:

- BrushManagerMixin: Brush size control and preset selection
- GridManagerMixin: Grid CRUD and reordering operations  
- SelectionManagerMixin: Button and grid selection handling
- ThumbnailManagerMixin: Thumbnail refresh on events
- ShortcutHandlerMixin: Keyboard shortcut handling
- DragManagerMixin: Drag & drop and auto-scroll
- IconButtonFactoryMixin: Icon button creation
- GridUpdateMixin: Grid layout updates
- NameButtonEventsMixin: Grid name button events

PERFORMANCE OPTIMIZATIONS:
- Signal-based brush change detection (replaces polling when possible)
- Event-driven thumbnail updates: Brush Editor close, preset save
- Startup refresh of all thumbnails
- Cached active view/window references
- Widget reuse instead of recreation
- Batch UI updates with signal blocking
- Visibility-aware timer pausing
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
    get_exclusive_uncollapse,
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
# Note: Intervals tuned for minimal CPU usage - signals are the PRIMARY detection method
# These are FALLBACK intervals for edge cases where signals don't fire
_BRUSH_CHECK_INTERVAL = 1000  # Fallback - signals handle most cases
_BRUSH_POLL_INTERVAL = 150  # Brush size polling (no signal available for this)
_RESIZE_DEBOUNCE = 75  # Slightly increased for smoother resize
_SAVE_DEBOUNCE = 200  # Debounce for save operations
_DEFERRED_INIT_DELAY = 100  # Delay before starting deferred initialization
_VISIBILITY_SETTLE_DELAY = 50  # Delay after becoming visible before processing

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
        self._setup_krita_signals()  # Connect to Krita signals first
        self._setup_timers()  # Fallback timers (start paused)
        self._init_brush_editor_monitor()  # Monitor Brush Editor Docker state
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
        self._save_pending = False
        self._grids_pending_update = set()
        
        # Cached references (refreshed on relevant signals)
        self._cached_view = None
        self._cached_window = None
        self._cached_preset_dict = None
        self._preset_dict_dirty = True  # Flag to refresh preset dict lazily
        
        # Signal connection state
        self._signals_connected = False
        self._window_signals_connected = False
        
        # Visibility and initialization state
        self._docker_was_visible = False
        self._initialization_complete = False
        self._deferred_init_pending = False
        
        # Timer state tracking (for pause/resume)
        self._timers_paused = False

    def _init_config_paths(self):
        """Setup configuration file paths."""
        config_dir = os.path.join(os.path.dirname(__file__), "config")
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        self.data_file = os.path.join(config_dir, "grids_data.json")
        self.common_config_path = os.path.join(config_dir, "common.json")

    def _load_data(self):
        """Load preset resources and grid data.
        
        Uses lazy loading for preset dictionary to avoid expensive
        resource scanning at startup.
        """
        # Get preset dict (cached after first call)
        self.preset_dict = self._get_preset_dict()
        self.grids, self.grid_counter = load_grids_data(
            self.data_file, self.preset_dict
        )
        self.setup_add_brush_shortcut()
        QApplication.instance().installEventFilter(self)
    
    def _get_preset_dict(self):
        """Get preset dictionary with caching.
        
        Only refreshes from Krita when marked dirty (e.g., after resource changes).
        """
        if self._preset_dict_dirty or self._cached_preset_dict is None:
            self._cached_preset_dict = Krita.instance().resources("preset")
            self._preset_dict_dirty = False
        return self._cached_preset_dict
    
    def _invalidate_preset_cache(self):
        """Mark preset cache as dirty, forcing refresh on next access."""
        self._preset_dict_dirty = True
        self._cached_preset_dict = None
    
    def _setup_krita_signals(self):
        """Connect to Krita's native signals for efficient event handling.
        
        Uses signals instead of polling where available:
        - windowCreated: For deferred window-specific signal connections
        - Notifier signals for resource changes
        """
        try:
            app = Krita.instance()
            notifier = app.notifier()
            
            # Connect to window creation for view-specific signals
            notifier.windowCreated.connect(self._on_window_created)
            
            # Resource change signals (invalidate caches)
            if hasattr(notifier, 'resourceChanged'):
                notifier.resourceChanged.connect(self._on_resource_changed)
            
            self._signals_connected = True
            
            # If window already exists, connect immediately
            if app.activeWindow():
                QTimer.singleShot(_DEFERRED_INIT_DELAY, self._connect_window_signals)
                
        except Exception as e:
            # Fallback to timer-based approach if signals fail
            self._signals_connected = False
    
    def _on_window_created(self):
        """Handle window creation - connect window-specific signals."""
        QTimer.singleShot(_DEFERRED_INIT_DELAY, self._connect_window_signals)
    
    def _connect_window_signals(self):
        """Connect to window and view signals for brush change detection."""
        if self._window_signals_connected:
            return
            
        try:
            app = Krita.instance()
            window = app.activeWindow()
            if not window:
                return
            
            # Cache window reference
            self._cached_window = window
            
            # Connect to view change signal if available
            if hasattr(window, 'activeViewChanged'):
                window.activeViewChanged.connect(self._on_view_changed)
            
            self._window_signals_connected = True
            
            # Initial view cache
            self._update_cached_view()
            
        except Exception:
            pass
    
    def _on_view_changed(self):
        """Handle active view change - update cached view and brush state."""
        self._update_cached_view()
        # Check brush when view changes
        if self._is_docker_visible():
            self.check_brush_change()
    
    def _on_resource_changed(self, resource_type, resource_name):
        """Handle resource changes from Krita.
        
        Invalidates caches and refreshes the changed preset.
        """
        if resource_type == "preset" or resource_type == "brushpreset":
            self._invalidate_preset_cache()
            # Refresh the preset thumbnail if docker is visible
            if resource_name and self._is_docker_visible():
                self._refresh_preset_by_name(resource_name)
    
    def _update_cached_view(self):
        """Update cached view reference."""
        try:
            app = Krita.instance()
            window = app.activeWindow()
            if window:
                self._cached_view = window.activeView()
                self._cached_window = window
            else:
                self._cached_view = None
        except Exception:
            self._cached_view = None

    def _setup_timers(self):
        """Setup periodic timers for brush monitoring.
        
        Timers start paused and are resumed when docker becomes visible.
        This saves CPU when the docker is hidden.
        
        NOTE: Thumbnail change detection is now event-driven (Brush Editor close)
        rather than interval-based, so no thumbnail_check_timer is needed.
        """
        # Brush change timer (fallback when signals unavailable)
        self.brush_check_timer = QTimer()
        self.brush_check_timer.timeout.connect(self._safe_check_brush_change)
        # Don't start yet - will start when docker becomes visible
        
        self._timers_paused = True  # Track timer state
    
    def _start_timers(self):
        """Start/resume all periodic timers."""
        if not self._timers_paused:
            return
        
        self._timers_paused = False
        
        if hasattr(self, 'brush_check_timer') and not self.brush_check_timer.isActive():
            self.brush_check_timer.start(_BRUSH_CHECK_INTERVAL)
        
        if hasattr(self, 'brush_size_poll_timer') and not self.brush_size_poll_timer.isActive():
            self.brush_size_poll_timer.start(_BRUSH_POLL_INTERVAL)
    
    def _pause_timers(self):
        """Pause all periodic timers to save CPU when docker is hidden."""
        if self._timers_paused:
            return
        
        self._timers_paused = True
        
        if hasattr(self, 'brush_check_timer'):
            self.brush_check_timer.stop()
        
        if hasattr(self, 'brush_size_poll_timer'):
            self.brush_size_poll_timer.stop()

    def _is_docker_visible(self):
        """Check if the docker is visible and should process updates.
        
        Returns False if docker is hidden/minimized to skip expensive operations.
        """
        try:
            if not self.isVisible():
                return False
            # Also check if we have a valid parent window
            parent = self.parent()
            if parent and hasattr(parent, 'isVisible') and not parent.isVisible():
                return False
            return True
        except (RuntimeError, AttributeError):
            return False
    
    def showEvent(self, event):
        """Handle docker becoming visible.
        
        Resumes timers and triggers deferred initialization if needed.
        """
        super().showEvent(event)
        
        # Resume timers when docker becomes visible
        QTimer.singleShot(_VISIBILITY_SETTLE_DELAY, self._on_became_visible)
    
    def _on_became_visible(self):
        """Called after docker becomes visible and settles."""
        if not self._is_docker_visible():
            return
        
        # Start/resume timers
        self._start_timers()
        
        # Complete deferred initialization if pending
        if self._deferred_init_pending and not self._initialization_complete:
            self._deferred_init_pending = False
            self._complete_deferred_init()
        
        # Refresh view cache and brush state
        self._update_cached_view()
        self.check_brush_change()
        
        self._docker_was_visible = True
    
    def hideEvent(self, event):
        """Handle docker becoming hidden.
        
        Pauses timers to save CPU.
        """
        super().hideEvent(event)
        
        # Pause timers when docker is hidden
        self._pause_timers()
        self._docker_was_visible = False

    def _safe_check_brush_change(self):
        """Wrapper for check_brush_change with visibility guard."""
        if self._is_docker_visible():
            self.check_brush_change()

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
        """Initialize the docker UI layout.
        
        Uses deferred initialization for expensive operations like
        thumbnail caching to improve startup time.
        """
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
        
        # Mark deferred init as pending - will complete when docker becomes visible
        # This avoids expensive thumbnail loading if docker starts hidden
        if self._is_docker_visible():
            # Docker is already visible, start deferred init after short delay
            QTimer.singleShot(_DEFERRED_INIT_DELAY, self._complete_deferred_init)
        else:
            # Docker is hidden, defer until it becomes visible
            self._deferred_init_pending = True
        
        # Schedule initial layout update
        QTimer.singleShot(_DEFERRED_INIT_DELAY, self._update_all_grids_on_resize)
    
    def _complete_deferred_init(self):
        """Complete deferred initialization tasks.
        
        Called when docker first becomes visible after startup.
        Refreshes all thumbnails to ensure they are up-to-date.
        """
        if self._initialization_complete:
            return
        
        self._initialization_complete = True
        
        # Start timers now that we're visible
        self._start_timers()
        
        # Perform startup thumbnail refresh for all presets
        self._perform_startup_thumbnail_refresh()

    def _create_top_row(self, main_layout):
        """Create top controls row with brush size slider and settings."""
        top_row_layout = QHBoxLayout()
        top_row_layout.setSpacing(4)
        top_row_layout.setContentsMargins(4, 2, 4, 2)

        self.brush_size_slider = QSlider(Qt.Horizontal)
        self.brush_size_slider.setMinimum(1)
        self.brush_size_slider.setMaximum(self.max_brush_size)
        self.brush_size_slider.setValue(100)
        self.brush_size_slider.setMinimumWidth(50)
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
        self.icon_size_slider.setMinimumWidth(50)
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
        # Capture old exclusive_uncollapse value before dialog opens
        old_exclusive_uncollapse = get_exclusive_uncollapse()
        
        dlg = CommonConfigDialog(self.common_config_path, self)
        if not dlg.exec_():
            return
        reload_config()
        
        # Check if exclusive_uncollapse transitioned from OFF to ON
        new_exclusive_uncollapse = get_exclusive_uncollapse()
        if not old_exclusive_uncollapse and new_exclusive_uncollapse:
            self._apply_exclusive_uncollapse_transition()
        
        new_max = self.get_max_brush_size_from_config()
        self.update_max_brush_size(new_max)
        self.setup_add_brush_shortcut()
        self._apply_grid_spacing()
        self.refresh_styles()

    def _apply_exclusive_uncollapse_transition(self):
        """Collapse all grids when exclusive uncollapse is turned on.
        
        Exception: If exactly one grid is the active_grid (singular selection),
        that grid remains uncollapsed. If multiple grids are selected or no
        grid is active, all grids are collapsed.
        """
        # Determine if we have a singular active grid (not multiple selection)
        has_singular_active = (
            self.active_grid is not None and
            len(self.selected_grids) <= 1
        )
        
        # The grid to keep uncollapsed (if any)
        grid_to_keep_uncollapsed = self.active_grid if has_singular_active else None
        
        # Collapse all grids except the singular active one
        for grid_info in self.grids:
            if grid_info == grid_to_keep_uncollapsed:
                # Keep this grid uncollapsed
                if grid_info.get("is_collapsed", False):
                    grid_info["is_collapsed"] = False
                    self._update_collapse_button_icon(grid_info)
                    self.update_grid_visibility(grid_info)
            else:
                # Collapse this grid
                if not grid_info.get("is_collapsed", False):
                    grid_info["is_collapsed"] = True
                    self._update_collapse_button_icon(grid_info)
                    self.update_grid_visibility(grid_info)
        
        # Save the new collapse states
        self.save_grids_data()

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
