"""Окно открытого проекта: верхняя панель, вкладки и общие операции (сохранение, отмена)."""
from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QListWidget, QMessageBox, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from ..core.exporter import Report, export_project
from ..core.i18n import tr
from ..core.spell import SpellContext
from .editor import EditorPage
from .export_page import ExportPage
from .library import LibraryPage
from .menu_designer import MenuPage
from .style_page import StylePage
from .theme import AudioPreview, clear_thumbs

PAGES = ["editor", "library", "menu", "style", "export"]
PAGE_NAMES = ["Сценарий", "Библиотека", "Меню игры", "Оформление", "Проверка и экспорт"]


class Workspace(QWidget):
    closed = Signal()

    def __init__(self, project, settings, parent=None) -> None:
        super().__init__(parent)
        self.project = project
        self.settings = settings
        self.dirty = False
        self.undo_stack: List[str] = []
        self.redo_stack: List[str] = []
        self.audio = AudioPreview(settings.volume)
        self.spell = SpellContext(project, settings.spell_lang, on_ignore=self.mark_dirty)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top = QHBoxLayout()
        top.setContentsMargins(14, 10, 14, 10)
        back = QPushButton("‹  " + tr("Проекты"))
        back.clicked.connect(self.back)
        top.addWidget(back)
        self.title = QLabel(project.name)
        self.title.setProperty("role", "h2")
        top.addWidget(self.title)
        top.addStretch(1)
        self.status = QLabel("")
        self.status.setProperty("role", "sub")
        top.addWidget(self.status)
        self.btn_save = QPushButton(tr("Сохранить проект"))
        self.btn_save.setProperty("accent", True)
        self.btn_save.clicked.connect(lambda: self.save())
        top.addWidget(self.btn_save)
        root.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(0)
        self.nav = QListWidget()
        self.nav.setFixedWidth(170)
        for name in PAGE_NAMES:
            self.nav.addItem(tr(name))
        body.addWidget(self.nav)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        root.addLayout(body, 1)

        self.editor = EditorPage(self)
        self.library = LibraryPage(self)
        self.menu = MenuPage(self)
        self.style_page = StylePage(self)
        self.export = ExportPage(self)
        for w in (self.editor, self.library, self.menu, self.style_page, self.export):
            self.pages.addWidget(w)
        self.nav.currentRowChanged.connect(self.on_nav)
        self.nav.setCurrentRow(0)

        sc = QShortcut(QKeySequence(QKeySequence.StandardKey.Save), self)
        sc.activated.connect(lambda: self.save())
        for key, fn in (("Ctrl+Z", self.undo), ("Ctrl+Shift+Z", self.redo), ("Ctrl+Y", self.redo)):
            s = QShortcut(QKeySequence(key), self.editor)
            s.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            s.activated.connect(fn)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.autosave)
        self.apply_autosave()

    # -------------------------------------------------------------- навигация
    def show_page(self, name: str) -> None:
        if name in PAGES:
            self.nav.setCurrentRow(PAGES.index(name))

    def on_nav(self, row: int) -> None:
        if row < 0:
            return
        self.pages.setCurrentIndex(row)
        name = PAGES[row]
        if name == "editor":
            self.editor.refresh_soft()
        elif name == "library":
            self.library.refresh()
        elif name == "menu":
            self.menu.reload()
        elif name == "style":
            self.style_page.reload()
        elif name == "export":
            self.export.reload()

    def goto_block(self, bid: str) -> None:
        self.show_page("editor")
        self.editor.select_block(bid)

    def assets_changed(self) -> None:
        clear_thumbs()
        self.editor.preview.refresh()

    # ------------------------------------------------------------- состояние
    def mark_dirty(self) -> None:
        self.dirty = True
        self.status.setText(tr("Есть несохранённые изменения"))

    def push_undo(self) -> None:
        self.undo_stack.append(self.project.snapshot_blocks())
        if len(self.undo_stack) > 60:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self) -> None:
        if not self.undo_stack:
            return
        self.redo_stack.append(self.project.snapshot_blocks())
        self.project.restore_blocks(self.undo_stack.pop())
        self.mark_dirty()
        self.editor.reload()

    def redo(self) -> None:
        if not self.redo_stack:
            return
        self.undo_stack.append(self.project.snapshot_blocks())
        self.project.restore_blocks(self.redo_stack.pop())
        self.mark_dirty()
        self.editor.reload()

    # ------------------------------------------------------------ сохранение
    def export_dir(self) -> Path:
        return self.project.root / "renpy_export"

    def save(self) -> Optional[Report]:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.project.save()
            rep = export_project(self.project, self.export_dir() / "game")
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, tr("Не удалось сохранить"), str(e))
            return None
        QApplication.restoreOverrideCursor()
        self.dirty = False
        self.status.setText(tr("Сохранено") + " " + time.strftime("%H:%M"))
        return rep

    def apply_autosave(self) -> None:
        self.timer.stop()
        if self.settings.autosave:
            self.timer.start(max(1, self.settings.autosave_minutes) * 60000)

    def autosave(self) -> None:
        if self.dirty and self.settings.autosave:
            try:
                self.project.save()
                self.dirty = False
                self.status.setText(tr("Автосохранено") + " " + time.strftime("%H:%M"))
            except Exception:
                pass

    def request_close(self) -> bool:
        """True — можно закрывать проект."""
        if not self.dirty:
            return True
        box = QMessageBox(self)
        box.setWindowTitle(tr("Несохранённые изменения"))
        box.setText(tr("Сохранить проект перед выходом?"))
        yes = box.addButton(tr("Сохранить"), QMessageBox.ButtonRole.AcceptRole)
        no = box.addButton(tr("Не сохранять"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(tr("Отмена"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is yes:
            return self.save() is not None
        return clicked is no

    def back(self) -> None:
        if self.request_close():
            self.audio.stop()
            self.timer.stop()
            self.closed.emit()
