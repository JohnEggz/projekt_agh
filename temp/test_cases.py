import sys
import random
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QCheckBox
from flow_lib import FlowContainer

class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlowLayout with Debug Lines")
        self.resize(600, 600)
        
        main_layout = QVBoxLayout(self)

        # --- Controls ---
        btn_add = QPushButton("Add Widget")
        btn_add.clicked.connect(self.add_item)
        
        chk_grid = QCheckBox("Enable Grid Snapping (40px)")
        chk_grid.toggled.connect(self.toggle_grid)
        
        chk_debug = QCheckBox("Show Alignment Debug Lines")
        chk_debug.setStyleSheet("color: red; font-weight: bold;")
        chk_debug.toggled.connect(self.toggle_debug)
        
        main_layout.addWidget(btn_add)
        main_layout.addWidget(chk_grid)
        main_layout.addWidget(chk_debug)
        
        # --- Container ---
        lbl_info = QLabel("The red dashed lines show exactly where the children are aligned (Y-Axis).")
        main_layout.addWidget(lbl_info)

        self.flow_container = FlowContainer(min_height=100, max_height=400)
        self.flow_container.content_widget.setStyleSheet("background-color: #f9f9f9;")
        
        main_layout.addWidget(self.flow_container)
        main_layout.addStretch()

    def add_item(self):
        h = random.randint(30, 80)
        w = random.randint(60, 120)
        
        wid = QLabel(f"{h}px")
        wid.setFixedSize(w, h)
        wid.setStyleSheet(f"background-color: {self.random_color()}; border: 1px solid #555;")
        wid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 1. Force New Line
        if random.random() < 0.15:
            wid.setProperty("force_new_line", True)
            wid.setText(wid.text() + "\n(Force New)")

        # 2. Base Point (Alignment Axis)
        if random.random() < 0.6:
            # Align near the top (e.g., 15px down)
            base_p = 15
            wid.setProperty("base_point", base_p)
            wid.setText(wid.text() + f"\nBP:{base_p}")
        else:
            # Default (Middle)
            wid.setText(wid.text() + "\nBP:Mid")

        self.flow_container.add_widget(wid)
        self.flow_container.adjust_height()

    def toggle_grid(self, checked):
        self.flow_container.set_grid(checked, size=40)

    def toggle_debug(self, checked):
        self.flow_container.set_debug(checked)

    def random_color(self):
        return f"rgb({random.randint(200,240)}, {random.randint(200,240)}, {random.randint(200,240)})"

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
