class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt6 Recipe Search")
        self.setGeometry(100, 100, 900, 600)
        self.setObjectName("mainWindow")
        
        # Data Loading
        self.recipe_db = {}
        self.current_results_ids = []
        self.current_detail_id = None
        
        self._load_recipe_db()
        
        # Load Trie
        self.trie_handler = TrieHandler(INGRIDIENTS_TRIE)

        self._ui()
        
        self._setup_file_watcher()
        self.reload_results_from_file()

    # ... (Other methods remain unchanged) ...

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
