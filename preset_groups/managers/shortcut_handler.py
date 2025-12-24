"""Shortcut handling functionality.

Provides mixin class for setting up and handling keyboard shortcuts,
including the add brush shortcut, navigation shortcuts, and event filtering.
"""

from PyQt5.QtWidgets import QApplication, QLineEdit, QTextEdit, QPlainTextEdit, QShortcut
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QKeySequence

from ..utils.data_manager import check_common_config


class ShortcutHandlerMixin:
    """Mixin class providing shortcut handling functionality for the docker widget."""
    
    def setup_add_brush_shortcut(self):
        """Setup global shortcut to add current brush based on config"""
        try:
            from krita import Krita  # type: ignore
            
            config = check_common_config()
            shortcut_key = config.get("shortcut", {}).get("add_brush_to_grid", "W")

            qt_key = self._resolve_key(shortcut_key)
            if qt_key is None:
                qt_key = Qt.Key_W
            self._add_brush_qt_key = qt_key

            parent = self
            try:
                qt_parent = QApplication.activeWindow()
                if qt_parent:
                    parent = qt_parent
            except Exception:
                parent = self

            key_sequence = QKeySequence(self._add_brush_qt_key)
            
            if hasattr(self, 'add_brush_shortcut') and self.add_brush_shortcut:
                try:
                    self.add_brush_shortcut.setEnabled(False)
                    self.add_brush_shortcut.deleteLater()
                except RuntimeError:
                    pass
                finally:
                    self.add_brush_shortcut = None
            
            self.add_brush_shortcut = QShortcut(key_sequence, parent)
            self.add_brush_shortcut.activated.connect(self.add_current_brush)
            self.add_brush_shortcut.setContext(Qt.ApplicationShortcut)

            # Setup navigation shortcuts
            self._setup_navigation_shortcuts()

        except Exception as e:
            print(f"Error setting up add brush shortcut: {e}")

    def _setup_navigation_shortcuts(self):
        """Setup keyboard shortcuts for grid navigation (left/right)."""
        try:
            config = check_common_config()
            shortcut_config = config.get("shortcut", {})
            
            left_key = shortcut_config.get("choose_left_in_grid", ",")
            right_key = shortcut_config.get("choose_right_in_grid", ".")
            
            # Resolve Qt keys for navigation
            self._nav_left_qt_key = self._resolve_key(left_key)
            self._nav_right_qt_key = self._resolve_key(right_key)
            
            # Store wrap-around setting
            self._wrap_around_navigation = shortcut_config.get("wrap_around_navigation", True)
            
        except Exception as e:
            print(f"Error setting up navigation shortcuts: {e}")
            self._nav_left_qt_key = Qt.Key_Comma
            self._nav_right_qt_key = Qt.Key_Period
            self._wrap_around_navigation = True

    # Mapping of special characters to Qt.Key constants
    _SPECIAL_KEY_MAP = {
        ',': Qt.Key_Comma,
        '.': Qt.Key_Period,
        '/': Qt.Key_Slash,
        ';': Qt.Key_Semicolon,
        "'": Qt.Key_Apostrophe,
        '[': Qt.Key_BracketLeft,
        ']': Qt.Key_BracketRight,
        '\\': Qt.Key_Backslash,
        '-': Qt.Key_Minus,
        '=': Qt.Key_Equal,
        '`': Qt.Key_QuoteLeft,
    }

    def _resolve_key(self, key_char):
        """Resolve a single character to its Qt.Key constant.
        
        Handles both special characters (.,;etc) and alphanumeric keys.
        Returns None if the key cannot be resolved.
        """
        if not key_char or not isinstance(key_char, str):
            return None
        
        key_char = key_char.strip()
        if len(key_char) != 1:
            return None
        
        # Check special characters first
        if key_char in self._SPECIAL_KEY_MAP:
            return self._SPECIAL_KEY_MAP[key_char]
        
        # Try standard key resolution (letters and numbers)
        return getattr(Qt, f"Key_{key_char.upper()}", None)

    def _should_ignore_text_input(self, obj):
        """Return True if the focused widget is a text input where typing should pass through."""
        text_widgets = (QLineEdit, QTextEdit, QPlainTextEdit)
        return isinstance(obj, text_widgets)

    def _handle_grid_name_editor_event(self, obj, event):
        """Handle events for inline grid name editor"""
        if not isinstance(obj, QLineEdit) or obj.objectName() != "grid_name_editor":
            return None

        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self._finish_inline_grid_rename(obj, apply_change=False)
            return True
        if event.type() == QEvent.FocusOut:
            self._finish_inline_grid_rename(obj, apply_change=True)
            return False
        return None

    def _is_add_brush_key_pressed(self, event):
        """Check if the add brush shortcut key was pressed"""
        expected_key = getattr(self, "_add_brush_qt_key", Qt.Key_W)
        return event.key() == expected_key and not event.isAutoRepeat()

    def _is_nav_left_key_pressed(self, event):
        """Check if the navigate left shortcut key was pressed"""
        expected_key = getattr(self, "_nav_left_qt_key", Qt.Key_Comma)
        return expected_key is not None and event.key() == expected_key and not event.isAutoRepeat()

    def _is_nav_right_key_pressed(self, event):
        """Check if the navigate right shortcut key was pressed"""
        expected_key = getattr(self, "_nav_right_qt_key", Qt.Key_Period)
        return expected_key is not None and event.key() == expected_key and not event.isAutoRepeat()

    def _handle_add_brush_key_press(self, event):
        """Handle add brush shortcut key press"""
        focus_widget = QApplication.focusWidget()
        if focus_widget and self._should_ignore_text_input(focus_widget):
            return False

        if event.modifiers() in (Qt.NoModifier,):
            self.add_current_brush()
            return True
        return False

    def _handle_nav_left_key_press(self, event):
        """Handle navigate left (choose previous brush) key press"""
        focus_widget = QApplication.focusWidget()
        if focus_widget and self._should_ignore_text_input(focus_widget):
            return False

        if event.modifiers() in (Qt.NoModifier,):
            self.navigate_brush_in_grid(-1)
            return True
        return False

    def _handle_nav_right_key_press(self, event):
        """Handle navigate right (choose next brush) key press"""
        focus_widget = QApplication.focusWidget()
        if focus_widget and self._should_ignore_text_input(focus_widget):
            return False

        if event.modifiers() in (Qt.NoModifier,):
            self.navigate_brush_in_grid(1)
            return True
        return False

    def navigate_brush_in_grid(self, direction):
        """Navigate to adjacent brush in the active grid.
        
        Args:
            direction: -1 for left (previous), 1 for right (next)
        """
        if not self.active_grid:
            return
        
        # Get total button count in active grid
        button_count = self.get_button_count_in_grid(self.active_grid)
        if button_count == 0:
            return
        
        # Get current index
        current_index = self.get_current_button_index_in_active_grid()
        
        # If no button is currently selected in the active grid, select appropriate boundary
        if current_index is None:
            if direction == -1:
                # Navigating left with nothing selected - select last button
                target_index = button_count
            else:
                # Navigating right with nothing selected - select first button
                target_index = 1
        else:
            # Calculate new index
            target_index = current_index + direction
            
            # Check wrap-around setting
            wrap_around = getattr(self, '_wrap_around_navigation', True)
            
            if target_index < 1:
                if wrap_around:
                    target_index = button_count
                else:
                    return  # At left boundary, do nothing
            elif target_index > button_count:
                if wrap_around:
                    target_index = 1
                else:
                    return  # At right boundary, do nothing
        
        # Get the button at target index and select it
        target_button = self.get_button_by_grid_index(self.active_grid, target_index)
        if target_button and hasattr(target_button, 'preset'):
            # Clear any multi-selection
            self.selected_buttons = []
            self.last_selected_button = None
            
            # Select the brush preset (simulates left-click on the button)
            self.select_brush_preset(target_button.preset, source_button=target_button)

    def eventFilter(self, obj, event):
        """
        Global event filter.
        - Handles Esc / focus-out for inline grid name editor.
        - Fallback handler to capture global shortcut when QShortcut is blocked.
        - Handles navigation shortcuts for grid brush selection.
        
        PERFORMANCE CRITICAL: This runs for EVERY event in the application.
        Must return as fast as possible for non-handled events.
        """
        # Fast path: only process KeyPress and specific focus events
        event_type = event.type()
        
        # Most events are not keyboard - exit immediately
        if event_type != QEvent.KeyPress and event_type != QEvent.FocusOut:
            return False
        
        try:
            # Handle inline grid name editor events (FocusOut and KeyPress for Escape)
            result = self._handle_grid_name_editor_event(obj, event)
            if result is not None:
                return result

            # Only process KeyPress events from here
            if event_type == QEvent.KeyPress:
                # Cache the key for quick comparison
                key = event.key()
                
                # Quick check against our configured shortcut keys
                add_key = getattr(self, "_add_brush_qt_key", Qt.Key_W)
                left_key = getattr(self, "_nav_left_qt_key", Qt.Key_Comma)
                right_key = getattr(self, "_nav_right_qt_key", Qt.Key_Period)
                
                # Fast path: if key doesn't match any of our shortcuts, exit immediately
                if key != add_key and key != left_key and key != right_key:
                    return False
                
                # Skip auto-repeat events
                if event.isAutoRepeat():
                    return False
                
                if key == add_key:
                    return self._handle_add_brush_key_press(event)
                elif key == left_key:
                    return self._handle_nav_left_key_press(event)
                elif key == right_key:
                    return self._handle_nav_right_key_press(event)
        except Exception:
            pass
        return False
