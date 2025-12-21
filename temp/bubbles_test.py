import sys
from PyQt6.QtCore import Qt, QPoint, QRect, QSize, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLayout,
    QSizePolicy,
    QPushButton,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QScrollArea,
)

# --- 1. Custom Flow Layout ---
# PyQt6 doesn't have a built-in FlowLayout, so we must implement one.
# This implementation is adapted from the standard Qt examples.
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, h_spacing=5, v_spacing=5):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self._item_list = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing

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
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        # Add margins to the calculated size
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only):
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(+left, +top, -right, -bottom)
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0
        
        for item in self._item_list:
            widget = item.widget()
            space_x = self._h_spacing
            space_y = self._v_spacing
            
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y() + bottom


# --- 2. Bubble Widget (The Tag) ---
class BubbleWidget(QFrame):
    # Signal emitted when the 'x' is clicked, passing the bubble's unique ID
    delete_requested = pyqtSignal(str)

    def __init__(self, text, bubble_id):
        super().__init__()
        self.bubble_id = bubble_id
        
        # Style the bubble
        self.setObjectName("bubble")
        self.setStyleSheet("""
            #bubble {
                background-color: #E0E0E0;
                border-radius: 15px;
                border: 1px solid #C0C0C0;
            }
            QLabel {
                color: #333333;
                font-weight: bold;
                padding-left: 5px;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                color: #555555;
                font-weight: bold;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #FFCDD2; /* Light red on hover */
                color: #D32F2F;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 5, 5) # Left, Top, Right, Bottom
        layout.setSpacing(5)

        # The Text
        self.label = QLabel(text)
        layout.addWidget(self.label)

        # The 'X' Button
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.remove_self)
        layout.addWidget(self.close_btn)

        # Ensure the widget fits its content snugly
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def remove_self(self):
        self.delete_requested.emit(self.bubble_id)


# --- 3. Main Window (Controller) ---
class TagEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto-Collapsing Filter Bubbles")
        self.resize(400, 300)

        self.tags_data = {} 
        self.next_id = 0
        self.max_area_height = 150  # Cap the height at 150px

        main_layout = QVBoxLayout(self)

        # 1. Input Line
        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Type a tag and press Enter...")
        self.input_line.returnPressed.connect(self.add_tag_from_input)
        main_layout.addWidget(self.input_line)

        # 2. Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        # Start collapsed (Height = 0)
        self.scroll_area.setFixedHeight(0)
        
        # Scroll Content
        self.scroll_content = QWidget()
        self.flow_layout = FlowLayout(self.scroll_content)
        self.flow_layout.setContentsMargins(0, 0, 0, 0) # Tight fit
        self.scroll_area.setWidget(self.scroll_content)
        
        main_layout.addWidget(self.scroll_area)

        # 3. Bottom Widget (To prove the collapsing works)
        self.submit_btn = QPushButton("I sit directly below the input when empty")
        main_layout.addWidget(self.submit_btn)
        
        main_layout.addStretch()

    # --- The Logic to Auto-Resize ---
    def update_area_height(self):
        """
        Calculates the height the FlowLayout WANTS to be,
        and forces the ScrollArea to match it (up to a limit).
        """
        # If no tags, collapse to 0
        if self.flow_layout.count() == 0:
            self.scroll_area.setFixedHeight(0)
            return

        # 1. Get the width available for the bubbles
        # We use viewport().width() to account for scrollbars if they exist
        width = self.scroll_area.viewport().width()

        # 2. Ask FlowLayout: "How tall are you if constrained to this width?"
        needed_height = self.flow_layout.heightForWidth(width)

        # 3. Cap the height
        final_height = min(needed_height, self.max_area_height)

        # 4. Apply
        self.scroll_area.setFixedHeight(final_height)
        
        # 5. Scroll to bottom if we are at the limit (user experience)
        if final_height == self.max_area_height:
             self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()
            )

    # --- Event Handlers ---

    def resizeEvent(self, event):
        """
        If the user resizes the window width, the text might wrap differently.
        We need to recalculate height.
        """
        super().resizeEvent(event)
        self.update_area_height()

    def add_tag_from_input(self):
        text = self.input_line.text().strip()
        if not text: return

        unique_id = str(self.next_id)
        self.tags_data[unique_id] = text
        self.next_id += 1

        self.create_bubble_widget(text, unique_id)
        self.input_line.clear()
        
        # Recalculate height after adding
        self.update_area_height()

    def create_bubble_widget(self, text, unique_id):
        bubble = BubbleWidget(text, unique_id)
        bubble.delete_requested.connect(self.remove_tag)
        self.flow_layout.addWidget(bubble)

    def remove_tag(self, bubble_id):
        if bubble_id in self.tags_data:
            del self.tags_data[bubble_id]

        for i in range(self.flow_layout.count()):
            item = self.flow_layout.itemAt(i)
            widget = item.widget()
            if widget and isinstance(widget, BubbleWidget) and widget.bubble_id == bubble_id:
                self.flow_layout.takeAt(i)
                widget.deleteLater()
                break
        
        # Recalculate height after removing (important! might shrink back to 0)
        # We use a slight timer sometimes for safety, but usually direct call works 
        # providing the widget is gone from layout logic.
        self.update_area_height()
        QTimer.singleShot(0, self.update_area_height)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TagEditor()
    window.show()
    sys.exit(app.exec())
