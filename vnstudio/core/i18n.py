"""Простой перевод: в коде используется русский текст, для английского есть словарь EN."""
from __future__ import annotations

from .en import EN

_lang = "ru"


def set_language(lang: str) -> None:
    global _lang
    _lang = lang if lang in ("ru", "en") else "ru"


def get_language() -> str:
    return _lang


def tr(text: str) -> str:
    if _lang == "en":
        return EN.get(text, text)
    return text
