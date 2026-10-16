"""Упрощённая имитация PySide6: позволяет выполнять реальный код интерфейса без экрана.

Проверяет НАШУ логику (имена, вызовы, сигналы, состояние). Правильность вызовов самого Qt она
не проверяет — для этого нужен настоящий PySide6.
"""
import inspect
import sys
import types

SIGNALS = {"clicked", "toggled", "textChanged", "valueChanged", "currentIndexChanged", "currentRowChanged",
           "currentItemChanged", "itemDoubleClicked", "itemSelectionChanged", "selectionChanged", "accepted",
           "rejected", "timeout", "activated", "triggered", "stateChanged", "finished"}

ANSWERS = {}
DIALOG_HOOK = [None]
LOG = []


class BoundSignal:
    def __init__(self, owner):
        self.owner = owner
        self.slots = []

    def connect(self, f):
        self.slots.append(f)

    def disconnect(self, *a):
        self.slots.clear()

    def emit(self, *args):
        if getattr(self.owner, "_blocked", False):
            return
        for f in list(self.slots):
            try:
                params = list(inspect.signature(f).parameters.values())
            except (ValueError, TypeError):
                params = None
            if params is None or any(p.kind == p.VAR_POSITIONAL for p in params):
                f(*args)
            else:
                n = len([p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)])
                f(*args[:n])


class Signal:
    def __init__(self, *a):
        self.name = ""

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, inst, owner):
        if inst is None:
            return self
        sig = BoundSignal(inst)
        inst.__dict__[self.name] = sig
        return sig


class _Meta(type):
    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        v = Loose()
        type.__setattr__(cls, name, v)
        return v


class Loose(metaclass=_Meta):
    _blocked = False

    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name in SIGNALS:
            s = BoundSignal(self)
            self.__dict__[name] = s
            return s
        v = Loose()
        self.__dict__[name] = v
        return v

    def __call__(self, *a, **k):
        return Loose()

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return True

    def __or__(self, o):
        return self

    __ror__ = __and__ = __add__ = __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = __truediv__ = __or__

    def __lt__(self, o):
        return False

    __le__ = __gt__ = __ge__ = __lt__

    def __int__(self):
        return 0

    def __float__(self):
        return 0.0

    def __index__(self):
        return 0

    def blockSignals(self, b):
        old = self._blocked
        self._blocked = bool(b)
        return old

    def setProperty(self, k, v):
        self.__dict__.setdefault("_props", {})[k] = v

    def property(self, k):
        return self.__dict__.get("_props", {}).get(k)


# ------------------------------------------------------------ виджеты
class QWidget(Loose):
    def __init__(self, *a, **k):
        self._visible = True
        self._enabled = True
        self._layout = None

    def setVisible(self, v):
        self._visible = bool(v)

    def isVisible(self):
        return self._visible

    def setEnabled(self, v):
        self._enabled = bool(v)

    def isEnabled(self):
        return self._enabled

    def setLayout(self, l):
        self._layout = l

    def setParent(self, p):
        pass

    def deleteLater(self):
        pass

    def width(self):
        return 800

    def height(self):
        return 450

    def rect(self):
        return Loose()

    def update(self):
        pass


class _LItem:
    def __init__(self, w=None, layout=None):
        self.w, self.l = w, layout

    def widget(self):
        return self.w

    def layout(self):
        return self.l


class _Layout(Loose):
    def __init__(self, *a, **k):
        self._items = []

    def addWidget(self, w, *a, **k):
        self._items.append(_LItem(w))

    def addLayout(self, l, *a, **k):
        self._items.append(_LItem(None, l))

    def addStretch(self, *a):
        self._items.append(_LItem())

    def addSpacing(self, *a):
        self._items.append(_LItem())

    def addRow(self, *a):
        for x in a:
            if isinstance(x, QWidget):
                self._items.append(_LItem(x))
            elif isinstance(x, _Layout):
                self._items.append(_LItem(None, x))

    def insertWidget(self, i, w, *a):
        self._items.insert(i, _LItem(w))

    def count(self):
        return len(self._items)

    def takeAt(self, i):
        return self._items.pop(i)


class QVBoxLayout(_Layout):
    pass


class QHBoxLayout(_Layout):
    pass


class QGridLayout(_Layout):
    pass


class QFormLayout(_Layout):
    pass


class QListWidgetItem(Loose):
    def __init__(self, *a):
        self._text = next((x for x in a if isinstance(x, str)), "")
        self._data = {}

    def text(self):
        return self._text

    def setText(self, t):
        self._text = t

    def setData(self, role, v):
        self._data[role] = v

    def data(self, role=None):
        return self._data.get(role)


