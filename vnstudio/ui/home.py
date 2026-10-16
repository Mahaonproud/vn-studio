"""Главное меню приложения."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from ..core.i18n import tr
from ..core.model import list_projects
from ..core.settings import APP_NAME


class HomePage(QWidget):
    new_project = Signal()
    open_project = Signal(str)
    open_settings = Signal()

    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.stack = QStackedWidget()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.stack)
        self.stack.addWidget(self._menu_view())
        self.stack.addWidget(self._projects_view())

    def _menu_view(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.addStretch(2)
        col = QVBoxLayout()
        col.setSpacing(14)
        title = QLabel(APP_NAME)
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = QLabel(tr("Создавайте визуальные новеллы без единой строчки кода"))
        sub.setProperty("role", "sub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(title)
        col.addWidget(sub)
        col.addSpacing(24)
        for text, fn, accent in ((tr("Новый проект"), self.new_project.emit, True),
                                 (tr("Старые проекты"), self.show_projects, False),
                                 (tr("Настройки"), self.open_settings.emit, False)):
            b = QPushButton(text)
            b.setProperty("big", True)
            if accent:
                b.setProperty("accent", True)
            b.setFixedWidth(340)
            b.clicked.connect(lambda checked=False, fn=fn: fn())
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(b)
            row.addStretch(1)
            col.addLayout(row)
        outer.addLayout(col)
        outer.addStretch(3)
        return w

    def _projects_view(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(60, 40, 60, 40)
        head = QHBoxLayout()
        back = QPushButton("‹  " + tr("Назад"))
        back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        head.addWidget(back)
        h = QLabel(tr("Старые проекты"))
        h.setProperty("role", "h2")
        head.addWidget(h)
        head.addStretch(1)
        lay.addLayout(head)
        self.lst = QListWidget()
        self.lst.itemDoubleClicked.connect(lambda _i: self.open_current())
        lay.addWidget(self.lst, 1)
        self.empty = QLabel(tr("Проектов пока нет. Вернитесь назад и нажмите «Новый проект»."))
        self.empty.setProperty("role", "sub")
        lay.addWidget(self.empty)
        row = QHBoxLayout()
        b_open = QPushButton(tr("Открыть"))
        b_open.setProperty("accent", True)
        b_open.clicked.connect(self.open_current)
        b_dir = QPushButton(tr("Показать папку"))
        b_dir.clicked.connect(self.show_folder)
        b_del = QPushButton(tr("Удалить"))
        b_del.setProperty("danger", True)
        b_del.clicked.connect(self.delete_current)
        for b in (b_open, b_dir, b_del):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        return w

    def show_projects(self) -> None:
        self.lst.clear()
        items = list_projects(self.settings.projects_path())
        for it in items:
            when = time.strftime("%d.%m.%Y %H:%M", time.localtime(it["modified"]))
            li = QListWidgetItem(f"{it['name']}      {when}")
            li.setData(Qt.ItemDataRole.UserRole, it["path"])
            self.lst.addItem(li)
        self.empty.setVisible(not items)
        if items:
            self.lst.setCurrentRow(0)
        self.stack.setCurrentIndex(1)

    def current_path(self) -> str:
        it = self.lst.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else ""

    def open_current(self) -> None:
        p = self.current_path()
        if p:
            self.open_project.emit(p)

    def show_folder(self) -> None:
        p = self.current_path()
        if p:
            QDesktopServices.openUrl(QUrl.fromLocalFile(p))

    def delete_current(self) -> None:
        p = self.current_path()
        if not p:
            return
        if QMessageBox.question(self, tr("Удалить проект"), tr(
                "Удалить проект вместе со всеми файлами без возможности восстановления?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) \
                != QMessageBox.StandardButton.Yes:
            return
        try:
            shutil.rmtree(Path(p))
        except OSError as e:
            QMessageBox.warning(self, tr("Удалить проект"), str(e))
        self.show_projects()
