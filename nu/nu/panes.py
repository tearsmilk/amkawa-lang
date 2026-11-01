"""Things that live in editor tabs: code editor (+ find bar, breadcrumbs), image preview, diff, welcome."""
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImageReader, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget,
)

from . import APP_NAME, LOGO, __version__, icons, languages
from .editor import CodeEditor

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".icns", ".tiff", ".tif", ".heic", ".svg"}


class FindBar(QFrame):
    def __init__(self, pane):
        super().__init__(pane)
        self.setObjectName("FindBar")
        self.pane = pane
        self.matches = []
        self.index = -1
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 5, 6, 5)
        lay.setSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(2)
        self.expand = QToolButton()
        self.expand.setText("›")
        self.expand.setCheckable(True)
        self.expand.setToolTip("Заменить (⌥⌘F)")
        self.expand.toggled.connect(self._toggle_replace)
        row.addWidget(self.expand)
        self.find = QLineEdit()
        self.find.setPlaceholderText("Найти")
        self.find.setMinimumWidth(220)
        row.addWidget(self.find)
        self.toggles = {}
        for key, label, tip in (("case", "Aa", "Учитывать регистр"), ("word", "ab", "Слово целиком"),
                                ("regex", ".*", "Регулярное выражение")):
            b = QToolButton()
            b.setText(label)
            b.setCheckable(True)
            b.setToolTip(tip)
            b.toggled.connect(self.update_matches)
            row.addWidget(b)
            self.toggles[key] = b
        self.count = QLabel("Нет результатов")
        self.count.setObjectName("FindCount")
        row.addWidget(self.count)
        self.prev_btn = QToolButton()
        self.next_btn = QToolButton()
        self.close_btn = QToolButton()
        for b, tip, fn in ((self.prev_btn, "Предыдущее (⇧↩)", lambda: self.step(-1)),
                           (self.next_btn, "Следующее (↩)", lambda: self.step(1)), (self.close_btn, "Закрыть (Esc)", self.hide_bar)):
            b.setToolTip(tip)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        self.rrow = QWidget()
        rl = QHBoxLayout(self.rrow)
        rl.setContentsMargins(26, 0, 0, 0)
        rl.setSpacing(4)
        self.replace = QLineEdit()
        self.replace.setPlaceholderText("Заменить")
        rl.addWidget(self.replace)
        one = QPushButton("Заменить")
        one.clicked.connect(self.replace_one)
        rl.addWidget(one)
        allb = QPushButton("Все")
        allb.clicked.connect(self.replace_all)
        rl.addWidget(allb)
        lay.addWidget(self.rrow)
        self.rrow.hide()
        self.find.textChanged.connect(self.update_matches)
        self.find.installEventFilter(self)
        self.replace.installEventFilter(self)
        self.timer = QTimer(self, singleShot=True, interval=80, timeout=self._recount)
        self.hide()
        self.set_colors(pane.win.colors)

    def set_colors(self, c):
        self.prev_btn.setIcon(icons.glyph("chevron-up", c["muted"]))
        self.next_btn.setIcon(icons.glyph("chevron-down", c["muted"]))
        self.close_btn.setIcon(icons.glyph("close", c["muted"]))

    def eventFilter(self, obj, e):
        if e.type() == e.Type.KeyPress:
            if e.key() == Qt.Key_Escape:
                self.hide_bar()
                return True
            if e.key() in (Qt.Key_Return, Qt.Key_Enter):
                if obj is self.replace:
                    self.replace_all() if e.modifiers() & Qt.ControlModifier else self.replace_one()
                else:
                    self.step(-1 if e.modifiers() & Qt.ShiftModifier else 1)
                return True
        return super().eventFilter(obj, e)

    def _toggle_replace(self, on):
        self.rrow.setVisible(on)
        self.expand.setText("⌄" if on else "›")
        self.adjustSize()
        self.pane.place_findbar()

    def show_bar(self, replace=False):
        ed = self.pane.editor
        sel = ed.textCursor().selectedText()
        if sel and " " not in sel and len(sel) < 200:
            self.find.setText(sel)
        self.expand.setChecked(replace)
        self.show()
        self.adjustSize()
        self.pane.place_findbar()
        (self.replace if replace and self.find.text() else self.find).setFocus()
        self.find.selectAll()
        self.update_matches()

    def hide_bar(self):
        self.hide()
        self.matches = []
        self.pane.editor.set_find_matches([])
        self.pane.editor.setFocus()

    def update_matches(self, *_):
        self.timer.start()

    def _recount(self):
        ed = self.pane.editor
        if not self.isVisible():
            return
        t = self.toggles
        self.matches = ed.find_all(self.find.text(), t["case"].isChecked(), t["regex"].isChecked(), t["word"].isChecked())
        pos = ed.textCursor().selectionStart()
        self.index = next((i for i, m in enumerate(self.matches) if m.selectionStart() >= pos), 0 if self.matches else -1)
        self._show_current(move=False)

    def _show_current(self, move=True):
        ed = self.pane.editor
        cur = self.matches[self.index] if 0 <= self.index < len(self.matches) else None
        ed.set_find_matches(self.matches[:5000], cur)
        if self.matches:
            self.count.setText(f"{self.index + 1} из {len(self.matches)}" + ("+" if len(self.matches) >= 20000 else ""))
        else:
            self.count.setText("Нет результатов" if self.find.text() else "")
        if move and cur is not None:
            c = QTextCursor(cur)
            ed.setTextCursor(c)
            ed.centerCursor()

    def step(self, d):
        if not self.matches:
            self._recount()
        if not self.matches:
            return
        self.index = (self.index + d) % len(self.matches)
        self._show_current()

    def _replacement(self, cursor):
        text = self.replace.text()
        if self.toggles["regex"].isChecked():
            import re

            flags = 0 if self.toggles["case"].isChecked() else re.IGNORECASE
            try:
                return re.sub(self.find.text(), text, cursor.selectedText(), count=1, flags=flags)
            except re.error:
                return text
        return text

    def replace_one(self):
        if not self.matches:
            self._recount()
        if not (0 <= self.index < len(self.matches)):
            return
        cur = self.matches[self.index]
        cur.insertText(self._replacement(cur))
        self._recount()
        self._show_current()

    def replace_all(self):
        if not self.matches:
            self._recount()
        ed = self.pane.editor
        c = ed.textCursor()
        c.beginEditBlock()
        n = 0
        for cur in reversed(self.matches):
            cur.insertText(self._replacement(cur))
            n += 1
        c.endEditBlock()
        self._recount()
        self.pane.win.status_message(f"Заменено: {n}")


