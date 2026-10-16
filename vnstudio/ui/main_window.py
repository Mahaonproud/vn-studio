"""Главное окно: главное меню <-> открытый проект."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit, QMainWindow, QMessageBox, QStackedWidget

from ..core import assets as A
from ..core.i18n import set_language, tr
from ..core.model import Project
from ..core.settings import APP_NAME
from .dialogs import SettingsDialog
from .home import HomePage
from .theme import build_qss
from .workspace import Workspace


class MainWindow(QMainWindow):
    def __init__(self, settings) -> None:
        super().__init__()
        self.settings = settings
        self.ws = None
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.resize(1400, 860)
        self.setMinimumSize(1100, 700)
        self.show_home()

    def _set_page(self, widget) -> None:
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()
        self.stack.addWidget(widget)

    def show_home(self) -> None:
        self.ws = None
        home = HomePage(self.settings)
        home.new_project.connect(self.new_project)
        home.open_project.connect(self.open_project)
        home.open_settings.connect(self.open_settings)
        self._set_page(home)
        self.setWindowTitle(APP_NAME)

    def new_project(self) -> None:
        name, ok = QInputDialog.getText(self, tr("Новый проект"), tr("Название новеллы:"), QLineEdit.EchoMode.Normal, "")
        if not ok or not name.strip():
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            p = Project.create(name.strip(), self.settings.projects_path())
            A.add_builtin_effects(p)
            p.save()
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, tr("Не удалось создать проект"), str(e))
            return
        QApplication.restoreOverrideCursor()
        self.open_workspace(p, new=True)

    def open_project(self, path: str) -> None:
        try:
            p = Project.load(path)
        except Exception as e:
            QMessageBox.critical(self, tr("Не удалось открыть проект"), str(e))
            return
        self.open_workspace(p, new=False)

    def open_workspace(self, project, new: bool) -> None:
        ws = Workspace(project, self.settings)
        ws.closed.connect(self.show_home)
        self.ws = ws
        self._set_page(ws)
        self.setWindowTitle(f"{project.name} — {APP_NAME}")
        if new:
            ws.show_page("library")

    def open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self)
        if dlg.run():
            dlg.apply()
            self.settings.save()
            set_language(self.settings.language)
            QApplication.instance().setStyleSheet(build_qss(self.settings.theme))
            self.show_home()

    def closeEvent(self, event) -> None:
        if self.ws is not None and not self.ws.request_close():
            event.ignore()
            return
        event.accept()
