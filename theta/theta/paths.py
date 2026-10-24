"""Settings and folders (data in ~/Library/Application Support/Theta, override with THETA_DATA)."""
import json
import os
import sys
from pathlib import Path

from . import APP_ID


def data_dir() -> Path:
    override = os.environ.get("THETA_DATA")
    if override:
        base = Path(override)
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_ID
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_ID
    base.mkdir(parents=True, exist_ok=True)
    return base


def cache_dir() -> Path:
    p = data_dir() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def resource_path(*parts: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base).joinpath(*parts)
    return Path(__file__).resolve().parent.parent.joinpath(*parts)


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text("utf-8"))
    except Exception:
        return default


def save_json(path, data):
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, path)


class Settings(dict):
    DEFAULTS = {
        "theme": "system", "accent": "#D97757", "serif_headings": True, "sidebar_hidden": False,
        "nickname": "", "mapillary_token": "", "cache_mb": 500, "source": "mapillary",
        "map": "world", "mode": "classic", "time_limit": 0, "no_move": False, "no_pan": False, "no_zoom": False,
        "map_size": 1, "map_pinned": False,
    }

    def __init__(self, file=None):
        super().__init__(self.DEFAULTS)
        self.file = Path(file) if file else data_dir() / "settings.json"
        self.update(load_json(self.file, {}))

    def save(self):
        try:
            save_json(self.file, dict(self))
        except OSError:
            pass
