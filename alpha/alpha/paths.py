"""Settings and resources."""
import json
import os
import sys
from pathlib import Path

from . import APP_ID


def data_dir() -> Path:
    override = os.environ.get("ALPHA_DATA")
    if override:
        base = Path(override)
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_ID
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_ID
    base.mkdir(parents=True, exist_ok=True)
    return base


def resource_path(*parts: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base).joinpath(*parts)
    return Path(__file__).resolve().parent.parent.joinpath(*parts)


class Settings(dict):
    DEFAULTS = {
        "theme": "system", "last_board": "", "notify": True, "soon_hours": 24, "week_monday": True,
        "my_name": "Я", "compact": False,
    }

    def __init__(self, file=None):
        super().__init__(self.DEFAULTS)
        self.file = Path(file) if file else data_dir() / "settings.json"
        try:
            self.update(json.loads(self.file.read_text("utf-8")))
        except Exception:
            pass

    def save(self):
        try:
            self.file.write_text(json.dumps(self, ensure_ascii=False, indent=2), "utf-8")
        except Exception:
            pass
