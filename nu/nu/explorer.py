"""Explorer: the open folder as a tree (file icons, git colours, create / rename / delete / reveal)."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QDir, QFileInfo, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView, QFileIconProvider, QFileSystemModel, QHBoxLayout, QInputDialog, QLabel, QMenu, QMessageBox,
    QToolButton, QTreeView, QVBoxLayout, QWidget,
)

from . import icons
from .systrash import move_to_trash


def reveal(path):
    if sys.platform == "darwin":
        subprocess.run(["open", "-R", str(path)])
    else:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))


class IconProvider(QFileIconProvider):
    def __init__(self, colors):
        super().__init__()
        self.c = colors

    def icon(self, arg):
        if isinstance(arg, QFileInfo):
            if arg.isDir():
                return icons.folder_icon(self.c["muted"])
            return icons.file_icon(arg.fileName())
        return icons.folder_icon(self.c["muted"])


class TreeModel(QSortFilterProxyModel):
    """Hides excluded names, sorts folders first, colours git changes."""

    def __init__(self, source, excludes, colors):
        super().__init__()
        self.setSourceModel(source)
        self.excludes = set(excludes)
        self.c = colors
        self.git = {}       # abs path → status letter
        self.git_dirs = {}  # abs dir → status of something inside

    def set_git(self, status):
        self.git = status
        self.git_dirs = {}
        for path, st in status.items():
            d = os.path.dirname(path)
            while d and d not in self.git_dirs and len(d) > 1:
                self.git_dirs[d] = st
                d = os.path.dirname(d)
        self.layoutChanged.emit()

    def filterAcceptsRow(self, row, parent):
        idx = self.sourceModel().index(row, 0, parent)
        return self.sourceModel().fileName(idx) not in self.excludes

    def lessThan(self, a, b):
        m = self.sourceModel()
        da, db = m.isDir(a), m.isDir(b)
        if da != db:
            return da
        return m.fileName(a).lower() < m.fileName(b).lower()

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.ForegroundRole and index.column() == 0:
            path = self.sourceModel().filePath(self.mapToSource(index))
            st = self.git.get(path) or self.git_dirs.get(path)
            if st:
                key = {"M": "git_modified", "A": "git_added", "D": "git_deleted", "?": "git_untracked",
                       "R": "git_modified", "U": "git_deleted"}.get(st, "git_modified")
                return QColor(self.c[key])
        return super().data(index, role)


class Explorer(QWidget):
    open_file = Signal(str)
    open_terminal = Signal(str)
    path_renamed = Signal(str, str)
    path_deleted = Signal(str)

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.root = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        head = QHBoxLayout()
        head.setContentsMargins(14, 10, 8, 6)
        self.title = QLabel("ПРОВОДНИК")
        self.title.setObjectName("SideTitle")
        head.addWidget(self.title, 1)
        self.buttons = []
        for name, tip, fn in (("newfile", "Новый файл", lambda: self.new_file()),
                              ("newfolder", "Новая папка", lambda: self.new_folder()),
                              ("refresh", "Обновить", self.refresh), ("collapse", "Свернуть всё", lambda: self.tree.collapseAll())):
            b = QToolButton()
            b.setToolTip(tip)
            b.setProperty("glyph", name)
            b.clicked.connect(fn)
            head.addWidget(b)
            self.buttons.append(b)
        lay.addLayout(head)
        self.folder_label = QLabel()
        self.folder_label.setObjectName("Section")
        self.folder_label.setContentsMargins(14, 2, 8, 6)
        lay.addWidget(self.folder_label)
        self.fs = QFileSystemModel()
        self.fs.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot | QDir.Hidden | QDir.System)
        self.fs.setReadOnly(False)
        self.provider = IconProvider(win.colors)
        self.fs.setIconProvider(self.provider)
        self.fs.fileRenamed.connect(self._fs_renamed)
        self.model = TreeModel(self.fs, win.settings.get("exclude", []), win.colors)
        self.model.setDynamicSortFilter(True)
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        for col in (1, 2, 3):
            self.tree.hideColumn(col)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setAnimated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setEditTriggers(QAbstractItemView.EditKeyPressed)
        self.tree.setDragDropMode(QAbstractItemView.DragDrop)
        self.tree.setDefaultDropAction(Qt.MoveAction)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.sortByColumn(0, Qt.AscendingOrder)
        self.tree.setSortingEnabled(True)
        self.tree.clicked.connect(self._clicked)
        self.tree.activated.connect(self._clicked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        lay.addWidget(self.tree, 1)
        self.empty = QLabel("Папка не открыта.\n\n⌘O — открыть папку")
        self.empty.setObjectName("Muted")
        self.empty.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.empty, 1)
        self.set_colors(win.colors)
        self.set_root(None)

    def set_colors(self, colors):
        self.provider.c = colors
        self.model.c = colors
        for b in self.buttons:
            b.setIcon(icons.glyph(b.property("glyph"), colors["muted"]))
        self.tree.viewport().update()

    def set_root(self, folder):
        self.root = Path(folder) if folder else None
        has = self.root is not None
        self.tree.setVisible(has)
        self.empty.setVisible(not has)
        for b in self.buttons:
            b.setEnabled(has)
        if has:
            src = self.fs.setRootPath(str(self.root))
            self.tree.setRootIndex(self.model.mapFromSource(src))
            self.folder_label.setText(self.root.name.upper())
        else:
            self.folder_label.setText("")

    def refresh(self):
        if self.root:
            self.set_root(self.root)
            self.win.refresh_git()

    def reveal_path(self, path):
        if not self.root:
            return
        idx = self.model.mapFromSource(self.fs.index(str(path)))
        if idx.isValid():
            self.tree.setCurrentIndex(idx)
            self.tree.scrollTo(idx)

    # ------------------------------------------------------------------ actions
    def _path(self, idx):
        return Path(self.fs.filePath(self.model.mapToSource(idx)))

    def _clicked(self, idx):
        path = self._path(idx)
        if path.is_file():
            self.open_file.emit(str(path))

    def _target_dir(self, idx=None):
        if idx is None:
            idx = self.tree.currentIndex()
        if idx is not None and idx.isValid():
            p = self._path(idx)
            return p if p.is_dir() else p.parent
        return self.root

    def new_file(self, folder=None):
        folder = Path(folder) if folder else self._target_dir()
        if folder is None:
            return
        name, ok = QInputDialog.getText(self, "Новый файл", f"Имя файла в «{folder.name}»:\n(можно с папками: src/app.py)")
        if not ok or not name.strip():
            return
        path = folder / name.strip()
        if path.exists():
            QMessageBox.warning(self, "Ню", f"«{path.name}» уже существует")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        self.open_file.emit(str(path))
        self.reveal_path(path)

    def new_folder(self, folder=None):
        folder = Path(folder) if folder else self._target_dir()
        if folder is None:
            return
        name, ok = QInputDialog.getText(self, "Новая папка", f"Имя папки в «{folder.name}»:")
        if ok and name.strip():
            path = folder / name.strip()
            path.mkdir(parents=True, exist_ok=True)
            self.reveal_path(path)

    def rename(self, path):
        path = Path(path)
        name, ok = QInputDialog.getText(self, "Переименовать", "Новое имя:", text=path.name)
        if not ok or not name.strip() or name.strip() == path.name:
            return
        new = path.with_name(name.strip())
        if new.exists():
            QMessageBox.warning(self, "Ню", f"«{new.name}» уже существует")
            return
        path.rename(new)
        self.path_renamed.emit(str(path), str(new))

    def _fs_renamed(self, folder, old, new):
        self.path_renamed.emit(os.path.join(folder, old), os.path.join(folder, new))

    def delete(self, paths):
        paths = [Path(p) for p in paths]
        names = ", ".join(f"«{p.name}»" for p in paths[:3]) + (" …" if len(paths) > 3 else "")
        if QMessageBox.question(self, "Ню", f"Переместить {names} в Корзину?") != QMessageBox.Yes:
            return
        for p in paths:
            try:
                move_to_trash(p)
            except Exception as exc:
                QMessageBox.warning(self, "Ню", f"Не удалось удалить «{p.name}»: {exc}")
                continue
            self.path_deleted.emit(str(p))

    def duplicate(self, path):
        path = Path(path)
        n = 1
        while True:
            new = path.with_name(f"{path.stem} копия{'' if n == 1 else ' ' + str(n)}{path.suffix}")
            if not new.exists():
                break
            n += 1
        if path.is_dir():
            shutil.copytree(path, new)
        else:
            shutil.copy2(path, new)
        self.reveal_path(new)

    def _menu(self, pos):
        idx = self.tree.indexAt(pos)
        menu = QMenu(self)
        if not self.root:
            return
        path = self._path(idx) if idx.isValid() else self.root
        folder = path if path.is_dir() else path.parent
        selected = [self._path(i) for i in self.tree.selectionModel().selectedRows()] or [path]
        if path.is_file():
            menu.addAction("Открыть", lambda: self.open_file.emit(str(path)))
            menu.addAction("Открыть сбоку", lambda: self.win.open_file(str(path), split=True))
            menu.addSeparator()
        menu.addAction("Новый файл…", lambda: self.new_file(folder))
        menu.addAction("Новая папка…", lambda: self.new_folder(folder))
        menu.addSeparator()
        menu.addAction("Показать в Finder", lambda: reveal(path))
        menu.addAction("Открыть в терминале", lambda: self.open_terminal.emit(str(folder)))
        menu.addAction("Найти в папке…", lambda: self.win.search_in(folder))
        menu.addSeparator()
        menu.addAction("Копировать путь", lambda: QGuiApplication.clipboard().setText(str(path)))
        menu.addAction("Копировать относительный путь",
                       lambda: QGuiApplication.clipboard().setText(os.path.relpath(path, self.root)))
        if idx.isValid():
            menu.addSeparator()
            menu.addAction("Дублировать", lambda: self.duplicate(path))
            menu.addAction("Переименовать…", lambda: self.rename(path))
            menu.addAction("Удалить в Корзину", lambda: self.delete(selected))
        menu.exec(self.tree.viewport().mapToGlobal(pos))
