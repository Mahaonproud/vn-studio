"""Модель данных проекта новеллы (чистый Python, без Qt)."""
from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, field, fields, asdict
from pathlib import Path
from typing import Dict, List, Optional

from .util import short_id, slug, atomic_write

SCHEMA = 1
PROJECT_FILE = "project.json"

ASSET_CATS = ("backgrounds", "effects", "music", "loading", "menu_bg")
CAT_PREFIX = {"backgrounds": "bg", "effects": "fx", "music": "mu", "loading": "ld", "menu_bg": "mb"}

POSITIONS = ("left", "center", "right")

MENU_ACTIONS = {
    "start": "Start()",
    "load": 'ShowMenu("load")',
    "preferences": 'ShowMenu("preferences")',
    "help": 'ShowMenu("help")',
    "about": 'ShowMenu("about")',
    "quit": "Quit(confirm=False)",
}

CHAR_COLORS = ["#ff8fa3", "#7cc6fe", "#ffd166", "#95e1a3", "#c8a2ff", "#ff9f68", "#8fe3e3", "#e5a0ff"]


def _build(cls, data: dict):
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in (data or {}).items() if k in names})


@dataclass
class Asset:
    id: str
    name: str
    file: str = ""                 # путь относительно папки проекта
    kind: str = "file"             # эффекты: image | solid | shake | flash
    params: dict = field(default_factory=dict)


@dataclass
class Character:
    id: str
    name: str
    color: str = "#ffffff"
    emotions: Dict[str, str] = field(default_factory=dict)   # имя эмоции -> файл


@dataclass
class TextStyle:
    color: str = "#ffffff"
    opacity: int = 100
    size: int = 36
    kerning: float = 0.0
    font_file: str = ""
    box_enabled: bool = True
    box_color: str = "#000000"
    box_opacity: int = 62
    thought_italic: bool = True


@dataclass
class MenuConfig:
    title: str = ""
    title_x: int = 160
    title_y: int = 150
    title_size: int = 96
    title_color: str = "#ffffff"
    button_color: str = "#ffffff"
    hover_color: str = "#ff5a5f"
    bg: str = ""
    music: str = ""
    loading: List[dict] = field(default_factory=list)    # {"asset": id, "seconds": 2.0}
    effects: List[str] = field(default_factory=list)     # id эффектов поверх меню
    buttons: List[dict] = field(default_factory=list)


def default_menu_buttons() -> List[dict]:
    from .i18n import tr
    items = [("start", tr("Играть")), ("load", tr("Продолжить")), ("preferences", tr("Настройки")),
             ("help", tr("Управление")), ("quit", tr("Выход"))]
    out = []
    for i, (act, label) in enumerate(items):
        out.append({"id": f"btn{i + 1}", "label": label, "action": act,
                    "x": 160, "y": 430 + i * 110, "size": 56})
    return out


@dataclass
class Step:
    id: str
    kind: str
    data: dict = field(default_factory=dict)

    @staticmethod
    def new(kind: str, data: Optional[dict] = None) -> "Step":
        return Step(short_id(), kind, dict(data or {}))


@dataclass
class Block:
    id: str
    title: str = ""
    parent: str = ""             # id блока-родителя (для веток)
    parent_step: str = ""        # id шага «варианты ответа» в родителе
    steps: List[Step] = field(default_factory=list)
    shared_end: bool = False     # «конечный для всех»
    link_to: str = ""            # id блока, к которому ветка присоединяется


@dataclass
class SceneState:
    bg: str = ""
    music: str = ""
    chars: Dict[str, tuple] = field(default_factory=dict)   # id -> (эмоция, позиция)
    fx: List[str] = field(default_factory=list)

    def copy(self) -> "SceneState":
        return SceneState(self.bg, self.music, dict(self.chars), list(self.fx))


def apply_step(st: SceneState, step: Step) -> None:
    k, d = step.kind, step.data
    if k == "bg":
        st.bg = d.get("asset", "")
        if d.get("clear"):
            st.chars = {}
            st.fx = []
    elif k == "music":
        st.music = d.get("asset", "")
    elif k == "music_stop":
        st.music = ""
    elif k == "show":
        cid = d.get("char", "")
        old = st.chars.get(cid)
        pos = d.get("pos") or (old[1] if old else "center")
        st.chars[cid] = (d.get("emotion", ""), pos)
    elif k == "hide":
        st.chars.pop(d.get("char", ""), None)
    elif k == "fx_on":
        a = d.get("asset", "")
        if a and a not in st.fx:
            st.fx.append(a)
    elif k == "fx_off":
        a = d.get("asset", "")
        if a in st.fx:
            st.fx.remove(a)


