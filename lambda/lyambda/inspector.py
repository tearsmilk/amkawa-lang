"""Right panel: properties of the selection (Figma-like «Дизайн» / «Прототип» tabs; «Сайт» and «Слайд» tabs in
those editors). Values apply to every selected node; number fields scrub by dragging their label."""
import copy
import re

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFileDialog, QFontComboBox, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QTabBar, QToolButton,
                               QVBoxLayout, QWidget)

from . import icons
from . import templates as tpl
from . import text as textlib
from .model import FRAMELIKE, SHAPE_KINDS, TYPE_TITLES, owning_instance, solid
from .render import BLEND_TITLES

ARROWS = [("none", "Нет"), ("arrow", "Стрелка"), ("line", "Уголок"), ("circle", "Круг"), ("square", "Квадрат")]
TRANSITIONS = [("none", "Мгновенно"), ("dissolve", "Растворение"), ("slide_left", "Сдвиг влево"),
               ("slide_right", "Сдвиг вправо"), ("push", "Выталкивание")]
PAINT_TYPES = [("solid", "Сплошная"), ("linear", "Линейный градиент"), ("radial", "Радиальный градиент"),
               ("image", "Изображение")]


def _parse_num(s):
    s = s.strip().replace(",", ".").replace("×", "*").rstrip("%° px")
    if not s:
        return None
    if re.fullmatch(r"[0-9+\-*/(). ]+", s):
        try:
            return float(eval(s, {"__builtins__": {}}, {}))  # noqa: S307 — digits and operators only
        except Exception:
            return None
    return None


def _fmt(v, decimals=2):
    if v is None:
        return "Смешано"
    v = round(float(v), decimals)
    return str(int(v)) if v == int(v) else f"{v:g}"


class ScrubLabel(QLabel):
    def __init__(self, text, field):
        super().__init__(text)
        self.field = field
        self.setObjectName("Scrub")
        self.setCursor(Qt.SizeHorCursor)
        self._x = None

    def mousePressEvent(self, e):
        self._x = e.position().x()
        self._v = self.field.value or 0.0

    def mouseMoveEvent(self, e):
        if self._x is None:
            return
        k = 10 if e.modifiers() & Qt.ShiftModifier else 1
        v = self._v + (e.position().x() - self._x) * self.field.step * k
        self.field.set_value(v, emit="live")

    def mouseReleaseEvent(self, e):
        if self._x is not None and self.field.value is not None:
            self.field.committed.emit(self.field.value)
        self._x = None


class NumField(QWidget):
    committed = Signal(float)
    live = Signal(float)

    def __init__(self, label, value, step=1.0, lo=None, hi=None, key="", suffix=""):
        super().__init__()
        self.key = key
        self.step, self.lo, self.hi, self.suffix = step, lo, hi, suffix
        self.value = value
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.label = ScrubLabel(label, self)
        self.edit = QLineEdit()
        self.edit.setObjectName("Field")
        self.edit.setMinimumWidth(36)
        lay.addWidget(self.label)
        lay.addWidget(self.edit, 1)
        self.edit.setText(_fmt(value) + (suffix if value is not None else ""))
        self.edit.editingFinished.connect(self._finished)

    def clamp(self, v):
        if self.lo is not None:
            v = max(self.lo, v)
        if self.hi is not None:
            v = min(self.hi, v)
        return v

    def set_value(self, v, emit=None):
        self.value = self.clamp(v)
        self.edit.setText(_fmt(self.value) + self.suffix)
        if emit == "live":
            self.live.emit(self.value)

    def _finished(self):
        if not self.edit.isModified():
            return
        self.edit.setModified(False)
        v = _parse_num(self.edit.text())
        if v is None:
            self.edit.setText(_fmt(self.value) + (self.suffix if self.value is not None else ""))
            return
        self.set_value(v)
        self.committed.emit(self.value)


class Swatch(QToolButton):
    picked = Signal(str)
    live = Signal(str)

    def __init__(self, color, size=20, alpha=False):
        super().__init__()
        self.color = color or "#000000"
        self.alpha = alpha
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self.choose)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        q = QColor(self.color)
        if q.alpha() < 255:
            p.fillRect(r, QColor("#FFFFFF"))
            p.fillRect(QRectF(r.x(), r.y(), r.width() / 2, r.height() / 2), QColor("#D8D4C8"))
            p.fillRect(QRectF(r.center().x(), r.center().y(), r.width() / 2, r.height() / 2), QColor("#D8D4C8"))
        p.setPen(QPen(QColor(0, 0, 0, 40), 1))
        p.setBrush(q)
        p.drawRoundedRect(r, 4, 4)

    def choose(self):
        orig = self.color
        dlg = QColorDialog(QColor(self.color), self.window())
        dlg.setOption(QColorDialog.DontUseNativeDialog, True)
        dlg.setOption(QColorDialog.ShowAlphaChannel, self.alpha)
        dlg.setWindowTitle("Цвет")
        dlg.currentColorChanged.connect(lambda c: self.live.emit(_hex(c, self.alpha)))
        if dlg.exec():
            self.color = _hex(dlg.currentColor(), self.alpha)
            self.update()
            self.picked.emit(self.color)
        else:
            self.live.emit(orig)


def _hex(q, alpha=False):
    if alpha and q.alpha() < 255:
        return q.name(QColor.HexArgb)
    return q.name().upper()


def seg(options, current, on_pick, icon_mode=False, ink="#141413", accent="#D97757"):
    """A segmented row of checkable buttons: options = [(value, label or icon name, tooltip)]."""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    for value, label, tip in options:
        b = QToolButton()
        b.setCheckable(True)
        b.setChecked(value == current)
        b.setToolTip(tip)
        if icon_mode:
            b.setIcon(icons.icon(label, ink, accent))
            b.setIconSize(QSize(16, 16))
        else:
            b.setText(label)
        b.clicked.connect(lambda _=False, v=value: on_pick(v))
        lay.addWidget(b)
    lay.addStretch(1)
    return w


