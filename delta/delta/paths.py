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
        "theme": "system", "recent": [], "last_dir": "", "new_width": 1240, "new_height": 1754, "new_dpi": 150,
        "new_background": "#FFFFFF", "brush": "Карандаш", "brushes": {}, "swatches": [], "fill_tolerance": 24,
        "fill_all_layers": False, "fill_expand": 1, "shape_fill": False, "gradient_radial": False,
        "gradient_to_transparent": False, "tone_spacing": 8, "tone_size": 50, "tone_angle": 45, "panel_width": 6,
        "panel_gutter": 24, "text_font": "", "text_size": 36, "text_vertical": False, "export_scale": 1,
        "dock_state": "", "onion": False,
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