class Project:
    def __init__(self, name: str = "", root=None) -> None:
        self.name = name
        self.root: Optional[Path] = Path(root) if root else None
        self.resolution = [1920, 1080]
        self.assets: Dict[str, List[Asset]] = {c: [] for c in ASSET_CATS}
        self.characters: List[Character] = []
        self.style = TextStyle()
        self.menu = MenuConfig(buttons=default_menu_buttons())
        self.blocks: List[Block] = []
        self.counters: Dict[str, int] = {}
        self.ignored: List[str] = []
        self.created = time.time()
        self.modified = time.time()

    # ------------------------------------------------------------ id / пути
    def new_id(self, prefix: str) -> str:
        n = self.counters.get(prefix, 0) + 1
        self.counters[prefix] = n
        return f"{prefix}{n}"

    def abs(self, rel: str) -> Path:
        return (self.root or Path(".")) / rel

    # --------------------------------------------------------------- поиск
    def find_asset(self, aid: str) -> Optional[Asset]:
        for lst in self.assets.values():
            for a in lst:
                if a.id == aid:
                    return a
        return None

    def get_char(self, cid: str) -> Optional[Character]:
        for c in self.characters:
            if c.id == cid:
                return c
        return None

    def block(self, bid: str) -> Optional[Block]:
        for b in self.blocks:
            if b.id == bid:
                return b
        return None

    def top_blocks(self) -> List[Block]:
        return [b for b in self.blocks if not b.parent]

    def children_of(self, bid: str) -> List[Block]:
        """Ветки блока в порядке вариантов ответа."""
        kids = [b for b in self.blocks if b.parent == bid]
        parent = self.block(bid)
        order: Dict[str, int] = {}
        if parent:
            for s in parent.steps:
                if s.kind == "choice":
                    for i, o in enumerate(s.data.get("options", [])):
                        order[o.get("block", "")] = i
        kids.sort(key=lambda k: order.get(k.id, 999))
        return kids

    def root_of(self, b: Block) -> Block:
        seen = set()
        cur = b
        while cur.parent and cur.id not in seen:
            seen.add(cur.id)
            nxt = self.block(cur.parent)
            if not nxt:
                break
            cur = nxt
        return cur

    def next_top(self, b: Block) -> Optional[Block]:
        root = self.root_of(b)
        tops = self.top_blocks()
        for i, t in enumerate(tops):
            if t.id == root.id:
                return tops[i + 1] if i + 1 < len(tops) else None
        return None

    def descendants(self, bid: str) -> List[str]:
        out: List[str] = []
        stack = [bid]
        while stack:
            cur = stack.pop()
            for k in self.blocks:
                if k.parent == cur and k.id not in out:
                    out.append(k.id)
                    stack.append(k.id)
        return out

    # --------------------------------------------------------- состояние сцены
    def state_at(self, block_id: str, upto: int, _depth: int = 0) -> SceneState:
        """Состояние сцены после первых `upto` шагов блока."""
        b = self.block(block_id)
        if not b:
            return SceneState()
        st = SceneState()
        if b.parent and _depth < 50:
            par = self.block(b.parent)
            if par:
                idx = next((i for i, s in enumerate(par.steps) if s.id == b.parent_step), len(par.steps))
                st = self.state_at(par.id, idx, _depth + 1)
        for s in b.steps[:max(0, upto)]:
            apply_step(st, s)
        return st

    # ------------------------------------------------------------ ветвления
    def add_block(self, title: str, parent: str = "", parent_step: str = "") -> Block:
        b = Block(self.new_id("b"), title, parent, parent_step)
        self.blocks.append(b)
        return b

    def remove_block_tree(self, bid: str) -> None:
        ids = set(self.descendants(bid)) | {bid}
        self.blocks = [b for b in self.blocks if b.id not in ids]
        for b in self.blocks:
            if b.link_to in ids:
                b.link_to = ""

    def snapshot_blocks(self) -> str:
        return json.dumps({"blocks": [_block_to_dict(b) for b in self.blocks],
                           "counters": self.counters}, ensure_ascii=False)

    def restore_blocks(self, snap: str) -> None:
        data = json.loads(snap)
        self.blocks = [_block_from_dict(d) for d in data["blocks"]]
        self.counters = data["counters"]

    # --------------------------------------------------------- сохранение
    def to_dict(self) -> dict:
        return {
            "schema": SCHEMA,
            "name": self.name,
            "resolution": self.resolution,
            "created": self.created,
            "modified": self.modified,
            "counters": self.counters,
            "ignored": self.ignored,
            "assets": {c: [asdict(a) for a in lst] for c, lst in self.assets.items()},
            "characters": [asdict(c) for c in self.characters],
            "style": asdict(self.style),
            "menu": asdict(self.menu),
            "blocks": [_block_to_dict(b) for b in self.blocks],
        }

    @classmethod
    def from_dict(cls, d: dict, root=None) -> "Project":
        p = cls(d.get("name", ""), root)
        p.resolution = list(d.get("resolution", [1920, 1080]))
        p.created = d.get("created", time.time())
        p.modified = d.get("modified", time.time())
        p.counters = dict(d.get("counters", {}))
        p.ignored = list(d.get("ignored", []))
        for c in ASSET_CATS:
            p.assets[c] = [_build(Asset, a) for a in d.get("assets", {}).get(c, [])]
        p.characters = [_build(Character, c) for c in d.get("characters", [])]
        p.style = _build(TextStyle, d.get("style", {}))
        p.menu = _build(MenuConfig, d.get("menu", {}))
        if not p.menu.buttons and "menu" not in d:
            p.menu.buttons = default_menu_buttons()
        p.blocks = [_block_from_dict(b) for b in d.get("blocks", [])]
        return p

    def save(self) -> None:
        if not self.root:
            raise RuntimeError("У проекта нет папки")
        self.root.mkdir(parents=True, exist_ok=True)
        self.modified = time.time()
        target = self.root / PROJECT_FILE
        if target.exists():
            try:
                shutil.copy2(target, self.root / (PROJECT_FILE + ".bak"))
            except OSError:
                pass
        atomic_write(target, json.dumps(self.to_dict(), ensure_ascii=False, indent=1))

    @classmethod
    def load(cls, root) -> "Project":
        root = Path(root)
        data = json.loads((root / PROJECT_FILE).read_text("utf-8"))
        return cls.from_dict(data, root)

    @classmethod
    def create(cls, name: str, projects_dir) -> "Project":
        projects_dir = Path(projects_dir)
        projects_dir.mkdir(parents=True, exist_ok=True)
        base = slug(name, "novella")
        folder, i = projects_dir / base, 2
        while folder.exists():
            folder = projects_dir / f"{base}-{i}"
            i += 1
        folder.mkdir(parents=True)
        p = cls(name.strip() or "Новелла", folder)
        p.save()
        return p


