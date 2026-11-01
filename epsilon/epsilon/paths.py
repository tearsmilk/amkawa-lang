"""App data locations (settings live outside the vault; the vault is a plain folder)."""
import json
import os
import sys
from pathlib import Path

from . import APP_ID


def data_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / APP_ID
    legacy = base / "MilkysHub"  # the app was called Milkys Hub before: keep its settings
    if not path.exists() and legacy.is_dir():
        legacy.rename(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_vault() -> Path:
    legacy = Path.home() / "Documents" / "Milkys Hub"
    if legacy.is_dir() and not (Path.home() / "Documents" / "Epsilon").exists():
        return legacy
    return Path.home() / "Documents" / "Epsilon"


def resource_path(*parts: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base).joinpath(*parts)
    return Path(__file__).resolve().parent.parent.joinpath(*parts)


class Settings(dict):
    DEFAULTS = {"vault": None, "theme": "system", "mode": "split", "open_tabs": [], "right_panel": True,
                "font_size": 14, "recent_vaults": [], "delete_to_system_trash": False}

    def __init__(self):
        super().__init__(self.DEFAULTS)
        self.file = data_dir() / "settings.json"
        try:
            self.update(json.loads(self.file.read_text("utf-8")))
        except Exception:
            pass

    def save(self):
        try:
            self.file.write_text(json.dumps(self, ensure_ascii=False, indent=2), "utf-8")
        except Exception:
            pass
