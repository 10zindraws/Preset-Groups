"""Drag and drop management functionality.

Provides mixin class for handling drag operations, edge highlighting,
and auto-scrolling during drag.
"""

from PyQt5.QtCore import QTimer, QPoint, QTime
from PyQt5.QtGui import QCursor


class DragManagerMixin:
    """Mixin class providing drag management functionality for the docker widget."""
    
    def init_drag_tracking(self):
        """Initialize drag tracking state and timers"""
        self.dragging_button = None
        self.drag_highlight_timer = QTimer()
        self.drag_highlight_timer.timeout.connect(self.update_drag_highlights)
        self.drag_highlight_timer.setInterval(16)  # ~60fps
        
        # Auto-scroll tracking
        self.auto_scroll_timer = QTimer()
        self.auto_scroll_timer.timeout.connect(self.perform_auto_scroll)
        self.auto_scroll_timer.setInterval(16)  # ~60fps for smooth scrolling
        self.edge_scroll_distance = 0
        self.edge_scroll_direction = 0
        self.edge_touch_start_time = None
        self.base_scroll_speed = 6.0
        
        # Scroll position preservation after autoscroll
        self._autoscroll_used = False
        self._preserved_scroll_position = None
        
        # Scroll position monitoring timer for robust restoration
        self._scroll_monitor_timer = QTimer()
        self._scroll_monitor_timer.timeout.connect(self._monitor_scroll_position)
        self._scroll_monitor_timer.setInterval(16)  # Check frequently
        self._scroll_monitor_start_time = None
        self._scroll_monitor_duration = 600  # Monitor for 600ms after drop
    
    def start_drag_tracking(self, button):
        """Start tracking drag for edge highlighting"""
        self.dragging_button = button
        self._autoscroll_used = False
        self._preserved_scroll_position = None
        # Stop any ongoing scroll monitoring from previous drag
        self._scroll_monitor_timer.stop()
        self._scroll_monitor_start_time = None
        self.drag_highlight_timer.start()
        self.auto_scroll_timer.start()
    
    def stop_drag_tracking(self):
        """Stop tracking drag and clear highlights.
        
        If autoscroll was used during drag, preserve the current scroll position
        and start continuous monitoring to restore it. This handles edge cases where
        Qt's layout system triggers late scroll adjustments, especially when dropping
        at the first/last buttons of the topmost/bottommost grids.
        """
        # Capture scroll position before stopping, if autoscroll was used
        if self._autoscroll_used and hasattr(self, 'scroll_area') and self.scroll_area:
            scroll_bar = self.scroll_area.verticalScrollBar()
            if scroll_bar:
                self._preserved_scroll_position = scroll_bar.value()
                # Start continuous monitoring to catch and correct any scroll jumps
                self._scroll_monitor_start_time = QTime.currentTime()
                self._scroll_monitor_timer.start()
        
        self.dragging_button = None
        self.drag_highlight_timer.stop()
        self.auto_scroll_timer.stop()
        # Clear all edge highlights
        for btn in self.brush_buttons:
            if hasattr(btn, 'clear_edge_highlight'):
                btn.clear_edge_highlight()
    
    def _monitor_scroll_position(self):
        """Continuously monitor and restore scroll position after drag drop.
        
        This runs at 60fps for a fixed duration after drop to catch any
        late scroll adjustments from Qt's layout system, especially for
        edge cases like dropping at first/last buttons of topmost/bottommost grids.
        """
        if self._preserved_scroll_position is None or self._scroll_monitor_start_time is None:
            self._scroll_monitor_timer.stop()
            return
        
        # Check if monitoring period has elapsed
        elapsed_ms = self._scroll_monitor_start_time.msecsTo(QTime.currentTime())
        if elapsed_ms >= self._scroll_monitor_duration:
            # Monitoring complete - clean up
            self._scroll_monitor_timer.stop()
            self._preserved_scroll_position = None
            self._autoscroll_used = False
            self._scroll_monitor_start_time = None
            return
        
        # Restore scroll position if it has drifted
        if hasattr(self, 'scroll_area') and self.scroll_area:
            scroll_bar = self.scroll_area.verticalScrollBar()
            if scroll_bar and scroll_bar.value() != self._preserved_scroll_position:
                scroll_bar.setValue(self._preserved_scroll_position)
    
    def update_drag_highlights(self):
        """Update edge highlights based on cursor position during drag"""
        if not self.dragging_button:
            return
        
        cursor_pos = QCursor.pos()

        # Update auto-scroll edge detection
        self.update_auto_scroll_edge_detection(cursor_pos)
        
        # Find which button the cursor is over
        hovered_button = None
        for btn in self.brush_buttons:
            if btn == self.dragging_button:
                continue
            
            btn_global_pos = btn.mapToGlobal(QPoint(0, 0))
            btn_rect = btn.geometry()
            btn_right = btn_global_pos.x() + btn_rect.width()
            btn_bottom = btn_global_pos.y() + btn_rect.height()
            
            if (btn_global_pos.x() <= cursor_pos.x() <= btn_right and
                btn_global_pos.y() <= cursor_pos.y() <= btn_bottom):
                hovered_button = btn
                break
        
        # Update highlights for all buttons
        for btn in self.brush_buttons:
            if btn == self.dragging_button:
                continue
            
            if btn == hovered_button:
                if hasattr(btn, 'is_cursor_on_left_half'):
                    is_left = btn.is_cursor_on_left_half(cursor_pos)
                    if is_left:
                        btn.highlight_edge('left')
                    else:
                        btn.highlight_edge('right')
            else:
                if hasattr(btn, 'clear_edge_highlight'):
                    btn.clear_edge_highlight()

    def update_auto_scroll_edge_detection(self, cursor_pos):
        """Update auto-scroll edge detection based on cursor position"""
        if not hasattr(self, 'scroll_area') or not self.scroll_area:
            self.edge_scroll_direction = 0
            self.edge_scroll_distance = 0
            self.edge_touch_start_time = None
            return
        
        viewport = self.scroll_area.viewport()
        viewport_global_pos = viewport.mapToGlobal(QPoint(0, 0))
        viewport_height = viewport.height()
        
        cursor_y_relative = cursor_pos.y() - viewport_global_pos.y()
        
        distance_from_top = cursor_y_relative
        distance_from_bottom = viewport_height - cursor_y_relative
        
        SCROLL_ZONE = 30
        
        if distance_from_top <= SCROLL_ZONE:
            self.edge_scroll_direction = -1
            self.edge_scroll_distance = max(0, distance_from_top)
            
            if distance_from_top <= 1:
                if self.edge_touch_start_time is None:
                    self.edge_touch_start_time = QTime.currentTime()
            else:
                self.edge_touch_start_time = None
        elif distance_from_bottom <= SCROLL_ZONE:
            self.edge_scroll_direction = 1
            self.edge_scroll_distance = max(0, distance_from_bottom)
            
            if distance_from_bottom <= 1:
                if self.edge_touch_start_time is None:
                    self.edge_touch_start_time = QTime.currentTime()
            else:
                self.edge_touch_start_time = None
        else:
            self.edge_scroll_direction = 0
            self.edge_scroll_distance = 0
            self.edge_touch_start_time = None
    
    def perform_auto_scroll(self):
        """Perform auto-scrolling based on edge detection"""
        if not self.edge_scroll_direction or not hasattr(self, 'scroll_area') or not self.scroll_area:
            return
        
        SCROLL_ZONE = 30
        
        if self.edge_scroll_distance <= 1 and self.edge_touch_start_time:
            elapsed_ms = self.edge_touch_start_time.msecsTo(QTime.currentTime())
            elapsed_seconds = elapsed_ms / 300.0
            exponential_factor = min(2.0 ** elapsed_seconds, 3.0)
            scroll_speed = self.base_scroll_speed * exponential_factor
        else:
            speed_factor = (SCROLL_ZONE - self.edge_scroll_distance) / SCROLL_ZONE
            scroll_speed = self.base_scroll_speed * (0.1 + 0.9 * speed_factor)
        
        scroll_bar = self.scroll_area.verticalScrollBar()
        if scroll_bar:
            current_value = scroll_bar.value()
            new_value = current_value + (self.edge_scroll_direction * scroll_speed)
            scroll_bar.setValue(int(new_value))
            
            # Mark that autoscroll was used (for scroll position preservation)
            if scroll_bar.value() != current_value:
                self._autoscroll_used = True