def _block_to_dict(b: Block) -> dict:
    return {"id": b.id, "title": b.title, "parent": b.parent, "parent_step": b.parent_step,
            "shared_end": b.shared_end, "link_to": b.link_to,
            "steps": [{"id": s.id, "kind": s.kind, "data": s.data} for s in b.steps]}


def _block_from_dict(d: dict) -> Block:
    b = Block(d["id"], d.get("title", ""), d.get("parent", ""), d.get("parent_step", ""),
              [], bool(d.get("shared_end", False)), d.get("link_to", ""))
    b.steps = [Step(s["id"], s["kind"], dict(s.get("data", {}))) for s in d.get("steps", [])]
    return b


def list_projects(projects_dir) -> List[dict]:
    """Короткие сведения о проектах в папке (для экрана «Старые проекты»)."""
    out = []
    root = Path(projects_dir)
    if not root.exists():
        return out
    for sub in sorted(root.iterdir()):
        f = sub / PROJECT_FILE
        if sub.is_dir() and f.exists():
            try:
                d = json.loads(f.read_text("utf-8"))
                out.append({"path": str(sub), "name": d.get("name", sub.name),
                            "modified": float(d.get("modified", os.path.getmtime(f)))})
            except Exception:
                out.append({"path": str(sub), "name": sub.name, "modified": os.path.getmtime(f)})
    out.sort(key=lambda x: -x["modified"])
    return out
