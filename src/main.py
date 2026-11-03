import sys
import os

# Add the src directory to the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from ui.main_window import MainWindow
from PySide6.QtWidgets import QApplication
from qt_material import apply_stylesheet

def main():
    app = QApplication(sys.argv)
    
    # Apply a modern dark theme
    apply_stylesheet(app, theme='dark_teal.xml')
    
    window = MainWindow(app)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
