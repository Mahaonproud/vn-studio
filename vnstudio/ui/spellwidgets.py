"""Текстовое поле с проверкой орфографии: подчёркивание, меню исправлений, панель-подсказка."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QColor, QSyntaxHighlighter, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from ..core.i18n import tr


class SpellHighlighter(QSyntaxHighlighter):
    def __init__(self, document, ctx) -> None:
        super().__init__(document)
        self.ctx = ctx
        self.fmt = QTextCharFormat()
        self.fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        self.fmt.setUnderlineColor(QColor("#ff453a"))

    def highlightBlock(self, text: str) -> None:
        if self.ctx is None:
            return
        for s, e, _w in self.ctx.errors(text):
            self.setFormat(s, e - s, self.fmt)


class SpellTextEdit(QPlainTextEdit):
    def __init__(self, ctx=None, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.hl = SpellHighlighter(self.document(), ctx)

    def set_ctx(self, ctx) -> None:
        self.ctx = ctx
        self.hl.ctx = ctx
        self.hl.rehighlight()

    def replace_range(self, start: int, end: int, new: str) -> None:
        cur = self.textCursor()
        cur.setPosition(start)
        cur.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cur.insertText(new)
        self.setTextCursor(cur)

    def contextMenuEvent(self, ev) -> None:
        menu = self.createStandardContextMenu()
        if self.ctx is not None:
            pos = self.cursorForPosition(ev.pos()).position()
            for s, e, w in self.ctx.errors(self.toPlainText()):
                if s <= pos <= e:
                    acts = menu.actions()
                    first = acts[0] if acts else None
                    items = []
                    for sg in self.ctx.suggest(w)[:6]:
                        a = QAction(sg, menu)
                        a.triggered.connect(lambda checked=False, s=s, e=e, sg=sg: self.replace_range(s, e, sg))
                        items.append(a)
                    keep = QAction(tr("Оставить как есть"), menu)
                    keep.triggered.connect(lambda checked=False, w=w: self._keep(w))
                    items.append(keep)
                    for a in items:
                        menu.insertAction(first, a)
                    menu.insertSeparator(first)
                    break
        menu.exec(ev.globalPos())

    def _keep(self, word: str) -> None:
        self.ctx.ignore_word(word)
        self.hl.rehighlight()


class SpellStrip(QWidget):
    """Под полем ввода: «слво → слово  [Оставить]»."""
    replace = Signal(int, int, str)
    keep = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(4)
        self.setVisible(False)

    def _clear(self) -> None:
        while self.lay.count():
            item = self.lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def set_errors(self, errs) -> None:
        """errs: список (start, end, слово, [варианты])."""
        self._clear()
        for s, e, word, sugg in errs[:3]:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            lab = QLabel("«" + word + "» →")
            lab.setProperty("role", "warn")
            h.addWidget(lab)
            for sg in sugg[:3]:
                b = QPushButton(sg)
                b.clicked.connect(lambda checked=False, s=s, e=e, sg=sg: self.replace.emit(s, e, sg))
                h.addWidget(b)
            if not sugg:
                h.addWidget(QLabel(tr("нет вариантов")))
            k = QPushButton(tr("Оставить"))
            k.clicked.connect(lambda checked=False, w=word: self.keep.emit(w))
            h.addWidget(k)
            h.addStretch(1)
            self.lay.addWidget(row)
        self.setVisible(bool(errs))