class Inspector(QWidget):
    def __init__(self, editor):
        super().__init__()
        self.ed = editor
        self.setObjectName("Inspector")
        self.tab = 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.tabs = QTabBar()
        self.tabs.setObjectName("DocTabs")
        self.tabs.setDrawBase(False)
        self.tabs.setExpanding(False)
        second = {"design": "Прототип", "site": "Сайт", "slides": "Слайд"}.get(editor.doc.kind)
        self.tabs.addTab("Дизайн")
        if second:
            self.tabs.addTab(second)
        self.tabs.setVisible(bool(second))
        self.tabs.currentChanged.connect(self._tab)
        lay.addWidget(self.tabs)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        lay.addWidget(self.scroll, 1)
        self.body = None
        self.fields = {}
        self._pending = False

    def _tab(self, i):
        self.tab = i
        self.rebuild()

    # ------------------------------------------------------------------ plumbing
    @property
    def nodes(self):
        return self.ed.selection

    def schedule(self):
        if not self._pending:
            self._pending = True
            QTimer.singleShot(0, self._do_rebuild)

    def _do_rebuild(self):
        self._pending = False
        self.rebuild()

    def apply(self, key, value, commit=True, nodes=None):
        self.ed.set_attr(nodes if nodes is not None else self.nodes, key, value, commit=commit)

    def apply_each(self, fn, label="Свойства", commit=True):
        """fn(node) mutates the node directly (geometry, nested lists)."""
        for n in self.nodes:
            fn(n)
            self.ed.note_override(n)
        if commit:
            self.ed.commit(label)
        else:
            self.ed.live_changed()

    def common(self, key):
        vals = [getattr(n, key) for n in self.nodes]
        if not vals:
            return None
        return vals[0] if all(v == vals[0] for v in vals) else None

    def rebuild(self):
        focused = None
        fw = self.window().focusWidget() if self.window() else None
        for key, f in self.fields.items():
            if isinstance(f, NumField) and f.edit is fw:
                focused = key
        self.fields = {}
        body = QWidget()
        body.setObjectName("InspectorBody")
        self.lay = QVBoxLayout(body)
        self.lay.setContentsMargins(14, 8, 14, 14)
        self.lay.setSpacing(6)
        kind = self.ed.doc.kind
        try:
            if self.tab == 1 and kind == "design":
                self.build_prototype()
            elif self.tab == 1 and kind == "site":
                self.build_site()
            elif self.tab == 1 and kind == "slides":
                self.build_slide()
            elif not self.nodes:
                self.build_empty()
            else:
                self.build_design()
        except RuntimeError:
            pass
        self.lay.addStretch(1)
        pos = self.scroll.verticalScrollBar().value()
        self.scroll.setWidget(body)  # deletes the previous body
        self.scroll.verticalScrollBar().setValue(pos)
        if focused and focused in self.fields:
            self.fields[focused].edit.setFocus()
            self.fields[focused].edit.selectAll()

    # ------------------------------------------------------------------ builders
    def section(self, title, plus=None, plus_tip=""):
        row = QHBoxLayout()
        row.setContentsMargins(0, 8, 0, 2)
        lbl = QLabel(title.upper())
        lbl.setObjectName("Section")
        row.addWidget(lbl)
        row.addStretch(1)
        if plus is not None:
            b = QToolButton()
            b.setIcon(icons.icon("plus", self.ed.theme["text"], self.ed.theme["accent"]))
            b.setIconSize(QSize(14, 14))
            b.setToolTip(plus_tip)
            b.clicked.connect(plus)
            row.addWidget(b)
        self.lay.addLayout(row)

    def sep(self):
        line = QFrame()
        line.setObjectName("Sep")
        line.setFixedHeight(1)
        self.lay.addWidget(line)

    def grid(self, widgets, cols=2):
        g = QGridLayout()
        g.setContentsMargins(0, 0, 0, 0)
        g.setHorizontalSpacing(8)
        g.setVerticalSpacing(4)
        for i, w in enumerate(widgets):
            if w is not None:
                g.addWidget(w, i // cols, i % cols)
        self.lay.addLayout(g)

    def num(self, label, key, value, step=1.0, lo=None, hi=None, on_commit=None, on_live=None, suffix=""):
        f = NumField(label, value, step, lo, hi, key, suffix)
        if on_commit is None:
            on_commit = lambda v, k=key: self.apply(k, v)  # noqa: E731
        if on_live is None:
            on_live = lambda v, k=key: self.apply(k, v, commit=False)  # noqa: E731
        f.committed.connect(on_commit)
        f.live.connect(on_live)
        self.fields[key] = f
        return f

    def check(self, text, value, on):
        c = QCheckBox(text)
        c.setChecked(bool(value))
        c.toggled.connect(on)
        return c

    def combo(self, options, current, on):
        cb = QComboBox()
        for v, t in options:
            cb.addItem(t, v)
        i = cb.findData(current)
        cb.setCurrentIndex(max(0, i))
        cb.activated.connect(lambda i, c=cb: on(c.itemData(i)))
        return cb

    def button(self, text, on, accent=False):
        b = QPushButton(text)
        if accent:
            b.setObjectName("Accent")
        b.clicked.connect(on)
        return b

    def row(self, *widgets, stretch_last=False):
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        for w in widgets:
            if isinstance(w, int):
                h.addStretch(w)
            else:
                h.addWidget(w)
        self.lay.addLayout(h)
        return h

    def palette(self, colors, current, on, size=22):
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(5)
        for i, c in enumerate(colors):
            hexv = c[1] if isinstance(c, tuple) else c
            b = QToolButton()
            b.setFixedSize(size, size)
            border = self.ed.theme["accent"] if (current or "").upper() == hexv.upper() else "rgba(0,0,0,0.15)"
            b.setStyleSheet(f"QToolButton {{ background: {hexv}; border: 2px solid {border}; border-radius: {size // 2}px; }}")
            if isinstance(c, tuple):
                b.setToolTip(c[0])
            b.clicked.connect(lambda _=False, h=hexv: on(h))
            g.addWidget(b, i // 9, i % 9)
        self.lay.addWidget(w)

    # ------------------------------------------------------------------ nothing selected
    def build_empty(self):
        ed = self.ed
        kind = ed.doc.kind
        page = ed.page
        if kind in ("design", "board") and ed.tool == "frame" and kind == "design":
            self.section("Фрейм")
            for group, items in tpl.FRAME_PRESETS:
                lbl = QLabel(group)
                lbl.setObjectName("Muted")
                self.lay.addWidget(lbl)
                for name, w, h in items:
                    b = QPushButton(f"{name}    {w} × {h}")
                    b.setObjectName("Link")
                    b.clicked.connect(lambda _=False, n=name, ww=w, hh=h: ed.add_preset_frame(n, ww, hh))
                    self.lay.addWidget(b)
            return
        if kind == "slides":
            self.build_slide()
            return
        if kind == "site":
            self.build_site()
            return
        self.section("Страница")
        sw = Swatch(page.bg or (ed.theme["board"] if kind == "board" else ed.theme["canvas"]))
        sw.picked.connect(lambda c: self._page_bg(c))
        sw.live.connect(lambda c: self._page_bg(c, False))
        hexe = QLineEdit(page.bg or "по умолчанию")
        hexe.setObjectName("Field")
        hexe.editingFinished.connect(lambda e=hexe: self._page_bg(e.text() if QColor(e.text()).isValid() else ""))
        self.row(sw, hexe)
        if page.bg:
            self.lay.addWidget(self.button("Сбросить фон", lambda: self._page_bg("")))
        self.section("Экспорт")
        lbl = QLabel("Выделите объекты или фреймы, чтобы экспортировать их в PNG, JPG, SVG или PDF.")
        lbl.setWordWrap(True)
        lbl.setObjectName("Muted")
        self.lay.addWidget(lbl)
        if kind == "design":
            self.lay.addWidget(self.button("Экспортировать все фреймы…", lambda: ed.export_dialog(all_frames=True)))

    def _page_bg(self, c, commit=True):
        self.ed.page.bg = c
        if commit:
            self.ed.commit("Фон страницы")
        self.ed.canvas.update()

    # ------------------------------------------------------------------ design tab
    def build_design(self):
        ed = self.ed
        nodes = self.nodes
        n = nodes[0]
        types = {x.type for x in nodes}
        th = ed.theme
        # header
        title = TYPE_TITLES.get(n.type, n.type) if len(types) == 1 else "Несколько объектов"
        if len(nodes) > 1:
            title += f" · {len(nodes)}"
        head = QLabel(title)
        head.setObjectName("Logo")
        self.lay.addWidget(head)
        inst = owning_instance(n)
        if n.type == "instance":
            comp = ed.doc.find(n.master)
            self.row(self.button("К главному", lambda: ed.reveal(comp)),
                     self.button("Отсоединить", ed.detach_instance))
            if n.overrides:
                self.lay.addWidget(self.button("Сбросить изменения", ed.reset_overrides))
        elif n.type == "component":
            self.lay.addWidget(self.button("Создать экземпляр", lambda: ed.create_instance(n)))
        elif inst is not None:
            lbl = QLabel(f"Часть экземпляра «{inst.name}». Изменения текста и цвета сохранятся при обновлении компонента.")
            lbl.setWordWrap(True)
            lbl.setObjectName("Muted")
            self.lay.addWidget(lbl)
        # alignment
        al = QWidget()
        h = QHBoxLayout(al)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(1)
        for key, tip in (("align_left", "По левому краю"), ("align_hcenter", "По центру"), ("align_right", "По правому"),
                         ("align_top", "По верху"), ("align_vcenter", "По середине"), ("align_bottom", "По низу"),
                         ("dist_h", "Распределить по горизонтали"), ("dist_v", "Распределить по вертикали")):
            b = QToolButton()
            b.setIcon(icons.icon(key, th["text"], th["accent"]))
            b.setIconSize(QSize(16, 16))
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, k=key: ed.align(k))
            h.addWidget(b)
        h.addStretch(1)
        self.lay.addWidget(al)
        self.sep()
        # geometry
        if "connector" not in types:
            in_flow = n.in_flow()
            self.section("Фрейм" if n.type in FRAMELIKE else "Положение и размер")
            self.grid([
                self.num("X", "x", self.common("x"), 1, on_commit=lambda v: self._geom("x", v),
                         on_live=lambda v: self._geom("x", v, False)) if not in_flow else None,
                self.num("Y", "y", self.common("y"), 1, on_commit=lambda v: self._geom("y", v),
                         on_live=lambda v: self._geom("y", v, False)) if not in_flow else None,
                self.num("Ш", "w", self.common("w"), 1, 0, on_commit=lambda v: self._size("w", v),
                         on_live=lambda v: self._size("w", v, False)),
                self.num("В", "h", self.common("h"), 1, 0, on_commit=lambda v: self._size("h", v),
                         on_live=lambda v: self._size("h", v, False)),
                self.num("↻", "rotation", self.common("rotation"), 1, -180, 180, suffix="°")
                if not types & {"group"} and not in_flow else None,
                self.num("◜", "radius", self.common("radius"), 1, 0)
                if types <= {"rect", "frame", "component", "instance", "section"} else None,
            ])
            if types <= FRAMELIKE - {"section"}:
                self.lay.addWidget(self.check("Обрезать содержимое", self.common("clip"), lambda v: self.apply("clip", v)))
        if types <= {"polygon", "star"}:
            self.grid([self.num("Углы", "count", self.common("count"), 1, 3, 60),
                       self.num("Глубина", "ratio", self.common("ratio"), 0.01, 0.05, 1.0) if types == {"star"}
                       else None])
        # auto layout
        if types <= {"frame", "component", "instance"} and len(nodes) == 1:
            self.build_autolayout(n)
        if any(x.in_flow() for x in nodes):
            self.build_child_flow()
        self.sep()
        # layer
        self.section("Слой")
        self.row(self.combo(BLEND_TITLES, self.common("blend") or "normal", lambda v: self.apply("blend", v)),
                 self.num("", "opacity_pct", None if self.common("opacity") is None else self.common("opacity") * 100,
                          1, 0, 100, on_commit=lambda v: self.apply("opacity", v / 100),
                          on_live=lambda v: self.apply("opacity", v / 100, commit=False), suffix="%"))
        # type-specific
        if types <= {"text"}:
            self.build_text()
        if types <= {"sticky", "shape"}:
            self.build_box_text(types)
        if types == {"connector"}:
            self.build_connector()
        if types == {"stamp"}:
            self.section("Штамп")
            self.palette(tpl.STAMPS, self.common("glyph"), lambda g: self.apply("glyph", g), 24)
        if not types <= {"connector", "group", "stamp"}:
            self.build_paints("fills", "Заливка" if not types <= {"text"} else "Цвет текста")
        if not types <= {"group", "text", "stamp"}:
            self.build_paints("strokes", "Обводка")
        if not types <= {"connector", "group"}:
            self.build_effects()
        self.build_export()

    def _geom(self, key, v, commit=True):
        for n in self.nodes:
            setattr(n, key, v)
        if commit:
            self.ed.commit("Положение")
        else:
            self.ed.live_changed()

    def _size(self, key, v, commit=True):
        from .model import resize_node
        for n in self.nodes:
            w = v if key == "w" else n.w
            h = v if key == "h" else n.h
            if n.type == "text":
                if key == "w" and n.sizing == "auto_w":
                    n.sizing = "auto_h"
                elif key == "h":
                    n.sizing = "fixed"
            if n.type in FRAMELIKE and n.auto:
                if key == "w":
                    n.hug_w = False
                else:
                    n.hug_h = False
            if n.in_flow():
                if key == "w" and (n.grow if n.parent.layout == "row" else n.stretch):
                    n.grow = n.grow and n.parent.layout != "row"
                    n.stretch = n.stretch and n.parent.layout == "row"
            resize_node(n, w, h)
        if commit:
            self.ed.commit("Размер")
        else:
            self.ed.live_changed()

    def build_autolayout(self, n):
        th = self.ed.theme
        self.sep()
        if not n.auto:
            self.section("Автолейаут", plus=lambda: self.ed.add_autolayout(), plus_tip="Добавить автолейаут (⇧A)")
            return
        self.section("Автолейаут", plus=None)
        self.lay.addWidget(seg([("row", "row", "По горизонтали"), ("column", "column", "По вертикали"),
                                ("none", "no_layout", "Убрать автолейаут")], n.layout,
                               lambda v: self.ed.set_layout(v), True, th["text"], th["accent"]))
        pad = list(n.pad)
        self.grid([
            self.num("↔", "gap", n.gap, 1, 0, suffix="" if n.justify != "between" else ""),
            None,
            self.num("Поля ↔", "pad_h", pad[3] if pad[1] == pad[3] else None, 1, 0,
                     on_commit=lambda v: self._pad(v, None), on_live=lambda v: self._pad(v, None, False)),
            self.num("↕", "pad_v", pad[0] if pad[0] == pad[2] else None, 1, 0,
                     on_commit=lambda v: self._pad(None, v), on_live=lambda v: self._pad(None, v, False)),
        ])
        lbl = QLabel("Распределение")
        lbl.setObjectName("Muted")
        self.lay.addWidget(lbl)
        self.lay.addWidget(seg([("start", "Начало", ""), ("center", "Центр", ""), ("end", "Конец", ""),
                                ("between", "Между", "Равные промежутки")], n.justify,
                               lambda v: self.apply("justify", v)))
        lbl = QLabel("Выравнивание")
        lbl.setObjectName("Muted")
        self.lay.addWidget(lbl)
        self.lay.addWidget(seg([("start", "Начало", ""), ("center", "Центр", ""), ("end", "Конец", "")], n.align,
                               lambda v: self.apply("align", v)))
        self.row(self.check("Обнять ширину", n.hug_w, lambda v: self.apply("hug_w", v)),
                 self.check("Обнять высоту", n.hug_h, lambda v: self.apply("hug_h", v)))
        if n.layout == "row" and self.ed.doc.kind == "site":
            self.lay.addWidget(self.check("На телефоне — в колонку", n.stack, lambda v: self.apply("stack", v)))

    def _pad(self, h, v, commit=True):
        for n in self.nodes:
            p = list(n.pad)
            if h is not None:
                p[1] = p[3] = h
            if v is not None:
                p[0] = p[2] = v
            n.pad = p
        if commit:
            self.ed.commit("Поля")
        else:
            self.ed.live_changed()

    def build_child_flow(self):
        n = self.nodes[0]
        horiz = n.parent.layout == "row"
        self.section("В автолейауте")
        self.row(self.check("Заполнить ширину" if horiz else "Заполнить высоту", self.common("grow"),
                            lambda v: self.apply("grow", v)),
                 self.check("Заполнить высоту" if horiz else "Заполнить ширину", self.common("stretch"),
                            lambda v: self.apply("stretch", v)))
        self.lay.addWidget(self.check("Абсолютное положение", self.common("absolute"), lambda v: self.apply("absolute", v)))
        if self.ed.doc.kind == "site" and not horiz:
            self.grid([self.num("Макс. ширина", "max_w", self.common("max_w"), 1, 0)])

    def build_text(self):
        ed = self.ed
        n = self.nodes[0]
        self.sep()
        self.section("Текст")
        fc = QFontComboBox()
        fc.setCurrentFont(textlib.make_font(n.font, 13))
        fc.setEditable(False)
        fc.currentFontChanged.connect(lambda f: self.apply("font", f.family()))
        self.lay.addWidget(fc)
        self.row(self.combo([(w, t) for w, t in textlib.WEIGHTS], int(self.common("weight") or 400),
                            lambda v: self.apply("weight", v)),
                 self.num("", "size", self.common("size"), 1, 1, 1000))
        self.grid([self.num("Интерл.", "line_height", self.common("line_height"), 1, 0, 400, suffix="%"),
                   self.num("Трекинг", "letter", self.common("letter"), 0.1, -50, 200)])
        th = ed.theme
        self.lay.addWidget(seg([("left", "align_left", "Влево"), ("center", "align_hcenter", "По центру"),
                                ("right", "align_right", "Вправо")], self.common("talign"),
                               lambda v: self.apply("talign", v), True, th["text"], th["accent"]))
        self.lay.addWidget(seg([("auto_w", "Авто ширина", "Блок растёт по ширине"),
                                ("auto_h", "Авто высота", "Фиксированная ширина, высота по тексту"),
                                ("fixed", "Фикс.", "Фиксированный размер")], self.common("sizing"),
                               lambda v: self.apply("sizing", v)))
        self.row(self.check("Курсив", self.common("italic"), lambda v: self.apply("italic", v)),
                 self.check("Подчёркнутый", "underline" in (self.common("deco") or ""),
                            lambda v: self.apply("deco", "underline" if v else "")))
        if ed.doc.kind == "site":
            self.row(QLabel("Тег"), self.combo([("p", "Абзац"), ("h1", "Заголовок 1"), ("h2", "Заголовок 2"),
                                                ("h3", "Заголовок 3"), ("h4", "Заголовок 4")],
                                               self.common("tag") or "p", lambda v: self.apply("tag", v)), 1)

    def build_box_text(self, types):
        n = self.nodes[0]
        self.sep()
        if types == {"sticky"}:
            self.section("Стикер")
            self.palette(tpl.STICKY_COLORS, n.fills[0]["color"] if n.fills else "",
                         lambda c: self.apply("fills", [solid(c)]))
        else:
            self.section("Фигура")
            self.lay.addWidget(self.combo(SHAPE_KINDS, self.common("shape"), lambda v: self.apply("shape", v)))
            self.palette(tpl.BOARD_COLORS + [c for _, c in tpl.STICKY_COLORS[:6]],
                         n.fills[0]["color"] if n.fills else "", lambda c: self.apply("fills", [solid(c)]))
        self.section("Текст")
        self.row(self.num("", "size", self.common("size"), 1, 6, 400),
                 self.combo([("left", "Влево"), ("center", "По центру"), ("right", "Вправо")], self.common("talign"),
                            lambda v: self.apply("talign", v)))
        self.row(self.combo([(w, t) for w, t in textlib.WEIGHTS], int(self.common("weight") or 400),
                            lambda v: self.apply("weight", v)), 1)
        self.palette(tpl.BOARD_COLORS, self.common("text_color"), lambda c: self.apply("text_color", c), 18)

    def build_connector(self):
        n = self.nodes[0]
        th = self.ed.theme
        self.sep()
        self.section("Соединитель")
        self.lay.addWidget(seg([("elbow", "Ломаный", ""), ("straight", "Прямой", ""), ("curved", "Кривой", "")],
                               self.common("route"), lambda v: self.apply("route", v)))
        self.row(QLabel("Начало"), self.combo(ARROWS, self.common("arrow_start"), lambda v: self.apply("arrow_start", v)),
                 QLabel("Конец"), self.combo(ARROWS, self.common("arrow_end"), lambda v: self.apply("arrow_end", v)))
        self.grid([self.num("Толщина", "stroke_width", self.common("stroke_width"), 0.5, 0.5, 40),
                   self.num("Пунктир", "dash", self.common("dash"), 1, 0, 100)])
        self.palette(tpl.BOARD_COLORS, n.strokes[0]["color"] if n.strokes else "",
                     lambda c: self.apply("strokes", [solid(c)]), 18)
        lbl = QLabel("Двойной щелчок по линии — подпись. Концы можно перетащить на другие объекты.")
        lbl.setWordWrap(True)
        lbl.setObjectName("Muted")
        self.lay.addWidget(lbl)
        del th

    # ------------------------------------------------------------------ paints
    def build_paints(self, key, title):
        self.sep()
        nodes = self.nodes
        paints = getattr(nodes[0], key)
        same = all(getattr(x, key) == paints for x in nodes)

        def add():
            default = "#141413" if key == "strokes" else "#D9D9D9"
            for x in nodes:
                setattr(x, key, getattr(x, key) + [solid(default)])
                if key == "strokes" and x.stroke_width <= 0:
                    x.stroke_width = 1.0
            self.ed.commit(title)
        self.section(title, plus=add, plus_tip="Добавить")
        if not same:
            lbl = QLabel("Разные значения — нажмите + чтобы задать для всех")
            lbl.setObjectName("Muted")
            self.lay.addWidget(lbl)
            return
        for i, paint in enumerate(paints):
            self.paint_row(key, i, paint)
        if key == "strokes" and paints:
            t = nodes[0].type
            self.grid([self.num("Толщина", "stroke_width", self.common("stroke_width"), 0.5, 0, 400),
                       self.num("Пунктир", "dash", self.common("dash"), 1, 0, 400)])
            if t not in ("path", "connector", "text"):
                self.lay.addWidget(self.combo([("inside", "Внутри"), ("center", "По центру"), ("outside", "Снаружи")],
                                              self.common("stroke_align"), lambda v: self.apply("stroke_align", v)))
            if t == "path":
                self.row(QLabel("Начало"), self.combo(ARROWS, self.common("arrow_start"),
                                                      lambda v: self.apply("arrow_start", v)),
                         QLabel("Конец"), self.combo(ARROWS, self.common("arrow_end"),
                                                     lambda v: self.apply("arrow_end", v)))

    def _set_paint(self, key, i, fn, commit=True, label="Цвет"):
        for x in self.nodes:
            lst = copy.deepcopy(getattr(x, key))
            if i < len(lst):
                fn(lst[i])
                setattr(x, key, lst)
                self.ed.note_override(x, key)
        if commit:
            self.ed.commit(label)
        else:
            self.ed.live_changed()

    def paint_row(self, key, i, paint):
        th = self.ed.theme
        t = paint.get("type", "solid")
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        if t == "solid":
            sw = Swatch(paint.get("color", "#000000"))
            sw.picked.connect(lambda c: self._set_paint(key, i, lambda p: p.update(color=c)))
            sw.live.connect(lambda c: self._set_paint(key, i, lambda p: p.update(color=c), False))
            h.addWidget(sw)
            hexe = QLineEdit(paint.get("color", "#000000").upper().lstrip("#"))
            hexe.setObjectName("Field")
            hexe.setMaximumWidth(72)

            def set_hex(e=hexe):
                v = e.text().strip()
                v = v if v.startswith("#") else "#" + v
                if QColor(v).isValid():
                    self._set_paint(key, i, lambda p: p.update(color=QColor(v).name().upper()))
            hexe.editingFinished.connect(set_hex)
            h.addWidget(hexe)
        elif t in ("linear", "radial"):
            stops = paint.get("stops") or [[0, "#FFFFFF"], [1, "#000000"]]
            for si in (0, len(stops) - 1):
                sw = Swatch(stops[si][1])

                def pick(c, si=si, commit=True):
                    self._set_paint(key, i, lambda p: p.__setitem__("stops", [
                        [pos, c if k == si else col] for k, (pos, col) in enumerate(p.get("stops") or stops)]), commit)
                sw.picked.connect(pick)
                sw.live.connect(lambda c, f=pick: f(c, commit=False))
                h.addWidget(sw)
            if t == "linear":
                f = self.num("∠", f"{key}{i}_angle", paint.get("angle", 90), 1, -360, 360,
                             on_commit=lambda v: self._set_paint(key, i, lambda p: p.update(angle=v)),
                             on_live=lambda v: self._set_paint(key, i, lambda p: p.update(angle=v), False), suffix="°")
                h.addWidget(f)
        elif t == "image":
            b = QPushButton("Заменить…")
            b.clicked.connect(lambda: self._pick_image(key, i))
            h.addWidget(b)
            h.addWidget(self.combo([("fill", "Заполнить"), ("fit", "Вписать"), ("tile", "Плитка"), ("stretch", "Растянуть")],
                                   paint.get("mode", "fill"),
                                   lambda v: self._set_paint(key, i, lambda p: p.update(mode=v))))
        op = self.num("", f"{key}{i}_op", paint.get("opacity", 1.0) * 100, 1, 0, 100,
                      on_commit=lambda v: self._set_paint(key, i, lambda p: p.update(opacity=v / 100)),
                      on_live=lambda v: self._set_paint(key, i, lambda p: p.update(opacity=v / 100), False), suffix="%")
        op.setMaximumWidth(64)
        h.addWidget(op, 1)
        vis = QToolButton()
        vis.setIcon(icons.icon("eye" if paint.get("visible", True) else "eye_off", th["text"], th["accent"]))
        vis.setIconSize(QSize(14, 14))
        vis.clicked.connect(lambda: self._set_paint(key, i, lambda p: p.update(visible=not p.get("visible", True))))
        h.addWidget(vis)
        rm = QToolButton()
        rm.setIcon(icons.icon("minus", th["text"], th["accent"]))
        rm.setIconSize(QSize(14, 14))
        rm.clicked.connect(lambda: self._remove_paint(key, i))
        h.addWidget(rm)
        self.lay.addWidget(w)
        if key == "fills":
            self.lay.addWidget(self.combo(PAINT_TYPES, t, lambda v: self._paint_type(key, i, v)))

    def _remove_paint(self, key, i):
        for x in self.nodes:
            lst = list(getattr(x, key))
            if i < len(lst):
                lst.pop(i)
                setattr(x, key, lst)
                self.ed.note_override(x, key)
        self.ed.commit("Удалить заливку")

    def _paint_type(self, key, i, t):
        if t == "image":
            self._pick_image(key, i)
            return
        cur = getattr(self.nodes[0], key)[i]
        color = cur.get("color", "#D97757")
        if t == "solid":
            new = solid(cur.get("stops", [[0, color]])[0][1] if "stops" in cur else color)
        else:
            stops = cur.get("stops") or [[0, color if cur.get("type") == "solid" else "#F2C3AE"], [1, "#141413"]]
            new = {"type": t, "stops": stops, "angle": cur.get("angle", 90.0), "opacity": cur.get("opacity", 1.0)}
        self._set_paint(key, i, lambda p: (p.clear(), p.update(new)))

    def _pick_image(self, key, i):
        path, _ = QFileDialog.getOpenFileName(self, "Изображение", self.ed.settings.get("last_dir", ""),
                                              "Изображения (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.tiff)")
        if not path:
            return
        try:
            data = open(path, "rb").read()
        except OSError:
            return
        ref = self.ed.doc.add_image(data)
        self._set_paint(key, i, lambda p: (p.clear(), p.update({"type": "image", "ref": ref, "mode": "fill",
                                                                 "opacity": 1.0})), label="Изображение")

    # ------------------------------------------------------------------ effects
    def build_effects(self):
        self.sep()
        nodes = self.nodes

        def add():
            for x in nodes:
                x.effects = x.effects + [{"type": "shadow", "x": 0, "y": 4, "blur": 12, "spread": 0,
                                          "color": "#000000", "opacity": 0.2}]
            self.ed.commit("Эффект")
        self.section("Эффекты", plus=add, plus_tip="Добавить тень")
        effects = nodes[0].effects
        if not all(x.effects == effects for x in nodes):
            return
        th = self.ed.theme
        for i, e in enumerate(effects):
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(4)
            h.addWidget(self.combo([("shadow", "Тень"), ("inner", "Внутренняя тень")], e.get("type", "shadow"),
                                   lambda v, i=i: self._set_effect(i, "type", v)), 1)
            sw = Swatch(e.get("color", "#000000"))
            sw.picked.connect(lambda c, i=i: self._set_effect(i, "color", c))
            h.addWidget(sw)
            rm = QToolButton()
            rm.setIcon(icons.icon("minus", th["text"], th["accent"]))
            rm.setIconSize(QSize(14, 14))
            rm.clicked.connect(lambda _=False, i=i: self._remove_effect(i))
            h.addWidget(rm)
            self.lay.addWidget(w)
            self.grid([self.num("X", f"e{i}x", e.get("x", 0), 1, on_commit=lambda v, i=i: self._set_effect(i, "x", v),
                                on_live=lambda v, i=i: self._set_effect(i, "x", v, False)),
                       self.num("Y", f"e{i}y", e.get("y", 4), 1, on_commit=lambda v, i=i: self._set_effect(i, "y", v),
                                on_live=lambda v, i=i: self._set_effect(i, "y", v, False)),
                       self.num("Размытие", f"e{i}b", e.get("blur", 12), 1, 0, 400,
                                on_commit=lambda v, i=i: self._set_effect(i, "blur", v),
                                on_live=lambda v, i=i: self._set_effect(i, "blur", v, False)),
                       self.num("Непрозр.", f"e{i}o", e.get("opacity", 0.2) * 100, 1, 0, 100, suffix="%",
                                on_commit=lambda v, i=i: self._set_effect(i, "opacity", v / 100),
                                on_live=lambda v, i=i: self._set_effect(i, "opacity", v / 100, False))])

    def _set_effect(self, i, k, v, commit=True):
        for x in self.nodes:
            lst = copy.deepcopy(x.effects)
            if i < len(lst):
                lst[i][k] = v
                x.effects = lst
        self.ed.renderer.drop_caches()
        if commit:
            self.ed.commit("Эффект")
        else:
            self.ed.live_changed()

    def _remove_effect(self, i):
        for x in self.nodes:
            lst = list(x.effects)
            if i < len(lst):
                lst.pop(i)
                x.effects = lst
        self.ed.commit("Эффект")

    # ------------------------------------------------------------------ export
    def build_export(self):
        self.sep()
        self.section("Экспорт")
        st = self.ed.settings
        fmt = self.combo([(f, f) for f in ("PNG", "JPG", "WEBP", "SVG", "PDF")], st.get("export_format", "PNG"),
                         lambda v: st.__setitem__("export_format", v))
        scale = self.combo([(s, f"{s}×") for s in (0.5, 1, 2, 3, 4)], st.get("export_scale", 2),
                           lambda v: st.__setitem__("export_scale", v))
        self.row(scale, fmt)
        n = len(self.nodes)
        self.lay.addWidget(self.button("Экспортировать" + (f" ({n})" if n > 1 else ""),
                                       lambda: self.ed.export_selection()))

    # ------------------------------------------------------------------ prototype
    def build_prototype(self):
        ed = self.ed
        frames = [c for c in ed.page.children if c.type in ("frame", "component")]
        self.section("Прототип")
        if not self.nodes:
            lbl = QLabel("Выделите объект и выберите, к какому фрейму переходить по нажатию. "
                         "«Презентовать» открывает прототип в окне.")
            lbl.setWordWrap(True)
            lbl.setObjectName("Muted")
            self.lay.addWidget(lbl)
            self.lay.addWidget(self.button("▶  Презентовать", ed.present, accent=True))
            return
        n = self.nodes[0]
        link = n.link or {}
        lbl = QLabel("При нажатии — перейти к")
        lbl.setObjectName("Muted")
        self.lay.addWidget(lbl)
        opts = [("", "— нет —"), ("__back", "← Назад")] + [(f.id, f.name) for f in frames if f is not n]
        self.lay.addWidget(self.combo(opts, link.get("target", ""), self._set_link_target))
        if link.get("target"):
            lbl = QLabel("Анимация")
            lbl.setObjectName("Muted")
            self.lay.addWidget(lbl)
            self.lay.addWidget(self.combo(TRANSITIONS, link.get("transition", "dissolve"),
                                          lambda v: self.apply("link", dict(link, transition=v))))
        self.sep()
        self.lay.addWidget(self.button("▶  Презентовать", ed.present, accent=True))

    def _set_link_target(self, target):
        if not target:
            self.apply("link", {})
        else:
            for n in self.nodes:
                cur = dict(n.link or {})
                cur["target"] = target
                cur.setdefault("transition", "dissolve")
                n.link = cur
            self.ed.commit("Связь")

    # ------------------------------------------------------------------ site
    def build_site(self):
        ed = self.ed
        doc = ed.doc
        if not self.nodes:
            self.section("Сайт")
            name = QLineEdit(doc.site.get("name", ""))
            name.setObjectName("Field")
            name.setPlaceholderText("Название сайта")
            name.editingFinished.connect(lambda e=name: (doc.site.__setitem__("name", e.text()), ed.commit("Сайт")))
            self.lay.addWidget(QLabel("Название (заголовок вкладки)"))
            self.lay.addWidget(name)
            self.section("Страница")
            pn = QLineEdit(ed.page.name)
            pn.setObjectName("Field")
            pn.editingFinished.connect(lambda e=pn: ed.rename_page(ed.page, e.text()))
            self.lay.addWidget(pn)
            root = doc.site_root(ed.page)
            if root is not None:
                sw = Swatch(root.fills[0]["color"] if root.fills and root.fills[0].get("type") == "solid" else "#FFFFFF")
                sw.picked.connect(lambda c: self.apply("fills", [solid(c)], nodes=[root]))
                self.row(QLabel("Фон страницы"), sw, 1)
            self.section("Публикация")
            lbl = QLabel("Сайт экспортируется в папку с HTML и CSS — её можно открыть в браузере или выложить "
                         "на любой хостинг.")
            lbl.setWordWrap(True)
            lbl.setObjectName("Muted")
            self.lay.addWidget(lbl)
            self.lay.addWidget(self.button("Предпросмотр в браузере", ed.preview_site, accent=True))
            self.lay.addWidget(self.button("Экспортировать сайт…", ed.export_site))
            return
        n = self.nodes[0]
        self.section("Ссылка")
        link = n.link or {}
        mode = "url" if n.href else ("page" if link.get("target") else "none")
        self.lay.addWidget(seg([("none", "Нет", ""), ("page", "Страница", ""), ("url", "Адрес", "")], mode,
                               self._site_link_mode))
        if mode == "page":
            self.lay.addWidget(self.combo([(p.id, p.name) for p in doc.pages], link.get("target"),
                                          lambda v: (self.apply("href", "", commit=False), self.apply("link", {"target": v}))))
        elif mode == "url":
            e = QLineEdit(n.href)
            e.setObjectName("Field")
            e.setPlaceholderText("https://…, mailto:…, #раздел")
            e.editingFinished.connect(lambda e=e: self.apply("href", e.text().strip() or "#"))
            self.lay.addWidget(e)
        self.sep()
        self.section("При наведении")
        hv = dict(n.hover or {})
        self.grid([self.num("Непрозр.", "hv_op", hv.get("opacity", 1) * 100, 1, 0, 100, suffix="%",
                            on_commit=lambda v: self._hover("opacity", v / 100), on_live=lambda v: None),
                   self.num("Масштаб", "hv_sc", hv.get("scale", 1) * 100, 1, 50, 200, suffix="%",
                            on_commit=lambda v: self._hover("scale", v / 100), on_live=lambda v: None)])
        sw = Swatch(hv.get("fill") or "#D97757")
        sw.picked.connect(lambda c: self._hover("fill", c))
        self.row(self.check("Цвет", bool(hv.get("fill")), lambda v: self._hover("fill", sw.color if v else None)), sw, 1)
        lbl = QLabel("Эффекты наведения видны в предпросмотре и на экспортированном сайте.")
        lbl.setWordWrap(True)
        lbl.setObjectName("Muted")
        self.lay.addWidget(lbl)

    def _site_link_mode(self, mode):
        for n in self.nodes:
            if mode == "none":
                n.href, n.link = "", {}
            elif mode == "url":
                n.href, n.link = n.href or "https://", {}
            else:
                n.href = ""
                n.link = {"target": self.ed.doc.pages[0].id}
        self.ed.commit("Ссылка")

    def _hover(self, k, v):
        for n in self.nodes:
            hv = dict(n.hover or {})
            if v is None or (k in ("opacity", "scale") and abs(v - 1) < 1e-6):
                hv.pop(k, None)
            else:
                hv[k] = v
            n.hover = hv
        self.ed.commit("Наведение")

    # ------------------------------------------------------------------ slides
    def build_slide(self):
        ed = self.ed
        slide = ed.current_slide()
        self.section("Тема")
        cur = ed.doc.theme.get("name", tpl.THEMES[0]["name"])
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(6)
        for i, t in enumerate(tpl.THEMES):
            b = QToolButton()
            b.setFixedSize(QSize(72, 46))
            border = ed.theme["accent"] if t["name"] == cur else "rgba(0,0,0,0.15)"
            b.setStyleSheet(f"QToolButton {{ background: {t['bg']}; color: {t['text']}; border: 2px solid {border}; "
                            f"border-radius: 8px; font-family: Georgia; font-size: 15px; }}")
            b.setText("Аа")
            b.setToolTip(t["name"])
            b.clicked.connect(lambda _=False, t=t: ed.apply_theme(t))
            g.addWidget(b, i // 3, i % 3)
        self.lay.addWidget(w)
        if slide is None:
            return
        self.sep()
        self.section("Слайд")
        self.lay.addWidget(QLabel("Переход"))
        self.lay.addWidget(self.combo(TRANSITIONS, slide.transition,
                                      lambda v: self.apply("transition", v, nodes=[slide])))
        sw = Swatch(slide.fills[0]["color"] if slide.fills and slide.fills[0].get("type") == "solid" else "#FFFFFF")
        sw.picked.connect(lambda c: self.apply("fills", [solid(c)], nodes=[slide]))
        self.row(QLabel("Фон"), sw, 1)
        self.lay.addWidget(self.button("Применить тему к слайду заново", lambda: ed.apply_theme(ed.doc.theme, [slide])))
        self.sep()
        self.lay.addWidget(self.button("▶  Показ слайдов", ed.present, accent=True))
        self.lay.addWidget(self.button("Режим докладчика", ed.present_presenter))
        self.lay.addWidget(self.button("Экспорт в PDF…", ed.export_pdf_all))
