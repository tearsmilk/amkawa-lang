"""Source control (git): branch, changed files, diff, stage-all + commit, pull / push."""
import os
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout,
    QWidget,
)

from . import icons

LABELS = {"M": "изменён", "A": "добавлен", "D": "удалён", "R": "переименован", "?": "новый", "U": "конфликт", "C": "скопирован"}


def git(root, *args, timeout=20):
    if not shutil.which("git"):
        return 127, "", "git не найден (установите Xcode Command Line Tools: xcode-select --install)"
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", str(exc)


def repo_root(folder):
    if not folder:
        return None
    code, out, _ = git(folder, "rev-parse", "--show-toplevel", timeout=5)
    return Path(out.strip()) if code == 0 and out.strip() else None


def parse_status(text, root):
    """`git status --porcelain=v1 -z` → {abs path: letter}."""
    out = {}
    parts = text.split("\0")
    i = 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if len(entry) < 4:
            continue
        x, y, path = entry[0], entry[1], entry[3:]
        if x == "R" or x == "C":
            i += 1  # original name follows
        if x == "?" and y == "?":
            letter = "?"
        elif "U" in (x, y) or (x == y == "A") or (x == y == "D"):
            letter = "U"
        else:
            letter = (y if y != " " else x).replace(" ", "M")
        out[str(Path(root) / path)] = letter
    return out


def status(root):
    code, out, _ = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all", timeout=10)
    return parse_status(out, root) if code == 0 else {}


def branch(root):
    code, out, _ = git(root, "rev-parse", "--abbrev-ref", "HEAD", timeout=5)
    return out.strip() if code == 0 else ""


class ScmPanel(QWidget):
    open_file = Signal(str)
    open_diff = Signal(str, str)  # title, diff text

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.root = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 10, 8)
        lay.setSpacing(8)
        head = QHBoxLayout()
        t = QLabel("СИСТЕМА КОНТРОЛЯ ВЕРСИЙ")
        t.setObjectName("SideTitle")
        head.addWidget(t, 1)
        lay.addLayout(head)
        self.branch = QLabel("")
        self.branch.setObjectName("Muted")
        lay.addWidget(self.branch)
        self.message = QPlainTextEdit()
        self.message.setObjectName("Input")
        self.message.setPlaceholderText("Сообщение коммита (⌘↩ — зафиксировать)")
        self.message.setFixedHeight(64)
        lay.addWidget(self.message)
        row = QHBoxLayout()
        self.commit_btn = QPushButton("✓  Зафиксировать всё")
        self.commit_btn.setObjectName("Accent")
        self.commit_btn.clicked.connect(self.commit)
        row.addWidget(self.commit_btn, 1)
        sync = QPushButton("⇅")
        sync.setToolTip("Pull, затем Push")
        sync.clicked.connect(self.sync)
        row.addWidget(sync)
        lay.addLayout(row)
        self.count = QLabel("")
        self.count.setObjectName("Section")
        lay.addWidget(self.count)
        self.list = QListWidget()
        self.list.itemActivated.connect(self._diff)
        self.list.itemClicked.connect(self._diff)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        lay.addWidget(self.list, 1)
        self.init_btn = QPushButton("Инициализировать репозиторий")
        self.init_btn.clicked.connect(self.init_repo)
        lay.addWidget(self.init_btn)
        self.message.installEventFilter(self)

    def eventFilter(self, obj, e):
        if obj is self.message and e.type() == e.Type.KeyPress and e.key() in (Qt.Key_Return, Qt.Key_Enter) \
                and e.modifiers() & Qt.ControlModifier:
            self.commit()
            return True
        return super().eventFilter(obj, e)

    def refresh(self, folder=None):
        folder = folder or self.win.folder
        self.root = repo_root(folder) if folder else None
        self.list.clear()
        has = self.root is not None
        for w in (self.message, self.commit_btn):
            w.setEnabled(has)
        self.init_btn.setVisible(bool(folder) and not has)
        if not has:
            self.branch.setText("Папка не является git-репозиторием" if folder else "Папка не открыта")
            self.count.setText("")
            return {}, ""
        st = status(self.root)
        br = branch(self.root)
        self.branch.setText(f"Ветка: {br}")
        c = self.win.colors
        for path, letter in sorted(st.items()):
            rel = os.path.relpath(path, self.root)
            item = QListWidgetItem(icons.file_icon(path), f"{rel}    {letter}")
            item.setToolTip(f"{rel} — {LABELS.get(letter, letter)}")
            item.setData(Qt.UserRole, (path, letter))
            key = {"M": "git_modified", "A": "git_added", "D": "git_deleted", "?": "git_untracked", "U": "git_deleted"}
            item.setForeground(QColor(c[key.get(letter, "git_modified")]))
            self.list.addItem(item)
        self.count.setText(f"ИЗМЕНЕНИЯ  {len(st)}" if st else "НЕТ ИЗМЕНЕНИЙ")
        return st, br

    def _diff(self, item):
        path, letter = item.data(Qt.UserRole)
        if letter == "?":
            self.open_file.emit(path)
            return
        rel = os.path.relpath(path, self.root)
        _code, out, err = git(self.root, "diff", "HEAD", "--", rel)
        self.open_diff.emit(f"{Path(path).name} (изменения)", out or err or "Нет отличий")

    def _menu(self, pos):
        item = self.list.itemAt(pos)
        if not item:
            return
        path, letter = item.data(Qt.UserRole)
        menu = QMenu(self)
        menu.addAction("Открыть файл", lambda: self.open_file.emit(path))
        menu.addAction("Показать изменения", lambda: self._diff(item))
        if letter != "?":
            menu.addAction("Отменить изменения…", lambda: self.discard(path))
        menu.exec(self.list.viewport().mapToGlobal(pos))

    def discard(self, path):
        rel = os.path.relpath(path, self.root)
        if QMessageBox.question(self, "Ню", f"Отменить все изменения в «{rel}»? Это нельзя отменить.") != QMessageBox.Yes:
            return
        git(self.root, "checkout", "HEAD", "--", rel)
        self.win.reload_open_files()
        self.win.refresh_git()

    def commit(self):
        msg = self.message.toPlainText().strip()
        if not self.root:
            return
        if not msg:
            self.message.setFocus()
            self.win.status_message("Введите сообщение коммита")
            return
        self.win.save_all()
        git(self.root, "add", "-A")
        code, out, err = git(self.root, "commit", "-m", msg)
        if code != 0:
            QMessageBox.warning(self, "Ню", (err or out).strip()[:1500] or "Коммит не удался")
        else:
            self.message.clear()
            self.win.status_message("Изменения зафиксированы")
        self.win.refresh_git()

    def sync(self):
        if not self.root:
            return
        self.win.status_message("Синхронизация…")
        for args in (("pull", "--ff-only"), ("push",)):
            code, out, err = git(self.root, *args, timeout=120)
            if code != 0:
                QMessageBox.warning(self, "Ню", f"git {' '.join(args)}:\n{(err or out).strip()[:1500]}")
                break
        self.win.refresh_git()
        self.win.status_message("Готово")

    def init_repo(self):
        if self.win.folder:
            git(self.win.folder, "init")
            self.win.refresh_git()
