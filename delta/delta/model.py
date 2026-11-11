"""Document model: raster layers (blend mode, opacity, alpha lock, clipping mask) and an After Effects-like
composition — every layer has keyframed transform properties (position, scale, rotation, opacity) and an
in / out range on the timeline.

Layer images are canvas-sized QImage (ARGB32_Premultiplied). Undo snapshots keep shallow QImage copies
(Qt implicit sharing); painting on the live image detaches it, so a snapshot costs nothing until a layer
actually changes.
"""
import copy
import itertools
import math
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QTransform

FMT = QImage.Format_ARGB32_Premultiplied
_ids = itertools.count(1)

BLEND_MODES = [
    ("normal", "Обычный", QPainter.CompositionMode_SourceOver), ("multiply", "Умножение", QPainter.CompositionMode_Multiply),
    ("screen", "Экран", QPainter.CompositionMode_Screen), ("overlay", "Перекрытие", QPainter.CompositionMode_Overlay),
    ("darken", "Затемнение", QPainter.CompositionMode_Darken), ("lighten", "Замена светлым", QPainter.CompositionMode_Lighten),
    ("dodge", "Осветление основы", QPainter.CompositionMode_ColorDodge),
    ("burn", "Затемнение основы", QPainter.CompositionMode_ColorBurn),
    ("hard", "Жёсткий свет", QPainter.CompositionMode_HardLight), ("soft", "Мягкий свет", QPainter.CompositionMode_SoftLight),
    ("difference", "Разница", QPainter.CompositionMode_Difference), ("exclusion", "Исключение", QPainter.CompositionMode_Exclusion),
    ("add", "Добавление", QPainter.CompositionMode_Plus),
]
BLEND_QT = {k: m for k, _n, m in BLEND_MODES}
PROPS = [("x", "Позиция X", 0.0), ("y", "Позиция Y", 0.0), ("scale", "Масштаб", 100.0), ("rotation", "Поворот", 0.0),
         ("opacity", "Непрозрачность", 100.0)]
PROP_DEFAULT = {k: d for k, _n, d in PROPS}
EASINGS = [("linear", "Линейно"), ("ease", "Плавно (ease in-out)"), ("ease_in", "Разгон (ease in)"),
           ("ease_out", "Торможение (ease out)"), ("hold", "Удержание (hold)")]


def blank(w, h, color=None):
    img = QImage(int(w), int(h), FMT)
    img.fill(QColor(color) if color else Qt.transparent)
    return img


def ease(kind, t):
    if kind == "hold":
        return 0.0
    if kind == "ease":
        return t * t * (3 - 2 * t)
    if kind == "ease_in":
        return t * t * t
    if kind == "ease_out":
        return 1 - (1 - t) ** 3
    return t


@dataclass
class Key:
    frame: int
    value: float
    ease: str = "ease"


@dataclass
class Layer:
    name: str
    image: QImage = None
    visible: bool = True
    locked: bool = False
    alpha_lock: bool = False
    clip: bool = False          # clipping mask: shows only where the layer below has pixels
    opacity: float = 1.0
    blend: str = "normal"
    keys: dict = field(default_factory=dict)   # prop → [Key] sorted by frame
    start: int = 0              # first frame on the timeline
    end: int = -1               # last frame (-1 = until the end of the composition)
    id: int = field(default_factory=lambda: next(_ids))

    # ------------------------------------------------------------------ animation
    def value(self, prop, frame):
        keys = self.keys.get(prop)
        if not keys:
            return PROP_DEFAULT[prop]
        if frame <= keys[0].frame:
            return keys[0].value
        if frame >= keys[-1].frame:
            return keys[-1].value
        for a, b in zip(keys, keys[1:]):
            if a.frame <= frame <= b.frame:
                t = (frame - a.frame) / max(1e-9, b.frame - a.frame)
                return a.value + (b.value - a.value) * ease(a.ease, t)
        return keys[-1].value

    def set_key(self, prop, frame, value, kind=None):
        keys = self.keys.setdefault(prop, [])
        for k in keys:
            if k.frame == frame:
                k.value = value
                if kind:
                    k.ease = kind
                return k
        k = Key(frame, value, kind or "ease")
        keys.append(k)
        keys.sort(key=lambda k: k.frame)
        return k

    def remove_key(self, prop, frame):
        keys = self.keys.get(prop, [])
        self.keys[prop] = [k for k in keys if k.frame != frame]
        if not self.keys[prop]:
            del self.keys[prop]

    def key_at(self, prop, frame):
        return next((k for k in self.keys.get(prop, []) if k.frame == frame), None)

    def animated(self):
        return any(self.keys.values())

    def active(self, frame, length):
        end = self.end if self.end >= 0 else length - 1
        return self.start <= frame <= end

    def transform(self, frame, w, h):
        """Layer → canvas transform at `frame` (anchor: canvas centre)."""
        x, y = self.value("x", frame), self.value("y", frame)
        s = self.value("scale", frame) / 100.0
        r = self.value("rotation", frame)
        if x == 0 and y == 0 and s == 1 and r == 0:
            return QTransform()
        cx, cy = w / 2.0, h / 2.0
        t = QTransform()
        t.translate(cx + x, cy + y)
        t.rotate(r)
        t.scale(s, s)
        t.translate(-cx, -cy)
        return t

    def anim_opacity(self, frame):
        return max(0.0, min(1.0, self.value("opacity", frame) / 100.0))


