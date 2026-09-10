from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .gui import MainWindow
from .logging_setup import configure_logging


def main() -> int:
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("IFC Steel List Generator")
    window = MainWindow(); window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

