"""Main window: tabs (home + open files), menus with Figma-like shortcuts, theme, open / save."""
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence, QPalette
from PySide6.QtWidgets import (QApplication, QFileDialog, QMainWindow, QMessageBox, QStackedWidget, QTabBar,
                               QVBoxLayout, QWidget)

from . import APP_NAME, LOGO, __version__, fileio, icons
from . import templates as tpl
from .editor import Editor
from .home import Home
from .model import KIND_TITLES
from .paths import Settings, resource_path
from .theme import DARK, LIGHT, stylesheet

FILE_FILTER = "Лямбда (*.lambda)"
IMPORT_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".svg"}


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.settings = Settings()
        self.theme = LIGHT
        self.setWindowTitle(f"{LOGO} {APP_NAME}")
        self.resize(1440, 900)
        self.setMinimumSize(1000, 640)
        central = QWidget()
        central.setObjectName("Main")
        self.setCentralWidget(central)
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        holder = QWidget()
        holder.setObjectName("AppTabs")
        hl = QVBoxLayout(holder)
        hl.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabBar()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setExpanding(False)
        self.tabs.setDocumentMode(True)
        self.tabs.setDrawBase(False)
        self.tabs.setIconSize(QSize(16, 16))
        hl.addWidget(self.tabs)
        v.addWidget(holder)
        self.stack = QStackedWidget()
        v.addWidget(self.stack, 1)
        self.home = Home(self)
        self.stack.addWidget(self.home)
        self.tabs.addTab("Главная")
        for side in (QTabBar.LeftSide, QTabBar.RightSide):
            self.tabs.setTabButton(0, side, None)
        self.tabs.currentChanged.connect(self._tab_changed)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.tabMoved.connect(self._tab_moved)
        self.editors = []
        self._build_menus()
        self.statusBar()
        self.apply_theme()
        self.home.refresh()

    # ================================================================== documents
    def current_editor(self):
        w = self.stack.currentWidget()
        return w if isinstance(w, Editor) else None

    def new_document(self, kind, key="blank"):
        doc = tpl.new_document(kind, key)
        return self.add_editor(doc, None)

    def add_editor(self, doc, path):
        ed = Editor(doc, path, self)
        ed.set_ui_theme(self.theme)
        self.editors.append(ed)
        self.stack.addWidget(ed)
        i = self.tabs.addTab(icons.icon(doc.kind, self.theme["text"], self.theme["accent"]), ed.title())
        self.tabs.setTabData(i, id(ed))
        ed.titleChanged.connect(lambda e=ed: self._retitle(e))
        self.tabs.setCurrentIndex(i)
        return ed

    def _tab_index(self, ed):
        for i in range(1, self.tabs.count()):
            if self.tabs.tabData(i) == id(ed):
                return i
        return -1

    def _retitle(self, ed):
        i = self._tab_index(ed)
        if i >= 0:
            self.tabs.setTabText(i, ed.title() + (" •" if ed.is_dirty() else ""))
        if ed is self.current_editor():
            self.setWindowTitle(f"{ed.title()}{' •' if ed.is_dirty() else ''} — {LOGO} {APP_NAME}")

    def _tab_changed(self, i):
        if i <= 0:
            self.stack.setCurrentWidget(self.home)
            self.home.refresh()
            self.setWindowTitle(f"{LOGO} {APP_NAME}")
        else:
            ed = next((e for e in self.editors if id(e) == self.tabs.tabData(i)), None)
            if ed is not None:
                self.stack.setCurrentWidget(ed)
                self.statusBar().clearMessage()
                self._retitle(ed)
                ed.canvas.setFocus()
        self._update_actions()

    def _tab_moved(self, a, b):
        if self.tabs.tabText(0) != "Главная":  # keep home first
            self.tabs.blockSignals(True)
            self.tabs.moveTab(b, a)
            self.tabs.blockSignals(False)

    def open_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Открыть", self.settings.get("last_dir", ""),
                                                FILE_FILTER + ";;Изображения и SVG (*.png *.jpg *.jpeg *.gif *.webp "
                                                              "*.svg);;Все файлы (*)")
        for p in paths:
            self.open_path(p)

    def open_path(self, path):
        path = Path(path)
        for ed in self.editors:
            if ed.path is not None and ed.path.resolve() == path.resolve():
                self.tabs.setCurrentIndex(self._tab_index(ed))
                return ed
        ext = path.suffix.lower()
        if ext in IMPORT_EXT:
            ed = self.current_editor() or self.new_document("design")
            ed.import_files([str(path)])
            return ed
        try:
            doc = fileio.load(path)
        except Exception as ex:  # noqa: BLE001
            QMessageBox.warning(self, "Открыть", f"Не удалось открыть «{path.name}»:\n{ex}")
            return None
        self.settings["last_dir"] = str(path.parent)
        self.settings.add_recent(path)
        return self.add_editor(doc, path)

    def save(self, ed=None):
        ed = ed or self.current_editor()
        if ed is None:
            return False
        if ed.path is None:
            return self.save_as(ed)
        try:
            ed.save()
        except Exception as ex:  # noqa: BLE001
            QMessageBox.warning(self, "Сохранение", f"Не удалось сохранить:\n{ex}")
            return False
        return True

    def save_as(self, ed=None):
        ed = ed or self.current_editor()
        if ed is None:
            return False
        last = self.settings.get("last_dir", "") or str(Path.home() / "Documents")
        name = ed.title() if ed.path else f"{KIND_TITLES[ed.doc.kind]} без названия"
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить", str(Path(last) / f"{name}.lambda"), FILE_FILTER)
        if not path:
            return False
        try:
            ed.save(path)
        except Exception as ex:  # noqa: BLE001
            QMessageBox.warning(self, "Сохранение", f"Не удалось сохранить:\n{ex}")
            return False
        self.settings["last_dir"] = str(Path(path).parent)
        self._retitle(ed)
        return True

    def maybe_save(self, ed):
        if not ed.is_dirty():
            return True
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setText(f"Сохранить изменения в «{ed.title()}»?")
        box.setInformativeText("Если не сохранить, изменения пропадут.")
        save = box.addButton("Сохранить", QMessageBox.AcceptRole)
        discard = box.addButton("Не сохранять", QMessageBox.DestructiveRole)
        box.addButton("Отмена", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is save:
            return self.save(ed)
        return box.clickedButton() is discard

    def close_tab(self, i):
        if i <= 0:
            return
        ed = next((e for e in self.editors if id(e) == self.tabs.tabData(i)), None)
        if ed is None or not self.maybe_save(ed):
            return
        ed.close_windows()
        self.editors.remove(ed)
        self.tabs.removeTab(i)
        self.stack.removeWidget(ed)
        ed.deleteLater()

    def closeEvent(self, e):
        for ed in list(self.editors):
            self.tabs.setCurrentIndex(self._tab_index(ed))
            if not self.maybe_save(ed):
                e.ignore()
                return
        for ed in self.editors:
            ed.close_windows()
        self.settings.save()
        e.accept()

    # ================================================================== menus
    def _build_menus(self):
        mb = self.menuBar()
        self.editor_actions = []

        def act(menu, text, fn, shortcut=None, needs=True, kinds=None):
            a = QAction(text, self)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            a.triggered.connect(lambda: self._run(fn, needs))
            menu.addAction(a)
            if needs:
                self.editor_actions.append((a, kinds))
            return a

        e = lambda name, *args: (lambda: getattr(self.current_editor(), name)(*args))  # noqa: E731

        m = mb.addMenu("Файл")
        act(m, "Новый дизайн", lambda: self.new_document("design"), "Ctrl+N", needs=False)
        act(m, "Новая доска", lambda: self.new_document("board"), "Ctrl+Shift+N", needs=False)
        act(m, "Новая презентация", lambda: self.new_document("slides"), None, needs=False)
        act(m, "Новый сайт", lambda: self.new_document("site"), None, needs=False)
        m.addSeparator()
        act(m, "Открыть…", self.open_dialog, QKeySequence.Open, needs=False)
        act(m, "Главная", lambda: self.tabs.setCurrentIndex(0), None, needs=False)
        m.addSeparator()
        act(m, "Сохранить", lambda: self.save(), QKeySequence.Save)
        act(m, "Сохранить как…", lambda: self.save_as(), "Ctrl+Shift+S")
        m.addSeparator()
        act(m, "Поместить изображение или SVG…", e("place_image_dialog"), "Ctrl+Shift+K")
        act(m, "Экспорт выделенного…", e("export_dialog"), "Ctrl+Shift+E")
        act(m, "Экспорт всех фреймов…", lambda: self.current_editor().export_dialog(all_frames=True),
            kinds=("design", "board"))
        act(m, "Экспорт в PDF…", e("export_pdf_all"), kinds=("slides", "design"))
        act(m, "Экспорт сайта…", e("export_site"), kinds=("site",))
        m.addSeparator()
        act(m, "Закрыть вкладку", lambda: self.close_tab(self.tabs.currentIndex()), QKeySequence.Close)

        m = mb.addMenu("Правка")
        act(m, "Отменить", e("undo"), QKeySequence.Undo)
        act(m, "Повторить", e("redo"), "Ctrl+Shift+Z")
        m.addSeparator()
        act(m, "Вырезать", e("cut"), QKeySequence.Cut)
        act(m, "Копировать", e("copy"), QKeySequence.Copy)
        act(m, "Вставить", e("paste"), QKeySequence.Paste)
        act(m, "Дублировать", e("duplicate"), "Ctrl+D")
        act(m, "Удалить", e("delete_selection"))
        m.addSeparator()
        act(m, "Выделить всё", e("select_all"), QKeySequence.SelectAll)
        act(m, "Переименовать…", e("rename"), "Ctrl+R")

        m = mb.addMenu("Вид")
        act(m, "Увеличить", lambda: self.current_editor().canvas.set_zoom(self.current_editor().canvas.zoom * 1.25),
            "Ctrl+=")
        act(m, "Уменьшить", lambda: self.current_editor().canvas.set_zoom(self.current_editor().canvas.zoom / 1.25),
            "Ctrl+-")
        act(m, "Масштаб 100%", lambda: self.current_editor().canvas.set_zoom(1.0), "Ctrl+0")
        act(m, "Показать всё\t⇧1", lambda: self.current_editor().canvas.fit())
        act(m, "К выделению\t⇧2", e("zoom_selection"))
        m.addSeparator()
        act(m, "Панели слоёв", self.toggle_left, "Ctrl+Alt+1")
        act(m, "Скрыть интерфейс", self.toggle_ui, "Ctrl+\\")
        snap = act(m, "Привязка к пикселям", self.toggle_snap, None, needs=False)
        snap.setCheckable(True)
        snap.setChecked(self.settings.get("snap_pixels", True))
        m.addSeparator()
        tm = m.addMenu("Тема")
        group = QActionGroup(self)
        self.theme_actions = {}
        for key, title in (("system", "Как в системе"), ("light", "Светлая"), ("dark", "Тёмная")):
            a = QAction(title, self, checkable=True)
            a.triggered.connect(lambda _=False, k=key: self.set_theme(k))
            group.addAction(a)
            tm.addAction(a)
            self.theme_actions[key] = a

        m = mb.addMenu("Объект")
        act(m, "Сгруппировать", e("group"), "Ctrl+G")
        act(m, "Разгруппировать", e("ungroup"), "Ctrl+Shift+G")
        act(m, "Фрейм из выделения", e("frame_selection"), "Ctrl+Alt+G", kinds=("design", "slides", "site"))
        act(m, "Добавить автолейаут", e("add_autolayout"), None, kinds=("design", "slides", "site"))
        m.addSeparator()
        act(m, "Создать компонент", e("create_component"), "Ctrl+Alt+K", kinds=("design",))
        act(m, "Отсоединить экземпляр", e("detach_instance"), "Ctrl+Alt+B", kinds=("design",))
        m.addSeparator()
        b = m.addMenu("Булевы операции")
        for op, title, sc in (("union", "Объединить", None), ("subtract", "Вычесть", None),
                              ("intersect", "Пересечь", None), ("exclude", "Исключить", None)):
            act(b, title, e("boolean", op), sc)
        act(m, "Преобразовать в кривые", e("flatten"), "Ctrl+E")
        act(m, "Обвести контур", e("outline_stroke"), "Ctrl+Shift+O")
        act(m, "Использовать как маску", e("use_as_mask"), "Ctrl+Meta+M")
        m.addSeparator()
        o = m.addMenu("Порядок")
        act(o, "На передний план", e("order", "front"), "Ctrl+Alt+]")
        act(o, "Вперёд", e("order", "forward"), "Ctrl+]")
        act(o, "Назад", e("order", "backward"), "Ctrl+[")
        act(o, "На задний план", e("order", "back"), "Ctrl+Alt+[")
        a = m.addMenu("Выравнивание")
        for key, title in (("align_left", "По левому краю\t⌥A"), ("align_hcenter", "По центру\t⌥H"),
                           ("align_right", "По правому краю\t⌥D"), ("align_top", "По верху\t⌥W"),
                           ("align_vcenter", "По середине\t⌥V"), ("align_bottom", "По низу\t⌥S"),
                           ("dist_h", "Распределить по горизонтали"), ("dist_v", "Распределить по вертикали")):
            act(a, title, e("align", key))
        m.addSeparator()
        act(m, "Показать / скрыть", e("toggle_visible"), "Ctrl+Shift+H")
        act(m, "Заблокировать / разблокировать", e("toggle_lock"), "Ctrl+Shift+L")

        m = mb.addMenu("Показ")
        act(m, "▶ Презентовать", e("present"), "Ctrl+Alt+Return", kinds=("design", "slides"))
        act(m, "Режим докладчика", e("present_presenter"), "Ctrl+Alt+Shift+Return", kinds=("slides",))
        act(m, "Новый слайд", lambda: self.current_editor().add_slide("title_body"), "Ctrl+Return", kinds=("slides",))
        act(m, "Предпросмотр сайта", e("preview_site"), "Ctrl+Alt+P", kinds=("site",))

        m = mb.addMenu("Справка")
        act(m, "Горячие клавиши", self.shortcuts_help, "Ctrl+Shift+/", needs=False)
        about = act(m, f"О программе {APP_NAME}", self.about, None, needs=False)
        about.setMenuRole(QAction.AboutRole)
        self._update_actions()

    def _run(self, fn, needs):
        if needs and self.current_editor() is None:
            return
        ed = self.current_editor()
        if ed is not None and ed.canvas.editing is not None and needs:
            fw = QApplication.focusWidget()
            if fw is ed.canvas.overlay:
                return
        fn()

    def _update_actions(self):
        ed = self.current_editor()
        for a, kinds in self.editor_actions:
            a.setEnabled(ed is not None and (kinds is None or ed.doc.kind in kinds))

    def toggle_left(self):
        ed = self.current_editor()
        if ed is not None:
            ed.left.setVisible(not ed.left.isVisible())

    def toggle_ui(self):
        ed = self.current_editor()
        if ed is not None:
            show = not ed.right.isVisible()
            ed.right.setVisible(show)
            ed.left.setVisible(show and ed.doc.kind != "board")

    def toggle_snap(self):
        self.settings["snap_pixels"] = not self.settings.get("snap_pixels", True)
        self.settings.save()

    def shortcuts_help(self):
        QMessageBox.information(self, "Горячие клавиши", (
            "Инструменты: V перемещение · H рука (или пробел) · F фрейм · ⇧S секция · R прямоугольник · O эллипс · "
            "L линия · ⇧L стрелка · P перо · ⇧P карандаш · T текст\n\n"
            "Доска: S стикер · R/O фигура · X соединитель · M маркер · ⇧M выделитель · E штамп\n\n"
            "Объекты: ⌘G группа · ⇧⌘G разгруппировать · ⌥⌘G фрейм · ⇧A автолейаут · ⌥⌘K компонент · "
            "⌥⌘B отсоединить · ⌘E в кривые · ⌘D дублировать · ⌘] / ⌘[ порядок · ⇧⌘H скрыть · ⇧⌘L заблокировать\n\n"
            "Перемещение: стрелки — 1 px, ⇧ + стрелки — 10 px · ⌥ + перетаскивание — копия · ⇧ — по оси · "
            "⌘ при щелчке — глубокое выделение · двойной щелчок — внутрь группы / редактировать текст / точки\n\n"
            "Вид: ⇧1 всё · ⇧2 к выделению · ⌘0 100% · ⌘ + колесо или щипок — масштаб · ⌘\\ скрыть панели\n\n"
            "Показ: ⌥⌘↩ презентовать · ← → листать · N заметки · Esc выход"))

    def about(self):
        QMessageBox.about(self, APP_NAME, f"<h3>{LOGO} {APP_NAME} {__version__}</h3>"
                                          "<p>Дизайн, доски, презентации и сайты — без интернета.</p>"
                                          "<p>Файлы .lambda хранятся у вас. macOS 11+ (Intel).</p>")

    # ================================================================== theme
    def _is_dark(self):
        mode = self.settings.get("theme", "system")
        if mode == "system":
            try:
                return self.app.styleHints().colorScheme() == Qt.ColorScheme.Dark
            except Exception:
                return self.app.palette().color(QPalette.Window).lightness() < 128
        return mode == "dark"

    def apply_theme(self):
        self.theme = DARK if self._is_dark() else LIGHT
        self.app.setStyleSheet(stylesheet(self.theme))
        self.theme_actions[self.settings.get("theme", "system")].setChecked(True)
        self.tabs.setTabIcon(0, icons.icon("lambda", self.theme["text"], self.theme["accent"]))
        for ed in self.editors:
            ed.set_ui_theme(self.theme)
            i = self._tab_index(ed)
            if i >= 0:
                self.tabs.setTabIcon(i, icons.icon(ed.doc.kind, self.theme["text"], self.theme["accent"]))
        self.home.set_theme(self.theme)

    def set_theme(self, mode):
        self.settings["theme"] = mode
        self.settings.save()
        self.apply_theme()

    def changeEvent(self, e):
        if e.type() == e.Type.PaletteChange and self.settings.get("theme") == "system":
            if self._is_dark() != (self.theme is DARK):
                QTimer.singleShot(0, self.apply_theme)
        super().changeEvent(e)


class App(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.win = None
        self.pending = []

    def event(self, e):
        if e.type() == e.Type.FileOpen:  # Finder: open with / double-click a .lambda file
            path = e.file()
            if self.win is not None:
                self.win.open_path(path)
            else:
                self.pending.append(path)
            return True
        return super().event(e)


def main():
    app = App(sys.argv)
    app.setApplicationName("Lambda")
    app.setApplicationDisplayName(APP_NAME)
    icon = resource_path("assets", "icon.png")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    win = MainWindow(app)
    app.win = win
    win.show()
    for arg in sys.argv[1:] + app.pending:
        if not arg.startswith("-") and Path(arg).exists():
            win.open_path(arg)
    return app.exec()
