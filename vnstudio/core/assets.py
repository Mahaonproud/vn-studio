"""Добавление, удаление и массовый импорт ассетов проекта."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Dict, Optional

from .i18n import tr
from .model import ASSET_CATS, CAT_PREFIX, CHAR_COLORS, Asset, Character, Project
from .procfx import BUILTIN, generate_file
from .util import slug

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
AUDIO_EXT = {".ogg", ".mp3", ".wav", ".opus", ".flac"}
FONT_EXT = {".ttf", ".otf"}

CAT_EXT = {"backgrounds": IMAGE_EXT, "effects": IMAGE_EXT, "loading": IMAGE_EXT,
           "menu_bg": IMAGE_EXT, "music": AUDIO_EXT}

# как могут называться папки при массовой загрузке
ALIASES = {
    "backgrounds": {"backgrounds", "background", "bg", "backs", "фоны", "фон"},
    "effects": {"effects", "effect", "fx", "эффекты", "эффект"},
    "music": {"music", "audio", "sounds", "songs", "музыка", "песни", "аудио"},
    "loading": {"loading", "loading_screens", "loadingscreens", "splash", "загрузочные",
                "загрузочные экраны", "загрузка"},
    "menu_bg": {"menu", "menu_bg", "screens", "задние экраны", "экраны", "меню", "экраны меню"},
    "characters": {"characters", "character", "chars", "персонажи", "герои"},
}

Progress = Optional[Callable[[int, int, str], None]]


def _copy_in(project: Project, sub: str, src: Path, stem: str) -> str:
    dest_dir = project.abs(f"assets/{sub}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{stem}{src.suffix.lower()}"
    dest = dest_dir / name
    i = 2
    while dest.exists():
        dest = dest_dir / f"{stem}_{i}{src.suffix.lower()}"
        i += 1
    shutil.copy2(src, dest)
    return f"assets/{sub}/{dest.name}"


def _check_ext(src: Path, allowed) -> None:
    if src.suffix.lower() not in allowed:
        raise ValueError(tr("Неподдерживаемый формат файла: {}").format(src.name))


def import_asset(project: Project, cat: str, src, name: Optional[str] = None) -> Asset:
    src = Path(src)
    _check_ext(src, CAT_EXT[cat])
    aid = project.new_id(CAT_PREFIX[cat])
    kind = "image" if cat == "effects" else "file"
    rel = _copy_in(project, cat, src, f"{aid}_{slug(src.stem)}")
    a = Asset(aid, name or src.stem, rel, kind)
    project.assets[cat].append(a)
    return a


def remove_asset(project: Project, aid: str) -> None:
    for lst in project.assets.values():
        for a in list(lst):
            if a.id == aid:
                if a.file:
                    try:
                        project.abs(a.file).unlink()
                    except OSError:
                        pass
                lst.remove(a)
                return


def add_character(project: Project, name: str, color: Optional[str] = None) -> Character:
    cid = project.new_id("ch")
    n = len(project.characters)
    c = Character(cid, name.strip() or tr("Персонаж"), color or CHAR_COLORS[n % len(CHAR_COLORS)])
    project.characters.append(c)
    return c


def add_emotion(project: Project, char: Character, emotion: str, src) -> None:
    src = Path(src)
    _check_ext(src, IMAGE_EXT)
    emotion = emotion.strip() or tr("обычная")
    if emotion in char.emotions:
        old = char.emotions[emotion]
        try:
            project.abs(old).unlink()
        except OSError:
            pass
    char.emotions[emotion] = _copy_in(project, "characters", src, f"{char.id}_{slug(emotion)}")


def remove_emotion(project: Project, char: Character, emotion: str) -> None:
    rel = char.emotions.pop(emotion, None)
    if rel:
        try:
            project.abs(rel).unlink()
        except OSError:
            pass


def rename_emotion(project: Project, char: Character, old: str, new: str) -> None:
    """Переименовывает эмоцию и обновляет все шаги сценария, где она использована."""
    if old not in char.emotions or new in char.emotions:
        return
    char.emotions = {(new if k == old else k): v for k, v in char.emotions.items()}
    for b in project.blocks:
        for s in b.steps:
            if s.kind == "show" and s.data.get("char") == char.id and s.data.get("emotion") == old:
                s.data["emotion"] = new


def remove_character(project: Project, cid: str) -> None:
    c = project.get_char(cid)
    if not c:
        return
    for rel in list(c.emotions.values()):
        try:
            project.abs(rel).unlink()
        except OSError:
            pass
    project.characters.remove(c)


def import_font(project: Project, src) -> str:
    src = Path(src)
    _check_ext(src, FONT_EXT)
    return _copy_in(project, "fonts", src, f"font_{slug(src.stem)}")


def add_builtin_effects(project: Project) -> int:
    """Добавляет встроенные эффекты (если ещё не добавлены). Возвращает сколько добавлено."""
    have = {a.params.get("builtin") for a in project.assets["effects"]}
    folder = project.abs("assets/effects")
    folder.mkdir(parents=True, exist_ok=True)
    added = 0
    for item in BUILTIN:
        if item["key"] in have:
            continue
        aid = project.new_id("fx")
        params = dict(item.get("params", {}))
        params["builtin"] = item["key"]
        rel = ""
        if item.get("gen"):
            generate_file(item, folder)
            rel = f"assets/effects/{item['file']}"
        project.assets["effects"].append(Asset(aid, tr(item["name"]), rel, item["kind"], params))
        added += 1
    return added


# ------------------------------------------------------------ массовый импорт
def _files(folder: Path, exts):
    return sorted(f for f in folder.rglob("*") if f.is_file() and f.suffix.lower() in exts)


def bulk_import(project: Project, folder, progress: Progress = None) -> Dict[str, int]:
    """Загружает всё из папки, внутри которой лежат подпапки «фоны», «эффекты», «музыка» и т.д."""
    folder = Path(folder)
    summary = {c: 0 for c in (*ASSET_CATS, "characters")}
    summary["skipped"] = 0
    plan = []
    for sub in sorted(p for p in folder.iterdir() if p.is_dir()):
        key = sub.name.strip().lower()
        cat = next((c for c, al in ALIASES.items() if key in al), None)
        if cat:
            plan.append((cat, sub))
    if not plan:
        raise ValueError(tr("В выбранной папке не найдены подпапки «фоны», «эффекты», «музыка», "
                            "«загрузочные», «экраны», «персонажи». Создайте их и положите туда файлы "
                            "или добавляйте файлы по одной категории кнопкой «Добавить ещё»."))
    jobs = []
    for cat, sub in plan:
        if cat == "characters":
            jobs.append((cat, sub, None))
        else:
            for f in _files(sub, CAT_EXT[cat]):
                jobs.append((cat, sub, f))
    total = len(jobs) or 1
    for i, (cat, sub, f) in enumerate(jobs):
        if progress:
            progress(i, total, sub.name)
        if cat == "characters":
            _bulk_characters(project, sub, summary)
            continue
        if any(a.name == f.stem for a in project.assets[cat]):
            summary["skipped"] += 1
            continue
        import_asset(project, cat, f)
        summary[cat] += 1
    if progress:
        progress(total, total, "")
    return summary


def _bulk_characters(project: Project, folder: Path, summary: Dict[str, int]) -> None:
    for item in sorted(folder.iterdir()):
        if item.is_dir():
            char = next((c for c in project.characters if c.name == item.name), None)
            if char is None:
                char = add_character(project, item.name)
                summary["characters"] += 1
            for f in _files(item, IMAGE_EXT):
                if f.stem in char.emotions:
                    summary["skipped"] += 1
                else:
                    add_emotion(project, char, f.stem, f)
        elif item.suffix.lower() in IMAGE_EXT:
            if any(c.name == item.stem for c in project.characters):
                summary["skipped"] += 1
                continue
            char = add_character(project, item.stem)
            add_emotion(project, char, tr("обычная"), item)
            summary["characters"] += 1
