"""Epsilon main window: sidebar (notes tree, tags, sections), tabbed notes, right panel."""
import datetime as dt
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QDir, QSortFilterProxyModel, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QImage, QKeySequence, QPalette, QShortcut, QTextDocument
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFileSystemModel, QFrame,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMenu, QMessageBox, QPushButton, QSpinBox, QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem, QTabWidget,
    QTextBrowser, QTreeView, QVBoxLayout, QWidget,
)

from . import APP_NAME, LOGO, __version__
from .calendar_view import CalendarTab, notify
from .editor import MarkdownEditor
from .graph import GraphView
from .mdrender import Renderer
from .paths import Settings, default_vault, resource_path
from .theme import DARK, LIGHT, stylesheet
from .tasks import TaskIndex
from .vault import ATTACHMENTS, Vault

MODES = [("edit", "Редактор"), ("split", "Разделить"), ("read", "Просмотр")]


def reveal_in_finder(path):
    path = str(path)
    if sys.platform == "darwin":
        subprocess.run(["open", "-R", path])
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))


def human_size(n):
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if n < 1024 or unit == "ГБ":
            return f"{n:.0f} {unit}" if unit == "Б" else f"{n:.1f} {unit}"
        n /= 1024


def muted(text):
    label = QLabel(text)
    label.setObjectName("Muted")
    label.setWordWrap(True)
    return label


def section(text):
    label = QLabel(text.upper())
    label.setObjectName("Section")
    return label


# ====================================================================== reader
class Reader(QTextBrowser):
    """Rendered Markdown. Links: note:, tag:, task:, copy:, http(s), local files."""

    def __init__(self):
        super().__init__()
        self.setObjectName("Reader")
        self.setOpenLinks(False)
        self.document().setDocumentMargin(28)

    def loadResource(self, kind, url):
        if kind == QTextDocument.ImageResource and url.isLocalFile():
            img = QImage(url.toLocalFile())
            if not img.isNull():
                max_w = max(200, self.viewport().width() - 90)
                if img.width() > max_w:
                    img = img.scaledToWidth(max_w, Qt.SmoothTransformation)
                return img
        return super().loadResource(kind, url)


# ====================================================================== note tab
class NoteTab(QWidget):
    open_target = Signal(str)       # note name from [[link]]
    show_tag = Signal(str)
    status = Signal(str)
    renamed = Signal(object, object)
    saved = Signal(object)

    def __init__(self, win, path, mode):
        super().__init__()
        self.win = win
        self.vault = win.vault
        self.path = Path(path)
        self.kind = "note"
        self._mtime = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QHBoxLayout()
        head.setContentsMargins(28, 14, 18, 10)
        self.title = QLineEdit(self.path.stem)
        self.title.setObjectName("NoteTitle")
        self.title.editingFinished.connect(self._rename)
        self.crumbs = muted("")
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_col.addWidget(self.title)
        title_col.addWidget(self.crumbs)
        head.addLayout(title_col, 1)
        seg = QFrame()
        seg.setObjectName("Segment")
        seg_lay = QHBoxLayout(seg)
        seg_lay.setContentsMargins(0, 0, 0, 0)
        seg_lay.setSpacing(0)
        self.mode_group = QButtonGroup(self)
        for key, label in MODES:
            b = QPushButton(label)
            b.setCheckable(True)
            b.setProperty("mode", key)
            self.mode_group.addButton(b)
            seg_lay.addWidget(b)
        self.mode_group.buttonClicked.connect(lambda b: self.set_mode(b.property("mode")))
        head.addWidget(seg)
        more = QPushButton("···")
        more.setObjectName("Link")
        more.clicked.connect(lambda: self._more_menu(more))
        head.addWidget(more)
        lay.addLayout(head)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(1)
        self.editor = MarkdownEditor(self.vault, self.path, win.colors)
        self.editor.status.connect(self.status)
        self.reader = Reader()
        self.reader.anchorClicked.connect(self._link_clicked)
        self.splitter.addWidget(self.editor)
        self.splitter.addWidget(self.reader)
        lay.addWidget(self.splitter, 1)

        self.save_timer = QTimer(self, singleShot=True, interval=600, timeout=self.save)
        self.preview_timer = QTimer(self, singleShot=True, interval=250, timeout=self.refresh_preview)
        self.load()
        self.editor.textChanged.connect(self._changed)
        self.apply_font(win.settings.get("font_size", 14))
        self.set_mode(mode)

    # ------------------------------------------------------------ file
    def load(self):
        text = self.vault.read(self.path)
        self.editor.blockSignals(True)
        self.editor.setPlainText(text)
        self.editor.blockSignals(False)
        self._mtime = self.path.stat().st_mtime if self.path.exists() else None
        rel = Path(self.vault.rel(self.path)).parent
        self.crumbs.setText(" / ".join([self.vault.root.name] + ([str(rel)] if str(rel) != "." else [])))
        self.refresh_preview()

    def _changed(self):
        self.save_timer.start()
        self.preview_timer.start()

    def save(self):
        if self.save_timer.isActive():
            self.save_timer.stop()
        text = self.editor.toPlainText()
        if self.path.exists() and self.vault.read(self.path) == text:
            return
        self.vault.write(self.path, text)
        self._mtime = self.path.stat().st_mtime
        self.saved.emit(self.path)

    def reload_if_changed(self):
        if self.path.exists() and self._mtime and self.path.stat().st_mtime > self._mtime + 0.5 \
                and not self.save_timer.isActive():
            pos = self.editor.textCursor().position()
            self.load()
            c = self.editor.textCursor()
            c.setPosition(min(pos, len(self.editor.toPlainText())))
            self.editor.setTextCursor(c)

    def _rename(self):
        new = self.title.text().strip()
        if not new or new == self.path.stem:
            self.title.setText(self.path.stem)
            return
        self.save()
        old = self.path
        try:
            self.path = self.vault.rename(self.path, new)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            self.title.setText(self.path.stem)
            return
        self.editor.note_path = self.path
        self.title.setText(self.path.stem)
        self.renamed.emit(old, self.path)

    # ------------------------------------------------------------ view
    def set_mode(self, mode):
        self.mode = mode
        for b in self.mode_group.buttons():
            b.setChecked(b.property("mode") == mode)
        self.editor.setVisible(mode in ("edit", "split"))
        self.reader.setVisible(mode in ("read", "split"))
        if mode == "split":
            w = max(600, self.splitter.width())
            self.splitter.setSizes([w // 2, w // 2])
        if mode != "edit":
            self.refresh_preview()
        (self.editor if mode != "read" else self.reader).setFocus()

    def apply_font(self, size):
        f = self.editor.font()
        f.setPointSize(size)
        self.editor.setFont(f)
        self.refresh_preview()

    def apply_colors(self, colors):
        self.editor.set_colors(colors)
        self.refresh_preview()

    def refresh_preview(self):
        if not self.reader.isVisible() and getattr(self, "mode", "split") == "edit":
            return
        renderer = Renderer(self.win.colors, self.vault.resolve, self.win.colors.get("code_style", "default"))
        html = renderer.render(self.editor.toPlainText())
        self.renderer = renderer
        doc = self.reader.document()
        doc.setDefaultStyleSheet(renderer.stylesheet(self.win.settings.get("font_size", 14) + 1))
        doc.setBaseUrl(QUrl.fromLocalFile(str(self.path.parent) + "/"))
        bar = self.reader.verticalScrollBar()
        pos = bar.value()
        self.reader.setHtml(html)
        bar.setValue(pos)

    # ------------------------------------------------------------ links
    def _link_clicked(self, url: QUrl):
        s = url.toString()
        scheme = url.scheme()
        if scheme == "note":
            self.open_target.emit(QUrl.fromPercentEncoding(s[5:].encode()))
        elif scheme == "tag":
            self.show_tag.emit(QUrl.fromPercentEncoding(s[4:].encode()))
        elif scheme == "task":
            self.toggle_task(int(s[5:]))
        elif scheme == "copy":
            n = int(s[5:])
            if n < len(self.renderer.code_blocks):
                QApplication.clipboard().setText(self.renderer.code_blocks[n])
                self.status.emit("Код скопирован")
        elif url.isLocalFile() or scheme == "":
            local = Path(url.toLocalFile()) if url.isLocalFile() else (self.path.parent / QUrl.fromPercentEncoding(s.encode()))
            if local.suffix == ".md" and local.exists():
                self.win.open_note(local)
            elif local.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(local)))
        else:
            QDesktopServices.openUrl(url)

    def toggle_task(self, line_no):
        block = self.editor.document().findBlockByNumber(line_no)
        if not block.isValid():
            return
        text = block.text()
        import re

        m = re.match(r"^(\s*(?:[-*+]|\d+\.)\s+)\[( |x|X)\]", text)
        if not m:
            return
        from PySide6.QtGui import QTextCursor

        c = QTextCursor(block)
        c.setPosition(block.position() + len(m.group(1)) + 1)
        c.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
        c.insertText(" " if m.group(2).lower() == "x" else "x")

    def _more_menu(self, button):
        menu = QMenu(self)
        menu.addAction("Показать в Finder", lambda: reveal_in_finder(self.path))
        menu.addAction("Экспорт в PDF…", self.export_pdf)
        menu.addAction("Копировать как Markdown", lambda: QApplication.clipboard().setText(self.editor.toPlainText()))
        menu.addSeparator()
        menu.addAction("Удалить заметку", lambda: self.win.delete_path(self.path))
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def export_pdf(self):
        try:
            from PySide6.QtPrintSupport import QPrinter
        except Exception:
            QMessageBox.warning(self, APP_NAME, "Экспорт в PDF недоступен в этой сборке")
            return
        dest, _ = QFileDialog.getSaveFileName(self, "Экспорт в PDF", str(Path.home() / f"{self.path.stem}.pdf"), "PDF (*.pdf)")
        if not dest:
            return
        self.refresh_preview()
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(dest)
        self.reader.document().print_(printer)
        self.status.emit(f"PDF сохранён: {Path(dest).name}")