class QListWidget(QWidget):
    def __init__(self, *a):
        super().__init__()
        self._items = []
        self._cur = -1

    def addItem(self, it):
        if isinstance(it, str):
            it = QListWidgetItem(it)
        self._items.append(it)

    def item(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def count(self):
        return len(self._items)

    def clear(self):
        self._items = []
        if self._cur != -1:
            self._cur = -1
            self.currentRowChanged.emit(-1)

    def currentRow(self):
        return self._cur

    def setCurrentRow(self, r):
        r = max(-1, min(r, len(self._items) - 1))
        if r != self._cur:
            self._cur = r
            self.currentRowChanged.emit(r)

    def currentItem(self):
        return self.item(self._cur)

    def setCurrentItem(self, it):
        self.setCurrentRow(self._items.index(it))


class QTreeWidgetItem(Loose):
    def __init__(self, texts=None):
        self._texts = list(texts or [""])
        self._data = {}
        self.children = []

    def setText(self, col, t):
        self._texts[col] = t

    def text(self, col=0):
        return self._texts[col]

    def setData(self, col, role, v):
        self._data[(col, role)] = v

    def data(self, col, role=None):
        return self._data.get((col, role))

    def addChild(self, c):
        self.children.append(c)


class QTreeWidget(QWidget):
    def __init__(self, *a):
        super().__init__()
        self.tops = []
        self._cur = None

    def clear(self):
        self.tops = []
        self._cur = None

    def addTopLevelItem(self, it):
        self.tops.append(it)

    def setCurrentItem(self, it):
        prev, self._cur = self._cur, it
        if prev is not it:
            self.currentItemChanged.emit(it, prev)

    def currentItem(self):
        return self._cur


class QComboBox(QWidget):
    def __init__(self, *a):
        super().__init__()
        self._items = []
        self._cur = -1

    def addItem(self, *a):
        if a and isinstance(a[0], str):
            text, data = a[0], (a[1] if len(a) > 1 else None)
        else:
            text, data = a[1], (a[2] if len(a) > 2 else None)
        self._items.append((text, data))
        if self._cur == -1:
            self._cur = 0
            self.currentIndexChanged.emit(0)

    def count(self):
        return len(self._items)

    def clear(self):
        self._items = []
        if self._cur != -1:
            self._cur = -1
            self.currentIndexChanged.emit(-1)

    def currentIndex(self):
        return self._cur

    def setCurrentIndex(self, i):
        i = max(-1, min(i, len(self._items) - 1))
        if i != self._cur:
            self._cur = i
            self.currentIndexChanged.emit(i)

    def currentData(self):
        return self._items[self._cur][1] if 0 <= self._cur < len(self._items) else None

    def currentText(self):
        return self._items[self._cur][0] if 0 <= self._cur < len(self._items) else ""

    def findData(self, d):
        for i, (_t, v) in enumerate(self._items):
            if v == d:
                return i
        return -1

    def itemText(self, i):
        return self._items[i][0]

    def itemData(self, i):
        return self._items[i][1]


class QLineEdit(QWidget):
    def __init__(self, text="", *a):
        super().__init__()
        self._t = text if isinstance(text, str) else ""

    def text(self):
        return self._t

    def setText(self, t):
        if t != self._t:
            self._t = t
            self.textChanged.emit(t)


class QPlainTextEdit(QWidget):
    def __init__(self, *a):
        super().__init__()
        self._t = ""

    def toPlainText(self):
        return self._t

    def setPlainText(self, t):
        if t != self._t:
            self._t = t
            self.textChanged.emit()


class QSyntaxHighlighter(Loose):
    def __init__(self, doc=None):
        pass


class _Num(QWidget):
    def __init__(self, *a):
        super().__init__()
        self._v = 0

    def value(self):
        return self._v

    def setValue(self, v):
        if v != self._v:
            self._v = v
            self.valueChanged.emit(v)


class QSpinBox(_Num):
    pass


class QDoubleSpinBox(_Num):
    pass


class QSlider(_Num):
    pass


class _Btn(QWidget):
    def __init__(self, text="", *a):
        super().__init__()
        self._text = text if isinstance(text, str) else ""
        self._checked = False
        self._checkable = False

    def setCheckable(self, b):
        self._checkable = bool(b)

    def isChecked(self):
        return self._checked

    def setChecked(self, b):
        if bool(b) != self._checked:
            self._checked = bool(b)
            self.toggled.emit(self._checked)

    def setText(self, t):
        self._text = t

    def text(self):
        return self._text

    def click(self):
        if self._checkable:
            self.setChecked(not self._checked)
        self.clicked.emit(self._checked)


class QPushButton(_Btn):
    pass


class QToolButton(_Btn):
    pass


class QCheckBox(_Btn):
    def __init__(self, text="", *a):
        super().__init__(text)
        self._checkable = True


class QLabel(QWidget):
    def __init__(self, text="", *a):
        super().__init__()
        self._t = text if isinstance(text, str) else ""

    def setText(self, t):
        self._t = t

    def text(self):
        return self._t


class QButtonGroup(Loose):
    def __init__(self, *a):
        self._b = []

    def addButton(self, b, *a):
        self._b.append(b)

    def removeButton(self, b):
        self._b.remove(b)

    def buttons(self):
        return list(self._b)


class QStackedWidget(QWidget):
    def __init__(self, *a):
        super().__init__()
        self._w = []
        self._cur = -1

    def addWidget(self, w):
        self._w.append(w)
        if self._cur == -1:
            self._cur = 0
        return len(self._w) - 1

    def removeWidget(self, w):
        self._w.remove(w)
        self._cur = 0 if self._w else -1

    def widget(self, i):
        return self._w[i]

    def count(self):
        return len(self._w)

    def currentIndex(self):
        return self._cur

    def setCurrentIndex(self, i):
        self._cur = i


class QDialog(QWidget):
    def exec(self):
        h = DIALOG_HOOK[0]
        LOG.append(type(self).__name__)
        if h:
            h(self)
        return 0

    def accept(self):
        pass

    def reject(self):
        pass


class QMessageBox(QDialog):
    def __init__(self, *a):
        super().__init__()
        self._btns = []

    @staticmethod
    def question(*a, **k):
        return ANSWERS.get("question", QMessageBox.StandardButton.Yes)

    @staticmethod
    def information(*a, **k):
        LOG.append("info:" + str(a[2] if len(a) > 2 else ""))
        return QMessageBox.StandardButton.Ok

    warning = critical = information

    def addButton(self, *a):
        b = Loose()
        self._btns.append(b)
        return b

    def clickedButton(self):
        return self._btns[0] if self._btns else None


class QFileDialog(Loose):
    @staticmethod
    def getOpenFileNames(*a, **k):
        return ANSWERS.get("files", []), ""

    @staticmethod
    def getOpenFileName(*a, **k):
        return ANSWERS.get("file", ""), ""

    @staticmethod
    def getExistingDirectory(*a, **k):
        return ANSWERS.get("dir", "")


class QInputDialog(Loose):
    @staticmethod
    def getText(*a, **k):
        return ANSWERS.get("text", ("", False))


class QColorDialog(Loose):
    @staticmethod
    def getColor(*a, **k):
        c = Loose()
        c.isValid = lambda: False
        return c


class QApplication(Loose):
    @staticmethod
    def setOverrideCursor(*a):
        pass

    @staticmethod
    def restoreOverrideCursor():
        pass

    @staticmethod
    def processEvents():
        pass

    @staticmethod
    def instance():
        return Loose()


class _GItem(Loose):
    def __init__(self, *a, **k):
        self._p = (0, 0)
        self._sel = False
        self._scene = None

    def setPos(self, x, y=None):
        self._p = (x, y)

    def pos(self):
        class P:
            def __init__(s, p):
                s.p = p

            def x(s):
                return s.p[0]

            def y(s):
                return s.p[1]
        return P(self._p)

    def setSelected(self, b):
        self._sel = bool(b)
        if self._scene is not None:
            self._scene.selectionChanged.emit()

    def isSelected(self):
        return self._sel

    def mouseReleaseEvent(self, ev):
        pass


class QGraphicsScene(Loose):
    def __init__(self, *a):
        self._items = []

    def addItem(self, it):
        it._scene = self
        self._items.append(it)

    def addRect(self, *a):
        it = _GItem()
        self.addItem(it)
        return it

    addPixmap = addRect

    def clear(self):
        for it in self._items:
            it._scene = None
        self._items = []

    def selectedItems(self):
        return [i for i in self._items if i.isSelected()]

    def clearSelection(self):
        for i in self._items:
            i._sel = False
        self.selectionChanged.emit()


class QGraphicsView(QWidget):
    def __init__(self, scene=None, *a):
        super().__init__()
        self._scene = scene

    def scene(self):
        return self._scene


class QTimer(Loose):
    def __init__(self, *a):
        self.running = False

    def start(self, *a):
        self.running = True

    def stop(self):
        self.running = False


EXPLICIT = {k: v for k, v in list(globals().items()) if isinstance(v, type) and issubclass(v, Loose)}
EXPLICIT["Signal"] = Signal
EXPLICIT["QGraphicsRectItem"] = type("QGraphicsRectItem", (_GItem,), {})
EXPLICIT["QGraphicsSimpleTextItem"] = type("QGraphicsSimpleTextItem", (_GItem,), {
    "boundingRect": lambda self: Loose()})
EXPLICIT["QGraphicsItem"] = _GItem


def _module(name):
    m = types.ModuleType(name)
    cache = {}

    def getattr_(attr):
        if attr.startswith("__"):
            raise AttributeError(attr)
        if attr in EXPLICIT:
            return EXPLICIT[attr]
        if attr not in cache:
            cache[attr] = _Meta(attr, (QWidget,) if attr.startswith("Q") and "Layout" not in attr else (Loose,), {})
        return cache[attr]

    m.__getattr__ = getattr_
    return m


def install():
    root = types.ModuleType("PySide6")
    root.__path__ = []
    sys.modules["PySide6"] = root
    for sub in ("QtCore", "QtGui", "QtWidgets", "QtMultimedia"):
        mod = _module("PySide6." + sub)
        sys.modules["PySide6." + sub] = mod
        setattr(root, sub, mod)