class EditorPane(QWidget):
    kind = "editor"
    title_changed = Signal()

    def __init__(self, win, path=None, share=None):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.crumbs = QLabel()
        self.crumbs.setObjectName("Breadcrumbs")
        lay.addWidget(self.crumbs)
        self.editor = CodeEditor(win.colors, win.settings, path, share=share.editor if share else None)
        lay.addWidget(self.editor, 1)
        self.untitled = None
        if path and share is None:
            self.editor.load(path)
        self.editor.modified_changed.connect(lambda *_: self.title_changed.emit())
        self.editor.cursor_moved.connect(lambda l, c: win.update_cursor_status(self, l, c))
        self.findbar = FindBar(self)
        self.update_crumbs()

    @property
    def path(self):
        return self.editor.path

    def title(self):
        if self.path:
            return self.path.name
        return self.untitled or "Без названия"

    def modified(self):
        return self.editor.document().isModified()

    def update_crumbs(self):
        if self.path:
            root = self.win.folder
            try:
                parts = Path(self.path).relative_to(root).parts if root else Path(self.path).parts[-3:]
            except ValueError:
                parts = Path(self.path).parts[-3:]
            self.crumbs.setText("  ›  ".join(parts))
            self.crumbs.setToolTip(str(self.path))
        else:
            self.crumbs.setText(self.title())

    def place_findbar(self):
        fb = self.findbar
        fb.adjustSize()
        w = fb.sizeHint().width()
        fb.setGeometry(self.width() - w - 22, self.crumbs.height() + 4, w, fb.sizeHint().height())
        fb.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.findbar.isVisible():
            self.place_findbar()

    def set_colors(self, colors):
        self.editor.set_colors(colors)
        self.findbar.set_colors(colors)


