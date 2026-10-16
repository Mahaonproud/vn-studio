"""Проверка проекта и экспорт в Ren'Py."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QBrush, QColor, QDesktopServices
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from ..core.check import validate
from ..core.exporter import export_project
from ..core.i18n import tr

COLORS = {"error": "#ff453a", "warn": "#ff9f0a", "info": "#0a84ff"}
MARKS = {"error": "●", "warn": "●", "info": "●"}


class ExportPage(QWidget):
    def __init__(self, ws, parent=None) -> None:
        super().__init__(parent)
        self.ws = ws
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(16)

        left = QVBoxLayout()
        h = QLabel(tr("Проверка проекта"))
        h.setProperty("role", "h2")
        left.addWidget(h)
        self.lst = QListWidget()
        self.lst.itemDoubleClicked.connect(self.open_issue)
        left.addWidget(self.lst, 1)
        b = QPushButton(tr("Проверить проект"))
        b.setProperty("accent", True)
        b.clicked.connect(self.check)
        left.addWidget(b)
        hint = QLabel(tr("Красные пункты нужно исправить, жёлтые — желательно. Двойной щелчок открывает нужное место."))
        hint.setProperty("role", "sub")
        hint.setWordWrap(True)
        left.addWidget(hint)
        root.addLayout(left, 1)

        right = QVBoxLayout()
        h2 = QLabel(tr("Экспорт в Ren'Py"))
        h2.setProperty("role", "h2")
        right.addWidget(h2)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        right.addWidget(self.info)
        b1 = QPushButton(tr("Сохранить и экспортировать"))
        b1.setProperty("accent", True)
        b1.setProperty("big", True)
        b1.clicked.connect(self.save_and_export)
        right.addWidget(b1)
        b2 = QPushButton(tr("Экспортировать в мой проект Ren'Py…"))
        b2.clicked.connect(self.export_to_renpy)
        right.addWidget(b2)
        b3 = QPushButton(tr("Открыть папку экспорта"))
        b3.clicked.connect(self.open_folder)
        right.addWidget(b3)
        self.result = QLabel()
        self.result.setWordWrap(True)
        self.result.setProperty("role", "sub")
        right.addWidget(self.result)
        right.addStretch(1)
        root.addLayout(right, 1)
        self.reload()

    def reload(self) -> None:
        self.info.setText(tr(
            "Как запустить новеллу:\n"
            "1. Установите Ren'Py (renpy.org) и создайте в нём новый проект.\n"
            "2. Нажмите «Экспортировать в мой проект Ren'Py…» и выберите папку этого проекта.\n"
            "3. В Ren'Py нажмите «Запустить проект».\n\n"
            "Программа заменит script.rpy и добавит vn_setup.rpy, vn_menu.rpy и папку vn_assets. "
            "Остальные файлы проекта Ren'Py она не трогает."))
        self.check()

    def check(self) -> None:
        issues = validate(self.ws.project)
        self.lst.clear()
        if not issues:
            self.lst.addItem(tr("Всё в порядке: проблем не найдено."))
            return
        order = {"error": 0, "warn": 1, "info": 2}
        for i in sorted(issues, key=lambda x: order[x.level]):
            it = QListWidgetItem(f"{MARKS[i.level]}  {i.text}")
            it.setForeground(QBrush(QColor(COLORS[i.level])))
            it.setData(Qt.ItemDataRole.UserRole, i.block)
            self.lst.addItem(it)

    def open_issue(self, item) -> None:
        bid = item.data(Qt.ItemDataRole.UserRole)
        if bid:
            self.ws.goto_block(bid)

    def _errors(self) -> int:
        return sum(1 for i in validate(self.ws.project) if i.level == "error")

    def _show_report(self, rep) -> None:
        text = tr("Готово. Создано файлов: {}. Папка: {}").format(len(rep.files), rep.out_dir)
        if rep.warnings:
            text += "\n" + tr("Предупреждения:") + "\n- " + "\n- ".join(rep.warnings[:8])
        self.result.setText(text)

    def save_and_export(self) -> None:
        if self._errors():
            QMessageBox.warning(self, tr("Есть ошибки"), tr(
                "В проекте есть ошибки (красные пункты). Экспорт всё равно выполнится, но игра может работать неправильно."))
        rep = self.ws.save()
        if rep:
            self._show_report(rep)
        self.check()

    def export_to_renpy(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr("Папка вашего проекта Ren'Py"))
        if not folder:
            return
        path = Path(folder)
        if path.name == "game":
            game = path
        elif (path / "game").is_dir():
            game = path / "game"
        else:
            QMessageBox.warning(self, tr("Экспорт"), tr(
                "В выбранной папке нет папки «game». Выберите папку проекта Ren'Py (ту, где лежит game)."))
            return
        try:
            self.ws.save()
            rep = export_project(self.ws.project, game)
        except Exception as e:
            QMessageBox.warning(self, tr("Экспорт"), str(e))
            return
        self._show_report(rep)

    def open_folder(self) -> None:
        folder = self.ws.export_dir()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
