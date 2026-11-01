"""Search (and replace) in the files of the open folder."""
import fnmatch
import os
import re
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget,
)

from . import icons

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".mypy_cache", ".pytest_cache",
             ".idea", ".next", "target", ".gradle", "Pods", "DerivedData"}
MAX_FILE = 2_000_000
MAX_RESULTS = 5000


def compile_query(query, case=False, regex=False, word=False):
    if not query:
        return None
    pattern = query if regex else re.escape(query)
    if word:
        pattern = rf"\b{pattern}\b"
    try:
        return re.compile(pattern, 0 if case else re.IGNORECASE)
    except re.error:
        return None


def iter_files(root, include="", exclude=""):
    inc = [p.strip() for p in include.split(",") if p.strip()]
    exc = [p.strip() for p in exclude.split(",") if p.strip()]
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not any(fnmatch.fnmatch(d, e) for e in exc)]
        for name in filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            if inc and not any(fnmatch.fnmatch(name, i) or fnmatch.fnmatch(rel, i) for i in inc):
                continue
            if exc and any(fnmatch.fnmatch(name, e) or fnmatch.fnmatch(rel, e) for e in exc):
                continue
            yield path


def search(root, rx, include="", exclude="", stop=None):
    """→ list of (path, [(line_no, col, length, text)])."""
    results = []
    total = 0
    for path in iter_files(root, include, exclude):
        if stop and stop.is_set():
            break
        try:
            if os.path.getsize(path) > MAX_FILE:
                continue
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError:
            continue
        if b"\0" in data[:4000]:
            continue
        text = data.decode("utf-8", errors="replace")
        hits = []
        for n, line in enumerate(text.split("\n")):
            for m in rx.finditer(line):
                if m.end() > m.start():
                    hits.append((n + 1, m.start(), m.end() - m.start(), line.rstrip("\r")))
                    total += 1
                if total >= MAX_RESULTS:
                    break
        if hits:
            results.append((path, hits))
        if total >= MAX_RESULTS:
            break
    return results


def replace_in_files(results, rx, replacement):
    changed = 0
    for path, _hits in results:
        try:
            p = Path(path)
            text = p.read_text("utf-8")
            new, n = rx.subn(replacement, text)
            if n:
                p.write_text(new, "utf-8")
                changed += n
        except (OSError, UnicodeDecodeError):
            continue
    return changed


class _Bridge(QObject):
    done = Signal(object, int)


class SearchPanel(QWidget):
    open_location = Signal(str, int, int, int)  # path, line, col, length

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.bridge = _Bridge()
        self.bridge.done.connect(self._show)
        self._stop = None
        self._gen = 0
        self.results = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 10, 6)
        lay.setSpacing(6)
        t = QLabel("ПОИСК")
        t.setObjectName("SideTitle")
        lay.addWidget(t)
        row = QHBoxLayout()
        row.setSpacing(2)
        self.query = QLineEdit()
        self.query.setPlaceholderText("Найти")
        self.query.setClearButtonEnabled(True)
        row.addWidget(self.query, 1)
        self.toggles = {}
        for key, label, tip in (("case", "Aa", "Учитывать регистр"), ("word", "ab", "Слово целиком"),
                                ("regex", ".*", "Регулярное выражение")):
            b = QToolButton()
            b.setText(label)
            b.setCheckable(True)
            b.setToolTip(tip)
            b.toggled.connect(self.schedule)
            row.addWidget(b)
            self.toggles[key] = b
        lay.addLayout(row)
        rrow = QHBoxLayout()
        self.replace = QLineEdit()
        self.replace.setPlaceholderText("Заменить")
        rrow.addWidget(self.replace, 1)
        self.replace_btn = QPushButton("Заменить всё")
        self.replace_btn.clicked.connect(self.replace_all)
        rrow.addWidget(self.replace_btn)
        lay.addLayout(rrow)
        self.include = QLineEdit()
        self.include.setPlaceholderText("Включить файлы, напр. *.py, src/*")
        self.exclude = QLineEdit()
        self.exclude.setPlaceholderText("Исключить, напр. *.min.js")
        lay.addWidget(self.include)
        lay.addWidget(self.exclude)
        self.info = QLabel("")
        self.info.setObjectName("Muted")
        lay.addWidget(self.info)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(12)
        self.tree.itemActivated.connect(self._activated)
        self.tree.itemClicked.connect(self._activated)
        lay.addWidget(self.tree, 1)
        self.timer = QTimer(self, singleShot=True, interval=300, timeout=self.run)
        for w in (self.query, self.include, self.exclude):
            w.textChanged.connect(self.schedule)
        self.query.returnPressed.connect(self.run)

    def focus(self, text=None):
        if text:
            self.query.setText(text)
        self.query.setFocus()
        self.query.selectAll()

    def schedule(self, *_):
        self.timer.start()

    def _rx(self):
        return compile_query(self.query.text(), self.toggles["case"].isChecked(), self.toggles["regex"].isChecked(),
                             self.toggles["word"].isChecked())

    def run(self):
        root = self.win.folder
        rx = self._rx()
        if self._stop:
            self._stop.set()
        self.tree.clear()
        if not root or rx is None:
            self.info.setText("Откройте папку, чтобы искать по файлам" if not root else
                              ("Неверное регулярное выражение" if self.query.text() else ""))
            return
        self.info.setText("Поиск…")
        self._gen += 1
        gen = self._gen
        stop = self._stop = threading.Event()
        inc, exc = self.include.text(), self.exclude.text()
        threading.Thread(target=lambda: self.bridge.done.emit(search(root, rx, inc, exc, stop), gen), daemon=True).start()

    def _show(self, results, gen):
        if gen != self._gen:
            return
        self.results = results
        self.tree.clear()
        root = Path(self.win.folder)
        count = 0
        for path, hits in results:
            item = QTreeWidgetItem([f"{os.path.relpath(path, root)}   {len(hits)}"])
            item.setIcon(0, icons.file_icon(path))
            item.setData(0, Qt.UserRole, (path, hits[0][0], hits[0][1], hits[0][2]))
            for line, col, length, text in hits[:500]:
                start = max(0, col - 30)
                snippet = ("…" if start else "") + text[start:].strip()[:160]
                child = QTreeWidgetItem([f"{line}:  {snippet}"])
                child.setData(0, Qt.UserRole, (path, line, col, length))
                child.setToolTip(0, text.strip()[:400])
                item.addChild(child)
            count += len(hits)
            self.tree.addTopLevelItem(item)
            item.setExpanded(len(results) < 30)
        more = " (показаны первые)" if count >= MAX_RESULTS else ""
        self.info.setText(f"{count} совпадений в {len(results)} файлах{more}" if results else "Ничего не найдено")

    def _activated(self, item, _col=0):
        data = item.data(0, Qt.UserRole)
        if data:
            self.open_location.emit(*data)

    def replace_all(self):
        rx = self._rx()
        if rx is None or not self.results:
            return
        files = len(self.results)
        if QMessageBox.question(self, "Ню", f"Заменить все совпадения в {files} файлах на «{self.replace.text()}»?") \
                != QMessageBox.Yes:
            return
        self.win.save_all()
        replacement = self.replace.text() if self.toggles["regex"].isChecked() else self.replace.text().replace("\\", "\\\\")
        n = replace_in_files(self.results, rx, replacement)
        self.win.reload_open_files()
        self.info.setText(f"Заменено: {n}")
        self.run()
