import sys
import pprint
import json
import os
import csv
import ast
from typing import List, Optional
import pandas as pd
import orjson
import subprocess


from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from PySide6.QtCore import (
    Qt,
    QRect,
    QSize,
    QPoint,
    QTimer,
    Signal,
    QObject,
    QEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLayout,
    QLayoutItem,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
    QStackedWidget,
    QFrame,
    QListWidget,
)

from paths import RECIPES_FOUND, DISPLAY_CSV, SEARCH_CSV, INGRIDIENTS_TRIE, USER_OUTPUT

def _convert_sets_to_lists(obj):
    if isinstance(obj, dict):
        return {k: _convert_sets_to_lists(v) for k, v in obj.items()}
    if isinstance(obj, set):
        return sorted(list(obj))
    return obj

def _create_trie_from_csv(
    source_csv: str,
    output_json: str,
    id_col: str,
    data_col: str,
    separator: str,
):
    print("Reading CSV and preprocessing data...")
    df = pd.read_csv(source_csv, usecols=[id_col, data_col]).dropna()

    doc_ids = df[id_col].tolist()
    items_data = df[data_col].str.lower().tolist()
    del df

    print("Building Trie...")
    trie_root = {}
    for doc_id, item_str in zip(doc_ids, items_data):
        items = [x.strip() for x in item_str.split(separator) if x.strip()]
        for word in items:
            node = trie_root
            for char in word:
                node = node.setdefault(char, {})
            node.setdefault("__ids__", set()).add(doc_id)

    print("Converting sets to lists for serialization...")
    trie_root = _convert_sets_to_lists(trie_root)

    print(f"Writing Trie to {output_json}...")
    os.makedirs(os.path.dirname(os.path.abspath(output_json)), exist_ok=True)
    if orjson:
        with open(output_json, 'wb') as f:
            f.write(orjson.dumps(trie_root))
    else:
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(trie_root, f, separators=(',', ':'))
    print("Trie generation complete.")
    return trie_root

class TrieHandler:
    def __init__(
        self,
        filepath: str,
        source_csv: str = None,
        id_col: str = None,
        data_col: str = None,
        separator: str = ';',
    ):
        self.filepath = filepath
        self.root = {}
        self._load_or_generate(source_csv, id_col, data_col, separator)

    def _load_or_generate(
        self, source_csv: str, id_col: str, data_col: str, separator: str
    ):
        if os.path.exists(self.filepath):
            print(f"Loading Trie from {self.filepath}...")
            try:
                if orjson:
                    with open(self.filepath, "rb") as f:
                        self.root = orjson.loads(f.read())
                else:
                    with open(self.filepath, "r", encoding="utf-8") as f:
                        self.root = json.load(f)
            except Exception as e:
                print(f"Error loading Trie: {e}. Trie will be empty.")
                self.root = {}
            return
        if source_csv and id_col and data_col:
            print(f"Trie file not found: {self.filepath}. Generating...")
            self.root = _create_trie_from_csv(
                source_csv=source_csv,
                output_json=self.filepath,
                id_col=id_col,
                data_col=data_col,
                separator=separator,
            )
        else:
            print(f"Trie file not found: {self.filepath}. "
                  "Generation arguments not provided. Trie will be empty.")

    def get_suggestions(self, prefix: str, limit: int = 5) -> list[str]:
        if not prefix or not self.root:
            return []

        prefix = prefix.lower()
        node = self.root
        for char in prefix:
            if char not in node:
                return []
            node = node[char]
        results = []
        stack = [(node, prefix)]
        while stack and len(results) < limit:
            current_node, current_word = stack.pop()
            if "__ids__" in current_node:
                results.append(current_word)
            for char, next_node in reversed(list(current_node.items())):
                if char != "__ids__":
                    stack.append((next_node, current_word + char))
        return results

    def is_valid_ingredient(self, word: str) -> bool:
        if not word or not self.root:
            return False
        node = self.root
        for char in word.lower():
            if char not in node:
                return False
            node = node[char]
        return "__ids__" in node

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
        self.setStyleSheet(
            """
            QListWidget {
                background-color: white;
                border: 1px solid #ccc;
                font-size: 14px;
                border-radius: 5px;
            }
            QListWidget::item {
                padding: 5px;
                color: black;
            }
            QListWidget::item:selected {
                background-color: #0078d7;
                color: white;
            }
        """
        )
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

