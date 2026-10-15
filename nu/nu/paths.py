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


def default_shell():
    shell = os.environ.get("SHELL")
    if shell and Path(shell).exists():
        return shell
    for cand in ("/bin/zsh", "/bin/bash", "/bin/sh"):
        if Path(cand).exists():
            return cand
    return "/bin/sh"


class Settings(dict):
    DEFAULTS = {
        "theme": "system", "font_family": "", "font_size": 13, "terminal_font_size": 12, "tab_size": 4,
        "insert_spaces": True, "word_wrap": False, "indent_guides": True, "autosave": False,
        "auto_close": True, "autocomplete": True, "trim_trailing": False, "final_newline": True,
        "folder": None, "open_files": [], "recent": [], "sidebar": True, "panel": False,
        "shell": "", "exclude": [".git", ".DS_Store", "__pycache__", ".mypy_cache", ".pytest_cache", ".idea"],
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
