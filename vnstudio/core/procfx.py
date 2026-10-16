"""Встроенные эффекты, которые рисуются кодом (собственные, без авторских прав)."""
from __future__ import annotations

import math
import random
from pathlib import Path

from .util import write_png

W, H = 960, 540  # в игре растягивается на весь экран


def vignette(path, strength: float = 0.92) -> None:
    cx, cy = (W - 1) / 2, (H - 1) / 2
    xs = [((x - cx) / cx) ** 2 for x in range(W)]
    buf = bytearray(W * H * 4)
    for y in range(H):
        ny2 = ((y - cy) / cy) ** 2
        row = bytearray(W)
        for x in range(W):
            d = math.sqrt((xs[x] + ny2) / 2.0)
            t = (d - 0.38) / 0.62
            if t > 0:
                t = min(1.0, t)
                row[x] = int(255 * strength * (t * t * (3 - 2 * t)))
        buf[y * W * 4 + 3:(y + 1) * W * 4:4] = row
    write_png(path, W, H, buf)


def grain(path, seed: int = 7, alpha: int = 44) -> None:
    rnd = random.Random(seed)
    g = rnd.randbytes(W * H)
    buf = bytearray(W * H * 4)
    buf[0::4] = g
    buf[1::4] = g
    buf[2::4] = g
    buf[3::4] = bytes([alpha]) * (W * H)
    write_png(path, W, H, buf)


def blood(path, seed: int = 13) -> None:
    rnd = random.Random(seed)
    mask = bytearray(W * H)

    def disc(cx: float, cy: float, r: float) -> None:
        x0, x1 = max(0, int(cx - r - 1)), min(W - 1, int(cx + r + 1))
        y0, y1 = max(0, int(cy - r - 1)), min(H - 1, int(cy + r + 1))
        for y in range(y0, y1 + 1):
            dy = y - cy
            base = y * W
            for x in range(x0, x1 + 1):
                a = r + 0.5 - math.hypot(x - cx, dy)
                if a > 0:
                    v = 255 if a >= 1 else int(a * 255)
                    if v > mask[base + x]:
                        mask[base + x] = v

    def blob(cx: float, cy: float, r: float) -> None:
        disc(cx, cy, r)
        for _ in range(rnd.randint(5, 10)):
            a = rnd.uniform(0, 2 * math.pi)
            dist = r * rnd.uniform(0.6, 1.4)
            disc(cx + math.cos(a) * dist, cy + math.sin(a) * dist, r * rnd.uniform(0.25, 0.6))
        for _ in range(rnd.randint(8, 18)):
            a = rnd.uniform(0, 2 * math.pi)
            dist = r * rnd.uniform(1.4, 3.6)
            disc(cx + math.cos(a) * dist, cy + math.sin(a) * dist, rnd.uniform(1.2, 4.5))

    def drip(x: float, y: float, length: float, w0: float) -> None:
        steps = max(1, int(length / 2))
        for i in range(steps):
            t = i / steps
            disc(x + math.sin(i * 0.3) * 0.6, y + i * 2, max(1.0, w0 * (1 - 0.5 * t)))
        disc(x, y + length, w0 * 1.3)

    anchors = [(60, 50), (W - 70, 60), (40, H - 80), (W - 60, H - 60),
               (W * 0.5, 30), (W * 0.12, H * 0.5), (W * 0.9, H * 0.45)]
    for ax, ay in anchors:
        ax += rnd.uniform(-30, 30)
        ay += rnd.uniform(-20, 20)
        r = rnd.uniform(24, 58)
        blob(ax, ay, r)
        for _ in range(rnd.randint(1, 3)):
            drip(ax + rnd.uniform(-r * 0.6, r * 0.6), ay + r * 0.5,
                 rnd.uniform(40, 170), rnd.uniform(2.0, 4.5))

    buf = bytearray(W * H * 4)
    n = W * H
    buf[0::4] = bytes([150]) * n
    buf[1::4] = bytes([4]) * n
    buf[2::4] = bytes([14]) * n
    buf[3::4] = bytes(int(m * 0.93) for m in mask)
    write_png(path, W, H, buf)


# key, имя (рус.), тип, файл-генератор / параметры
BUILTIN = [
    {"key": "vignette", "name": "Виньетка", "kind": "image", "file": "builtin_vignette.png", "gen": vignette},
    {"key": "blood", "name": "Кровавые брызги", "kind": "image", "file": "builtin_blood.png", "gen": blood},
    {"key": "grain", "name": "Зерно (плёнка)", "kind": "image", "file": "builtin_grain.png", "gen": grain},
    {"key": "tint_red", "name": "Красный оттенок", "kind": "solid", "params": {"color": "#b00010", "alpha": 28}},
    {"key": "darken", "name": "Затемнение", "kind": "solid", "params": {"color": "#000000", "alpha": 45}},
    {"key": "shake", "name": "Тряска экрана", "kind": "shake"},
    {"key": "flash", "name": "Вспышка", "kind": "flash"},
]


def generate_file(item: dict, folder) -> Path:
    path = Path(folder) / item["file"]
    if not path.exists():
        item["gen"](path)
    return path
