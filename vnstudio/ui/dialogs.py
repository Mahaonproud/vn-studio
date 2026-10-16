"""Диалоговые окна редактора."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSlider, QSpinBox,
                               QVBoxLayout, QWidget)

from ..core import assets as A
from ..core.i18n import tr
from ..core.model import POSITIONS
from ..core.settings import Settings
from .theme import icon_for, thumb

POS_NAMES = {"left": "Слева", "center": "По центру", "right": "Справа"}
TRANS_NAMES = [("fade", "Затемнение"), ("dissolve", "Плавно"), ("none", "Сразу")]


class BaseDialog(QDialog):
    def __init__(self, title: str, parent=None, ok_text: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.ok = False
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(22, 20, 22, 16)
        self.root.setSpacing(12)
        self.form = QFormLayout()
        self.form.setSpacing(10)
        self.root.addLayout(self.form)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        okb = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        okb.setText(ok_text or tr("Готово"))
        okb.setProperty("accent", True)
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Отмена"))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.root.addWidget(self.buttons)

    def add_widget(self, w: QWidget) -> None:
        self.root.insertWidget(self.root.count() - 1, w)

    def accept(self) -> None:
        self.ok = True
        super().accept()

    def run(self) -> bool:
        self.exec()
        return self.ok


class ColorButton(QPushButton):
    changed = Signal(str)

    def __init__(self, color: str = "#ffffff", parent=None) -> None:
        super().__init__(parent)
        self._c = color
        self.setFixedWidth(96)
        self._paint()
        self.clicked.connect(self._pick)

    def color(self) -> str:
        return self._c

    def set_color(self, c: str) -> None:
        self._c = c
        self._paint()

    def _paint(self) -> None:
        fg = "#000000" if QColor(self._c).lightness() > 128 else "#ffffff"
        self.setText(self._c.upper())
        self.setStyleSheet(f"QPushButton {{ background: {self._c}; color: {fg}; border: 1px solid #888888; }}")

    def _pick(self) -> None:
        c = QColorDialog.getColor(QColor(self._c), self, tr("Выберите цвет"))
        if c.isValid():
            self._c = c.name()
            self._paint()
            self.changed.emit(self._c)


def asset_combo(project, cat: str, none_text=None, current: str = "") -> QComboBox:
    cb = QComboBox()
    cb.setIconSize(QSize(64, 36))
    cb.setMinimumWidth(260)
    if none_text is not None:
        cb.addItem(none_text, "")
    for a in project.assets[cat]:
        icon = QIcon()
        if a.file and cat != "music" and a.kind in ("file", "image"):
            icon = icon_for(str(project.abs(a.file)), 64, 36)
        label = a.name
        if cat == "effects" and a.kind in ("shake", "flash"):
            label += "  (" + tr("разовый") + ")"
        cb.addItem(icon, label, a.id)
    i = cb.findData(current)
    if i >= 0:
        cb.setCurrentIndex(i)
    return cb


def trans_combo(default: str = "fade") -> QComboBox:
    cb = QComboBox()
    for key, name in TRANS_NAMES:
        cb.addItem(tr(name), key)
    cb.setCurrentIndex(max(0, cb.findData(default)))
    return cb


def pos_combo(current: str = "center") -> QComboBox:
    cb = QComboBox()
    for key in POSITIONS:
        cb.addItem(tr(POS_NAMES[key]), key)
    cb.setCurrentIndex(max(0, cb.findData(current)))
    return cb


class PickDialog(BaseDialog):
    """Выбор одного пункта из списка (+ необязательное число)."""

    def __init__(self, title, label, items, parent=None, current=None, spin=None, ok_text=""):
        super().__init__(title, parent, ok_text)
        self.combo = QComboBox()
        self.combo.setIconSize(QSize(64, 36))
        self.combo.setMinimumWidth(260)
        for it in items:
            text, value = it[0], it[1]
            icon = it[2] if len(it) > 2 and it[2] is not None else QIcon()
            self.combo.addItem(icon, text, value)
        if current is not None:
            self.combo.setCurrentIndex(max(0, self.combo.findData(current)))
        self.form.addRow(label, self.combo)
        self.spin = None
        if spin:
            lab, lo, hi, default = spin
            self.spin = QDoubleSpinBox()
            self.spin.setRange(lo, hi)
            self.spin.setDecimals(1)
            self.spin.setSingleStep(0.5)
            self.spin.setValue(default)
            self.form.addRow(lab, self.spin)

    def value(self):
        return self.combo.currentData()

    def spin_value(self) -> float:
        return self.spin.value() if self.spin else 0.0


class CharPicker(QWidget):
    """Персонаж + эмоция + позиция + маленькое превью."""

    def __init__(self, project, allow_none=False, char="", emotion="", pos="center", parent=None) -> None:
        super().__init__(parent)
        self.project = project
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        form = QFormLayout()
        form.setSpacing(10)
        self.cb_char = QComboBox()
        self.cb_char.setMinimumWidth(240)
        if allow_none:
            self.cb_char.addItem(tr("— без персонажа (мысли героя) —"), "")
        for c in project.characters:
            self.cb_char.addItem(c.name, c.id)
        self.cb_emo = QComboBox()
        self.cb_pos = pos_combo(pos)
        form.addRow(tr("Персонаж"), self.cb_char)
        form.addRow(tr("Эмоция"), self.cb_emo)
        form.addRow(tr("Где стоит"), self.cb_pos)
        lay.addLayout(form)
        self.pic = QLabel()
        self.pic.setFixedSize(110, 150)
        self.pic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.pic)
        i = self.cb_char.findData(char)
        if i >= 0:
            self.cb_char.setCurrentIndex(i)
        self._fill(emotion)
        self.cb_char.currentIndexChanged.connect(lambda _i: self._fill(""))
        self.cb_emo.currentIndexChanged.connect(lambda _i: self._pic())

    def _fill(self, emotion: str) -> None:
        self.cb_emo.blockSignals(True)
        self.cb_emo.clear()
        c = self.project.get_char(self.cb_char.currentData() or "")
        if c:
            for emo in c.emotions:
                self.cb_emo.addItem(emo, emo)
            i = self.cb_emo.findData(emotion)
            if i >= 0:
                self.cb_emo.setCurrentIndex(i)
        self.cb_emo.setEnabled(c is not None)
        self.cb_pos.setEnabled(c is not None)
        self.cb_emo.blockSignals(False)
        self._pic()

    def _pic(self) -> None:
        c = self.project.get_char(self.cb_char.currentData() or "")
        rel = c.emotions.get(self.cb_emo.currentData() or "", "") if c else ""
        if rel:
            pm = thumb(str(self.project.abs(rel)), 110, 150)
            if not pm.isNull():
                self.pic.setPixmap(pm)
                return
        self.pic.clear()

    def value(self) -> dict:
        return {"char": self.cb_char.currentData() or "", "emotion": self.cb_emo.currentData() or "",
                "pos": self.cb_pos.currentData() or "center"}


class NewDialogDialog(BaseDialog):
    """Мастер «Начать новый диалог»: фон → музыка → персонаж."""

    def __init__(self, project, parent=None) -> None:
        super().__init__(tr("Новый диалог"), parent, tr("Начать"))
        hint = QLabel(tr("Выберите фон, музыку и (если нужно) персонажа. Потом всё можно изменить."))
        hint.setProperty("role", "sub")
        hint.setWordWrap(True)
        self.root.insertWidget(0, hint)
        self.cb_bg = asset_combo(project, "backgrounds", tr("— без фона —"))
        self.cb_music = asset_combo(project, "music", tr("— без музыки —"))
        self.form.addRow(tr("1. Фон"), self.cb_bg)
        self.form.addRow(tr("2. Музыка"), self.cb_music)
        self.picker = CharPicker(project, True)
        self.add_widget(QLabel(tr("3. Персонаж")))
        self.add_widget(self.picker)

    def values(self) -> dict:
        v = self.picker.value()
        v.update({"bg": self.cb_bg.currentData() or "", "music": self.cb_music.currentData() or ""})
        return v


class BgDialog(BaseDialog):
    def __init__(self, project, current: str = "", parent=None) -> None:
        super().__init__(tr("Сменить фон"), parent)
        self.cb = asset_combo(project, "backgrounds", None, current)
        self.tr_cb = trans_combo("fade")
        self.chk = QCheckBox(tr("Новая сцена: убрать персонажей и эффекты"))
        self.form.addRow(tr("Фон"), self.cb)
        self.form.addRow(tr("Переход"), self.tr_cb)
        self.form.addRow("", self.chk)

    def values(self) -> dict:
        return {"asset": self.cb.currentData() or "", "trans": self.tr_cb.currentData(),
                "clear": self.chk.isChecked()}


class ChoiceDialog(BaseDialog):
    def __init__(self, texts=None, parent=None) -> None:
        super().__init__(tr("Варианты ответа"), parent)
        hint = QLabel(tr("От 2 до 4 вариантов. Для каждого создастся своя ветка."))
        hint.setProperty("role", "sub")
        self.root.insertWidget(0, hint)
        self.edits = []
        texts = list(texts or [])
        for i in range(4):
            e = QLineEdit()
            e.setPlaceholderText(tr("Вариант {}").format(i + 1))
            if i < len(texts):
                e.setText(texts[i])
            self.edits.append(e)
            self.form.addRow(f"{i + 1}.", e)

    def accept(self) -> None:
        if len(self.values()) < 2:
            QMessageBox.information(self, tr("Варианты ответа"), tr("Заполните хотя бы два варианта."))
            return
        super().accept()

    def values(self) -> list:
        return [e.text().strip() for e in self.edits if e.text().strip()]


class CharacterDialog(BaseDialog):
    """Имя, цвет имени и эмоции (картинки) персонажа."""

    def __init__(self, project, char, parent=None) -> None:
        super().__init__(tr("Персонаж"), parent, tr("Сохранить"))
        self.project = project
        self.char = char
        self.touched = False
        self.name = QLineEdit(char.name)
        self.color = ColorButton(char.color)
        self.form.addRow(tr("Имя"), self.name)
        self.form.addRow(tr("Цвет имени"), self.color)
        self.add_widget(QLabel(tr("Эмоции (по одной картинке на эмоцию):")))
        self.lst = QListWidget()
        self.lst.setIconSize(QSize(56, 72))
        self.lst.setMinimumHeight(220)
        self.add_widget(self.lst)
        row = QHBoxLayout()
        b_add = QPushButton(tr("Добавить эмоции…"))
        b_ren = QPushButton(tr("Переименовать"))
        b_del = QPushButton(tr("Удалить"))
        b_del.setProperty("danger", True)
        for b in (b_add, b_ren, b_del):
            row.addWidget(b)
        w = QWidget()
        w.setLayout(row)
        self.add_widget(w)
        b_add.clicked.connect(self.add_emotions)
        b_ren.clicked.connect(self.rename_emotion)
        b_del.clicked.connect(self.delete_emotion)
        self.refresh()

    def refresh(self) -> None:
        self.lst.clear()
        for emo, rel in self.char.emotions.items():
            it = QListWidgetItem(icon_for(str(self.project.abs(rel)), 56, 72), emo)
            it.setData(Qt.ItemDataRole.UserRole, emo)
            self.lst.addItem(it)

    def add_emotions(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, tr("Картинки эмоций"), "",
                                                tr("Изображения") + " (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        errors = []
        for f in files:
            try:
                A.add_emotion(self.project, self.char, Path(f).stem, f)
                self.touched = True
            except Exception as e:
                errors.append(str(e))
        if errors:
            QMessageBox.warning(self, tr("Ошибка"), "\n".join(errors))
        self.refresh()

    def _current(self) -> str:
        it = self.lst.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else ""

    def rename_emotion(self) -> None:
        old = self._current()
        if not old:
            return
        new, ok = QInputDialog.getText(self, tr("Переименовать эмоцию"), tr("Новое название:"), text=old)
        if ok and new.strip() and new.strip() != old:
            if new.strip() in self.char.emotions:
                QMessageBox.warning(self, tr("Ошибка"), tr("Такая эмоция уже есть."))
                return
            A.rename_emotion(self.project, self.char, old, new.strip())
            self.touched = True
            self.refresh()

    def delete_emotion(self) -> None:
        emo = self._current()
        if not emo:
            return
        if QMessageBox.question(self, tr("Удалить эмоцию"), tr("Удалить эмоцию «{}»?").format(emo),
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) \
                == QMessageBox.StandardButton.Yes:
            A.remove_emotion(self.project, self.char, emo)
            self.touched = True
            self.refresh()

    def accept(self) -> None:
        name = self.name.text().strip()
        if name and name != self.char.name:
            self.char.name = name
            self.touched = True
        if self.color.color() != self.char.color:
            self.char.color = self.color.color()
            self.touched = True
        super().accept()


class SettingsDialog(BaseDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(tr("Настройки"), parent, tr("Сохранить"))
        self.s = settings
        self.projects_dir = str(settings.projects_path())
        self.cb_lang = QComboBox()
        self.cb_lang.addItem("Русский", "ru")
        self.cb_lang.addItem("English", "en")
        self.cb_lang.setCurrentIndex(max(0, self.cb_lang.findData(settings.language)))
        self.cb_theme = QComboBox()
        self.cb_theme.addItem(tr("Тёмная"), "dark")
        self.cb_theme.addItem(tr("Светлая"), "light")
        self.cb_theme.setCurrentIndex(max(0, self.cb_theme.findData(settings.theme)))
        self.cb_spell = QComboBox()
        self.cb_spell.addItem("Русский", "ru")
        self.cb_spell.addItem("English", "en")
        self.cb_spell.setCurrentIndex(max(0, self.cb_spell.findData(settings.spell_lang)))
        self.vol = QSlider(Qt.Orientation.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(settings.volume)
        self.chk_auto = QCheckBox(tr("Автосохранение проекта"))
        self.chk_auto.setChecked(settings.autosave)
        self.sp_min = QSpinBox()
        self.sp_min.setRange(1, 60)
        self.sp_min.setValue(settings.autosave_minutes)
        self.sp_min.setSuffix(" " + tr("мин"))
        self.lbl_dir = QLabel(self.projects_dir)
        self.lbl_dir.setWordWrap(True)
        b_dir = QPushButton(tr("Изменить…"))
        b_dir.clicked.connect(self.pick_dir)
        self.form.addRow(tr("Язык интерфейса"), self.cb_lang)
        self.form.addRow(tr("Оформление"), self.cb_theme)
        self.form.addRow(tr("Язык проверки орфографии"), self.cb_spell)
        self.form.addRow(tr("Громкость предпрослушивания музыки"), self.vol)
        self.form.addRow(self.chk_auto, self.sp_min)
        self.form.addRow(tr("Папка проектов"), self.lbl_dir)
        self.form.addRow("", b_dir)

    def pick_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, tr("Папка для проектов"), self.projects_dir)
        if d:
            self.projects_dir = d
            self.lbl_dir.setText(d)

    def apply(self) -> Settings:
        s = self.s
        s.language = self.cb_lang.currentData()
        s.theme = self.cb_theme.currentData()
        s.spell_lang = self.cb_spell.currentData()
        s.volume = self.vol.value()
        s.autosave = self.chk_auto.isChecked()
        s.autosave_minutes = self.sp_min.value()
        s.projects_dir = self.projects_dir
        return s
