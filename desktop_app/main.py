
import sys
import os

# Add project root to sys.path to allow imports from desktop_app package
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

from PySide6.QtWidgets import QApplication
from desktop_app.ui.main_window import MainWindow

def main():
    """
    Entry point for the Walkability Optimization Desktop App.
    """
    # Create QApplication instance
    app = QApplication(sys.argv)
    app.setApplicationName("Walkability Optimization Tool")
    
    # Create and show main window
    window = MainWindow()
    window.resize(1280, 800)  # Set reasonable default size
    window.showMaximized()  # Start maximized instead of normal size
    
    # Execute application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
