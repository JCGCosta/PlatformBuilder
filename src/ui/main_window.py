import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QStackedWidget, QLabel, QFrame)
from PySide6.QtCore import Qt
from qt_material import apply_stylesheet

# Local imports
from ui.admin_panel import AdminPanel
from ui.user_panel import UserPanel # We'll update this next

class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app # Store QApplication instance
        self.setWindowTitle("PlatformBuilder IDE")
        self.resize(1200, 800)
        
        self.current_theme = 'dark_teal.xml' # Default theme
        self.current_font_size = 12 # Default font size
        
        font = self.font()
        font.setPointSize(self.current_font_size)
        self.setFont(font)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Header / Navigation Bar
        self.header = QFrame()
        self.header.setObjectName("Header")
        self.header.setFixedHeight(60)
        self.header_layout = QHBoxLayout(self.header)
        
        self.title_label = QLabel("PlatformBuilder")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.header_layout.addWidget(self.title_label)
        
        self.header_layout.addStretch()
        
        # Admin/User Toggle
        self.mode_toggle_btn = QPushButton("Switch to Admin Mode")
        self.mode_toggle_btn.setCheckable(True)
        self.mode_toggle_btn.clicked.connect(self.toggle_mode)
        self.header_layout.addWidget(self.mode_toggle_btn)
        
        self.layout.addWidget(self.header)
        
        # Main Content Area (Stacked Widget)
        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget)
        
        # Panels
        self.user_view = UserPanel(self)
        
        self.admin_view = AdminPanel(self)
        self.code_editor = self.admin_view.editor # Expose for settings dialog

        
        self.stacked_widget.addWidget(self.user_view) # Index 0: User
        self.stacked_widget.addWidget(self.admin_view) # Index 1: Admin
        
        # Footer / Status Bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

    def toggle_mode(self):
        if self.mode_toggle_btn.isChecked():
            pm = self.user_view.project_manager
            proj_dir = pm.get_proj_dir_path() if pm.have_active_project() else None
            if not self.admin_view.set_project(proj_dir, pm.get_proj_name() if proj_dir else ""):
                self.mode_toggle_btn.setChecked(False)
                return
            self.mode_toggle_btn.setText("Switch to User Mode")
            self.stacked_widget.setCurrentIndex(1)
            self.status_bar.showMessage("Admin Mode Active")
        else:
            self.mode_toggle_btn.setText("Switch to Admin Mode")
            self.stacked_widget.setCurrentIndex(0)
            if self.admin_view.files_changed:  # concept files edited in the IDE: reload them keeping the canvas
                self.admin_view.files_changed = False
                self.user_view.reload_concepts()
            self.status_bar.showMessage("User Mode Active")

    def closeEvent(self, event):
        # Don't leave the generated API running in the background after the IDE closes
        if not self.admin_view.editor.close_all():
            event.ignore()
            return
        engine = self.user_view.engine_integration
        if engine.is_running():
            engine.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_stylesheet(app, theme='dark_teal.xml')
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
