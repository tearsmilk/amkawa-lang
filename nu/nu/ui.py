"""Ню main window: activity bar, side bar (explorer / search / git), editor groups with tabs,
terminal panel, status bar, menus, command palette."""
import os
import shlex
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog,
    QLabel, QMainWindow, QMessageBox, QPushButton, QSpinBox, QSplitter, QStackedWidget, QTabWidget, QToolButton,
    QVBoxLayout, QWidget,
)

from . import APP_NAME, LOGO, __version__, icons, languages
from .explorer import Explorer, reveal
from .palette import Palette
from .panes import IMAGE_EXT, DiffPane, EditorPane, ImagePane, WelcomePane
from .paths import Settings, resource_path
from .scm import ScmPanel
from .search import SearchPanel
from .terminal import TerminalWidget
from .theme import DARK, LIGHT, MONO_FAMILIES, stylesheet

MAC = sys.platform == "darwin"
CTRL = "Meta" if MAC else "Ctrl"  # the physical Control key (⌃) on macOS


def native(seq):
    return QKeySequence(seq).toString(QKeySequence.NativeText) if seq else ""


class EditorGroup(QTabWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setObjectName("EditorTabs")
        self.setDocumentMode(True)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setUsesScrollButtons(True)
        self.setElideMode(Qt.ElideNone)
        self.tabCloseRequested.connect(lambda i: win.close_tab(self, i))
        self.currentChanged.connect(lambda _i: win.tab_changed(self))
        self.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabBar().customContextMenuRequested.connect(self._menu)
        self.tabBar().tabBarDoubleClicked.connect(lambda i: i < 0 and win.new_file())

    def panes(self):
        return [self.widget(i) for i in range(self.count())]

    def _menu(self, pos):
        from PySide6.QtWidgets import QMenu

        i = self.tabBar().tabAt(pos)
        if i < 0:
            return
        pane = self.widget(i)
        m = QMenu(self)
        m.addAction("Закрыть", lambda: self.win.close_tab(self, self.indexOf(pane)))
        m.addAction("Закрыть другие", lambda: self.win.close_others(self, pane))
        m.addAction("Закрыть все", lambda: self.win.close_others(self, None))
        if getattr(pane, "path", None):
            m.addSeparator()
            m.addAction("Открыть сбоку", lambda: self.win.split_editor(pane))
            m.addAction("Показать в Finder", lambda: reveal(pane.path))
            m.addAction("Показать в проводнике", lambda: self.win.reveal_in_explorer(pane.path))
            m.addAction("Копировать путь", lambda: QApplication.clipboard().setText(str(pane.path)))
        m.exec(self.tabBar().mapToGlobal(pos))


class SettingsDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        s = win.settings
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 20)
        t = QLabel("Настройки")
        t.setObjectName("Title")
        lay.addWidget(t)
        form = QFormLayout()
        form.setVerticalSpacing(10)
        self.theme = QComboBox()
        for key, label in (("system", "Системная"), ("light", "Светлая"), ("dark", "Тёмная")):
            self.theme.addItem(label, key)
        self.theme.setCurrentIndex(self.theme.findData(s.get("theme", "system")))
        form.addRow("Тема", self.theme)
        self.family = QComboBox()
        self.family.addItem("Системный моноширинный", "")
        from PySide6.QtGui import QFontDatabase

        fams = set(QFontDatabase.families())
        for f in MONO_FAMILIES:
            if f in fams:
                self.family.addItem(f, f)
        self.family.setCurrentIndex(max(0, self.family.findData(s.get("font_family", ""))))
        form.addRow("Шрифт", self.family)
        self.size = QSpinBox()
        self.size.setRange(8, 40)
        self.size.setValue(int(s.get("font_size", 13)))
        form.addRow("Размер шрифта", self.size)
        self.tsize = QSpinBox()
        self.tsize.setRange(8, 40)
        self.tsize.setValue(int(s.get("terminal_font_size", 12)))
        form.addRow("Шрифт терминала", self.tsize)
        self.tab = QSpinBox()
        self.tab.setRange(1, 16)
        self.tab.setValue(int(s.get("tab_size", 4)))
        form.addRow("Ширина табуляции", self.tab)
        self.shell = QComboBox()
        self.shell.setEditable(True)
        for sh in ("", "/bin/zsh", "/bin/bash", "/bin/sh"):
            self.shell.addItem(sh or "Оболочка по умолчанию", sh)
        idx = self.shell.findData(s.get("shell", ""))
        if idx >= 0:
            self.shell.setCurrentIndex(idx)
        else:
            self.shell.setEditText(s.get("shell", ""))
        form.addRow("Терминал", self.shell)
        lay.addLayout(form)
        self.checks = {}
        for key, label in (("insert_spaces", "Пробелы вместо табуляции"), ("word_wrap", "Перенос строк"),
                           ("indent_guides", "Направляющие отступов"), ("auto_close", "Автозакрытие скобок и кавычек"),
                           ("autocomplete", "Автодополнение слов"), ("autosave", "Автосохранение"),
                           ("trim_trailing", "Удалять пробелы в конце строк при сохранении"),
                           ("final_newline", "Пустая строка в конце файла")):
            cb = QCheckBox(label)
            cb.setChecked(bool(s.get(key)))
            lay.addWidget(cb)
            self.checks[key] = cb
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Сохранить")
        ok.setObjectName("Accent")
        ok.clicked.connect(self.save)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addSpacing(8)
        lay.addLayout(row)

    def save(self):
        s = self.win.settings
        s["theme"] = self.theme.currentData()
        s["font_family"] = self.family.currentData()
        s["font_size"] = self.size.value()
        s["terminal_font_size"] = self.tsize.value()
        s["tab_size"] = self.tab.value()
        shell = self.shell.currentText().strip()
        s["shell"] = "" if shell == "Оболочка по умолчанию" else shell
        for key, cb in self.checks.items():
            s[key] = cb.isChecked()
        s.save()
        self.win.apply_settings()
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.settings = Settings()
        self.colors = LIGHT
        self.folder = None
        self.groups = []
        self.active_group = None
        self._untitled = 0
        self._last_editor = None
        self.setWindowTitle(f"{LOGO} {APP_NAME}")
        self.resize(1400, 880)
        self.setMinimumSize(900, 560)
        self.setUnifiedTitleAndToolBarOnMac(True)

        central = QWidget()
        central.setObjectName("Main")
        self.setCentralWidget(central)
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self._build_activity())
        self.hsplit = QSplitter(Qt.Horizontal)
        self.hsplit.setHandleWidth(1)
        self.hsplit.setChildrenCollapsible(False)
        h.addWidget(self.hsplit, 1)
        self.sidebar = self._build_sidebar()
        self.hsplit.addWidget(self.sidebar)
        self.vsplit = QSplitter(Qt.Vertical)
        self.vsplit.setHandleWidth(1)
        self.vsplit.setChildrenCollapsible(False)
        self.editors = QSplitter(Qt.Horizontal)
        self.editors.setHandleWidth(1)
        self.vsplit.addWidget(self.editors)
        self.panel = self._build_panel()
        self.vsplit.addWidget(self.panel)
        self.vsplit.setSizes([620, 240])
        self.hsplit.addWidget(self.vsplit)
        self.hsplit.setSizes([270, 1100])
        self.hsplit.setStretchFactor(1, 1)
        self.add_group()
        self._build_status()
        self._build_menus()
        self.apply_theme()
        self.panel.setVisible(False)
        self.sidebar.setVisible(bool(self.settings.get("sidebar", True)))

        self.poll_timer = QTimer(self, interval=2500, timeout=self._poll_files)
        self.poll_timer.start()
        self.autosave_timer = QTimer(self, singleShot=True, interval=1000, timeout=self._autosave)
        self.git_timer = QTimer(self, singleShot=True, interval=400, timeout=self.refresh_git)
        app.applicationStateChanged.connect(self._app_state)
        self._restore()

    # ================================================================== building
    def _build_activity(self):
        bar = QWidget()
        bar.setObjectName("ActivityBar")
        bar.setFixedWidth(52)
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(0, 8, 0, 8)
        lay.setSpacing(2)
        logo = QLabel(LOGO)
        logo.setObjectName("Nu")
        logo.setAlignment(Qt.AlignCenter)
        logo.setToolTip(APP_NAME)
        lay.addWidget(logo)
        lay.addSpacing(6)
        self.activity = QButtonGroup(self)
        self.activity.setExclusive(False)
        self.activity_buttons = {}
        for key, tip in (("files", "Проводник (⇧⌘E)"), ("search", "Поиск (⇧⌘F)"), ("git", "Система контроля версий (⌃⇧G)")):
            b = QToolButton()
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setIconSize(QSize(24, 24))
            b.setFixedSize(52, 46)
            b.clicked.connect(lambda _=False, k=key: self.show_side(k, toggle=True))
            lay.addWidget(b)
            self.activity_buttons[key] = b
        lay.addStretch(1)
        self.run_btn = QToolButton()
        self.run_btn.setToolTip("Запустить файл (F5)")
        self.run_btn.setIconSize(QSize(22, 22))
        self.run_btn.setFixedSize(52, 42)
        self.run_btn.clicked.connect(self.run_file)
        lay.addWidget(self.run_btn)
        self.term_btn = QToolButton()
        self.term_btn.setToolTip("Терминал (⌃`)")
        self.term_btn.setIconSize(QSize(22, 22))
        self.term_btn.setFixedSize(52, 42)
        self.term_btn.clicked.connect(self.toggle_terminal)
        lay.addWidget(self.term_btn)
        self.gear_btn = QToolButton()
        self.gear_btn.setToolTip("Настройки (⌘,)")
        self.gear_btn.setIconSize(QSize(22, 22))
        self.gear_btn.setFixedSize(52, 42)
        self.gear_btn.clicked.connect(self.open_settings)
        lay.addWidget(self.gear_btn)
        return bar

    def _build_sidebar(self):
        side = QStackedWidget()
        side.setObjectName("SideBar")
        side.setMinimumWidth(190)
        self.explorer = Explorer(self)
        self.explorer.open_file.connect(lambda p: self.open_file(p))
        self.explorer.open_terminal.connect(lambda p: self.new_terminal(p))
        self.explorer.path_renamed.connect(self._path_renamed)
        self.explorer.path_deleted.connect(self._path_deleted)
        self.search = SearchPanel(self)
        self.search.open_location.connect(self._open_location)
        self.scm = ScmPanel(self)
        self.scm.open_file.connect(lambda p: self.open_file(p))
        self.scm.open_diff.connect(self.open_diff)
        for w in (self.explorer, self.search, self.scm):
            side.addWidget(w)
        self.side_keys = {"files": self.explorer, "search": self.search, "git": self.scm}
        return side

    def _build_panel(self):
        panel = QWidget()
        panel.setObjectName("Panel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        self.terms = QTabWidget()
        self.terms.setObjectName("PanelTabs")
        self.terms.setDocumentMode(True)
        self.terms.setTabsClosable(True)
        self.terms.setMovable(True)
        self.terms.tabCloseRequested.connect(self.kill_terminal)
        corner = QWidget()
        cl = QHBoxLayout(corner)
        cl.setContentsMargins(0, 0, 6, 0)
        cl.setSpacing(2)
        self.panel_buttons = []
        for glyph, tip, fn in (("plus", "Новый терминал (⌃⇧`)", lambda: self.new_terminal()),
                               ("trash", "Закрыть терминал", lambda: self.kill_terminal(self.terms.currentIndex())),
                               ("close", "Скрыть панель (⌘J)", lambda: self.panel.setVisible(False))):
            b = QToolButton()
            b.setToolTip(tip)
            b.setProperty("glyph", glyph)
            b.clicked.connect(fn)
            cl.addWidget(b)
            self.panel_buttons.append(b)
        self.terms.setCornerWidget(corner, Qt.TopRightCorner)
        lay.addWidget(self.terms)
        return panel

    def _build_status(self):
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        self.branch_btn = QPushButton("")
        self.branch_btn.setObjectName("Branch")
        self.branch_btn.clicked.connect(lambda: self.show_side("git"))
        sb.addWidget(self.branch_btn)
        self.msg = QLabel("")
        sb.addWidget(self.msg, 1)
        self.pos_btn = QPushButton("")
        self.pos_btn.clicked.connect(lambda: self.show_palette(":"))
        self.indent_btn = QPushButton("")
        self.indent_btn.clicked.connect(self._indent_menu)
        self.enc_btn = QPushButton("")
        self.enc_btn.clicked.connect(self._encoding_menu)
        self.eol_btn = QPushButton("")
        self.eol_btn.clicked.connect(self._toggle_eol)
        self.lang_btn = QPushButton("")
        self.lang_btn.clicked.connect(self.pick_language)
        for w in (self.pos_btn, self.indent_btn, self.enc_btn, self.eol_btn, self.lang_btn):
            sb.addPermanentWidget(w)

    # ------------------------------------------------------------------ menus / commands
    def _build_menus(self):
        self._commands = []
        mb = self.menuBar()

        def menu(title):
            return mb.addMenu(title)

        def act(m, cid, title, fn, shortcut=None, checkable=False):
            a = QAction(title, self)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            a.triggered.connect(lambda checked=False: fn())
            a.setCheckable(checkable)
            if m is not None:
                m.addAction(a)
            self.addAction(a)
            self._commands.append({"id": cid, "title": f"{m.title().replace('&', '')}: {title}" if m else title,
                                   "shortcut": native(shortcut), "action": a})
            return a

        ed = lambda name, *args: (lambda: self._ed(name, *args))  # noqa: E731

        m = menu("Файл")
        act(m, "file.new", "Новый файл", self.new_file, "Ctrl+N")
        act(m, "file.open", "Открыть файл…", self.open_file_dialog, "Ctrl+Alt+O")
        act(m, "file.openFolder", "Открыть папку…", self.open_folder_dialog, "Ctrl+O")
        self.recent_menu = m.addMenu("Открыть недавние")
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        m.addSeparator()
        act(m, "file.save", "Сохранить", self.save, "Ctrl+S")
        act(m, "file.saveAs", "Сохранить как…", self.save_as, "Ctrl+Shift+S")
        act(m, "file.saveAll", "Сохранить всё", self.save_all, "Ctrl+Alt+S")
        self.autosave_act = act(m, "file.autosave", "Автосохранение", self._toggle_autosave, checkable=True)
        m.addSeparator()
        act(m, "file.revert", "Вернуть файл с диска", self.revert_file)
        act(m, "file.close", "Закрыть вкладку", lambda: self.close_tab(self.active_group, self.active_group.currentIndex()),
            "Ctrl+W")
        act(m, "file.closeFolder", "Закрыть папку", self.close_folder)
        m.addSeparator()
        act(m, "app.settings", "Настройки…", self.open_settings, "Ctrl+,").setMenuRole(QAction.PreferencesRole)
        quit_ = act(m, "app.quit", "Выйти", self.close, "Ctrl+Q")
        quit_.setMenuRole(QAction.QuitRole)

        m = menu("Правка")
        act(m, "edit.undo", "Отменить", lambda: self._focus_call("undo"), "Ctrl+Z")
        act(m, "edit.redo", "Повторить", lambda: self._focus_call("redo"), "Ctrl+Shift+Z")
        m.addSeparator()
        act(m, "edit.cut", "Вырезать", lambda: self._focus_call("cut"), "Ctrl+X")
        act(m, "edit.copy", "Копировать", lambda: self._focus_call("copy"), "Ctrl+C")
        act(m, "edit.paste", "Вставить", lambda: self._focus_call("paste"), "Ctrl+V")
        m.addSeparator()
        act(m, "edit.find", "Найти", lambda: self._find(False), "Ctrl+F")
        act(m, "edit.replace", "Заменить", lambda: self._find(True), "Ctrl+Alt+F")
        act(m, "edit.findInFiles", "Найти в файлах", lambda: self.show_side("search", focus=True), "Ctrl+Shift+F")
        m.addSeparator()
        act(m, "edit.comment", "Закомментировать строку", ed("toggle_comment"), "Ctrl+/")
        act(m, "edit.blockComment", "Блочный комментарий", self._block_comment, "Shift+Alt+A")
        act(m, "edit.indent", "Увеличить отступ", ed("indent"), "Ctrl+]")
        act(m, "edit.outdent", "Уменьшить отступ", ed("outdent"), "Ctrl+[")
        sub = m.addMenu("Преобразовать")
        act(sub, "edit.upper", "В ВЕРХНИЙ РЕГИСТР", ed("transform", str.upper))
        act(sub, "edit.lower", "в нижний регистр", ed("transform", str.lower))
        act(sub, "edit.title", "Каждое Слово С Заглавной", ed("transform", str.title))
        act(sub, "edit.sort", "Сортировать строки", self._sort_lines)
        act(sub, "edit.trim", "Удалить пробелы в конце строк", self._trim_trailing)

        m = menu("Выделение")
        act(m, "sel.all", "Выделить всё", lambda: self._focus_call("selectAll"), "Ctrl+A")
        act(m, "sel.line", "Выделить строку", ed("select_line"), "Ctrl+L")
        m.addSeparator()
        act(m, "sel.copyUp", "Копировать строку вверх", ed("duplicate_lines", False), "Shift+Alt+Up")
        act(m, "sel.copyDown", "Копировать строку вниз", ed("duplicate_lines", True), "Shift+Alt+Down")
        act(m, "sel.moveUp", "Переместить строку вверх", ed("move_lines", -1), "Alt+Up")
        act(m, "sel.moveDown", "Переместить строку вниз", ed("move_lines", 1), "Alt+Down")
        act(m, "sel.delete", "Удалить строку", ed("delete_lines"), "Ctrl+Shift+K")
        act(m, "sel.insertBelow", "Вставить строку ниже", ed("insert_line", True), "Ctrl+Return")
        act(m, "sel.insertAbove", "Вставить строку выше", ed("insert_line", False), "Ctrl+Shift+Return")

        m = menu("Вид")
        act(m, "view.palette", "Палитра команд…", lambda: self.show_palette(">"), "Ctrl+Shift+P")
        m.addSeparator()
        act(m, "view.explorer", "Проводник", lambda: self.show_side("files"), "Ctrl+Shift+E")
        act(m, "view.search", "Поиск", lambda: self.show_side("search", focus=True))
        act(m, "view.scm", "Система контроля версий", lambda: self.show_side("git"), f"{CTRL}+Shift+G")
        act(m, "view.sidebar", "Показать/скрыть боковую панель", self.toggle_sidebar, "Ctrl+B")
        act(m, "view.panel", "Показать/скрыть панель", self.toggle_panel, "Ctrl+J")
        act(m, "view.terminal", "Терминал", self.toggle_terminal, f"{CTRL}+`")
        m.addSeparator()
        act(m, "view.split", "Разделить редактор", lambda: self.split_editor(), "Ctrl+\\")
        self.wrap_act = act(m, "view.wrap", "Перенос строк", self._toggle_wrap, "Alt+Z", checkable=True)
        m.addSeparator()
        act(m, "view.zoomIn", "Увеличить шрифт", lambda: self.set_font_size(int(self.settings["font_size"]) + 1), "Ctrl+=")
        act(m, "view.zoomOut", "Уменьшить шрифт", lambda: self.set_font_size(int(self.settings["font_size"]) - 1), "Ctrl+-")
        act(m, "view.zoomReset", "Обычный размер шрифта", lambda: self.set_font_size(13), "Ctrl+0")
        theme = m.addMenu("Тема")
        self.theme_group = QActionGroup(self)
        self.theme_actions = {}
        for key, label in (("system", "Системная"), ("light", "Светлая"), ("dark", "Тёмная")):
            a = act(theme, f"theme.{key}", label, lambda k=key: self.set_theme(k), checkable=True)
            self.theme_group.addAction(a)
            self.theme_actions[key] = a

        m = menu("Перейти")
        act(m, "go.quickOpen", "Перейти к файлу…", lambda: self.show_palette(""), "Ctrl+P")
        act(m, "go.symbol", "Перейти к символу…", lambda: self.show_palette("@"), "Ctrl+Shift+O")
        act(m, "go.line", "Перейти к строке…", lambda: self.show_palette(":"), f"{CTRL}+G")
        act(m, "go.bracket", "Перейти к парной скобке", self._goto_bracket, "Ctrl+Shift+\\")
        m.addSeparator()
        act(m, "go.nextTab", "Следующая вкладка", lambda: self._cycle_tab(1), "Ctrl+Shift+]")
        act(m, "go.prevTab", "Предыдущая вкладка", lambda: self._cycle_tab(-1), "Ctrl+Shift+[")
        act(m, "go.nextGroup", "Следующая группа редакторов", self._next_group, "Ctrl+K")

        m = menu("Запуск")
        act(m, "run.file", "Запустить файл", self.run_file, "F5")
        act(m, "run.selection", "Выполнить выделение в терминале", self.run_selection, "Ctrl+Shift+Return")
        act(m, "run.stop", "Остановить (⌃C)", self.stop_run, "Shift+F5")

        m = menu("Терминал")
        act(m, "term.new", "Новый терминал", lambda: self.new_terminal(), f"{CTRL}+Shift+`")
        act(m, "term.kill", "Закрыть терминал", lambda: self.kill_terminal(self.terms.currentIndex()))
        act(m, "term.clear", "Очистить терминал", self._clear_terminal)
        act(m, "term.restart", "Перезапустить терминал", self._restart_terminal)

        m = menu("Справка")
        act(m, "help.keys", "Сочетания клавиш", lambda: self.show_palette(">"))
        act(m, "help.about", f"О программе {APP_NAME}", self.about).setMenuRole(QAction.AboutRole)

    def commands(self):
        return [c for c in self._commands if c["action"].isEnabled()]

    def run_command(self, cid):
        for c in self._commands:
            if c["id"] == cid:
                c["action"].trigger()
                return

    def _focus_call(self, name):
        w = QApplication.focusWidget()
        if w is not None and hasattr(w, name):
            getattr(w, name)()

    def _ed(self, name, *args):
        ed = self.current_editor()
        if ed is not None and not ed.isReadOnly():
            getattr(ed, name)(*args)

    # ================================================================== theme / settings
    def _is_dark(self):
        mode = self.settings.get("theme", "system")
        if mode == "system":
            try:
                return self.app.styleHints().colorScheme() == Qt.ColorScheme.Dark
            except Exception:
                return self.app.palette().color(QPalette.Window).lightness() < 128
        return mode == "dark"

    def apply_theme(self):
        self.colors = DARK if self._is_dark() else LIGHT
        c = self.colors
        self.app.setStyleSheet(stylesheet(c, str(resource_path("assets"))))
        pal = self.app.palette()
        pal.setColor(QPalette.Highlight, QColor(c["selection"]))
        pal.setColor(QPalette.HighlightedText, QColor(c["text"]))
        pal.setColor(QPalette.Base, QColor(c["editor"]))
        pal.setColor(QPalette.Text, QColor(c["text"]))
        pal.setColor(QPalette.Window, QColor(c["bg"]))
        pal.setColor(QPalette.WindowText, QColor(c["text"]))
        self.app.setPalette(pal)
        for key, b in self.activity_buttons.items():
            b.setIcon(icons.glyph(key, c["muted"]))
        self.run_btn.setIcon(icons.glyph("run", c["accent"]))
        self.term_btn.setIcon(icons.glyph("terminal", c["muted"]))
        self.gear_btn.setIcon(icons.glyph("gear", c["muted"]))
        for b in self.panel_buttons:
            b.setIcon(icons.glyph(b.property("glyph"), c["muted"]))
        self.explorer.set_colors(c)
        for g in self.groups:
            for pane in g.panes():
                pane.set_colors(c)
        for i in range(self.terms.count()):
            self.terms.widget(i).set_colors(c)
        if hasattr(self, "theme_actions"):
            self.theme_actions[self.settings.get("theme", "system")].setChecked(True)

    def set_theme(self, mode):
        self.settings["theme"] = mode
        self.settings.save()
        self.apply_theme()

    def set_font_size(self, size):
        size = max(8, min(40, int(size)))
        self.settings["font_size"] = size
        self.settings.save()
        for ed in self.all_editors():
            ed.apply_font()

    def apply_settings(self):
        self.apply_theme()
        for ed in self.all_editors():
            ed.tab_size = int(self.settings["tab_size"])
            ed.apply_font()
            ed.set_wrap(bool(self.settings.get("word_wrap")))
            ed.viewport().update()
        for i in range(self.terms.count()):
            self.terms.widget(i).apply_font()
        self.wrap_act.setChecked(bool(self.settings.get("word_wrap")))
        self.autosave_act.setChecked(bool(self.settings.get("autosave")))
        self.refresh_status()

    def open_settings(self):
        SettingsDialog(self).exec()

    def _app_state(self, state):
        if state == Qt.ApplicationActive:
            self._poll_files()
            self.git_timer.start()
        elif self.settings.get("autosave"):
            self.save_all(quiet=True)

    def changeEvent(self, e):
        if e.type() == e.Type.PaletteChange and self.settings.get("theme") == "system":
            dark = self._is_dark()
            if dark != (self.colors is DARK):
                QTimer.singleShot(0, self.apply_theme)
        super().changeEvent(e)

    # ================================================================== side bar / panel
    def show_side(self, key, toggle=False, focus=False):
        w = self.side_keys[key]
        if toggle and self.sidebar.isVisible() and self.sidebar.currentWidget() is w:
            self.sidebar.setVisible(False)
        else:
            self.sidebar.setVisible(True)
            self.sidebar.setCurrentWidget(w)
            if key == "git":
                self.refresh_git()
            if key == "search" and focus:
                ed = self.current_editor()
                sel = ed.textCursor().selectedText() if ed else ""
                self.search.focus(sel if sel and " " not in sel else None)
        for k, b in self.activity_buttons.items():
            b.setChecked(self.sidebar.isVisible() and self.side_keys[k] is self.sidebar.currentWidget())
        self.settings["sidebar"] = self.sidebar.isVisible()

    def toggle_sidebar(self):
        self.sidebar.setVisible(not self.sidebar.isVisible())
        self.show_side(next(k for k, w in self.side_keys.items() if w is self.sidebar.currentWidget()))
        if not self.sidebar.isVisible():
            for b in self.activity_buttons.values():
                b.setChecked(False)

    def search_in(self, folder):
        self.show_side("search", focus=True)
        if self.folder:
            rel = os.path.relpath(folder, self.folder)
            self.search.include.setText("" if rel == "." else f"{rel}/*")

    def toggle_panel(self):
        if self.panel.isVisible():
            self.panel.setVisible(False)
            ed = self.current_editor()
            if ed:
                ed.setFocus()
        else:
            self.panel.setVisible(True)
            if not self.terms.count():
                self.new_terminal()
            else:
                self.terms.currentWidget().setFocus()

    def toggle_terminal(self):
        term = self.terms.currentWidget()
        if self.panel.isVisible() and term is not None and term.hasFocus():
            self.panel.setVisible(False)
            ed = self.current_editor()
            if ed:
                ed.setFocus()
            return
        self.panel.setVisible(True)
        if term is None:
            self.new_terminal()
        else:
            term.setFocus()

    def new_terminal(self, cwd=None):
        cwd = cwd or self.folder or str(Path.home())
        try:
            term = TerminalWidget(self.colors, self.settings, cwd=str(cwd))
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Не удалось запустить терминал: {exc}")
            return None
        shell = os.path.basename(term.shell or os.environ.get("SHELL", "zsh"))
        n = self.terms.count() + 1
        i = self.terms.addTab(term, f"{shell or 'терминал'} {n}" if n > 1 else (shell or "терминал"))
        term.title_changed.connect(lambda t, w=term: self._term_title(w, t))
        self.terms.setCurrentIndex(i)
        self.panel.setVisible(True)
        term.setFocus()
        return term

    def _term_title(self, term, title):
        i = self.terms.indexOf(term)
        if i >= 0 and title:
            self.terms.setTabToolTip(i, title)

    def kill_terminal(self, index):
        if index < 0:
            return
        term = self.terms.widget(index)
        term.close_process()
        self.terms.removeTab(index)
        term.deleteLater()
        if not self.terms.count():
            self.panel.setVisible(False)

    def _clear_terminal(self):
        if self.terms.currentWidget():
            self.terms.currentWidget().clear()

    def _restart_terminal(self):
        if self.terms.currentWidget():
            self.terms.currentWidget().restart()

    # ================================================================== editor groups
    def add_group(self):
        g = EditorGroup(self)
        self.groups.append(g)
        self.editors.addWidget(g)
        n = len(self.groups)
        self.editors.setSizes([max(200, self.editors.width() // n)] * n)
        self.active_group = g
        self._mark_active()
        return g

    def _mark_active(self):
        for g in self.groups:
            g.setProperty("active", "true" if g is self.active_group or len(self.groups) == 1 else "false")
            g.style().unpolish(g)
            g.style().polish(g)

    def editor_focused(self, editor):
        self._last_editor = editor
        for g in self.groups:
            for pane in g.panes():
                if getattr(pane, "editor", None) is editor and g is not self.active_group:
                    self.active_group = g
                    self._mark_active()
                    self.tab_changed(g)
                    return

    def current_pane(self):
        g = self.active_group
        return g.currentWidget() if g is not None else None

    def current_editor(self):
        pane = self.current_pane()
        return getattr(pane, "editor", None)

    def all_panes(self):
        return [p for g in self.groups for p in g.panes()]

    def all_editors(self):
        return [p.editor for p in self.all_panes() if hasattr(p, "editor")]

    def tab_changed(self, group):
        if group is self.active_group or group.count() and group.currentWidget() and group.currentWidget().hasFocus():
            self.active_group = group
        pane = self.current_pane()
        self.refresh_status()
        title = f"{LOGO} {APP_NAME}"
        if pane is not None:
            title = f"{pane.title()} — " + (f"{Path(self.folder).name} — " if self.folder else "") + title
            if getattr(pane, "path", None):
                self.setWindowFilePath(str(pane.path))
        self.setWindowTitle(title)
        if pane is not None and getattr(pane, "path", None) and self.explorer.isVisible():
            self.explorer.reveal_path(pane.path)

    def _tab_text(self, group, pane):
        i = group.indexOf(pane)
        if i < 0:
            return
        mod = pane.modified()
        group.setTabText(i, ("● " if mod else "") + pane.title())
        group.setTabToolTip(i, str(pane.path) if getattr(pane, "path", None) else pane.title())
        path = getattr(pane, "path", None)
        group.setTabIcon(i, icons.file_icon(path or pane.title()) if pane.kind in ("editor", "image") else QIcon())
        if mod and self.settings.get("autosave") and path:
            self.autosave_timer.start()

    def _add_pane(self, pane, group=None):
        group = group or self.active_group
        i = group.addTab(pane, pane.title())
        pane.title_changed.connect(lambda g=group, p=pane: self._tab_text(self._group_of(p) or g, p))
        self._tab_text(group, pane)
        group.setCurrentIndex(i)
        self.active_group = group
        self._mark_active()
        return pane

    def _group_of(self, pane):
        return next((g for g in self.groups if g.indexOf(pane) >= 0), None)

    def find_pane(self, path, group=None):
        path = str(Path(path).resolve())
        for g in ([group] if group else self.groups):
            for pane in g.panes():
                if getattr(pane, "path", None) and str(Path(pane.path).resolve()) == path:
                    return g, pane
        return None, None

    # ================================================================== opening
    def open_path(self, path):
        p = Path(path)
        if p.is_dir():
            self.open_folder(p)
        elif p.exists():
            self.open_file(str(p))

    def open_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Открыть папку", self.folder or str(Path.home()))
        if folder:
            self.open_folder(folder)

    def open_file_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Открыть файл", self.folder or str(Path.home()))
        for p in paths:
            self.open_file(p)

    def open_folder(self, folder):
        folder = str(Path(folder).resolve())
        if self.folder == folder:
            return
        if not self._confirm_close(self.all_panes()):
            return
        for g in list(self.groups):
            for pane in g.panes():
                self._remove_pane(g, pane)
        self.folder = folder
        self.settings["folder"] = folder
        self.settings.add_recent(folder)
        self.explorer.set_root(folder)
        self.show_side("files")
        self.refresh_git()
        self._ensure_welcome()
        self.tab_changed(self.active_group)
        for i in range(self.terms.count()):
            self.terms.widget(i).run(f"cd {shlex.quote(folder)}")

    def close_folder(self):
        if not self._confirm_close(self.all_panes()):
            return
        for g in list(self.groups):
            for pane in g.panes():
                self._remove_pane(g, pane)
        self.folder = None
        self.settings["folder"] = None
        self.settings.save()
        self.explorer.set_root(None)
        self.refresh_git()
        self._ensure_welcome()

    def open_file(self, path, split=False, line=None, col=None, length=0, group=None):
        path = Path(path)
        if not path.is_file():
            self.status_message(f"Файл не найден: {path}")
            return None
        group = group or self.active_group
        if split:
            group = self.groups[1] if len(self.groups) > 1 else self.add_group()
        g, pane = self.find_pane(path, group)
        if pane is None:
            self._drop_welcome(group)
            if path.suffix.lower() in IMAGE_EXT and path.suffix.lower() != ".svg":
                pane = ImagePane(self, path)
            else:
                try:
                    pane = EditorPane(self, path)
                except ValueError:
                    if QMessageBox.question(self, APP_NAME, f"«{path.name}» — двоичный файл. Открыть в другой программе?") \
                            == QMessageBox.Yes:
                        from PySide6.QtCore import QUrl
                        from PySide6.QtGui import QDesktopServices

                        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
                    return None
                except OSError as exc:
                    QMessageBox.warning(self, APP_NAME, f"Не удалось открыть «{path.name}»: {exc}")
                    return None
            self._add_pane(pane, group)
            if self.folder is None or not str(path).startswith(self.folder):
                self.settings.add_recent(str(path))
        else:
            g.setCurrentWidget(pane)
            self.active_group = g
        self._mark_active()
        if hasattr(pane, "editor"):
            if line:
                pane.editor.goto_line(line, (col or 0) + 1)
                if length:
                    c = pane.editor.textCursor()
                    c.movePosition(c.MoveOperation.Right, c.MoveMode.KeepAnchor, length)
                    pane.editor.setTextCursor(c)
            pane.editor.setFocus()
        self._save_session()
        return pane

    def _open_location(self, path, line, col, length):
        self.open_file(path, line=line, col=col, length=length)

    def open_diff(self, title, text):
        self._drop_welcome(self.active_group)
        self._add_pane(DiffPane(self, title, text))

    def new_file(self):
        self._untitled += 1
        self._drop_welcome(self.active_group)
        pane = EditorPane(self)
        pane.untitled = f"Без названия-{self._untitled}"
        pane.update_crumbs()
        self._add_pane(pane)
        pane.editor.setFocus()
        return pane

    def split_editor(self, pane=None):
        pane = pane or self.current_pane()
        if pane is None or not hasattr(pane, "editor") or pane.kind != "editor":
            return
        target = next((g for g in self.groups if g is not self._group_of(pane)), None) or self.add_group()
        _g, existing = self.find_pane(pane.path, target) if pane.path else (None, None)
        if existing:
            target.setCurrentWidget(existing)
        else:
            twin = EditorPane(self, share=pane)
            twin.untitled = pane.untitled
            twin.update_crumbs()
            self._add_pane(twin, target)
            twin.editor.setTextCursor(pane.editor.textCursor())
            twin.editor.centerCursor()
            twin.editor.setFocus()
        self.active_group = target
        self._mark_active()

    def _ensure_welcome(self):
        if not any(g.count() for g in self.groups):
            self._add_pane(WelcomePane(self), self.groups[0])

    def _drop_welcome(self, group):
        for pane in group.panes():
            if pane.kind == "welcome":
                self._remove_pane(group, pane)

    def reveal_in_explorer(self, path):
        self.show_side("files")
        self.explorer.reveal_path(path)

    # ================================================================== saving / closing
    def save(self, pane=None, quiet=False):
        pane = pane or self.current_pane()
        if pane is None or not hasattr(pane, "editor") or pane.kind != "editor":
            return False
        if pane.path is None:
            return self.save_as(pane)
        try:
            pane.editor.save()
        except OSError as exc:
            QMessageBox.warning(self, APP_NAME, f"Не удалось сохранить «{pane.title()}»: {exc}")
            return False
        for other in self._twins(pane):
            other.editor.disk_mtime = pane.editor.disk_mtime
        if not quiet:
            self.status_message(f"Сохранено: {pane.title()}")
        self.git_timer.start()
        return True

    def save_as(self, pane=None):
        pane = pane or self.current_pane()
        if pane is None or not hasattr(pane, "editor"):
            return False
        start = str(pane.path) if pane.path else str(Path(self.folder or Path.home()) / pane.title())
        dest, _ = QFileDialog.getSaveFileName(self, "Сохранить как", start)
        if not dest:
            return False
        try:
            pane.editor.save(dest)
        except OSError as exc:
            QMessageBox.warning(self, APP_NAME, f"Не удалось сохранить: {exc}")
            return False
        pane.untitled = None
        pane.update_crumbs()
        g = self._group_of(pane)
        if g:
            self._tab_text(g, pane)
        self.refresh_status()
        self.git_timer.start()
        return True

    def save_all(self, quiet=False):
        seen = set()
        for pane in self.all_panes():
            if hasattr(pane, "editor") and pane.kind == "editor" and pane.modified() and pane.path:
                doc = id(pane.editor.document())
                if doc not in seen:
                    seen.add(doc)
                    self.save(pane, quiet=True)
        if not quiet:
            self.status_message("Все файлы сохранены")

    def _autosave(self):
        if self.settings.get("autosave"):
            self.save_all(quiet=True)

    def _toggle_autosave(self):
        self.settings["autosave"] = not self.settings.get("autosave")
        self.settings.save()
        self.autosave_act.setChecked(bool(self.settings["autosave"]))

    def revert_file(self):
        pane = self.current_pane()
        if pane is not None and getattr(pane, "path", None) and pane.kind == "editor":
            pane.editor.reload()

    def _twins(self, pane):
        if not hasattr(pane, "editor"):
            return []
        doc = pane.editor.document()
        return [p for p in self.all_panes() if p is not pane and hasattr(p, "editor") and p.editor.document() is doc]

    def _confirm_close(self, panes):
        dirty = []
        seen = set()
        for p in panes:
            if hasattr(p, "editor") and p.kind == "editor" and p.modified() and id(p.editor.document()) not in seen:
                twins_outside = [t for t in self._twins(p) if t not in panes]
                if not twins_outside:
                    seen.add(id(p.editor.document()))
                    dirty.append(p)
        if not dirty:
            return True
        names = "\n".join(f"• {p.title()}" for p in dirty[:10])
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setText(f"Сохранить изменения?\n\n{names}")
        save = box.addButton("Сохранить", QMessageBox.AcceptRole)
        box.addButton("Не сохранять", QMessageBox.DestructiveRole)
        cancel = box.addButton("Отмена", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is cancel:
            return False
        if box.clickedButton() is save:
            for p in dirty:
                if not self.save(p, quiet=True):
                    return False
        return True

    def _remove_pane(self, group, pane):
        # a split twin keeps the document alive after the original editor goes
        if hasattr(pane, "editor"):
            twins = self._twins(pane)
            if twins and pane.editor.document().parent() is pane.editor:
                pane.editor.document().setParent(twins[0].editor)
        i = group.indexOf(pane)
        if i >= 0:
            group.removeTab(i)
        pane.deleteLater()

    def close_tab(self, group, index):
        if group is None or index < 0:
            return
        pane = group.widget(index)
        if not self._confirm_close([pane]):
            return
        self._remove_pane(group, pane)
        if not group.count() and len(self.groups) > 1:
            self.groups.remove(group)
            group.deleteLater()
            self.active_group = self.groups[0]
            self._mark_active()
        self._ensure_welcome()
        self.tab_changed(self.active_group)
        self._save_session()

    def close_others(self, group, keep):
        panes = [p for p in group.panes() if p is not keep]
        if not self._confirm_close(panes):
            return
        for p in panes:
            self._remove_pane(group, p)
        self._ensure_welcome()

    def _path_renamed(self, old, new):
        for pane in self.all_panes():
            p = getattr(pane, "path", None)
            if not p:
                continue
            p = str(p)
            if p == old or p.startswith(old + os.sep):
                pane.editor.path = Path(new + p[len(old):])
                pane.update_crumbs()
                g = self._group_of(pane)
                if g:
                    self._tab_text(g, pane)
        self.git_timer.start()

    def _path_deleted(self, path):
        for pane in self.all_panes():
            p = str(getattr(pane, "path", "") or "")
            if p and (p == path or p.startswith(path + os.sep)):
                pane.editor.document().setModified(True)
                g = self._group_of(pane)
                if g:
                    self._tab_text(g, pane)
        self.git_timer.start()

    # ================================================================== external changes
    def _poll_files(self):
        for pane in self.all_panes():
            if pane.kind != "editor" or not pane.path:
                continue
            ed = pane.editor
            try:
                mtime = pane.path.stat().st_mtime
            except OSError:
                continue
            if ed.disk_mtime and mtime != ed.disk_mtime:
                if not ed.document().isModified():
                    ed.reload()
                    for t in self._twins(pane):
                        t.editor.disk_mtime = ed.disk_mtime
                else:
                    ed.disk_mtime = mtime
                    self.status_message(f"«{pane.title()}» изменён на диске — «Файл → Вернуть файл с диска»")

    def reload_open_files(self):
        self._poll_files()

    # ================================================================== git / status
    def refresh_git(self):
        st, br = self.scm.refresh(self.folder)
        self.explorer.model.set_git(st)
        self.branch_btn.setText(f"⑂ {br}" if br else "")
        self.branch_btn.setVisible(bool(br))

    def status_message(self, text, ms=5000):
        self.msg.setText(text)
        QTimer.singleShot(ms, lambda t=text: self.msg.text() == t and self.msg.setText(""))

    def update_cursor_status(self, pane, line, col):
        if pane is self.current_pane():
            sel = pane.editor.textCursor().selectedText()
            extra = f" (выделено {len(sel)})" if sel else ""
            self.pos_btn.setText(f"Стр {line}, стлб {col}{extra}")

    def refresh_status(self):
        ed = self.current_editor()
        for w in (self.pos_btn, self.indent_btn, self.enc_btn, self.eol_btn, self.lang_btn):
            w.setVisible(ed is not None)
        if ed is None:
            return
        c = ed.textCursor()
        self.pos_btn.setText(f"Стр {c.blockNumber() + 1}, стлб {c.positionInBlock() + 1}")
        self.indent_btn.setText(f"Пробелы: {ed.tab_size}" if ed.insert_spaces else f"Табуляция: {ed.tab_size}")
        self.enc_btn.setText({"utf-8": "UTF-8", "utf-8-sig": "UTF-8 BOM", "cp1251": "Windows-1251",
                              "latin-1": "Latin-1"}.get(ed.encoding, ed.encoding))
        self.eol_btn.setText("CRLF" if ed.eol == "\r\n" else "LF")
        self.lang_btn.setText(ed.lang.name)
        self.wrap_act.setChecked(ed.lineWrapMode() != ed.LineWrapMode.NoWrap)

    def _indent_menu(self):
        ed = self.current_editor()
        if ed is None:
            return
        from PySide6.QtWidgets import QMenu

        m = QMenu(self)
        for n in (2, 4, 8):
            m.addAction(f"Пробелы: {n}", lambda n=n: self._set_indent(True, n))
        for n in (4, 8):
            m.addAction(f"Табуляция: {n}", lambda n=n: self._set_indent(False, n))
        m.exec(self.indent_btn.mapToGlobal(self.indent_btn.rect().topLeft()))

    def _set_indent(self, spaces, n):
        ed = self.current_editor()
        ed.insert_spaces, ed.tab_size = spaces, n
        ed.setTabStopDistance(ed.char_w * n)
        ed.viewport().update()
        self.refresh_status()

    def _encoding_menu(self):
        ed = self.current_editor()
        if ed is None:
            return
        from PySide6.QtWidgets import QMenu

        m = QMenu(self)
        for enc, label in (("utf-8", "UTF-8"), ("utf-8-sig", "UTF-8 с BOM"), ("cp1251", "Windows-1251"), ("latin-1", "Latin-1")):
            m.addAction(f"Сохранять в {label}", lambda e=enc: self._set_encoding(e))
        m.exec(self.enc_btn.mapToGlobal(self.enc_btn.rect().topLeft()))

    def _set_encoding(self, enc):
        ed = self.current_editor()
        ed.encoding = enc
        ed.document().setModified(True)
        self.refresh_status()

    def _toggle_eol(self):
        ed = self.current_editor()
        if ed is not None:
            ed.eol = "\n" if ed.eol == "\r\n" else "\r\n"
            ed.document().setModified(True)
            self.refresh_status()

    def pick_language(self):
        ed = self.current_editor()
        if ed is None:
            return
        langs = languages.all_languages()
        names = [l.name for l in langs]
        cur = names.index(ed.lang.name) if ed.lang.name in names else 0
        name, ok = QInputDialog.getItem(self, "Язык", "Режим языка для файла:", names, cur, False)
        if ok:
            lang = langs[names.index(name)]
            ed.set_language(lang)
            for t in self._twins(self.current_pane()):
                t.editor.lang = lang
            self.refresh_status()

    def _toggle_wrap(self):
        ed = self.current_editor()
        on = self.wrap_act.isChecked()
        if ed:
            ed.set_wrap(on)

    # ================================================================== editing commands
    def _find(self, replace):
        pane = self.current_pane()
        if pane is not None and hasattr(pane, "findbar"):
            pane.findbar.show_bar(replace)

    def _block_comment(self):
        ed = self.current_editor()
        if ed is None or not ed.lang.block:
            return self._ed("toggle_comment")
        first, last = ed._selected_blocks()
        ed._toggle_block_comment(list(ed._blocks(first, last)), *ed.lang.block)

    def _sort_lines(self):
        ed = self.current_editor()
        if ed is None:
            return
        ed.select_line()
        c = ed.textCursor()
        text = c.selectedText().replace(" ", "\n")
        end_nl = text.endswith("\n")
        lines = sorted(text.rstrip("\n").split("\n"), key=str.lower)
        c.insertText("\n".join(lines) + ("\n" if end_nl else ""))

    def _trim_trailing(self):
        ed = self.current_editor()
        if ed is None:
            return
        c = ed.textCursor()
        c.beginEditBlock()
        b = ed.document().begin()
        while b.isValid():
            t = b.text()
            s = t.rstrip()
            if s != t:
                cur = ed.textCursor()
                cur.setPosition(b.position() + len(s))
                cur.setPosition(b.position() + len(t), cur.MoveMode.KeepAnchor)
                cur.removeSelectedText()
            b = b.next()
        c.endEditBlock()

    def _goto_bracket(self):
        ed = self.current_editor()
        if ed is None:
            return
        pos = ed.textCursor().position()
        doc = ed.document()
        for at in (pos, pos - 1):
            ch = doc.characterAt(at)
            if ch and ch in "()[]{}":
                other = ed._match_bracket(at, ch)
                if other is not None:
                    c = ed.textCursor()
                    c.setPosition(other)
                    ed.setTextCursor(c)
                    return

    def _cycle_tab(self, d):
        g = self.active_group
        if g and g.count():
            g.setCurrentIndex((g.currentIndex() + d) % g.count())

    def _next_group(self):
        if len(self.groups) > 1:
            i = (self.groups.index(self.active_group) + 1) % len(self.groups)
            self.active_group = self.groups[i]
            self._mark_active()
            w = self.active_group.currentWidget()
            if w is not None:
                (getattr(w, "editor", None) or w).setFocus()

    # ================================================================== palette
    def show_palette(self, prefix=""):
        pal = Palette(self, prefix)
        pal.chosen.connect(self._palette_chosen)
        pal.show()
        pal.edit.setFocus()
        pal.edit.setCursorPosition(len(prefix))

    def _palette_chosen(self, data):
        kind, value = data
        if kind == "file":
            self.open_file(value)
        elif kind == "cmd":
            self.run_command(value)
        elif kind == "line":
            ed = self.current_editor()
            try:
                parts = [int(x) for x in str(value).replace(",", ":").split(":") if x.strip()]
            except ValueError:
                return
            if ed and parts:
                ed.goto_line(parts[0], parts[1] if len(parts) > 1 else 1)

    def recent_files(self):
        return [p for p in self.settings.get("recent", []) if Path(p).is_file()]

    def _fill_recent(self):
        self.recent_menu.clear()
        for p in self.settings.get("recent", []):
            if Path(p).exists():
                self.recent_menu.addAction(str(p).replace(str(Path.home()), "~"), lambda p=p: self.open_path(p))
        if self.recent_menu.isEmpty():
            a = self.recent_menu.addAction("Пусто")
            a.setEnabled(False)

    # ================================================================== run
    def run_file(self):
        pane = self.current_pane()
        if pane is None or not hasattr(pane, "editor") or pane.kind != "editor":
            self.status_message("Откройте файл, чтобы запустить его")
            return
        if pane.path is None or pane.modified():
            if not self.save(pane, quiet=True):
                return
        cmd = languages.run_command(pane.editor.lang, pane.path, tempfile.gettempdir())
        if not cmd:
            self.status_message(f"Не знаю, как запустить {pane.editor.lang.name} — используйте терминал (⌃`)")
            return
        cwd = self.folder if self.folder and str(pane.path).startswith(self.folder) else str(pane.path.parent)
        term = self.terms.currentWidget()
        if term is None or term.busy():
            term = self.new_terminal(cwd)
            if term is None:
                return
        self.panel.setVisible(True)
        self.terms.setCurrentWidget(term)
        term.run(f"cd {shlex.quote(cwd)} && {cmd}")
        pane.editor.setFocus()

    def run_selection(self):
        ed = self.current_editor()
        if ed is None:
            return
        text = ed.textCursor().selectedText().replace(" ", "\n") or ed.textCursor().block().text()
        term = self.terms.currentWidget() or self.new_terminal()
        if term:
            self.panel.setVisible(True)
            for line in text.split("\n"):
                term.run(line)

    def stop_run(self):
        term = self.terms.currentWidget()
        if term:
            term.send("\x03")

    # ================================================================== session
    def _save_session(self):
        files = []
        for g in self.groups:
            for p in g.panes():
                path = getattr(p, "path", None)
                if path and p.kind in ("editor", "image") and str(path) not in files:
                    files.append(str(path))
        self.settings["open_files"] = files
        cur = self.current_pane()
        self.settings["active_file"] = str(cur.path) if cur is not None and getattr(cur, "path", None) else None
        self.settings["sidebar"] = self.sidebar.isVisible()
        self.settings.save()

    def _restore(self):
        folder = self.settings.get("folder")
        if folder and Path(folder).is_dir():
            self.folder = str(Path(folder))
            self.explorer.set_root(self.folder)
            self.refresh_git()
        self.show_side("files") if self.settings.get("sidebar", True) else None
        for p in self.settings.get("open_files", []):
            if Path(p).is_file():
                self.open_file(p)
        active = self.settings.get("active_file")
        if active:
            g, pane = self.find_pane(active)
            if pane is not None:
                g.setCurrentWidget(pane)
        self._ensure_welcome()
        self.apply_settings()
        self.tab_changed(self.active_group)

    def closeEvent(self, e):
        if not self._confirm_close(self.all_panes()):
            e.ignore()
            return
        self._save_session()
        for i in range(self.terms.count()):
            self.terms.widget(i).close_process()
        e.accept()

    def about(self):
        QMessageBox.about(self, APP_NAME, f"<h2 style='font-family:Georgia'>{LOGO} {APP_NAME}</h2>"
                          f"<p>Редактор кода, версия {__version__}</p>"
                          "<p>Подсветка ~500 языков (Pygments), встроенный терминал (pyte), git.</p>")


def main():
    if sys.platform == "darwin":
        os.environ.setdefault("QT_MAC_WANTS_LAYER", "1")
    app = QApplication(sys.argv)
    app.setApplicationName("Nu")
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("Nu")
    icon = resource_path("assets", "icon.png")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    win = MainWindow(app)
    app.main_window = win
    win.show()
    for arg in sys.argv[1:]:
        if not arg.startswith("-") and Path(arg).exists():
            win.open_path(arg)
    return app.exec()
