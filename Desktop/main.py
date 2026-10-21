"""Entry point for the Clock Drift Synchronizer desktop application."""
import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def _apply_bright_theme(app: QApplication) -> None:
    """Force a bright palette so the UI stays light even on dark OS themes."""
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#FFFFFF"))
    palette.setColor(QPalette.WindowText, QColor("#1A1A1A"))
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.AlternateBase, QColor("#F5F5F7"))
    palette.setColor(QPalette.Text, QColor("#1A1A1A"))
    palette.setColor(QPalette.Button, QColor("#FFFFFF"))
    palette.setColor(QPalette.ButtonText, QColor("#1A1A1A"))
    palette.setColor(QPalette.ToolTipBase, QColor("#FFFFFF"))
    palette.setColor(QPalette.ToolTipText, QColor("#1A1A1A"))
    app.setPalette(palette)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Clock Drift Synchronizer")
    _apply_bright_theme(app)

    window = MainWindow()
    window.resize(420, 720)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
