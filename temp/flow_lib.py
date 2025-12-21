from PyQt6.QtCore import Qt, QPoint, QRect, QSize, QEvent
from PyQt6.QtWidgets import QWidget, QLayout, QScrollArea, QFrame
from PyQt6.QtGui import QPainter, QPen, QColor

class FlowLayout(QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._item_list = []
        self._line_debug_positions = [] 
        
        # Grid Configuration
        self.grid_enabled = False
        self.grid_size = 20
        self.grid_offset = 0
        self.show_debug_lines = False
        
        self.setSpacing(10)

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._item_list.append(item)

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), apply_geometry=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, apply_geometry=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        return size

    # --- Debug Painting ---
    def paint_debug_visuals(self, painter):
        if not self.show_debug_lines:
            return

        pen = QPen(QColor(255, 0, 0, 180)) 
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)

        for y_pos, line_width in self._line_debug_positions:
            painter.drawLine(0, y_pos, line_width, y_pos)

    # --- Core Logic ---
    def _get_alignment_point(self, item, item_height):
        widget = item.widget()
        if widget:
            base_point = widget.property("base_point")
            if base_point is not None and isinstance(base_point, int):
                return base_point
        return item_height // 2

    def _do_layout(self, rect, apply_geometry=False):
        x = rect.x()
        y = rect.y()
        effective_width = rect.width()
        spacing = self.spacing()
        
        if apply_geometry:
            self._line_debug_positions = []

        line_items = []

        def process_line(current_items, current_y, is_dry_run):
            if not current_items:
                return current_y

            max_ascent = 0
            max_descent = 0

            for item in current_items:
                size = item.sizeHint()
                ascent = self._get_alignment_point(item, size.height())
                descent = size.height() - ascent
                max_ascent = max(max_ascent, ascent)
                max_descent = max(max_descent, descent)

            candidate_baseline_y = current_y + max_ascent

            if self.grid_enabled and self.grid_size > 0:
                rel_y = candidate_baseline_y - self.grid_offset
                if rel_y < 0: rel_y = 0
                grid_index = (rel_y + self.grid_size - 1) // self.grid_size
                snapped_y = (grid_index * self.grid_size) + self.grid_offset
                
                final_baseline_y = snapped_y
                while (final_baseline_y - max_ascent) < current_y:
                     final_baseline_y += self.grid_size
            else:
                final_baseline_y = candidate_baseline_y

            if not is_dry_run:
                self._line_debug_positions.append((final_baseline_y, effective_width))

            if not is_dry_run:
                current_x_cursor = rect.x()
                for item in current_items:
                    size = item.sizeHint()
                    item_ascent = self._get_alignment_point(item, size.height())
                    item_y = final_baseline_y - item_ascent
                    item.setGeometry(QRect(QPoint(current_x_cursor, item_y), size))
                    current_x_cursor += size.width() + spacing

            return (final_baseline_y + max_descent) + spacing

        current_x = 0
        current_y_cursor = y
        
        for item in self._item_list:
            size = item.sizeHint()
            widget = item.widget()
            
            force_new_line = False
            if widget:
                force_new_line = widget.property("force_new_line") or False

            next_x = current_x + size.width()
            
            if len(line_items) > 0 and (next_x > effective_width or force_new_line):
                current_y_cursor = process_line(line_items, current_y_cursor, not apply_geometry)
                line_items = []
                current_x = 0
                next_x = size.width()

            line_items.append(item)
            current_x = next_x + spacing

        if line_items:
            current_y_cursor = process_line(line_items, current_y_cursor, not apply_geometry)

        return current_y_cursor - rect.y()


class _FlowWidget(QWidget):
    """Internal widget to handle painting debug lines on top of the layout."""
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.layout():
            painter = QPainter(self)
            self.layout().paint_debug_visuals(painter)

class FlowContainer(QScrollArea):
    def __init__(self, min_height=None, max_height=None, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        
        self._min_height = min_height
        self._max_height = max_height

        self.content_widget = _FlowWidget()
        self.flow_layout = FlowLayout(self.content_widget)
        self.setWidget(self.content_widget)
        
        # --- NEW: Install Event Filter ---
        # We need to catch LayoutRequest on the content widget.
        # This event is fired when a child widget calls updateGeometry().
        self.content_widget.installEventFilter(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")

    def eventFilter(self, obj, event):
        """Monitor the content widget for layout changes."""
        if obj == self.content_widget and event.type() == QEvent.Type.LayoutRequest:
            # A child widget has changed size (or layout is dirty)
            self.adjust_height()
        return super().eventFilter(obj, event)

    def add_widget(self, widget):
        self.flow_layout.addWidget(widget)
        # adjust_height will be triggered by the LayoutRequest automatically, 
        # but for initial addition we might want to force it or just updateGeometry
        self.content_widget.updateGeometry() 

    def set_grid(self, enabled, size=20):
        self.flow_layout.grid_enabled = enabled
        self.flow_layout.grid_size = size
        self.flow_layout.invalidate()
        self.content_widget.update()

    def set_debug(self, enabled):
        self.flow_layout.show_debug_lines = enabled
        self.content_widget.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adjust_height()

    def adjust_height(self):
        content_width = self.viewport().width()
        ideal_height = self.flow_layout.heightForWidth(content_width)
        
        actual_height = ideal_height
        if self.flow_layout.count() == 0:
            actual_height = 0
        else:
            if self._min_height is not None:
                actual_height = max(actual_height, self._min_height)
            if self._max_height is not None:
                actual_height = min(actual_height, self._max_height)

        if self.height() != actual_height:
            self.setFixedHeight(actual_height)
