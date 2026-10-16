"""Редактор сценария: диалоги, фразы, фоны, музыка, персонажи, эффекты, варианты ответа."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                               QStackedWidget, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

from ..core.i18n import tr
from ..core.model import SceneState, Step
from .dialogs import BaseDialog, BgDialog, CharPicker, ChoiceDialog, NewDialogDialog, PickDialog
from .preview import ScenePreview
from .spellwidgets import SpellStrip, SpellTextEdit
from .theme import icon_for

TERMINAL = ("choice", "ending")


class EditorPage(QWidget):
    def __init__(self, ws, parent=None) -> None:
        super().__init__(parent)
        self.ws = ws
        self.block_id = ""
        self._items: dict = {}
        self._loading = False
        self._build()
        self.reload()

    # ------------------------------------------------------------------ доступ
    @property
    def p(self):
        return self.ws.project

    def cur_block(self):
        return self.p.block(self.block_id) if self.block_id else None

    def step_at(self, row: int):
        b = self.cur_block()
        if b and 0 <= row < len(b.steps):
            return b.steps[row]
        return None

    def cur_step(self):
        return self.step_at(self.timeline.currentRow())

    def asset_name(self, aid: str) -> str:
        a = self.p.find_asset(aid)
        return a.name if a else tr("(удалено)")

    def char_name(self, cid: str) -> str:
        c = self.p.get_char(cid)
        return c.name if c else tr("(удалён)")

    # ------------------------------------------------------------------- вёрстка
    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # левая колонка
        left = QWidget()
        left.setFixedWidth(250)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        h = QLabel(tr("Диалоги и ветки"))
        h.setProperty("role", "h2")
        ll.addWidget(h)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.currentItemChanged.connect(self.on_tree_changed)
        ll.addWidget(self.tree, 1)
        b_new = QPushButton(tr("Новый диалог"))
        b_new.setProperty("accent", True)
        b_new.clicked.connect(self.new_dialog)
        ll.addWidget(b_new)
        r1 = QHBoxLayout()
        for text, fn in ((tr("Переименовать"), self.rename_block), (tr("Удалить"), self.delete_block)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            r1.addWidget(b)
        ll.addLayout(r1)
        r2 = QHBoxLayout()
        for text, fn in ((tr("Выше"), lambda: self.move_block(-1)), (tr("Ниже"), lambda: self.move_block(1))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            r2.addWidget(b)
        ll.addLayout(r2)
        r3 = QHBoxLayout()
        for text, fn in ((tr("Отменить"), self.ws.undo), (tr("Повторить"), self.ws.redo)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            r3.addWidget(b)
        ll.addLayout(r3)
        root.addWidget(left)

        # центр
        center = QVBoxLayout()
        center.setSpacing(8)
        self.preview = ScenePreview()
        self.preview.set_project(self.p)
        center.addWidget(self.preview, 5)

        self.bar = QFrame()
        self.bar.setProperty("card", True)
        bl = QHBoxLayout(self.bar)
        bl.setContentsMargins(10, 6, 10, 6)
        self.lbl_branch = QLabel()
        bl.addWidget(self.lbl_branch, 1)
        self.btn_shared = QPushButton(tr("Конечный для всех"))
        self.btn_shared.setCheckable(True)
        self.btn_shared.setToolTip(tr("Отметьте ветку, в которую в итоге придут и остальные ответы"))
        self.btn_shared.toggled.connect(self.toggle_shared)
        self.btn_link = QPushButton(tr("Связать с конечным…"))
        self.btn_link.clicked.connect(self.link_to_shared)
        self.btn_link_all = QPushButton(tr("Связать остальные ответы сюда"))
        self.btn_link_all.clicked.connect(self.link_all_here)
        self.btn_unlink = QPushButton(tr("Разорвать связь"))
        self.btn_unlink.clicked.connect(self.unlink)
        for w in (self.btn_shared, self.btn_link, self.btn_link_all, self.btn_unlink):
            bl.addWidget(w)
        center.addWidget(self.bar)

        grid = QGridLayout()
        grid.setSpacing(6)
        tools = [(tr("+ Фраза"), self.add_say, True), (tr("Фон"), self.add_bg, False),
                 (tr("Музыка"), self.add_music, False), (tr("Персонаж"), self.add_show, False),
                 (tr("Убрать персонажа"), self.add_hide, False), (tr("Эффект"), self.add_fx, False),
                 (tr("Убрать эффект"), self.add_fx_off, False), (tr("Варианты ответа"), self.add_choice, False),
                 (tr("Конец игры"), self.add_ending, False)]
        for i, (text, fn, accent) in enumerate(tools):
            b = QPushButton(text)
            if accent:
                b.setProperty("accent", True)
            b.clicked.connect(fn)
            grid.addWidget(b, i // 5, i % 5)
        center.addLayout(grid)

        self.timeline = QListWidget()
        self.timeline.currentRowChanged.connect(self.on_row)
        center.addWidget(self.timeline, 4)
        tl = QHBoxLayout()
        for text, fn in ((tr("Шаг выше"), lambda: self.move_step(-1)), (tr("Шаг ниже"), lambda: self.move_step(1))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            tl.addWidget(b)
        b_del = QPushButton(tr("Удалить шаг"))
        b_del.setProperty("danger", True)
        b_del.clicked.connect(self.delete_step)
        tl.addWidget(b_del)
        center.addLayout(tl)
        sc = QShortcut(QKeySequence(QKeySequence.StandardKey.Delete), self.timeline)
        sc.setContext(Qt.ShortcutContext.WidgetShortcut)
        sc.activated.connect(self.delete_step)
        root.addLayout(center, 1)

        # правая колонка
        self.stack = QStackedWidget()
        self.stack.setFixedWidth(380)
        self.stack.addWidget(self._page_empty())
        self.stack.addWidget(self._page_say())
        self.stack.addWidget(self._page_info())
        self.stack.addWidget(self._page_choice())
        root.addWidget(self.stack)

        self.spell_timer = QTimer(self)
        self.spell_timer.setSingleShot(True)
        self.spell_timer.setInterval(300)
        self.spell_timer.timeout.connect(self.update_strip)

    def _page_empty(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lab = QLabel(tr("Создайте диалог кнопкой «Новый диалог» слева или выберите шаг в списке."))
        lab.setWordWrap(True)
        lab.setProperty("role", "sub")
        lay.addWidget(lab)
        lay.addStretch(1)
        return w

    def _page_say(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        h = QLabel(tr("Кто говорит"))
        h.setProperty("role", "h2")
        lay.addWidget(h)
        self.chip_host = QWidget()
        self.chip_lay = QGridLayout(self.chip_host)
        self.chip_lay.setContentsMargins(0, 0, 0, 0)
        self.chip_lay.setSpacing(6)
        self.chip_group = QButtonGroup(self)
        self.chip_group.setExclusive(True)
        lay.addWidget(self.chip_host)
        h2 = QLabel(tr("Текст"))
        h2.setProperty("role", "h2")
        lay.addWidget(h2)
        self.text = SpellTextEdit(self.ws.spell)
        self.text.setPlaceholderText(tr("Напишите реплику…"))
        self.text.textChanged.connect(self.on_text)
        lay.addWidget(self.text, 1)
        self.strip = SpellStrip()
        self.strip.replace.connect(self.text.replace_range)
        self.strip.keep.connect(self.on_keep)
        lay.addWidget(self.strip)
        self.lbl_spell = QLabel()
        self.lbl_spell.setWordWrap(True)
        self.lbl_spell.setProperty("role", "sub")
        lay.addWidget(self.lbl_spell)
        nxt = QPushButton(tr("Далее  (Ctrl+Enter)"))
        nxt.setProperty("accent", True)
        nxt.setProperty("big", True)
        nxt.clicked.connect(self.next_phrase)
        lay.addWidget(nxt)
        for key in ("Ctrl+Return", "Ctrl+Enter"):
            s = QShortcut(QKeySequence(key), self.text)
            s.setContext(Qt.ShortcutContext.WidgetShortcut)
            s.activated.connect(self.next_phrase)
        return w

    def _page_info(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self.lbl_info_h = QLabel()
        self.lbl_info_h.setProperty("role", "h2")
        lay.addWidget(self.lbl_info_h)
        self.lbl_info = QLabel()
        self.lbl_info.setWordWrap(True)
        lay.addWidget(self.lbl_info)
        self.btn_edit = QPushButton(tr("Изменить…"))
        self.btn_edit.clicked.connect(self.edit_step)
        lay.addWidget(self.btn_edit)
        lay.addStretch(1)
        return w

    def _page_choice(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        h = QLabel(tr("Варианты ответа"))
        h.setProperty("role", "h2")
        lay.addWidget(h)
        self.choice_host = QWidget()
        self.choice_lay = QVBoxLayout(self.choice_host)
        self.choice_lay.setContentsMargins(0, 0, 0, 0)
        self.choice_lay.setSpacing(8)
        lay.addWidget(self.choice_host)
        self.btn_add_opt = QPushButton(tr("Добавить вариант"))
        self.btn_add_opt.clicked.connect(self.add_option)
        lay.addWidget(self.btn_add_opt)
        hint = QLabel(tr("«Открыть» переключает редактор на ветку этого ответа. Остальные ветки ждут в списке слева."))
        hint.setWordWrap(True)
        hint.setProperty("role", "sub")
        lay.addWidget(hint)
        lay.addStretch(1)
        return w

    # ------------------------------------------------------------- дерево блоков
    def block_label(self, b) -> str:
        label = b.title or b.id
        if not b.steps:
            label += "  · " + tr("пусто")
        if b.shared_end:
            label += "  · " + tr("конечный")
        if b.link_to:
            t = self.p.block(b.link_to)
            label += "  → " + (t.title if t else "?")
        return label

    def build_tree(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        self._items = {}

        def add(parent_item, b) -> None:
            it = QTreeWidgetItem([self.block_label(b)])
            it.setData(0, Qt.ItemDataRole.UserRole, b.id)
            if parent_item is None:
                self.tree.addTopLevelItem(it)
            else:
                parent_item.addChild(it)
            self._items[b.id] = it
            for k in self.p.children_of(b.id):
                add(it, k)

        for t in self.p.top_blocks():
            add(None, t)
        self.tree.expandAll()
        if self.block_id in self._items:
            self.tree.setCurrentItem(self._items[self.block_id])
        self.tree.blockSignals(False)

    def refresh_tree_labels(self) -> None:
        for bid, it in self._items.items():
            b = self.p.block(bid)
            if b:
                it.setText(0, self.block_label(b))

    def on_tree_changed(self, cur, prev) -> None:
        if cur is not None:
            self.select_block(cur.data(0, Qt.ItemDataRole.UserRole))

    def select_block(self, bid: str) -> None:
        self.block_id = bid if self.p.block(bid) else ""
        if self.block_id in self._items:
            self.tree.blockSignals(True)
            self.tree.setCurrentItem(self._items[self.block_id])
            self.tree.blockSignals(False)
        self.fill_timeline()
        self.update_bar()

    def reload(self) -> None:
        """Полная перерисовка (после отмены, открытия проекта, возврата из библиотеки)."""
        keep = self.block_id if self.p.block(self.block_id) else ""
        if not keep and self.p.top_blocks():
            keep = self.p.top_blocks()[0].id
        self.block_id = keep
        self.preview.set_project(self.p)
        self.text.set_ctx(self.ws.spell)
        self.build_tree()
        self.select_block(keep)

    def refresh_soft(self) -> None:
        """Обновить подписи и превью после изменений в библиотеке (без потери места в диалоге)."""
        row = self.timeline.currentRow()
        self.preview.refresh()
        self.text.set_ctx(self.ws.spell)
        self.refresh_tree_labels()
        self.fill_timeline(select=row if row >= 0 else None)
        self.update_bar()

    # --------------------------------------------------------------- таймлайн
    def describe(self, s):
        d, k = s.data, s.kind
        if k == "say":
            who = self.char_name(d["who"]) if d.get("who") else tr("Мысли")
            t = d.get("text", "").replace("\n", " ").strip() or "…"
            return who + ":", t, ""
        if k == "bg":
            return tr("Фон"), self.asset_name(d.get("asset", "")), "#0a84ff"
        if k == "music":
            return tr("Музыка"), self.asset_name(d.get("asset", "")), "#bf5af2"
        if k == "music_stop":
            return tr("Музыка"), tr("остановить"), "#bf5af2"
        if k == "show":
            return tr("Персонаж"), f"{self.char_name(d.get('char', ''))}: {d.get('emotion', '')}", "#ff9f0a"
        if k == "hide":
            return tr("Убрать"), self.char_name(d.get("char", "")), "#ff9f0a"
        if k == "fx_on":
            return tr("Эффект"), self.asset_name(d.get("asset", "")), "#ff453a"
        if k == "fx_off":
            return tr("Эффект выкл."), self.asset_name(d.get("asset", "")), "#ff453a"
        if k == "fx_once":
            return tr("Эффект"), self.asset_name(d.get("asset", "")), "#ff453a"
        if k == "choice":
            texts = " / ".join(o.get("text", "") or "…" for o in d.get("options", []))
            return tr("Варианты"), texts, "#30d158"
        if k == "ending":
            return tr("Конец игры"), d.get("title", ""), "#ff375f"
        return k, "", ""

    def make_item(self, s) -> QListWidgetItem:
        label, text, color = self.describe(s)
        it = QListWidgetItem(f"{label}   {text}")
        if color:
            it.setForeground(QBrush(QColor(color)))
        return it

    def fill_timeline(self, select=None) -> None:
        b = self.cur_block()
        self.timeline.blockSignals(True)
        self.timeline.clear()
        if b:
            for s in b.steps:
                self.timeline.addItem(self.make_item(s))
        n = self.timeline.count()
        row = -1
        if n:
            row = n - 1 if select is None else max(0, min(n - 1, select))
            self.timeline.setCurrentRow(row)
        self.timeline.blockSignals(False)
        self.on_row(row)

    def update_row(self, row: int) -> None:
        s = self.step_at(row)
        it = self.timeline.item(row)
        if s and it:
            label, text, _c = self.describe(s)
            it.setText(f"{label}   {text}")

    def on_row(self, row: int) -> None:
        s = self.step_at(row)
        self._loading = True
        if s is None:
            self.stack.setCurrentIndex(0)
        elif s.kind == "say":
            self.stack.setCurrentIndex(1)
            self.load_say(s)
        elif s.kind == "choice":
            self.stack.setCurrentIndex(3)
            self.load_choice(s)
        else:
            self.stack.setCurrentIndex(2)
            self.load_info(s)
        self._loading = False
        self.update_preview()

    def update_preview(self) -> None:
        b = self.cur_block()
        if not b:
            self.preview.set_scene(SceneState(), "", "")
            return
        row = self.timeline.currentRow()
        st = self.p.state_at(b.id, row + 1 if row >= 0 else 0)
        who, text = "", ""
        if row >= 0:
            for s in reversed(b.steps[:row + 1]):
                if s.kind == "say":
                    who, text = s.data.get("who", ""), s.data.get("text", "")
                    break
        self.preview.set_scene(st, who, text)

    # ---------------------------------------------------------------- фразы
    def load_say(self, s) -> None:
        self.text.setPlainText(s.data.get("text", ""))
        self.build_chips(s.data.get("who", ""))
        self.spell_timer.start()

    def build_chips(self, selected: str) -> None:
        for btn in list(self.chip_group.buttons()):
            self.chip_group.removeButton(btn)
        while self.chip_lay.count():
            item = self.chip_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        b = self.cur_block()
        st = self.p.state_at(b.id, max(0, self.timeline.currentRow())) if b else SceneState()
        items = [("", tr("Мысли"), True)]
        items += [(c.id, c.name, True) for c in self.p.characters if c.id in st.chars]
        items += [(c.id, c.name, False) for c in self.p.characters if c.id not in st.chars]
        for i, (cid, name, present) in enumerate(items):
            btn = QToolButton()
            btn.setText(name)
            btn.setCheckable(True)
            btn.setProperty("dim", not present)
            if not present and cid:
                btn.setToolTip(tr("Сейчас этого персонажа нет на сцене"))
            btn.setChecked(cid == selected)
            self.chip_group.addButton(btn)
            btn.clicked.connect(lambda checked=False, cid=cid: self.set_speaker(cid))
            self.chip_lay.addWidget(btn, i // 3, i % 3)

    def set_speaker(self, cid: str) -> None:
        s = self.cur_step()
        if self._loading or not s or s.kind != "say":
            return
        s.data["who"] = cid
        self.update_row(self.timeline.currentRow())
        self.update_preview()
        self.ws.mark_dirty()

    def on_text(self) -> None:
        if self._loading:
            return
        s = self.cur_step()
        if not s or s.kind != "say":
            return
        s.data["text"] = self.text.toPlainText()
        self.update_row(self.timeline.currentRow())
        self.update_preview()
        self.ws.mark_dirty()
        self.spell_timer.start()

    def update_strip(self) -> None:
        ctx = self.ws.spell
        errs = [(s, e, w, ctx.suggest(w)) for s, e, w in ctx.errors(self.text.toPlainText())[:3]]
        self.strip.set_errors(errs)
        self.lbl_spell.setText(ctx.status)
        self.lbl_spell.setVisible(bool(ctx.status))

    def on_keep(self, word: str) -> None:
        self.ws.spell.ignore_word(word)
        self.text.hl.rehighlight()
        self.update_strip()

    def last_speaker(self, b) -> str:
        for s in reversed(b.steps):
            if s.kind == "say":
                return s.data.get("who", "")
        return ""

    def next_phrase(self) -> None:
        b = self.cur_block()
        if not b:
            return
        cur = self.cur_step()
        who = cur.data.get("who", "") if cur and cur.kind == "say" else self.last_speaker(b)
        self.insert_step("say", {"who": who, "text": ""})
        self.text.setFocus()

    # ------------------------------------------------------------- вставка шагов
    def insert_index(self, b) -> int:
        row = self.timeline.currentRow()
        idx = row + 1 if row >= 0 else len(b.steps)
        for i, s in enumerate(b.steps):
            if s.kind in TERMINAL:
                idx = min(idx, i)
                break
        return idx

    def insert_step(self, kind: str, data: dict):
        b = self.cur_block()
        if not b:
            QMessageBox.information(self, tr("Нет диалога"), tr("Сначала создайте диалог кнопкой «Новый диалог»."))
            return None
        self.ws.push_undo()
        idx = self.insert_index(b)
        s = Step.new(kind, data)
        b.steps.insert(idx, s)
        self.after_change(select=idx)
        return s

    def after_change(self, select=None, tree: bool = False) -> None:
        self.ws.mark_dirty()
        if tree:
            self.build_tree()
        self.fill_timeline(select)
        self.refresh_tree_labels()
        self.update_bar()

    def need(self, cat: str, text: str) -> bool:
        if self.p.assets[cat]:
            return True
        box = QMessageBox(self)
        box.setWindowTitle(tr("В библиотеке пусто"))
        box.setText(text)
        go = box.addButton(tr("Открыть библиотеку"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Закрыть"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is go:
            self.ws.show_page("library")
        return False

    def need_chars(self) -> bool:
        if any(c.emotions for c in self.p.characters):
            return True
        box = QMessageBox(self)
        box.setWindowTitle(tr("Нет персонажей"))
        box.setText(tr("Сначала добавьте персонажа с картинкой в библиотеке."))
        go = box.addButton(tr("Открыть библиотеку"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("Закрыть"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is go:
            self.ws.show_page("library")
        return False

    def state_after_current(self) -> SceneState:
        b = self.cur_block()
        if not b:
            return SceneState()
        return self.p.state_at(b.id, self.timeline.currentRow() + 1 if self.timeline.currentRow() >= 0 else len(b.steps))

    def add_say(self) -> None:
        b = self.cur_block()
        if b:
            self.insert_step("say", {"who": self.last_speaker(b), "text": ""})
            self.text.setFocus()
        else:
            self.insert_step("say", {})

    def add_bg(self) -> None:
        if not self.need("backgrounds", tr("В библиотеке нет фонов. Добавьте их на вкладке «Библиотека».")):
            return
        dlg = BgDialog(self.p, self.state_after_current().bg, self)
        if dlg.run():
            v = dlg.values()
            if v["asset"]:
                self.insert_step("bg", v)

    def add_music(self) -> None:
        if not self.need("music", tr("В библиотеке нет музыки. Добавьте её на вкладке «Библиотека».")):
            return
        items = [(tr("— остановить музыку —"), "")] + [(a.name, a.id) for a in self.p.assets["music"]]
        dlg = PickDialog(tr("Музыка"), tr("Трек"), items, self, self.state_after_current().music)
        if dlg.run():
            v = dlg.value()
            if v:
                self.insert_step("music", {"asset": v})
            else:
                self.insert_step("music_stop", {})

    def add_show(self) -> None:
        if not self.need_chars():
            return
        st = self.state_after_current()
        cid, emo, pos = "", "", "center"
        if st.chars:
            cid = list(st.chars.keys())[-1]
            emo, pos = st.chars[cid]
        dlg = BaseDialog(tr("Добавить персонажа / сменить эмоцию"), self)
        picker = CharPicker(self.p, False, cid, emo, pos)
        dlg.add_widget(picker)
        if dlg.run():
            v = picker.value()
            if v["char"] and v["emotion"]:
                v["trans"] = "dissolve"
                self.insert_step("show", v)

    def add_hide(self) -> None:
        st = self.state_after_current()
        items = [(self.char_name(cid), cid) for cid in st.chars]
        if not items:
            QMessageBox.information(self, tr("Убрать персонажа"), tr("В этом месте на сцене нет персонажей."))
            return
        dlg = PickDialog(tr("Убрать персонажа"), tr("Кто уходит со сцены"), items, self)
        if dlg.run():
            self.insert_step("hide", {"char": dlg.value(), "trans": "dissolve"})

    def add_fx(self) -> None:
        if not self.need("effects", tr("В библиотеке нет эффектов. Нажмите «Встроенные эффекты» на вкладке «Библиотека».")):
            return
        items = []
        for a in self.p.assets["effects"]:
            icon = icon_for(str(self.p.abs(a.file)), 64, 36) if a.file and a.kind == "image" else None
            items.append((a.name + ("  (" + tr("разовый") + ")" if a.kind in ("shake", "flash") else ""), a.id, icon))
        dlg = PickDialog(tr("Эффект"), tr("Что включить"), items, self)
        if dlg.run():
            a = self.p.find_asset(dlg.value())
            if a:
                self.insert_step("fx_once" if a.kind in ("shake", "flash") else "fx_on",
                                 {"asset": a.id, "trans": "dissolve"})

    def add_fx_off(self) -> None:
        st = self.state_after_current()
        items = [(self.asset_name(a), a) for a in st.fx]
        if not items:
            QMessageBox.information(self, tr("Убрать эффект"), tr("В этом месте нет включённых эффектов."))
            return
        dlg = PickDialog(tr("Убрать эффект"), tr("Какой выключить"), items, self)
        if dlg.run():
            self.insert_step("fx_off", {"asset": dlg.value(), "trans": "dissolve"})

    def add_ending(self) -> None:
        b = self.cur_block()
        if not b:
            return self.insert_step("ending", {})
        if any(s.kind in TERMINAL for s in b.steps):
            QMessageBox.information(self, tr("Конец игры"), tr("В этом диалоге уже есть варианты ответа или конец."))
            return
        title, ok = QInputDialog.getText(self, tr("Конец игры"), tr("Название концовки (можно оставить пустым):"),
                                         QLineEdit.EchoMode.Normal, "")
        if ok:
            self.ws.push_undo()
            b.steps.append(Step.new("ending", {"title": title.strip()}))
            self.after_change(select=len(b.steps) - 1)

    # ------------------------------------------------------- правка / перемещение
    def load_info(self, s) -> None:
        label, text, _c = self.describe(s)
        self.lbl_info_h.setText(label)
        self.lbl_info.setText(text or "—")
        self.btn_edit.setVisible(s.kind != "music_stop")

    def edit_step(self) -> None:
        s, b = self.cur_step(), self.cur_block()
        if not s or not b:
            return
        d = s.data
        new = None
        if s.kind == "bg":
            dlg = BgDialog(self.p, d.get("asset", ""), self)
            dlg.chk.setChecked(bool(d.get("clear")))
            if dlg.run():
                new = dlg.values()
        elif s.kind == "music":
            items = [(a.name, a.id) for a in self.p.assets["music"]]
            dlg = PickDialog(tr("Музыка"), tr("Трек"), items, self, d.get("asset"))
            if dlg.run():
                new = {"asset": dlg.value()}
        elif s.kind == "show":
            dlg = BaseDialog(tr("Добавить персонажа / сменить эмоцию"), self)
            picker = CharPicker(self.p, False, d.get("char", ""), d.get("emotion", ""), d.get("pos", "center"))
            dlg.add_widget(picker)
            if dlg.run():
                new = picker.value()
        elif s.kind == "hide":
            items = [(c.name, c.id) for c in self.p.characters]
            dlg = PickDialog(tr("Убрать персонажа"), tr("Кто уходит со сцены"), items, self, d.get("char"))
            if dlg.run():
                new = {"char": dlg.value()}
        elif s.kind in ("fx_on", "fx_off", "fx_once"):
            items = [(a.name, a.id) for a in self.p.assets["effects"]]
            dlg = PickDialog(tr("Эффект"), tr("Эффект"), items, self, d.get("asset"))
            if dlg.run():
                new = {"asset": dlg.value()}
        elif s.kind == "ending":
            title, ok = QInputDialog.getText(self, tr("Конец игры"), tr("Название концовки:"),
                                             QLineEdit.EchoMode.Normal, d.get("title", ""))
            if ok:
                new = {"title": title.strip()}
        if new is not None:
            self.ws.push_undo()
            s.data.update(new)
            self.update_row(self.timeline.currentRow())
            self.load_info(s)
            self.update_preview()
            self.ws.mark_dirty()

    def move_step(self, delta: int) -> None:
        b, row = self.cur_block(), self.timeline.currentRow()
        if not b or row < 0:
            return
        j = row + delta
        if j < 0 or j >= len(b.steps):
            return
        if b.steps[row].kind in TERMINAL or b.steps[j].kind in TERMINAL:
            return
        self.ws.push_undo()
        b.steps[row], b.steps[j] = b.steps[j], b.steps[row]
        self.after_change(select=j)

    def delete_step(self) -> None:
        b, row = self.cur_block(), self.timeline.currentRow()
        s = self.step_at(row)
        if not b or not s:
            return
        tree = False
        if s.kind == "choice":
            kids = [o.get("block") for o in s.data.get("options", [])]
            if QMessageBox.question(self, tr("Удалить варианты ответа"),
                                    tr("Вместе с вариантами будут удалены все их ветки ({}). Продолжить?").format(len(kids)),
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) \
                    != QMessageBox.StandardButton.Yes:
                return
            self.ws.push_undo()
            for k in kids:
                self.p.remove_block_tree(k)
            tree = True
        else:
            self.ws.push_undo()
        b.steps.pop(row)
        self.after_change(select=max(0, row - 1), tree=tree)

    # ------------------------------------------------------------- диалоги / ветки
    def new_dialog(self) -> None:
        dlg = NewDialogDialog(self.p, self)
        if not dlg.run():
            return
        v = dlg.values()
        self.ws.push_undo()
        b = self.p.add_block(tr("Диалог {}").format(len(self.p.top_blocks()) + 1))
        if v["bg"]:
            b.steps.append(Step.new("bg", {"asset": v["bg"], "clear": True, "trans": "fade"}))
        if v["music"]:
            b.steps.append(Step.new("music", {"asset": v["music"]}))
        if v["char"] and v["emotion"]:
            b.steps.append(Step.new("show", {"char": v["char"], "emotion": v["emotion"], "pos": v["pos"],
                                             "trans": "dissolve"}))
        b.steps.append(Step.new("say", {"who": v["char"] if v["char"] and v["emotion"] else "", "text": ""}))
        self.ws.mark_dirty()
        self.block_id = b.id
        self.build_tree()
        self.select_block(b.id)
        self.text.setFocus()

    def rename_block(self) -> None:
        b = self.cur_block()
        if not b:
            return
        name, ok = QInputDialog.getText(self, tr("Переименовать"), tr("Название:"), QLineEdit.EchoMode.Normal, b.title)
        if ok and name.strip():
            self.ws.push_undo()
            b.title = name.strip()
            self.refresh_tree_labels()
            self.ws.mark_dirty()

    def delete_block(self) -> None:
        b = self.cur_block()
        if not b:
            return
        if b.parent:
            QMessageBox.information(self, tr("Удалить"), tr(
                "Ветку нельзя удалить отдельно. Измените или удалите варианты ответа в родительском диалоге."))
            return
        n = len(self.p.descendants(b.id))
        text = tr("Удалить диалог «{}»?").format(b.title or b.id)
        if n:
            text += " " + tr("Вместе с ним удалятся его ветки ({}).").format(n)
        if QMessageBox.question(self, tr("Удалить"), text,
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) \
                != QMessageBox.StandardButton.Yes:
            return
        self.ws.push_undo()
        self.p.remove_block_tree(b.id)
        self.ws.mark_dirty()
        tops = self.p.top_blocks()
        self.block_id = tops[0].id if tops else ""
        self.build_tree()
        self.select_block(self.block_id)

    def move_block(self, delta: int) -> None:
        b = self.cur_block()
        if not b or b.parent:
            return
        tops = self.p.top_blocks()
        i = next((k for k, t in enumerate(tops) if t.id == b.id), -1)
        j = i + delta
        if i < 0 or j < 0 or j >= len(tops):
            return
        self.ws.push_undo()
        a, c = self.p.blocks.index(tops[i]), self.p.blocks.index(tops[j])
        self.p.blocks[a], self.p.blocks[c] = self.p.blocks[c], self.p.blocks[a]
        self.ws.mark_dirty()
        self.build_tree()

    # ----------------------------------------------------------- варианты ответа
    def branch_title(self, i: int, text: str) -> str:
        t = text.strip().replace("\n", " ")
        return tr("Ответ {}").format(i + 1) + (": " + (t[:24] + ("…" if len(t) > 24 else "")) if t else "")

    def add_choice(self) -> None:
        b = self.cur_block()
        if not b:
            QMessageBox.information(self, tr("Нет диалога"), tr("Сначала создайте диалог кнопкой «Новый диалог»."))
            return
        if any(s.kind in TERMINAL for s in b.steps):
            QMessageBox.information(self, tr("Варианты ответа"), tr("В этом диалоге уже есть варианты ответа или конец."))
            return
        dlg = ChoiceDialog(None, self)
        if not dlg.run():
            return
        texts = dlg.values()[:4]
        self.ws.push_undo()
        step = Step.new("choice", {"options": []})
        b.steps.append(step)
        opts = []
        for i, t in enumerate(texts):
            kid = self.p.add_block(self.branch_title(i, t), b.id, step.id)
            opts.append({"text": t, "block": kid.id})
        step.data["options"] = opts
        self.ws.mark_dirty()
        self.build_tree()
        self.fill_timeline(select=len(b.steps) - 1)
        self.select_block(opts[0]["block"])

    def load_choice(self, s) -> None:
        while self.choice_lay.count():
            item = self.choice_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        opts = s.data.get("options", [])
        for i, o in enumerate(opts):
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            e = QLineEdit(o.get("text", ""))
            e.setPlaceholderText(tr("Вариант {}").format(i + 1))
            e.textChanged.connect(lambda text, i=i: self.on_option_text(i, text))
            b_open = QPushButton(tr("Открыть"))
            b_open.clicked.connect(lambda checked=False, bid=o.get("block", ""): self.select_block(bid))
            b_del = QPushButton("×")
            b_del.setFixedWidth(34)
            b_del.clicked.connect(lambda checked=False, i=i: self.remove_option(i))
            h.addWidget(e, 1)
            h.addWidget(b_open)
            h.addWidget(b_del)
            self.choice_lay.addWidget(row)
        self.btn_add_opt.setVisible(len(opts) < 4)

    def on_option_text(self, i: int, text: str) -> None:
        if self._loading:
            return
        s = self.cur_step()
        if not s or s.kind != "choice" or i >= len(s.data["options"]):
            return
        o = s.data["options"][i]
        o["text"] = text
        kid = self.p.block(o.get("block", ""))
        if kid:
            kid.title = self.branch_title(i, text)
        self.update_row(self.timeline.currentRow())
        self.refresh_tree_labels()
        self.ws.mark_dirty()

    def add_option(self) -> None:
        s, b = self.cur_step(), self.cur_block()
        if not s or s.kind != "choice" or len(s.data["options"]) >= 4:
            return
        self.ws.push_undo()
        i = len(s.data["options"])
        kid = self.p.add_block(self.branch_title(i, ""), b.id, s.id)
        s.data["options"].append({"text": "", "block": kid.id})
        self.ws.mark_dirty()
        self.build_tree()
        self.fill_timeline(select=self.timeline.currentRow())

    def remove_option(self, i: int) -> None:
        s = self.cur_step()
        if not s or s.kind != "choice":
            return
        opts = s.data["options"]
        if len(opts) <= 2:
            QMessageBox.information(self, tr("Варианты ответа"),
                                    tr("Нужно минимум два варианта. Чтобы убрать выбор целиком, удалите шаг «Варианты»."))
            return
        kid = self.p.block(opts[i].get("block", ""))
        if kid and (kid.steps or self.p.descendants(kid.id)):
            if QMessageBox.question(self, tr("Удалить вариант"), tr("В ветке этого ответа уже есть текст. Удалить её?"),
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) \
                    != QMessageBox.StandardButton.Yes:
                return
        self.ws.push_undo()
        if kid:
            self.p.remove_block_tree(kid.id)
        opts.pop(i)
        for k, o in enumerate(opts):
            kb = self.p.block(o.get("block", ""))
            if kb:
                kb.title = self.branch_title(k, o.get("text", ""))
        self.ws.mark_dirty()
        self.build_tree()
        self.fill_timeline(select=self.timeline.currentRow())

    # ------------------------------------------------------ «конечный для всех»
    def update_bar(self) -> None:
        b = self.cur_block()
        if not b or not b.parent:
            self.bar.setVisible(False)
            return
        self.bar.setVisible(True)
        par = self.p.block(b.parent)
        text = tr("Ветка диалога «{}»").format(par.title if par else "?")
        if b.link_to:
            t = self.p.block(b.link_to)
            text += "  ·  " + tr("ведёт к «{}»").format(t.title if t else "?")
        self.lbl_branch.setText(text)
        self.btn_shared.blockSignals(True)
        self.btn_shared.setChecked(b.shared_end)
        self.btn_shared.blockSignals(False)
        self.btn_link_all.setVisible(b.shared_end)
        self.btn_link.setVisible(not b.shared_end)
        self.btn_unlink.setVisible(bool(b.link_to))

    def toggle_shared(self, checked: bool) -> None:
        b = self.cur_block()
        if not b:
            return
        self.ws.push_undo()
        b.shared_end = checked
        if checked:
            b.link_to = ""
        self.ws.mark_dirty()
        self.refresh_tree_labels()
        self.update_bar()

    def would_cycle(self, b, target) -> bool:
        cur, seen = target, set()
        while cur is not None and cur.id not in seen:
            if cur.id == b.id:
                return True
            seen.add(cur.id)
            cur = self.p.block(cur.link_to) if cur.link_to else None
        return False

    def link_to_shared(self) -> None:
        b = self.cur_block()
        if not b:
            return
        cands = [k for k in self.p.blocks if k.shared_end and k.id != b.id]
        cands.sort(key=lambda k: (k.parent_step != b.parent_step, k.title))
        if not cands:
            QMessageBox.information(self, tr("Связать с конечным"), tr(
                "Сначала откройте ветку, которая должна стать общим финалом, и нажмите на ней «Конечный для всех»."))
            return
        dlg = PickDialog(tr("Связать с конечным"), tr("Общий финал"), [(k.title or k.id, k.id) for k in cands], self)
        if dlg.run():
            target = self.p.block(dlg.value())
            if target and self.would_cycle(b, target):
                QMessageBox.warning(self, tr("Связать с конечным"), tr("Так получится замкнутый круг."))
                return
            self.ws.push_undo()
            b.link_to = dlg.value()
            self.ws.mark_dirty()
            self.refresh_tree_labels()
            self.update_bar()

    def link_all_here(self) -> None:
        b = self.cur_block()
        if not b or not b.shared_end:
            return
        sibs = [k for k in self.p.blocks if k.parent == b.parent and k.parent_step == b.parent_step
                and k.id != b.id and not k.shared_end and k.steps and k.steps[-1].kind not in TERMINAL]
        if not sibs:
            QMessageBox.information(self, tr("Связать остальные ответы"), tr("Нет готовых веток, которые можно связать."))
            return
        self.ws.push_undo()
        for k in sibs:
            k.link_to = b.id
        self.ws.mark_dirty()
        self.refresh_tree_labels()
        QMessageBox.information(self, tr("Связать остальные ответы"), tr("Связано веток: {}").format(len(sibs)))

    def unlink(self) -> None:
        b = self.cur_block()
        if b and b.link_to:
            self.ws.push_undo()
            b.link_to = ""
            self.ws.mark_dirty()
            self.refresh_tree_labels()
            self.update_bar()
