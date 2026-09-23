"""Entry point for the Clock Drift Synchronizer desktop application."""
import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Clock Drift Synchronizer")

    window = MainWindow()
    window.resize(420, 720)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
