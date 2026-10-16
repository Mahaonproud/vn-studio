"""Тёмная и светлая тема в духе приложений Apple + общие помощники для виджетов."""
from __future__ import annotations

from string import Template

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QColor, QIcon, QImageReader, QPixmap

DARK = dict(bg="#1c1c1e", panel="#2c2c2e", panel2="#3a3a3c", text="#f5f5f7", sub="#98989d",
            accent="#0a84ff", accent_hover="#409cff", accent_text="#ffffff", danger="#ff453a",
            border="#48484a", hover="#48484a")
LIGHT = dict(bg="#f2f2f7", panel="#ffffff", panel2="#e5e5ea", text="#1c1c1e", sub="#6e6e73",
             accent="#007aff", accent_hover="#3395ff", accent_text="#ffffff", danger="#ff3b30",
             border="#d1d1d6", hover="#d8d8de")

QSS = Template("""
* { font-family: "SF Pro Text", "Segoe UI", "Ubuntu", "Noto Sans", sans-serif; font-size: 13px; }
QWidget { background: $bg; color: $text; }
QLabel { background: transparent; }
QLabel[role="title"] { font-size: 34px; font-weight: 600; }
QLabel[role="h2"] { font-size: 18px; font-weight: 600; }
QLabel[role="sub"] { color: $sub; }
QLabel[role="warn"] { color: $danger; }
QFrame[card="true"] { background: $panel; border: 1px solid $border; border-radius: 12px; }
QPushButton { background: $panel2; border: none; border-radius: 8px; padding: 7px 14px; }
QPushButton:hover { background: $hover; }
QPushButton:disabled { color: $sub; }
QPushButton[accent="true"] { background: $accent; color: $accent_text; font-weight: 600; }
QPushButton[accent="true"]:hover { background: $accent_hover; }
QPushButton[danger="true"] { color: $danger; }
QPushButton[big="true"] { font-size: 17px; padding: 15px 30px; border-radius: 12px; }
QPushButton:checked { background: $accent; color: $accent_text; }
QToolButton { background: $panel2; border: none; border-radius: 13px; padding: 5px 12px; }
QToolButton:hover { background: $hover; }
QToolButton:checked { background: $accent; color: $accent_text; }
QToolButton[dim="true"] { color: $sub; }
QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: $panel; border: 1px solid $border; border-radius: 8px; padding: 6px 8px;
    selection-background-color: $accent; selection-color: $accent_text; }
QLineEdit:focus, QPlainTextEdit:focus { border: 1px solid $accent; }
QComboBox QAbstractItemView { background: $panel; selection-background-color: $accent; outline: 0; }
QListWidget, QTreeWidget { background: $panel; border: 1px solid $border; border-radius: 10px; outline: 0; }
QListWidget::item { padding: 6px 8px; border-radius: 6px; }
QListWidget::item:selected, QTreeWidget::item:selected { background: $accent; color: $accent_text; }
QTreeWidget::item { padding: 5px 4px; }
QScrollArea { border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: $panel2; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: $panel2; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QSlider::groove:horizontal { height: 4px; background: $panel2; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $accent; border-radius: 2px; }
QSlider::handle:horizontal { background: $accent; width: 16px; margin: -6px 0; border-radius: 8px; }
QMenu { background: $panel; border: 1px solid $border; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 6px; }
QMenu::item:selected { background: $accent; color: $accent_text; }
QToolTip { background: $panel; color: $text; border: 1px solid $border; padding: 4px; }
QDialog { background: $bg; }
QCheckBox { background: transparent; spacing: 8px; }
QSplitter::handle { background: $border; }
QGraphicsView { border: 1px solid $border; border-radius: 10px; }
QProgressDialog { background: $bg; }
""")


def build_qss(theme: str) -> str:
    return QSS.substitute(DARK if theme == "dark" else LIGHT)


def palette(theme: str) -> dict:
    return DARK if theme == "dark" else LIGHT


def rgba_color(hex_color: str, percent=100) -> QColor:
    """Цвет '#rrggbb' с прозрачностью в процентах (у Qt формат '#aarrggbb', поэтому так)."""
    c = QColor(hex_color)
    if not c.isValid():
        c = QColor("#ffffff")
    c.setAlphaF(max(0.0, min(1.0, float(percent) / 100.0)))
    return c


_THUMBS: dict = {}


def thumb(path: str, w: int = 96, h: int = 54) -> QPixmap:
    """Маленькая картинка для списков (кэшируется)."""
    key = (path, w, h)
    if key in _THUMBS:
        return _THUMBS[key]
    pm = QPixmap()
    try:
        r = QImageReader(path)
        size = r.size()
        if size.isValid() and size.width() > 0 and size.height() > 0:
            k = min(w * 2 / size.width(), h * 2 / size.height(), 1.0)
            r.setScaledSize(QSize(max(1, int(size.width() * k)), max(1, int(size.height() * k))))
        img = r.read()
        if not img.isNull():
            pm = QPixmap.fromImage(img).scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation)
    except Exception:
        pm = QPixmap()
    _THUMBS[key] = pm
    return pm


def clear_thumbs() -> None:
    _THUMBS.clear()


def icon_for(path: str, w: int = 96, h: int = 54) -> QIcon:
    pm = thumb(path, w, h)
    return QIcon(pm) if not pm.isNull() else QIcon()


class AudioPreview:
    """Предпрослушивание музыки (QtMultimedia). Если модуля нет — просто не играет."""

    def __init__(self, volume: int = 70) -> None:
        self.ok = False
        self.player = None
        self.out = None
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            self.player = QMediaPlayer()
            self.out = QAudioOutput()
            self.player.setAudioOutput(self.out)
            self.set_volume(volume)
            self.ok = True
        except Exception:
            self.ok = False

    def set_volume(self, v: int) -> None:
        if self.out is not None:
            self.out.setVolume(max(0, min(100, v)) / 100.0)

    def play(self, path) -> bool:
        if not self.ok:
            return False
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()
        return True

    def stop(self) -> None:
        if self.ok:
            self.player.stop()
