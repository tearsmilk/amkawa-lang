"""Where the app keeps its data (models, settings, downloads)."""
import os
import sys
from pathlib import Path

from . import APP_ID, LEGACY_ID


def data_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / APP_ID
    legacy = base / LEGACY_ID  # Amkawa Voice → Каппа: keep the models and settings
    if not path.exists() and legacy.is_dir():
        try:
            legacy.rename(path)
        except OSError:
            pass
    path.mkdir(parents=True, exist_ok=True)
    return path


def models_dir() -> Path:
    path = data_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = data_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> Path:
    return data_dir() / "settings.json"


def resource_path(*parts: str) -> Path:
    """Path to a file shipped with the app (works inside the PyInstaller bundle)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base).joinpath(*parts)
    return Path(__file__).resolve().parent.parent.joinpath(*parts)
