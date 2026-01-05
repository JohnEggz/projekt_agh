import sys
import pprint
import json
import os
import time
import csv
import ast
from typing import List, Optional


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
    QAbstractItemView,
)
from PySide6.QtGui import (
    QResizeEvent,
)

from paths import RECIPES_FOUND, DISPLAY_CSV, SEARCH_CSV, INGRIDIENTS_TRIE


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
                color: black;
            }
            QListWidget::item:selected {
                background-color: #0078d7; 
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
        
        # Calculate dynamic height
        row_height = 30 # Approx height per item
        total_content_height = len(items) * row_height + 5
        final_height = min(total_content_height, self.MAX_HEIGHT)
        
        self.setFixedHeight(final_height)
        self.show()
        self.raise_() # Crucial: Bring to front of Z-order

class ClickableCard(QFrame):
    """A Frame that acts like a button, emitting a signal with its ID when clicked."""
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
    """
    A rounded 'pill' widget with text and a delete button.
    It automatically removes itself from its parent FlowScrollArea when closed.
    """
    def __init__(self, text: str, parent_area: 'FlowScrollArea'):
        super().__init__()
        self._text = text
        self._parent_area = parent_area
        
        # Styling
        self.setObjectName("bubble")
        self.setStyleSheet("""
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
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)
        
        # Label
        lbl = QLabel(text)
        layout.addWidget(lbl)
        
        # Remove Button (X)
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(20, 20)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self._remove_self)
        layout.addWidget(btn_close)
        
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def text(self) -> str:
        """Exposes the text attribute for the Storage class."""
        return self._text

    def _remove_self(self):
        """Removes self from the parent FlowScrollArea."""
        if self._parent_area:
            self._parent_area.removeWidget(self)
class TrieHandler:
    def __init__(self, filepath):
        self.root = {}
        self._load(filepath)

    def _load(self, filepath):
        if not filepath or not os.path.exists(filepath):
            print(f"Trie file not found: {filepath}")
            return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.root = json.load(f)
        except Exception as e:
            print(f"Error loading Trie: {e}")

    def get_suggestions(self, prefix: str, limit: int = 5) -> list[str]:
        """Returns a list of up to `limit` valid words starting with `prefix`."""
        if not prefix or not self.root:
            return []
        
        prefix = prefix.lower()
        node = self.root
        
        # 1. Traverse to the end of the prefix
        for char in prefix:
            if char not in node:
                return []
            node = node[char]
            
        # 2. DFS to find words
        results = []
        
        def dfs(current_node, current_word):
            if len(results) >= limit:
                return
            
            # If this node has IDs, it's a valid word
            if "__ids__" in current_node:
                results.append(current_word)
            
            # Continue deeper
            for char, next_node in current_node.items():
                if char == "__ids__": continue
                dfs(next_node, current_word + char)

        dfs(node, prefix)
        return results

    def is_valid_ingredient(self, word: str) -> bool:
        """Checks if a word exists in the Trie and has an ID."""
        if not word: return False
        node = self.root
        for char in word.lower():
            if char not in node: return False
            node = node[char]
        return "__ids__" in node
class AutocompleteLineEdit(QLineEdit):
    def __init__(self, trie_handler: TrieHandler, parent=None):
        super().__init__(parent)
        self.trie = trie_handler
        self.setPlaceholderText("Type ingredient...")
        self.popup = None # Created lazily or attached to window later

        self.textEdited.connect(self._on_text_edited)
        
        # Event filter to handle keys (Down/Up/Enter)
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
        # 1. Initialize Popup if needed (Parented to the Window)
        if not self.popup:
            self.popup = FloatingList(self.window())
            self.popup.itemClicked.connect(self._on_item_clicked)

        # 2. Validation & Search
        if len(text) < 2:
            self.popup.hide()
            return

        suggestions = self.trie.get_suggestions(text)
        if not suggestions:
            self.popup.hide()
            return

        # 3. Update Content
        self.popup.update_items(suggestions)
        self.popup.setCurrentRow(-1) # Deselect

        # 4. Position Popup
        # We must map coordinates to the *Window* because popup is child of Window
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
        # Small delay or check logic to allow click events to register
        # For simplicity, if we click outside, we just hide.
        if self.popup and not self.popup.hasFocus():
             self.popup.hide()
        super().focusOutEvent(event)

class FlowLayout(QLayout):
    def __init__(self, parent: Optional[QWidget] = None, margin: int = 0, h_spacing: int = -1, v_spacing: int = -1):
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
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def getWidgets(self) -> List[QWidget]:
        widgets = []
        for item in self._item_list:
            widget = item.widget()
            if widget:
                widgets.append(widget)
        return widgets

    def horizontalSpacing(self) -> int:
        if self._h_space >= 0: return self._h_space
        return self.smartSpacing(QStyle.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self) -> int:
        if self._v_space >= 0: return self._v_space
        return self.smartSpacing(QStyle.PM_LayoutVerticalSpacing)

    def smartSpacing(self, pm: QStyle.PixelMetric) -> int:
        parent = self.parent()
        if not parent: return -1
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
        if spacing_x == -1: spacing_x = 10
        if spacing_y == -1: spacing_y = 10

        for item in self._item_list:
            next_x = x + item.sizeHint().width() + spacing_x
            if next_x - spacing_x > effective_rect.right() and line_height > 0:
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
    """
    A QScrollArea that automatically contains a widget with a FlowLayout.
    It proxies the FlowLayout API methods.
    """
    def __init__(self, height: Optional[int] = 50, parent: Optional[QWidget] = None):
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
        """Adds a widget to the internal FlowLayout."""
        self._flow_layout.addWidget(widget)

    def getWidgets(self) -> List[QWidget]:
        """Returns the list of widgets in the internal FlowLayout."""
        return self._flow_layout.getWidgets()

    def removeWidget(self, widget: QWidget):
        """Removes a widget from the internal layout."""
        self._flow_layout.removeWidget(widget)
        widget.deleteLater()

    def clear(self):
        """Removes all widgets."""
        item = self._flow_layout.takeAt(0)
        while item:
            if item.widget():
                item.widget().deleteLater()
            item = self._flow_layout.takeAt(0)

    def setSpacing(self, h_spacing: int, v_spacing: int):
        """Sets horizontal and vertical spacing."""
        self._flow_layout._h_space = h_spacing
        self._flow_layout._v_space = v_spacing
        self._flow_layout.update()

    def setContentsMargins(self, left: int, top: int, right: int, bottom: int):
        """Sets margins on the INTERNAL layout, not the scroll area frame."""
        self._flow_layout.setContentsMargins(left, top, right, bottom)

    def sizeHint(self) -> QSize:
        """Tell the parent layout (left_menu) to respect the inner content height."""
        inner_size = self._container.sizeHint()
        height = inner_size.height() + self.frameWidth() * 2
        return QSize(super().sizeHint().width(), height)
class Storage:
    def __init__(self) -> None:
        self._subscribers: list[tuple[str, object]] = []

    def add(self, key_name:str, object_instance:object):
        new_entry: tuple[str, object] = (key_name, object_instance)
        self._subscribers.append(new_entry)

    def _objects_to_dict(self) -> dict[str, str | list[str]]:
        def _object_to_data(object_instance: object) -> str | list[str]:
            if hasattr(object_instance, "text"):
                return object_instance.text() # type: ignore
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

        output:dict[str, str | list[str]] = {}
        for pair in self._subscribers:
            key_name, object_instance = pair
            widget_contents = _object_to_data(object_instance)
            if not widget_contents or widget_contents == "" or widget_contents == []:
                continue
            if not key_name or key_name == "":
                print("WARNING: Passed a empty key_name for contents", f"'{widget_contents}'")
                continue
            output[key_name] = widget_contents
        return output

    def get_data(self) -> dict[str, str | list[str]]:
        return self._objects_to_dict()

storage = Storage()

class RecipeFileHandler(QObject, FileSystemEventHandler):
    """
    Monitors file system events (Create, Modify, Delete, Move) 
    and emits a signal when the target file is affected.
    """
    file_changed = Signal()

    def __init__(self, target_filename):
        super().__init__()
        self.target_filename = target_filename

    def _process_event(self, event):
        # Check if the event involves our target file
        # For 'moved', dest_path might be the target
        is_target = False
        if hasattr(event, 'dest_path'):
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
        self.setWindowTitle("PyQt6 Recipe Search")
        self.setGeometry(100, 100, 900, 600)
        self.setObjectName("mainWindow")
        
        # Data Loading
        self.recipe_db = {}
        self.current_results_ids = [] 
        self.current_accuracies = {} # <--- NEW: Store accuracy map
        self.current_detail_id = None
        
        self._load_recipe_db()
        
        # Load Trie
        self.trie_handler = TrieHandler(INGRIDIENTS_TRIE)

        self._ui()
        
        self._setup_file_watcher()
        self.reload_results_from_file()

    def _ui(self):
        # We use a Stack to switch between Search (Index 0) and Details (Index 1)
        self.stack = QStackedWidget(self)
        
        # --- LAYER 0: SEARCH VIEW ---
        search_widget = QWidget()
        search_layout = QHBoxLayout(search_widget)
        
        # Left Menu
        left_menu = QVBoxLayout()
        search_button = QPushButton("Search") # Does nothing, but kept as requested
        search_button.clicked.connect(self.on_search_press)
        left_menu.addWidget(self._ui_app_title())
        left_menu.addWidget(self._ui_scrollable_menu())
        left_menu.addWidget(search_button)

        # Right Menu (Results)
        right_decoration = QWidget()
        self.right_menu_layout = QVBoxLayout(right_decoration)
        self.right_menu_layout.addStretch()

        search_layout.addLayout(left_menu)
        search_layout.addWidget(right_decoration)
        search_layout.setStretch(0, 1)
        search_layout.setStretch(1, 2)
        
        self.stack.addWidget(search_widget) # Add to stack at index 0

        # --- LAYER 1: DETAIL VIEW ---
        self.detail_view = self._ui_detail_view_layer()
        self.stack.addWidget(self.detail_view) # Add to stack at index 1

        # Main Layout for the Window
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.stack)

    def _ui_app_title(self) -> QWidget:
        app_title_widget = QWidget()
        app_title = QVBoxLayout(app_title_widget)
        app_title.addWidget(QLabel("Wyszukiwarka"))
        app_title.addWidget(QLabel("Przepisów"))
        app_title_widget.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed
        )
        return app_title_widget

    def _ui_detail_view_layer(self) -> QWidget:
        """Constructs the container for the detail view."""
        container = QWidget()
        layout = QVBoxLayout(container)
        
        # 1. Header Area (Will hold the duplicate card)
        self.detail_header_container = QVBoxLayout()
        layout.addLayout(self.detail_header_container)

        # 2. Scrollable Content (Details)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.detail_content_widget = QWidget()
        self.detail_content_layout = QVBoxLayout(self.detail_content_widget)
        self.detail_content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        scroll.setWidget(self.detail_content_widget)
        layout.addWidget(scroll)

        # 3. Floating Controls (Bottom Bar)
        controls = QHBoxLayout()
        
        btn_prev = QPushButton("Previous")
        btn_prev.clicked.connect(self.action_prev_recipe)
        
        btn_close = QPushButton("Close / Back")
        btn_close.clicked.connect(self.action_close_detail)
        btn_close.setStyleSheet("background-color: #ffcccc; color: red; font-weight: bold;")
        
        btn_next = QPushButton("Next")
        btn_next.clicked.connect(self.action_next_recipe)

        controls.addWidget(btn_prev)
        controls.addWidget(btn_close)
        controls.addWidget(btn_next)
        
        layout.addLayout(controls)
        
        return container

    def _ui_scrollable_menu(self) -> QScrollArea:
        content_widget = QWidget()
        filter_menu = QVBoxLayout(content_widget)

        # Existing Filters
        filter_menu.addWidget(self._ui_recipe_name())
        filter_menu.addWidget(self._ui_liked_box())
        filter_menu.addWidget(self._ui_disliked_box())
        
        # New Min/Max Filters
        # We use a separator line or spacing to distinguish sections if desired
        filter_menu.addSpacing(10)
        
        filter_menu.addWidget(self._ui_min_max_input("Rating (0-5)", "rating"))
        filter_menu.addWidget(self._ui_min_max_input("Time (Minutes)", "minutes"))
        filter_menu.addWidget(self._ui_min_max_input("Calories", "cal"))
        filter_menu.addWidget(self._ui_min_max_input("Protein (g)", "prot"))
        filter_menu.addWidget(self._ui_min_max_input("Fat (g)", "fat"))

        filter_menu.addStretch()

        scrollable_menu = QScrollArea()
        scrollable_menu.setWidget(content_widget)
        scrollable_menu.setWidgetResizable(True)
        scrollable_menu.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scrollable_menu.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scrollable_menu.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        return scrollable_menu

    def _ui_min_max_input(self, label_text: str, key_prefix: str) -> QWidget:
        """
        Creates a vertical box with a label and a row containing [Min] - [Max] inputs.
        Hooks them up to storage as key_prefix_min and key_prefix_max.
        """
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 5, 0, 5) # Slight vertical padding
        
        # Main Label
        lbl = QLabel(label_text)
        layout.addWidget(lbl)
        
        # Horizontal Row for Inputs
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        
        # Min Input
        min_edit = QLineEdit()
        min_edit.setPlaceholderText("Min")
        storage.add(f"{key_prefix}_min", min_edit)
        
        # Separator
        sep = QLabel("-")
        sep.setStyleSheet("color: #777; font-weight: bold;")
        
        # Max Input
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
        label = QLabel("Nazwa Przepisu")
        line_edit = QLineEdit()
        storage.add("recipe_name",line_edit)

        layout.addWidget(label)
        layout.addWidget(line_edit)

        return output_widget

    def _ui_liked_box(self) -> QWidget:
        output_widget = QWidget()
        layout = QVBoxLayout(output_widget)
        
        label = QLabel("Składniki Lubiane")
        
        # Use AutocompleteLineEdit
        line_edit = AutocompleteLineEdit(self.trie_handler, output_widget)
        
        flow_area = FlowScrollArea()
        storage.add("liked_recipes", flow_area)

        self._setup_bubble_input(line_edit, flow_area)

        layout.addWidget(label)
        layout.addWidget(line_edit)
        layout.addWidget(flow_area)

        return output_widget

    def _ui_disliked_box(self) -> QWidget:
        output_widget = QWidget()
        layout = QVBoxLayout(output_widget)
        
        label = QLabel("Składniki Nielubiane")
        
        # Use AutocompleteLineEdit
        line_edit = AutocompleteLineEdit(self.trie_handler, output_widget)
        
        flow_area = FlowScrollArea()
        storage.add("disiked_recipes", flow_area)

        self._setup_bubble_input(line_edit, flow_area)

        layout.addWidget(label)
        layout.addWidget(line_edit)
        layout.addWidget(flow_area)

        return output_widget

    def _setup_bubble_input(self, line_edit: AutocompleteLineEdit, flow_area: FlowScrollArea):
        """Connects return signal to validation and bubble creation."""
        def add_bubble():
            text = line_edit.text().strip()
            
            # 1. Validation Logic
            # Only add if text is not empty AND exists in Trie
            if text and self.trie_handler.is_valid_ingredient(text):
                bubble = BubbleWidget(text, flow_area)
                flow_area.addWidget(bubble)
                line_edit.clear()
                line_edit.popup.hide() # Ensure popup goes away
            else:
                # Optional: Visual feedback for invalid input (e.g., flash red)
                print(f"Invalid ingredient: {text}")

        line_edit.returnPressed.connect(add_bubble)

    def _load_recipe_db(self):
        """Loads CSVs and parses stringified lists using ast.literal_eval."""
        # Load Display Data (Name, Desc, Steps, Ingredients)
        if os.path.exists(DISPLAY_CSV):
            try:
                with open(DISPLAY_CSV, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            r_id = int(row['id'])
                            if r_id not in self.recipe_db: self.recipe_db[r_id] = {}
                            
                            self.recipe_db[r_id]['name'] = row.get('name', 'Unknown')
                            self.recipe_db[r_id]['description'] = row.get('description', '')
                            
                            # Parse lists safely
                            try:
                                self.recipe_db[r_id]['steps'] = ast.literal_eval(row.get('steps', '[]'))
                            except:
                                self.recipe_db[r_id]['steps'] = []
                                
                            try:
                                self.recipe_db[r_id]['ingredients'] = ast.literal_eval(row.get('ingredients', '[]'))
                            except:
                                self.recipe_db[r_id]['ingredients'] = []
                                
                        except ValueError:
                            continue
            except Exception as e:
                print(f"Error loading DISPLAY_CSV: {e}")

        # Load Search Data (Stats)
        if os.path.exists(SEARCH_CSV):
            try:
                with open(SEARCH_CSV, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            r_id = int(row['id'])
                            if r_id not in self.recipe_db: self.recipe_db[r_id] = {}
                            self.recipe_db[r_id]['rating'] = row.get('avg_rating', '-')
                            self.recipe_db[r_id]['minutes'] = row.get('minutes', '-')
                            self.recipe_db[r_id]['cal'] = row.get('cal', '-')
                            self.recipe_db[r_id]['prot'] = row.get('prot', '-')
                            self.recipe_db[r_id]['fat'] = row.get('fat', '-')
                        except ValueError:
                            continue
            except Exception as e:
                print(f"Error loading SEARCH_CSV: {e}")

    def on_search_press(self):
        pprint.pprint(storage.get_data())

    def _setup_file_watcher(self):
        # 1. Setup Debounce Timer
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(200) # 200ms delay
        self.debounce_timer.timeout.connect(self.reload_results_from_file)

        # 2. Setup Watchdog
        # Ensure directory exists or handle error, here we assume paths are valid
        folder = os.path.dirname(RECIPES_FOUND)
        filename = os.path.basename(RECIPES_FOUND)

        if not os.path.exists(folder):
            print(f"Warning: Folder {folder} does not exist. Watcher might fail.")
            return

        self.event_handler = RecipeFileHandler(filename)
        self.event_handler.file_changed.connect(self.on_file_change_signal)

        self.observer = Observer()
        self.observer.schedule(self.event_handler, folder, recursive=False)
        self.observer.start()

    def closeEvent(self, event):
        """Clean up observer thread on app exit"""
        if hasattr(self, 'observer'):
            self.observer.stop()
            self.observer.join()
        event.accept()

    def on_file_change_signal(self):
        """Called when file changes. Resets the timer (Debouncing)."""
        self.debounce_timer.start()

    def reload_results_from_file(self):
        """Reads file, validates structure, and updates UI."""
        # 1. Handle File Missing / Deleted
        if not os.path.exists(RECIPES_FOUND):
            self._show_placeholder("File not found. Waiting for recipes...")
            return

        try:
            with open(RECIPES_FOUND, 'r') as f:
                # Handle empty file case (e.g. created but not written yet)
                content = f.read().strip()
                if not content:
                    self._show_placeholder("File is empty...")
                    return 
                data = json.loads(content)

            # Validate top-level structure is a list
            if not isinstance(data, list):
                self._show_placeholder("Invalid data format: Expected a List")
                return

            self.populate_results(data)

        except json.JSONDecodeError:
            # Common during write operations
            pass 
        except Exception as e:
            print(f"Error reading file: {e}")
            self._show_placeholder(f"Error reading file: {e}")

    def populate_results(self, results: list):
        self._clear_right_menu()
        self.current_results_ids.clear()
        self.current_accuracies.clear() # <--- NEW: Reset map

        valid_items_count = 0
        for data in results:
            if not isinstance(data, dict): continue
            if "id" not in data or "accuracy" not in data: continue

            r_id = data.get("id")
            accuracy = data.get("accuracy", 0.0)
            
            # Store data for later use
            self.current_results_ids.append(r_id)
            self.current_accuracies[r_id] = accuracy # <--- NEW: Save accuracy

            # Create Widget
            widget = self._create_result_widget(data)
            self.right_menu_layout.addWidget(widget)
            valid_items_count += 1
        
        if valid_items_count == 0:
            self._show_placeholder("No matching recipes found")
        else:
            self.right_menu_layout.addStretch()

    def _show_placeholder(self, message: str):
        """Helper to show a gray placeholder text in the right menu."""
        self._clear_right_menu()
        
        label = QLabel(message)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #888888; font-size: 16px; padding: 20px;")
        
        self.right_menu_layout.addWidget(label)
        self.right_menu_layout.addStretch()

    def _clear_right_menu(self):
        """Removes all widgets from the right menu layout."""
        while self.right_menu_layout.count():
            item = self.right_menu_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _create_result_widget(self, data: dict, clickable: bool = True) -> QWidget:
        r_id = data.get("id")
        
        # Use ClickableCard if it needs to be interactive, else standard QWidget
        if clickable:
            card = ClickableCard(r_id)
            card.clicked.connect(self.open_detail_view) # Connect signal
        else:
            card = QWidget()

        card.setObjectName("resultCard")
        card.setStyleSheet("""
            QWidget#resultCard {
                background-color: #ffffff; 
                border: 1px solid #d0d0d0; 
                border-radius: 8px;
            }
            QLabel { color: #333; }
            QLabel#title { font-size: 16px; font-weight: bold; color: #000; }
            QLabel#desc { font-size: 12px; color: #555; }
            QLabel#stat { font-size: 11px; font-weight: bold; color: #444; }
        """)

        # ... (Rest of layout logic identical to previous answer) ...
        # (For brevity, assuming the layout logic from previous response is here)
        # REPEATING LAYOUT LOGIC FOR COMPLETENESS:
        main_layout = QHBoxLayout(card)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(20)

        db_entry = self.recipe_db.get(r_id, {})
        name = db_entry.get('name', f"Unknown Recipe (ID: {r_id})")
        desc = db_entry.get('description', "No description available.")
        
        # Stats
        accuracy = data.get("accuracy", 0.0)
        rating = db_entry.get('rating', '-')
        minutes = db_entry.get('minutes', '-')
        cal = db_entry.get('cal', '-')
        prot = db_entry.get('prot', '-')
        fat = db_entry.get('fat', '-')

        # Left Column
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
        left_layout.addWidget(lbl_desc)
        left_layout.addStretch()

        # Right Column
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_widget.setFixedWidth(120)

        acc_text = f"{accuracy * 100:.1f}%"
        lbl_acc = QLabel(f"Match: {acc_text}")
        lbl_acc.setObjectName("stat")
        if accuracy > 0.9: lbl_acc.setStyleSheet("color: green;")
        elif accuracy > 0.6: lbl_acc.setStyleSheet("color: orange;")
        else: lbl_acc.setStyleSheet("color: red;")

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
        self.stack.setCurrentIndex(1) # Switch to Detail Layer

    def action_close_detail(self):
        self.stack.setCurrentIndex(0) # Switch back to Search Layer

    def action_next_recipe(self):
        if not self.current_detail_id or not self.current_results_ids: return
        try:
            curr_idx = self.current_results_ids.index(self.current_detail_id)
            next_idx = (curr_idx + 1) % len(self.current_results_ids) # Loop around
            next_id = self.current_results_ids[next_idx]
            self.open_detail_view(next_id)
        except ValueError:
            pass

    def action_prev_recipe(self):
        if not self.current_detail_id or not self.current_results_ids: return
        try:
            curr_idx = self.current_results_ids.index(self.current_detail_id)
            prev_idx = (curr_idx - 1) % len(self.current_results_ids) # Loop around
            prev_id = self.current_results_ids[prev_idx]
            self.open_detail_view(prev_id)
        except ValueError:
            pass

    def _populate_detail_view(self, r_id: int):
        """Fills the detail view with content for the given ID."""
        
        # 1. Clear previous content
        while self.detail_header_container.count():
            item = self.detail_header_container.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        while self.detail_content_layout.count():
            item = self.detail_content_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        # 2. Re-create the Top Card
        # RETRIEVE SAVED ACCURACY HERE
        accuracy = self.current_accuracies.get(r_id, 0.0) 
        data_packet = {"id": r_id, "accuracy": accuracy}
        
        header_card = self._create_result_widget(data_packet, clickable=False)
        self.detail_header_container.addWidget(header_card)

        # 3. Add Details (Rest remains the same)
        db_data = self.recipe_db.get(r_id, {})
        
        def add_section_title(text):
            lbl = QLabel(text)
            lbl.setStyleSheet("font-size: 18px; font-weight: bold; margin-top: 20px; color: #222;")
            self.detail_content_layout.addWidget(lbl)

        # Name
        add_section_title("Name")
        lbl_name = QLabel(db_data.get('name', ''))
        lbl_name.setStyleSheet("font-size: 16px;")
        lbl_name.setWordWrap(True)
        self.detail_content_layout.addWidget(lbl_name)

        # Description
        add_section_title("Description")
        lbl_desc = QLabel(db_data.get('description', ''))
        lbl_desc.setWordWrap(True)
        self.detail_content_layout.addWidget(lbl_desc)

        # Ingredients
        add_section_title("Ingredients")
        ingredients = db_data.get('ingredients', [])
        if ingredients:
            ing_text = "\n".join([f"• {item}" for item in ingredients])
            lbl_ing = QLabel(ing_text)
            lbl_ing.setWordWrap(True)
            lbl_ing.setStyleSheet("margin-left: 10px;")
            self.detail_content_layout.addWidget(lbl_ing)
        else:
            self.detail_content_layout.addWidget(QLabel("No ingredients listed."))

        # Steps
        add_section_title("Steps")
        steps = db_data.get('steps', [])
        if steps:
            steps_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps)])
            lbl_steps = QLabel(steps_text)
            lbl_steps.setWordWrap(True)
            lbl_steps.setStyleSheet("margin-left: 10px;")
            self.detail_content_layout.addWidget(lbl_steps)
        else:
            self.detail_content_layout.addWidget(QLabel("No steps listed."))

        self.detail_content_layout.addStretch()


def get_stylesheet() -> str:
    try:
        with open("styles.css", "r") as f:
            stylesheet = f.read()
            return stylesheet
    except FileNotFoundError:
        print("Stylesheet 'styles.css' not found. Using default styles.")
        return ""
def test_vertical_group() -> QWidget:
    new_widget = QWidget()
    new_widget.setObjectName("test")
    return new_widget
def vertical_group() -> QWidget:
    new_widget = QWidget()
    new_widget.setObjectName("test")
    return new_widget

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(get_stylesheet())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
