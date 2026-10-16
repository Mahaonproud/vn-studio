"""Проверка орфографии. Использует pyspellchecker (pip install pyspellchecker)."""
from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional, Set, Tuple

from .i18n import tr

WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё]+(?:[-'’][A-Za-zА-Яа-яЁё]+)*")

_cache: Dict[str, "Speller"] = {}


class Speller:
    def __init__(self, lang: str = "ru") -> None:
        self.lang = lang
        self.sp = None
        self.error = ""
        try:
            from spellchecker import SpellChecker  # type: ignore
            self.sp = SpellChecker(language=lang)
        except Exception as e:  # библиотека не установлена или нет словаря
            self.error = str(e) or e.__class__.__name__

    @property
    def available(self) -> bool:
        return self.sp is not None

    def known(self, word: str) -> bool:
        if not self.sp:
            return True
        w = word.lower()
        if w in self.sp:
            return True
        if "ё" in w and w.replace("ё", "е") in self.sp:
            return True
        if "-" in w or "'" in w or "’" in w:
            parts = [x for x in re.split(r"[-'’]", w) if x]
            return bool(parts) and all((x in self.sp) or len(x) < 2 for x in parts)
        return False

    def suggestions(self, word: str, limit: int = 5) -> List[str]:
        if not self.sp:
            return []
        try:
            cands = self.sp.candidates(word.lower()) or set()
        except Exception:
            cands = set()
        cands = {c for c in cands if c and c != word.lower()}

        def freq(c: str) -> float:
            try:
                return float(self.sp.word_usage_frequency(c))
            except Exception:
                try:
                    return float(self.sp[c])
                except Exception:
                    return 0.0

        ordered = sorted(cands, key=lambda c: (-freq(c), c))[:limit]
        return [_match_case(word, c) for c in ordered]


def _match_case(original: str, cand: str) -> str:
    if original.isupper() and len(original) > 1:
        return cand.upper()
    if original[:1].isupper():
        return cand[:1].upper() + cand[1:]
    return cand


def get_speller(lang: str) -> Speller:
    if lang not in _cache:
        _cache[lang] = Speller(lang)
    return _cache[lang]


class SpellContext:
    """Связывает проверку орфографии с проектом: слова-исключения, имена персонажей."""

    def __init__(self, project, lang: str,
                 on_ignore: Optional[Callable[[], None]] = None) -> None:
        self.project = project
        self.speller = get_speller(lang)
        self.on_ignore = on_ignore

    def set_lang(self, lang: str) -> None:
        self.speller = get_speller(lang)

    @property
    def status(self) -> str:
        if self.speller.available:
            return ""
        return tr("Проверка орфографии выключена: установите пакет pyspellchecker "
                  "(команда: pip install pyspellchecker).")

    def _skip(self) -> Set[str]:
        names: Set[str] = set(w.lower() for w in self.project.ignored)
        for c in self.project.characters:
            for part in WORD_RE.findall(c.name):
                names.add(part.lower())
        return names

    def errors(self, text: str) -> List[Tuple[int, int, str]]:
        if not self.speller.available:
            return []
        skip = self._skip()
        out = []
        for m in WORD_RE.finditer(text):
            w = m.group(0)
            if len(w) < 2 or w.lower() in skip:
                continue
            if not self.speller.known(w):
                out.append((m.start(), m.end(), w))
        return out

    def suggest(self, word: str) -> List[str]:
        return self.speller.suggestions(word)

    def ignore_word(self, word: str) -> None:
        lw = word.lower()
        if lw not in self.project.ignored:
            self.project.ignored.append(lw)
        if self.on_ignore:
            self.on_ignore()
