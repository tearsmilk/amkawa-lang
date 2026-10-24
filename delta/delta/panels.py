"""Docks: colour (HSV square, hue / alpha bars, hex, recent colours), brushes (presets + settings),
layers (thumbnails, visibility, lock, alpha lock, clipping, blend mode, opacity)."""
from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
    QSizePolicy, QSlider, QToolButton, QVBoxLayout, QWidget,
)

from . import icons
from .brushes import PRESETS, Brush
from .model import BLEND_MODES


def checker(p, rect, cell=5):
    p.save()
    p.setClipRect(rect)
    p.fillRect(rect, QColor("#FFFFFF"))
    y = rect.top()
    while y < rect.bottom():
        x = rect.left() + (((y - rect.top()) // cell) % 2) * cell
        while x < rect.right():
            p.fillRect(QRectF(x, y, cell, cell), QColor("#D7D3C8"))
            x += cell * 2
        y += cell
    p.restore()


class SVSquare(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.h, self.s, self.v = 0.0, 1.0, 1.0
        self.setMinimumSize(150, 120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, e):
        p = QPainter(self)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.fillRect(r, QColor.fromHsvF(self.h, 1, 1))
        g = QLinearGradient(r.topLeft(), r.topRight())
        g.setColorAt(0, QColor(255, 255, 255, 255))
        g.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(r, g)
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, QColor(0, 0, 0, 0))
        g.setColorAt(1, QColor(0, 0, 0, 255))
        p.fillRect(r, g)
        x = r.left() + self.s * r.width()
        y = r.top() + (1 - self.v) * r.height()
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#FFFFFF" if self.v < 0.6 else "#141413"), 1.5))
        p.drawEllipse(QPointF(x, y), 5, 5)

    def _pick(self, pos):
        self.s = min(1.0, max(0.0, pos.x() / max(1, self.width())))
        self.v = 1 - min(1.0, max(0.0, pos.y() / max(1, self.height())))
        self.update()
        self.changed.emit()

    def mousePressEvent(self, e):
        self._pick(e.position())

    def mouseMoveEvent(self, e):
        if e.buttons():
            self._pick(e.position())


class Bar(QWidget):
    """Horizontal hue or alpha slider."""
    changed = Signal()

    def __init__(self, kind):
        super().__init__()
        self.kind = kind
        self.value = 0.0
        self.color = QColor("#D97757")
        self.setFixedHeight(14)

    def paintEvent(self, e):
        p = QPainter(self)
        r = QRectF(self.rect()).adjusted(0, 2, 0, -2)
        g = QLinearGradient(r.topLeft(), r.topRight())
        if self.kind == "hue":
            for i in range(7):
                g.setColorAt(i / 6, QColor.fromHsvF((i / 6) % 1.0, 1, 1))
        else:
            checker(p, r, 4)
            c0, c1 = QColor(self.color), QColor(self.color)
            c0.setAlpha(0)
            c1.setAlpha(255)
            g.setColorAt(0, c0)
            g.setColorAt(1, c1)
        p.fillRect(r, g)
        x = r.left() + self.value * r.width()
        p.setPen(QPen(QColor("#141413"), 1))
        p.setBrush(QColor("#FFFFFF"))
        p.drawRect(QRectF(x - 2, 0, 4, self.height() - 1))

    def _pick(self, pos):
        self.value = min(1.0, max(0.0, pos.x() / max(1, self.width())))
        self.update()
        self.changed.emit()

    def mousePressEvent(self, e):
        self._pick(e.position())

    def mouseMoveEvent(self, e):
        if e.buttons():
            self._pick(e.position())


class Swatches(QWidget):
    """Primary / secondary colours + recent colours."""
    swap = Signal()
    select = Signal(bool)
    picked = Signal(QColor, bool)

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.recent = []
        self.setFixedHeight(46)

    def remember(self, color):
        argb = QColor(color).rgba()
        self.recent = [argb] + [c for c in self.recent if c != argb][:17]
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        c = self.win.theme
        back, front = QRect(18, 16, 26, 26), QRect(2, 2, 26, 26)
        for rect, col in ((back, self.win.secondary), (front, self.win.primary)):
            checker(p, rect, 4)
            p.fillRect(rect, col)
            p.setPen(QPen(QColor(c["border"]), 1))
            p.drawRect(rect.adjusted(0, 0, -1, -1))
        p.setPen(QColor(c["muted"]))
        p.drawText(QRect(30, 0, 18, 14), Qt.AlignCenter, "⇄")
        for i, argb in enumerate(self.recent):
            r = QRect(56 + (i % 9) * 19, 4 + (i // 9) * 20, 16, 16)
            p.fillRect(r, QColor.fromRgba(argb))
            p.setPen(QPen(QColor(c["border"]), 1))
            p.drawRect(r.adjusted(0, 0, -1, -1))

    def mousePressEvent(self, e):
        pos = e.position().toPoint()
        if pos.x() > 30 and pos.x() < 50 and pos.y() < 14:
            self.swap.emit()
            return
        if pos.x() < 50:
            self.select.emit(not QRect(2, 2, 26, 26).contains(pos))
            return
        i = ((pos.y() - 4) // 20) * 9 + (pos.x() - 56) // 19
        if 0 <= i < len(self.recent) and pos.x() >= 56:
            self.picked.emit(QColor.fromRgba(self.recent[i]), e.button() == Qt.RightButton)


class ColorPanel(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)
        self.sv = SVSquare()
        self.sv.setMinimumHeight(140)
        lay.addWidget(self.sv, 1)
        self.hue = Bar("hue")
        self.alpha = Bar("alpha")
        lay.addWidget(self.hue)
        lay.addWidget(self.alpha)
        row = QHBoxLayout()
        self.hex = QLineEdit()
        self.hex.setMaxLength(9)
        self.hex.editingFinished.connect(self._hex)
        row.addWidget(self.hex, 1)
        self.info = QLabel()
        self.info.setObjectName("Muted")
        row.addWidget(self.info)
        lay.addLayout(row)
        self.swatches = Swatches(win)
        self.swatches.swap.connect(win.swap_colors)
        self.swatches.select.connect(lambda sec: self.show_color(win.secondary if sec else win.primary, sec))
        self.swatches.picked.connect(lambda c, sec: win.set_color(c, sec))
        lay.addWidget(self.swatches)
        self.secondary = False
        self.sv.changed.connect(self._picker)
        self.hue.changed.connect(self._picker)
        self.alpha.changed.connect(self._picker)

    def show_color(self, color, secondary=False):
        self.secondary = secondary
        h, s, v, a = QColor(color).getHsvF()
        if h >= 0:
            self.sv.h = self.hue.value = h
        self.sv.s, self.sv.v, self.alpha.value = s, v, a
        self.alpha.color = QColor(color)
        for w in (self.sv, self.hue, self.alpha, self.swatches):
            w.update()
        self._text(QColor(color))

    def _text(self, col):
        self.hex.setText(col.name().upper() if col.alpha() == 255 else "#" + f"{col.rgba() & 0xFFFFFF:06X}{col.alpha():02X}")
        self.info.setText(f"{'второй' if self.secondary else 'основной'} · {round(col.alpha() / 2.55)}%")

    def _picker(self):
        self.sv.h = self.hue.value
        col = QColor.fromHsvF(self.hue.value, self.sv.s, self.sv.v, self.alpha.value)
        self.sv.update()
        self.alpha.color = col
        self.alpha.update()
        self.win.set_color(col, self.secondary, from_picker=True)
        self._text(col)

    def _hex(self):
        t = self.hex.text().strip().lstrip("#")
        col = QColor()
        if len(t) in (3, 6):
            col = QColor("#" + (t if len(t) == 6 else "".join(ch * 2 for ch in t)))
        elif len(t) == 8:
            col = QColor("#" + t[:6])
            col.setAlpha(int(t[6:], 16))
        if col.isValid():
            self.win.set_color(col, self.secondary)


# ====================================================================== brushes
class BrushPanel(QWidget):
    changed = Signal()

    SLIDERS = [("size", "Размер", 1, 500, 1), ("opacity", "Непрозрачность", 1, 100, 100), ("flow", "Поток", 1, 100, 100),
               ("hardness", "Жёсткость", 0, 100, 100), ("spacing", "Интервал", 1, 100, 100),
               ("smoothing", "Сглаживание", 0, 100, 100), ("grain", "Зерно", 0, 100, 100),
               ("scatter", "Разброс", 0, 100, 100), ("min_size", "Мин. размер", 0, 100, 100)]

    def __init__(self, win):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(4)
        self.list = QListWidget()
        self.list.setObjectName("BrushList")
        self.list.setIconSize(QSize(18, 18))
        self.list.currentRowChanged.connect(self._select)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        lay.addWidget(self.list, 1)
        form = QFormLayout()
        form.setVerticalSpacing(2)
        form.setHorizontalSpacing(8)
        self.sliders = {}
        for key, label, lo, hi, scale in self.SLIDERS:
            s = QSlider(Qt.Horizontal)
            s.setRange(lo, hi)
            val = QLabel()
            val.setObjectName("Muted")
            val.setFixedWidth(34)
            row = QHBoxLayout()
            row.addWidget(s, 1)
            row.addWidget(val)
            s.valueChanged.connect(lambda v, k=key, sc=scale, lab=val: self._slider(k, v, sc, lab))
            form.addRow(label, row)
            self.sliders[key] = (s, val, scale)
        lay.addLayout(form)
        prow = QHBoxLayout()
        self.p_size = QCheckBox("Нажим → размер")
        self.p_opacity = QCheckBox("Нажим → прозрачн.")
        self.p_size.toggled.connect(lambda v: self._set("pressure_size", v))
        self.p_opacity.toggled.connect(lambda v: self._set("pressure_opacity", v))
        prow.addWidget(self.p_size)
        prow.addWidget(self.p_opacity)
        lay.addLayout(prow)
        self._loading = False
        self.brushes = []
        self.load()

    def load(self):
        saved = self.win.settings.get("brushes") or {}
        self.brushes = []
        for b in PRESETS:
            d = saved.get(b.name)
            self.brushes.append(Brush.from_dict({**b.to_dict(), **d}) if d else Brush.from_dict(b.to_dict()))
        for name, d in saved.items():
            if not any(b.name == name for b in self.brushes):
                self.brushes.append(Brush.from_dict(d))
        self.list.clear()
        for b in self.brushes:
            item = QListWidgetItem(f"{b.icon}  {b.name}")
            item.setToolTip({"paint": "Рисование", "erase": "Ластик", "smudge": "Размазывание", "blur": "Размытие"}[b.mode])
            self.list.addItem(item)
        current = self.win.settings.get("brush", "Карандаш")
        idx = next((i for i, b in enumerate(self.brushes) if b.name == current), 0)
        self.list.setCurrentRow(idx)

    def by_name(self, name):
        return next((b for b in self.brushes if b.name == name), None)

    def _select(self, row):
        if row < 0:
            return
        b = self.brushes[row]
        if b.mode == "erase":
            self.win.eraser_brush = b
            if self.win.tool.key != "eraser":
                self.win.select_tool("eraser", keep_brush=True)
        else:
            self.win.brush = b
            self.win.settings["brush"] = b.name
            if self.win.tool.key not in ("brush",):
                self.win.select_tool("brush", keep_brush=True)
        self.show_brush(b)

    def show_brush(self, b):
        self._loading = True
        for key, (s, val, scale) in self.sliders.items():
            v = getattr(b, key)
            s.setValue(int(round(v * scale if scale != 1 else v)))
            val.setText(f"{int(v)} px" if key == "size" else f"{int(round(v * 100))}%")
        self.p_size.setChecked(b.pressure_size)
        self.p_opacity.setChecked(b.pressure_opacity)
        self._loading = False

    def current(self):
        row = self.list.currentRow()
        return self.brushes[row] if 0 <= row < len(self.brushes) else None

    def _slider(self, key, v, scale, label):
        value = v / scale if scale != 1 else float(v)
        label.setText(f"{v} px" if key == "size" else f"{int(round(value * 100))}%")
        self._set(key, value)

    def _set(self, key, value):
        if self._loading:
            return
        b = self.current()
        if b is None:
            return
        setattr(b, key, value)
        saved = self.win.settings.setdefault("brushes", {})
        saved[b.name] = b.to_dict()
        self.win.settings.save()
        self.changed.emit()

    def set_size(self, size):
        b = self.win.eraser_brush if self.win.tool.key == "eraser" else self.win.brush
        b.size = max(1.0, min(500.0, size))
        if b is self.current():
            self.show_brush(b)
        saved = self.win.settings.setdefault("brushes", {})
        saved[b.name] = b.to_dict()
        self.win.settings.save()

    def _menu(self, pos):
        row = self.list.indexAt(pos).row()
        if row < 0:
            return
        b = self.brushes[row]
        m = QMenu(self)
        m.addAction("Сбросить настройки кисти", lambda: self._reset(b))
        m.exec(self.list.viewport().mapToGlobal(pos))

    def _reset(self, b):
        saved = self.win.settings.get("brushes") or {}
        saved.pop(b.name, None)
        self.win.settings.save()
        name = self.win.settings.get("brush")
        self.load()
        self.win.settings["brush"] = name


# ====================================================================== layers
class LayerRow(QWidget):
    def __init__(self, panel, layer):
        super().__init__()
        self.panel = panel
        self.layer = layer
        win = panel.win
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(6)
        c = win.theme
        self.eye = QToolButton()
        self.eye.setIcon(icons.icon("eye", c["text"] if layer.visible else c["faint"], c["accent"]))
        self.eye.setIconSize(QSize(16, 16))
        self.eye.setToolTip("Показать / скрыть")
        self.eye.clicked.connect(lambda: win.toggle_layer(layer, "visible"))
        lay.addWidget(self.eye)
        if layer.clip:
            arrow = QLabel("↳")
            arrow.setObjectName("Muted")
            lay.addWidget(arrow)
        self.thumb = QLabel()
        self.thumb.setFixedSize(40, 30)
        self.thumb.setPixmap(panel.thumbnail(layer))
        lay.addWidget(self.thumb)
        col = QVBoxLayout()
        col.setSpacing(0)
        name = QLabel(layer.name)
        col.addWidget(name)
        blend = dict((k, n) for k, n, _m in BLEND_MODES).get(layer.blend, "")
        flags = []
        if layer.alpha_lock:
            flags.append("α")
        if layer.animated():
            flags.append("◆ анимация")
        meta = QLabel(f"{blend} · {round(layer.opacity * 100)}%" + ("  " + " ".join(flags) if flags else ""))
        meta.setObjectName("Muted")
        col.addWidget(meta)
        lay.addLayout(col, 1)
        if layer.locked:
            lk = QToolButton()
            lk.setIcon(icons.icon("lock", c["muted"], c["accent"]))
            lk.setIconSize(QSize(14, 14))
            lk.clicked.connect(lambda: win.toggle_layer(layer, "locked"))
            lay.addWidget(lk)


class LayersPanel(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(4)
        top = QHBoxLayout()
        self.blend = QComboBox()
        for key, label, _m in BLEND_MODES:
            self.blend.addItem(label, key)
        self.blend.activated.connect(lambda _i: win.set_layer_prop("blend", self.blend.currentData()))
        top.addWidget(self.blend, 1)
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(0, 100)
        self.opacity.setFixedWidth(90)
        self.opacity.sliderReleased.connect(lambda: win.set_layer_prop("opacity", self.opacity.value() / 100))
        self.op_label = QLabel()
        self.op_label.setObjectName("Muted")
        self.opacity.valueChanged.connect(lambda v: self.op_label.setText(f"{v}%"))
        top.addWidget(self.opacity)
        top.addWidget(self.op_label)
        lay.addLayout(top)
        flags = QHBoxLayout()
        self.alpha = QCheckBox("Защитить прозрачность")
        self.alpha.toggled.connect(lambda v: win.set_layer_prop("alpha_lock", v))
        self.clip = QCheckBox("Обтравка")
        self.clip.setToolTip("Обтравочная маска: слой виден только там, где есть пиксели слоя ниже")
        self.clip.toggled.connect(lambda v: win.set_layer_prop("clip", v))
        flags.addWidget(self.alpha)
        flags.addWidget(self.clip)
        lay.addLayout(flags)
        self.list = QListWidget()
        self.list.setObjectName("LayerList")
        self.list.currentRowChanged.connect(self._select)
        self.list.itemDoubleClicked.connect(lambda _i: win.rename_layer())
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        row.setSpacing(2)
        for text, tip, fn in (("＋", "Новый слой (⇧⌘N)", win.new_layer), ("⧉", "Дублировать", win.duplicate_layer),
                              ("⤓", "Объединить с нижним (⌘E)", win.merge_down), ("↑", "Выше", lambda: win.move_layer(1)),
                              ("↓", "Ниже", lambda: win.move_layer(-1)), ("🗑", "Удалить", win.delete_layer)):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self._updating = False

    def thumbnail(self, layer):
        img = layer.image.scaled(80, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pix = QPixmap(80, 60)
        pix.fill(QColor(self.win.theme["checker_a"]))
        p = QPainter(pix)
        p.drawImage((80 - img.width()) // 2, (60 - img.height()) // 2, img)
        p.setPen(QColor(self.win.theme["border"]))
        p.drawRect(0, 0, 79, 59)
        p.end()
        pix.setDevicePixelRatio(2)
        return pix

    def refresh(self):
        doc = self.win.doc
        self._updating = True
        self.list.clear()
        if doc is None:
            self._updating = False
            return
        rows = list(reversed(doc.layers))
        for layer in rows:
            item = QListWidgetItem()
            item.setSizeHint(QSize(100, 40))
            self.list.addItem(item)
            self.list.setItemWidget(item, LayerRow(self, layer))
        self.list.setCurrentRow(rows.index(doc.current))
        cur = doc.current
        self.blend.setCurrentIndex(max(0, self.blend.findData(cur.blend)))
        self.opacity.setValue(round(cur.opacity * 100))
        self.op_label.setText(f"{round(cur.opacity * 100)}%")
        for box, val in ((self.alpha, cur.alpha_lock), (self.clip, cur.clip)):
            box.blockSignals(True)
            box.setChecked(val)
            box.blockSignals(False)
        self._updating = False

    def _select(self, row):
        if self._updating or row < 0 or self.win.doc is None:
            return
        rows = list(reversed(self.win.doc.layers))
        self.win.doc.current = rows[row]
        self.refresh()
        self.win.timeline.update_view()

    def _menu(self, pos):
        w = self.win
        m = QMenu(self)
        m.addAction("Переименовать…", w.rename_layer)
        m.addAction("Новый слой", w.new_layer)
        m.addAction("Дублировать", w.duplicate_layer)
        m.addAction("Объединить с нижним", w.merge_down)
        m.addAction("Очистить слой", w.clear_layer)
        m.addAction("Заблокировать / разблокировать", lambda: w.toggle_layer(w.doc.current, "locked"))
        m.addSeparator()
        m.addAction("Удалить слой", w.delete_layer)
        m.exec(self.list.viewport().mapToGlobal(pos))


