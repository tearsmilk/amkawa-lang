"""Settings, folders and resources."""
import json
import os
import sys
from pathlib import Path

from . import APP_ID

# hotkeys: {"vk": macOS virtual key code, "key": Qt key, "mods": Qt modifier bits, "text": label}
# Qt on macOS: ControlModifier = ⌘, MetaModifier = ⌃, AltModifier = ⌥
_CMD, _SHIFT = 0x04000000, 0x02000000


def _hk(vk, key, text):
    return {"vk": vk, "key": key, "mods": _CMD | _SHIFT, "text": text}


DEFAULT_HOTKEYS = {
    "shot_region": _hk(0x13, 0x32, "⇧⌘2"),
    "shot_screen": _hk(0x12, 0x31, "⇧⌘1"),
    "rec_region": _hk(0x1C, 0x38, "⇧⌘8"),
    "rec_screen": _hk(0x19, 0x39, "⇧⌘9"),
    "replay_save": _hk(0x1D, 0x30, "⇧⌘0"),
    "replay_toggle": _hk(0x1B, 0x2D, "⇧⌘-"),
    "show": None,
}

HOTKEY_TITLES = {
    "shot_region": "Снимок области",
    "shot_screen": "Снимок экрана",
    "rec_region": "Запись области (повтор — стоп)",
    "rec_screen": "Запись экрана (повтор — стоп)",
    "replay_save": "Сохранить откат",
    "replay_toggle": "Включить / выключить откат",
    "show": "Показать Гамму",
}


def data_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / APP_ID
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir(*parts) -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    path = base.joinpath(APP_ID, *parts)
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_path(*parts: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base).joinpath(*parts)
    return Path(__file__).resolve().parent.parent.joinpath(*parts)


def default_video_dir() -> str:
    return str(Path.home() / ("Movies" if sys.platform == "darwin" else "Videos") / "Гамма")


def default_shot_dir() -> str:
    return str(Path.home() / "Pictures" / "Гамма")


class Settings(dict):
    DEFAULTS = {
        "theme": "system",
        "video_dir": "", "shot_dir": "", "video_format": "mp4", "shot_format": "png", "jpg_quality": 92,
        "fps": 30, "quality": 2, "encoder": "hw", "max_height": 0, "cursor": True, "clicks": False,
        "countdown": 3, "hide_windows": True, "minimize": True,
        "audio": "none", "mic_device": "", "system_device": "",
        "clipboard": True, "preview": True, "shutter": True, "shot_delay": 0, "screen_mode": "cursor",
        "instant_shot": True,
        "replay_on_start": False, "replay_before": 5.0, "replay_after": 1.0, "replay_screen": 0,
        "hotkeys": {},
    }

    def __init__(self, file=None):
        super().__init__(json.loads(json.dumps(self.DEFAULTS)))
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

    def folder(self, kind) -> Path:
        """kind = "video" | "shot"; created on demand."""
        raw = self.get(kind + "_dir") or (default_video_dir() if kind == "video" else default_shot_dir())
        path = Path(raw).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            path = Path.home()
        return path

    def hotkey(self, action):
        hk = self.get("hotkeys", {})
        if action in hk:
            return hk[action]
        return DEFAULT_HOTKEYS.get(action)

    def hotkeys(self):
        return {a: self.hotkey(a) for a in HOTKEY_TITLES}