# ====================================================================== other tabs
class LinksTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.kind = "links"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 20)
        lay.setSpacing(12)
        title = QLabel("Ссылки")
        title.setObjectName("Title")
        lay.addWidget(title)
        lay.addWidget(muted("Закладки хранятся в хранилище (.epsilon/links.json). Двойной щелчок — открыть."))
        row = QHBoxLayout()
        self.url = QLineEdit(placeholderText="https://…")
        self.name = QLineEdit(placeholderText="Название (необязательно)")
        self.tags = QLineEdit(placeholderText="теги через запятую")
        add = QPushButton("Добавить")
        add.setObjectName("Accent")
        add.clicked.connect(self.add)
        self.url.returnPressed.connect(self.add)
        row.addWidget(self.url, 3)
        row.addWidget(self.name, 2)
        row.addWidget(self.tags, 2)
        row.addWidget(add)
        lay.addLayout(row)
        self.filter = QLineEdit(placeholderText="Фильтр…")
        self.filter.textChanged.connect(self.refresh)
        lay.addWidget(self.filter)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Название", "Адрес", "Теги", "Добавлено"])
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.cellDoubleClicked.connect(lambda r, _c: self._open(r))
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)
        lay.addWidget(self.table, 1)
        self.refresh()

    def add(self):
        if not self.url.text().strip():
            return
        self.win.vault.add_link(self.url.text(), self.name.text(), self.tags.text().split(","))
        for w in (self.url, self.name, self.tags):
            w.clear()
        self.refresh()

    def refresh(self):
        q = self.filter.text().lower().strip()
        self.links = [l for l in self.win.vault.links()
                      if not q or q in f"{l.title} {l.url} {' '.join(l.tags)} {l.note}".lower()]
        self.table.setRowCount(len(self.links))
        for r, l in enumerate(self.links):
            for c, val in enumerate([l.title, l.url, ", ".join("#" + t for t in l.tags), l.added.replace("T", " ")]):
                self.table.setItem(r, c, QTableWidgetItem(val))

    def _open(self, row):
        QDesktopServices.openUrl(QUrl(self.links[row].url))

    def _menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        link = self.links[row]
        menu = QMenu(self)
        menu.addAction("Открыть", lambda: self._open(row))
        menu.addAction("Копировать адрес", lambda: QApplication.clipboard().setText(link.url))
        menu.addAction("Вставить в заметку", lambda: self.win.insert_into_current(f"[{link.title}]({link.url})"))

        def rename():
            text, ok = QInputDialog.getText(self, "Название", "Название ссылки:", text=link.title)
            if ok and text.strip():
                link.title = text.strip()
                self.win.vault.update_link(link)
                self.refresh()

        menu.addAction("Переименовать…", rename)
        menu.addSeparator()
        menu.addAction("Удалить", lambda: (self.win.vault.delete_link(link.id), self.refresh()))
        menu.exec(self.table.viewport().mapToGlobal(pos))


class FilesTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.kind = "files"
        self.setAcceptDrops(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 20)
        lay.setSpacing(12)
        title = QLabel("Файлы")
        title.setObjectName("Title")
        lay.addWidget(title)
        lay.addWidget(muted("Все файлы копируются в папку attachments внутри хранилища. Перетащите файлы сюда."))
        row = QHBoxLayout()
        add = QPushButton("Добавить файлы…")
        add.setObjectName("Accent")
        add.clicked.connect(self._pick)
        row.addWidget(add)
        row.addWidget(QPushButton("Открыть папку", clicked=lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.win.vault.root / ATTACHMENTS)))))
        row.addStretch(1)
        lay.addLayout(row)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Имя", "Размер", "Изменён"])
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.cellDoubleClicked.connect(lambda r, _c: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.files[r]))))
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)
        lay.addWidget(self.table, 1)
        self.refresh()

    def refresh(self):
        self.files = self.win.vault.attachments()
        self.table.setRowCount(len(self.files))
        for r, p in enumerate(self.files):
            st = p.stat()
            for c, val in enumerate([p.name, human_size(st.st_size),
                                     dt.datetime.fromtimestamp(st.st_mtime).strftime("%d.%m.%Y %H:%M")]):
                self.table.setItem(r, c, QTableWidgetItem(val))

    def import_files(self, paths):
        for p in paths:
            if Path(p).is_file():
                self.win.vault.import_file(p)
        self.refresh()

    def _pick(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Добавить файлы")
        self.import_files(paths)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.import_files([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

    def _menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        p = self.files[row]
        menu = QMenu(self)
        menu.addAction("Открыть", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(p))))
        menu.addAction("Показать в Finder", lambda: reveal_in_finder(p))
        menu.addAction("Вставить в заметку", lambda: self.win.insert_file_link(p))
        menu.addSeparator()

        def delete():
            to_system = bool(self.win.settings.get("delete_to_system_trash"))
            where = "в Корзину macOS" if to_system else "в корзину хранилища"
            if QMessageBox.question(self, APP_NAME, f"Переместить «{p.name}» {where}?") == QMessageBox.Yes:
                self.win.vault.delete(p, to_system_trash=to_system)
                self.refresh()

        menu.addAction("Удалить", delete)
        menu.exec(self.table.viewport().mapToGlobal(pos))


class SearchTab(QWidget):
    def __init__(self, win, query=""):
        super().__init__()
        self.win = win
        self.kind = "search"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 20)
        lay.setSpacing(12)
        title = QLabel("Поиск")
        title.setObjectName("Title")
        lay.addWidget(title)
        self.query = QLineEdit(query, placeholderText="Текст или #тег")
        self.query.textChanged.connect(lambda: self.timer.start())
        lay.addWidget(self.query)
        self.count = muted("")
        lay.addWidget(self.count)
        self.results = QListWidget()
        self.results.setObjectName("Plain")
        self.results.setWordWrap(True)
        self.results.itemActivated.connect(lambda it: self.win.open_note(Path(it.data(Qt.UserRole))))
        self.results.itemClicked.connect(lambda it: self.win.open_note(Path(it.data(Qt.UserRole))))
        lay.addWidget(self.results, 1)
        self.timer = QTimer(self, singleShot=True, interval=200, timeout=self.run)
        self.run()

    def run(self):
        hits = self.win.vault.search(self.query.text())
        self.results.clear()
        for path, snippet in hits:
            item = QListWidgetItem(f"{path.stem}\n{snippet}" if snippet else path.stem)
            item.setData(Qt.UserRole, str(path))
            self.results.addItem(item)
        self.count.setText(f"Найдено: {len(hits)}" if self.query.text().strip() else "Введите запрос")


class GraphTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.kind = "graph"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        head = QHBoxLayout()
        head.setContentsMargins(28, 18, 18, 8)
        title = QLabel("Граф связей")
        title.setObjectName("Title")
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(muted("Двойной щелчок — открыть заметку, колесо — масштаб"))
        lay.addLayout(head)
        self.view = GraphView(win.colors)
        self.view.open_note.connect(lambda p: self.win.open_note(Path(p)))
        lay.addWidget(self.view, 1)
        self.refresh()

    def refresh(self):
        self.view.c = self.win.colors
        notes, edges = self.win.vault.graph()
        cur = self.win.current_note_path()
        self.view.set_graph(notes, edges, cur)


