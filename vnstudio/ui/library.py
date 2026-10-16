"""Библиотека ресурсов проекта: загрузить всё сразу и добавлять ещё по одному."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox, QProgressDialog, QPushButton,
                               QVBoxLayout, QWidget)

from ..core import assets as A
from ..core.i18n import tr
from .dialogs import CharacterDialog
from .theme import clear_thumbs, icon_for

CATS = [
    ("backgrounds", "Фоны"),
    ("characters", "Персонажи"),
    ("effects", "Эффекты"),
    ("music", "Музыка"),
    ("loading", "Загрузочные экраны"),
    ("menu_bg", "Экраны меню"),
]
FILTERS = {
    "backgrounds": "Изображения (*.png *.jpg *.jpeg *.webp *.bmp *.gif)",
    "effects": "Изображения (*.png *.jpg *.jpeg *.webp *.bmp *.gif)",
    "loading": "Изображения (*.png *.jpg *.jpeg *.webp *.bmp *.gif)",
    "menu_bg": "Изображения (*.png *.jpg *.jpeg *.webp *.bmp *.gif)",
    "music": "Музыка (*.ogg *.mp3 *.wav *.opus *.flac)",
}


class LibraryPage(QWidget):
    def __init__(self, ws, parent=None) -> None:
        super().__init__(parent)
        self.ws = ws
        self.cat = "backgrounds"
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        left = QWidget()
        left.setFixedWidth(220)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.cats = QListWidget()
        for key, name in CATS:
            it = QListWidgetItem(tr(name))
            it.setData(Qt.ItemDataRole.UserRole, key)
            self.cats.addItem(it)
        self.cats.setCurrentRow(0)
        self.cats.currentRowChanged.connect(self.on_cat)
        ll.addWidget(self.cats)
        b_all = QPushButton(tr("Загрузить всё из папки…"))
        b_all.setProperty("accent", True)
        b_all.setToolTip(tr("Выберите папку, в которой лежат подпапки «фоны», «эффекты», «музыка», "
                            "«загрузочные», «экраны», «персонажи»"))
        b_all.clicked.connect(self.bulk)
        ll.addWidget(b_all)
        root.addWidget(left)

        right = QVBoxLayout()
        head = QHBoxLayout()
        self.title = QLabel()
        self.title.setProperty("role", "h2")
        head.addWidget(self.title, 1)
        self.b_add = QPushButton(tr("Добавить ещё…"))
        self.b_add.setProperty("accent", True)
        self.b_add.clicked.connect(self.add_more)
        self.b_builtin = QPushButton(tr("Встроенные эффекты"))
        self.b_builtin.clicked.connect(self.add_builtin)
        self.b_play = QPushButton(tr("Прослушать"))
        self.b_play.clicked.connect(self.play)
        self.b_stop = QPushButton(tr("Стоп"))
        self.b_stop.clicked.connect(lambda: self.ws.audio.stop())
        self.b_edit = QPushButton(tr("Изменить…"))
        self.b_edit.clicked.connect(self.edit_item)
        self.b_ren = QPushButton(tr("Переименовать"))
        self.b_ren.clicked.connect(self.rename)
        self.b_del = QPushButton(tr("Удалить"))
        self.b_del.setProperty("danger", True)
        self.b_del.clicked.connect(self.remove)
        for b in (self.b_add, self.b_builtin, self.b_play, self.b_stop, self.b_edit, self.b_ren, self.b_del):
            head.addWidget(b)
        right.addLayout(head)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setProperty("role", "sub")
        right.addWidget(self.hint)
        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setMovement(QListWidget.Movement.Static)
        self.grid.setIconSize(QSize(160, 90))
        self.grid.setGridSize(QSize(190, 140))
        self.grid.setWordWrap(True)
        self.grid.setSpacing(6)
        self.grid.itemDoubleClicked.connect(lambda _it: self.edit_item())
        right.addWidget(self.grid, 1)
        root.addLayout(right, 1)
        self.refresh()

    @property
    def p(self):
        return self.ws.project

    # ------------------------------------------------------------------ вид
    def on_cat(self, row: int) -> None:
        it = self.cats.item(row)
        if it:
            self.cat = it.data(Qt.ItemDataRole.UserRole)
            self.refresh()

    def refresh(self) -> None:
        keep = self.cur_id()
        cat = self.cat
        names = dict(CATS)
        self.title.setText(tr(names[cat]))
        is_char = cat == "characters"
        self.b_builtin.setVisible(cat == "effects")
        self.b_play.setVisible(cat == "music")
        self.b_stop.setVisible(cat == "music")
        self.b_edit.setVisible(is_char)
        self.b_add.setText(tr("Добавить персонажа…") if is_char else tr("Добавить ещё…"))
        self.grid.clear()
        if is_char:
            self.grid.setIconSize(QSize(110, 140))
            self.grid.setGridSize(QSize(150, 200))
            for c in self.p.characters:
                icon = QIcon()
                if c.emotions:
                    icon = icon_for(str(self.p.abs(next(iter(c.emotions.values())))), 110, 140)
                it = QListWidgetItem(icon, f"{c.name}\n({len(c.emotions)})")
                it.setData(Qt.ItemDataRole.UserRole, c.id)
                self.grid.addItem(it)
            n = len(self.p.characters)
            self.hint.setText("" if n else tr(
                "Персонажей пока нет. Нажмите «Добавить персонажа…», а затем добавьте ему эмоции (картинки)."))
        else:
            self.grid.setIconSize(QSize(160, 90))
            self.grid.setGridSize(QSize(190, 140))
            for a in self.p.assets[cat]:
                icon = QIcon()
                text = a.name
                if cat != "music" and a.file and a.kind in ("file", "image"):
                    icon = icon_for(str(self.p.abs(a.file)), 160, 90)
                elif a.kind in ("solid", "shake", "flash"):
                    text += "\n(" + tr("встроенный") + ")"
                it = QListWidgetItem(icon, text)
                it.setData(Qt.ItemDataRole.UserRole, a.id)
                self.grid.addItem(it)
            if not self.p.assets[cat]:
                self.hint.setText(tr("Здесь пока пусто. Нажмите «Загрузить всё из папки…» слева или «Добавить ещё…»."))
            else:
                self.hint.setText("")
        for i in range(self.grid.count()):
            if keep and self.grid.item(i).data(Qt.ItemDataRole.UserRole) == keep:
                self.grid.setCurrentRow(i)
                break

    def cur_id(self) -> str:
        it = self.grid.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else ""

    def changed(self) -> None:
        self.ws.mark_dirty()
        self.refresh()
        self.ws.assets_changed()

    # ------------------------------------------------------------ действия
    def progress(self, text: str, total: int) -> QProgressDialog:
        dlg = QProgressDialog(text, "", 0, max(1, total), self)
        dlg.setCancelButton(None)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setValue(0)
        return dlg

    def bulk(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr("Папка со всеми ресурсами"))
        if not folder:
            return
        dlg = self.progress(tr("Загружаю ресурсы…"), 100)

        def cb(i: int, n: int, name: str) -> None:
            dlg.setMaximum(max(1, n))
            dlg.setValue(i)
            if name:
                dlg.setLabelText(tr("Загружаю: {}").format(name))
            QApplication.processEvents()

        try:
            s = A.bulk_import(self.p, folder, cb)
        except Exception as e:
            dlg.close()
            QMessageBox.warning(self, tr("Загрузка"), str(e))
            return
        dlg.close()
        total = sum(v for k, v in s.items() if k != "skipped")
        QMessageBox.information(self, tr("Готово"), tr(
            "Загружено: фонов — {}, персонажей — {}, эффектов — {}, музыки — {}, загрузочных экранов — {}, "
            "экранов меню — {}. Пропущено (уже были): {}.").format(
            s["backgrounds"], s["characters"], s["effects"], s["music"], s["loading"], s["menu_bg"], s["skipped"]))
        if total:
            clear_thumbs()
            self.changed()

    def add_more(self) -> None:
        if self.cat == "characters":
            name, ok = QInputDialog.getText(self, tr("Новый персонаж"), tr("Имя персонажа:"), QLineEdit.EchoMode.Normal, "")
            if not ok or not name.strip():
                return
            c = A.add_character(self.p, name)
            self.changed()
            self.open_character(c)
            return
        files, _ = QFileDialog.getOpenFileNames(self, tr("Добавить файлы"), "", tr(FILTERS[self.cat]))
        if not files:
            return
        errors = []
        for f in files:
            try:
                A.import_asset(self.p, self.cat, f)
            except Exception as e:
                errors.append(str(e))
        if errors:
            QMessageBox.warning(self, tr("Не все файлы загружены"), "\n".join(errors[:6]))
        self.changed()

    def add_builtin(self) -> None:
        dlg = self.progress(tr("Создаю встроенные эффекты…"), 0)
        QApplication.processEvents()
        n = A.add_builtin_effects(self.p)
        dlg.close()
        if n == 0:
            QMessageBox.information(self, tr("Встроенные эффекты"), tr("Все встроенные эффекты уже добавлены."))
        self.changed()

    def open_character(self, c) -> None:
        dlg = CharacterDialog(self.p, c, self)
        dlg.run()
        if dlg.touched:
            clear_thumbs()
            self.changed()

    def edit_item(self) -> None:
        if self.cat != "characters":
            return
        c = self.p.get_char(self.cur_id())
        if c:
            self.open_character(c)

    def rename(self) -> None:
        cid = self.cur_id()
        if not cid:
            return
        obj = self.p.get_char(cid) if self.cat == "characters" else self.p.find_asset(cid)
        if not obj:
            return
        name, ok = QInputDialog.getText(self, tr("Переименовать"), tr("Название:"), QLineEdit.EchoMode.Normal, obj.name)
        if ok and name.strip():
            obj.name = name.strip()
            self.changed()

    def remove(self) -> None:
        cid = self.cur_id()
        if not cid:
            return
        used = self.is_used(cid)
        text = tr("Удалить выбранное?")
        if used:
            text += " " + tr("Оно используется в сценарии — в проверке проекта появятся ошибки.")
        if QMessageBox.question(self, tr("Удалить"), text,
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) \
                != QMessageBox.StandardButton.Yes:
            return
        if self.cat == "characters":
            A.remove_character(self.p, cid)
        else:
            A.remove_asset(self.p, cid)
        self.changed()

    def is_used(self, oid: str) -> bool:
        for b in self.p.blocks:
            for s in b.steps:
                if oid in (s.data.get("asset"), s.data.get("char"), s.data.get("who")):
                    return True
        m = self.p.menu
        return oid in (m.bg, m.music) or oid in m.effects or any(i.get("asset") == oid for i in m.loading)

    def play(self) -> None:
        a = self.p.find_asset(self.cur_id())
        if not a or not a.file:
            return
        if not self.ws.audio.play(self.p.abs(a.file)):
            QMessageBox.information(self, tr("Музыка"), tr("Предпрослушивание недоступно: не найден модуль QtMultimedia."))
