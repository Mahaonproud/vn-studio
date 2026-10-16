"""Настройки приложения (хранятся в JSON в папке конфигурации пользователя)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

APP_NAME = "VN Studio"


def config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    d = base / "VNStudio"
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_projects_dir() -> str:
    return str(Path.home() / "VNStudio Projects")


@dataclass
class Settings:
    language: str = "ru"        # язык интерфейса: ru | en
    theme: str = "dark"         # dark | light
    volume: int = 70            # громкость предпрослушивания музыки, %
    autosave: bool = True
    autosave_minutes: int = 3
    spell_lang: str = "ru"      # язык проверки орфографии: ru | en
    projects_dir: str = ""

    def projects_path(self) -> Path:
        p = Path(self.projects_dir or default_projects_dir())
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def load(cls) -> "Settings":
        s = cls()
        try:
            data = json.loads((config_dir() / "settings.json").read_text("utf-8"))
            names = {f.name for f in fields(cls)}
            for k, v in data.items():
                if k in names:
                    setattr(s, k, v)
        except Exception:
            pass
        if s.language not in ("ru", "en"):
            s.language = "ru"
        if s.theme not in ("dark", "light"):
            s.theme = "dark"
        s.volume = max(0, min(100, int(s.volume)))
        s.autosave_minutes = max(1, min(60, int(s.autosave_minutes)))
        return s

    def save(self) -> None:
        try:
            (config_dir() / "settings.json").write_text(
                json.dumps(asdict(self), ensure_ascii=False, indent=1), "utf-8")
        except Exception:
            pass