class ClickableCard(QFrame):
    clicked = Signal(int)

    def __init__(self, recipe_id: int, parent=None):
        super().__init__(parent)
        self.recipe_id = recipe_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.recipe_id)
        super().mouseReleaseEvent(event)

class BubbleWidget(QFrame):
    def __init__(self, text: str, parent_area: "FlowScrollArea"):
        super().__init__()
        self._text = text
        self._parent_area = parent_area
        self.setObjectName("bubble")
        self.setStyleSheet(
            """
            QFrame#bubble {
                background-color: #e0e0e0;
                border-radius: 15px;
                border: 1px solid #ccc;
            }
            QLabel { color: #333; font-weight: 500; }
            QPushButton {
                background-color: transparent;
                color: #555;
                font-weight: bold;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover { background-color: #d0d0d0; color: red; }
        """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)
        lbl = QLabel(text)
        layout.addWidget(lbl)
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(20, 20)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self._remove_self)
        layout.addWidget(btn_close)

        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def text(self) -> str:
        return self._text

    def _remove_self(self):
        if self._parent_area:
            self._parent_area.removeWidget(self)

class AutocompleteLineEdit(QLineEdit):
    def __init__(self, trie_handler: TrieHandler, parent=None):
        super().__init__(parent)
        self.trie = trie_handler
        self.setPlaceholderText("Type ingredient...")
        self.popup = None

        self.textEdited.connect(self._on_text_edited)
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self and self.popup and self.popup.isVisible():
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()
                if key == Qt.Key.Key_Down:
                    idx = self.popup.currentRow()
                    if idx < self.popup.count() - 1:
                        self.popup.setCurrentRow(idx + 1)
                    elif idx == -1 and self.popup.count() > 0:
                        self.popup.setCurrentRow(0)
                    return True
                elif key == Qt.Key.Key_Up:
                    idx = self.popup.currentRow()
                    if idx > 0:
                        self.popup.setCurrentRow(idx - 1)
                    return True
                elif key == Qt.Key.Key_Enter or key == Qt.Key.Key_Return:
                    if self.popup.currentItem():
                        self._complete_text(self.popup.currentItem().text())
                        return True
        return super().eventFilter(obj, event)

    def _on_text_edited(self, text):
        if not self.popup:
            self.popup = FloatingList(self.window())
            self.popup.itemClicked.connect(self._on_item_clicked)
        if len(text) < 2:
            self.popup.hide()
            return

        suggestions = self.trie.get_suggestions(text)
        if not suggestions:
            self.popup.hide()
            return
        self.popup.update_items(suggestions)
        self.popup.setCurrentRow(-1)
        global_pos = self.mapToGlobal(QPoint(0, self.height()))
        window_pos = self.window().mapFromGlobal(global_pos)

        self.popup.move(window_pos)
        self.popup.setFixedWidth(self.width())

    def _on_item_clicked(self, item):
        self._complete_text(item.text())

    def _complete_text(self, text):
        self.setText(text)
        if self.popup:
            self.popup.hide()
        self.setFocus()

    def focusOutEvent(self, event):
        if self.popup and not self.popup.hasFocus():
            self.popup.hide()
        super().focusOutEvent(event)

