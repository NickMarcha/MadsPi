import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

# Ensure package root (src) is on sys.path when running this file directly
_package_root = Path(__file__).resolve().parents[1]
if str(_package_root) not in sys.path:
    sys.path.insert(0, str(_package_root))

# Import via package so relative imports in submodules work
from madspipeline.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("MadsPipeline")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("MadsPipeline")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
