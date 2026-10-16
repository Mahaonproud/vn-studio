"""Оформление текста новеллы с живым превью."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget)

from ..core import assets as A
from ..core.i18n import tr
from ..core.model import SceneState
from .dialogs import ColorButton
from .preview import ScenePreview


class StylePage(QWidget):
    def __init__(self, ws, parent=None) -> None:
        super().__init__(parent)
        self.ws = ws
        self._loading = False
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(16)

        panel = QWidget()
        panel.setFixedWidth(400)
        v = QVBoxLayout(panel)
        h = QLabel(tr("Оформление текста"))
        h.setProperty("role", "h2")
        v.addWidget(h)
        form = QFormLayout()
        form.setSpacing(10)
        v.addLayout(form)

        self.col = ColorButton("#ffffff")
        self.op = QSlider(Qt.Orientation.Horizontal)
        self.op.setRange(5, 100)
        self.op_lbl = QLabel("100%")
        row = QHBoxLayout()
        row.addWidget(self.op, 1)
        row.addWidget(self.op_lbl)
        opw = QWidget()
        opw.setLayout(row)
        self.size = QSpinBox()
        self.size.setRange(12, 120)
        self.size.setSuffix(" px")
        self.kern = QDoubleSpinBox()
        self.kern.setRange(-5.0, 20.0)
        self.kern.setSingleStep(0.5)
        self.kern.setDecimals(1)
        self.kern.setSuffix(" px")
        self.thought = QCheckBox(tr("Мысли героя — курсивом"))
        self.font_lbl = QLabel()
        self.font_lbl.setProperty("role", "sub")
        b_font = QPushButton(tr("Выбрать свой шрифт (.ttf, .otf)…"))
        b_font.clicked.connect(self.pick_font)
        b_reset = QPushButton(tr("Шрифт по умолчанию"))
        b_reset.clicked.connect(self.reset_font)
        self.box_on = QCheckBox(tr("Своя подложка под текстом"))
        self.box_col = ColorButton("#000000")
        self.box_op = QSlider(Qt.Orientation.Horizontal)
        self.box_op.setRange(0, 100)
        self.box_op_lbl = QLabel("60%")
        row2 = QHBoxLayout()
        row2.addWidget(self.box_op, 1)
        row2.addWidget(self.box_op_lbl)
        box_w = QWidget()
        box_w.setLayout(row2)

        form.addRow(tr("Цвет текста"), self.col)
        form.addRow(tr("Непрозрачность текста"), opw)
        form.addRow(tr("Размер букв"), self.size)
        form.addRow(tr("Расстояние между буквами"), self.kern)
        form.addRow("", self.thought)
        form.addRow(tr("Шрифт"), self.font_lbl)
        form.addRow("", b_font)
        form.addRow("", b_reset)
        form.addRow("", self.box_on)
        form.addRow(tr("Цвет подложки"), self.box_col)
        form.addRow(tr("Непрозрачность подложки"), box_w)
        v.addStretch(1)
        root.addWidget(panel)

        right = QVBoxLayout()
        lab = QLabel(tr("Так будет выглядеть текст в игре"))
        lab.setProperty("role", "sub")
        right.addWidget(lab)
        self.preview = ScenePreview()
        right.addWidget(self.preview, 1)
        root.addLayout(right, 1)

        self.col.changed.connect(lambda _c: self.apply())
        self.box_col.changed.connect(lambda _c: self.apply())
        self.op.valueChanged.connect(lambda _v: self.apply())
        self.box_op.valueChanged.connect(lambda _v: self.apply())
        self.size.valueChanged.connect(lambda _v: self.apply())
        self.kern.valueChanged.connect(lambda _v: self.apply())
        self.thought.toggled.connect(lambda _v: self.apply())
        self.box_on.toggled.connect(lambda _v: self.apply())
        self.reload()

    @property
    def p(self):
        return self.ws.project

    def reload(self) -> None:
        s = self.p.style
        self._loading = True
        self.col.set_color(s.color)
        self.op.setValue(int(s.opacity))
        self.size.setValue(int(s.size))
        self.kern.setValue(float(s.kerning))
        self.thought.setChecked(bool(s.thought_italic))
        self.box_on.setChecked(bool(s.box_enabled))
        self.box_col.set_color(s.box_color)
        self.box_op.setValue(int(s.box_opacity))
        self.font_lbl.setText(s.font_file.split("/")[-1] if s.font_file else tr("стандартный"))
        self._loading = False
        self.op_lbl.setText(f"{self.op.value()}%")
        self.box_op_lbl.setText(f"{self.box_op.value()}%")
        self.preview.set_project(self.p)
        self.update_preview()

    def update_preview(self) -> None:
        who = self.p.characters[0].id if self.p.characters else ""
        self.preview.set_scene(SceneState(), who, tr("Какая сегодня хорошая погода? Просто пример текста для проверки оформления."))

    def apply(self) -> None:
        if self._loading:
            return
        s = self.p.style
        s.color = self.col.color()
        s.opacity = self.op.value()
        s.size = self.size.value()
        s.kerning = self.kern.value()
        s.thought_italic = self.thought.isChecked()
        s.box_enabled = self.box_on.isChecked()
        s.box_color = self.box_col.color()
        s.box_opacity = self.box_op.value()
        self.op_lbl.setText(f"{s.opacity}%")
        self.box_op_lbl.setText(f"{s.box_opacity}%")
        self.ws.mark_dirty()
        self.preview.update()

    def pick_font(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, tr("Файл шрифта"), "", tr("Шрифты") + " (*.ttf *.otf)")
        if not f:
            return
        try:
            self.p.style.font_file = A.import_font(self.p, f)
        except Exception as e:
            QMessageBox.warning(self, tr("Шрифт"), str(e))
            return
        self.ws.mark_dirty()
        self.font_lbl.setText(self.p.style.font_file.split("/")[-1])
        self.preview.refresh()
        self.ws.assets_changed()

    def reset_font(self) -> None:
        self.p.style.font_file = ""
        self.font_lbl.setText(tr("стандартный"))
        self.ws.mark_dirty()
        self.preview.refresh()
        self.ws.assets_changed()