class FlowLayout(QLayout):
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        margin: int = 0,
        h_spacing: int = -1,
        v_spacing: int = -1,
    ):
        super().__init__(parent)
        self._item_list: List[QLayoutItem] = []
        self._h_space = h_spacing
        self._v_space = v_spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item: QLayoutItem):
        self._item_list.append(item)

    def count(self) -> int:
        return len(self._item_list)

    def itemAt(self, index: int) -> Optional[QLayoutItem]:
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index: int) -> Optional[QLayoutItem]:
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(), margins.top() + margins.bottom()
        )
        return size

    def getWidgets(self) -> List[QWidget]:
        widgets = []
        for item in self._item_list:
            widget = item.widget()
            if widget:
                widgets.append(widget)
        return widgets

    def horizontalSpacing(self) -> int:
        if self._h_space >= 0:
            return self._h_space
        return self.smartSpacing(QStyle.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self) -> int:
        if self._v_space >= 0:
            return self._v_space
        return self.smartSpacing(QStyle.PM_LayoutVerticalSpacing)

    def smartSpacing(self, pm: QStyle.PixelMetric) -> int:
        parent = self.parent()
        if not parent:
            return -1
        if parent.isWidgetType():
            return parent.style().pixelMetric(pm, None, parent)
        return QApplication.style().pixelMetric(pm, None, None)

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(+left, +top, -right, -bottom)
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0
        spacing_x = self.horizontalSpacing()
        spacing_y = self.verticalSpacing()
        if spacing_x == -1:
            spacing_x = 10
        if spacing_y == -1:
            spacing_y = 10

        for item in self._item_list:
            next_x = x + item.sizeHint().width() + spacing_x
            if (
                next_x - spacing_x > effective_rect.right()
                and line_height > 0
            ):
                x = effective_rect.x()
                y = y + line_height + spacing_y
                next_x = x + item.sizeHint().width() + spacing_x
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        return y + line_height - rect.y() + top + bottom

