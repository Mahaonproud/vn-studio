"""Виджет, который рисует сцену так, как она будет выглядеть в игре."""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPixmap, QTextOption
from PySide6.QtWidgets import QWidget

from ..core.model import SceneState
from .theme import rgba_color

X_POS = {"left": 0.22, "center": 0.5, "right": 0.78}


class ScenePreview(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.project = None
        self.state = SceneState()
        self.who = ""
        self.text = ""
        self._pix: dict = {}
        self._scaled: dict = {}
        self._family = ""
        self._font_loaded = None
        self.setMinimumSize(360, 203)

    def sizeHint(self) -> QSize:
        return QSize(640, 360)

    def set_project(self, project) -> None:
        self.project = project
        self.refresh()

    def set_scene(self, state: SceneState, who: str, text: str) -> None:
        self.state = state
        self.who = who
        self.text = text
        self.update()

    def refresh(self) -> None:
        self._pix.clear()
        self._scaled.clear()
        self._font_loaded = None
        self.update()

    # ---------------------------------------------------------------- вспомогательное
    def _pm(self, rel: str) -> QPixmap:
        if rel not in self._pix:
            self._pix[rel] = QPixmap(str(self.project.abs(rel))) if rel else QPixmap()
        return self._pix[rel]

    def _scaled_pm(self, rel: str, w: int, h: int) -> QPixmap:
        key = (rel, w, h)
        if key not in self._scaled:
            pm = self._pm(rel)
            self._scaled[key] = pm if pm.isNull() else pm.scaled(
                w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        return self._scaled[key]

    def _ensure_font(self) -> None:
        ff = self.project.style.font_file
        if ff == self._font_loaded:
            return
        self._font_loaded = ff
        self._family = ""
        if ff:
            fid = QFontDatabase.addApplicationFont(str(self.project.abs(ff)))
            fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
            if fams:
                self._family = fams[0]

    def stage_rect(self) -> QRectF:
        rw, rh = self.project.resolution if self.project else (1920, 1080)
        ratio = rw / float(rh or 1)
        W, H = float(self.width()), float(self.height())
        w = W
        h = w / ratio
        if h > H:
            h = H
            w = h * ratio
        return QRectF((W - w) / 2, (H - h) / 2, w, h)

    # ----------------------------------------------------------------- рисование
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#000000"))
        if not self.project:
            p.end()
            return
        r = self.stage_rect()
        st = self.state
        res_h = float(self.project.resolution[1] or 1080)
        scale = r.height() / res_h
        p.save()
        p.setClipRect(r)
        p.fillRect(r, QColor("#101018"))
        # фон
        bg = self.project.find_asset(st.bg) if st.bg else None
        if bg and bg.file:
            pm = self._pm(bg.file)
            if not pm.isNull():
                p.drawPixmap(r.toRect(), pm)
        # персонажи
        for cid, (emo, pos) in st.chars.items():
            ch = self.project.get_char(cid)
            rel = ch.emotions.get(emo, "") if ch else ""
            if not rel:
                continue
            pm = self._scaled_pm(rel, int(r.width()), int(r.height() * 0.92))
            if pm.isNull():
                continue
            cx = r.left() + r.width() * X_POS.get(pos, 0.5)
            p.drawPixmap(int(cx - pm.width() / 2), int(r.bottom() - pm.height()), pm)
        # эффекты
        for fid in st.fx:
            a = self.project.find_asset(fid)
            if not a:
                continue
            if a.kind == "solid":
                p.fillRect(r, rgba_color(a.params.get("color", "#000000"), a.params.get("alpha", 40)))
            elif a.kind == "image" and a.file:
                pm = self._pm(a.file)
                if not pm.isNull():
                    p.drawPixmap(r.toRect(), pm)
        # диалоговое окно
        if self.text or self.who:
            self._draw_dialogue(p, r, scale)
        p.restore()
        p.end()

    def _draw_dialogue(self, p: QPainter, r: QRectF, scale: float) -> None:
        self._ensure_font()
        s = self.project.style
        box_h = r.height() * 0.28
        box = QRectF(r.left(), r.bottom() - box_h, r.width(), box_h)
        if s.box_enabled:
            p.fillRect(box, rgba_color(s.box_color, s.box_opacity))
        else:
            p.fillRect(box, QColor(20, 30, 50, 190))
        font = QFont(self._family) if self._family else QFont()
        px = max(8, int(s.size * scale))
        font.setPixelSize(px)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, float(s.kerning) * scale)
        who_name, who_color = "", "#ffffff"
        if self.who:
            ch = self.project.get_char(self.who)
            if ch:
                who_name, who_color = ch.name, ch.color
        pad = r.width() * 0.06
        y = box.top() + box_h * 0.10
        if who_name:
            nf = QFont(font)
            nf.setBold(True)
            p.setFont(nf)
            p.setPen(QColor(who_color))
            p.drawText(QRectF(box.left() + pad, y, box.width() - 2 * pad, px * 1.6), who_name, QTextOption(Qt.AlignmentFlag.AlignLeft))
            y += px * 1.5
        tf = QFont(font)
        tf.setItalic(bool(s.thought_italic and not self.who))
        p.setFont(tf)
        p.setPen(rgba_color(s.color, s.opacity))
        opt = QTextOption(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        opt.setWrapMode(QTextOption.WrapMode.WordWrap)
        p.drawText(QRectF(box.left() + pad, y, box.width() - 2 * pad, box.bottom() - y - 4), self.text, opt)
