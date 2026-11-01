"""Attachments: file kinds, sizes and preview thumbnails (cached in .epsilon/thumbs).

Thumbnails of videos, PDFs and documents come from macOS Quick Look (`qlmanage -t`), made in a
background thread; images and GIFs are shown directly and need none.
"""
import hashlib
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".svg", ".heic", ".tiff", ".tif"}
GIF_EXT = {".gif"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".3gp"}
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".opus", ".aiff", ".aif"}
PDF_EXT = {".pdf"}
DOC_EXT = {".doc", ".docx", ".pages", ".rtf", ".txt", ".odt", ".xls", ".xlsx", ".numbers", ".csv",
           ".ppt", ".pptx", ".key", ".epub"}
ARCHIVE_EXT = {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".dmg"}

# kind → (label, icon)
KINDS = {
    "image": ("Фото", "🖼"), "gif": ("GIF", "✨"), "video": ("Видео", "🎬"), "audio": ("Аудио", "🎵"),
    "pdf": ("PDF", "📕"), "doc": ("Документ", "📄"), "archive": ("Архив", "🗜"), "file": ("Файл", "📎"),
}
# what the media viewer can show inside the app
VIEWABLE = {"image", "gif", "video", "audio"}
# filters of the attach dialog and the Files section
FILTERS = [
    ("Все", None), ("Фото", {"image"}), ("GIF", {"gif"}), ("Видео", {"video"}), ("Аудио", {"audio"}),
    ("Документы", {"pdf", "doc"}), ("Другое", {"archive", "file"}),
]


def kind_of(path):
    ext = Path(path).suffix.lower()
    for kind, exts in (("image", IMAGE_EXT), ("gif", GIF_EXT), ("video", VIDEO_EXT), ("audio", AUDIO_EXT),
                       ("pdf", PDF_EXT), ("doc", DOC_EXT), ("archive", ARCHIVE_EXT)):
        if ext in exts:
            return kind
    return "file"


def label_of(path):
    return KINDS[kind_of(path)][0]


def icon_of(path):
    return KINDS[kind_of(path)][1]


def human_size(n):
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if n < 1024 or unit == "ГБ":
            return f"{n:.0f} {unit}" if unit == "Б" else f"{n:.1f} {unit}"
        n /= 1024


def describe(path):
    """«Видео · MP4 · 12.4 МБ»"""
    path = Path(path)
    parts = [label_of(path)]
    if path.suffix:
        parts.append(path.suffix[1:].upper())
    try:
        parts.append(human_size(path.stat().st_size))
    except OSError:
        pass
    return " · ".join(dict.fromkeys(parts))


def dialog_filters():
    """Name filters for QFileDialog."""
    groups = [("Все файлы", ["*"]),
              ("Фото и GIF", sorted(IMAGE_EXT | GIF_EXT)), ("Видео", sorted(VIDEO_EXT)),
              ("Аудио", sorted(AUDIO_EXT)), ("Документы", sorted(PDF_EXT | DOC_EXT))]
    out = []
    for name, exts in groups:
        pats = " ".join(e if e == "*" else "*" + e for e in exts)
        out.append(f"{name} ({pats})")
    return ";;".join(out)


# ---------------------------------------------------------------------- thumbnails
class Thumbnails:
    """Quick Look previews for non-image attachments. `get()` never blocks: it returns a cached PNG
    or None and starts making one; `on_ready(path)` is then called from a worker thread."""

    SIZE = 360

    def __init__(self, cache_dir, on_ready=None):
        self.dir = Path(cache_dir)
        self.on_ready = on_ready
        self._pending = set()
        self._failed = set()
        self._lock = threading.Lock()

    @staticmethod
    def supported():
        return sys.platform == "darwin" and shutil.which("qlmanage") is not None

    def _key(self, path):
        st = path.stat()
        return hashlib.sha1(f"{path}|{st.st_mtime_ns}|{st.st_size}|{self.SIZE}".encode()).hexdigest()

    def cached(self, path):
        try:
            thumb = self.dir / f"{self._key(Path(path))}.png"
        except OSError:
            return None
        return thumb if thumb.exists() else None

    def get(self, path):
        path = Path(path)
        if kind_of(path) in ("image", "gif") or not path.is_file():
            return None
        thumb = self.cached(path)
        if thumb or not self.supported():
            return thumb
        with self._lock:
            if path in self._pending or path in self._failed:
                return None
            self._pending.add(path)
        threading.Thread(target=self._make, args=(path,), daemon=True).start()
        return None

    def _make(self, path):
        ok = False
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory() as tmp:
                subprocess.run(["qlmanage", "-t", "-s", str(self.SIZE), "-o", tmp, str(path)],
                               capture_output=True, timeout=30)
                made = next(Path(tmp).glob("*.png"), None)
                if made is not None:
                    shutil.move(str(made), self.dir / f"{self._key(path)}.png")
                    ok = True
        except Exception:
            pass
        with self._lock:
            self._pending.discard(path)
            if not ok:
                self._failed.add(path)
        if ok and self.on_ready:
            self.on_ready(path)
