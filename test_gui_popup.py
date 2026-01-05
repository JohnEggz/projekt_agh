import sys
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLineEdit,
                             QLabel, QListWidget, QPushButton)
from PySide6.QtCore import Qt
import os
import json
import pandas as pd

class TrieManager:
    def __init__(self, source_csv, output_json, id_col, data_col, separator=';'):
        self.source_csv = os.path.abspath(source_csv)
        self.output_json = os.path.abspath(output_json)
        self.id_col = id_col
        self.data_col = data_col
        self.separator = separator
        self.trie_root = {}
        self._load_trie()

    def _get_file_mtime(self, filepath):
        try:
            return os.path.getmtime(filepath)
        except OSError:
            return 0

    def _add_to_trie(self, trie, word, doc_id):
        node = trie
        clean_word = word.lower().strip()
        if not clean_word:
            return

        for char in clean_word:
            if char not in node:
                node[char] = {}
            node = node[char]
        if "__ids__" not in node:
            node["__ids__"] = []
        if doc_id not in node["__ids__"]:
            node["__ids__"].append(doc_id)

    def _generate_trie_if_needed(self):
        input_mtime = self._get_file_mtime(self.source_csv)
        output_mtime = self._get_file_mtime(self.output_json)

        if output_mtime > input_mtime and output_mtime > 0:
            print(f"[{self.output_json}] is up to date. Skipping generation.")
            return

        print(f"Source changed or output missing. Generating Trie from {self.source_csv}...")
        try:
            df = pd.read_csv(self.source_csv, usecols=[self.id_col, self.data_col])
        except (FileNotFoundError, ValueError) as e:
            print(f"Error reading CSV: {e}")
            self.trie_root = {}
            return

        temp_root = {}
        for doc_id, data_str in zip(df[self.id_col], df[self.data_col]):
            if pd.isna(data_str):
                continue
            items = str(data_str).split(self.separator)
            for item in items:
                self._add_to_trie(temp_root, item, doc_id)
        os.makedirs(os.path.dirname(self.output_json), exist_ok=True)
        with open(self.output_json, 'w', encoding='utf-8') as f:
            json.dump(temp_root, f, separators=(',', ':'))
        print("Trie generation complete.")

    def _load_trie(self):
        try:
            with open(self.output_json, 'r', encoding='utf-8') as f:
                self.trie_root = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print("Error: Could not load JSON trie.")
            self.trie_root = {}

    def search(self, prefix):
        """
        Returns a list of full words starting with 'prefix'.
        Returns empty list if input length < 1.
        """
        if not prefix or len(prefix) < 1:
            return []

        prefix = prefix.lower()
        node = self.trie_root
        for char in prefix:
            if char in node:
                node = node[char]
            else:
                return []
        results = []
        self._dfs(node, prefix, results)
        return results

    def _dfs(self, node, current_word, results):
        if "__ids__" in node:
            results.append(current_word)
        for char, child_node in node.items():
            if char != "__ids__":
                self._dfs(child_node, current_word + char, results)

from paths import SEARCH_CSV, INGRIDIENTS_TRIE

CSV_PATH = SEARCH_CSV
JSON_PATH = INGRIDIENTS_TRIE

class FloatingList(QListWidget):
    """
    A custom list widget that floats, auto-scales height,
    and scrolls if content exceeds MAX_HEIGHT.
    """
    MAX_HEIGHT = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet("""
            QListWidget {
                background-color: white;
                border: 1px solid #ccc;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #0078d7; /* Standard blue highlight */
                color: white;
            }
        """)
        self.hide()

    def update_items(self, items):
        self.clear()
        if not items:
            self.hide()
            return
        self.addItems(items)
        row_height = 30
        total_content_height = len(items) * row_height + 5
        final_height = min(total_content_height, self.MAX_HEIGHT)
        self.setFixedHeight(final_height)
        self.show()
        self.raise_()

class MainWindow(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Trie Floating Autocomplete")
        self.setGeometry(100, 100, 400, 300)
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type 'beef'...")
        self.input_field.textChanged.connect(self.on_text_changed)
        layout.addWidget(self.input_field)
        self.other_label = QLabel("I am a widget underneath.\nThe list should float over me.")
        self.other_label.setStyleSheet("background-color: lightgray; padding: 20px;")
        self.other_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.other_label)
        layout.addWidget(QPushButton("Useless Button"))
        layout.addStretch()
        self.setLayout(layout)
        self.suggestion_list = FloatingList(self)
        self.suggestion_list.itemClicked.connect(self.on_item_clicked)

    def on_text_changed(self, text):
        suggestions = self.manager.search(text)
        self.suggestion_list.update_items(suggestions)
        geo = self.input_field.geometry()
        self.suggestion_list.setGeometry(geo.x(), geo.y() + geo.height(), geo.width(), self.suggestion_list.height())

    def on_item_clicked(self, item):
        self.input_field.setText(item.text())
        self.suggestion_list.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.suggestion_list.isHidden():
            geo = self.input_field.geometry()
            self.suggestion_list.move(geo.x(), geo.y() + geo.height())
            self.suggestion_list.setFixedWidth(geo.width())

class LineEditSuggestions(QWidget):
    def __init__(self, line_edit_object: QLineEdit, trie_manager_object: TrieManager) -> None:
        super().__init__()
        pass

if __name__ == "__main__":
    trie_manager = TrieManager(
        source_csv=CSV_PATH,
        output_json=JSON_PATH,
        id_col='id',
        data_col='ingredients_serialized',
        separator=';'
    )

    app = QApplication(sys.argv)
    window = MainWindow(trie_manager)
    window.show()
    sys.exit(app.exec())
