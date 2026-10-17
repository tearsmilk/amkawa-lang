"""Command palette (⇧⌘P) and Quick Open (⌘P): one fuzzy list, VS Code prefixes:
no prefix → files, «>» → commands, «:» → go to line, «@» → symbols of the current file."""
import os
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from . import icons
from .search import SKIP_DIRS

SYMBOL_RE = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?(?:def|class|function|func|fn|struct|enum|interface|trait|impl|type|module|"
    r"public\s+(?:static\s+)?(?:class|void|[\w<>\[\]]+)|private\s+[\w<>\[\]]+|protected\s+[\w<>\[\]]+)\s+([A-Za-z_][\w]*)"
)


def fuzzy_score(query, text):
    """Subsequence match score (higher is better) or None."""
    if not query:
        return 0
    q, t = query.lower(), text.lower()
    pos = -1
    score = 0
    prev = -2
    for ch in q:
        pos = t.find(ch, pos + 1)
        if pos < 0:
            return None
        score += 3 if pos == prev + 1 else 1
        if pos == 0 or t[pos - 1] in "/_-. ":
            score += 2
        prev = pos
    base = os.path.basename(t)
    if q in base:
        score += 10 + (5 if base.startswith(q) else 0)
    return score - len(t) * 0.01


def list_files(root, limit=30000):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git"))
        for name in filenames:
            if name == ".DS_Store":
                continue
            out.append(os.path.relpath(os.path.join(dirpath, name), root))
            if len(out) >= limit:
                return out
    return out


def symbols(text):
    out = []
    for n, line in enumerate(text.split("\n")):
        m = SYMBOL_RE.match(line)
        if m:
            out.append((m.group(1), n + 1, line.strip()[:90]))
    return out


class Palette(QDialog):
    chosen = Signal(object)

    def __init__(self, win, mode=""):
        super().__init__(win, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("Palette")
        self.win = win
        self.setAttribute(Qt.WA_DeleteOnClose)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(4)
        self.edit = QLineEdit(mode)
        lay.addWidget(self.edit)
        self.list = QListWidget()
        lay.addWidget(self.list)
        self.edit.textChanged.connect(self.refresh)
        self.list.itemActivated.connect(self.accept_item)
        self.list.itemClicked.connect(self.accept_item)
        self.edit.installEventFilter(self)
        self._files = None
        self._symbols = None
        w = min(640, int(win.width() * 0.6))
        self.resize(w, 420)
        geo = win.geometry()
        self.move(geo.x() + (geo.width() - w) // 2, geo.y() + 70)
        self.refresh()

    def eventFilter(self, obj, e):
        if e.type() == e.Type.KeyPress:
            if e.key() in (Qt.Key_Down, Qt.Key_Up, Qt.Key_PageDown, Qt.Key_PageUp):
                self.list.keyPressEvent(e)
                return True
            if e.key() in (Qt.Key_Return, Qt.Key_Enter):
                item = self.list.currentItem()
                if item:
                    self.accept_item(item)
                elif self.edit.text().startswith(":"):
                    self.accept_item(None)
                return True
            if e.key() == Qt.Key_Escape:
                self.close()
                return True
        return super().eventFilter(obj, e)

    def _add(self, text, data, icon=None, hint=""):
        item = QListWidgetItem(text + (f"      {hint}" if hint else ""))
        item.setData(Qt.UserRole, data)
        if icon is not None:
            item.setIcon(icon)
        self.list.addItem(item)

    def refresh(self):
        text = self.edit.text()
        self.list.clear()
        if text.startswith(">"):
            q = text[1:].strip()
            scored = []
            for cmd in self.win.commands():
                s = fuzzy_score(q, cmd["title"])
                if s is not None:
                    scored.append((-s if q else 0, cmd["title"], cmd))
            for _s, _t, cmd in sorted(scored, key=lambda x: (x[0], x[1]))[:200]:
                self._add(cmd["title"], ("cmd", cmd["id"]), hint=cmd.get("shortcut", ""))
        elif text.startswith(":"):
            ed = self.win.current_editor()
            total = ed.blockCount() if ed else 0
            line = text[1:].strip()
            self._add(f"Перейти к строке {line or '…'}" + (f"  (строк: {total})" if total else ""), ("line", line))
        elif text.startswith("@"):
            ed = self.win.current_editor()
            if self._symbols is None:
                self._symbols = symbols(ed.toPlainText()) if ed else []
            q = text[1:].strip()
            scored = [(fuzzy_score(q, name), name, line, src) for name, line, src in self._symbols]
            for s, name, line, src in sorted((x for x in scored if x[0] is not None), key=lambda x: (-x[0], x[2]))[:300]:
                self._add(f"{name}", ("line", str(line)), hint=f"{line}: {src}")
            if not self._symbols:
                self._add("Символы не найдены", None)
        else:
            root = self.win.folder
            if not root:
                for path in self.win.recent_files()[:30]:
                    self._add(os.path.basename(path), ("file", path), icons.file_icon(path), os.path.dirname(path))
                if not self.list.count():
                    self._add("Откройте папку (⌘O), чтобы искать файлы", None)
            else:
                if self._files is None:
                    self._files = list_files(root)
                q = text.strip()
                if not q:
                    picks = [os.path.relpath(p, root) for p in self.win.recent_files() if p.startswith(str(root))][:20]
                    picks += [f for f in self._files[:200] if f not in picks]
                    ranked = picks
                else:
                    scored = [(fuzzy_score(q, f), f) for f in self._files]
                    ranked = [f for s, f in sorted((x for x in scored if x[0] is not None), key=lambda x: -x[0])[:200]]
                for rel in ranked:
                    path = os.path.join(root, rel)
                    self._add(os.path.basename(rel), ("file", path), icons.file_icon(rel), os.path.dirname(rel))
        if self.list.count():
            self.list.setCurrentRow(0)

    def accept_item(self, item):
        data = item.data(Qt.UserRole) if item else ("line", self.edit.text()[1:].strip())
        if not data:
            return
        self.close()
        self.chosen.emit(data)
