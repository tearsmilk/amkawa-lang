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
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_vault() -> Path:
    return Path.home() / "Documents" / "Milkys Hub"


def resource_path(*parts: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base).joinpath(*parts)
    return Path(__file__).resolve().parent.parent.joinpath(*parts)


class Settings(dict):
    DEFAULTS = {"vault": None, "theme": "system", "mode": "split", "open_tabs": [], "right_panel": True,
                "font_size": 14, "recent_vaults": []}

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
