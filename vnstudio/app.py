"""Точка входа приложения."""
from __future__ import annotations

import sys


def run() -> int:
    from PySide6.QtWidgets import QApplication
    from .core.i18n import set_language
    from .core.settings import APP_NAME, Settings
    from .ui.main_window import MainWindow
    from .ui.theme import build_qss

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    settings = Settings.load()
    set_language(settings.language)
    app.setStyleSheet(build_qss(settings.theme))
    win = MainWindow(settings)
    win.show()
    return app.exec()
