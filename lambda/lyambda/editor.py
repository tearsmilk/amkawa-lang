"""One open file: canvas + panels for its kind (Дизайн / Доска / Презентация / Сайт), undo history and every
editing command (groups, frames, auto layout, components, booleans, alignment, clipboard, import / export…)."""
import base64
import copy
import json
from pathlib import Path

from PySide6.QtCore import QMimeData, QPointF, QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QImage, QPainterPath, QPainterPathStroker, QTransform
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QMenu, QMessageBox,
                               QPlainTextEdit, QTabBar, QToolButton, QVBoxLayout, QWidget)

from . import fileio, icons
from . import templates as tpl
from . import text as textlib
from .canvas import Canvas
from .inspector import Inspector
from .model import (FRAMELIKE, KIND_TITLES, TYPE_TITLES, Node, make_instance, new_id, normalize_group, normalize_path,
                    owning_instance, parent_transform, path_to_points, shape_path, solid, union_rect, world_bounds,
                    world_shape, world_transform)
from .panels import AssetsPanel, BlocksPanel, LayersPanel, PagesPanel, SlidesPanel
from .render import Renderer, render_image

MIME = "application/x-lambda-nodes"
OVERRIDE_KEYS = ("text", "fills", "strokes", "visible", "font", "size", "weight", "italic", "text_color", "opacity",
                 "effects", "talign", "name")

TOOLS = {
    "design": [("select", "select", "Перемещение", "V"), ("hand", "hand", "Рука", "H"),
               ("frame", "frame", "Фрейм", "F"), ("section", "section", "Секция", "⇧S"),
               ("rect", "rect", "Прямоугольник", "R"), ("ellipse", "ellipse", "Эллипс", "O"),
               ("line", "line", "Линия", "L"), ("arrow", "arrow", "Стрелка", "⇧L"),
               ("polygon", "polygon", "Многоугольник", ""), ("star", "star", "Звезда", ""),
               ("pen", "pen", "Перо", "P"), ("pencil", "pencil", "Карандаш", "⇧P"), ("text", "text", "Текст", "T"),
               ("image", "image", "Изображение", "⇧⌘K")],
    "board": [("select", "select", "Выделение", "V"), ("hand", "hand", "Рука", "H"),
              ("marker", "marker", "Маркер", "M"), ("highlighter", "highlighter", "Выделитель", "⇧M"),
              ("sticky", "sticky", "Стикер", "S"), ("shape", "shape", "Фигура", "R"),
              ("connector", "connector", "Соединитель", "X"), ("text", "text", "Текст", "T"),
              ("section", "section", "Секция", "⇧S"), ("stamp", "stamp", "Штамп", "E"),
              ("image", "image", "Изображение", "⇧⌘K")],
    "slides": [("select", "select", "Перемещение", "V"), ("hand", "hand", "Рука", "H"),
               ("rect", "rect", "Прямоугольник", "R"), ("ellipse", "ellipse", "Эллипс", "O"),
               ("line", "line", "Линия", "L"), ("arrow", "arrow", "Стрелка", "⇧L"), ("star", "star", "Звезда", ""),
               ("pen", "pen", "Перо", "P"), ("text", "text", "Текст", "T"), ("image", "image", "Изображение", "⇧⌘K")],
    "site": [("select", "select", "Перемещение", "V"), ("hand", "hand", "Рука", "H"),
             ("frame", "frame", "Стек (автолейаут)", "F"), ("rect", "rect", "Прямоугольник", "R"),
             ("ellipse", "ellipse", "Эллипс", "O"), ("text", "text", "Текст", "T"),
             ("image", "image", "Изображение", "⇧⌘K")],
}
KEYS = {
    "design": {("v", False): "select", ("h", False): "hand", ("f", False): "frame", ("s", True): "section",
               ("r", False): "rect", ("o", False): "ellipse", ("l", False): "line", ("l", True): "arrow",
               ("p", False): "pen", ("p", True): "pencil", ("t", False): "text"},
    "board": {("v", False): "select", ("h", False): "hand", ("m", False): "marker", ("m", True): "highlighter",
              ("s", False): "sticky", ("r", False): "shape", ("o", False): "shape", ("x", False): "connector",
              ("t", False): "text", ("s", True): "section", ("e", False): "stamp"},
    "slides": {("v", False): "select", ("h", False): "hand", ("r", False): "rect", ("o", False): "ellipse",
               ("l", False): "line", ("l", True): "arrow", ("p", False): "pen", ("t", False): "text"},
    "site": {("v", False): "select", ("h", False): "hand", ("f", False): "frame", ("r", False): "rect",
             ("o", False): "ellipse", ("t", False): "text"},
}


