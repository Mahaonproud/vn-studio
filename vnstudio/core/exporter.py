"""Генерация кода Ren'Py из проекта."""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .check import collect_usage
from .i18n import tr
from .model import MENU_ACTIONS, POSITIONS, Project, SceneState, apply_step
from .util import Namer, hex_alpha, image_size

ASSET_DIR = "vn_assets"
TRANS = {"none": "", "dissolve": "dissolve", "fade": "fade"}
HEADER = "# -*- coding: utf-8 -*-\n# Файл создан программой VN Studio. Не правьте его вручную:\n# при следующем сохранении проекта изменения будут перезаписаны.\n\n"


@dataclass
class Report:
    out_dir: str = ""
    files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def rpy(text: str) -> str:
    """Экранирует текст для строки Ren'Py."""
    s = (text or "").replace("\\", "\\\\").replace('"', '\\"').replace("\r", "")
    s = s.replace("\n", "\\n").replace("{", "{{").replace("[", "[[")
    return s


def export_project(project: Project, game_dir) -> Report:
    return _Exporter(project, Path(game_dir)).run()


class _Exporter:
    def __init__(self, p: Project, game: Path) -> None:
        self.p = p
        self.game = game
        self.rep = Report(out_dir=str(game))
        self.use = collect_usage(p)
        self.W, self.H = p.resolution[0], p.resolution[1]
        self.files: Dict[str, str] = {}          # id ресурса -> путь относительно game/
        self.img: Dict[str, str] = {}            # id ресурса -> имя изображения Ren'Py
        self.fx_expr: Dict[str, str] = {}
        self.char_var: Dict[str, str] = {}
        self.char_tag: Dict[str, str] = {}
        self.emo_attr: Dict[tuple, str] = {}
        self.fnames = {sub: Namer() for sub in ("bg", "fx", "audio", "chars", "loading", "menu", "fonts")}
        self.inames = Namer()
        self._nm: Dict[str, Namer] = {}
        self.music: Dict[str, str] = {}

    def warn(self, text: str) -> None:
        self.rep.warnings.append(text)

    # ----------------------------------------------------------- копирование
    def _copy(self, rel: str, sub: str, base: str) -> Optional[str]:
        src = self.p.abs(rel)
        if not rel or not src.exists():
            return None
        name = self.fnames[sub].get(base, "file")
        dst_dir = self.game / ASSET_DIR / sub
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / (name + src.suffix.lower())
        shutil.copy2(src, dst)
        return f"{ASSET_DIR}/{sub}/{dst.name}"

    def _fit(self, path: str) -> str:
        return f'Transform("{path}", xysize=({self.W}, {self.H}))'

    # ------------------------------------------------------------------ запуск
    def run(self) -> Report:
        p = self.p
        assets_dir = self.game / ASSET_DIR
        if assets_dir.exists():
            shutil.rmtree(assets_dir)
        self.game.mkdir(parents=True, exist_ok=True)

        setup = [HEADER, "init offset = 10\n\n"]
        # персонажи
        setup.append("define thought = Character(None%s)\n" % (", what_italic=True" if p.style.thought_italic else ""))
        char_ids = [c.id for c in p.characters if c.id in self.use.chars or c.id in self.use.speakers]
        for cid in char_ids:
            c = p.get_char(cid)
            self.char_var[cid] = self._unique("c_", c.name, "chv")
            self.char_tag[cid] = self._unique("ch_", c.name, "cht")
            setup.append(f'define {self.char_var[cid]} = Character("{rpy(c.name)}", color="{c.color}")\n')
        setup.append("\n")
        # спрайты
        for cid in char_ids:
            c = p.get_char(cid)
            if cid not in self.use.chars:
                continue
            emo_namer = Namer()
            for emo in sorted(self.use.chars[cid]):
                rel = c.emotions.get(emo, "")
                path = self._copy(rel, "chars", f"{self.char_tag[cid]}_{emo}")
                if not path:
                    self.warn(tr("Не найден файл эмоции «{}» у персонажа «{}».").format(emo, c.name))
                    continue
                attr = emo_namer.get(emo, "emo")
                self.emo_attr[(cid, emo)] = attr
                size = image_size(self.game / path)
                zoom = ""
                if size and size[1] > 0:
                    z = round(0.92 * self.H / size[1], 4)
                    zoom = f", zoom={z}"
                setup.append(f'image {self.char_tag[cid]} {attr} = Transform("{path}"{zoom})\n')
        setup.append("\n")
        # фоны
        for aid in sorted(self.use.bg):
            a = p.find_asset(aid)
            path = self._copy(a.file, "bg", a.name) if a else None
            if not path:
                self.warn(tr("Не найден фон «{}».").format(a.name if a else aid))
                continue
            name = self.inames.get(a.name, "bg")
            self.img[aid] = f"bg {name}"
            setup.append(f"image bg {name} = {self._fit(path)}\n")
        # эффекты
        for aid in sorted(self.use.fx):
            a = p.find_asset(aid)
            if not a:
                continue
            if a.kind == "solid":
                self.fx_expr[aid] = f'Solid("{hex_alpha(a.params.get("color", "#000000"), a.params.get("alpha", 40))}")'
            elif a.kind == "image":
                path = self._copy(a.file, "fx", a.name)
                if not path:
                    self.warn(tr("Не найден файл эффекта «{}».").format(a.name))
                    continue
                self.fx_expr[aid] = self._fit(path)
            else:
                continue
            name = self.inames.get(a.name, "fx", prefix="fx_")
            self.img[aid] = name
            setup.append(f"image {name} = {self.fx_expr[aid]}\n")
        # загрузочные экраны
        for aid in sorted(self.use.loading):
            a = p.find_asset(aid)
            path = self._copy(a.file, "loading", a.name) if a else None
            if not path:
                self.warn(tr("Не найден загрузочный экран «{}».").format(a.name if a else aid))
                continue
            name = self.inames.get(a.name, "ld", prefix="ld_")
            self.img[aid] = name
            setup.append(f"image {name} = {self._fit(path)}\n")
        setup.append("\n")
        setup.append(self._style_block())

        # музыка
        for aid in sorted(self.use.music):
            a = p.find_asset(aid)
            path = self._copy(a.file, "audio", a.name) if a else None
            if path:
                self.music[aid] = path
            else:
                self.warn(tr("Не найдена музыка «{}».").format(a.name if a else aid))

        self._write("vn_setup.rpy", "".join(setup))
        self._write("vn_menu.rpy", self._menu_file())
        self._write("script.rpy", self._script_file())
        return self.rep

    def _unique(self, prefix: str, text: str, key: str) -> str:
        nm = self._nm.setdefault(key, Namer())
        return nm.get(text, "x", prefix=prefix)

    def _write(self, name: str, text: str) -> None:
        path = self.game / name
        path.write_text(text, encoding="utf-8")
        self.rep.files.append(str(path))

    # ---------------------------------------------------------------- стили
    def _style_block(self) -> str:
        s = self.p.style
        font = ""
        if s.font_file:
            fp = self._copy(s.font_file, "fonts", "font")
            if fp:
                font = f'    font "{fp}"\n'
            else:
                self.warn(tr("Файл шрифта не найден — используется шрифт по умолчанию."))
        out = ["style say_dialogue:\n",
               f'    color "{hex_alpha(s.color, s.opacity)}"\n',
               f"    size {int(s.size)}\n",
               f"    kerning {float(s.kerning)}\n", font, "\n"]
        if s.box_enabled:
            out.append(f'style window:\n    background Solid("{hex_alpha(s.box_color, s.box_opacity)}")\n')
        return "".join(out)

    # ----------------------------------------------------------------- меню
    def _menu_file(self) -> str:
        p, m = self.p, self.p.menu
        out = [HEADER, "init offset = 10\n\n"]
        mp = self.music.get(m.music) if m.music else None
        if mp:
            out.append(f'define config.main_menu_music = "{mp}"\n\n')
        out.append("screen main_menu():\n    tag menu\n")
        bg = p.find_asset(m.bg) if m.bg else None
        bgpath = self._copy(bg.file, "menu", bg.name) if bg else None
        if bg and not bgpath:
            self.warn(tr("Не найден фон главного меню."))
        out.append(f"    add {self._fit(bgpath)}\n" if bgpath else '    add Solid("#000000")\n')
        for aid in m.effects:
            expr = self.fx_expr.get(aid)
            if expr:
                out.append(f"    add {expr}\n")
        if m.title.strip():
            out.append(f'    text "{rpy(m.title)}" xpos {int(m.title_x)} ypos {int(m.title_y)} '
                       f'size {int(m.title_size)} color "{m.title_color}"\n')
        for b in m.buttons:
            action = MENU_ACTIONS.get(b.get("action", ""), "Start()")
            out.append(f'    textbutton "{rpy(b.get("label", ""))}":\n'
                       f"        action {action}\n"
                       f"        xpos {int(b.get('x', 0))} ypos {int(b.get('y', 0))}\n"
                       f"        text_size {int(b.get('size', 48))}\n"
                       f'        text_idle_color "{m.button_color}"\n'
                       f'        text_hover_color "{m.hover_color}"\n')
        if not m.buttons and not m.title.strip():
            out.append("    null\n")
        return "".join(out)

    # --------------------------------------------------------------- сценарий
    def _script_file(self) -> str:
        p = self.p
        out = [HEADER]
        loads = [i for i in p.menu.loading if i.get("asset") in self.img]
        if loads:
            out.append("label splashscreen:\n    scene black\n")
            for it in loads:
                sec = max(0.5, float(it.get("seconds", 2.0)))
                out.append(f"    scene {self.img[it['asset']]} with dissolve\n    pause {sec}\n")
            out.append("    scene black with dissolve\n    return\n\n")
        tops = p.top_blocks()
        out.append("label start:\n")
        out.append(f"    jump vn_{tops[0].id}\n\n" if tops else "    return\n\n")
        for b in p.blocks:
            out.append(self._block(b))
        return "".join(out)

    def _trans(self, key: str, default: str) -> str:
        t = TRANS.get(key or default, TRANS[default])
        return f" with {t}" if t else ""

    def _block(self, b) -> str:
        p = self.p
        title = (b.title or b.id).replace("\n", " ")
        lines: List[str] = [f"# {title}", f"label vn_{b.id}:"]
        st = p.state_at(b.id, 0)
        body: List[str] = []
        for s in b.steps:
            self._step(b, s, st, body)
            apply_step(st, s)
        last = b.steps[-1].kind if b.steps else ""
        if last not in ("choice", "ending"):
            target = p.block(b.link_to) if b.link_to else None
            if target:
                body.append(f"jump vn_{target.id}")
            else:
                nxt = p.next_top(b)
                body.append(f"jump vn_{nxt.id}" if nxt else "return")
        if not body:
            body.append("return")
        lines += ["    " + ln for ln in body]
        return "\n".join(lines) + "\n\n"

    def _step(self, b, s, st: SceneState, out: List[str]) -> None:
        p, d = self.p, s.data
        k = s.kind
        if k == "say":
            text = d.get("text", "").strip()
            if not text:
                return
            who = self.char_var.get(d.get("who", ""), "thought")
            out.append(f'{who} "{rpy(text)}"')
        elif k == "bg":
            name = self.img.get(d.get("asset", ""))
            if not name:
                return
            kw = "scene" if (d.get("clear") or not st.bg) else "show"
            out.append(f"{kw} {name}{self._trans(d.get('trans'), 'fade')}")
        elif k == "music":
            path = self.music.get(d.get("asset", ""))
            if path:
                out.append(f'play music "{path}" fadein 1.0')
        elif k == "music_stop":
            out.append("stop music fadeout 1.0")
        elif k == "show":
            cid, emo = d.get("char", ""), d.get("emotion", "")
            attr = self.emo_attr.get((cid, emo))
            if not attr:
                return
            pos = d.get("pos") or (st.chars[cid][1] if cid in st.chars else "center")
            if pos not in POSITIONS:
                pos = "center"
            at = "" if (cid in st.chars and st.chars[cid][1] == pos) else f" at {pos}"
            out.append(f"show {self.char_tag[cid]} {attr}{at}{self._trans(d.get('trans'), 'dissolve')}")
        elif k == "hide":
            tag = self.char_tag.get(d.get("char", ""))
            if tag:
                out.append(f"hide {tag}{self._trans(d.get('trans'), 'dissolve')}")
        elif k == "fx_on":
            name = self.img.get(d.get("asset", ""))
            if name:
                out.append(f"show {name} zorder 60{self._trans(d.get('trans'), 'dissolve')}")
        elif k == "fx_off":
            name = self.img.get(d.get("asset", ""))
            if name:
                out.append(f"hide {name}{self._trans(d.get('trans'), 'dissolve')}")
        elif k == "fx_once":
            a = p.find_asset(d.get("asset", ""))
            if a and a.kind == "shake":
                out.append("with vpunch")
            elif a and a.kind == "flash":
                out.append('with Fade(0.1, 0.0, 0.5, color="#ffffff")')
        elif k == "choice":
            out.append("menu:")
            for o in d.get("options", []):
                text = o.get("text", "").strip() or "..."
                out.append(f'    "{rpy(text)}":')
                tgt = p.block(o.get("block", ""))
                out.append(f"        jump vn_{tgt.id}" if tgt else "        pass")
            out.append("return")
        elif k == "ending":
            out.append("scene black with fade")
            title = d.get("title", "").strip()
            if title:
                out.append(f'centered "{rpy(title)}"')
            out.append("return")
