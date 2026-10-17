"""Дзета main window: tools (left), tool options (top), canvas with document tabs, colour panel (right),
timeline (bottom), menus, dialogs, open / save / export, playback."""
import json
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QImage, QImageReader, QKeySequence, QPainter, QPalette, QRegion
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QSlider,
    QSpinBox, QSplitter, QStackedWidget, QTabBar, QToolButton, QVBoxLayout, QWidget,
)

from . import APP_NAME, LOGO, __version__, ase, icons, palettes
from .canvas import Canvas
from .colorpanel import ColorPanel, Swatches
from .gif import save_gif
from .model import BLEND_MODES, FMT, TAG_DIRECTIONS, Document, Sprite, Tag, blank, content_rect
from .paths import Settings, resource_path
from .theme import DARK, LIGHT, stylesheet
from .timeline import Timeline
from .tools import TOOLS

MAC = sys.platform == "darwin"
OPEN_FILTER = "Все изображения (*.aseprite *.ase *.png *.gif *.jpg *.jpeg *.bmp *.webp);;Aseprite (*.aseprite *.ase);;PNG (*.png);;GIF (*.gif)"


# ====================================================================== file helpers
def load_sprite(path):
    path = Path(path)
    ext = path.suffix.lower()
    if ext in (".aseprite", ".ase"):
        return ase.load(path)
    reader = QImageReader(str(path))
    count = max(1, reader.imageCount())
    frames, delays = [], []
    for _ in range(count):
        img = reader.read()
        if img.isNull():
            break
        frames.append(img.convertToFormat(FMT))
        delays.append(reader.nextImageDelay() or 100)
        if not reader.canRead():
            break
    if not frames:
        raise ValueError(reader.errorString() or "Не удалось прочитать изображение")
    w, h = frames[0].width(), frames[0].height()
    sprite = Sprite(w, h)
    sprite.durations = delays
    layer = sprite.layers[0]
    for i, img in enumerate(frames):
        if img.size() != frames[0].size():
            img = img.copy(0, 0, w, h)
        sprite.set_cel(layer, i, img)
    return sprite


def unique_colors(sprite, limit=256):
    seen = {}
    for img in sprite.cels.values():
        data = bytes(img.constBits())
        n = img.width() * img.height()
        for v in struct.unpack(f"<{n}I", data[: n * 4]):
            if v >> 24:
                seen[v | 0xFF000000 if (v >> 24) == 255 else v] = True
                if len(seen) >= limit:
                    return list(seen)
    return list(seen)


