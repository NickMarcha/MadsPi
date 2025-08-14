import sys
from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout

def main():
    app = QApplication(sys.argv)
    window = QWidget()
    layout = QVBoxLayout()
    layout.addWidget(QLabel("Hello, Qt for Python!"))
    window.setLayout(layout)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