class FlowScrollArea(QScrollArea):
    def __init__(
        self, height: Optional[int] = 50, parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._container = QWidget()
        self._container.setObjectName("flowContainer")
        self._flow_layout = FlowLayout(self._container)
        self.setWidget(self._container)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        if height is not None:
            self.setFixedHeight(height)

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.updateGeometry()

    def addWidget(self, widget: QWidget):
        self._flow_layout.addWidget(widget)

    def getWidgets(self) -> List[QWidget]:
        return self._flow_layout.getWidgets()

    def removeWidget(self, widget: QWidget):
        self._flow_layout.removeWidget(widget)
        widget.deleteLater()

    def clear(self):
        item = self._flow_layout.takeAt(0)
        while item:
            if item.widget():
                item.widget().deleteLater()
            item = self._flow_layout.takeAt(0)

    def setSpacing(self, h_spacing: int, v_spacing: int):
        self._flow_layout._h_space = h_spacing
        self._flow_layout._v_space = v_spacing
        self._flow_layout.update()

    def setContentsMargins(self, left: int, top: int, right: int, bottom: int):
        self._flow_layout.setContentsMargins(left, top, right, bottom)

    def sizeHint(self) -> QSize:
        inner_size = self._container.sizeHint()
        height = inner_size.height() + self.frameWidth() * 2
        return QSize(super().sizeHint().width(), height)

class Storage:
    def __init__(self) -> None:
        self._subscribers: list[tuple[str, object]] = []

    def add(self, key_name: str, object_instance: object):
        new_entry: tuple[str, object] = (key_name, object_instance)
        self._subscribers.append(new_entry)

    def _objects_to_dict(self) -> dict[str, str | list[str]]:
        def _object_to_data(object_instance: object) -> str | list[str]:
            if hasattr(object_instance, "text"):
                return object_instance.text()
            match object_instance:
                case str():
                    return object_instance
                case int():
                    return str(object_instance)
                case FlowScrollArea():
                    items = []
                    widgets = object_instance.getWidgets()
                    for widget in widgets:
                        item = _object_to_data(widget)
                        if not item or item == "":
                            continue
                        items.append(item)
                    return items
                case _:
                    return ""

        output: dict[str, str | list[str]] = {}
        for pair in self._subscribers:
            key_name, object_instance = pair
            widget_contents = _object_to_data(object_instance)
            if (
                not widget_contents
                or widget_contents == ""
                or widget_contents == []
            ):
                continue
            if not key_name or key_name == "":
                print(
                    "WARNING: Passed a empty key_name for contents",
                    f"'{widget_contents}'",
                )
                continue
            output[key_name] = widget_contents
        return output

    def get_data(self) -> dict[str, str | list[str]]:
        return self._objects_to_dict()

storage = Storage()

class RecipeFileHandler(QObject, FileSystemEventHandler):
    file_changed = Signal()

    def __init__(self, target_filename):
        super().__init__()
        self.target_filename = target_filename

    def _process_event(self, event):
        is_target = False
        if hasattr(event, "dest_path"):
            if os.path.basename(event.dest_path) == self.target_filename:
                is_target = True

        if os.path.basename(event.src_path) == self.target_filename:
            is_target = True

        if is_target:
            self.file_changed.emit()

    def on_modified(self, event):
        self._process_event(event)

    def on_created(self, event):
        self._process_event(event)

    def on_deleted(self, event):
        self._process_event(event)

    def on_moved(self, event):
        self._process_event(event)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wyszukiwarka Przepisów")
        self.setGeometry(100, 100, 1000, 700)
        self.setObjectName("mainWindow")
        self.recipe_db = {}
        self.current_results_ids = []
        self.current_accuracies = {}
        self.current_detail_id = None

        self._load_recipe_db()
        self.trie_handler = TrieHandler(
            INGRIDIENTS_TRIE,
            SEARCH_CSV,
            "id",
            "ingredients_serialized",
            ";"
        )

        self._ui()
        self._apply_stylesheet()

        self._setup_file_watcher()
        self.reload_results_from_file()

    def _apply_stylesheet(self):
        stylesheet = """
            QWidget#mainWindow {
                background-color: #f0f2f5;
            }
            QLabel#appTitle1, QLabel#appTitle2 {
                font-size: 28px;
                font-weight: bold;
                color: #2c3e50;
            }
            QLabel {
                font-size: 14px;
                color: #34495e;
                font-weight: 500;
            }

            QLineEdit {
                background-color: white;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
            }
            QScrollArea#leftMenuScrollArea {
                border: none;
            }
            QWidget#flowContainer {
                background-color: #f8f9fa;
                border: 1px dashed #ccc;
                border-radius: 5px;
            }

            QPushButton#searchButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 12px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton#searchButton:hover {
                background-color: #2980b9;
            }

            QWidget#resultsPanel {
                background-color: #ffffff;
                border-left: 1px solid #e0e0e0;
            }
            QWidget#resultCard {
                background-color: #f8f9fa;
                border: 1px solid #d0d0d0;
                border-radius: 12px;
            }
            QLabel#title {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
            }
            QLabel#desc {
                font-size: 13px;
                color: #7f8c8d;
            }
            QLabel#stat, QLabel#matchStat {
                font-size: 12px;
                font-weight: bold;
                color: #34495e;
            }

            QPushButton {
                background-color: #e0e0e0;
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 8px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
        """
        self.setStyleSheet(stylesheet)

    def _ui(self):
        self.stack = QStackedWidget(self)
        search_widget = QWidget()
        search_layout = QHBoxLayout(search_widget)
        search_layout.setContentsMargins(15, 15, 0, 15)
        search_layout.setSpacing(0)
        left_menu_container = QWidget()
        left_menu_container.setFixedWidth(350)
        left_menu = QVBoxLayout(left_menu_container)
        left_menu.setSpacing(15)

        search_button = QPushButton("Search")
        search_button.setObjectName("searchButton")
        search_button.clicked.connect(self.on_search_press)
        left_menu.addWidget(self._ui_app_title())
        left_menu.addWidget(self._ui_scrollable_menu())
        left_menu.addWidget(search_button)
        self.results_panel = QWidget()
        self.results_panel.setObjectName("resultsPanel")
        self.right_menu_layout = QVBoxLayout(self.results_panel)
        self.right_menu_layout.setContentsMargins(20, 10, 20, 10)
        self.right_menu_layout.setSpacing(15)

        search_layout.addWidget(left_menu_container)
        search_layout.addWidget(self.results_panel, stretch=1)

        self.stack.addWidget(search_widget)
        self.detail_view = self._ui_detail_view_layer()
        self.stack.addWidget(self.detail_view)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.stack)

    def _ui_app_title(self) -> QWidget:
        app_title_widget = QWidget()
        app_title = QVBoxLayout(app_title_widget)
        app_title.setContentsMargins(0, 0, 0, 0)
        app_title.setSpacing(0)
        lbl1 = QLabel("Wyszukiwarka")
        lbl1.setObjectName("appTitle1")
        lbl2 = QLabel("Przepisów")
        lbl2.setObjectName("appTitle2")

        app_title.addWidget(lbl1)
        app_title.addWidget(lbl2)
        app_title_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        return app_title_widget

    def _ui_detail_view_layer(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        self.detail_header_container = QVBoxLayout()
        layout.addLayout(self.detail_header_container)
        scroll = QScrollArea()
        scroll.setObjectName("leftMenuScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.detail_content_widget = QWidget()
        self.detail_content_layout = QVBoxLayout(self.detail_content_widget)
        self.detail_content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.detail_content_layout.setContentsMargins(10, 10, 10, 10)

        scroll.setWidget(self.detail_content_widget)
        layout.addWidget(scroll, stretch=1)
        controls_widget = QWidget()
        controls = QHBoxLayout(controls_widget)

        btn_prev = QPushButton("Previous")
        btn_prev.clicked.connect(self.action_prev_recipe)

        btn_close = QPushButton("Close / Back")
        btn_close.clicked.connect(self.action_close_detail)
        btn_close.setStyleSheet(
            """
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                border: 1px solid #c0392b;
            }
            QPushButton:hover { background-color: #c0392b; }
        """
        )

        btn_next = QPushButton("Next")
        btn_next.clicked.connect(self.action_next_recipe)

        controls.addWidget(btn_prev)
        controls.addWidget(btn_close)
        controls.addWidget(btn_next)

        layout.addWidget(controls_widget)

        return container

    def _ui_scrollable_menu(self) -> QScrollArea:
        content_widget = QWidget()
        filter_menu = QVBoxLayout(content_widget)
        filter_menu.setSpacing(15)
        filter_menu.addWidget(self._ui_recipe_name())
        filter_menu.addWidget(self._ui_liked_box())
        filter_menu.addWidget(self._ui_disliked_box())

        filter_menu.addSpacing(10)

        filter_menu.addWidget(self._ui_min_max_input("Rating (0-5)", "rating"))
        filter_menu.addWidget(
            self._ui_min_max_input("Time (Minutes)", "minutes")
        )
        filter_menu.addWidget(self._ui_min_max_input("Calories", "cal"))
        filter_menu.addWidget(self._ui_min_max_input("Protein (g)", "prot"))
        filter_menu.addWidget(self._ui_min_max_input("Fat (g)", "fat"))

        filter_menu.addStretch()

        scrollable_menu = QScrollArea()
        scrollable_menu.setObjectName("leftMenuScrollArea")
        scrollable_menu.setWidget(content_widget)
        scrollable_menu.setWidgetResizable(True)
        return scrollable_menu

    def _ui_min_max_input(self, label_text: str, key_prefix: str) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        lbl = QLabel(label_text)
        layout.addWidget(lbl)
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)
        min_edit = QLineEdit()
        min_edit.setPlaceholderText("Min")
        storage.add(f"{key_prefix}_min", min_edit)
        sep = QLabel("-")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        max_edit = QLineEdit()
        max_edit.setPlaceholderText("Max")
        storage.add(f"{key_prefix}_max", max_edit)

        row_layout.addWidget(min_edit)
        row_layout.addWidget(sep)
        row_layout.addWidget(max_edit)

        layout.addWidget(row_widget)

        return container

    def _ui_recipe_name(self) -> QWidget:
        output_widget = QWidget()
        layout = QVBoxLayout(output_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        label = QLabel("Nazwa Przepisu")
        line_edit = QLineEdit()
        storage.add("recipe_name", line_edit)

        layout.addWidget(label)
        layout.addWidget(line_edit)

        return output_widget

    def _ui_liked_box(self) -> QWidget:
        output_widget = QWidget()
        layout = QVBoxLayout(output_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        label = QLabel("Składniki Lubiane")
        line_edit = AutocompleteLineEdit(self.trie_handler, output_widget)

        flow_area = FlowScrollArea()
        storage.add("ingredients_liked", flow_area)

        self._setup_bubble_input(line_edit, flow_area)

        layout.addWidget(label)
        layout.addWidget(line_edit)
        layout.addWidget(flow_area)

        return output_widget

    def _ui_disliked_box(self) -> QWidget:
        output_widget = QWidget()
        layout = QVBoxLayout(output_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        label = QLabel("Składniki Nielubiane")
        line_edit = AutocompleteLineEdit(self.trie_handler, output_widget)

        flow_area = FlowScrollArea()
        storage.add("ingredients_disliked", flow_area)

        self._setup_bubble_input(line_edit, flow_area)

        layout.addWidget(label)
        layout.addWidget(line_edit)
        layout.addWidget(flow_area)

        return output_widget

    def _setup_bubble_input(
        self, line_edit: AutocompleteLineEdit, flow_area: FlowScrollArea
    ):
        def add_bubble():
            text = line_edit.text().strip()
            if text and self.trie_handler.is_valid_ingredient(text):
                bubble = BubbleWidget(text, flow_area)
                flow_area.addWidget(bubble)
                line_edit.clear()
                if line_edit.popup:
                    line_edit.popup.hide()
            else:
                print(f"Invalid ingredient: {text}")

        line_edit.returnPressed.connect(add_bubble)

    def _load_recipe_db(self):
        if os.path.exists(DISPLAY_CSV):
            try:
                with open(DISPLAY_CSV, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            r_id = int(row["id"])
                            if r_id not in self.recipe_db:
                                self.recipe_db[r_id] = {}

                            self.recipe_db[r_id]["name"] = row.get(
                                "name", "Unknown"
                            )
                            self.recipe_db[r_id]["description"] = row.get(
                                "description", ""
                            )
                            try:
                                self.recipe_db[r_id]["steps"] = ast.literal_eval(
                                    row.get("steps", "[]")
                                )
                            except:
                                self.recipe_db[r_id]["steps"] = []

                            try:
                                self.recipe_db[r_id][
                                    "ingredients"
                                ] = ast.literal_eval(
                                    row.get("ingredients", "[]")
                                )
                            except:
                                self.recipe_db[r_id]["ingredients"] = []

                        except ValueError:
                            continue
            except Exception as e:
                print(f"Error loading DISPLAY_CSV: {e}")
        if os.path.exists(SEARCH_CSV):
            try:
                with open(SEARCH_CSV, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            r_id = int(row["id"])
                            if r_id not in self.recipe_db:
                                self.recipe_db[r_id] = {}

                            raw_rating = row.get("avg_rating", "-")
                            try:
                                self.recipe_db[r_id]["rating"] = f"{float(raw_rating):.2f}"
                            except (ValueError, TypeError):
                                self.recipe_db[r_id]["rating"] = "-"

                            self.recipe_db[r_id]["minutes"] = row.get(
                                "minutes", "-"
                            )
                            self.recipe_db[r_id]["cal"] = row.get("cal", "-")
                            self.recipe_db[r_id]["prot"] = row.get("prot", "-")
                            self.recipe_db[r_id]["fat"] = row.get("fat", "-")
                        except ValueError:
                            continue
            except Exception as e:
                print(f"Error loading SEARCH_CSV: {e}")

    def on_search_press(self):
        result_data = storage.get_data()
        pprint.pprint(result_data)
        json_str = json.dumps(result_data, indent=4)

        with open(USER_OUTPUT, "w") as f:
            f.write(json_str)

        try:
            subprocess.run(["./recipe_matcher", USER_OUTPUT, SEARCH_CSV, RECIPES_FOUND])
        except Exception as e:
            print(e)

    def _setup_file_watcher(self):
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(200)
        self.debounce_timer.timeout.connect(self.reload_results_from_file)
        folder = os.path.dirname(RECIPES_FOUND)
        filename = os.path.basename(RECIPES_FOUND)

        if not os.path.exists(folder):
            print(
                f"Warning: Folder {folder} does not exist. Watcher might fail."
            )
            return

        self.event_handler = RecipeFileHandler(filename)
        self.event_handler.file_changed.connect(self.on_file_change_signal)

        self.observer = Observer()
        self.observer.schedule(self.event_handler, folder, recursive=False)
        self.observer.start()

    def closeEvent(self, event):
        if hasattr(self, "observer"):
            self.observer.stop()
            self.observer.join()
        event.accept()

    def on_file_change_signal(self):
        self.debounce_timer.start()

    def reload_results_from_file(self):
        if not os.path.exists(RECIPES_FOUND):
            self._show_placeholder("File not found. Waiting for recipes...")
            return

        try:
            with open(RECIPES_FOUND, "r") as f:
                content = f.read().strip()
                if not content:
                    self._show_placeholder("File is empty...")
                    return
                data = json.loads(content)
            if not isinstance(data, list):
                self._show_placeholder("Invalid data format: Expected a List")
                return

            self.populate_results(data)

        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"Error reading file: {e}")
            self._show_placeholder(f"Error reading file: {e}")

    def populate_results(self, results: list):
        self._clear_right_menu()
        self.current_results_ids.clear()
        self.current_accuracies.clear()

        valid_items_count = 0
        if not results:
            self._show_placeholder("No matching recipes found")
            return

        for data in results:
            if not isinstance(data, dict):
                continue
            if "id" not in data or "accuracy" not in data:
                continue

            r_id = data.get("id")
            accuracy = data.get("accuracy", 0.0)
            self.current_results_ids.append(r_id)
            self.current_accuracies[r_id] = accuracy
            widget = self._create_result_widget(data)
            self.right_menu_layout.addWidget(widget)
            valid_items_count += 1

        self.right_menu_layout.addStretch()

    def _show_placeholder(self, message: str):
        self._clear_right_menu()

        label = QLabel(message)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            "color: #888888; font-size: 16px; padding: 20px;"
        )

        self.right_menu_layout.addWidget(label)
        self.right_menu_layout.addStretch()

    def _clear_right_menu(self):
        """Removes all widgets from the right menu layout."""
        if self.right_menu_layout.count():
            stretch_item = self.right_menu_layout.takeAt(self.right_menu_layout.count() - 1)
            if stretch_item:
                del stretch_item

        while self.right_menu_layout.count():
            item = self.right_menu_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _create_result_widget(
        self, data: dict, clickable: bool = True
    ) -> QWidget:
        r_id = data.get("id")
        if clickable:
            card = ClickableCard(r_id)
            card.clicked.connect(self.open_detail_view)
        else:
            card = QWidget()

        card.setObjectName("resultCard")

        main_layout = QHBoxLayout(card)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(20)

        db_entry = self.recipe_db.get(r_id, {})
        name = db_entry.get("name", f"Unknown Recipe (ID: {r_id})")
        desc = db_entry.get("description", "No description available.")
        accuracy = data.get("accuracy", 0.0)
        rating = db_entry.get("rating", "-")
        minutes = db_entry.get("minutes", "-")
        cal = db_entry.get("cal", "-")
        prot = db_entry.get("prot", "-")
        fat = db_entry.get("fat", "-")
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        lbl_name = QLabel(name)
        lbl_name.setObjectName("title")
        lbl_name.setWordWrap(True)
        lbl_desc = QLabel(desc)
        lbl_desc.setObjectName("desc")
        lbl_desc.setWordWrap(True)
        lbl_desc.setAlignment(Qt.AlignmentFlag.AlignTop)
        left_layout.addWidget(lbl_name)
        left_layout.addWidget(lbl_desc, stretch=1)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_widget.setFixedWidth(120)

        acc_text = f"{accuracy * 100:.1f}%"
        lbl_acc = QLabel(f"Match: {acc_text}")
        lbl_acc.setObjectName("matchStat")
        if accuracy > 0.9:
            lbl_acc.setStyleSheet("color: #27ae60;")
        elif accuracy > 0.6:
            lbl_acc.setStyleSheet("color: #f39c12;")
        else:
            lbl_acc.setStyleSheet("color: #e74c3c;")

        def make_stat_row(label, value):
            l = QLabel(f"{label}: {value}")
            l.setObjectName("stat")
            return l

        right_layout.addWidget(lbl_acc)
        right_layout.addWidget(make_stat_row("Rating", rating))
        right_layout.addWidget(make_stat_row("Time", f"{minutes} min"))
        right_layout.addWidget(make_stat_row("Cal", cal))
        right_layout.addWidget(make_stat_row("Prot", f"{prot} g"))
        right_layout.addWidget(make_stat_row("Fat", f"{fat} g"))
        right_layout.addStretch()

        main_layout.addWidget(left_widget, stretch=3)
        main_layout.addWidget(right_widget, stretch=1)

        return card

    def open_detail_view(self, r_id: int):
        self.current_detail_id = r_id
        self._populate_detail_view(r_id)
        self.stack.setCurrentIndex(1)

    def action_close_detail(self):
        self.stack.setCurrentIndex(0)

    def action_next_recipe(self):
        if not self.current_detail_id or not self.current_results_ids:
            return
        try:
            curr_idx = self.current_results_ids.index(self.current_detail_id)
            next_idx = (curr_idx + 1) % len(
                self.current_results_ids
            )
            next_id = self.current_results_ids[next_idx]
            self.open_detail_view(next_id)
        except ValueError:
            pass

    def action_prev_recipe(self):
        if not self.current_detail_id or not self.current_results_ids:
            return
        try:
            curr_idx = self.current_results_ids.index(self.current_detail_id)
            prev_idx = (curr_idx - 1) % len(
                self.current_results_ids
            )
            prev_id = self.current_results_ids[prev_idx]
            self.open_detail_view(prev_id)
        except ValueError:
            pass

    def _populate_detail_view(self, r_id: int):
        while self.detail_header_container.count():
            item = self.detail_header_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        while self.detail_content_layout.count():
            item = self.detail_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        accuracy = self.current_accuracies.get(r_id, 0.0)
        data_packet = {"id": r_id, "accuracy": accuracy}

        header_card = self._create_result_widget(data_packet, clickable=False)
        self.detail_header_container.addWidget(header_card)
        db_data = self.recipe_db.get(r_id, {})

        def add_section_title(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(
                "font-size: 18px; font-weight: bold; margin-top: 20px; color: #222;"
            )
            self.detail_content_layout.addWidget(lbl)
        add_section_title("Name")
        lbl_name = QLabel(db_data.get("name", ""))
        lbl_name.setStyleSheet("font-size: 16px;")
        lbl_name.setWordWrap(True)
        self.detail_content_layout.addWidget(lbl_name)
        add_section_title("Description")
        lbl_desc = QLabel(db_data.get("description", ""))
        lbl_desc.setWordWrap(True)
        self.detail_content_layout.addWidget(lbl_desc)
        add_section_title("Ingredients")
        ingredients = db_data.get("ingredients", [])
        if ingredients:
            ing_text = "\n".join([f"• {item}" for item in ingredients])
            lbl_ing = QLabel(ing_text)
            lbl_ing.setWordWrap(True)
            lbl_ing.setStyleSheet("margin-left: 10px; font-size: 14px;")
            self.detail_content_layout.addWidget(lbl_ing)
        else:
            self.detail_content_layout.addWidget(QLabel("No ingredients listed."))
        add_section_title("Steps")
        steps = db_data.get("steps", [])
        if steps:
            steps_text = "\n".join(
                [f"{i+1}. {step}" for i, step in enumerate(steps)]
            )
            lbl_steps = QLabel(steps_text)
            lbl_steps.setWordWrap(True)
            lbl_steps.setStyleSheet("margin-left: 10px; font-size: 14px; line-height: 150%;")
            self.detail_content_layout.addWidget(lbl_steps)
        else:
            self.detail_content_layout.addWidget(QLabel("No steps listed."))

        self.detail_content_layout.addStretch()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