class Editor(QWidget):
    titleChanged = Signal()
    CREATE_TOOLS = ("frame", "section", "rect", "ellipse", "line", "arrow", "polygon", "star", "shape")

    def __init__(self, doc, path, window):
        super().__init__()
        self.win = window
        self.settings = window.settings
        self.theme = window.theme
        self.doc = doc
        self.path = Path(path) if path else None
        self.renderer = Renderer(doc)
        self.page = doc.pages[0]
        self.slide_id = None
        self.selection = []
        self.tool = "select"
        self.tool_opts = {"sticky": "#FFE29A", "shape": "rect", "stamp": "👍", "line_color": "#141413",
                          "route": "elbow", "marker": "#141413", "text_color": "#141413"}
        self.history = [doc.snapshot()]
        self.hist_i = 0
        self.saved_i = 0
        self.windows = []
        self.tool_buttons = {}
        doc.relayout()
        self._thumbs = QTimer(self, singleShot=True, interval=350, timeout=self._refresh_thumbs)
        self._build()
        self.autosave = QTimer(self, interval=60000, timeout=self._autosave)
        self.autosave.start()
        QTimer.singleShot(0, self._first_view)

    # ================================================================== layout
    def _build(self):
        kind = self.doc.kind
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._top_bar())
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body, 1)
        self.canvas = Canvas(self)
        self.canvas.zoomChanged.connect(self._zoom_label)
        self.canvas.resized.connect(self._place_float)
        self.inspector = Inspector(self)
        self.left = QWidget()
        self.left.setObjectName("LeftPanel")
        self.left.setFixedWidth(self.settings.get("left_width", 240))
        ll = QVBoxLayout(self.left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)
        self.pages = self.layers = self.assets = self.slides_panel = self.blocks = None
        if kind == "slides":
            self.slides_panel = SlidesPanel(self)
            ll.addWidget(self.slides_panel)
        else:
            tabs = QTabBar()
            tabs.setObjectName("DocTabs")
            tabs.setDrawBase(False)
            tabs.setExpanding(False)
            tabs.addTab("Слои")
            self.left_stack = []
            layers_box = QWidget()
            lb = QVBoxLayout(layers_box)
            lb.setContentsMargins(0, 0, 0, 0)
            lb.setSpacing(0)
            self.pages = PagesPanel(self, "Страницы сайта" if kind == "site" else "Страницы")
            self.layers = LayersPanel(self)
            lb.addWidget(self.pages)
            lb.addWidget(self.layers, 1)
            ll.addWidget(tabs)
            ll.addWidget(layers_box, 1)
            self.left_stack.append(layers_box)
            extra = None
            if kind == "design":
                tabs.addTab("Ресурсы")
                self.assets = AssetsPanel(self)
                extra = self.assets
            elif kind == "site":
                tabs.addTab("Блоки")
                self.blocks = BlocksPanel(self)
                extra = self.blocks
            if extra is not None:
                ll.addWidget(extra, 1)
                extra.hide()
                self.left_stack.append(extra)
                tabs.currentChanged.connect(self._left_tab)
            else:
                tabs.hide()
        body.addWidget(self.left)
        center = QVBoxLayout()
        center.setSpacing(0)
        center.setContentsMargins(0, 0, 0, 0)
        center.addWidget(self.canvas, 1)
        self.notes = None
        if kind == "slides":
            self.notes = QPlainTextEdit()
            self.notes.setObjectName("Notes")
            self.notes.setPlaceholderText("Заметки докладчика — видны в режиме докладчика")
            self.notes.setFixedHeight(96)
            self.notes.textChanged.connect(self._notes_changed)
            self._notes_timer = QTimer(self, singleShot=True, interval=700, timeout=lambda: self.commit("Заметки"))
            center.addWidget(self.notes)
        body.addLayout(center, 1)
        self.right = QWidget()
        self.right.setObjectName("RightPanel")
        self.right.setFixedWidth(self.settings.get("right_width", 264))
        rl = QVBoxLayout(self.right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(self.inspector)
        body.addWidget(self.right)
        self.float_bar = None
        if kind == "board":
            self.left.hide()
            self._build_float_bar()
        self.refresh_all()

    def _left_tab(self, i):
        for k, w in enumerate(self.left_stack):
            w.setVisible(k == i)
        if i == 1 and self.assets is not None:
            self.assets.refresh()
        if i == 1 and self.blocks is not None:
            self.blocks.refresh()

    def _top_bar(self):
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(46)
        h = QHBoxLayout(bar)
        h.setContentsMargins(8, 4, 10, 4)
        h.setSpacing(2)

        kind = self.doc.kind
        if kind != "board":
            for key, ic, name, sc in TOOLS[kind]:
                b = QToolButton()
                b.setCheckable(key != "image")
                b.setToolTip(f"{name}  {sc}" if sc else name)
                b.setIconSize(QSize(18, 18))
                b.clicked.connect(lambda _=False, k=key: self.set_tool(k))
                h.addWidget(b)
                self.tool_buttons[key] = (b, ic)
        h.addStretch(1)
        self.name_label = QLabel()
        self.name_label.setObjectName("FileName")
        h.addWidget(self.name_label)
        self.kind_label = QLabel(f"  ·  {KIND_TITLES[kind]}")
        self.kind_label.setObjectName("Muted")
        h.addWidget(self.kind_label)
        h.addStretch(1)
        if kind == "site":
            self.bp_buttons = {}
            for bp, name in ((1440, "Компьютер"), (768, "Планшет"), (375, "Телефон")):
                b = QToolButton()
                b.setText(name)
                b.setCheckable(True)
                b.setChecked(self.doc.site.get("breakpoint", 1440) == bp)
                b.clicked.connect(lambda _=False, v=bp: self.set_breakpoint(v))
                h.addWidget(b)
                self.bp_buttons[bp] = b
            h.addSpacing(8)
        self.zoom_btn = QToolButton()
        self.zoom_btn.setText("100%")
        self.zoom_btn.setPopupMode(QToolButton.InstantPopup)
        zm = QMenu(self.zoom_btn)
        zm.addAction("Увеличить\t⌘+", lambda: self.canvas.set_zoom(self.canvas.zoom * 1.25))
        zm.addAction("Уменьшить\t⌘−", lambda: self.canvas.set_zoom(self.canvas.zoom / 1.25))
        zm.addAction("Показать всё\t⇧1", lambda: self.canvas.fit())
        zm.addAction("К выделению\t⇧2", self.zoom_selection)
        zm.addAction("100%\t⇧0", lambda: self.canvas.set_zoom(1.0))
        self.zoom_btn.setMenu(zm)
        h.addWidget(self.zoom_btn)
        if kind in ("design", "slides"):
            self.play_btn = QToolButton()
            self.play_btn.setToolTip("Презентовать  ⌥⌘↩")
            self.play_btn.setIconSize(QSize(18, 18))
            self.play_btn.clicked.connect(self.present)
            h.addWidget(self.play_btn)
        if kind == "site":
            self.play_btn = QToolButton()
            self.play_btn.setToolTip("Предпросмотр в браузере")
            self.play_btn.setIconSize(QSize(18, 18))
            self.play_btn.clicked.connect(self.preview_site)
            h.addWidget(self.play_btn)
        self.update_title()
        return bar

    def _build_float_bar(self):

        fb = QFrame(self.canvas)
        fb.setObjectName("FloatBar")
        v = QVBoxLayout(fb)
        v.setContentsMargins(8, 6, 8, 6)
        v.setSpacing(4)
        self.options_strip = QWidget()
        self.options_lay = QHBoxLayout(self.options_strip)
        self.options_lay.setContentsMargins(0, 0, 0, 0)
        self.options_lay.setSpacing(4)
        v.addWidget(self.options_strip)
        row = QHBoxLayout()
        row.setSpacing(2)
        for key, ic, name, sc in TOOLS["board"]:
            b = QToolButton()
            b.setCheckable(key != "image")
            b.setToolTip(f"{name}  {sc}" if sc else name)
            b.setIconSize(QSize(26, 26))
            b.clicked.connect(lambda _=False, k=key: self.set_tool(k))
            row.addWidget(b)
            self.tool_buttons[key] = (b, ic)
        v.addLayout(row)
        self.float_bar = fb
        self._fill_options()
        fb.show()

    def _fill_options(self):
        if self.float_bar is None:
            return
        while self.options_lay.count():
            it = self.options_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        tool = self.tool

        def swatches(colors, key, size=20):
            for c in colors:
                hexv = c[1] if isinstance(c, tuple) else c
                b = QToolButton()
                b.setFixedSize(size, size)
                sel = self.tool_opts.get(key, "").upper() == hexv.upper()
                b.setStyleSheet(f"QToolButton {{ background: {hexv}; border-radius: {size // 2}px; "
                                f"border: 2px solid {self.theme['accent'] if sel else 'rgba(0,0,0,0.15)'}; }}")
                b.clicked.connect(lambda _=False, h=hexv: (self.tool_opts.__setitem__(key, h), self._fill_options()))
                self.options_lay.addWidget(b)
        if tool == "sticky":
            swatches(tpl.STICKY_COLORS, "sticky")
        elif tool == "shape":
            from .model import SHAPE_KINDS
            for k, name in SHAPE_KINDS:
                b = QToolButton()
                b.setText({"rect": "▭", "rounded": "▢", "ellipse": "◯", "diamond": "◇", "triangle": "△",
                           "parallelogram": "▱", "hexagon": "⬡", "star": "☆", "arrow": "➔", "plus": "✚",
                           "cylinder": "⛁"}.get(k, "□"))
                b.setToolTip(name)
                b.setCheckable(True)
                b.setChecked(self.tool_opts["shape"] == k)
                b.clicked.connect(lambda _=False, kk=k: (self.tool_opts.__setitem__("shape", kk), self._fill_options()))
                self.options_lay.addWidget(b)
        elif tool in ("marker", "connector"):
            swatches(tpl.BOARD_COLORS, "marker" if tool == "marker" else "line_color")
            if tool == "connector":
                for k, name in (("elbow", "Ломаный"), ("straight", "Прямой"), ("curved", "Кривой")):
                    b = QToolButton()
                    b.setText(name)
                    b.setCheckable(True)
                    b.setChecked(self.tool_opts["route"] == k)
                    b.clicked.connect(lambda _=False, kk=k: (self.tool_opts.__setitem__("route", kk),
                                                              self._fill_options()))
                    self.options_lay.addWidget(b)
        elif tool == "stamp":
            for g in tpl.STAMPS:
                b = QToolButton()
                b.setText(g)
                b.setCheckable(True)
                b.setChecked(self.tool_opts["stamp"] == g)
                b.clicked.connect(lambda _=False, gg=g: (self.tool_opts.__setitem__("stamp", gg), self._fill_options()))
                self.options_lay.addWidget(b)
        self.options_strip.setVisible(self.options_lay.count() > 0)
        QTimer.singleShot(0, self._place_float)

    def _place_float(self):
        if self.float_bar is None:
            return
        fb = self.float_bar
        fb.adjustSize()
        fb.move(int((self.canvas.width() - fb.width()) / 2), int(self.canvas.height() - fb.height() - 18))
        fb.raise_()

    def _first_view(self):
        kind = self.doc.kind
        if kind == "slides":
            slides = self.slides()
            if slides:
                self.set_slide(slides[0])
        elif kind == "site":
            root = self.doc.site_root(self.page)
            if root is not None:
                self.canvas.fit_width(root)
        else:
            if self.page.children:
                self.canvas.fit(max_zoom=1.0)
            else:
                self.canvas.set_zoom(1.0)
                self.canvas.off = QPointF(self.canvas.width() / 2 - 200, self.canvas.height() / 2 - 200)
        self._place_float()

    # ================================================================== theme / title
    def apply_theme(self, theme=None, slides=None):
        """Slides: apply a colour theme to all slides (or the given ones)."""
        if theme is None:
            return
        if slides is None:
            tpl.apply_theme(self.doc, theme)
        else:
            for s in slides:
                for n in s.walk():
                    tpl.apply_role(n, theme)
        self.commit("Тема")

    def set_ui_theme(self, theme):
        self.theme = theme
        for key, (b, ic) in self.tool_buttons.items():
            b.setIcon(icons.icon(ic, theme["text"], theme["accent"]))
        if hasattr(self, "play_btn"):
            self.play_btn.setIcon(icons.icon("present" if self.doc.kind != "site" else "globe", theme["text"],
                                             theme["accent"]))
        self._update_tool_buttons()
        self.refresh_all()
        self._fill_options()

    def title(self):
        return self.path.stem if self.path else "Без названия"

    def is_dirty(self):
        return self.hist_i != self.saved_i

    def update_title(self):
        if hasattr(self, "name_label"):
            self.name_label.setText(self.title() + (" •" if self.is_dirty() else ""))
        self.titleChanged.emit()

    def status(self, msg):
        if msg:
            self.win.statusBar().showMessage(msg, 6000)
        else:
            self.win.statusBar().clearMessage()

    def show_cursor_pos(self, w):
        pass

    def _zoom_label(self, z):
        self.zoom_btn.setText(f"{round(z * 100)}%")

    # ================================================================== scopes
    def slides(self):
        return [c for c in self.page.children if c.type in ("frame", "component")]

    def current_slide(self):
        if self.doc.kind != "slides":
            return None
        s = self.doc.find(self.slide_id) if self.slide_id else None
        if s is None or s.parent is not self.page:
            sl = self.slides()
            s = sl[0] if sl else None
            self.slide_id = s.id if s else None
        return s

    def scope_root(self):
        kind = self.doc.kind
        if kind == "slides":
            return self.current_slide() or self.page
        if kind == "site":
            return self.doc.site_root(self.page) or self.page
        return self.page

    def scope_children(self):
        return self.scope_root().children

    def layers_root(self):
        return self.scope_root()

    def visible_roots(self):
        kind = self.doc.kind
        if kind == "slides":
            s = self.current_slide()
            return [s] if s is not None else []
        if kind == "site":
            r = self.doc.site_root(self.page)
            return [r] if r is not None else []
        return self.page.children

    def top_selection(self):
        sel = self.selection
        ids = {n.id for n in sel}
        return [n for n in sel if not any(a.id in ids for a in n.ancestors())]

    # ================================================================== selection
    def select(self, nodes, source=None, quiet=False):
        seen = []
        for n in nodes:
            if n is not None and n not in seen and n.type != "page":
                seen.append(n)
        if [n.id for n in seen] == [n.id for n in self.selection] and all(a is b for a, b in zip(seen, self.selection)):
            return
        self.selection = seen
        self.canvas.update()
        if self.layers is not None and source is not self.layers:
            self.layers.show_selection()
        self.inspector.schedule()
        if len(seen) == 1:
            n = seen[0]
            self.status(f"{TYPE_TITLES.get(n.type, n.type)} «{n.name}»  ·  {round(n.w)} × {round(n.h)}")

    def toggle_select(self, n):
        if n in self.selection:
            self.select([x for x in self.selection if x is not n])
        else:
            self.select(self.selection + [n])

    def select_all(self):
        if self.selection and self.selection[0].parent is not None and self.selection[0].parent is not self.scope_root():
            par = self.selection[0].parent
            self.select([c for c in par.children if c.visible and not c.locked])
        else:
            self.select([c for c in self.scope_children() if c.visible and not c.locked])

    def _resolve_selection(self):
        out = []
        for n in self.selection:
            m = self.doc.find(n.id)
            if m is not None and m.page() is self.page:
                out.append(m)
        self.selection = out

    # ================================================================== tools
    def set_tool(self, name):
        if name == "image":
            self.place_image_dialog()
            return
        if self.canvas.pen is not None and name != "pen":
            self.canvas.finish_pen(False)
        if self.canvas.vec is not None:
            self.canvas.exit_vector_edit()
        self.tool = name
        self._update_tool_buttons()
        self._fill_options()
        self.canvas.hover = None
        self.canvas.update()
        if self.doc.kind == "design":
            self.inspector.schedule()

    def _update_tool_buttons(self):
        for key, (b, ic) in self.tool_buttons.items():
            b.setChecked(key == self.tool)

    def shortcut(self, ch, shift):
        kind = self.doc.kind
        tool = KEYS[kind].get((ch, shift))
        if tool is not None:
            if kind == "board" and ch == "o":
                self.tool_opts["shape"] = "ellipse"
            elif kind == "board" and ch == "r":
                self.tool_opts["shape"] = "rect"
            self.set_tool(tool)
            return True
        if ch == "a" and shift:
            self.add_autolayout()
            return True
        return False

    def make_tool_node(self, tool):
        kind = self.doc.kind
        if tool == "frame":
            if kind == "site":
                return Node("frame", name="Стек", layout="column", gap=16, pad=[24, 24, 24, 24], hug_w=False,
                            hug_h=True, fills=[], clip=False)
            return Node("frame", name=self._next_name("Фрейм"))
        if tool == "section":
            return Node("section", name=self._next_name("Секция"))
        if tool in ("line", "arrow"):
            return Node("path", name="Стрелка" if tool == "arrow" else "Линия", strokes=[solid("#141413")],
                        stroke_width=2.0 if kind == "board" else 1.5, arrow_end="arrow" if tool == "arrow" else "none")
        if tool == "shape":
            n = Node("shape", shape=self.tool_opts["shape"])
            return n
        n = Node(tool)
        if kind == "slides" and tool in ("rect", "ellipse", "star", "polygon"):
            n.fills = [solid(self.doc.theme.get("accent", "#D97757"))]
        return n

    def _next_name(self, base):
        names = {n.name for n in self.page.walk()}
        k = 1
        while f"{base} {k}" in names:
            k += 1
        return f"{base} {k}"

    def default_size(self, tool):
        kind = self.doc.kind
        return {"frame": (360, 240) if kind == "site" else (100, 100), "section": (640, 420),
                "shape": (200, 120), "line": (120, 0), "arrow": (120, 0)}.get(tool, (100, 100))

    def default_text_size(self):
        return {"board": 24.0, "slides": 48.0}.get(self.doc.kind, 16.0)

    def freehand_style(self, tool):
        if tool == "marker":
            return {"color": self.tool_opts.get("marker", "#141413"), "width": 6.0, "name": "Маркер"}
        if tool == "highlighter":
            return {"color": "#F2D15B", "width": 24.0, "opacity": 0.45, "name": "Выделитель"}
        return {"color": "#141413", "width": 2.0, "name": "Карандаш"}

    # ================================================================== mutations
    def add_node(self, n, parent, index=None):
        parent.add(n, index)
        self.doc.invalidate()

    def remove_node(self, n):
        n.remove()
        self.doc.invalidate()

    def set_attr(self, nodes, key, value, commit=True):
        for n in nodes:
            setattr(n, key, copy.deepcopy(value))
            self.note_override(n, key)
        if key in ("effects", "radius", "shape"):
            self.renderer.drop_caches()
        if commit:
            self.commit(TYPE_TITLES.get(key, "Свойства"))
        else:
            self.live_changed()

    def note_override(self, n, key=None):
        if key is None or key not in OVERRIDE_KEYS:
            return
        inst = owning_instance(n)
        if inst is None:
            return
        orig = n.id[len(inst.id) + 1:]
        ov = dict(inst.overrides)
        entry = dict(ov.get(orig, {}))
        entry[key] = copy.deepcopy(getattr(n, key))
        ov[orig] = entry
        inst.overrides = ov

    def live_changed(self, relayout=True):
        if relayout:
            self.doc.relayout(sync=False)
        else:
            self.doc.update_connectors(self.page)
        self.canvas.update()
        self.canvas.reposition_overlay()

    def commit(self, label="Изменение"):
        self.doc.relayout()
        self._resolve_selection()
        snap = self.doc.snapshot()
        if snap != self.history[self.hist_i]:
            del self.history[self.hist_i + 1:]
            self.history.append(snap)
            if len(self.history) > 300:
                self.history.pop(0)
                self.saved_i -= 1
            self.hist_i = len(self.history) - 1
        self.refresh_all()
        self.update_title()

    def refresh_all(self):
        if self.pages is not None:
            self.pages.refresh()
        if self.layers is not None:
            self.layers.refresh()
        if self.assets is not None and self.assets.isVisible():
            self.assets.refresh()
        if self.slides_panel is not None:
            self._thumbs.start()
        if self.notes is not None:
            s = self.current_slide()
            if s is not None and self.notes.toPlainText() != s.notes and not self.notes.hasFocus():
                self.notes.blockSignals(True)
                self.notes.setPlainText(s.notes)
                self.notes.blockSignals(False)
        self.inspector.schedule()
        self.canvas.update()

    def _refresh_thumbs(self):
        if self.slides_panel is not None:
            self.slides_panel.refresh()

    def undo(self):
        if self.canvas.editing is not None:
            return
        if self.hist_i > 0:
            self.hist_i -= 1
            self._restore(self.history[self.hist_i])

    def redo(self):
        if self.hist_i < len(self.history) - 1:
            self.hist_i += 1
            self._restore(self.history[self.hist_i])

    def _restore(self, snap):
        page_id = self.page.id
        self.doc.set_state(json.loads(snap))
        self.renderer.drop_caches()
        self.page = next((p for p in self.doc.pages if p.id == page_id), self.doc.pages[0])
        self._resolve_selection()
        self.refresh_all()
        self.update_title()

    def _autosave(self):
        if self.path is not None and self.is_dirty() and self.canvas.editing is None and self.canvas.drag is None:
            try:
                self.save(self.path, quiet=True)
            except Exception:
                pass

    # ================================================================== pages
    def set_page(self, page):
        self.canvas.finish_text_edit()
        self.page = page
        self.selection = []
        self.slide_id = None
        self.refresh_all()
        if self.doc.kind == "site":
            root = self.doc.site_root(page)
            if root is not None:
                self.canvas.fit_width(root)
        elif page.children:
            self.canvas.fit(max_zoom=1.0)
        self.canvas.update()

    def add_page(self):
        k = len(self.doc.pages) + 1
        p = Node("page", name=f"Страница {k}")
        if self.doc.kind == "site":
            p.name = f"Страница {k}"
            root = tpl.webpage(p.name)
            root.add(tpl.block_nav([(q.name, q.id) for q in self.doc.pages[1:]] + [(p.name, p.id)]))
            root.add(tpl.block_text(p.name, "Текст новой страницы."))
            root.add(tpl.block_footer())
            p.add(root)
        self.doc.pages.append(p)
        self.doc.invalidate()
        self.commit("Новая страница")
        self.set_page(p)

    def rename_page(self, page, name):
        if not name:
            return
        page.name = name
        root = self.doc.site_root(page) if self.doc.kind == "site" else None
        if root is not None:
            root.name = name
        self.commit("Переименование страницы")

    def duplicate_page(self, page):
        d = page.to_dict()
        from .model import _remap_ids
        _remap_ids(d)
        p = Node.from_dict(d)
        p.name = page.name + " (копия)"
        self.doc.pages.insert(self.doc.pages.index(page) + 1, p)
        self.doc.invalidate()
        self.commit("Копия страницы")
        self.set_page(p)

    def delete_page(self, page):
        if len(self.doc.pages) <= 1:
            return
        i = self.doc.pages.index(page)
        self.doc.pages.remove(page)
        self.doc.invalidate()
        if page is self.page:
            self.page = self.doc.pages[max(0, i - 1)]
        self.selection = []
        self.commit("Удаление страницы")
        self.set_page(self.page)

    # ================================================================== slides
    def set_slide(self, s):
        self.canvas.finish_text_edit()
        self.slide_id = s.id if s is not None else None
        self.selection = []
        self.canvas.auto_fit = True
        self.canvas.fit(margin=40)
        if self.notes is not None:
            self.notes.blockSignals(True)
            self.notes.setPlainText(s.notes if s is not None else "")
            self.notes.blockSignals(False)
        if self.slides_panel is not None:
            self.slides_panel.refresh()
        if self.layers is not None:
            self.layers.refresh()
        self.inspector.schedule()
        self.canvas.update()

    def step_slide(self, d):
        sl = self.slides()
        cur = self.current_slide()
        if cur is None:
            return
        i = sl.index(cur) + d
        if 0 <= i < len(sl):
            self.set_slide(sl[i])

    def add_slide(self, layout="title_body"):
        theme = self.doc.theme or tpl.THEMES[0]
        s = tpl.make_slide(layout, theme)
        cur = self.current_slide()
        idx = self.page.children.index(cur) + 1 if cur is not None else None
        self.page.add(s, idx)
        self.doc.invalidate()
        self.commit("Новый слайд")
        self.set_slide(s)

    def duplicate_slide(self, s):
        c = s.clone()
        self.page.add(c, self.page.children.index(s) + 1)
        self.doc.invalidate()
        self.commit("Копия слайда")
        self.set_slide(c)

    def delete_slide(self, s):
        sl = self.slides()
        if len(sl) <= 1:
            return
        i = sl.index(s)
        s.remove()
        self.doc.invalidate()
        self.slide_id = None
        self.commit("Удаление слайда")
        rest = self.slides()
        self.set_slide(rest[min(i, len(rest) - 1)])

    def _notes_changed(self):
        s = self.current_slide()
        if s is not None:
            s.notes = self.notes.toPlainText()
            self._notes_timer.start()

    # ================================================================== site
    def set_breakpoint(self, bp):
        self.doc.site["breakpoint"] = bp
        for k, b in self.bp_buttons.items():
            b.setChecked(k == bp)
        self.doc.relayout()
        root = self.doc.site_root(self.page)
        if root is not None:
            self.canvas.fit_width(root)
        self.canvas.update()

    def insert_block(self, key):
        block = tpl.clone_block(key)
        root = self.doc.site_root(self.page)
        if block is None or root is None:
            return
        if key == "nav" and len(self.doc.pages) > 1:
            block = tpl.block_nav([(p.name, p.id) for p in self.doc.pages[1:]])
        idx = None
        for n in self.selection:
            sec = n
            while sec.parent is not None and sec.parent is not root:
                sec = sec.parent
            if sec.parent is root:
                idx = root.children.index(sec) + 1
        root.add(block, idx)
        self.doc.invalidate()
        self.select([block])
        self.commit("Блок")
        r = world_bounds(block)
        self.canvas.off = QPointF(self.canvas.off.x(), 80 - r.y() * self.canvas.zoom)
        self.canvas.update()

    def site_preview_dir(self):
        from .paths import data_dir
        d = data_dir() / "preview" / (self.path.stem if self.path else "untitled")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def preview_site(self):
        from .site import export_site, page_slugs
        out = self.site_preview_dir()
        export_site(self.doc, out, clean=True)
        slug = page_slugs(self.doc).get(self.page.id, "index")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(out / f"{slug}.html")))
        self.status("Сайт открыт в браузере (локальная копия)")

    def export_site(self):
        from .site import export_site, slugify
        base = QFileDialog.getExistingDirectory(self, "Папка для сайта", self.settings.get("last_dir", ""))
        if not base:
            return
        folder = Path(base) / slugify(self.doc.site.get("name", "site"))
        index = export_site(self.doc, folder, clean=True)
        self.status(f"Сайт сохранён: {folder}")
        box = QMessageBox(self)
        box.setWindowTitle("Сайт экспортирован")
        box.setText(f"Готово: {len(self.doc.pages)} стр. в папке\n{folder}")
        openb = box.addButton("Открыть в браузере", QMessageBox.AcceptRole)
        box.addButton("Готово", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is openb:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(index)))

    # ================================================================== structure commands
    def reparent_keep_world(self, n, target, center=None):
        wc = center if center is not None else world_transform(n).map(QPointF(n.w / 2, n.h / 2))
        n.remove()
        target.add(n)
        if target.type == "page":
            lc = wc
        else:
            inv, _ = world_transform(target).inverted()
            lc = inv.map(wc)
        n.x, n.y = lc.x() - n.w / 2, lc.y() - n.h / 2
        if self.settings.get("snap_pixels", True) and n.rotation == 0:
            n.x, n.y = round(n.x), round(n.y)
        self.doc.invalidate()

    def adopt_contained(self, frame):
        par = frame.parent
        fb = world_bounds(frame)
        for c in list(par.children):
            if c is frame or c.type == "connector" or c.locked:
                continue
            if fb.contains(world_bounds(c)) and par.children.index(c) < par.children.index(frame):
                self.reparent_keep_world(c, frame)

    def duplicate_in_place(self, nodes):
        out = []
        for n in nodes:
            c = n.clone()
            n.parent.add(c, n.parent.children.index(n) + 1)
            out.append(c)
        self.doc.invalidate()
        self.selection = out
        return out

    def duplicate(self):
        nodes = self.top_selection()
        if not nodes:
            return
        out = self.duplicate_in_place(nodes)
        for c in out:
            if c.in_flow():
                continue
            if c.parent is self.page and c.type in FRAMELIKE:
                c.x += c.w + 40
            elif self.doc.kind == "board":
                c.x += 24
                c.y += 24
        self.select(out)
        self.commit("Дублирование")

    def delete_nodes(self, nodes, commit=True):
        ids = set()
        protected = {self.scope_root().id}
        for n in nodes:
            if n.id in protected or owning_instance(n) is not None:
                continue
            for d in n.walk():
                ids.add(d.id)
        if not ids:
            return
        for p in self.doc.pages:  # connectors keep their ends where the deleted objects were
            for c in p.children:
                if c.type == "connector" and c.id not in ids:
                    for key in ("start", "end"):
                        e = getattr(c, key)
                        if e.get("id") in ids and c._path is not None:
                            el = c._path.elementAt(0 if key == "start" else c._path.elementCount() - 1)
                            setattr(c, key, {"x": el.x, "y": el.y})
        for n in nodes:
            if n.id in ids and n.parent is not None:
                n.remove()
        self.doc.invalidate()
        self.selection = []
        if commit:
            self.commit("Удаление")

    def delete_selection(self):
        if self.canvas.editing is not None:
            return
        self.delete_nodes(self.top_selection())

    def nudge(self, dx, dy):
        moved = False
        for n in self.top_selection():
            if n.in_flow() or n.locked:
                continue
            pinv, _ = parent_transform(n).inverted()
            d = pinv.map(QPointF(dx, dy)) - pinv.map(QPointF(0, 0))
            n.x += d.x()
            n.y += d.y()
            if n.type == "connector":
                for key in ("start", "end"):
                    e = getattr(n, key)
                    if "x" in e:
                        setattr(n, key, {"x": e["x"] + dx, "y": e["y"] + dy})
            moved = True
        if moved:
            self.commit("Сдвиг")

    def _same_parent(self, nodes):
        return nodes and all(n.parent is nodes[0].parent for n in nodes)

    def group(self, kind="group"):
        nodes = [n for n in self.top_selection() if n.type != "connector" and owning_instance(n) is None]
        if not nodes:
            return None
        if not self._same_parent(nodes):
            nodes = [n for n in nodes if n.parent is nodes[0].parent]
        par = nodes[0].parent
        nodes.sort(key=lambda n: par.children.index(n))
        idx = par.children.index(nodes[-1])
        b = union_rect(world_bounds(n) for n in nodes)
        if kind == "group":
            g = Node("group", name=self._next_name("Группа"))
        else:
            g = Node(kind, name=self._next_name("Компонент" if kind == "component" else "Фрейм"), fills=[],
                     clip=False)
        par.add(g, idx + 1)
        pinv, _ = world_transform(par).inverted() if par.type != "page" else (QTransform(), True)
        tl = pinv.map(b.topLeft())
        g.x, g.y, g.w, g.h = tl.x(), tl.y(), b.width(), b.height()
        if nodes[0].in_flow():
            g.x, g.y = nodes[0].x, nodes[0].y
        for n in nodes:
            self.reparent_keep_world(n, g)
            n.absolute = False
        if kind == "group":
            normalize_group(g)
        self.doc.invalidate()
        self.select([g])
        self.commit("Группировка" if kind == "group" else "Фрейм")
        return g

    def ungroup(self):
        out = []
        for g in self.top_selection():
            if g.type not in ("group", "frame", "section") or not g.children or g is self.scope_root():
                continue
            par = g.parent
            idx = par.children.index(g)
            for c in list(g.children):
                wt = world_transform(c)
                self.reparent_keep_world(c, par)
                par.children.remove(c)
                par.children.insert(idx, c)
                idx += 1
                del wt
                out.append(c)
            g.remove()
        if out:
            self.doc.invalidate()
            self.select(out)
            self.commit("Разгруппировка")

    def frame_selection(self):
        self.group("frame")

    def add_autolayout(self):
        sel = self.top_selection()
        if len(sel) == 1 and sel[0].type in ("frame", "component") and not sel[0].auto:
            f = sel[0]
            kids = [c for c in f.children if c.visible]
            if kids:
                bs = [world_bounds(c) for c in kids]
                spread_x = max(b.right() for b in bs) - min(b.left() for b in bs)
                spread_y = max(b.bottom() for b in bs) - min(b.top() for b in bs)
                f.layout = "row" if spread_x > spread_y else "column"
                key = (lambda c: c.x) if f.layout == "row" else (lambda c: c.y)
                f.children.sort(key=key)
            else:
                f.layout = "column"
            f.gap = f.gap or 10
            if not any(f.pad):
                f.pad = [16, 16, 16, 16]
            f.hug_w = f.hug_h = True
            self.commit("Автолейаут")
            return
        if not sel:
            return
        bs = [world_bounds(n) for n in sel]
        spread_x = max(b.right() for b in bs) - min(b.left() for b in bs)
        spread_y = max(b.bottom() for b in bs) - min(b.top() for b in bs)
        row = spread_x > spread_y
        ordered = sorted(sel, key=lambda n: world_bounds(n).left() if row else world_bounds(n).top())
        gaps = []
        for a, b in zip(ordered, ordered[1:]):
            ba, bb = world_bounds(a), world_bounds(b)
            gaps.append((bb.left() - ba.right()) if row else (bb.top() - ba.bottom()))
        g = self.group("frame")
        if g is None:
            return
        g.layout = "row" if row else "column"
        g.gap = max(0.0, round(sum(gaps) / len(gaps))) if gaps else 10.0
        g.hug_w = g.hug_h = True
        g.children.sort(key=lambda c: ordered.index(c) if c in ordered else 0)
        self.commit("Автолейаут")

    def set_layout(self, v):
        for n in self.selection:
            if n.type in FRAMELIKE:
                n.layout = v
                if v != "none" and not n.gap:
                    n.gap = 10
        self.commit("Автолейаут")

    # ================================================================== components
    def create_component(self):
        sel = self.top_selection()
        if len(sel) == 1 and sel[0].type == "frame":
            sel[0].type = "component"
            sel[0].name = sel[0].name if not sel[0].name.startswith("Фрейм") else self._next_name("Компонент")
            self.commit("Компонент")
            self.select(sel)
            return
        g = self.group("component")
        if g is not None:
            g.fills = []
            self.commit("Компонент")

    def create_instance(self, comp, at_view_center=False):
        inst = make_instance(comp)
        parent = self.scope_root()
        if at_view_center or comp.page() is not self.page or self.doc.kind != "design":
            c = self.canvas.to_world(QPointF(self.canvas.width() / 2, self.canvas.height() / 2))
            if parent.type != "page":
                inv, _ = world_transform(parent).inverted()
                c = inv.map(c)
            inst.x, inst.y = round(c.x() - inst.w / 2), round(c.y() - inst.h / 2)
        else:
            b = world_bounds(comp)
            inst.x, inst.y = b.right() + 40, b.top()
            parent = self.page
        parent.add(inst)
        self.doc.invalidate()
        self.select([inst])
        self.commit("Экземпляр")

    def detach_instance(self):
        for n in self.top_selection():
            if n.type != "instance":
                continue
            n.type = "frame"
            n.master = ""
            n.overrides = {}
            for d in list(n.walk())[1:]:
                d.id = new_id()
        self.doc.invalidate()
        self.commit("Отсоединение")

    def reset_overrides(self):
        for n in self.top_selection():
            if n.type == "instance":
                n.overrides = {}
        self.commit("Сброс изменений")

    def reveal(self, n):
        if n is None:
            return
        if n.page() is not self.page:
            self.set_page(n.page())
        self.select([n])
        self.canvas.fit(world_bounds(n), 120, max_zoom=2.0)

    def zoom_selection(self):
        if self.selection:
            self.canvas.fit(union_rect(world_bounds(n) for n in self.selection), 80)

    # ================================================================== arrange
    def align(self, kind):
        nodes = [n for n in self.top_selection() if not n.in_flow()]
        if not nodes:
            return
        if len(nodes) == 1:
            par = nodes[0].parent
            if par is None or par.type == "page":
                return
            ref = world_bounds(par)
        else:
            ref = union_rect(world_bounds(n) for n in nodes)
        if kind in ("dist_h", "dist_v"):
            if len(nodes) < 3:
                return
            horiz = kind == "dist_h"
            items = sorted(nodes, key=lambda n: world_bounds(n).left() if horiz else world_bounds(n).top())
            total = sum((world_bounds(n).width() if horiz else world_bounds(n).height()) for n in items)
            span = ref.width() if horiz else ref.height()
            gap = (span - total) / (len(items) - 1)
            pos = ref.left() if horiz else ref.top()
            for n in items:
                b = world_bounds(n)
                self._shift_world(n, (pos - b.left(), 0) if horiz else (0, pos - b.top()))
                pos += (b.width() if horiz else b.height()) + gap
        else:
            for n in nodes:
                b = world_bounds(n)
                dx = dy = 0.0
                if kind == "align_left":
                    dx = ref.left() - b.left()
                elif kind == "align_hcenter":
                    dx = ref.center().x() - b.center().x()
                elif kind == "align_right":
                    dx = ref.right() - b.right()
                elif kind == "align_top":
                    dy = ref.top() - b.top()
                elif kind == "align_vcenter":
                    dy = ref.center().y() - b.center().y()
                elif kind == "align_bottom":
                    dy = ref.bottom() - b.bottom()
                self._shift_world(n, (dx, dy))
        self.commit("Выравнивание")

    def _shift_world(self, n, d):
        pinv, _ = parent_transform(n).inverted()
        ld = pinv.map(QPointF(*d)) - pinv.map(QPointF(0, 0))
        n.x += ld.x()
        n.y += ld.y()
        if self.settings.get("snap_pixels", True) and n.rotation == 0:
            n.x, n.y = round(n.x * 2) / 2, round(n.y * 2) / 2

    def order(self, how):
        for n in self.top_selection():
            par = n.parent
            if par is None:
                continue
            i = par.children.index(n)
            par.children.pop(i)
            if how == "front":
                par.children.append(n)
            elif how == "back":
                par.children.insert(0, n)
            elif how == "forward":
                par.children.insert(min(len(par.children), i + 1), n)
            else:
                par.children.insert(max(0, i - 1), n)
        self.commit("Порядок")

    def toggle_visible(self):
        sel = self.top_selection()
        if sel:
            v = not sel[0].visible
            self.set_attr(sel, "visible", v)

    def toggle_lock(self):
        sel = self.top_selection()
        if sel:
            v = not sel[0].locked
            self.set_attr(sel, "locked", v)
            if v:
                self.select([])

    def rename(self, n=None):
        n = n or (self.selection[0] if self.selection else None)
        if n is None:
            return
        name, ok = QInputDialog.getText(self, "Переименовать", "Имя слоя:", text=n.name)
        if ok and name.strip():
            self.set_attr([n], "name", name.strip())

    # ================================================================== vector operations
    def boolean(self, op):
        nodes = [n for n in self.top_selection() if n.type not in ("connector", "page")]
        if len(nodes) < 2:
            self.status("Выделите хотя бы две фигуры")
            return
        par = nodes[0].parent
        nodes = [n for n in nodes if n.parent is par]
        nodes.sort(key=lambda n: par.children.index(n))
        shapes = [self._world_outline(n) for n in nodes]
        res = shapes[0]
        for s in shapes[1:]:
            if op == "union":
                res = res.united(s)
            elif op == "subtract":
                res = res.subtracted(s)
            elif op == "intersect":
                res = res.intersected(s)
            else:
                res = res.united(s).subtracted(res.intersected(s))
        pinv, _ = world_transform(par).inverted() if par.type != "page" else (QTransform(), True)
        local = pinv.map(res.simplified())
        base = nodes[0]
        n = Node("path", name={"union": "Объединение", "subtract": "Вычитание", "intersect": "Пересечение",
                               "exclude": "Исключение"}[op], paths=path_to_points(local),
                 fills=copy.deepcopy(base.fills) or [solid("#D9D9D9")], strokes=copy.deepcopy(base.strokes),
                 stroke_width=base.stroke_width, effects=copy.deepcopy(base.effects), stroke_align="inside")
        if not n.paths:
            self.status("Результат пустой")
            return
        normalize_path(n)
        idx = par.children.index(nodes[-1])
        par.add(n, idx + 1)
        for m in nodes:
            m.remove()
        self.doc.invalidate()
        self.select([n])
        self.commit("Булева операция")

    def _world_outline(self, n):
        if n.type == "text":
            return world_transform(n).map(self._text_path(n))
        if n.container:
            p = QPainterPath()
            for c in n.children:
                p = p.united(self._world_outline(c))
            return p if n.type == "group" else p.united(world_shape(n))
        return world_shape(n)

    def _text_path(self, n):
        width = None if n.sizing == "auto_w" else n.w
        block = textlib.node_block(n, width)
        f = textlib.node_font(n)
        p = QPainterPath()
        for s, x, base, _ in block.lines:
            if s:
                p.addText(QPointF(x, base), f, s)
        return p

    def flatten(self):
        out = []
        for n in self.top_selection():
            if n.type in ("connector", "page", "path") or n.container:
                continue
            qp = self._text_path(n) if n.type == "text" else shape_path(n)
            m = Node("path", name=n.name, x=n.x, y=n.y, w=n.w, h=n.h, rotation=n.rotation,
                     paths=path_to_points(qp), fills=copy.deepcopy(n.fills), strokes=copy.deepcopy(n.strokes),
                     stroke_width=n.stroke_width, effects=copy.deepcopy(n.effects), opacity=n.opacity,
                     stroke_align=n.stroke_align, grow=n.grow, stretch=n.stretch)
            if not m.paths:
                continue
            normalize_path(m)
            par = n.parent
            par.add(m, par.children.index(n))
            n.remove()
            out.append(m)
        if out:
            self.doc.invalidate()
            self.select(out)
            self.commit("В кривые")

    def outline_stroke(self):
        out = []
        for n in self.top_selection():
            paints = [s for s in n.strokes if s.get("visible", True)]
            if not paints or n.stroke_width <= 0 or n.container:
                continue
            st = QPainterPathStroker()
            st.setWidth(n.stroke_width)
            st.setCapStyle(Qt.RoundCap if n.type == "path" else Qt.FlatCap)
            st.setJoinStyle(Qt.RoundJoin)
            qp = st.createStroke(shape_path(n)).simplified()
            m = Node("path", name=n.name + " (контур)", x=n.x, y=n.y, w=n.w, h=n.h, rotation=n.rotation,
                     paths=path_to_points(qp), fills=copy.deepcopy(paints), opacity=n.opacity)
            normalize_path(m)
            par = n.parent
            par.add(m, par.children.index(n) + 1)
            if n.fills and n.type != "path":
                n.strokes = []
            else:
                n.remove()
            out.append(m)
        if out:
            self.doc.invalidate()
            self.select(out)
            self.commit("Обвести контур")

    def use_as_mask(self):
        sel = self.top_selection()
        if len(sel) < 2:
            if len(sel) == 1:
                self.set_attr(sel, "mask", not sel[0].mask)
            return
        par = sel[0].parent
        bottom = min(sel, key=lambda n: par.children.index(n) if n.parent is par else 1e9)
        g = self.group()
        if g is not None:
            bottom.mask = True
            g.name = "Маска"
            self.commit("Маска")

    # ================================================================== clipboard
    def copy(self):
        nodes = self.top_selection()
        if not nodes:
            return
        imgs = {}
        for n in nodes:
            for d in n.walk():
                for p in d.fills:
                    if p.get("type") == "image" and p.get("ref") in self.doc.images:
                        imgs[p["ref"]] = base64.b64encode(self.doc.images[p["ref"]]).decode()
        data = {"nodes": [n.to_dict() for n in nodes],
                "world": [[world_bounds(n).x(), world_bounds(n).y()] for n in nodes],
                "images": imgs}
        md = QMimeData()
        md.setData(MIME, json.dumps(data, ensure_ascii=False).encode("utf-8"))
        try:
            md.setImageData(render_image(self.renderer, nodes, 2.0))
        except Exception:
            pass
        QGuiApplication.clipboard().setMimeData(md)
        self.status(f"Скопировано: {len(nodes)}")

    def cut(self):
        self.copy()
        self.delete_selection()

    def paste(self):
        md = QGuiApplication.clipboard().mimeData()
        center = self.canvas.to_world(QPointF(self.canvas.width() / 2, self.canvas.height() / 2))
        if md.hasFormat(MIME):
            data = json.loads(bytes(md.data(MIME)).decode("utf-8"))
            for ref, b64 in data.get("images", {}).items():
                self.doc.images.setdefault(ref, base64.b64decode(b64))
            from .model import _remap_ids
            target = self.scope_root()
            if len(self.selection) == 1 and self.selection[0].type in ("frame", "component", "section") \
                    and owning_instance(self.selection[0]) is None:
                target = self.selection[0]
            out = []
            view = QRectF(self.canvas.to_world(QPointF(0, 0)),
                          self.canvas.to_world(QPointF(self.canvas.width(), self.canvas.height())))
            worlds = data.get("world") or [[0, 0]] * len(data["nodes"])
            union = None
            for d, (wx, wy) in zip(data["nodes"], worlds):
                r = QRectF(wx, wy, d.get("w", 100), d.get("h", 100))
                union = r if union is None else union.united(r)
            shift = QPointF(0, 0)
            if union is not None and not view.intersects(union):
                shift = center - union.center()
            for d, (wx, wy) in zip(data["nodes"], worlds):
                _remap_ids(d)
                n = Node.from_dict(d)
                target.add(n)
                if n.type == "connector":
                    for key in ("start", "end"):
                        e = getattr(n, key)
                        if e.get("id") and self.doc.find(e["id"]) is None:
                            setattr(n, key, {"x": e.get("x", wx), "y": e.get("y", wy)})
                else:
                    tl = QPointF(wx, wy) + shift
                    if target.type != "page":
                        inv, _ = world_transform(target).inverted()
                        tl = inv.map(tl)
                    n.x, n.y = tl.x(), tl.y()
                out.append(n)
            self.doc.invalidate()
            self.select(out)
            self.commit("Вставка")
            return
        if md.hasImage():
            self.insert_qimage(md.imageData(), center)
            return
        if md.hasUrls():
            self.import_files([u.toLocalFile() for u in md.urls() if u.isLocalFile()], center)
            return
        if md.hasText() and md.text().strip():
            t = md.text().strip()
            if t.lstrip().startswith("<svg"):
                self._insert_svg(t.encode("utf-8"), center, "SVG")
                return
            if self.doc.kind == "board":
                n = Node("sticky", text=t, fills=[solid(self.tool_opts["sticky"])])
            else:
                n = Node("text", text=t, size=self.default_text_size(), sizing="auto_w" if len(t) < 60 else "auto_h",
                         w=400, name=t[:30])
            n.x, n.y = center.x() - 100, center.y() - 20
            self._place_world(n, center)
            self.commit("Вставка")

    def _place_world(self, n, center):
        parent = self.canvas.container_at(center)
        from .model import arrange
        arrange(n)
        c = QPointF(center)
        if parent.type != "page":
            inv, _ = world_transform(parent).inverted()
            c = inv.map(c)
        n.x, n.y = round(c.x() - n.w / 2), round(c.y() - n.h / 2)
        parent.add(n)
        self.doc.invalidate()
        self.select([n])

    # ================================================================== import
    def place_image_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Изображения или SVG", self.settings.get("last_dir", ""),
                                                "Изображения (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.tiff *.svg)")
        if paths:
            self.settings["last_dir"] = str(Path(paths[0]).parent)
            self.import_files(paths)

    def import_files(self, paths, at=None):
        at = at or self.canvas.to_world(QPointF(self.canvas.width() / 2, self.canvas.height() / 2))
        done = 0
        for i, p in enumerate(paths):
            path = Path(p)
            ext = path.suffix.lower()
            pos = at + QPointF(i * 24, i * 24)
            try:
                if ext == ".lambda":
                    self.win.open_path(path)
                    continue
                data = path.read_bytes()
                if ext == ".svg":
                    self._insert_svg(data, pos, path.stem)
                else:
                    if not self.insert_image_bytes(data, pos, path.stem):
                        continue
                done += 1
            except Exception as ex:  # noqa: BLE001
                QMessageBox.warning(self, "Импорт", f"Не удалось открыть {path.name}:\n{ex}")
        if done:
            self.commit("Импорт")

    def _insert_svg(self, data, pos, name):
        from .svgio import import_svg
        g = import_svg(data, name)
        if not g.children:
            return
        if len(g.children) == 1:
            only = g.children[0]
            only.x += g.x
            only.y += g.y
            only.remove()
            g = only
        self._place_world(g, pos)

    def insert_image_bytes(self, data, pos, name="Изображение"):
        img = QImage.fromData(data)
        if img.isNull():
            return False
        ref = self.doc.add_image(data)
        w, h = img.width(), img.height()
        k = min(1.0, 1200 / max(w, h))
        n = Node("rect", name=name, w=round(w * k), h=round(h * k), fills=[{"type": "image", "ref": ref, "mode": "fill",
                                                                           "opacity": 1.0}])
        self._place_world(n, pos)
        return True

    def insert_qimage(self, img, pos):
        if isinstance(img, QImage) and not img.isNull():
            self.insert_image_bytes(fileio.image_bytes(img), pos, "Вставленное изображение")
            self.commit("Вставка изображения")

    # ================================================================== presets / misc
    def add_preset_frame(self, name, w, h):
        f = Node("frame", name=name, w=w, h=h)
        right = max([world_bounds(c).right() for c in self.page.children if c.type != "connector"] or [0.0])
        top = min([world_bounds(c).top() for c in self.page.children if c.type in FRAMELIKE] or [0.0])
        f.x, f.y = (right + 80 if self.page.children else 0), top
        self.page.add(f)
        self.doc.invalidate()
        self.select([f])
        self.set_tool("select")
        self.commit("Фрейм")
        self.canvas.fit(world_bounds(f), 80, max_zoom=1.0)

    # ================================================================== present / export
    def present(self):
        from .player import open_player
        kind = self.doc.kind
        if kind == "slides":
            frames = [s for s in self.slides() if s.visible]
            cur = self.current_slide()
            start = frames.index(cur) if cur in frames else 0
            p, pres = open_player(self, frames, start, slides=True)
        elif kind == "site":
            self.preview_site()
            return
        else:
            frames = [c for c in self.page.children if c.type == "frame" and c.visible] or \
                [c for c in self.page.children if c.type == "component" and c.visible]
            frames.sort(key=lambda f: (round(world_bounds(f).y() / 200), world_bounds(f).x()))
            if not frames:
                QMessageBox.information(self, "Прототип", "На странице нет фреймов. Нарисуйте фрейм (F) — "
                                                          "он станет экраном прототипа.")
                return
            start = 0
            for n in self.selection:
                top = n
                while top.parent is not None and top.parent.type != "page":
                    top = top.parent
                if top in frames:
                    start = frames.index(top)
            p, pres = open_player(self, frames, start)
        self.windows = [w for w in self.windows if w.isVisible()] + [w for w in (p, pres) if w is not None]

    def present_presenter(self):
        from .player import open_player
        frames = [s for s in self.slides() if s.visible]
        if not frames:
            return
        cur = self.current_slide()
        p, pres = open_player(self, frames, frames.index(cur) if cur in frames else 0, slides=True, presenter=True)
        self.windows = [w for w in self.windows if w.isVisible()] + [w for w in (p, pres) if w is not None]

    def _safe_name(self, s):
        import re
        return re.sub(r'[\\/:*?"<>|]+', "_", s).strip() or "export"

    def export_selection(self):
        nodes = self.top_selection()
        if not nodes:
            return
        fmt = self.settings.get("export_format", "PNG")
        scale = float(self.settings.get("export_scale", 2))
        ext = {"JPG": "jpg", "PNG": "png", "WEBP": "webp", "SVG": "svg", "PDF": "pdf"}[fmt]
        last = self.settings.get("last_dir", "") or str(Path.home())
        if len(nodes) == 1 or fmt == "PDF":
            name = self._safe_name(nodes[0].name if len(nodes) == 1 else self.title())
            path, _ = QFileDialog.getSaveFileName(self, "Экспорт", str(Path(last) / f"{name}.{ext}"), f"{fmt} (*.{ext})")
            if not path:
                return
            if fmt == "PDF":
                fileio.export_pdf(self.doc, nodes, path, self.renderer)
            else:
                fileio.export_nodes(self.doc, nodes, path, fmt, scale, self.renderer)
            self.settings["last_dir"] = str(Path(path).parent)
            self.status(f"Экспортировано: {Path(path).name}")
            return
        folder = QFileDialog.getExistingDirectory(self, "Папка для экспорта", last)
        if not folder:
            return
        self._export_each(nodes, Path(folder), fmt, scale, ext)

    def _export_each(self, nodes, folder, fmt, scale, ext):
        used = set()
        for n in nodes:
            base = self._safe_name(n.name)
            name, k = base, 2
            while name in used:
                name = f"{base} {k}"
                k += 1
            used.add(name)
            fileio.export_nodes(self.doc, [n], folder / f"{name}.{ext}", fmt, scale, self.renderer)
        self.settings["last_dir"] = str(folder)
        self.status(f"Экспортировано файлов: {len(nodes)} → {folder}")

    def export_dialog(self, all_frames=False):
        if not all_frames and self.selection:
            self.export_selection()
            return
        kind = self.doc.kind
        if kind == "slides":
            self.export_pdf_all()
            return
        if kind == "site":
            self.export_site()
            return
        frames = [c for c in self.page.children if c.type in FRAMELIKE and c.visible] or \
                 [c for c in self.page.children if c.visible]
        if not frames:
            return
        folder = QFileDialog.getExistingDirectory(self, "Папка для экспорта", self.settings.get("last_dir", ""))
        if not folder:
            return
        fmt = self.settings.get("export_format", "PNG")
        ext = {"JPG": "jpg", "PNG": "png", "WEBP": "webp", "SVG": "svg", "PDF": "pdf"}[fmt]
        self._export_each(frames, Path(folder), fmt, float(self.settings.get("export_scale", 2)), ext)

    def export_pdf_all(self):
        frames = [s for s in self.slides() if s.visible] if self.doc.kind == "slides" else \
            [c for c in self.page.children if c.type in FRAMELIKE and c.visible]
        if not frames:
            return
        last = self.settings.get("last_dir", "") or str(Path.home())
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт в PDF", str(Path(last) / f"{self._safe_name(self.title())}.pdf"),
                                              "PDF (*.pdf)")
        if not path:
            return
        fileio.export_pdf(self.doc, frames, path, self.renderer)
        self.settings["last_dir"] = str(Path(path).parent)
        self.status(f"PDF сохранён: {Path(path).name}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    # ================================================================== saving
    def save(self, path=None, quiet=False):
        path = Path(path or self.path)
        if path.suffix.lower() != ".lambda":
            path = path.with_suffix(".lambda")
        self.canvas.finish_text_edit()
        fileio.save(self.doc, path, self.renderer)
        self.path = path
        self.saved_i = self.hist_i
        if not quiet:
            self.settings.add_recent(path)
            self.status(f"Сохранено: {path.name}")
        self.update_title()
        return True

    # ================================================================== context menu
    def context_menu(self, gpos, w):
        m = QMenu(self)
        sel = self.top_selection()
        win = self.win
        if sel:
            m.addAction("Копировать\t⌘C", self.copy)
            m.addAction("Вырезать\t⌘X", self.cut)
            m.addAction("Вставить\t⌘V", self.paste)
            m.addAction("Дублировать\t⌘D", self.duplicate)
            m.addAction("Удалить\t⌫", self.delete_selection)
            m.addSeparator()
            m.addAction("Сгруппировать\t⌘G", self.group)
            if any(n.type in ("group", "frame", "section") for n in sel):
                m.addAction("Разгруппировать\t⇧⌘G", self.ungroup)
            if self.doc.kind != "board":
                m.addAction("Фрейм из выделения\t⌥⌘G", self.frame_selection)
                m.addAction("Добавить автолейаут\t⇧A", self.add_autolayout)
            if self.doc.kind == "design":
                m.addSeparator()
                if any(n.type == "instance" for n in sel):
                    m.addAction("Отсоединить экземпляр\t⌥⌘B", self.detach_instance)
                    comp = self.doc.find(sel[0].master) if sel[0].type == "instance" else None
                    if comp is not None:
                        m.addAction("Перейти к главному компоненту", lambda: self.reveal(comp))
                elif sel[0].type == "component":
                    m.addAction("Создать экземпляр", lambda: self.create_instance(sel[0]))
                else:
                    m.addAction("Создать компонент\t⌥⌘K", self.create_component)
            if self.doc.kind != "board" or len(sel) > 1:
                b = m.addMenu("Булевы операции")
                for op, title in (("union", "Объединить"), ("subtract", "Вычесть"), ("intersect", "Пересечь"),
                                  ("exclude", "Исключить")):
                    b.addAction(icons.icon(op, self.theme["text"], self.theme["accent"]), title,
                                lambda o=op: self.boolean(o))
            if self.doc.kind != "board":
                m.addAction("Преобразовать в кривые\t⌘E", self.flatten)
                m.addAction("Обвести контур", self.outline_stroke)
                m.addAction("Использовать как маску\t⌃⌘M", self.use_as_mask)
            m.addSeparator()
            o = m.addMenu("Порядок")
            o.addAction("На передний план\t⌥⌘]", lambda: self.order("front"))
            o.addAction("Вперёд\t⌘]", lambda: self.order("forward"))
            o.addAction("Назад\t⌘[", lambda: self.order("backward"))
            o.addAction("На задний план\t⌥⌘[", lambda: self.order("back"))
            m.addAction("Показать / скрыть\t⇧⌘H", self.toggle_visible)
            m.addAction("Заблокировать / разблокировать\t⇧⌘L", self.toggle_lock)
            m.addAction("Переименовать…", self.rename)
            m.addSeparator()
            m.addAction("Экспорт…", self.export_selection)
        else:
            m.addAction("Вставить\t⌘V", self.paste)
            m.addAction("Выделить всё\t⌘A", self.select_all)
            m.addAction("Показать всё\t⇧1", lambda: self.canvas.fit())
            if self.doc.kind == "slides":
                sub = m.addMenu("Новый слайд")
                for key, title in tpl.LAYOUTS:
                    sub.addAction(title, lambda k=key: self.add_slide(k))
            if self.doc.kind == "design":
                m.addAction("▶ Презентовать", self.present)
        del win
        m.exec(gpos)

    # ================================================================== shutdown
    def close_windows(self):
        for w in self.windows:
            try:
                w.close()
            except RuntimeError:
                pass
        self.autosave.stop()
