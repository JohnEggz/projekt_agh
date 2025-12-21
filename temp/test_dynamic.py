import sys
import random
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, 
                             QLabel, QCheckBox)
from flow_lib import FlowContainer

class ResizableBox(QPushButton):
    """A custom widget that changes its size when clicked."""
    def __init__(self, text, sizes):
        super().__init__(text)
        self._sizes = sizes # List of (width, height) tuples
        self._current_idx = 0
        self.setStyleSheet("""
            QPushButton {
                background-color: #3498db; 
                color: white; 
                border: 2px solid #2980b9; 
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #5dade2; }
        """)
        self.clicked.connect(self.cycle_size)
        self.update_label()

    def cycle_size(self):
        self._current_idx = (self._current_idx + 1) % len(self._sizes)
        self.update_label()
        
        # CRITICAL: Notify layout system that our sizeHint has changed
        self.updateGeometry()

    def update_label(self):
        w, h = self._sizes[self._current_idx]
        self.setText(f"Click Me\n{w}x{h}")

    def sizeHint(self):
        w, h = self._sizes[self._current_idx]
        return QSize(w, h)

class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlowLayout: Dynamic Resizing Test")
        self.resize(500, 600)
        
        main_layout = QVBoxLayout(self)

        # Controls
        btn_add = QPushButton("Add Dynamic Widget")
        btn_add.clicked.connect(self.add_dynamic_item)
        
        chk_debug = QCheckBox("Show Debug Lines")
        chk_debug.setStyleSheet("color: red;")
        chk_debug.toggled.connect(self.toggle_debug)
        
        main_layout.addWidget(btn_add)
        main_layout.addWidget(chk_debug)
        
        # Instructions
        lbl = QLabel("Click the blue boxes to resize them.\nThe Layout should reflow automatically.")
        lbl.setStyleSheet("color: #555; font-style: italic;")
        main_layout.addWidget(lbl)

        # Container
        self.flow_container = FlowContainer(min_height=100, max_height=400)
        self.flow_container.content_widget.setStyleSheet("background-color: #f0f0f0;")
        
        main_layout.addWidget(self.flow_container)
        main_layout.addStretch()

    def add_dynamic_item(self):
        # Define 3 states for the widget
        sizes = [
            (80, 40),   # Small
            (150, 80),  # Large (Might force wrap)
            (60, 120)   # Tall (Changes line height)
        ]
        
        wid = ResizableBox("Box", sizes)
        
        # Randomly assign a base point for variety
        if random.random() > 0.5:
            wid.setProperty("base_point", 20)
            
        self.flow_container.add_widget(wid)

    def toggle_debug(self, checked):
        self.flow_container.set_debug(checked)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