class Document:
    MAX_UNDO = 40

    def __init__(self, width=1240, height=1754, background="#FFFFFF", dpi=150):
        self.width, self.height = int(width), int(height)
        self.dpi = dpi
        self.background = background   # None = transparent
        self.layers = [Layer("Слой 1", blank(width, height))]
        self.current = self.layers[0]
        self.fps = 24
        self.length = 48
        self.frame = 0
        self.selection = QPainterPath()  # empty = everything
        self.path = None
        self.title_hint = None
        self.undo_stack, self.redo_stack = [], []
        self.version = 0
        self.saved_at = 0

    # ------------------------------------------------------------------ meta
    @property
    def modified(self):
        return self.version != self.saved_at

    def mark_saved(self):
        self.saved_at = self.version

    def title(self):
        return self.path.name if self.path else (self.title_hint or "Без названия")

    def rect(self):
        return QRectF(0, 0, self.width, self.height)

    def has_selection(self):
        return not self.selection.isEmpty()

    def clip_path(self):
        if self.has_selection():
            return self.selection
        p = QPainterPath()
        p.addRect(self.rect())
        return p

    # ------------------------------------------------------------------ layers
    def index(self, layer):
        return self.layers.index(layer)

    def add_layer(self, name=None, above=None, image=None):
        n = len(self.layers) + 1
        names = {l.name for l in self.layers}
        while f"Слой {n}" in names:
            n += 1
        layer = Layer(name or f"Слой {n}", image if image is not None else blank(self.width, self.height))
        i = self.index(above) + 1 if above is not None else len(self.layers)
        self.layers.insert(i, layer)
        self.current = layer
        return layer

    def remove_layer(self, layer):
        if len(self.layers) <= 1:
            return False
        i = self.index(layer)
        self.layers.remove(layer)
        self.current = self.layers[max(0, i - 1)]
        return True

    def duplicate_layer(self, layer):
        new = copy.copy(layer)
        new.id = next(_ids)
        new.name = layer.name + " копия"
        new.image = layer.image.copy()
        new.keys = {p: [copy.copy(k) for k in ks] for p, ks in layer.keys.items()}
        self.layers.insert(self.index(layer) + 1, new)
        self.current = new
        return new

    def merge_down(self, layer):
        i = self.index(layer)
        if i == 0:
            return None
        below = self.layers[i - 1]
        img = below.image.copy()
        p = QPainter(img)
        inv, ok = below.transform(self.frame, self.width, self.height).inverted()
        p.setTransform(layer.transform(self.frame, self.width, self.height) * inv)
        p.setOpacity(layer.opacity * layer.anim_opacity(self.frame))
        p.setCompositionMode(QPainter.CompositionMode_SourceAtop if layer.clip else BLEND_QT.get(layer.blend))
        p.drawImage(0, 0, layer.image)
        p.end()
        below.image = img
        self.layers.remove(layer)
        self.current = below
        return below

    def move_layer(self, layer, delta):
        i = self.index(layer)
        j = max(0, min(len(self.layers) - 1, i + delta))
        self.layers.insert(j, self.layers.pop(i))

    def flatten_image(self, frame=None, background=True):
        return self.render(self.frame if frame is None else frame, background)

    # ------------------------------------------------------------------ rendering
    def _draw_layer(self, p, layer, frame, mode=None, image=None):
        p.save()
        p.setTransform(layer.transform(frame, self.width, self.height), True)
        p.setOpacity(layer.opacity * layer.anim_opacity(frame))
        p.setCompositionMode(mode if mode is not None else BLEND_QT.get(layer.blend, QPainter.CompositionMode_SourceOver))
        p.drawImage(0, 0, image if image is not None else layer.image)
        p.restore()

    def render(self, frame=None, background=True, override=None, layers=None, rect=None):
        """Composite at `frame` (the whole canvas, or only `rect` — then the result is rect-sized).
        `override` = {layer id: QImage} for live stroke previews. Clipping layers are drawn onto their
        base layer (SourceAtop) before the group is blended."""
        frame = self.frame if frame is None else frame
        override = override or {}
        if rect is None:
            rect = QRect(0, 0, self.width, self.height)
        rect = QRect(rect).intersected(QRect(0, 0, self.width, self.height))
        out = blank(max(1, rect.width()), max(1, rect.height()))
        if rect.isEmpty():
            return out
        origin = QTransform.fromTranslate(-rect.x(), -rect.y())
        p = QPainter(out)
        p.setTransform(origin)
        if background and self.background:
            p.fillRect(rect, QColor(self.background))
        layers = self.layers if layers is None else layers
        i = 0
        while i < len(layers):
            base = layers[i]
            group = [base]
            j = i + 1
            while j < len(layers) and layers[j].clip:
                group.append(layers[j])
                j += 1
            i = j
            if not base.visible or not base.active(frame, self.length) or base.clip:
                continue
            if len(group) == 1:
                self._draw_layer(p, base, frame, image=override.get(base.id))
                continue
            tmp = blank(out.width(), out.height())
            tp = QPainter(tmp)
            tp.setTransform(origin)
            self._draw_layer(tp, base, frame, QPainter.CompositionMode_SourceOver, override.get(base.id))
            for clip in group[1:]:
                if clip.visible and clip.active(frame, self.length):
                    self._draw_layer(tp, clip, frame, QPainter.CompositionMode_SourceAtop, override.get(clip.id))
            tp.end()
            p.save()
            p.resetTransform()
            p.setOpacity(1.0)
            p.setCompositionMode(BLEND_QT.get(base.blend, QPainter.CompositionMode_SourceOver))
            p.drawImage(0, 0, tmp)
            p.restore()
        p.end()
        return out

    # ------------------------------------------------------------------ undo
    def _state(self):
        layers = []
        for l in self.layers:
            c = copy.copy(l)
            c.image = QImage(l.image)  # shares pixels until either side is painted on
            c.keys = {p: [copy.copy(k) for k in ks] for p, ks in l.keys.items()}
            layers.append(c)
        return {"layers": layers, "current": self.current.id, "size": (self.width, self.height),
                "selection": QPainterPath(self.selection), "fps": self.fps, "length": self.length,
                "background": self.background}

    def _apply(self, st):
        self.layers = st["layers"]
        self.width, self.height = st["size"]
        self.selection = st["selection"]
        self.fps, self.length, self.background = st["fps"], st["length"], st["background"]
        self.current = next((l for l in self.layers if l.id == st["current"]), self.layers[-1])
        self.frame = min(self.frame, self.length - 1)

    def push(self, label=""):
        self.undo_stack.append((label, self._state()))
        del self.undo_stack[:-self.MAX_UNDO]
        self.redo_stack.clear()
        self.version += 1

    def undo(self):
        if not self.undo_stack:
            return None
        label, st = self.undo_stack.pop()
        self.redo_stack.append((label, self._state()))
        self._apply(st)
        self.version += 1
        return label or True

    def redo(self):
        if not self.redo_stack:
            return None
        label, st = self.redo_stack.pop()
        self.undo_stack.append((label, self._state()))
        self._apply(st)
        self.version += 1
        return label or True

    # ------------------------------------------------------------------ geometry edits
    def resize_canvas(self, w, h, ox=0, oy=0):
        for l in self.layers:
            img = blank(w, h)
            p = QPainter(img)
            p.drawImage(ox, oy, l.image)
            p.end()
            l.image = img
        self.width, self.height = w, h
        self.selection = QPainterPath()

    def scale_image(self, w, h):
        for l in self.layers:
            l.image = l.image.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(FMT)
        self.width, self.height = w, h
        self.selection = QPainterPath()

    def rotate_image(self, deg):
        t = QTransform().rotate(deg)
        for l in self.layers:
            l.image = l.image.transformed(t, Qt.SmoothTransformation).convertToFormat(FMT)
        if deg % 180:
            self.width, self.height = self.height, self.width
        self.selection = QPainterPath()

    def flip_image(self, horizontal):
        for l in self.layers:
            l.image = l.image.mirrored(horizontal, not horizontal)


def layer_point(doc, layer, pt):
    """Canvas point → layer pixel coordinates (inverse of the animated transform)."""
    inv, ok = layer.transform(doc.frame, doc.width, doc.height).inverted()
    return inv.map(QPointF(pt)) if ok else QPointF(pt)


def distance(a, b):
    return math.hypot(a.x() - b.x(), a.y() - b.y())
