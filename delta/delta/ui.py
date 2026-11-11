"""Дельта main window: tool box, tool options, canvas with document tabs, docks (colour, brushes, layers,
animation timeline), menus, filters, manga tools, files and export."""
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QPointF, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QAction, QActionGroup, QColor, QFont, QFontMetricsF, QIcon, QImage, QKeySequence, QPainter, QPainterPath,
    QPainterPathStroker, QPalette, QPen,
)
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QDockWidget, QFileDialog, QGridLayout, QHBoxLayout,
    QInputDialog, QLabel, QMainWindow, QMessageBox, QProgressDialog, QPushButton, QSpinBox, QStackedWidget, QTabBar,
    QToolButton, QVBoxLayout, QWidget,
)

from . import APP_NAME, LOGO, __version__, fileio, icons, imgops
from .brushes import PRESETS, Brush
from .canvas import Canvas
from .dialogs import AdjustDialog, CanvasSizeDialog, ExportDialog, NewDocDialog, PanelGridDialog, TextDialog
from .model import FMT, PROPS, Document, Layer, blank
from .panels import BrushPanel, ColorPanel, LayersPanel
from .paths import Settings, resource_path
from .theme import DARK, LIGHT, stylesheet
from .timeline import Timeline
from .tools import TOOLS, bubble_path

MAC = sys.platform == "darwin"


