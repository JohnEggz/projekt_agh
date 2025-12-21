import sys
import random
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, 
                             QLabel, QHBoxLayout, QMessageBox)
from flow_lib import FlowContainer

class RemovableBox(QLabel):
    """A widget that deletes itself when Right-Clicked."""
    def __init__(self, text, container_ref):
        super().__init__(text)
        self.container_ref = container_ref
        self.setFixedSize(random.randint(60, 100), random.randint(40, 80))
        self.setStyleSheet(f"""
            background-color: {self.random_color()}; 
            border: 1px solid #555;
            color: white;
            font-weight: bold;
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setToolTip("Right-Click to Delete me")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            print(f"Removing widget: {self.text()}")
            self.container_ref.remove_widget(self)
        else:
            super().mousePressEvent(event)

    def random_color(self):
        # Generate Red-ish colors for "Danger/Removal" theme
        return f"rgb({random.randint(180,255)}, {random.randint(50,100)}, {random.randint(50,100)})"

class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlowLayout: Removal Test")
        self.resize(500, 500)
        
        main_layout = QVBoxLayout(self)

        # --- Controls ---
        btn_layout = QHBoxLayout()
        
        btn_add = QPushButton("Add Widget")
        btn_add.clicked.connect(self.add_item)
        
        btn_remove_last = QPushButton("Remove Last Added")
        btn_remove_last.clicked.connect(self.remove_last_item)
        
        btn_clear = QPushButton("Clear All")
        btn_clear.clicked.connect(self.clear_all)

        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_remove_last)
        btn_layout.addWidget(btn_clear)
        main_layout.addLayout(btn_layout)

        # --- Info ---
        lbl = QLabel("Right-Click any box to delete it.\nThe container height will shrink automatically.")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #666; padding: 5px;")
        main_layout.addWidget(lbl)

        # --- Container ---
        # Min Height 0 to prove it can collapse completely
        self.flow_container = FlowContainer(min_height=0, max_height=350)
        self.flow_container.content_widget.setStyleSheet("background-color: #eeeeee; border: 1px dashed #999;")
        
        main_layout.addWidget(self.flow_container)
        main_layout.addStretch()

        # Add initial items
        for _ in range(5):
            self.add_item()

    def add_item(self):
        count = self.flow_container.flow_layout.count()
        wid = RemovableBox(f"Item {count + 1}", self.flow_container)
        self.flow_container.add_widget(wid)

    def remove_last_item(self):
        count = self.flow_container.flow_layout.count()
        if count > 0:
            # Get the last LayoutItem
            item = self.flow_container.flow_layout.itemAt(count - 1)
            if item and item.widget():
                self.flow_container.remove_widget(item.widget())
        else:
            QMessageBox.information(self, "Empty", "No widgets left to remove!")

    def clear_all(self):
        # Loop backwards when removing to avoid index shifting issues
        layout = self.flow_container.flow_layout
        while layout.count() > 0:
            item = layout.itemAt(0)
            if item.widget():
                self.flow_container.remove_widget(item.widget())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