# ====================================================================== dialogs
class QuickSwitcher(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Перейти к заметке")
        self.setMinimumSize(520, 420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        self.edit = QLineEdit(placeholderText="Название заметки… (Enter — открыть или создать)")
        self.list = QListWidget()
        self.list.setObjectName("Plain")
        lay.addWidget(self.edit)
        lay.addWidget(self.list, 1)
        self.notes = win.vault.notes()
        self.edit.textChanged.connect(self.filter)
        self.edit.returnPressed.connect(self.accept_current)
        self.list.itemActivated.connect(lambda _: self.accept_current())
        self.filter("")

    def filter(self, text):
        q = text.lower().strip()
        self.list.clear()
        for p in self.notes:
            rel = self.win.vault.rel(p)
            if not q or all(part in rel.lower() for part in q.split()):
                it = QListWidgetItem(p.stem + ("" if Path(rel).parent == Path(".") else f"   ·  {Path(rel).parent}"))
                it.setData(Qt.UserRole, str(p))
                self.list.addItem(it)
            if self.list.count() > 200:
                break
        if self.list.count():
            self.list.setCurrentRow(0)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Down, Qt.Key_Up):
            self.list.keyPressEvent(e)
            return
        super().keyPressEvent(e)

    def accept_current(self):
        it = self.list.currentItem()
        if it is not None:
            self.win.open_note(Path(it.data(Qt.UserRole)))
        elif self.edit.text().strip():
            self.win.open_note(self.win.vault.create_note(self.edit.text().strip()))
        self.accept()


class SettingsDialog(QDialog):
    """App settings: appearance, vault, and the vault trash (restore / empty into the macOS Trash)."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Настройки")
        self.setMinimumSize(600, 640)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.setSpacing(10)
        title = QLabel("Настройки")
        title.setObjectName("Title")
        lay.addWidget(title)

        # appearance
        lay.addWidget(section("Внешний вид"))
        row = QHBoxLayout()
        self.theme = QComboBox()
        for key, label in (("system", "Системная"), ("light", "Светлая"), ("dark", "Тёмная")):
            self.theme.addItem(label, key)
        self.theme.setCurrentIndex(max(0, self.theme.findData(win.settings.get("theme", "system"))))
        self.theme.currentIndexChanged.connect(lambda: win.set_theme(self.theme.currentData()))
        self.font_box = QSpinBox()
        self.font_box.setRange(10, 24)
        self.font_box.setValue(win.settings.get("font_size", 14))
        self.font_box.setSuffix(" pt")
        self.font_box.valueChanged.connect(win.set_font_size)
        self.mode = QComboBox()
        for key, label in MODES:
            self.mode.addItem(label, key)
        self.mode.setCurrentIndex(max(0, self.mode.findData(win.settings.get("mode", "split"))))
        self.mode.currentIndexChanged.connect(self._mode_changed)
        for label, w in (("Тема", self.theme), ("Шрифт", self.font_box), ("Новые вкладки", self.mode)):
            col = QVBoxLayout()
            col.addWidget(muted(label))
            col.addWidget(w)
            row.addLayout(col)
        lay.addLayout(row)

        # vault
        lay.addSpacing(8)
        lay.addWidget(section("Хранилище"))
        lay.addWidget(muted(str(win.vault.root)))
        vrow = QHBoxLayout()
        vrow.addWidget(QPushButton("Показать в Finder", clicked=lambda: reveal_in_finder(win.vault.root)))
        vrow.addWidget(QPushButton("Открыть другое…", clicked=self._other_vault))
        vrow.addStretch(1)
        lay.addLayout(vrow)

        # trash
        lay.addSpacing(8)
        lay.addWidget(section("Корзина"))
        self.trash_info = muted("")
        lay.addWidget(self.trash_info)
        self.trash_list = QListWidget()
        self.trash_list.setObjectName("Plain")
        self.trash_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        lay.addWidget(self.trash_list, 1)
        trow = QHBoxLayout()
        self.restore_btn = QPushButton("Восстановить", clicked=self._restore)
        trow.addWidget(self.restore_btn)
        trow.addWidget(QPushButton("Показать папку", clicked=self._reveal_trash))
        trow.addStretch(1)
        self.empty_btn = QPushButton("Очистить корзину", clicked=self._empty)
        self.empty_btn.setObjectName("Accent")
        trow.addWidget(self.empty_btn)
        lay.addLayout(trow)
        self.direct = QCheckBox("Удалять сразу в Корзину macOS (минуя корзину хранилища)")
        self.direct.setChecked(bool(win.settings.get("delete_to_system_trash")))
        self.direct.toggled.connect(self._direct_changed)
        lay.addWidget(self.direct)
        lay.addWidget(muted("«Очистить корзину» перемещает всё удалённое в Корзину macOS — оттуда его можно "
                            "вернуть («Вернуть» в Finder) или удалить навсегда."))
        close = QHBoxLayout()
        close.addStretch(1)
        close.addWidget(QPushButton("Готово", clicked=self.accept))
        lay.addLayout(close)
        self.refresh_trash()

    def _mode_changed(self):
        self.win.settings["mode"] = self.mode.currentData()
        self.win.settings.save()

    def _direct_changed(self, on):
        self.win.settings["delete_to_system_trash"] = bool(on)
        self.win.settings.save()

    def _other_vault(self):
        self.accept()
        self.win._choose_vault()

    def _reveal_trash(self):
        self.win.vault.trash_dir.mkdir(exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.win.vault.trash_dir)))

    def refresh_trash(self):
        items = self.win.vault.trash_items()
        self.trash_list.clear()
        for path, original, when, size in items:
            when = when.replace("T", " ") if when else ""
            it = QListWidgetItem(f"{original}\n{when}  ·  {human_size(size)}".strip())
            it.setData(Qt.UserRole, str(path))
            self.trash_list.addItem(it)
        total = sum(i[3] for i in items)
        self.trash_info.setText(f"В корзине хранилища: {len(items)} · {human_size(total)}" if items
                                else "Корзина хранилища пуста.")
        self.empty_btn.setEnabled(bool(items))
        self.restore_btn.setEnabled(bool(items))

    def _restore(self):
        selected = self.trash_list.selectedItems()
        if not selected:
            self.win.status.showMessage("Выберите, что восстановить", 3000)
            return
        restored = [self.win.vault.restore(Path(it.data(Qt.UserRole))) for it in selected]
        self.refresh_trash()
        self.win.refresh_side()
        self.win.status.showMessage(f"Восстановлено: {len(restored)}", 4000)
        if len(restored) == 1 and restored[0].suffix == ".md":
            self.win.open_note(restored[0])

    def _empty(self):
        n = self.trash_list.count()
        if QMessageBox.question(self, "Очистить корзину",
                                f"Переместить {n} объект(ов) из корзины хранилища в Корзину macOS?") != QMessageBox.Yes:
            return
        moved, errors = self.win.vault.empty_trash()
        self.refresh_trash()
        if errors:
            QMessageBox.warning(self, APP_NAME, "Не всё удалось переместить:\n" + "\n".join(errors[:10]))
        self.win.status.showMessage(f"Перемещено в Корзину macOS: {moved}", 5000)


class NotesModel(QSortFilterProxyModel):
    """Hide the attachments folder at the vault root."""

    def __init__(self, root):
        super().__init__()
        self.root = str(root)

    def data(self, index, role=Qt.DisplayRole):
        value = super().data(index, role)
        if role in (Qt.DisplayRole, Qt.EditRole) and isinstance(value, str) and value.endswith(".md"):
            return value[:-3]
        return value

    def filterAcceptsRow(self, row, parent):
        model = self.sourceModel()
        idx = model.index(row, 0, parent)
        if model.fileName(idx) == ATTACHMENTS and model.filePath(parent) == self.root:
            return False
        return True


# ====================================================================== main window
class MainWindow(QMainWindow):
    def __init__(self, app, vault_path=None):
        super().__init__()
        self.app = app
        self.settings = Settings()
        self.colors = LIGHT
        root = vault_path or self.settings.get("vault") or default_vault()
        self.vault = Vault(root)
        welcome = self.vault.ensure_welcome()
        self.task_index = TaskIndex(self.vault)
        self._reminded = set()
        self.settings["vault"] = str(self.vault.root)
        recent = [v for v in self.settings.get("recent_vaults", []) if v != str(self.vault.root)]
        self.settings["recent_vaults"] = [str(self.vault.root)] + recent[:7]
        self.settings.save()

        self.setWindowTitle(f"{APP_NAME} — {self.vault.root.name}")
        self.resize(1280, 820)
        self.setMinimumSize(980, 620)
        central = QWidget()
        central.setObjectName("Main")
        self.setCentralWidget(central)
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self._build_sidebar())
        self.tabs = QTabWidget()
        self.tabs.setObjectName("DocTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._tab_changed)
        self.empty = self._build_empty()
        self.center = QStackedWidget()
        self.center.addWidget(self.empty)
        self.center.addWidget(self.tabs)
        h.addWidget(self.center, 1)
        self.right = self._build_right()
        h.addWidget(self.right)
        self.right.setVisible(bool(self.settings.get("right_panel", True)))

        self.status = self.statusBar()
        self.apply_theme()
        self._shortcuts()
        for rel in self.settings.get("open_tabs", []):
            p = self.vault.root / rel
            if p.exists():
                self.open_note(p)
        if welcome:
            self.open_note(welcome)
        self._update_center()
        self.refresh_side()
        self.focus_timer = QTimer(self, interval=2000, timeout=self._poll_external)
        self.focus_timer.start()
        self.reminder_timer = QTimer(self, interval=30000, timeout=self._check_reminders)
        self.reminder_timer.start()
        QTimer.singleShot(3000, self._check_reminders)

    # ------------------------------------------------------------ building
    def _build_sidebar(self):
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(280)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(14, 18, 14, 12)
        lay.setSpacing(8)
        logo_row = QHBoxLayout()
        spark = QLabel(LOGO)
        spark.setObjectName("Epsilon")
        logo = QLabel(APP_NAME)
        logo.setObjectName("Logo")
        logo_row.addWidget(spark)
        logo_row.addWidget(logo)
        logo_row.addStretch(1)
        lay.addLayout(logo_row)

        self.search = QLineEdit(placeholderText="Поиск  ⇧⌘F")
        self.search.returnPressed.connect(lambda: self.open_search(self.search.text()))
        lay.addWidget(self.search)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        new_note = QPushButton("＋ Заметка")
        new_note.setObjectName("Accent")
        new_note.clicked.connect(lambda: self.new_note())
        actions.addWidget(new_note, 1)
        actions.addWidget(QPushButton("Сегодня", clicked=lambda: self.open_note(self.vault.daily_note())))
        lay.addLayout(actions)

        for icon, text, fn in (("▦", "Календарь", self.open_calendar), ("☰", "Ссылки", self.open_links), ("▤", "Файлы", self.open_files),
                               ("◎", "Граф", self.open_graph), ("⌕", "Поиск", lambda: self.open_search(""))):
            b = QPushButton(f"{icon}   {text}")
            b.setObjectName("NavButton")
            b.clicked.connect(fn)
            lay.addWidget(b)

        head = QHBoxLayout()
        head.addWidget(section("Заметки"))
        head.addStretch(1)
        add_folder = QPushButton("＋ папка")
        add_folder.setObjectName("Link")
        add_folder.clicked.connect(lambda: self.new_folder())
        head.addWidget(add_folder)
        lay.addSpacing(6)
        lay.addLayout(head)

        self.fs = QFileSystemModel(self)
        self.fs.setRootPath(str(self.vault.root))
        self.fs.setNameFilters(["*.md"])
        self.fs.setNameFilterDisables(False)
        self.fs.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)
        self.fs.setReadOnly(False)
        self.fs.fileRenamed.connect(self._fs_renamed)
        self.proxy = NotesModel(self.vault.root)
        self.proxy.setSourceModel(self.fs)
        self.tree = QTreeView()
        self.tree.setModel(self.proxy)
        self.tree.setRootIndex(self.proxy.mapFromSource(self.fs.index(str(self.vault.root))))
        for col in (1, 2, 3):
            self.tree.hideColumn(col)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setAnimated(False)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree.clicked.connect(self._tree_clicked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_menu)

        self.tag_list = QListWidget()
        self.tag_list.setObjectName("Plain")
        self.tag_list.itemClicked.connect(lambda it: self.open_search("#" + it.data(Qt.UserRole)))
        tags_box = QWidget()
        tl = QVBoxLayout(tags_box)
        tl.setContentsMargins(0, 6, 0, 0)
        tl.addWidget(section("Теги"))
        tl.addWidget(self.tag_list, 1)
        split = QSplitter(Qt.Vertical)
        split.addWidget(self.tree)
        split.addWidget(tags_box)
        split.setSizes([420, 160])
        split.setHandleWidth(1)
        lay.addWidget(split, 1)

        bottom = QHBoxLayout()
        self.vault_btn = QPushButton(f"▣  {self.vault.root.name}")
        self.vault_btn.setObjectName("Link")
        self.vault_btn.clicked.connect(self._vault_menu)
        self.theme_btn = QPushButton()
        self.theme_btn.setObjectName("Link")
        self.theme_btn.clicked.connect(self._cycle_theme)
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setObjectName("Link")
        self.settings_btn.setToolTip("Настройки  ⌘,")
        self.settings_btn.clicked.connect(self.open_settings)
        bottom.addWidget(self.vault_btn)
        bottom.addStretch(1)
        bottom.addWidget(self.theme_btn)
        bottom.addWidget(self.settings_btn)
        lay.addLayout(bottom)
        return side

    def _build_empty(self):
        w = QWidget()
        w.setObjectName("Main")
        lay = QVBoxLayout(w)
        lay.addStretch(2)
        t = QLabel(f'<span style="font-style:italic; color:{self.colors["accent"]};">{LOGO}</span>&nbsp;{APP_NAME}')
        t.setObjectName("Title")
        t.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)
        sub = muted("Ваши заметки, файлы и ссылки — локально.\n⌘N — новая заметка · ⌘O — открыть · ⇧⌘F — поиск")
        sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(sub)
        row = QHBoxLayout()
        row.addStretch(1)
        b = QPushButton("Новая заметка")
        b.setObjectName("Primary")
        b.clicked.connect(lambda: self.new_note())
        row.addWidget(b)
        row.addStretch(1)
        lay.addSpacing(12)
        lay.addLayout(row)
        lay.addStretch(3)
        return w

    def _build_right(self):
        panel = QFrame()
        panel.setObjectName("RightPanel")
        panel.setFixedWidth(250)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 18, 14, 14)
        lay.setSpacing(6)
        lay.addWidget(section("Оглавление"))
        self.outline = QListWidget()
        self.outline.setObjectName("Plain")
        self.outline.setWordWrap(True)
        self.outline.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.outline.itemClicked.connect(self._jump_heading)
        lay.addWidget(self.outline, 2)
        lay.addWidget(section("Обратные ссылки"))
        self.backlinks = QListWidget()
        self.backlinks.setObjectName("Plain")
        self.backlinks.itemClicked.connect(lambda it: self.open_note(Path(it.data(Qt.UserRole))))
        lay.addWidget(self.backlinks, 1)
        lay.addWidget(section("Теги заметки"))
        self.note_tags = muted("—")
        lay.addWidget(self.note_tags)
        self.note_stats = muted("")
        lay.addWidget(self.note_stats)
        return panel

    def _shortcuts(self):
        def sc(seq, fn):
            QShortcut(QKeySequence(seq), self, activated=fn)

        sc("Ctrl+N", lambda: self.new_note())
        sc("Ctrl+,", self.open_settings)
        sc("Ctrl+O", lambda: QuickSwitcher(self).exec())
        sc("Ctrl+Shift+C", self.open_calendar)
        sc("Ctrl+Shift+F", lambda: self.open_search(""))
        sc("Ctrl+W", lambda: self.close_tab(self.tabs.currentIndex()))
        sc("Ctrl+E", self._cycle_mode)
        sc("Ctrl+\\", self._toggle_right)
        sc("Ctrl+S", lambda: (self.current_tab() and getattr(self.current_tab(), "save", lambda: None)()))
        sc("Ctrl+=", lambda: self._font_delta(1))
        sc("Ctrl+-", lambda: self._font_delta(-1))

    # ------------------------------------------------------------ theme
    def _is_dark(self):
        mode = self.settings.get("theme", "system")
        if mode in ("dark", "light"):
            return mode == "dark"
        try:
            return self.app.styleHints().colorScheme() == Qt.ColorScheme.Dark
        except Exception:
            return self.app.palette().color(QPalette.Window).lightness() < 128

    def apply_theme(self):
        self.colors = DARK if self._is_dark() else LIGHT
        close_icon = resource_path("assets", "close.svg").as_posix()
        self.app.setStyleSheet(stylesheet(self.colors) + f"""
#DocTabs QTabBar::close-button {{ image: url("{close_icon}"); subcontrol-position: right; border-radius: 4px; }}
#DocTabs QTabBar::close-button:hover {{ background: {self.colors['hover']}; }}
""")
        self.theme_btn.setText({"system": "◐ Системная", "light": "○ Светлая", "dark": "● Тёмная"}
                               .get(self.settings.get("theme", "system")))
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab.kind == "note":
                tab.apply_colors(self.colors)
            elif tab.kind in ("graph", "calendar"):
                tab.refresh()

    def _cycle_theme(self):
        order = ["system", "light", "dark"]
        cur = self.settings.get("theme", "system")
        self.settings["theme"] = order[(order.index(cur) + 1) % 3 if cur in order else 0]
        self.settings.save()
        self.apply_theme()

    def _font_delta(self, d):
        size = max(10, min(24, self.settings.get("font_size", 14) + d))
        self.settings["font_size"] = size
        self.settings.save()
        for i in range(self.tabs.count()):
            if self.tabs.widget(i).kind == "note":
                self.tabs.widget(i).apply_font(size)

    # ------------------------------------------------------------ tabs
    def current_tab(self):
        return self.tabs.currentWidget()

    def current_note_path(self):
        tab = self.current_tab()
        return tab.path if tab is not None and tab.kind == "note" else None

    def _find_tab(self, kind, path=None):
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab.kind == kind and (path is None or Path(tab.path) == Path(path)):
                return i
        return -1

    def _add_tab(self, widget, title):
        idx = self.tabs.addTab(widget, title)
        self.tabs.setCurrentIndex(idx)
        self._update_center()
        return idx

    def open_note(self, path, line=None):
        path = Path(path)
        if path.suffix.lower() != ".md":
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            return
        idx = self._find_tab("note", path)
        if idx >= 0:
            self.tabs.setCurrentIndex(idx)
            if line is not None:
                self._goto_line(self.tabs.widget(idx), line)
            return
        tab = NoteTab(self, path, self.settings.get("mode", "split"))
        tab.open_target.connect(self.open_target)
        tab.show_tag.connect(lambda t: self.open_search("#" + t))
        tab.status.connect(lambda m: self.status.showMessage(m, 4000))
        tab.renamed.connect(self._note_renamed)
        tab.saved.connect(lambda _p: self._note_saved())
        self._add_tab(tab, path.stem)
        self._save_open_tabs()
        if line is not None:
            self._goto_line(tab, line)

    def _goto_line(self, tab, line):
        from PySide6.QtGui import QTextCursor

        if tab.mode == "read":
            tab.set_mode("split")
        block = tab.editor.document().findBlockByNumber(int(line))
        if block.isValid():
            c = QTextCursor(block)
            c.movePosition(QTextCursor.EndOfBlock)
            tab.editor.setTextCursor(c)
            tab.editor.centerCursor()
            tab.editor.setFocus()

    def open_target(self, name):
        path = self.vault.resolve(name)
        if path is None:
            folder = self.current_note_path().parent if self.current_note_path() else self.vault.root
            path = self.vault.create_note(name, folder)
            self.status.showMessage(f"Создана заметка «{path.stem}»", 4000)
        self.open_note(path)

    def _singleton(self, kind, factory, title):
        idx = self._find_tab(kind)
        if idx >= 0:
            self.tabs.setCurrentIndex(idx)
            tab = self.tabs.widget(idx)
            if hasattr(tab, "refresh"):
                tab.refresh()
            return tab
        tab = factory()
        self._add_tab(tab, title)
        return tab

    def open_links(self):
        self._singleton("links", lambda: LinksTab(self), "☰ Ссылки")

    def open_files(self):
        self._singleton("files", lambda: FilesTab(self), "▤ Файлы")

    def open_calendar(self):
        self._singleton("calendar", lambda: CalendarTab(self), "▦ Календарь")

    def reload_open_notes(self):
        """Pick up edits made to note files outside the editor (e.g. ticking a task in the calendar)."""
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab.kind == "note" and not tab.save_timer.isActive() and tab.path.exists():
                if self.vault.read(tab.path) != tab.editor.toPlainText():
                    pos = tab.editor.textCursor().position()
                    tab.load()
                    c = tab.editor.textCursor()
                    c.setPosition(min(pos, len(tab.editor.toPlainText())))
                    tab.editor.setTextCursor(c)

    def _check_reminders(self):
        now = dt.datetime.now()
        try:
            due = [t for t in self.task_index.on(now.date()) if t.time and not t.done]
        except Exception:
            return
        for t in due:
            when = t.when
            if when <= now < when + dt.timedelta(minutes=5) and t.key not in self._reminded:
                self._reminded.add(t.key)
                notify("Epsilon — " + t.time.strftime("%H:%M"), t.text)
                self.status.showMessage(f"⏰ {t.time.strftime('%H:%M')}  {t.text}", 15000)

    def open_graph(self):
        self._singleton("graph", lambda: GraphTab(self), "◎ Граф")

    def open_search(self, query):
        tab = self._singleton("search", lambda: SearchTab(self, query), "⌕ Поиск")
        if query:
            tab.query.setText(query)
        tab.query.setFocus()

    def close_tab(self, index):
        if index < 0:
            return
        tab = self.tabs.widget(index)
        if tab.kind == "note":
            tab.save()
        self.tabs.removeTab(index)
        tab.deleteLater()
        self._update_center()
        self._save_open_tabs()

    def _update_center(self):
        self.center.setCurrentWidget(self.tabs if self.tabs.count() else self.empty)

    def _tab_changed(self, _i):
        self.refresh_side()
        tab = self.current_tab()
        # outline/backlinks only make sense next to a note
        self.right.setVisible(bool(self.settings.get("right_panel", True)) and (tab is None or tab.kind == "note"))
        if tab is not None and tab.kind == "calendar":
            tab.refresh()
        if tab is not None and tab.kind == "note":
            tab.reload_if_changed()
            path = tab.path
            for i in range(self.tabs.count()):
                if self.tabs.widget(i) is tab:
                    self.tabs.setTabText(i, path.stem)
            src = self.fs.index(str(path))
            self.tree.setCurrentIndex(self.proxy.mapFromSource(src))

    def _save_open_tabs(self):
        tabs = []
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab.kind == "note":
                try:
                    tabs.append(self.vault.rel(tab.path))
                except ValueError:
                    pass
        self.settings["open_tabs"] = tabs[-12:]
        self.settings.save()

    def _cycle_mode(self):
        tab = self.current_tab()
        if tab is None or tab.kind != "note":
            return
        keys = [k for k, _ in MODES]
        mode = keys[(keys.index(tab.mode) + 1) % len(keys)]
        tab.set_mode(mode)
        self.settings["mode"] = mode
        self.settings.save()

    def _toggle_right(self):
        self.settings["right_panel"] = not self.settings.get("right_panel", True)
        tab = self.current_tab()
        self.right.setVisible(self.settings["right_panel"] and (tab is None or tab.kind == "note"))
        self.settings.save()

    # ------------------------------------------------------------ side panels
    def _note_saved(self):
        self.side_timer = getattr(self, "side_timer", None) or QTimer(self, singleShot=True, interval=800,
                                                                     timeout=self.refresh_side)
        self.side_timer.start()

    def refresh_side(self):
        cal = self._find_tab("calendar")
        if cal >= 0 and self.tabs.currentIndex() != cal:
            self.tabs.widget(cal).refresh()
        tags = self.vault.tags()
        self.tag_list.clear()
        for t, n in list(tags.items())[:200]:
            it = QListWidgetItem(f"#{t}   {n}")
            it.setData(Qt.UserRole, t)
            self.tag_list.addItem(it)
        tab = self.current_tab()
        self.outline.clear()
        self.backlinks.clear()
        if tab is None or tab.kind != "note":
            self.note_tags.setText("—")
            self.note_stats.setText("")
            return
        text = tab.editor.toPlainText()
        for level, title, line in self.vault.outline(text):
            it = QListWidgetItem("    " * (level - 1) + title)
            it.setData(Qt.UserRole, line)
            self.outline.addItem(it)
        for p in self.vault.backlinks(tab.path):
            it = QListWidgetItem(p.stem)
            it.setData(Qt.UserRole, str(p))
            self.backlinks.addItem(it)
        if not self.backlinks.count():
            self.backlinks.addItem(QListWidgetItem("Нет"))
        info = self.vault.info(tab.path) if tab.path.exists() else None
        self.note_tags.setText(" ".join("#" + t for t in sorted(info.tags)) if info and info.tags else "—")
        words = len(text.split())
        self.note_stats.setText(f"{words} слов · {len(text)} символов")

    def _jump_heading(self, item):
        tab = self.current_tab()
        line = item.data(Qt.UserRole)
        if tab is None or tab.kind != "note" or line is None:
            return
        from PySide6.QtGui import QTextCursor

        block = tab.editor.document().findBlockByNumber(int(line))
        c = QTextCursor(block)
        tab.editor.setTextCursor(c)
        tab.editor.centerCursor()
        if tab.mode == "read":
            tab.reader.scrollToAnchor("")
        tab.editor.setFocus()

    # ------------------------------------------------------------ actions
    def _target_folder(self):
        idx = self.tree.currentIndex()
        if idx.isValid():
            p = Path(self.fs.filePath(self.proxy.mapToSource(idx)))
            return p if p.is_dir() else p.parent
        return self.vault.root

    def new_note(self, folder=None):
        path = self.vault.create_note("Без названия", folder or self._target_folder())
        self.open_note(path)
        tab = self.current_tab()
        tab.set_mode("edit" if self.settings.get("mode") == "read" else tab.mode)
        tab.title.setFocus()
        tab.title.selectAll()

    def new_folder(self, parent=None):
        name, ok = QInputDialog.getText(self, "Новая папка", "Название папки:")
        if ok and name.strip():
            self.vault.create_folder(name, parent or self._target_folder())

    def delete_path(self, path):
        path = Path(path)
        what = "папку" if path.is_dir() else "заметку"
        to_system = bool(self.settings.get("delete_to_system_trash"))
        where = "в Корзину macOS" if to_system else "в корзину хранилища"
        if QMessageBox.question(self, APP_NAME, f"Переместить {what} «{path.name}» {where}?") != QMessageBox.Yes:
            return
        for i in reversed(range(self.tabs.count())):
            tab = self.tabs.widget(i)
            if tab.kind == "note" and (tab.path == path or path in tab.path.parents):
                tab.save_timer.stop()
                self.tabs.removeTab(i)
                tab.deleteLater()
        try:
            self.vault.delete(path, to_system_trash=to_system)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
        self._update_center()
        self._save_open_tabs()
        self.refresh_side()

    def insert_into_current(self, text):
        tab = self.current_tab()
        for i in range(self.tabs.count()):
            if self.tabs.widget(i).kind == "note" and (tab is None or tab.kind != "note"):
                tab = self.tabs.widget(i)
                break
        if tab is None or tab.kind != "note":
            self.status.showMessage("Откройте заметку, чтобы вставить", 4000)
            return
        tab.editor.textCursor().insertText(text + "\n")
        self.tabs.setCurrentWidget(tab)

    def insert_file_link(self, path):
        tab = self.current_tab()
        target = tab if tab is not None and tab.kind == "note" else None
        if target is None:
            self.insert_into_current(f"[[{Path(path).name}]]")
        else:
            target.editor.textCursor().insertText(target.editor._link_for(Path(path)) + "\n")

    def _tree_clicked(self, idx):
        path = Path(self.fs.filePath(self.proxy.mapToSource(idx)))
        if path.is_file():
            self.open_note(path)

    def _tree_menu(self, pos):
        idx = self.tree.indexAt(pos)
        path = Path(self.fs.filePath(self.proxy.mapToSource(idx))) if idx.isValid() else self.vault.root
        folder = path if path.is_dir() else path.parent
        menu = QMenu(self)
        menu.addAction("Новая заметка", lambda: self.new_note(folder))
        menu.addAction("Новая папка", lambda: self.new_folder(folder))
        if idx.isValid():
            menu.addSeparator()

            def rename():
                name, ok = QInputDialog.getText(self, "Переименовать", "Новое имя:", text=path.stem)
                if ok and name.strip():
                    try:
                        new = self.vault.rename(path, name)
                    except Exception as exc:
                        QMessageBox.warning(self, APP_NAME, str(exc))
                        return
                    self._note_renamed(path, new)

            menu.addAction("Переименовать…", rename)
            menu.addAction("Показать в Finder", lambda: reveal_in_finder(path))
            menu.addSeparator()
            menu.addAction("Удалить", lambda: self.delete_path(path))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _note_renamed(self, old, new):
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab.kind == "note":
                if tab.path == old:
                    tab.path = new
                    tab.editor.note_path = new
                    tab.title.setText(new.stem)
                    self.tabs.setTabText(i, new.stem)
                elif old in tab.path.parents:
                    tab.path = new / tab.path.relative_to(old)
                    tab.editor.note_path = tab.path
                tab.reload_if_changed()
        self._save_open_tabs()
        self.refresh_side()

    def _fs_renamed(self, folder, old, new):
        self._note_renamed(Path(folder) / old, Path(folder) / new)

    def _poll_external(self):
        tab = self.current_tab()
        if tab is not None and tab.kind == "note" and self.isActiveWindow():
            tab.reload_if_changed()

    def open_settings(self):
        SettingsDialog(self).exec()

    def set_theme(self, mode):
        self.settings["theme"] = mode
        self.settings.save()
        self.apply_theme()

    def set_font_size(self, size):
        self._font_delta(size - self.settings.get("font_size", 14))

    def _vault_menu(self):
        menu = QMenu(self)
        menu.addAction("Открыть папку хранилища в Finder", lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.vault.root))))
        menu.addAction("Открыть другое хранилище…", self._choose_vault)
        recent = [v for v in self.settings.get("recent_vaults", []) if v != str(self.vault.root) and Path(v).exists()]
        if recent:
            menu.addSeparator()
            for v in recent:
                menu.addAction(f"↺  {Path(v).name}", lambda v=v: self.switch_vault(v))
        menu.exec(self.vault_btn.mapToGlobal(self.vault_btn.rect().topLeft()))

    def _choose_vault(self):
        folder = QFileDialog.getExistingDirectory(self, "Папка хранилища", str(self.vault.root.parent))
        if folder:
            self.switch_vault(folder)

    def switch_vault(self, folder):
        self.save_all()
        self.settings["vault"] = folder
        self.settings["open_tabs"] = []
        self.settings.save()
        new = MainWindow(self.app, folder)
        new.show()
        self.app.main_window = new
        self.close()

    def save_all(self):
        for i in range(self.tabs.count()):
            if self.tabs.widget(i).kind == "note":
                self.tabs.widget(i).save()

    def closeEvent(self, event):
        self.save_all()
        self._save_open_tabs()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    icon = resource_path("assets", "icon.png")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    app.main_window = MainWindow(app)
    app.main_window.show()
    try:
        app.styleHints().colorSchemeChanged.connect(lambda *_: app.main_window.apply_theme())
    except Exception:
        pass
    return app.exec()