class Welcome(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setObjectName("Main")
        outer = QHBoxLayout(self)
        outer.addStretch(1)
        col = QVBoxLayout()
        col.addStretch(1)
        head = QHBoxLayout()
        logo = QLabel(LOGO)
        logo.setObjectName("BigLogo")
        head.addWidget(logo)
        tc = QVBoxLayout()
        tc.addStretch(1)
        name = QLabel(APP_NAME)
        name.setObjectName("Title")
        tc.addWidget(name)
        sub = QLabel(f"Рисование манги, персонажей и анимации · версия {__version__}")
        sub.setObjectName("Muted")
        tc.addWidget(sub)
        tc.addStretch(1)
        head.addLayout(tc)
        head.addStretch(1)
        col.addLayout(head)
        col.addSpacing(16)
        row = QHBoxLayout()
        row.setSpacing(48)
        a = QVBoxLayout()
        s = QLabel("НАЧАЛО")
        s.setObjectName("Section")
        a.addWidget(s)
        for text, fn in (("Новый документ…", win.new_document), ("Страница манги (A4, разметка кадров)", win.new_manga_page),
                         ("Открыть…", win.open_dialog), ("Вставить из буфера", win.paste_as_document)):
            b = QPushButton(text)
            b.setObjectName("Link")
            b.clicked.connect(fn)
            a.addWidget(b)
        a.addStretch(1)
        row.addLayout(a)
        self.recent = QVBoxLayout()
        s = QLabel("НЕДАВНИЕ")
        s.setObjectName("Section")
        self.recent.addWidget(s)
        self.fill_recent()
        row.addLayout(self.recent)
        col.addLayout(row)
        col.addSpacing(18)
        k = QLabel("B кисть · E ластик · G заливка · I пипетка · F кадр · K реплика · T скринтон · ⌘T трансформация · "
                   "пробел — рука · R — поворот холста")
        k.setObjectName("Muted")
        col.addWidget(k)
        col.addStretch(2)
        outer.addLayout(col)
        outer.addStretch(1)

    def fill_recent(self):
        while self.recent.count() > 1:
            it = self.recent.takeAt(1)
            if it.widget():
                it.widget().deleteLater()
        items = [p for p in self.win.settings.get("recent", []) if Path(p).exists()][:8]
        for p in items:
            b = QPushButton(Path(p).name)
            b.setObjectName("Link")
            b.setToolTip(p)
            b.clicked.connect(lambda _=False, p=p: self.win.open_path(p))
            self.recent.addWidget(b)
        if not items:
            m = QLabel("Пока пусто")
            m.setObjectName("Muted")
            self.recent.addWidget(m)
        self.recent.addStretch(1)


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.settings = Settings()
        self.theme = LIGHT
        self.docs = []
        self.doc = None
        self.primary = QColor("#141413")
        self.secondary = QColor("#FFFFFF")
        self.brush = Brush.from_dict(PRESETS[0].to_dict())
        self.eraser_brush = Brush.from_dict(next(b for b in PRESETS if b.mode == "erase").to_dict())
        self.last_point = None
        self.clipboard = None
        self.tools = [T(self) for T in TOOLS]
        self.tool = self.tools[0]
        self.play_timer = QTimer(self, timeout=self._play_step)
        self.setWindowTitle(f"{LOGO} {APP_NAME}")
        self.resize(1440, 900)
        self.setMinimumSize(1000, 640)
        self.setDockNestingEnabled(True)
        self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)

        central = QWidget()
        central.setObjectName("Main")
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_context())
        mid = QHBoxLayout()
        mid.setSpacing(0)
        mid.addWidget(self._build_toolbox())
        center = QVBoxLayout()
        center.setSpacing(0)
        self.tabs = QTabBar()
        self.tabs.setObjectName("DocTabs")
        self.tabs.setTabsClosable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.setExpanding(False)
        self.tabs.currentChanged.connect(self._tab_changed)
        self.tabs.tabCloseRequested.connect(self.close_doc)
        tw = QWidget()
        tw.setObjectName("DocTabs")
        tl = QHBoxLayout(tw)
        tl.setContentsMargins(6, 0, 6, 0)
        tl.addWidget(self.tabs)
        tl.addStretch(1)
        center.addWidget(tw)
        self.stack = QStackedWidget()
        self.canvas = Canvas(self)
        self.canvas.hovered.connect(self._hovered)
        self.canvas.view_changed.connect(self._view_changed)
        self.welcome = Welcome(self)
        self.stack.addWidget(self.welcome)
        self.stack.addWidget(self.canvas)
        center.addWidget(self.stack, 1)
        mid.addLayout(center, 1)
        outer.addLayout(mid, 1)

        self.color_panel = ColorPanel(self)
        self.brush_panel = BrushPanel(self)
        self.layers_panel = LayersPanel(self)
        self.timeline = Timeline(self)
        self.docks = {}
        for key, title, widget, area in (("color", "ЦВЕТ", self.color_panel, Qt.RightDockWidgetArea),
                                         ("brushes", "КИСТИ", self.brush_panel, Qt.RightDockWidgetArea),
                                         ("layers", "СЛОИ", self.layers_panel, Qt.RightDockWidgetArea),
                                         ("timeline", "АНИМАЦИЯ", self.timeline, Qt.BottomDockWidgetArea)):
            d = QDockWidget(title, self)
            d.setObjectName(f"dock_{key}")
            d.setWidget(widget)
            d.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable)
            self.addDockWidget(area, d)
            self.docks[key] = d
        self.resizeDocks([self.docks["color"], self.docks["brushes"], self.docks["layers"]], [250, 300, 320], Qt.Vertical)
        self.resizeDocks([self.docks["color"]], [270], Qt.Horizontal)
        self.resizeDocks([self.docks["timeline"]], [190], Qt.Vertical)

        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        self.pos_label = QLabel()
        self.msg = QLabel()
        self.view_label = QLabel()
        self.size_label = QLabel()
        sb.addWidget(self.pos_label)
        sb.addWidget(self.msg, 1)
        sb.addPermanentWidget(self.view_label)
        sb.addPermanentWidget(self.size_label)
        self._build_menus()
        state = self.settings.get("dock_state")
        if state:
            try:
                self.restoreState(QByteArray.fromBase64(state.encode()))
            except Exception:
                pass
        self.brush_panel.load()
        self.apply_theme()
        self.select_tool("brush", keep_brush=True)
        self.set_color(self.primary)
        self._update_all()

    # ================================================================== building
    def _build_toolbox(self):
        box = QWidget()
        box.setObjectName("ToolBox")
        box.setFixedWidth(84)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(6, 8, 6, 8)
        lay.setSpacing(2)
        logo = QLabel(LOGO)
        logo.setObjectName("Delta")
        logo.setAlignment(Qt.AlignCenter)
        logo.setToolTip(APP_NAME)
        lay.addWidget(logo)
        lay.addSpacing(4)
        grid = QGridLayout()
        grid.setSpacing(2)
        self.tool_group = QButtonGroup(self)
        self.tool_buttons = {}
        for i, tool in enumerate(self.tools):
            b = QToolButton()
            b.setCheckable(True)
            b.setIconSize(QSize(20, 20))
            b.setFixedSize(34, 30)
            b.setToolTip(f"{tool.name} ({tool.shortcut})\n{tool.hint}")
            b.clicked.connect(lambda _=False, k=tool.key: self.select_tool(k))
            self.tool_group.addButton(b)
            grid.addWidget(b, i // 2, i % 2)
            self.tool_buttons[tool.key] = b
        lay.addLayout(grid)
        lay.addStretch(1)
        return box

    def _build_context(self):
        bar = QWidget()
        bar.setObjectName("ContextBar")
        bar.setFixedHeight(40)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 4, 12, 4)
        lay.setSpacing(8)
        self.tool_label = QLabel()
        self.tool_label.setObjectName("Logo")
        lay.addWidget(self.tool_label)
        lay.addSpacing(6)
        s = self.settings
        self.opt = {}

        def add(key, widget, label=None):
            wrap = QWidget()
            wl = QHBoxLayout(wrap)
            wl.setContentsMargins(0, 0, 0, 0)
            wl.setSpacing(4)
            if label:
                lab = QLabel(label)
                lab.setObjectName("Muted")
                wl.addWidget(lab)
            wl.addWidget(widget)
            lay.addWidget(wrap)
            self.opt.setdefault(key, []).append(wrap)
            return widget

        self.size_box = add("brush", QSpinBox(), "Размер")
        self.size_box.setRange(1, 500)
        self.size_box.setSuffix(" px")
        self.size_box.valueChanged.connect(self._size_changed)
        self.brush_name = add("brush", QLabel())
        self.brush_name.setObjectName("Muted")
        tol = add("fill", QSpinBox(), "Допуск")
        tol.setRange(0, 255)
        tol.setValue(int(s.get("fill_tolerance", 24)))
        tol.valueChanged.connect(lambda v: self._opt("fill_tolerance", v))
        exp = add("fill", QSpinBox(), "Расширить")
        exp.setRange(0, 8)
        exp.setValue(int(s.get("fill_expand", 1)))
        exp.setSuffix(" px")
        exp.valueChanged.connect(lambda v: self._opt("fill_expand", v))
        allc = add("fill", QCheckBox("По всем слоям"))
        allc.setChecked(bool(s.get("fill_all_layers")))
        allc.toggled.connect(lambda v: self._opt("fill_all_layers", v))
        for key, label, lo, hi, suffix in (("tone_spacing", "Шаг", 3, 60, " px"), ("tone_size", "Точка", 1, 100, " %")):
            sp = add("tone", QSpinBox(), label)
            sp.setRange(lo, hi)
            sp.setValue(int(s.get(key)))
            sp.setSuffix(suffix)
            sp.valueChanged.connect(lambda v, k=key: self._opt(k, v))
        ang = add("tone", QComboBox(), "Угол")
        ang.addItem("45°", 45)
        ang.addItem("0°", 0)
        ang.setCurrentIndex(0 if int(s.get("tone_angle", 45)) == 45 else 1)
        ang.currentIndexChanged.connect(lambda _i: self._opt("tone_angle", ang.currentData()))
        fillc = add("shape", QCheckBox("Залить"))
        fillc.setChecked(bool(s.get("shape_fill")))
        fillc.toggled.connect(lambda v: self._opt("shape_fill", v))
        rad = add("gradient", QCheckBox("Радиальный"))
        rad.setChecked(bool(s.get("gradient_radial")))
        rad.toggled.connect(lambda v: self._opt("gradient_radial", v))
        tr = add("gradient", QCheckBox("В прозрачность"))
        tr.setChecked(bool(s.get("gradient_to_transparent")))
        tr.toggled.connect(lambda v: self._opt("gradient_to_transparent", v))
        pw = add("panel", QSpinBox(), "Толщина рамки")
        pw.setRange(1, 60)
        pw.setValue(int(s.get("panel_width", 6)))
        pw.setSuffix(" px")
        pw.valueChanged.connect(lambda v: self._opt("panel_width", v))
        grid_btn = add("panel", QPushButton("Раскадровка страницы…"))
        grid_btn.clicked.connect(self.panel_grid)
        apply_t = add("transform", QPushButton("Применить (Enter)"))
        apply_t.setObjectName("Accent")
        apply_t.clicked.connect(lambda: self.tool_by_key("transform").apply())
        cancel_t = add("transform", QPushButton("Отмена"))
        cancel_t.clicked.connect(lambda: self.tool_by_key("transform").cancel())
        lay.addStretch(1)
        self.hint_label = QLabel()
        self.hint_label.setObjectName("Muted")
        lay.addWidget(self.hint_label)
        return bar

    def _opt(self, key, value):
        self.settings[key] = value
        self.settings.save()

    def _size_changed(self, v):
        if getattr(self, "_syncing", False):
            return
        self.brush_panel.set_size(v)
        self.canvas.update()

    # ------------------------------------------------------------------ menus
    def _build_menus(self):
        mb = self.menuBar()
        self.doc_actions = []

        def act(menu, title, fn, shortcut=None, needs_doc=True, checkable=False):
            a = QAction(title, self)
            if shortcut:
                a.setShortcuts([QKeySequence(s) for s in (shortcut if isinstance(shortcut, (list, tuple)) else [shortcut])])
            a.setCheckable(checkable)
            a.triggered.connect(lambda checked=False: fn())
            menu.addAction(a)
            self.addAction(a)
            if needs_doc:
                self.doc_actions.append(a)
            return a

        m = mb.addMenu("Файл")
        act(m, "Новый документ…", self.new_document, "Ctrl+N", needs_doc=False)
        act(m, "Новая страница манги…", self.new_manga_page, "Ctrl+Alt+N", needs_doc=False)
        act(m, "Открыть…", self.open_dialog, "Ctrl+O", needs_doc=False)
        self.recent_menu = m.addMenu("Открыть недавние")
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        act(m, "Поместить изображение как слой…", self.place_image, "Ctrl+Shift+O")
        m.addSeparator()
        act(m, "Сохранить", self.save, "Ctrl+S")
        act(m, "Сохранить как…", self.save_as, "Ctrl+Shift+S")
        act(m, "Экспорт…", self.export_dialog, "Ctrl+Alt+E")
        m.addSeparator()
        act(m, "Закрыть", lambda: self.close_doc(self.tabs.currentIndex()), "Ctrl+W")
        act(m, "Настройки…", self.preferences, "Ctrl+,", needs_doc=False).setMenuRole(QAction.PreferencesRole)
        act(m, "Выйти", self.close, "Ctrl+Q", needs_doc=False).setMenuRole(QAction.QuitRole)

        m = mb.addMenu("Правка")
        act(m, "Отменить", self.undo, "Ctrl+Z")
        act(m, "Повторить", self.redo, ["Ctrl+Shift+Z", "Ctrl+Y"])
        m.addSeparator()
        act(m, "Вырезать", self.cut, "Ctrl+X")
        act(m, "Копировать", self.copy, "Ctrl+C")
        act(m, "Копировать всё видимое", lambda: self.copy(merged=True), "Ctrl+Shift+C")
        act(m, "Вставить как новый слой", self.paste, "Ctrl+V", needs_doc=False)
        act(m, "Очистить", self.clear_selection, ["Delete", "Backspace"])
        act(m, "Залить выделение основным цветом", self.fill_selection, "Alt+Backspace")
        act(m, "Обвести выделение кистью", self.stroke_selection)
        m.addSeparator()
        act(m, "Свободная трансформация", lambda: self.select_tool("transform"), "Ctrl+T")
        act(m, "Отразить слой по горизонтали", lambda: self.flip_layer(True))
        act(m, "Отразить слой по вертикали", lambda: self.flip_layer(False))
        m.addSeparator()
        act(m, "Поменять цвета местами", self.swap_colors, "X", needs_doc=False)
        act(m, "Сбросить цвета (чёрный / белый)", self.default_colors, "D", needs_doc=False)

        m = mb.addMenu("Выделение")
        act(m, "Выделить всё", self.select_all, "Ctrl+A")
        act(m, "Снять выделение", self.deselect, "Ctrl+D")
        act(m, "Инвертировать", self.invert_selection, "Ctrl+Shift+I")
        act(m, "Выделить непрозрачное слоя", self.select_opaque)
        act(m, "Расширить на…", lambda: self.grow_selection(1))
        act(m, "Сузить на…", lambda: self.grow_selection(-1))

        m = mb.addMenu("Изображение")
        act(m, "Размер изображения…", self.image_size, "Ctrl+Alt+I")
        act(m, "Размер холста…", self.canvas_size, "Ctrl+Alt+C")
        act(m, "Кадрировать по выделению", self.crop)
        m.addSeparator()
        act(m, "Повернуть на 90° по часовой", lambda: self.rotate_image(90))
        act(m, "Повернуть на 90° против часовой", lambda: self.rotate_image(-90))
        act(m, "Повернуть на 180°", lambda: self.rotate_image(180))
        act(m, "Отразить всё по горизонтали", lambda: self.flip_image(True))
        act(m, "Отразить всё по вертикали", lambda: self.flip_image(False))
        m.addSeparator()
        act(m, "Цвет фона…", self.background_color)

        m = mb.addMenu("Слой")
        act(m, "Новый слой", self.new_layer, "Ctrl+Shift+N")
        act(m, "Дублировать слой", self.duplicate_layer, "Ctrl+J")
        act(m, "Удалить слой", self.delete_layer)
        act(m, "Объединить с нижним", self.merge_down, "Ctrl+E")
        act(m, "Свести изображение", self.flatten)
        act(m, "Очистить слой", self.clear_layer)
        m.addSeparator()
        act(m, "Переименовать…", self.rename_layer, "F2")
        act(m, "Обтравочная маска", lambda: self.set_layer_prop("clip", not self.doc.current.clip), "Ctrl+Alt+G")
        act(m, "Защитить прозрачность", lambda: self.set_layer_prop("alpha_lock", not self.doc.current.alpha_lock), "/")
        act(m, "Показать / скрыть", lambda: self.toggle_layer(self.doc.current, "visible"))
        act(m, "Заблокировать / разблокировать", lambda: self.toggle_layer(self.doc.current, "locked"))
        act(m, "Поднять", lambda: self.move_layer(1), "Ctrl+]")
        act(m, "Опустить", lambda: self.move_layer(-1), "Ctrl+[")

        m = mb.addMenu("Фильтры")
        act(m, "Яркость / контраст…", lambda: self.adjust("bc"), "Ctrl+Shift+B")
        act(m, "Цветовой тон / насыщенность…", lambda: self.adjust("hsl"), "Ctrl+U")
        act(m, "Уровни…", lambda: self.adjust("levels"), "Ctrl+L")
        act(m, "Размытие по Гауссу…", lambda: self.adjust("blur"))
        act(m, "Резкость…", lambda: self.adjust("sharpen"))
        act(m, "Постеризация…", lambda: self.adjust("posterize"))
        act(m, "Порог (чёрно-белый лайнарт)…", lambda: self.adjust("threshold"))
        act(m, "Шум…", lambda: self.adjust("noise"))
        m.addSeparator()
        act(m, "Обесцветить", lambda: self.quick_filter(imgops.grayscale, "Обесцветить"), "Ctrl+Shift+U")
        act(m, "Инвертировать цвета", lambda: self.quick_filter(imgops.invert, "Инверсия"), "Ctrl+I")

        m = mb.addMenu("Манга")
        act(m, "Раскадровка страницы…", self.panel_grid)
        act(m, "Скринтон в выделение", self.tone_selection)
        act(m, "Извлечь линии из скана (белое → прозрачное)", self.extract_lines)
        act(m, "Текст…", lambda: self.add_text(None))
        act(m, "Инструмент «Кадр»", lambda: self.select_tool("panel"), needs_doc=False)
        act(m, "Инструмент «Реплика»", lambda: self.select_tool("bubble"), needs_doc=False)

        m = mb.addMenu("Анимация")
        act(m, "Проиграть / пауза", self.toggle_play, "Return")
        act(m, "Ключ всех свойств слоя", self.key_all, "Shift+K")
        act(m, "Удалить ключи на кадре", self.remove_keys_here)
        act(m, "Сбросить анимацию слоя", self.clear_animation)
        m.addSeparator()
        act(m, "К началу", lambda: self.goto_frame(0), "Home")
        act(m, "Кадр назад", lambda: self.step_frame(-1), ",")
        act(m, "Кадр вперёд", lambda: self.step_frame(1), ".")
        act(m, "К концу", lambda: self.goto_frame(-1), "End")
        act(m, "Параметры композиции…", self.comp_settings)

        m = mb.addMenu("Вид")
        act(m, "Приблизить", lambda: self.canvas.step_zoom(1), ["Ctrl+=", "Ctrl++"])
        act(m, "Отдалить", lambda: self.canvas.step_zoom(-1), "Ctrl+-")
        act(m, "Вписать в окно", self.canvas.fit, "Ctrl+0")
        act(m, "Масштаб 100%", lambda: self.canvas.set_zoom(1.0), "Ctrl+1")
        m.addSeparator()
        act(m, "Повернуть вид влево", lambda: self.canvas.rotate_view(-15), "Alt+[")
        act(m, "Повернуть вид вправо", lambda: self.canvas.rotate_view(15), "Alt+]")
        act(m, "Сбросить поворот", lambda: self.canvas.rotate_view(0, absolute=True), "Alt+0")
        act(m, "Зеркально (проверка рисунка)", self.canvas.flip_view, "Alt+H")
        m.addSeparator()
        for key, d in self.docks.items():
            a = d.toggleViewAction()
            a.setText({"color": "Панель «Цвет»", "brushes": "Панель «Кисти»", "layers": "Панель «Слои»",
                       "timeline": "Панель «Анимация»"}[key])
            m.addAction(a)
        act(m, "Скрыть / показать панели", self.toggle_panels, "Tab", needs_doc=False)
        theme = m.addMenu("Тема")
        self.theme_group = QActionGroup(self)
        self.theme_actions = {}
        for key, label in (("system", "Системная"), ("light", "Светлая"), ("dark", "Тёмная")):
            a = act(theme, label, lambda k=key: self.set_theme(k), needs_doc=False, checkable=True)
            self.theme_group.addAction(a)
            self.theme_actions[key] = a

        m = mb.addMenu("Инструменты")
        for tool in self.tools:
            sc = {"⇧G": "Shift+G", "⇧U": "Shift+U", "⇧M": "Shift+M", "⇧T": "Shift+T", "⌘T": None}.get(tool.shortcut, tool.shortcut)
            act(m, tool.name, lambda k=tool.key: self.select_tool(k), sc, needs_doc=False)
        m.addSeparator()
        act(m, "Кисть больше", lambda: self.size_box.setValue(int(self.size_box.value() * 1.15) + 1), "]", needs_doc=False)
        act(m, "Кисть меньше", lambda: self.size_box.setValue(max(1, int(self.size_box.value() / 1.15))), "[", needs_doc=False)

        m = mb.addMenu("Справка")
        act(m, f"О программе {APP_NAME}", self.about, needs_doc=False).setMenuRole(QAction.AboutRole)

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
        c = self.theme
        self.app.setStyleSheet(stylesheet(c))
        for tool in self.tools:
            self.tool_buttons[tool.key].setIcon(icons.icon(tool.icon, c["text"], c["accent"]))
        self.timeline.play.setIcon(icons.icon("play", c["text"], c["accent"]))
        self.theme_actions[self.settings.get("theme", "system")].setChecked(True)
        self.layers_panel.refresh()
        self.canvas.update()
        self.timeline.track.update()

    def set_theme(self, mode):
        self.settings["theme"] = mode
        self.settings.save()
        self.apply_theme()

    def changeEvent(self, e):
        if e.type() == e.Type.PaletteChange and self.settings.get("theme") == "system":
            if self._is_dark() != (self.theme is DARK):
                QTimer.singleShot(0, self.apply_theme)
        super().changeEvent(e)

    # ================================================================== tools / colours / brushes
    def tool_by_key(self, key):
        return next(t for t in self.tools if t.key == key)

    def select_tool(self, key, keep_brush=False):
        prev = self.tool
        if prev.key == "transform" and key != "transform":
            prev.apply()
        self.tool = self.tool_by_key(key)
        self.tool_buttons[key].setChecked(True)
        self.tool_label.setText(self.tool.name)
        self.hint_label.setText(self.tool.hint)
        groups = {"brush": key in ("brush", "eraser"), "fill": key in ("fill", "wand", "tone"), "tone": key == "tone",
                  "shape": key in ("rect", "ellipse"), "gradient": key == "gradient", "panel": key == "panel",
                  "transform": key == "transform"}
        for k, wraps in self.opt.items():
            for w in wraps:
                w.setVisible(groups.get(k, False))
        if key in ("brush", "eraser"):
            self._sync_brush_ui()
        if key == "transform" and self.doc is not None:
            self.tool.activate()
        self.canvas.setCursor(self.tool.cursor)
        self.canvas.update()

    def _sync_brush_ui(self):
        b = self.eraser_brush if self.tool.key == "eraser" else self.brush
        self._syncing = True
        self.size_box.setValue(int(b.size))
        self._syncing = False
        self.brush_name.setText(f"{b.icon} {b.name}")
        self.brush_panel.show_brush(b)

    def set_color(self, color, secondary=False, from_picker=False):
        color = QColor(color)
        if secondary:
            self.secondary = color
        else:
            self.primary = color
        if not from_picker:
            self.color_panel.show_color(color, secondary)
        self.color_panel.swatches.update()

    def remember_color(self):
        self.color_panel.swatches.remember(self.primary)

    def swap_colors(self):
        self.primary, self.secondary = self.secondary, self.primary
        self.color_panel.show_color(self.primary)

    def default_colors(self):
        self.primary, self.secondary = QColor("#141413"), QColor("#FFFFFF")
        self.color_panel.show_color(self.primary)

    # ================================================================== documents
    def add_document(self, doc):
        self.docs.append(doc)
        i = self.tabs.addTab(doc.title())
        self.tabs.setCurrentIndex(i)
        self._tab_changed(i)
        QTimer.singleShot(0, self.canvas.fit)

    def _tab_changed(self, i):
        self.stop_play()
        self.doc = self.docs[i] if 0 <= i < len(self.docs) else None
        self.canvas.set_document(self.doc)
        self._update_all()

    def new_document(self):
        d = NewDocDialog(self)
        if d.exec() != QDialog.Accepted:
            return
        s = self.settings
        s.update(new_width=d.w.value(), new_height=d.h.value(), new_dpi=d.dpi.value(), new_background=d.bg.currentData())
        s.save()
        bg = None if d.bg.currentData() == "transparent" else d.bg.currentData()
        doc = Document(d.w.value(), d.h.value(), bg, d.dpi.value())
        doc.fps = d.fps.value()
        doc.length = max(1, round(d.secs.value() * doc.fps))
        n = sum(1 for x in self.docs if x.path is None) + 1
        doc.title_hint = f"Рисунок-{n}"
        self.add_document(doc)

    def new_manga_page(self):
        doc = Document(1240, 1754, "#FFFFFF", 150)
        doc.layers[0].name = "Набросок"
        doc.title_hint = f"Страница-{sum(1 for x in self.docs if x.path is None) + 1}"
        self.add_document(doc)
        self.panel_grid()

    def open_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Открыть", self.settings.get("last_dir") or str(Path.home()),
                                                fileio.OPEN_FILTER)
        for p in paths:
            self.open_path(p)

    def open_path(self, path):
        path = Path(path)
        for i, d in enumerate(self.docs):
            if d.path and d.path.resolve() == path.resolve():
                self.tabs.setCurrentIndex(i)
                return
        try:
            ext = path.suffix.lower()
            if ext == ".delta":
                doc = fileio.load_delta(path)
            elif ext == ".ora":
                doc = fileio.load_ora(path)
            else:
                doc = fileio.load_image_document(path)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Не удалось открыть «{path.name}»: {exc}")
            return
        self.settings["last_dir"] = str(path.parent)
        self.settings.add_recent(str(path))
        self.add_document(doc)
        self.welcome.fill_recent()

    def _fill_recent(self):
        self.recent_menu.clear()
        for p in self.settings.get("recent", []):
            if Path(p).exists():
                self.recent_menu.addAction(str(p).replace(str(Path.home()), "~"), lambda p=p: self.open_path(p))
        if self.recent_menu.isEmpty():
            self.recent_menu.addAction("Пусто").setEnabled(False)

    def place_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Поместить изображение", self.settings.get("last_dir") or str(Path.home()),
                                              fileio.IMAGE_FILTER)
        if path:
            img = QImage(path)
            if img.isNull():
                QMessageBox.warning(self, APP_NAME, "Не удалось прочитать изображение")
                return
            self._image_as_layer(img, Path(path).stem)

    def _image_as_layer(self, img, name, pos=None):
        doc = self.doc
        img = img.convertToFormat(FMT)
        if img.width() > doc.width or img.height() > doc.height:
            img = img.scaled(doc.width, doc.height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        layer_img = blank(doc.width, doc.height)
        p = QPainter(layer_img)
        if pos is None:
            pos = QPointF((doc.width - img.width()) / 2, (doc.height - img.height()) / 2)
        p.drawImage(pos, img)
        p.end()
        doc.push("Поместить")
        doc.add_layer(name, doc.current, layer_img)
        self.document_changed(thumbs=True)
        self.select_tool("transform")

    def save(self):
        if self.doc is None:
            return False
        if self.doc.path is None or self.doc.path.suffix.lower() != ".delta":
            return self.save_as()
        return self._write(self.doc.path)

    def save_as(self):
        if self.doc is None:
            return False
        base = self.doc.path.stem if self.doc.path else self.doc.title()
        start = str(Path(self.settings.get("last_dir") or Path.home()) / f"{base}.delta")
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить как", start, "Дельта (*.delta)")
        if not path:
            return False
        if not path.lower().endswith(".delta"):
            path += ".delta"
        return self._write(Path(path))

    def _write(self, path):
        try:
            fileio.save_delta(self.doc, path)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Не удалось сохранить: {exc}")
            return False
        self.doc.path = Path(path)
        self.doc.mark_saved()
        self.settings["last_dir"] = str(Path(path).parent)
        self.settings.add_recent(str(path))
        self._update_title()
        self.status_message(f"Сохранено: {Path(path).name}")
        return True

    def close_doc(self, i):
        if not 0 <= i < len(self.docs):
            return True
        doc = self.docs[i]
        if doc.modified:
            box = QMessageBox(self)
            box.setWindowTitle(APP_NAME)
            box.setText(f"Сохранить изменения в «{doc.title()}»?")
            save = box.addButton("Сохранить", QMessageBox.AcceptRole)
            box.addButton("Не сохранять", QMessageBox.DestructiveRole)
            cancel = box.addButton("Отмена", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is cancel:
                return False
            if box.clickedButton() is save:
                self.tabs.setCurrentIndex(i)
                if not self.save():
                    return False
        self.docs.pop(i)
        self.tabs.removeTab(i)
        self._tab_changed(self.tabs.currentIndex())
        return True

    def closeEvent(self, e):
        while self.docs:
            if not self.close_doc(len(self.docs) - 1):
                e.ignore()
                return
        self.settings["dock_state"] = bytes(self.saveState().toBase64()).decode()
        self.settings.save()
        e.accept()

    def export_dialog(self):
        doc = self.doc
        d = ExportDialog(self, doc)
        if d.exec() != QDialog.Accepted:
            return
        kind = d.kind.currentData()
        scale = d.scale.value() / 100
        self.settings["export_scale"] = scale
        ext = {"sequence": "png"}.get(kind, kind)
        base = doc.path.stem if doc.path else doc.title()
        start = str(Path(self.settings.get("last_dir") or Path.home()) / f"{base}.{ext}")
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт", start, f"{ext.upper()} (*.{ext})")
        if not path:
            return
        if not path.lower().endswith("." + ext):
            path += "." + ext
        progress = None
        if kind in ("gif", "mp4", "sequence"):
            progress = QProgressDialog("Экспорт анимации…", "Отмена", 0, doc.length, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(300)

        def tick(f):
            if progress is None:
                return True
            progress.setValue(f + 1)
            QApplication.processEvents()
            return not progress.wasCanceled()
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            if kind in ("png", "jpg", "webp"):
                fileio.save_flat(doc, path, scale)
            elif kind == "psd":
                fileio.save_psd(doc, path)
            elif kind == "ora":
                fileio.save_ora(doc, path)
            elif kind == "gif":
                fileio.save_gif(doc, path, scale, progress=tick)
            elif kind == "mp4":
                fileio.save_mp4(doc, path, scale, progress=tick)
            else:
                fileio.save_sequence(doc, path, scale, progress=tick)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, APP_NAME, f"Экспорт не удался: {exc}")
            return
        finally:
            if progress:
                progress.close()
        QApplication.restoreOverrideCursor()
        self.settings["last_dir"] = str(Path(path).parent)
        self.settings.save()
        self.status_message(f"Экспортировано: {Path(path).name}")

    # ================================================================== edit
    def _editable(self):
        if self.doc is None:
            return False
        if self.doc.current.locked:
            self.status_message("Слой заблокирован")
            return False
        return True

    def undo(self):
        tool = self.tool
        if tool.key == "transform" and getattr(tool, "t", None) is not None:
            tool.cancel()
            return
        if self.doc and self.doc.undo():
            self.document_changed(thumbs=True)
        else:
            self.status_message("Нечего отменять")

    def redo(self):
        if self.doc and self.doc.redo():
            self.document_changed(thumbs=True)

    def _layer_clip(self):
        doc = self.doc
        inv, _ = doc.current.transform(doc.frame, doc.width, doc.height).inverted()
        return inv.map(doc.clip_path())

    def copy(self, merged=False):
        doc = self.doc
        src = doc.render(background=False) if merged else doc.current.image
        rect = doc.clip_path().boundingRect().toAlignedRect().intersected(QRect(0, 0, doc.width, doc.height))
        piece = blank(rect.width(), rect.height())
        p = QPainter(piece)
        p.translate(-rect.x(), -rect.y())
        p.setClipPath(doc.clip_path())
        p.drawImage(0, 0, src)
        p.end()
        self.clipboard = (piece, rect.topLeft())
        QApplication.clipboard().setImage(piece)
        self.status_message("Скопировано")

    def cut(self):
        if self._editable():
            self.copy()
            self.clear_selection("Вырезать")

    def paste(self):
        img = QApplication.clipboard().image()
        pos = None
        if self.clipboard is not None and (img.isNull() or img.size() == self.clipboard[0].size()):
            img, pos = self.clipboard
            pos = QPointF(pos)
        if img.isNull():
            self.status_message("В буфере нет изображения")
            return
        if self.doc is None:
            return self.paste_as_document()
        self._image_as_layer(img, "Вставка", pos)

    def paste_as_document(self):
        img = QApplication.clipboard().image()
        if img.isNull():
            self.status_message("В буфере нет изображения")
            return
        doc = Document(img.width(), img.height(), None)
        doc.layers[0].image = img.convertToFormat(FMT)
        doc.title_hint = "Из буфера"
        self.add_document(doc)

    def _paint_layer(self, label, fn):
        """fn(painter) on a copy of the current layer image inside the selection."""
        if not self._editable():
            return
        doc, layer = self.doc, self.doc.current
        doc.push(label)
        img = layer.image.copy()
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setClipPath(self._layer_clip())
        fn(p, img)
        p.end()
        layer.image = img
        self.document_changed(thumbs=True)

    def clear_selection(self, label="Очистить"):
        def fn(p, img):
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.fillRect(img.rect(), Qt.transparent)
        self._paint_layer(label, fn)

    def fill_selection(self):
        def fn(p, img):
            if self.doc.current.alpha_lock:
                p.setCompositionMode(QPainter.CompositionMode_SourceAtop)
            p.fillRect(img.rect(), self.primary)
        self._paint_layer("Залить", fn)

    def stroke_selection(self):
        doc = self.doc
        if not doc.has_selection():
            self.status_message("Сначала выделите область")
            return
        if not self._editable():
            return
        from .brushes import path_points, stroke_path

        inv, _ = doc.current.transform(doc.frame, doc.width, doc.height).inverted()
        path = inv.map(doc.selection)
        b = Brush.from_dict({**self.brush.to_dict(), "pressure_size": False, "smoothing": 0, "mode": "paint"})
        doc.push("Обводка")
        doc.current.image = stroke_path(b, doc.current, self.primary, path_points(path, max(0.5, b.size * b.spacing)))
        self.document_changed(thumbs=True)

    def flip_layer(self, horizontal):
        if self._editable():
            self.doc.push("Отразить слой")
            self.doc.current.image = self.doc.current.image.mirrored(horizontal, not horizontal)
            self.document_changed(thumbs=True)

    # ------------------------------------------------------------------ selection
    def select_all(self):
        self.doc.push("Выделение")
        p = QPainterPath()
        p.addRect(self.doc.rect())
        self.doc.selection = p
        self.selection_changed()

    def deselect(self):
        if self.doc and self.doc.has_selection():
            self.doc.push("Снять выделение")
            self.doc.selection = QPainterPath()
            self.selection_changed()

    def invert_selection(self):
        doc = self.doc
        full = QPainterPath()
        full.addRect(doc.rect())
        doc.push("Инвертировать выделение")
        doc.selection = full.subtracted(doc.selection) if doc.has_selection() else QPainterPath()
        self.selection_changed()

    def select_opaque(self):
        doc = self.doc
        a = imgops.to_array(doc.current.image)
        path = imgops.mask_to_path(a[..., 3] > 0)
        doc.push("Выделение")
        doc.selection = doc.current.transform(doc.frame, doc.width, doc.height).map(path)
        self.selection_changed()

    def grow_selection(self, sign):
        doc = self.doc
        if not doc.has_selection():
            return
        px, ok = QInputDialog.getInt(self, "Выделение", "На сколько пикселей:", 4, 1, 500)
        if not ok:
            return
        stroker = QPainterPathStroker()
        stroker.setWidth(px * 2)
        stroker.setJoinStyle(Qt.RoundJoin)
        ring = stroker.createStroke(doc.selection)
        doc.push("Выделение")
        doc.selection = (doc.selection.united(ring) if sign > 0 else doc.selection.subtracted(ring)).simplified()
        self.selection_changed()

    # ------------------------------------------------------------------ image
    def image_size(self):
        d = CanvasSizeDialog(self, self.doc, scale=True)
        if d.exec() == QDialog.Accepted:
            self.doc.push("Размер изображения")
            self.doc.scale_image(d.w.value(), d.h.value())
            self.document_changed(thumbs=True, fit=True)

    def canvas_size(self):
        d = CanvasSizeDialog(self, self.doc)
        if d.exec() == QDialog.Accepted:
            ox, oy = d.offset()
            self.doc.push("Размер холста")
            self.doc.resize_canvas(d.w.value(), d.h.value(), ox, oy)
            self.document_changed(thumbs=True, fit=True)

    def crop(self):
        doc = self.doc
        if not doc.has_selection():
            self.status_message("Сначала выделите область")
            return
        r = doc.selection.boundingRect().toAlignedRect().intersected(QRect(0, 0, doc.width, doc.height))
        doc.push("Кадрировать")
        doc.resize_canvas(r.width(), r.height(), -r.x(), -r.y())
        self.document_changed(thumbs=True, fit=True)

    def rotate_image(self, deg):
        self.doc.push("Поворот")
        self.doc.rotate_image(deg)
        self.document_changed(thumbs=True, fit=True)

    def flip_image(self, horizontal):
        self.doc.push("Отражение")
        self.doc.flip_image(horizontal)
        self.document_changed(thumbs=True)

    def background_color(self):
        items = ["Белая бумага", "Тёплая бумага", "Прозрачный", "Чёрный", "Основной цвет"]
        vals = ["#FFFFFF", "#F6F1E4", None, "#141413", None]
        item, ok = QInputDialog.getItem(self, "Фон", "Цвет фона документа:", items, 0, False)
        if ok:
            self.doc.push("Фон")
            i = items.index(item)
            self.doc.background = self.primary.name() if i == 4 else vals[i]
            self.document_changed()

    # ------------------------------------------------------------------ filters
    def adjust(self, kind):
        if not self._editable():
            return
        doc, layer = self.doc, self.doc.current
        base = layer.image
        clip = self._layer_clip() if doc.has_selection() else None
        spec = {
            "bc": ("Яркость / контраст", [("b", "Яркость", -100, 100, 0), ("c", "Контраст", -100, 100, 0)], (),
                   lambda a, v: imgops.brightness_contrast(a, v["b"], v["c"])),
            "hsl": ("Цветовой тон / насыщенность", [("h", "Тон", -180, 180, 0), ("s", "Насыщенность", -100, 100, 0),
                                                     ("l", "Яркость", -100, 100, 0)], (("colorize", "Тонирование"),),
                    lambda a, v: imgops.hue_saturation(a, v["h"], v["s"], v["l"], v["colorize"])),
            "levels": ("Уровни", [("lo", "Чёрная точка", 0, 254, 0), ("hi", "Белая точка", 1, 255, 255),
                                  ("g", "Гамма ×100", 10, 400, 100)], (),
                       lambda a, v: imgops.levels(a, v["lo"], max(v["hi"], v["lo"] + 1), v["g"] / 100)),
            "blur": ("Размытие по Гауссу", [("r", "Радиус, px", 0, 100, 4)], (), lambda a, v: imgops.gaussian_blur(a, v["r"])),
            "sharpen": ("Резкость", [("amt", "Сила", 0, 300, 60), ("r", "Радиус", 1, 20, 2)], (),
                        lambda a, v: imgops.sharpen(a, v["amt"], v["r"])),
            "posterize": ("Постеризация", [("n", "Уровней", 2, 32, 4)], (), lambda a, v: imgops.posterize(a, v["n"])),
            "threshold": ("Порог", [("t", "Порог", 1, 254, 128)], (), lambda a, v: imgops.threshold(a, v["t"])),
            "noise": ("Шум", [("n", "Сила", 0, 100, 12)], (), lambda a, v: imgops.noise(a, v["n"])),
        }[kind]
        name, params, checks, fn = spec
        arr = imgops.to_array(base)
        preview_scale = 1.0
        if arr.shape[0] * arr.shape[1] > 3_000_000 and kind in ("blur", "sharpen", "hsl"):
            preview_scale = 0.5

        def preview(values):
            if values is None:
                self.canvas.stroke_preview(layer, base, QRect(0, 0, base.width(), base.height()))
                return
            if preview_scale != 1.0:
                small = base.scaled(int(base.width() * preview_scale), int(base.height() * preview_scale),
                                    Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                v = dict(values)
                if kind == "blur":
                    v["r"] = v["r"] * preview_scale
                out = imgops.from_array(fn(imgops.to_array(small), v)).scaled(base.size(), Qt.IgnoreAspectRatio,
                                                                              Qt.SmoothTransformation)
            else:
                out = imgops.from_array(fn(arr, values))
            if clip is not None:
                res = base.copy()
                p = QPainter(res)
                p.setClipPath(clip)
                p.setCompositionMode(QPainter.CompositionMode_Source)
                p.drawImage(0, 0, out)
                p.end()
                out = res
            self.canvas.stroke_preview(layer, out, QRect(0, 0, base.width(), base.height()))

        d = AdjustDialog(self, name, params, preview, checks)
        ok = d.exec() == QDialog.Accepted
        if ok:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            doc.push(name)
            layer.image = imgops.masked_apply(base, lambda a: fn(a, d.result_values()), clip)
            QApplication.restoreOverrideCursor()
        self.canvas.stroke_preview(None, None)
        self.document_changed(thumbs=True)

    def quick_filter(self, fn, name):
        if not self._editable():
            return
        doc, layer = self.doc, self.doc.current
        clip = self._layer_clip() if doc.has_selection() else None
        doc.push(name)
        layer.image = imgops.masked_apply(layer.image, fn, clip)
        self.document_changed(thumbs=True)

    def extract_lines(self):
        """Scanned / photographed line art → lines on transparent (luminance becomes alpha)."""
        if not self._editable():
            return
        import numpy as np

        doc, layer = self.doc, self.doc.current
        a = imgops.to_array(layer.image)
        y = imgops.grayscale(a)[..., 0].astype(np.float32)
        alpha = np.clip((255 - y) * 1.4 - 20, 0, 255) * (a[..., 3] / 255.0)
        out = np.zeros_like(a)
        c = self.primary
        out[..., 0], out[..., 1], out[..., 2] = c.blue(), c.green(), c.red()
        out[..., 3] = alpha.astype(np.uint8)
        doc.push("Извлечь линии")
        layer.image = imgops.from_array(out)
        self.document_changed(thumbs=True)
        self.status_message("Линии извлечены цветом основного цвета — белое стало прозрачным")

    # ------------------------------------------------------------------ manga
    def _panels_layer(self):
        doc = self.doc
        layer = next((l for l in doc.layers if l.name == "Кадры"), None)
        if layer is None:
            layer = doc.add_layer("Кадры")
        doc.current = layer
        return layer

    def draw_panels(self, rects):
        doc = self.doc
        doc.push("Кадры")
        layer = self._panels_layer()
        img = layer.image.copy()
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, False)
        w = int(self.settings.get("panel_width", 6))
        pen = QPen(QColor("#141413"), w)
        pen.setJoinStyle(Qt.MiterJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        for r in rects:
            p.drawRect(QRectF(r).adjusted(w / 2, w / 2, -w / 2, -w / 2))
        p.end()
        layer.image = img
        self.document_changed(thumbs=True)

    def panel_grid(self):
        if self.doc is None:
            return
        d = PanelGridDialog(self)
        if d.exec() != QDialog.Accepted:
            return
        self.settings["panel_gutter"] = d.gutter.value()
        self.settings["panel_width"] = d.width_.value()
        self.settings.save()
        doc = self.doc
        m, g = d.margin.value(), d.gutter.value()
        rows, cols = d.rows.value(), d.cols.value()
        cw = (doc.width - 2 * m - (cols - 1) * g) / cols
        ch = (doc.height - 2 * m - (rows - 1) * g) / rows
        rects = [QRectF(m + c * (cw + g), m + r * (ch + g), cw, ch) for r in range(rows) for c in range(cols)]
        self.draw_panels(rects)

    def make_bubble(self, rect, tail):
        doc = self.doc
        d = TextDialog(self)
        d.outline.setVisible(False)
        if d.exec() != QDialog.Accepted:
            return
        doc.push("Реплика")
        layer = doc.add_layer("Реплика", doc.current)
        img = layer.image
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#141413"), max(2.0, min(rect.width(), rect.height()) / 60)))
        p.setBrush(QColor("#FFFFFF"))
        p.drawPath(bubble_path(rect, tail))
        self._draw_text(p, d, rect.adjusted(rect.width() * 0.16, rect.height() * 0.16, -rect.width() * 0.16, -rect.height() * 0.16))
        p.end()
        layer.image = img
        self._remember_text(d)
        self.document_changed(thumbs=True)

    def add_text(self, pt):
        doc = self.doc
        if doc is None:
            return
        d = TextDialog(self)
        if d.exec() != QDialog.Accepted or not d.text.toPlainText().strip():
            return
        if pt is None:
            pt = QPointF(doc.width / 2, doc.height / 2)
        doc.push("Текст")
        layer = doc.add_layer("Текст: " + d.text.toPlainText().strip().split("\n")[0][:24], doc.current)
        img = layer.image
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        size = d.size.value()
        lines = d.text.toPlainText().split("\n")
        rect = QRectF(pt.x(), pt.y(), doc.width - pt.x(), doc.height - pt.y())
        if d.vertical.isChecked():
            rect = QRectF(pt.x() - size * len(lines) * 1.2, pt.y(), size * len(lines) * 1.2 + size, doc.height - pt.y())
        self._draw_text(p, d, rect, align=Qt.AlignLeft | Qt.AlignTop, outline=d.outline.isChecked())
        p.end()
        layer.image = img
        self._remember_text(d)
        self.document_changed(thumbs=True)

    def _remember_text(self, d):
        self.settings.update(text_font=d.font.currentFont().family(), text_size=d.size.value(),
                             text_vertical=d.vertical.isChecked())
        self.settings.save()

    def _draw_text(self, p, d, rect, align=Qt.AlignCenter, outline=False):
        font = QFont(d.font.currentFont())
        font.setPixelSize(d.size.value())
        font.setBold(d.bold.isChecked())
        p.setFont(font)
        text = d.text.toPlainText()
        color = QColor(self.primary)
        if d.vertical.isChecked():
            # columns right-to-left, characters top-to-bottom (Japanese manga style)
            fm = QFontMetricsF(font)
            step = fm.height() * 0.95
            cols = text.split("\n")
            total_w = len(cols) * step
            x0 = rect.center().x() + total_w / 2 - step if align == Qt.AlignCenter else rect.right() - step
            for i, col in enumerate(cols):
                y = rect.top() + (max(0.0, (rect.height() - len(col) * step) / 2) if align == Qt.AlignCenter else 0)
                for ch in col:
                    r = QRectF(x0 - i * step, y, step, step)
                    self._text_at(p, r, ch, color, outline, Qt.AlignCenter)
                    y += step
            return
        self._text_at(p, rect, text, color, outline, align | Qt.TextWordWrap)

    def _text_at(self, p, rect, text, color, outline, flags):
        if outline:
            path = QPainterPath()
            fm = QFontMetricsF(p.font())
            br = fm.boundingRect(rect, int(flags), text)
            y = br.top() + fm.ascent()
            for line in text.split("\n"):
                path.addText(QPointF(br.left(), y), p.font(), line)
                y += fm.lineSpacing()
            p.save()
            p.setPen(QPen(QColor("#FFFFFF"), max(3.0, p.font().pixelSize() / 6), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawPath(path)
            p.restore()
            return
        p.setPen(color)
        p.drawText(rect, int(flags), text)

    def tone_selection(self):
        doc = self.doc
        if not doc.has_selection():
            self.status_message("Выделите область для скринтона (или используйте инструмент «Скринтон» — T)")
            return
        if not self._editable():
            return
        s = self.settings
        doc.push("Скринтон")
        doc.current.image = imgops.tone_fill(doc.current.image, self._layer_clip(), int(s.get("tone_spacing", 8)),
                                             int(s.get("tone_size", 50)), int(s.get("tone_angle", 45)), self.primary)
        self.document_changed(thumbs=True)

    # ------------------------------------------------------------------ layers
    def select_layer(self, layer):
        self.doc.current = layer
        self.layers_panel.refresh()
        self.timeline.update_view()

    def toggle_layer(self, layer, attr):
        self.doc.push("Слой")
        setattr(layer, attr, not getattr(layer, attr))
        self.document_changed(thumbs=True)

    def set_layer_prop(self, attr, value):
        if self.doc is None or getattr(self.doc.current, attr) == value:
            return
        self.doc.push("Свойства слоя")
        setattr(self.doc.current, attr, value)
        self.document_changed(thumbs=True)

    def rename_layer(self):
        layer = self.doc.current
        name, ok = QInputDialog.getText(self, "Слой", "Имя слоя:", text=layer.name)
        if ok and name.strip():
            self.doc.push("Переименовать")
            layer.name = name.strip()
            self.document_changed(thumbs=True)

    def new_layer(self):
        self.doc.push("Новый слой")
        self.doc.add_layer(above=self.doc.current)
        self.document_changed(thumbs=True)

    def duplicate_layer(self):
        self.doc.push("Дублировать слой")
        self.doc.duplicate_layer(self.doc.current)
        self.document_changed(thumbs=True)

    def delete_layer(self):
        if len(self.doc.layers) <= 1:
            self.status_message("Нельзя удалить единственный слой")
            return
        self.doc.push("Удалить слой")
        self.doc.remove_layer(self.doc.current)
        self.document_changed(thumbs=True)

    def merge_down(self):
        if self.doc.index(self.doc.current) == 0:
            self.status_message("Ниже нет слоя")
            return
        self.doc.push("Объединить")
        self.doc.merge_down(self.doc.current)
        self.document_changed(thumbs=True)

    def flatten(self):
        doc = self.doc
        doc.push("Свести")
        img = doc.render(background=False)
        doc.layers = [Layer("Фон", img)]
        doc.current = doc.layers[0]
        self.document_changed(thumbs=True)

    def clear_layer(self):
        if self._editable():
            self.doc.push("Очистить слой")
            self.doc.current.image = blank(self.doc.width, self.doc.height)
            self.document_changed(thumbs=True)

    def move_layer(self, d):
        self.doc.push("Порядок слоёв")
        self.doc.move_layer(self.doc.current, d)
        self.document_changed(thumbs=True)

    # ================================================================== animation
    def goto_frame(self, f):
        doc = self.doc
        if doc is None:
            return
        doc.frame = f % doc.length if f >= 0 else doc.length - 1
        self.canvas.refresh()
        self.timeline.update_view()

    def step_frame(self, d):
        if self.doc:
            self.goto_frame((self.doc.frame + d) % self.doc.length)

    def toggle_play(self):
        if self.play_timer.isActive():
            self.stop_play()
            return
        if self.doc is None:
            return
        self.play_timer.start(max(5, int(1000 / self.doc.fps)))
        self.timeline.play.setChecked(True)
        self.timeline.play.setIcon(icons.icon("pause", self.theme["text"], self.theme["accent"]))

    def stop_play(self):
        self.play_timer.stop()
        self.timeline.play.setChecked(False)
        self.timeline.play.setIcon(icons.icon("play", self.theme["text"], self.theme["accent"]))

    def _play_step(self):
        doc = self.doc
        if doc is None:
            self.stop_play()
            return
        nxt = doc.frame + 1
        if nxt >= doc.length:
            if not self.timeline.loop.isChecked():
                self.stop_play()
                return
            nxt = 0
        self.goto_frame(nxt)

    def set_comp(self, fps=None, length=None):
        doc = self.doc
        if doc is None:
            return
        doc.push("Композиция")
        if fps:
            doc.fps = fps
        if length:
            doc.length = length
            doc.frame = min(doc.frame, length - 1)
        if self.play_timer.isActive():
            self.play_timer.setInterval(max(5, int(1000 / doc.fps)))
        self.document_changed()

    def comp_settings(self):
        doc = self.doc
        fps, ok = QInputDialog.getInt(self, "Композиция", "Кадров в секунду:", doc.fps, 1, 120)
        if not ok:
            return
        secs, ok = QInputDialog.getDouble(self, "Композиция", "Длительность, секунд:", doc.length / doc.fps, 0.1, 3600, 2)
        if ok:
            self.set_comp(fps, max(1, round(secs * fps)))

    def toggle_key(self, layer, prop):
        doc = self.doc
        doc.push("Ключ")
        if layer.key_at(prop, doc.frame) is not None:
            layer.remove_key(prop, doc.frame)
        else:
            layer.set_key(prop, doc.frame, layer.value(prop, doc.frame))
        self.document_changed()

    def key_all(self):
        doc = self.doc
        doc.push("Ключи")
        for key, _n, _d in PROPS:
            doc.current.set_key(key, doc.frame, doc.current.value(key, doc.frame))
        self.document_changed()
        self.status_message("Ключи поставлены — перейдите на другой кадр и измените слой (V — двигать, ⌘T — масштаб/поворот)")

    def remove_keys_here(self):
        doc = self.doc
        doc.push("Удалить ключи")
        for key, _n, _d in PROPS:
            doc.current.remove_key(key, doc.frame)
        self.document_changed()

    def clear_animation(self):
        self.doc.push("Сбросить анимацию")
        self.doc.current.keys = {}
        self.document_changed()

    def edit_key_value(self, layer, prop):
        doc = self.doc
        name = dict((k, n) for k, n, _d in PROPS)[prop]
        val, ok = QInputDialog.getDouble(self, name, f"{name} на кадре {doc.frame}:", layer.value(prop, doc.frame), -100000,
                                         100000, 2)
        if ok:
            doc.push("Значение")
            layer.set_key(prop, doc.frame, val)
            self.document_changed()

    def set_key_ease(self, layer, prop, key, kind):
        self.doc.push("Сглаживание ключа")
        key.ease = kind
        self.document_changed()

    def remove_key(self, layer, prop, frame):
        self.doc.push("Удалить ключ")
        layer.remove_key(prop, frame)
        self.document_changed()

    # ================================================================== view & misc
    def toggle_panels(self):
        vis = not any(d.isVisible() for d in self.docks.values())
        for d in self.docks.values():
            d.setVisible(vis)

    def preferences(self):
        d = QDialog(self)
        d.setWindowTitle("Настройки")
        lay = QVBoxLayout(d)
        lay.setContentsMargins(24, 20, 24, 18)
        t = QLabel("Настройки")
        t.setObjectName("Title")
        lay.addWidget(t)
        row = QHBoxLayout()
        row.addWidget(QLabel("Тема"))
        theme = QComboBox()
        for key, label in (("system", "Системная"), ("light", "Светлая"), ("dark", "Тёмная")):
            theme.addItem(label, key)
        theme.setCurrentIndex(theme.findData(self.settings.get("theme", "system")))
        row.addWidget(theme)
        lay.addLayout(row)
        reset = QPushButton("Сбросить все настройки кистей")
        reset.clicked.connect(lambda: (self.settings.update(brushes={}), self.settings.save(), self.brush_panel.load()))
        lay.addWidget(reset)
        ok = QPushButton("Готово")
        ok.setObjectName("Accent")
        ok.clicked.connect(d.accept)
        lay.addWidget(ok)
        if d.exec() == QDialog.Accepted:
            self.set_theme(theme.currentData())

    def about(self):
        QMessageBox.about(self, APP_NAME, f"<h2 style='font-family:Georgia'>{LOGO} {APP_NAME}</h2>"
                          f"<p>Рисование манги, персонажей и анимации, версия {__version__}.</p>"
                          "<p>Кисти с нажимом пера, слои, скринтон, кадры и реплики, анимация по ключам.</p>")

    def status_message(self, text, ms=5000):
        self.msg.setText(text)
        QTimer.singleShot(ms, lambda t=text: self.msg.text() == t and self.msg.setText(""))

    # ================================================================== refresh
    def document_changed(self, thumbs=False, fit=False):
        self.canvas.refresh()
        if fit:
            self.canvas.fit()
        self.layers_panel.refresh()
        self.timeline.update_view()
        self._update_status()
        self._update_title()

    def selection_changed(self):
        self.canvas.update()
        self._update_status()

    def _update_title(self):
        doc = self.doc
        i = self.tabs.currentIndex()
        if doc is not None and i >= 0:
            self.tabs.setTabText(i, ("● " if doc.modified else "") + doc.title())
            self.setWindowTitle(f"{doc.title()}{' •' if doc.modified else ''} — {LOGO} {APP_NAME}")
        else:
            self.setWindowTitle(f"{LOGO} {APP_NAME}")

    def _update_status(self):
        doc = self.doc
        if doc is None:
            self.size_label.setText("")
            return
        sel = doc.selection.boundingRect() if doc.has_selection() else None
        self.size_label.setText(f"{doc.width}×{doc.height} px · {doc.dpi} dpi · {len(doc.layers)} сл." +
                                (f" · выделено {sel.width():.0f}×{sel.height():.0f}" if sel else ""))

    def _update_all(self):
        has = self.doc is not None
        self.stack.setCurrentWidget(self.canvas if has else self.welcome)
        for a in self.doc_actions:
            a.setEnabled(has)
        self.layers_panel.refresh()
        self.timeline.update_view()
        self._update_status()
        self._update_title()
        self._view_changed()

    def _view_changed(self):
        c = self.canvas
        self.view_label.setText(f"{c.zoom * 100:.0f}%" + (f" · {c.angle:.0f}°" if c.angle else "") +
                                (" · зеркально" if c.mirror else "") if self.doc else "")

    def _hovered(self, pt):
        if pt is None or self.doc is None:
            self.pos_label.setText("")
            return
        self.pos_label.setText(f"x {pt.x():.0f}  y {pt.y():.0f}")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Delta")
    app.setApplicationDisplayName(APP_NAME)
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


