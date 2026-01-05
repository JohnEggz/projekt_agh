class MainWindow(QWidget):
    # ... (init and other methods remain unchanged) ...

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

    # ... (Rest of the class remains unchanged) ...
