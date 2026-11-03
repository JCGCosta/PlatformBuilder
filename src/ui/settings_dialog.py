from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel, QFontDialog, QSpinBox
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from qt_material import apply_stylesheet

class SettingsDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)  # parented to the main window so it opens centered over it
        self.setWindowTitle("Settings")
        self.resize(360, 0)
        self.main_window = main_window
        
        self.layout = QVBoxLayout(self)
        
        # Theme selection
        self.theme_layout = QHBoxLayout()
        self.theme_label = QLabel("Theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(['dark_teal.xml', 'light_blue.xml', 'dark_blue.xml', 'light_teal.xml'])
        self.theme_combo.setCurrentText(self.main_window.current_theme) # Assuming main_window holds current theme
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        self.theme_layout.addWidget(self.theme_label)
        self.theme_layout.addWidget(self.theme_combo)
        self.layout.addLayout(self.theme_layout)
        
        # Font size selection
        self.font_size_layout = QHBoxLayout()
        self.font_size_label = QLabel("Font Size:")
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setMinimum(8)
        self.font_size_spinbox.setMaximum(24)
        self.font_size_spinbox.setValue(self.main_window.current_font_size) # Assuming main_window holds current font size
        self.font_size_spinbox.valueChanged.connect(self.change_font_size)
        self.font_size_layout.addWidget(self.font_size_label)
        self.font_size_layout.addWidget(self.font_size_spinbox)
        self.layout.addLayout(self.font_size_layout)
        
        # OK/Cancel buttons
        self.button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.ok_button)
        self.layout.addLayout(self.button_layout)

    def change_theme(self, theme_name):
        apply_stylesheet(self.main_window.app, theme=theme_name) # Assuming app is accessible via main_window
        self.main_window.current_theme = theme_name
        self.main_window.code_editor.set_theme(theme_name.startswith('dark'))

    def change_font_size(self, size):
        font = self.main_window.font()
        font.setPointSize(size)
        self.main_window.setFont(font) # Apply to main window
        self.main_window.current_font_size = size
        
        # Also apply to the editor and other relevant widgets
        # This might need a more sophisticated signal/slot system or iterating through widgets
        self.main_window.code_editor.set_font(font) # Apply to admin editor
