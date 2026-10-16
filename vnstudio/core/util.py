"""Мелкие утилиты ядра (без зависимости от Qt)."""
from __future__ import annotations

import os
import re
import struct
import uuid
import zlib
from pathlib import Path

_RU = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}

# Слова, которые нельзя использовать как имена в Ren'Py-командах show/scene
RESERVED = {
    "at", "as", "behind", "onlayer", "zorder", "with", "expression", "in", "transform",
    "show", "hide", "scene", "image", "menu", "if", "else", "elif", "python", "label",
    "jump", "call", "return", "pass", "define", "default", "init", "screen", "style",
    "play", "stop", "queue", "pause", "window", "nvl", "while", "for", "True", "False",
    "None", "thought", "narrator", "centered", "extend", "black", "bg", "fade",
}


def slug(text: str, default: str = "x") -> str:
    """Безопасное ASCII-имя из любого текста (русский транслитерируется)."""
    out = []
    for ch in (text or "").lower():
        if ch in _RU:
            out.append(_RU[ch])
        elif ch.isascii() and ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    s = re.sub(r"_+", "_", "".join(out)).strip("_")
    if not s:
        s = default
    if s[0].isdigit():
        s = "n" + s
    return s


class Namer:
    """Выдаёт уникальные имена-идентификаторы."""

    def __init__(self) -> None:
        self.used: set = set()

    def get(self, text: str, default: str = "x", prefix: str = "") -> str:
        base = prefix + slug(text, default)
        if base in RESERVED:
            base += "_x"
        name, i = base, 2
        while name in self.used:
            name = f"{base}_{i}"
            i += 1
        self.used.add(name)
        return name


def short_id() -> str:
    return uuid.uuid4().hex[:8]


def hex_alpha(color: str, pct) -> str:
    """'#rrggbb' + прозрачность в процентах -> '#rrggbbaa' (формат Ren'Py)."""
    c = (color or "#000000").lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    c = (c + "000000")[:6]
    try:
        pct = float(pct)
    except (TypeError, ValueError):
        pct = 100.0
    aa = round(max(0.0, min(100.0, pct)) * 255 / 100)
    return f"#{c.lower()}{aa:02x}"


def atomic_write(path, text: str) -> None:
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------- картинки
def _jpeg_size(f):
    f.seek(2)
    while True:
        b = f.read(1)
        while b and b != b"\xff":
            b = f.read(1)
        while b == b"\xff":
            b = f.read(1)
        if not b:
            return None
        m = b[0]
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
            continue
        if m == 0xD9:
            return None
        seg = f.read(2)
        if len(seg) < 2:
            return None
        ln = struct.unpack(">H", seg)[0]
        if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
            data = f.read(5)
            if len(data) < 5:
                return None
            h, w = struct.unpack(">HH", data[1:5])
            return w, h
        f.seek(ln - 2, 1)


def image_size(path):
    """(ширина, высота) для PNG/JPEG/GIF/BMP/WEBP или None. Без внешних библиотек."""
    try:
        with open(path, "rb") as f:
            head = f.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n" and len(head) >= 24:
                return struct.unpack(">II", head[16:24])
            if head[:6] in (b"GIF87a", b"GIF89a") and len(head) >= 10:
                return struct.unpack("<HH", head[6:10])
            if head[:2] == b"BM" and len(head) >= 26:
                w, h = struct.unpack("<ii", head[18:26])
                return abs(w), abs(h)
            if head[:4] == b"RIFF" and head[8:12] == b"WEBP" and len(head) >= 30:
                kind = head[12:16]
                if kind == b"VP8 ":
                    w = struct.unpack("<H", head[26:28])[0] & 0x3FFF
                    h = struct.unpack("<H", head[28:30])[0] & 0x3FFF
                    return w, h
                if kind == b"VP8L":
                    bits = struct.unpack("<I", head[21:25])[0]
                    return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
                if kind == b"VP8X":
                    w = int.from_bytes(head[24:27], "little") + 1
                    h = int.from_bytes(head[27:30], "little") + 1
                    return w, h
            if head[:2] == b"\xff\xd8":
                return _jpeg_size(f)
    except Exception:
        return None
    return None


def write_png(path, w: int, h: int, rgba) -> None:
    """Записывает RGBA (8 бит) в PNG."""
    stride = w * 4
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
           + chunk(b"IEND", b""))
    Path(path).write_bytes(png)