# ====================================================================== dialogs
class NewSpriteDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.setWindowTitle("Новый спрайт")
        s = win.settings
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        t = QLabel("Новый спрайт")
        t.setObjectName("Title")
        lay.addWidget(t)
        presets = QHBoxLayout()
        for w, h in ((16, 16), (32, 32), (64, 64), (128, 128), (256, 144), (320, 180)):
            b = QPushButton(f"{w}×{h}")
            b.clicked.connect(lambda _=False, w=w, h=h: (self.w.setValue(w), self.h.setValue(h)))
            presets.addWidget(b)
        lay.addLayout(presets)
        form = QFormLayout()
        self.w = QSpinBox()
        self.w.setRange(1, 4096)
        self.w.setValue(int(s.get("new_width", 32)))
        self.h = QSpinBox()
        self.h.setRange(1, 4096)
        self.h.setValue(int(s.get("new_height", 32)))
        form.addRow("Ширина, px", self.w)
        form.addRow("Высота, px", self.h)
        self.bg = QComboBox()
        for key, label in (("transparent", "Прозрачный"), ("#FFFFFF", "Белый"), ("#000000", "Чёрный")):
            self.bg.addItem(label, key)
        self.bg.setCurrentIndex(max(0, self.bg.findData(s.get("new_background", "transparent"))))
        form.addRow("Фон", self.bg)
        self.pal = QComboBox()
        self.pal.addItems(list(palettes.PRESETS))
        self.pal.setCurrentText(s.get("palette", "DB32"))
        form.addRow("Палитра", self.pal)
        lay.addLayout(form)
        bb = QDialogButtonBox()
        ok = bb.addButton("Создать", QDialogButtonBox.AcceptRole)
        ok.setObjectName("Accent")
        bb.addButton("Отмена", QDialogButtonBox.RejectRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


class CanvasSizeDialog(QDialog):
    def __init__(self, win, sprite):
        super().__init__(win)
        self.setWindowTitle("Размер холста")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        t = QLabel("Размер холста")
        t.setObjectName("Title")
        lay.addWidget(t)
        form = QFormLayout()
        self.w = QSpinBox()
        self.w.setRange(1, 8192)
        self.w.setValue(sprite.width)
        self.h = QSpinBox()
        self.h.setRange(1, 8192)
        self.h.setValue(sprite.height)
        form.addRow("Ширина", self.w)
        form.addRow("Высота", self.h)
        lay.addLayout(form)
        lab = QLabel("Привязка содержимого")
        lab.setObjectName("Muted")
        lay.addWidget(lab)
        grid = QGridLayout()
        self.anchor = QButtonGroup(self)
        arrows = ["↖", "↑", "↗", "←", "•", "→", "↙", "↓", "↘"]
        for i in range(9):
            b = QToolButton()
            b.setText(arrows[i])
            b.setCheckable(True)
            b.setFixedSize(32, 32)
            self.anchor.addButton(b, i)
            grid.addWidget(b, i // 3, i % 3)
        self.anchor.button(4).setChecked(True)
        box = QHBoxLayout()
        box.addLayout(grid)
        box.addStretch(1)
        lay.addLayout(box)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def offset(self, sprite):
        i = self.anchor.checkedId()
        ax, ay = i % 3, i // 3
        dw, dh = self.w.value() - sprite.width, self.h.value() - sprite.height
        return (dw * ax) // 2, (dh * ay) // 2


class LayerDialog(QDialog):
    def __init__(self, win, layer):
        super().__init__(win)
        self.setWindowTitle("Свойства слоя")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        form = QFormLayout()
        self.name = QLineEdit(layer.name)
        form.addRow("Имя", self.name)
        self.blend = QComboBox()
        for code, label, _mode in BLEND_MODES:
            self.blend.addItem(label, code)
        self.blend.setCurrentIndex(max(0, self.blend.findData(layer.blend)))
        form.addRow("Наложение", self.blend)
        row = QHBoxLayout()
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(0, 255)
        self.opacity.setValue(layer.opacity)
        val = QLabel(str(layer.opacity))
        self.opacity.valueChanged.connect(lambda v: val.setText(str(v)))
        row.addWidget(self.opacity, 1)
        row.addWidget(val)
        form.addRow("Непрозрачность", row)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


class TagDialog(QDialog):
    def __init__(self, win, tag, frames):
        super().__init__(win)
        self.setWindowTitle("Метка анимации")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        form = QFormLayout()
        self.name = QLineEdit(tag.name)
        self.start = QSpinBox()
        self.start.setRange(1, frames)
        self.start.setValue(tag.start + 1)
        self.end = QSpinBox()
        self.end.setRange(1, frames)
        self.end.setValue(tag.end + 1)
        self.direction = QComboBox()
        self.direction.addItems(TAG_DIRECTIONS)
        self.direction.setCurrentIndex(tag.direction)
        self.color = QComboBox()
        for col, label in (("#D97757", "Терракотовый"), ("#3E8E63", "Зелёный"), ("#2E5E9E", "Синий"), ("#8A4FC2", "Фиолетовый"),
                           ("#B5862E", "Охра"), ("#6F6E69", "Серый")):
            self.color.addItem(label, col)
        idx = self.color.findData(tag.color.upper())
        self.color.setCurrentIndex(max(0, idx))
        form.addRow("Имя", self.name)
        form.addRow("С кадра", self.start)
        form.addRow("По кадр", self.end)
        form.addRow("Направление", self.direction)
        form.addRow("Цвет", self.color)
        lay.addLayout(form)
        self.delete = QCheckBox("Удалить метку")
        lay.addWidget(self.delete)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


class ExportDialog(QDialog):
    KINDS = [("png", "PNG — текущий кадр"), ("gif", "GIF — анимация"), ("sheet", "Спрайт-лист PNG + JSON"),
             ("sequence", "Последовательность PNG")]

    def __init__(self, win, doc):
        super().__init__(win)
        self.setWindowTitle("Экспорт")
        s = win.settings
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        t = QLabel("Экспорт")
        t.setObjectName("Title")
        lay.addWidget(t)
        form = QFormLayout()
        self.kind = QComboBox()
        for key, label in self.KINDS:
            self.kind.addItem(label, key)
        form.addRow("Формат", self.kind)
        self.scale = QSpinBox()
        self.scale.setRange(1, 20)
        self.scale.setValue(int(s.get("export_scale", 1)))
        self.scale.setSuffix("×")
        form.addRow("Масштаб", self.scale)
        self.range = QComboBox()
        self.range.addItem("Все кадры", None)
        for i, tag in enumerate(doc.sprite.tags):
            self.range.addItem(f"Метка «{tag.name}» ({tag.start + 1}–{tag.end + 1})", i)
        form.addRow("Кадры", self.range)
        self.layout_ = QComboBox()
        for key, label in (("row", "В строку"), ("column", "В столбец"), ("grid", "Сеткой")):
            self.layout_.addItem(label, key)
        form.addRow("Раскладка листа", self.layout_)
        lay.addLayout(form)
        self.kind.currentIndexChanged.connect(self._sync)
        self._sync()
        bb = QDialogButtonBox()
        ok = bb.addButton("Экспортировать…", QDialogButtonBox.AcceptRole)
        ok.setObjectName("Accent")
        bb.addButton("Отмена", QDialogButtonBox.RejectRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _sync(self):
        k = self.kind.currentData()
        self.range.setEnabled(k != "png")
        self.layout_.setEnabled(k == "sheet")


# ====================================================================== welcome
class Welcome(QWidget):
    def __init__(self, win):
        super().__init__()
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
        sub = QLabel(f"Пиксель-арт и анимация · версия {__version__}")
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
        for text, fn in (("Новый спрайт…", win.new_sprite), ("Открыть…", win.open_dialog),
                         ("Вставить из буфера как спрайт", win.paste_as_new)):
            b = QPushButton(text)
            b.setObjectName("Link")
            b.clicked.connect(fn)
            a.addWidget(b)
        a.addStretch(1)
        row.addLayout(a)
        r = QVBoxLayout()
        s = QLabel("НЕДАВНИЕ")
        s.setObjectName("Section")
        r.addWidget(s)
        self.recent = r
        self.win = win
        self.fill_recent()
        row.addLayout(r)
        col.addLayout(row)
        col.addSpacing(18)
        k = QLabel("B карандаш · E ластик · I пипетка · G заливка · M выделение · V перемещение · Enter — анимация")
        k.setObjectName("Muted")
        col.addWidget(k)
        col.addStretch(2)
        outer.addLayout(col)
        outer.addStretch(1)

    def fill_recent(self):
        while self.recent.count() > 1:
            item = self.recent.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
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


# ====================================================================== main window
class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.settings = Settings()
        self.theme = LIGHT
        self.docs = []
        self.doc = None
        self.primary = QColor("#141413")
        self.secondary = QColor(0, 0, 0, 0)
        self.symmetry = [False, False]
        self.last_point = None
        self.clipboard_image = None
        self.tools = [T(self) for T in TOOLS]
        self.tool = self.tools[0]
        self.play_timer = QTimer(self, singleShot=True, timeout=self._play_step)
        self._play_dir = 1
        self.setWindowTitle(f"{LOGO} {APP_NAME}")
        self.resize(1360, 860)
        self.setMinimumSize(980, 620)

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
        vsplit = QSplitter(Qt.Vertical)
        vsplit.setHandleWidth(1)
        vsplit.setChildrenCollapsible(False)
        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        self.tabs = QTabBar()
        self.tabs.setObjectName("DocTabs")
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(False)
        self.tabs.setDocumentMode(True)
        self.tabs.setExpanding(False)
        self.tabs.currentChanged.connect(self._tab_changed)
        self.tabs.tabCloseRequested.connect(self.close_doc)
        tabwrap = QWidget()
        tabwrap.setObjectName("DocTabs")
        tw = QHBoxLayout(tabwrap)
        tw.setContentsMargins(6, 0, 6, 0)
        tw.addWidget(self.tabs)
        tw.addStretch(1)
        cl.addWidget(tabwrap)
        self.stack = QStackedWidget()
        self.canvas = Canvas(self)
        self.canvas.hovered.connect(self._hovered)
        self.canvas.zoom_changed.connect(lambda z: self.zoom_label.setText(f"{z * 100:.0f}%"))
        self.welcome = Welcome(self)
        self.stack.addWidget(self.welcome)
        self.stack.addWidget(self.canvas)
        cl.addWidget(self.stack, 1)
        vsplit.addWidget(center)
        self.timeline = Timeline(self)
        vsplit.addWidget(self.timeline)
        vsplit.setSizes([620, 170])
        mid.addWidget(vsplit, 1)
        self.panel = ColorPanel(self)
        mid.addWidget(self.panel)
        outer.addLayout(mid, 1)
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        self.pos_label = QLabel("")
        self.color_label = QLabel("")
        self.msg = QLabel("")
        self.size_label = QLabel("")
        sb.addWidget(self.pos_label)
        sb.addWidget(self.color_label)
        sb.addWidget(self.msg, 1)
        sb.addPermanentWidget(self.size_label)
        self._build_menus()
        self.apply_theme()
        self.select_tool("pencil")
        self.set_color(self.primary)
        self.panel.set_palette(palettes.preset(self.settings.get("palette", "DB32")))
        self._update_all()

    # ================================================================== building
    def _build_toolbox(self):
        box = QWidget()
        box.setObjectName("ToolBox")
        box.setFixedWidth(64)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(3)
        logo = QLabel(LOGO)
        logo.setObjectName("Zeta")
        logo.setAlignment(Qt.AlignCenter)
        logo.setToolTip(APP_NAME)
        lay.addWidget(logo)
        lay.addSpacing(4)
        self.tool_group = QButtonGroup(self)
        self.tool_buttons = {}
        grid = QGridLayout()
        grid.setSpacing(3)
        for i, tool in enumerate(self.tools):
            b = QToolButton()
            b.setCheckable(True)
            b.setIconSize(QSize(24, 24))
            b.setFixedSize(46, 34)
            b.setToolTip(f"{tool.name} ({tool.shortcut})\n{tool.hint}")
            b.clicked.connect(lambda _=False, k=tool.key: self.select_tool(k))
            self.tool_group.addButton(b)
            grid.addWidget(b, i, 0)
            self.tool_buttons[tool.key] = b
        lay.addLayout(grid)
        lay.addStretch(1)
        self.swatches = Swatches(self)
        self.swatches.swap.connect(self.swap_colors)
        self.swatches.select.connect(lambda sec: self.panel.show_color(self.secondary if sec else self.primary, sec))
        lay.addWidget(self.swatches, 0, Qt.AlignCenter)
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
        lay.addSpacing(8)
        s = self.settings
        self.opt = {}

        def add(key, widget, label=None):
            wrap = QWidget()
            wl = QHBoxLayout(wrap)
            wl.setContentsMargins(0, 0, 0, 0)
            wl.setSpacing(4)
            if label:
                l = QLabel(label)
                l.setObjectName("Muted")
                wl.addWidget(l)
            wl.addWidget(widget)
            lay.addWidget(wrap)
            self.opt[key] = wrap
            return widget

        size = add("size", QSpinBox(), "Кисть")
        size.setRange(1, 64)
        size.setValue(int(s.get("brush_size", 1)))
        size.setSuffix(" px")
        size.valueChanged.connect(lambda v: self._set_opt("brush_size", v))
        self.size_box = size
        shape = add("shape", QComboBox())
        shape.addItem("■ квадрат", "square")
        shape.addItem("● круг", "circle")
        shape.setCurrentIndex(max(0, shape.findData(s.get("brush_shape", "square"))))
        shape.currentIndexChanged.connect(lambda _i: self._set_opt("brush_shape", shape.currentData()))
        pp = add("perfect", QCheckBox("Pixel-perfect"))
        pp.setChecked(bool(s.get("pixel_perfect")))
        pp.setToolTip("Убирает «ступеньки» в линиях толщиной 1 px")
        pp.toggled.connect(lambda v: self._set_opt("pixel_perfect", v))
        fill = add("fill", QCheckBox("Заливка"))
        fill.setChecked(bool(s.get("shape_fill")))
        fill.toggled.connect(lambda v: self._set_opt("shape_fill", v))
        cont = add("contiguous", QCheckBox("Смежные"))
        cont.setChecked(bool(s.get("contiguous", True)))
        cont.toggled.connect(lambda v: self._set_opt("contiguous", v))
        tol = add("tolerance", QSpinBox(), "Допуск")
        tol.setRange(0, 255)
        tol.setValue(int(s.get("tolerance", 0)))
        tol.valueChanged.connect(lambda v: self._set_opt("tolerance", v))
        sym = QWidget()
        sl = QHBoxLayout(sym)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(2)
        lab = QLabel("Симметрия")
        lab.setObjectName("Muted")
        sl.addWidget(lab)
        self.sym_buttons = []
        for i, (text, tip) in enumerate((("⇹", "Горизонтальная симметрия"), ("⇳", "Вертикальная симметрия"))):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.setCheckable(True)
            b.toggled.connect(lambda v, i=i: self._set_symmetry(i, v))
            sl.addWidget(b)
            self.sym_buttons.append(b)
        lay.addWidget(sym)
        self.opt["symmetry"] = sym
        lay.addStretch(1)
        self.hint_label = QLabel()
        self.hint_label.setObjectName("Muted")
        lay.addWidget(self.hint_label)
        lay.addSpacing(10)
        self.grid_btn = QToolButton()
        self.grid_btn.setText("#")
        self.grid_btn.setCheckable(True)
        self.grid_btn.setToolTip("Сетка (⌘')")
        self.grid_btn.setChecked(bool(s.get("grid")))
        self.grid_btn.toggled.connect(lambda v: (self._set_opt("grid", v), self.canvas.update()))
        lay.addWidget(self.grid_btn)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("Muted")
        self.zoom_label.setMinimumWidth(48)
        lay.addWidget(self.zoom_label)
        return bar

    def _set_opt(self, key, value):
        self.settings[key] = value
        self.settings.save()
        self.canvas.update()

    def _set_symmetry(self, i, v):
        self.symmetry[i] = v
        self.canvas.update()

    # ------------------------------------------------------------------ menus
    def _build_menus(self):
        mb = self.menuBar()

        def act(menu, title, fn, shortcut=None, checkable=False, needs_doc=True):
            a = QAction(title, self)
            if shortcut:
                if isinstance(shortcut, (list, tuple)):
                    a.setShortcuts([QKeySequence(s) for s in shortcut])
                else:
                    a.setShortcut(QKeySequence(shortcut))
            a.setCheckable(checkable)
            a.triggered.connect(lambda checked=False: fn())
            a.setProperty("needs_doc", needs_doc)
            menu.addAction(a)
            self.addAction(a)
            return a

        self.doc_actions = []

        def dact(*args, **kw):
            a = act(*args, **kw)
            if kw.get("needs_doc", True):
                self.doc_actions.append(a)
            return a

        m = mb.addMenu("Файл")
        act(m, "Новый спрайт…", self.new_sprite, "Ctrl+N", needs_doc=False)
        act(m, "Открыть…", self.open_dialog, "Ctrl+O", needs_doc=False)
        self.recent_menu = m.addMenu("Открыть недавние")
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        m.addSeparator()
        dact(m, "Сохранить", self.save, "Ctrl+S")
        dact(m, "Сохранить как…", self.save_as, "Ctrl+Shift+S")
        dact(m, "Экспорт…", self.export_dialog, "Ctrl+Shift+E")
        dact(m, "Повторить экспорт", self.repeat_export, "Ctrl+E")
        m.addSeparator()
        dact(m, "Закрыть", lambda: self.close_doc(self.tabs.currentIndex()), "Ctrl+W")
        act(m, "Настройки…", self.preferences, "Ctrl+,", needs_doc=False).setMenuRole(QAction.PreferencesRole)
        act(m, "Выйти", self.close, "Ctrl+Q", needs_doc=False).setMenuRole(QAction.QuitRole)

        m = mb.addMenu("Правка")
        dact(m, "Отменить", self.undo, "Ctrl+Z")
        dact(m, "Повторить", self.redo, ["Ctrl+Shift+Z", "Ctrl+Y"])
        m.addSeparator()
        dact(m, "Вырезать", self.cut, "Ctrl+X")
        dact(m, "Копировать", self.copy, "Ctrl+C")
        dact(m, "Копировать с объединением слоёв", lambda: self.copy(merged=True), "Ctrl+Shift+C")
        act(m, "Вставить", self.paste, "Ctrl+V", needs_doc=False)
        dact(m, "Очистить", self.clear_selection_pixels, ["Delete", "Backspace"])
        dact(m, "Залить выделение основным цветом", self.fill_selection, "Alt+Backspace")
        m.addSeparator()
        dact(m, "Отразить по горизонтали", lambda: self.flip(True), "Shift+H")
        dact(m, "Отразить по вертикали", lambda: self.flip(False), "Shift+V")
        dact(m, "Заменить цвет (основной → второй)", self.replace_color)
        dact(m, "Инвертировать цвета", self.invert_colors, "Ctrl+I")
        m.addSeparator()
        act(m, "Поменять цвета местами", self.swap_colors, "X", needs_doc=False)

        m = mb.addMenu("Выделение")
        dact(m, "Выделить всё", self.select_all, "Ctrl+A")
        dact(m, "Снять выделение", self.deselect, "Ctrl+D")
        dact(m, "Инвертировать выделение", self.invert_selection, "Ctrl+Shift+I")
        dact(m, "Выделить содержимое слоя", self.select_content)

        m = mb.addMenu("Вид")
        dact(m, "Приблизить", lambda: self.canvas.step_zoom(1), ["Ctrl+=", "+"])
        dact(m, "Отдалить", lambda: self.canvas.step_zoom(-1), ["Ctrl+-", "-"])
        dact(m, "Масштаб 100%", lambda: self.canvas.set_zoom(1), "Ctrl+1")
        dact(m, "Вписать в окно", self.canvas.fit, "Ctrl+0")
        m.addSeparator()
        self.grid_act = act(m, "Сетка", lambda: self.grid_btn.toggle(), "Ctrl+'", checkable=True, needs_doc=False)
        self.pixel_grid_act = act(m, "Пиксельная сетка", self._toggle_pixel_grid, "Ctrl+Shift+'", checkable=True,
                                  needs_doc=False)
        act(m, "Размер сетки…", self._grid_size, needs_doc=False)
        self.onion_act = act(m, "Кальки (onion skin)", self.toggle_onion, "F3", checkable=True, needs_doc=False)
        act(m, "Шахматный фон", self._toggle_checker, checkable=True, needs_doc=False).setChecked(
            bool(self.settings.get("checker", True)))
        act(m, "Скрыть / показать панели", self.toggle_panels, "Tab", needs_doc=False)
        theme = m.addMenu("Тема")
        self.theme_group = QActionGroup(self)
        self.theme_actions = {}
        for key, label in (("system", "Системная"), ("light", "Светлая"), ("dark", "Тёмная")):
            a = act(theme, label, lambda k=key: self.set_theme(k), checkable=True, needs_doc=False)
            self.theme_group.addAction(a)
            self.theme_actions[key] = a

        m = mb.addMenu("Спрайт")
        dact(m, "Размер холста…", self.canvas_size)
        dact(m, "Размер спрайта…", self.sprite_size, "Ctrl+Alt+I")
        dact(m, "Обрезать по выделению", self.crop)
        dact(m, "Обрезать пустые края", self.autocrop)
        m.addSeparator()
        dact(m, "Повернуть на 90° по часовой", lambda: self.rotate(90))
        dact(m, "Повернуть на 90° против часовой", lambda: self.rotate(-90))
        dact(m, "Повернуть на 180°", lambda: self.rotate(180))
        dact(m, "Отразить весь спрайт по горизонтали", lambda: self.flip_sprite(True))
        dact(m, "Отразить весь спрайт по вертикали", lambda: self.flip_sprite(False))

        m = mb.addMenu("Слой")
        dact(m, "Новый слой", self.new_layer, "Shift+N")
        dact(m, "Дублировать слой", self.duplicate_layer)
        dact(m, "Удалить слой", self.delete_layer)
        dact(m, "Объединить с нижним", self.merge_down, "Ctrl+M")
        dact(m, "Свести изображение", self.flatten)
        m.addSeparator()
        dact(m, "Свойства слоя…", lambda: self.layer_properties(self.doc.layer), "Shift+P")
        dact(m, "Показать / скрыть", lambda: self.toggle_layer(self.doc.layer, "visible"))
        dact(m, "Заблокировать / разблокировать", lambda: self.toggle_layer(self.doc.layer, "locked"))
        dact(m, "Поднять слой", lambda: self.move_layer(1), "Ctrl+]")
        dact(m, "Опустить слой", lambda: self.move_layer(-1), "Ctrl+[")
        dact(m, "Слой выше", lambda: self.step_layer(1), "Alt+Up")
        dact(m, "Слой ниже", lambda: self.step_layer(-1), "Alt+Down")

        m = mb.addMenu("Кадр")
        dact(m, "Новый кадр", lambda: self.new_frame(copy=False), "Alt+N")
        dact(m, "Дублировать кадр", lambda: self.new_frame(copy=True), "Alt+D")
        dact(m, "Удалить кадр", self.delete_frame, "Alt+C")
        dact(m, "Свойства кадра…", self.frame_properties, "Shift+F")
        dact(m, "Новая метка…", self.new_tag, "F2")
        m.addSeparator()
        dact(m, "Проиграть / пауза", self.toggle_play, "Return")
        dact(m, "Первый кадр", lambda: self.goto_frame(0), "Home")
        dact(m, "Предыдущий кадр", lambda: self.step_frame(-1), [",", "Left"])
        dact(m, "Следующий кадр", lambda: self.step_frame(1), [".", "Right"])
        dact(m, "Последний кадр", lambda: self.goto_frame(-1), "End")

        m = mb.addMenu("Инструменты")
        for tool in self.tools:
            key = tool.shortcut
            act(m, tool.name, lambda k=tool.key: self.select_tool(k), "Shift+U" if key == "⇧U" else key, needs_doc=False)
        m.addSeparator()
        act(m, "Кисть больше", lambda: self.size_box.setValue(self.size_box.value() + 1), "]", needs_doc=False)
        act(m, "Кисть меньше", lambda: self.size_box.setValue(self.size_box.value() - 1), "[", needs_doc=False)

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
        self.grid_act.setChecked(bool(self.settings.get("grid")))
        self.pixel_grid_act.setChecked(bool(self.settings.get("pixel_grid", True)))
        self.onion_act.setChecked(bool(self.settings.get("onion")))
        self.timeline.onion.setChecked(bool(self.settings.get("onion")))
        self.canvas.update()
        self.timeline.grid.update()
        self.panel.update()

    def set_theme(self, mode):
        self.settings["theme"] = mode
        self.settings.save()
        self.apply_theme()

    def changeEvent(self, e):
        if e.type() == e.Type.PaletteChange and self.settings.get("theme") == "system":
            if self._is_dark() != (self.theme is DARK):
                QTimer.singleShot(0, self.apply_theme)
        super().changeEvent(e)

    # ================================================================== tools & colours
    def tool_by_key(self, key):
        return next(t for t in self.tools if t.key == key)

    def select_tool(self, key):
        self.tool = self.tool_by_key(key)
        self.tool_buttons[key].setChecked(True)
        self.tool_label.setText(self.tool.name)
        self.hint_label.setText(self.tool.hint)
        draws = getattr(self.tool, "draws", False)
        vis = {"size": draws, "shape": draws, "perfect": key == "pencil", "fill": key in ("rect", "ellipse"),
               "contiguous": key in ("bucket", "wand"), "tolerance": key in ("bucket", "wand"),
               "symmetry": key in ("pencil", "eraser", "line", "rect", "ellipse")}
        for k, w in self.opt.items():
            w.setVisible(vis.get(k, False))
        self.canvas.setCursor(self.tool.cursor)
        self.canvas.update()

    def colors_for(self, button):
        return self.secondary if button == Qt.RightButton else self.primary

    def set_color(self, color, secondary=False, from_picker=False):
        color = QColor(color)
        if secondary:
            self.secondary = color
        else:
            self.primary = color
        if not from_picker:
            self.panel.show_color(color, secondary)
        self.swatches.update()
        self.panel.grid.update()

    def swap_colors(self):
        self.primary, self.secondary = self.secondary, self.primary
        self.panel.show_color(self.primary)
        self.swatches.update()
        self.panel.grid.update()

    def palette_edited(self, colors):
        if self.doc:
            self.doc.sprite.palette = list(colors)
            self.doc.version += 1
            self._update_title()

    def replace_palette(self, colors, name=""):
        self.panel.set_palette(colors)
        if self.doc:
            self.doc.push("Палитра")
            self.doc.sprite.palette = list(colors)
            self._update_title()
        if name in palettes.PRESETS:
            self.settings["palette"] = name
            self.settings.save()

    def palette_from_sprite(self):
        if self.doc:
            cols = unique_colors(self.doc.sprite)
            if cols:
                self.replace_palette(cols, "")
                self.status_message(f"Цветов в спрайте: {len(cols)}")

    # ================================================================== documents
    def add_document(self, doc):
        self.docs.append(doc)
        if not doc.sprite.palette:
            doc.sprite.palette = palettes.preset(self.settings.get("palette", "DB32"))
        i = self.tabs.addTab(doc.title())
        self.tabs.setCurrentIndex(i)
        self._tab_changed(i)
        self.canvas.fit()

    def _tab_changed(self, i):
        self.stop_play()
        self.doc = self.docs[i] if 0 <= i < len(self.docs) else None
        self.canvas.set_document(self.doc)
        if self.doc:
            self.panel.set_palette(self.doc.sprite.palette)
        self._update_all()

    def new_sprite(self):
        d = NewSpriteDialog(self)
        if d.exec() != QDialog.Accepted:
            return
        s = self.settings
        s["new_width"], s["new_height"] = d.w.value(), d.h.value()
        s["new_background"] = d.bg.currentData()
        s["palette"] = d.pal.currentText()
        s.save()
        bg = None if d.bg.currentData() == "transparent" else d.bg.currentData()
        sprite = Sprite(d.w.value(), d.h.value(), bg)
        sprite.palette = palettes.preset(d.pal.currentText())
        if bg:
            sprite.add_layer(name="Слой 1")
        doc = Document(sprite)
        n = sum(1 for x in self.docs if x.path is None) + 1
        doc.title_hint = f"Спрайт-{n}"
        doc.layer = sprite.layers[-1]
        self.add_document(doc)

    def open_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Открыть", self.settings.get("last_dir") or str(Path.home()), OPEN_FILTER)
        for p in paths:
            self.open_path(p)

    def open_path(self, path):
        path = Path(path)
        for i, d in enumerate(self.docs):
            if d.path and d.path.resolve() == path.resolve():
                self.tabs.setCurrentIndex(i)
                return
        try:
            sprite = load_sprite(path)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Не удалось открыть «{path.name}»: {exc}")
            return
        is_native = path.suffix.lower() in (".aseprite", ".ase")
        doc = Document(sprite, path if is_native else None)
        if not is_native:
            doc.title_hint = path.stem
            doc.import_path = path
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
            a = self.recent_menu.addAction("Пусто")
            a.setEnabled(False)

    def save(self):
        if not self.doc:
            return False
        if self.doc.path is None:
            return self.save_as()
        return self._write(self.doc, self.doc.path)

    def save_as(self):
        if not self.doc:
            return False
        start = str(self.doc.path or Path(self.settings.get("last_dir") or Path.home()) / f"{self.doc.title()}.aseprite")
        if not start.endswith((".aseprite", ".ase")):
            start = str(Path(start).with_suffix(".aseprite"))
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить как", start, "Aseprite (*.aseprite *.ase)")
        if not path:
            return False
        if not path.lower().endswith((".aseprite", ".ase")):
            path += ".aseprite"
        return self._write(self.doc, Path(path))

    def _write(self, doc, path):
        try:
            ase.save(doc.sprite, path)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Не удалось сохранить: {exc}")
            return False
        doc.path = Path(path)
        doc.mark_saved()
        self.settings["last_dir"] = str(Path(path).parent)
        self.settings.add_recent(str(path))
        self._update_title()
        self.status_message(f"Сохранено: {Path(path).name}")
        return True

    def close_doc(self, i):
        if not (0 <= i < len(self.docs)):
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
        self.settings.save()
        e.accept()

    # ------------------------------------------------------------------ export
    def export_dialog(self):
        if not self.doc:
            return
        d = ExportDialog(self, self.doc)
        if d.exec() != QDialog.Accepted:
            return
        kind = d.kind.currentData()
        ext = {"png": "png", "gif": "gif", "sheet": "png", "sequence": "png"}[kind]
        base = self.doc.path.stem if self.doc.path else self.doc.title()
        start = str(Path(self.settings.get("last_dir") or Path.home()) / f"{base}.{ext}")
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт", start, f"{ext.upper()} (*.{ext})")
        if not path:
            return
        if not path.lower().endswith("." + ext):
            path += "." + ext
        tag_i = d.range.currentData()
        opts = {"kind": kind, "path": path, "scale": d.scale.value(), "tag": tag_i, "layout": d.layout_.currentData()}
        self.settings["export_scale"] = d.scale.value()
        self.settings.save()
        self.export(opts)

    def repeat_export(self):
        opts = getattr(self.doc, "last_export", None) if self.doc else None
        if opts:
            self.export(opts)
        else:
            self.export_dialog()

    def export(self, opts):
        doc = self.doc
        sp = doc.sprite
        scale = int(opts.get("scale", 1))
        frames = list(range(sp.frames))
        tag_i = opts.get("tag")
        if tag_i is not None and tag_i < len(sp.tags):
            t = sp.tags[tag_i]
            frames = list(range(t.start, t.end + 1))

        def img(f):
            out = sp.flat_frame(f)
            if scale != 1:
                out = out.scaled(sp.width * scale, sp.height * scale, Qt.IgnoreAspectRatio, Qt.FastTransformation)
            return out

        path = Path(opts["path"])
        try:
            kind = opts["kind"]
            if kind == "png":
                img(doc.frame).save(str(path), "PNG")
            elif kind == "gif":
                save_gif(path, [img(f) for f in frames], [sp.durations[f] for f in frames])
            elif kind == "sequence":
                digits = max(2, len(str(len(frames))))
                for n, f in enumerate(frames):
                    img(f).save(str(path.with_name(f"{path.stem}_{n + 1:0{digits}d}.png")), "PNG")
            elif kind == "sheet":
                w, h = sp.width * scale, sp.height * scale
                n = len(frames)
                if opts.get("layout") == "column":
                    cols, rows = 1, n
                elif opts.get("layout") == "grid":
                    cols = max(1, round(n ** 0.5 + 0.49))
                    rows = (n + cols - 1) // cols
                else:
                    cols, rows = n, 1
                sheet = blank(w * cols, h * rows)
                p = QPainter(sheet)
                meta = {"frames": [], "meta": {"app": "Дзета", "version": __version__, "image": path.name,
                                                "size": {"w": w * cols, "h": h * rows}, "scale": str(scale),
                                                "frameTags": [{"name": t.name, "from": t.start, "to": t.end,
                                                               "direction": ["forward", "reverse", "pingpong",
                                                                             "pingpong_reverse"][t.direction]}
                                                              for t in sp.tags]}}
                for k, f in enumerate(frames):
                    x, y = (k % cols) * w, (k // cols) * h
                    p.drawImage(x, y, img(f))
                    meta["frames"].append({"filename": f"{path.stem} {f}.aseprite", "frame": {"x": x, "y": y, "w": w, "h": h},
                                           "duration": sp.durations[f]})
                p.end()
                sheet.save(str(path), "PNG")
                path.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), "utf-8")
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Экспорт не удался: {exc}")
            return
        doc.last_export = opts
        self.settings["last_dir"] = str(path.parent)
        self.status_message(f"Экспортировано: {path.name}")

    # ================================================================== edits (undoable)
    def _need_layer(self):
        if self.doc is None:
            return False
        if self.doc.layer.locked:
            self.status_message("Слой заблокирован")
            return False
        return True

    def undo(self):
        if self.doc and self.doc.undo():
            self.document_changed()
        else:
            self.status_message("Нечего отменять")

    def redo(self):
        if self.doc and self.doc.redo():
            self.document_changed()

    def copy(self, merged=False):
        doc = self.doc
        if doc is None:
            return
        src = doc.sprite.flat_frame(doc.frame) if merged else (doc.current_image() or blank(doc.sprite.width, doc.sprite.height))
        rect = doc.selection_bounds()
        piece = QImage(rect.size(), FMT)
        piece.fill(0)
        p = QPainter(piece)
        p.setClipRegion(doc.clip_region().translated(-rect.x(), -rect.y()))
        p.drawImage(-rect.x(), -rect.y(), src)
        p.end()
        self.clipboard_image = (piece, rect.topLeft())
        QApplication.clipboard().setImage(piece)
        self.status_message("Скопировано")

    def cut(self):
        if not self._need_layer():
            return
        self.copy()
        self.clear_selection_pixels(label="Вырезать")

    def _clipboard_piece(self):
        img = QApplication.clipboard().image()
        if self.clipboard_image is not None:
            own, pos = self.clipboard_image
            if img.isNull() or img.size() == own.size():
                return own, pos
        if not img.isNull():
            return img.convertToFormat(FMT), QPoint(0, 0)
        return None, None

    def paste(self):
        piece, pos = self._clipboard_piece()
        if piece is None:
            self.status_message("В буфере нет изображения")
            return
        if self.doc is None:
            return self.paste_as_new()
        if not self._need_layer():
            return
        doc = self.doc
        if not QRect(0, 0, doc.sprite.width, doc.sprite.height).intersects(QRect(pos, piece.size())):
            pos = QPoint(0, 0)
        doc.push("Вставить")
        img = doc.editable_image()
        p = QPainter(img)
        p.drawImage(pos, piece)
        p.end()
        doc.set_current(img)
        doc.selection = QRegion(QRect(pos, piece.size()))
        self.select_tool("move")
        self.document_changed()
        self.status_message("Вставлено — двигайте инструментом «Перемещение» (V)")

    def paste_as_new(self):
        piece, _pos = self._clipboard_piece()
        if piece is None:
            self.status_message("В буфере нет изображения")
            return
        sprite = Sprite(piece.width(), piece.height())
        sprite.set_cel(sprite.layers[0], 0, piece)
        doc = Document(sprite)
        doc.title_hint = "Из буфера"
        self.add_document(doc)

    def clear_selection_pixels(self, label="Очистить"):
        if not self._need_layer():
            return
        doc = self.doc
        doc.push(label)
        img = doc.editable_image()
        p = QPainter(img)
        p.setClipRegion(doc.clip_region())
        p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.fillRect(img.rect(), Qt.transparent)
        p.end()
        doc.set_current(img)
        self.document_changed()

    def fill_selection(self):
        if not self._need_layer():
            return
        doc = self.doc
        doc.push("Залить")
        img = doc.editable_image()
        p = QPainter(img)
        p.setClipRegion(doc.clip_region())
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.fillRect(img.rect(), self.primary)
        p.end()
        doc.set_current(img)
        self.document_changed()

    def flip(self, horizontal):
        """Flip the selection (or the whole current cel)."""
        if not self._need_layer():
            return
        doc = self.doc
        rect = doc.selection_bounds()
        doc.push("Отразить")
        img = doc.editable_image()
        piece = img.copy(rect).mirrored(horizontal, not horizontal)
        p = QPainter(img)
        p.setClipRegion(doc.clip_region())
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.drawImage(rect.topLeft(), piece)
        p.end()
        doc.set_current(img)
        self.document_changed()

    def replace_color(self):
        if not self._need_layer():
            return
        doc = self.doc
        src, dst = self.primary.rgba(), self.secondary.rgba()
        img = doc.current_image()
        if img is None:
            return
        doc.push("Заменить цвет")
        out = img.copy()
        clip = doc.clip_region()
        n = 0
        for y in range(out.height()):
            for x in range(out.width()):
                if out.pixel(x, y) == src and clip.contains(QPoint(x, y)):
                    out.setPixel(x, y, dst)
                    n += 1
        doc.set_current(out)
        self.document_changed()
        self.status_message(f"Заменено пикселей: {n}")

    def invert_colors(self):
        if not self._need_layer():
            return
        doc = self.doc
        img = doc.current_image()
        if img is None:
            return
        doc.push("Инвертировать")
        out = img.copy()
        inv = img.copy()
        inv.invertPixels(QImage.InvertRgb)
        p = QPainter(out)
        p.setClipRegion(doc.clip_region())
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.drawImage(0, 0, inv)
        p.end()
        doc.set_current(out)
        self.document_changed()

    def nudge(self, d):
        if not self._need_layer():
            return
        doc = self.doc
        tool = self.tool_by_key("move")
        tool.press(doc, QPoint(0, 0), Qt.LeftButton, Qt.NoModifier)
        tool.move(doc, d, Qt.LeftButton, Qt.NoModifier)
        tool.release(doc, d, Qt.LeftButton, Qt.NoModifier)

    # ------------------------------------------------------------------ selection
    def select_all(self):
        if self.doc:
            self.doc.push("Выделить всё")
            self.doc.selection = QRegion(0, 0, self.doc.sprite.width, self.doc.sprite.height)
            self.selection_changed()

    def deselect(self):
        if self.doc and self.doc.has_selection():
            self.doc.push("Снять выделение")
            self.doc.selection = QRegion()
            self.selection_changed()

    def invert_selection(self):
        if self.doc:
            self.doc.push("Инвертировать выделение")
            full = QRegion(0, 0, self.doc.sprite.width, self.doc.sprite.height)
            self.doc.selection = full.subtracted(self.doc.selection) if self.doc.has_selection() else QRegion()
            self.selection_changed()

    def select_content(self):
        if self.doc and self.doc.current_image() is not None:
            r = content_rect(self.doc.current_image())
            self.doc.push("Выделение")
            self.doc.selection = QRegion(r)
            self.selection_changed()

    # ------------------------------------------------------------------ sprite
    def canvas_size(self):
        d = CanvasSizeDialog(self, self.doc.sprite)
        if d.exec() == QDialog.Accepted:
            ox, oy = d.offset(self.doc.sprite)
            self.doc.push("Размер холста")
            self.doc.sprite.resize_canvas(d.w.value(), d.h.value(), ox, oy)
            self.doc.selection = QRegion()
            self.document_changed(fit=True)

    def sprite_size(self):
        sp = self.doc.sprite
        dlg = QDialog(self)
        dlg.setWindowTitle("Размер спрайта")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 18)
        form = QFormLayout()
        pct = QSpinBox()
        pct.setRange(1, 3200)
        pct.setValue(100)
        pct.setSuffix(" %")
        w = QSpinBox()
        w.setRange(1, 8192)
        w.setValue(sp.width)
        h = QSpinBox()
        h.setRange(1, 8192)
        h.setValue(sp.height)
        lock = QCheckBox("Сохранять пропорции")
        lock.setChecked(True)
        pct.valueChanged.connect(lambda v: (w.setValue(max(1, round(sp.width * v / 100))),
                                            h.setValue(max(1, round(sp.height * v / 100)))))

        def width_changed(v):
            if lock.isChecked():
                h.blockSignals(True)
                h.setValue(max(1, round(v * sp.height / sp.width)))
                h.blockSignals(False)
        w.valueChanged.connect(width_changed)
        form.addRow("Масштаб", pct)
        form.addRow("Ширина", w)
        form.addRow("Высота", h)
        lay.addLayout(form)
        lay.addWidget(lock)
        note = QLabel("Ближайший сосед — пиксели остаются чёткими")
        note.setObjectName("Muted")
        lay.addWidget(note)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec() == QDialog.Accepted:
            self.doc.push("Размер спрайта")
            sp.scale(w.value(), h.value())
            self.doc.selection = QRegion()
            self.document_changed(fit=True)

    def crop(self):
        doc = self.doc
        if not doc.has_selection():
            self.status_message("Сначала выделите область")
            return
        r = doc.selection_bounds().intersected(QRect(0, 0, doc.sprite.width, doc.sprite.height))
        doc.push("Обрезать")
        doc.sprite.resize_canvas(r.width(), r.height(), -r.x(), -r.y())
        doc.selection = QRegion()
        self.document_changed(fit=True)

    def autocrop(self):
        doc = self.doc
        sp = doc.sprite
        rect = QRect()
        for f in range(sp.frames):
            rect = rect.united(content_rect(sp.flat_frame(f)))
        if rect.isEmpty() or rect == QRect(0, 0, sp.width, sp.height):
            self.status_message("Нечего обрезать")
            return
        doc.push("Обрезать пустые края")
        sp.resize_canvas(rect.width(), rect.height(), -rect.x(), -rect.y())
        doc.selection = QRegion()
        self.document_changed(fit=True)

    def rotate(self, deg):
        self.doc.push("Поворот")
        self.doc.sprite.rotate(deg)
        self.doc.selection = QRegion()
        self.document_changed(fit=True)

    def flip_sprite(self, horizontal):
        self.doc.push("Отразить спрайт")
        self.doc.sprite.flip(horizontal)
        self.document_changed()

    # ------------------------------------------------------------------ layers
    def select(self, layer=None, frame=None):
        if self.doc is None:
            return
        if layer is not None:
            self.doc.layer = layer
        if frame is not None:
            self.doc.frame = frame
        self.canvas.refresh()
        self._update_all(canvas=False)

    def toggle_layer(self, layer, attr):
        self.doc.push("Слой")
        setattr(layer, attr, not getattr(layer, attr))
        self.document_changed()

    def new_layer(self):
        doc = self.doc
        doc.push("Новый слой")
        doc.layer = doc.sprite.add_layer(doc.sprite.layer_index(doc.layer) + 1)
        self.document_changed()

    def duplicate_layer(self):
        doc = self.doc
        doc.push("Дублировать слой")
        doc.layer = doc.sprite.duplicate_layer(doc.layer)
        self.document_changed()

    def delete_layer(self):
        doc = self.doc
        if len(doc.sprite.layers) <= 1:
            self.status_message("Нельзя удалить единственный слой")
            return
        doc.push("Удалить слой")
        i = doc.sprite.layer_index(doc.layer)
        doc.sprite.remove_layer(doc.layer)
        doc.layer = doc.sprite.layers[max(0, i - 1)]
        self.document_changed()

    def merge_down(self):
        doc = self.doc
        if doc.sprite.layer_index(doc.layer) == 0:
            self.status_message("Ниже нет слоя")
            return
        doc.push("Объединить слои")
        doc.layer = doc.sprite.merge_down(doc.layer)
        self.document_changed()

    def flatten(self):
        doc = self.doc
        sp = doc.sprite
        doc.push("Свести")
        layer = sp.layers[0]
        frames = [sp.flat_frame(f) for f in range(sp.frames)]
        for l in list(sp.layers[1:]):
            sp.remove_layer(l)
        layer.visible, layer.opacity, layer.blend = True, 255, 0
        for f, img in enumerate(frames):
            sp.set_cel(layer, f, img)
        doc.layer = layer
        self.document_changed()

    def move_layer(self, d):
        self.doc.push("Порядок слоёв")
        self.doc.sprite.move_layer(self.doc.layer, d)
        self.document_changed()

    def step_layer(self, d):
        layers = self.doc.sprite.layers
        i = max(0, min(len(layers) - 1, layers.index(self.doc.layer) + d))
        self.select(layer=layers[i])

    def layer_properties(self, layer):
        d = LayerDialog(self, layer)
        if d.exec() == QDialog.Accepted:
            self.doc.push("Свойства слоя")
            layer.name = d.name.text().strip() or layer.name
            layer.blend = d.blend.currentData()
            layer.opacity = d.opacity.value()
            self.document_changed()

    # ------------------------------------------------------------------ frames
    def new_frame(self, copy=True):
        doc = self.doc
        doc.push("Новый кадр")
        doc.sprite.insert_frame(doc.frame + 1, doc.frame if copy else None, doc.sprite.durations[doc.frame])
        doc.frame += 1
        self.document_changed()

    def delete_frame(self):
        doc = self.doc
        if doc.sprite.frames <= 1:
            self.status_message("Нельзя удалить единственный кадр")
            return
        doc.push("Удалить кадр")
        doc.sprite.remove_frame(doc.frame)
        doc.frame = min(doc.frame, doc.sprite.frames - 1)
        self.document_changed()

    def move_frame(self, src, dst):
        self.doc.push("Переместить кадр")
        self.doc.sprite.move_frame(src, dst)
        self.doc.frame = dst
        self.document_changed()

    def clear_cel(self):
        if self._need_layer() and self.doc.current_image() is not None:
            self.doc.push("Очистить ячейку")
            self.doc.set_current(None)
            self.document_changed()

    def set_duration(self, ms, all_frames=False):
        doc = self.doc
        if doc is None:
            return
        frames = range(doc.sprite.frames) if all_frames else [doc.frame]
        if all(doc.sprite.durations[f] == ms for f in frames):
            return
        doc.push("Длительность")
        for f in frames:
            doc.sprite.durations[f] = int(ms)
        self.document_changed()

    def frame_properties(self):
        doc = self.doc
        ms, ok = QInputDialog.getInt(self, "Свойства кадра", f"Длительность кадра {doc.frame + 1}, мс:",
                                     doc.sprite.durations[doc.frame], 1, 65535)
        if ok:
            all_frames = QMessageBox.question(self, APP_NAME, "Применить ко всем кадрам?") == QMessageBox.Yes \
                if doc.sprite.frames > 1 else False
            self.set_duration(ms, all_frames)

    def new_tag(self):
        doc = self.doc
        tag = Tag(f"Метка {len(doc.sprite.tags) + 1}", doc.frame, doc.frame)
        self.tag_properties(tag, new=True)

    def tag_properties(self, tag, new=False):
        doc = self.doc
        d = TagDialog(self, tag, doc.sprite.frames)
        if d.exec() != QDialog.Accepted:
            return
        doc.push("Метка")
        if not new:
            # snapshot copied the tags: find this tag in the live list again
            tag = next((t for t in doc.sprite.tags if t.name == tag.name and t.start == tag.start), tag)
        if d.delete.isChecked():
            doc.sprite.tags = [t for t in doc.sprite.tags if t is not tag]
        else:
            tag.name = d.name.text().strip() or tag.name
            tag.start, tag.end = sorted((d.start.value() - 1, d.end.value() - 1))
            tag.direction = d.direction.currentIndex()
            tag.color = d.color.currentData()
            if new:
                doc.sprite.tags.append(tag)
        self.document_changed()

    def goto_frame(self, f):
        if self.doc:
            self.doc.frame = f % self.doc.sprite.frames
            self.select()

    def step_frame(self, d):
        if self.doc:
            self.goto_frame(self.doc.frame + d)

    # ------------------------------------------------------------------ playback
    def toggle_play(self):
        if self.play_timer.isActive():
            self.stop_play()
            return
        if self.doc is None or self.doc.sprite.frames < 2:
            self.timeline.play.setChecked(False)
            return
        self._play_dir = 1
        self.timeline.play.setChecked(True)
        self.play_timer.start(self.doc.sprite.durations[self.doc.frame])

    def stop_play(self):
        self.play_timer.stop()
        self.timeline.play.setChecked(False)

    def _play_step(self):
        doc = self.doc
        if doc is None:
            return
        sp = doc.sprite
        tag = next((t for t in sp.tags if t.start <= doc.frame <= t.end), None)
        lo, hi = (tag.start, tag.end) if tag else (0, sp.frames - 1)
        direction = tag.direction if tag else 0
        if direction == 1:
            self._play_dir = -1
        elif direction == 0:
            self._play_dir = 1
        nxt = doc.frame + self._play_dir
        if direction in (2, 3) and not lo <= nxt <= hi:
            self._play_dir = -self._play_dir
            nxt = doc.frame + self._play_dir
        if nxt > hi:
            nxt = lo
        elif nxt < lo:
            nxt = hi
        doc.frame = max(lo, min(hi, nxt))
        self.select()
        self.play_timer.start(sp.durations[doc.frame])

    def toggle_onion(self):
        self.settings["onion"] = not self.settings.get("onion")
        self.settings.save()
        self.onion_act.setChecked(bool(self.settings["onion"]))
        self.timeline.onion.setChecked(bool(self.settings["onion"]))
        self.canvas.refresh()

    # ================================================================== view
    def _toggle_pixel_grid(self):
        self.settings["pixel_grid"] = not self.settings.get("pixel_grid", True)
        self.settings.save()
        self.canvas.update()

    def _toggle_checker(self):
        self.settings["checker"] = not self.settings.get("checker", True)
        self.settings.save()
        self.canvas.update()

    def _grid_size(self):
        v, ok = QInputDialog.getInt(self, "Сетка", "Размер ячейки сетки, px:", int(self.settings.get("grid_size", 16)), 2, 512)
        if ok:
            self.settings["grid_size"] = v
            self.settings["grid"] = True
            self.grid_btn.setChecked(True)
            self.settings.save()
            self.canvas.update()

    def toggle_panels(self):
        vis = not self.panel.isVisible()
        self.panel.setVisible(vis)
        self.timeline.setVisible(vis)

    def preferences(self):
        d = QDialog(self)
        d.setWindowTitle("Настройки")
        lay = QVBoxLayout(d)
        lay.setContentsMargins(24, 20, 24, 18)
        t = QLabel("Настройки")
        t.setObjectName("Title")
        lay.addWidget(t)
        form = QFormLayout()
        theme = QComboBox()
        for key, label in (("system", "Системная"), ("light", "Светлая"), ("dark", "Тёмная")):
            theme.addItem(label, key)
        theme.setCurrentIndex(theme.findData(self.settings.get("theme", "system")))
        form.addRow("Тема", theme)
        prev = QSpinBox()
        prev.setRange(0, 5)
        prev.setValue(int(self.settings.get("onion_prev", 1)))
        nxt = QSpinBox()
        nxt.setRange(0, 5)
        nxt.setValue(int(self.settings.get("onion_next", 1)))
        form.addRow("Кальки: кадров назад", prev)
        form.addRow("Кальки: кадров вперёд", nxt)
        pal = QComboBox()
        pal.addItems(list(palettes.PRESETS))
        pal.setCurrentText(self.settings.get("palette", "DB32"))
        form.addRow("Палитра по умолчанию", pal)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        lay.addWidget(bb)
        if d.exec() == QDialog.Accepted:
            self.settings.update(theme=theme.currentData(), onion_prev=prev.value(), onion_next=nxt.value(),
                                 palette=pal.currentText())
            self.settings.save()
            self.apply_theme()
            self.canvas.refresh()

    def about(self):
        QMessageBox.about(self, APP_NAME, f"<h2 style='font-family:Georgia'>{LOGO} {APP_NAME}</h2>"
                          f"<p>Редактор пиксель-арта и анимации, версия {__version__}.</p>"
                          "<p>Файлы .aseprite совместимы с Aseprite.</p>")

    # ================================================================== refresh
    def canvas_changed(self):
        """Pixels changed during a stroke (cheap refresh)."""
        self.canvas.refresh()
        self.panel.preview.set_image(self.canvas.cache)

    def document_changed(self, fit=False):
        self.canvas.refresh()
        if fit:
            self.canvas.fit()
        if self.doc and self.doc.sprite.palette != self.panel.grid.colors:
            self.panel.set_palette(self.doc.sprite.palette)
        self._update_all(canvas=False)

    def selection_changed(self):
        self.canvas.update()
        self._update_title()

    def _update_title(self):
        doc = self.doc
        i = self.tabs.currentIndex()
        if doc is not None and i >= 0:
            self.tabs.setTabText(i, ("● " if doc.modified else "") + doc.title())
            self.setWindowTitle(f"{doc.title()}{' •' if doc.modified else ''} — {LOGO} {APP_NAME}")
        else:
            self.setWindowTitle(f"{LOGO} {APP_NAME}")

    def _update_all(self, canvas=True):
        has = self.doc is not None
        self.stack.setCurrentWidget(self.canvas if has else self.welcome)
        for a in self.doc_actions:
            a.setEnabled(has)
        if canvas:
            self.canvas.refresh()
        self.timeline.refresh()
        self.panel.preview.set_image(self.canvas.cache if has else None)
        if has:
            sp = self.doc.sprite
            sel = self.doc.selection_bounds() if self.doc.has_selection() else None
            self.size_label.setText(f"{sp.width}×{sp.height} px · {len(sp.layers)} сл. · {sp.frames} к." +
                                    (f" · выделено {sel.width()}×{sel.height()}" if sel else ""))
        else:
            self.size_label.setText("")
        self._update_title()

    def _hovered(self, pt):
        if pt is None or self.doc is None:
            self.pos_label.setText("")
            self.color_label.setText("")
            return
        self.pos_label.setText(f"x {pt.x()}  y {pt.y()}")
        c = QColor.fromRgba(self.canvas.cache.pixel(pt)) if self.canvas.cache is not None else QColor()
        self.color_label.setText(f"{c.name().upper()} · α {c.alpha()}" if c.alpha() else "прозрачный")

    def status_message(self, text, ms=4000):
        self.msg.setText(text)
        QTimer.singleShot(ms, lambda t=text: self.msg.text() == t and self.msg.setText(""))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Zeta")
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
