"""Проверка проекта перед экспортом и анализ используемых ассетов."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

from .i18n import tr
from .model import Project


@dataclass
class Issue:
    level: str          # error | warn | info
    text: str
    block: str = ""


@dataclass
class Usage:
    bg: Set[str] = field(default_factory=set)
    fx: Set[str] = field(default_factory=set)
    music: Set[str] = field(default_factory=set)
    loading: Set[str] = field(default_factory=set)
    menu_bg: Set[str] = field(default_factory=set)
    chars: Dict[str, Set[str]] = field(default_factory=dict)   # персонаж -> эмоции
    speakers: Set[str] = field(default_factory=set)


def collect_usage(p: Project) -> Usage:
    u = Usage()
    for b in p.blocks:
        for s in b.steps:
            d = s.data
            if s.kind == "bg" and d.get("asset"):
                u.bg.add(d["asset"])
            elif s.kind == "music" and d.get("asset"):
                u.music.add(d["asset"])
            elif s.kind in ("fx_on", "fx_off", "fx_once") and d.get("asset"):
                u.fx.add(d["asset"])
            elif s.kind == "show" and d.get("char"):
                u.chars.setdefault(d["char"], set()).add(d.get("emotion", ""))
            elif s.kind == "say" and d.get("who"):
                u.speakers.add(d["who"])
    m = p.menu
    if m.bg:
        u.menu_bg.add(m.bg)
    if m.music:
        u.music.add(m.music)
    for it in m.loading:
        if it.get("asset"):
            u.loading.add(it["asset"])
    for a in m.effects:
        u.fx.add(a)
    return u


def _name(p: Project, b) -> str:
    return b.title or b.id


def validate(p: Project) -> List[Issue]:
    out: List[Issue] = []
    tops = p.top_blocks()
    if not tops:
        out.append(Issue("error", tr("В проекте нет ни одного диалога. Создайте его на вкладке «Сценарий».")))
    for b in p.blocks:
        nm = _name(p, b)
        if not b.steps and not b.link_to:
            out.append(Issue("warn", tr("«{}»: пока пусто.").format(nm), b.id))
            continue
        kinds = [s.kind for s in b.steps]
        if "choice" in kinds and kinds.index("choice") != len(kinds) - 1:
            out.append(Issue("error", tr("«{}»: после вариантов ответа есть лишние шаги — они недостижимы.").format(nm), b.id))
        if b.link_to:
            tgt = p.block(b.link_to)
            if not tgt:
                out.append(Issue("error", tr("«{}»: связанный конечный блок удалён.").format(nm), b.id))
            elif tgt.id == b.id:
                out.append(Issue("error", tr("«{}»: блок связан сам с собой.").format(nm), b.id))
        saw_text = False
        for s in b.steps:
            d = s.data
            if s.kind == "say":
                if not d.get("text", "").strip():
                    out.append(Issue("warn", tr("«{}»: есть пустая фраза.").format(nm), b.id))
                else:
                    saw_text = True
                if d.get("who") and not p.get_char(d["who"]):
                    out.append(Issue("error", tr("«{}»: фразу говорит удалённый персонаж.").format(nm), b.id))
            elif s.kind in ("bg", "music", "fx_on", "fx_off", "fx_once"):
                a = p.find_asset(d.get("asset", ""))
                if not a:
                    out.append(Issue("error", tr("«{}»: используется удалённый ресурс.").format(nm), b.id))
                elif a.file and not p.abs(a.file).exists():
                    out.append(Issue("error", tr("«{}»: файл «{}» не найден на диске.").format(nm, a.name), b.id))
            elif s.kind in ("show", "hide"):
                c = p.get_char(d.get("char", ""))
                if not c:
                    out.append(Issue("error", tr("«{}»: используется удалённый персонаж.").format(nm), b.id))
                elif s.kind == "show":
                    rel = c.emotions.get(d.get("emotion", ""))
                    if not rel:
                        out.append(Issue("error", tr("«{}»: у персонажа «{}» нет эмоции «{}».").format(nm, c.name, d.get("emotion", "")), b.id))
                    elif not p.abs(rel).exists():
                        out.append(Issue("error", tr("«{}»: файл эмоции «{}» не найден.").format(nm, c.name), b.id))
            elif s.kind == "choice":
                opts = d.get("options", [])
                if len(opts) < 2:
                    out.append(Issue("error", tr("«{}»: для выбора нужно минимум 2 варианта.").format(nm), b.id))
                for o in opts:
                    if not o.get("text", "").strip():
                        out.append(Issue("warn", tr("«{}»: у одного из вариантов ответа нет текста.").format(nm), b.id))
                    if not p.block(o.get("block", "")):
                        out.append(Issue("error", tr("«{}»: вариант ответа ведёт в никуда.").format(nm), b.id))
        if not saw_text and b.steps and "choice" not in kinds:
            out.append(Issue("info", tr("«{}»: в блоке нет ни одной фразы.").format(nm), b.id))
    m = p.menu
    for aid in [m.bg, m.music] + [i.get("asset", "") for i in m.loading] + list(m.effects):
        if aid:
            a = p.find_asset(aid)
            if not a:
                out.append(Issue("error", tr("В меню игры используется удалённый ресурс.")))
            elif a.file and not p.abs(a.file).exists():
                out.append(Issue("error", tr("В меню игры не найден файл «{}».").format(a.name)))
    if p.style.font_file and not p.abs(p.style.font_file).exists():
        out.append(Issue("error", tr("Файл шрифта не найден.")))
    last = tops[-1] if tops else None
    if last and not (last.steps and last.steps[-1].kind in ("ending", "choice")):
        out.append(Issue("info", tr("Последний диалог закончится выходом в главное меню.")))
    return out
