"""Конструктор главного меню новеллы: кнопки двигаются мышкой куда угодно."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QComboBox, QGraphicsItem, QGraphicsRectItem, QGraphicsScene,
                               QGraphicsSimpleTextItem, QGraphicsView, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea,
                               QSpinBox, QVBoxLayout, QWidget)

from ..core.i18n import tr
from ..core.model import default_menu_buttons
from ..core.util import short_id
from .dialogs import ColorButton, PickDialog, asset_combo
from .theme import rgba_color

ACTION_NAMES = {"start": "Играть", "load": "Продолжить (загрузка)", "preferences": "Настройки",
                "help": "Управление", "about": "Об игре", "quit": "Выход"}


class FitView(QGraphicsView):
    def _fit(self) -> None:
        if self.scene() is not None:
            self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._fit()

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self._fit()


class MenuItem(QGraphicsRectItem):
    """Надпись-кнопка, которую можно таскать мышкой."""

    def __init__(self, key: str, text: str, size: int, color: str, on_moved) -> None:
        super().__init__(0, 0, 10, 10)
        self.key = key
        self.on_moved = on_moved
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setZValue(10)
        self.label = QGraphicsSimpleTextItem(text or " ", self)
        f = QFont()
        f.setPixelSize(max(8, int(size)))
        self.label.setFont(f)
        self.label.setBrush(QBrush(QColor(color)))
        r = self.label.boundingRect()
        self.setRect(0, 0, r.width() + 16, r.height() + 8)
        self.label.setPos(8, 4)

    def paint(self, painter, option, widget=None) -> None:
        if self.isSelected():
            painter.setPen(QPen(QColor("#0a84ff"), 3, Qt.PenStyle.DashLine))
            painter.drawRect(self.rect())

    def mouseReleaseEvent(self, ev) -> None:
        super().mouseReleaseEvent(ev)
        self.on_moved(self)


class MenuPage(QWidget):
    def __init__(self, ws, parent=None) -> None:
        super().__init__(parent)
        self.ws = ws
        self._loading = False
        self._sync = False
        self.items: dict = {}
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        lay = QVBoxLayout()
        hint = QLabel(tr("Так будет выглядеть главное меню. Перетаскивайте кнопки и название мышкой."))
        hint.setProperty("role", "sub")
        lay.addWidget(hint)
        self.scene = QGraphicsScene(self)
        self.scene.selectionChanged.connect(self.on_scene_select)
        self.view = FitView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        lay.addWidget(self.view, 1)
        root.addLayout(lay, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(380)
        host = QWidget()
        form = QVBoxLayout(host)
        form.setSpacing(8)
        scroll.setWidget(host)
        root.addWidget(scroll)
        self._build_panel(form)
        self.reload()

    @property
    def p(self):
        return self.ws.project

    def _h(self, text: str) -> QLabel:
        h = QLabel(text)
        h.setProperty("role", "h2")
        return h

    def _build_panel(self, form: QVBoxLayout) -> None:
        form.addWidget(self._h(tr("Фон и музыка")))
        self.cb_bg = QComboBox()
        self.cb_music = QComboBox()
        form.addWidget(QLabel(tr("Фон меню")))
        form.addWidget(self.cb_bg)
        form.addWidget(QLabel(tr("Музыка в меню")))
        form.addWidget(self.cb_music)

        form.addWidget(self._h(tr("Загрузочные экраны")))
        self.lst_load = QListWidget()
        self.lst_load.setMaximumHeight(90)
        form.addWidget(self.lst_load)
        r = QHBoxLayout()
        b = QPushButton(tr("Добавить загрузочный экран…"))
        b.clicked.connect(self.add_loading)
        b2 = QPushButton(tr("Убрать"))
        b2.clicked.connect(self.remove_loading)
        r.addWidget(b)
        r.addWidget(b2)
        form.addLayout(r)

        form.addWidget(self._h(tr("Эффекты поверх меню")))
        self.lst_fx = QListWidget()
        self.lst_fx.setMaximumHeight(90)
        form.addWidget(self.lst_fx)
        r = QHBoxLayout()
        b = QPushButton(tr("Добавить эффект…"))
        b.clicked.connect(self.add_fx)
        b2 = QPushButton(tr("Убрать"))
        b2.clicked.connect(self.remove_fx)
        r.addWidget(b)
        r.addWidget(b2)
        form.addLayout(r)

        form.addWidget(self._h(tr("Название игры")))
        self.ed_title = QLineEdit()
        self.ed_title.setPlaceholderText(tr("Можно оставить пустым"))
        self.sp_title = QSpinBox()
        self.sp_title.setRange(16, 300)
        self.sp_title.setSuffix(" px")
        self.col_title = ColorButton("#ffffff")
        form.addWidget(self.ed_title)
        r = QHBoxLayout()
        r.addWidget(self.sp_title)
        r.addWidget(self.col_title)
        form.addLayout(r)

        form.addWidget(self._h(tr("Кнопки меню")))
        self.lst_btn = QListWidget()
        self.lst_btn.setMaximumHeight(150)
        self.lst_btn.currentRowChanged.connect(self.on_list_select)
        form.addWidget(self.lst_btn)
        r = QHBoxLayout()
        b = QPushButton(tr("Добавить кнопку"))
        b.clicked.connect(self.add_button)
        b2 = QPushButton(tr("Удалить"))
        b2.clicked.connect(self.delete_button)
        r.addWidget(b)
        r.addWidget(b2)
        form.addLayout(r)
        self.ed_label = QLineEdit()
        self.cb_action = QComboBox()
        for k, name in ACTION_NAMES.items():
            self.cb_action.addItem(tr(name), k)
        self.sp_size = QSpinBox()
        self.sp_size.setRange(12, 200)
        self.sp_size.setSuffix(" px")
        form.addWidget(QLabel(tr("Надпись кнопки")))
        form.addWidget(self.ed_label)
        form.addWidget(QLabel(tr("Что делает")))
        form.addWidget(self.cb_action)
        form.addWidget(QLabel(tr("Размер текста")))
        form.addWidget(self.sp_size)
        form.addWidget(QLabel(tr("Цвет кнопок / при наведении")))
        r = QHBoxLayout()
        self.col_btn = ColorButton("#ffffff")
        self.col_hover = ColorButton("#ff5a5f")
        r.addWidget(self.col_btn)
        r.addWidget(self.col_hover)
        form.addLayout(r)
        b = QPushButton(tr("Вернуть расположение по умолчанию"))
        b.clicked.connect(self.reset_layout)
        form.addWidget(b)
        form.addStretch(1)

        self.cb_bg.currentIndexChanged.connect(self.on_bg)
        self.cb_music.currentIndexChanged.connect(self.on_music)
        self.ed_title.textChanged.connect(self.on_title)
        self.sp_title.valueChanged.connect(self.on_title)
        self.col_title.changed.connect(lambda _c: self.on_title())
        self.ed_label.textChanged.connect(self.on_button_props)
        self.cb_action.currentIndexChanged.connect(self.on_button_props)
        self.sp_size.valueChanged.connect(self.on_button_props)
        self.col_btn.changed.connect(self.on_colors)
        self.col_hover.changed.connect(self.on_colors)

    # --------------------------------------------------------------- загрузка
    def reload(self) -> None:
        self._loading = True
        m = self.p.menu
        self.cb_bg.clear()
        tmp = asset_combo(self.p, "menu_bg", tr("— чёрный экран —"), m.bg)
        for i in range(tmp.count()):
            self.cb_bg.addItem(tmp.itemIcon(i), tmp.itemText(i), tmp.itemData(i))
        self.cb_bg.setCurrentIndex(max(0, self.cb_bg.findData(m.bg)))
        self.cb_music.clear()
        self.cb_music.addItem(tr("— без музыки —"), "")
        for a in self.p.assets["music"]:
            self.cb_music.addItem(a.name, a.id)
        self.cb_music.setCurrentIndex(max(0, self.cb_music.findData(m.music)))
        self.ed_title.setText(m.title)
        self.sp_title.setValue(int(m.title_size))
        self.col_title.set_color(m.title_color)
        self.col_btn.set_color(m.button_color)
        self.col_hover.set_color(m.hover_color)
        self.refresh_lists()
        self._loading = False
        self.rebuild()

    def refresh_lists(self, keep: str = "") -> None:
        m = self.p.menu
        self.lst_load.clear()
        for it in m.loading:
            a = self.p.find_asset(it.get("asset", ""))
            self.lst_load.addItem(f"{a.name if a else '?'} — {it.get('seconds', 2.0)} {tr('с')}")
        self.lst_fx.clear()
        for aid in m.effects:
            a = self.p.find_asset(aid)
            self.lst_fx.addItem(a.name if a else "?")
        self.lst_btn.blockSignals(True)
        self.lst_btn.clear()
        for b in m.buttons:
            it = QListWidgetItem(b.get("label", "") or "…")
            it.setData(Qt.ItemDataRole.UserRole, b["id"])
            self.lst_btn.addItem(it)
        if keep:
            for i in range(self.lst_btn.count()):
                if self.lst_btn.item(i).data(Qt.ItemDataRole.UserRole) == keep:
                    self.lst_btn.setCurrentRow(i)
        self.lst_btn.blockSignals(False)
        self.load_button_props()

    # ------------------------------------------------------------------ холст
    def rebuild(self, select: str = "") -> None:
        m = self.p.menu
        W, H = self.p.resolution
        self.scene.blockSignals(True)
        self.scene.clear()
        self.items = {}
        self.scene.setSceneRect(0, 0, W, H)
        bg = self.p.find_asset(m.bg) if m.bg else None
        placed = False
        if bg and bg.file:
            pm = QPixmap(str(self.p.abs(bg.file)))
            if not pm.isNull():
                it = self.scene.addPixmap(pm.scaled(W, H, Qt.AspectRatioMode.IgnoreAspectRatio,
                                                    Qt.TransformationMode.SmoothTransformation))
                it.setZValue(-10)
                placed = True
        if not placed:
            r = self.scene.addRect(0, 0, W, H, QPen(Qt.PenStyle.NoPen), QBrush(QColor("#000000")))
            r.setZValue(-10)
        for aid in m.effects:
            a = self.p.find_asset(aid)
            if not a:
                continue
            if a.kind == "solid":
                r = self.scene.addRect(0, 0, W, H, QPen(Qt.PenStyle.NoPen),
                                       QBrush(rgba_color(a.params.get("color", "#000000"), a.params.get("alpha", 40))))
                r.setZValue(-5)
            elif a.kind == "image" and a.file:
                pm = QPixmap(str(self.p.abs(a.file)))
                if not pm.isNull():
                    it = self.scene.addPixmap(pm.scaled(W, H, Qt.AspectRatioMode.IgnoreAspectRatio,
                                                        Qt.TransformationMode.SmoothTransformation))
                    it.setZValue(-5)
        if m.title.strip():
            ti = MenuItem("title", m.title, m.title_size, m.title_color, self.on_moved)
            ti.setPos(m.title_x, m.title_y)
            self.scene.addItem(ti)
            self.items["title"] = ti
        for b in m.buttons:
            bi = MenuItem(b["id"], b.get("label", ""), b.get("size", 48), m.button_color, self.on_moved)
            bi.setPos(b.get("x", 0), b.get("y", 0))
            self.scene.addItem(bi)
            self.items[b["id"]] = bi
        if select in self.items:
            self.items[select].setSelected(True)
        self.scene.blockSignals(False)
        self.view._fit()

    def on_moved(self, item: MenuItem) -> None:
        W, H = self.p.resolution
        x = int(max(0, min(W - 40, item.pos().x())))
        y = int(max(0, min(H - 40, item.pos().y())))
        item.setPos(x, y)
        m = self.p.menu
        if item.key == "title":
            m.title_x, m.title_y = x, y
        else:
            for b in m.buttons:
                if b["id"] == item.key:
                    b["x"], b["y"] = x, y
        self.ws.mark_dirty()

    def on_scene_select(self) -> None:
        sel = self.scene.selectedItems()
        if self._sync or not sel:
            return
        key = getattr(sel[0], "key", "")
        self._sync = True
        self.lst_btn.blockSignals(True)
        self.lst_btn.setCurrentRow(-1)
        for i in range(self.lst_btn.count()):
            if self.lst_btn.item(i).data(Qt.ItemDataRole.UserRole) == key:
                self.lst_btn.setCurrentRow(i)
        self.lst_btn.blockSignals(False)
        self._sync = False
        self.load_button_props()

    def on_list_select(self, row: int) -> None:
        if self._sync:
            return
        it = self.lst_btn.item(row)
        key = it.data(Qt.ItemDataRole.UserRole) if it else ""
        self._sync = True
        self.scene.blockSignals(True)
        self.scene.clearSelection()
        if key in self.items:
            self.items[key].setSelected(True)
        self.scene.blockSignals(False)
        self._sync = False
        self.load_button_props()

    # ---------------------------------------------------------- свойства кнопки
    def current_button(self):
        it = self.lst_btn.currentItem()
        if not it:
            return None
        key = it.data(Qt.ItemDataRole.UserRole)
        return next((b for b in self.p.menu.buttons if b["id"] == key), None)

    def load_button_props(self) -> None:
        b = self.current_button()
        self._loading = True
        on = b is not None
        for w in (self.ed_label, self.cb_action, self.sp_size):
            w.setEnabled(on)
        if b:
            self.ed_label.setText(b.get("label", ""))
            self.cb_action.setCurrentIndex(max(0, self.cb_action.findData(b.get("action", "start"))))
            self.sp_size.setValue(int(b.get("size", 48)))
        else:
            self.ed_label.setText("")
        self._loading = False

    def on_button_props(self) -> None:
        if self._loading:
            return
        b = self.current_button()
        if not b:
            return
        b["label"] = self.ed_label.text()
        b["action"] = self.cb_action.currentData()
        b["size"] = self.sp_size.value()
        self.ws.mark_dirty()
        self.refresh_lists(keep=b["id"])
        self.rebuild(select=b["id"])

    def on_colors(self, _c="") -> None:
        if self._loading:
            return
        m = self.p.menu
        m.button_color = self.col_btn.color()
        m.hover_color = self.col_hover.color()
        self.ws.mark_dirty()
        self.rebuild()

    def on_title(self) -> None:
        if self._loading:
            return
        m = self.p.menu
        m.title = self.ed_title.text()
        m.title_size = self.sp_title.value()
        m.title_color = self.col_title.color()
        self.ws.mark_dirty()
        self.rebuild(select="title")

    def on_bg(self) -> None:
        if self._loading:
            return
        self.p.menu.bg = self.cb_bg.currentData() or ""
        self.ws.mark_dirty()
        self.rebuild()

    def on_music(self) -> None:
        if self._loading:
            return
        self.p.menu.music = self.cb_music.currentData() or ""
        self.ws.mark_dirty()

    # ------------------------------------------------------------------ списки
    def add_loading(self) -> None:
        if not self.p.assets["loading"]:
            QMessageBox.information(self, tr("Загрузочные экраны"), tr(
                "Сначала добавьте загрузочные экраны в библиотеке (вкладка «Библиотека»)."))
            return
        items = [(a.name, a.id) for a in self.p.assets["loading"]]
        dlg = PickDialog(tr("Загрузочный экран"), tr("Картинка"), items, self,
                         spin=(tr("Сколько секунд показывать"), 0.5, 30.0, 2.5))
        if dlg.run():
            self.p.menu.loading.append({"asset": dlg.value(), "seconds": dlg.spin_value()})
            self.ws.mark_dirty()
            self.refresh_lists()

    def remove_loading(self) -> None:
        r = self.lst_load.currentRow()
        if 0 <= r < len(self.p.menu.loading):
            self.p.menu.loading.pop(r)
            self.ws.mark_dirty()
            self.refresh_lists()

    def add_fx(self) -> None:
        fx = [a for a in self.p.assets["effects"] if a.kind in ("image", "solid")]
        if not fx:
            QMessageBox.information(self, tr("Эффекты"), tr(
                "Сначала добавьте эффекты в библиотеке (кнопка «Встроенные эффекты»)."))
            return
        dlg = PickDialog(tr("Эффект поверх меню"), tr("Эффект"), [(a.name, a.id) for a in fx], self)
        if dlg.run() and dlg.value() not in self.p.menu.effects:
            self.p.menu.effects.append(dlg.value())
            self.ws.mark_dirty()
            self.refresh_lists()
            self.rebuild()

    def remove_fx(self) -> None:
        r = self.lst_fx.currentRow()
        if 0 <= r < len(self.p.menu.effects):
            self.p.menu.effects.pop(r)
            self.ws.mark_dirty()
            self.refresh_lists()
            self.rebuild()

    def add_button(self) -> None:
        m = self.p.menu
        n = len(m.buttons)
        b = {"id": "btn" + short_id(), "label": tr("Новая кнопка"), "action": "start",
             "x": 160, "y": min(self.p.resolution[1] - 100, 430 + n * 110), "size": 56}
        m.buttons.append(b)
        self.ws.mark_dirty()
        self.refresh_lists(keep=b["id"])
        self.load_button_props()
        self.rebuild(select=b["id"])

    def delete_button(self) -> None:
        b = self.current_button()
        if not b:
            return
        self.p.menu.buttons = [x for x in self.p.menu.buttons if x["id"] != b["id"]]
        self.ws.mark_dirty()
        self.refresh_lists()
        self.rebuild()

    def reset_layout(self) -> None:
        if QMessageBox.question(self, tr("Меню"), tr("Вернуть стандартные кнопки и их расположение?"),
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) \
                == QMessageBox.StandardButton.Yes:
            self.p.menu.buttons = default_menu_buttons()
            self.ws.mark_dirty()
            self.refresh_lists()
            self.rebuild()