class ImagePane(QScrollArea):
    kind = "image"
    title_changed = Signal()

    def __init__(self, win, path):
        super().__init__()
        self.win = win
        self.path = Path(path)
        self.setFrameShape(QFrame.NoFrame)
        self.setAlignment(Qt.AlignCenter)
        label = QLabel()
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        img = reader.read()
        if img.isNull():
            label.setText(f"Не удалось открыть изображение\n{reader.errorString()}")
            label.setObjectName("Muted")
        else:
            label.setPixmap(QPixmap.fromImage(img))
            label.setToolTip(f"{img.width()} × {img.height()}")
        self.setWidget(label)

    def title(self):
        return self.path.name

    def modified(self):
        return False

    def set_colors(self, colors):
        pass


class DiffPane(EditorPane):
    kind = "diff"

    def __init__(self, win, title, text):
        super().__init__(win)
        self.untitled = title
        self.editor.setPlainText(text)
        self.editor.set_language(languages.BY_ID["diff"])
        self.editor.setReadOnly(True)
        self.editor.document().setModified(False)
        self.update_crumbs()


class WelcomePane(QScrollArea):
    kind = "welcome"
    title_changed = Signal()
    path = None

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setFrameShape(QFrame.NoFrame)
        self.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName("Main")
        self.setWidget(body)
        outer = QHBoxLayout(body)
        outer.addStretch(1)
        col = QVBoxLayout()
        col.setSpacing(6)
        col.addStretch(1)
        head = QHBoxLayout()
        logo = QLabel(LOGO)
        logo.setObjectName("BigLogo")
        head.addWidget(logo)
        tcol = QVBoxLayout()
        tcol.addStretch(1)
        name = QLabel(APP_NAME)
        name.setObjectName("Title")
        tcol.addWidget(name)
        sub = QLabel(f"Редактор кода · версия {__version__}")
        sub.setObjectName("Muted")
        tcol.addWidget(sub)
        tcol.addStretch(1)
        head.addLayout(tcol)
        head.addStretch(1)
        col.addLayout(head)
        col.addSpacing(18)
        cols = QHBoxLayout()
        cols.setSpacing(60)
        start = QVBoxLayout()
        start.setSpacing(2)
        s = QLabel("НАЧАЛО")
        s.setObjectName("Section")
        start.addWidget(s)
        for text, fn in (("Открыть папку…", win.open_folder_dialog), ("Открыть файл…", win.open_file_dialog),
                         ("Новый файл", win.new_file), ("Новый терминал", win.new_terminal),
                         ("Палитра команд", lambda: win.show_palette(">"))):
            b = QPushButton(text)
            b.setObjectName("Link")
            b.clicked.connect(fn)
            start.addWidget(b)
        start.addStretch(1)
        cols.addLayout(start)
        recent = QVBoxLayout()
        recent.setSpacing(2)
        r = QLabel("НЕДАВНИЕ")
        r.setObjectName("Section")
        recent.addWidget(r)
        items = [p for p in win.settings.get("recent", []) if Path(p).exists()][:8]
        for p in items:
            b = QPushButton(f"{Path(p).name}    {str(Path(p).parent).replace(str(Path.home()), '~')}")
            b.setObjectName("Link")
            b.clicked.connect(lambda _=False, p=p: win.open_path(p))
            recent.addWidget(b)
        if not items:
            m = QLabel("Пока пусто")
            m.setObjectName("Muted")
            recent.addWidget(m)
        recent.addStretch(1)
        cols.addLayout(recent)
        col.addLayout(cols)
        col.addSpacing(24)
        k = QLabel("ГОРЯЧИЕ КЛАВИШИ")
        k.setObjectName("Section")
        col.addWidget(k)
        keys = [("⌘P", "быстрое открытие файла"), ("⇧⌘P", "палитра команд"), ("⇧⌘F", "поиск по файлам"),
                ("⌃`", "терминал"), ("F5", "запустить файл"), ("⌘/", "закомментировать"), ("⌘\\", "разделить редактор")]
        for key, what in keys:
            l = QLabel(f"<span style='font-family:Menlo,monospace'>{key}</span>&nbsp;&nbsp;&nbsp;{what}")
            l.setObjectName("Muted")
            col.addWidget(l)
        col.addStretch(2)
        outer.addLayout(col)
        outer.addStretch(1)

    def title(self):
        return "Добро пожаловать"

    def modified(self):
        return False

    def set_colors(self, colors):
        pass
