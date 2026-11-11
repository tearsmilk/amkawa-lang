"""Settings and resources."""
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


def resource_path(*parts: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base).joinpath(*parts)
    return Path(__file__).resolve().parent.parent.joinpath(*parts)


class Settings(dict):
    DEFAULTS = {
        "theme": "system", "recent": [], "palette": "DB32", "grid": False, "pixel_grid": True, "grid_size": 16,
        "onion": False, "onion_prev": 1, "onion_next": 1, "brush_size": 1, "brush_shape": "square",
        "pixel_perfect": False, "contiguous": True, "tolerance": 0, "shape_fill": False, "new_width": 32,
        "new_height": 32, "new_background": "transparent", "last_dir": "", "export_scale": 1, "panels": True,
        "checker": True,
    }

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

    def add_recent(self, path):
        path = str(path)
        self["recent"] = [path] + [p for p in self.get("recent", []) if p != path][:11]
        self.save()
