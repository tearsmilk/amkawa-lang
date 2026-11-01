"""Sprite model: layers × frames of RGBA cels, frame durations, tags, palette; documents with undo.

Cel images are full-canvas QImage (ARGB32, not premultiplied). Images are never edited in place once
stored: edits build a new QImage and put it back, so undo snapshots (which share image data via Qt's
implicit sharing) stay intact and cheap.
"""
import copy
import itertools
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QRegion, QTransform

FMT = QImage.Format_ARGB32
_ids = itertools.count(1)

BLEND_MODES = [
    (0, "Обычный", QPainter.CompositionMode_SourceOver), (1, "Умножение", QPainter.CompositionMode_Multiply),
    (2, "Экран", QPainter.CompositionMode_Screen), (3, "Перекрытие", QPainter.CompositionMode_Overlay),
    (4, "Затемнение", QPainter.CompositionMode_Darken), (5, "Замена светлым", QPainter.CompositionMode_Lighten),
    (6, "Осветление основы", QPainter.CompositionMode_ColorDodge), (7, "Затемнение основы", QPainter.CompositionMode_ColorBurn),
    (8, "Жёсткий свет", QPainter.CompositionMode_HardLight), (9, "Мягкий свет", QPainter.CompositionMode_SoftLight),
    (10, "Разница", QPainter.CompositionMode_Difference), (11, "Исключение", QPainter.CompositionMode_Exclusion),
    (16, "Сложение", QPainter.CompositionMode_Plus),
]
BLEND_QT = {code: mode for code, _name, mode in BLEND_MODES}
TAG_DIRECTIONS = ["Вперёд", "Назад", "Пинг-понг", "Пинг-понг назад"]


def blank(w, h):
    img = QImage(w, h, FMT)
    img.fill(0)
    return img


def is_empty(img):
    """True if every pixel is fully transparent."""
    if img is None:
        return True
    return not any(bytes(img.constBits())[3::4])


def content_rect(img):
    """Bounding rect of non-transparent pixels (QRect(), if none)."""
    w, h = img.width(), img.height()
    data = bytes(img.constBits())[: w * h * 4]
    alpha = data[3::4]
    top = bottom = None
    left, right = w, -1
    for y in range(h):
        row = alpha[y * w:(y + 1) * w]
        if any(row):
            if top is None:
                top = y
            bottom = y
            l = next(i for i, a in enumerate(row) if a)
            r = w - 1 - next(i for i, a in enumerate(reversed(row)) if a)
            left, right = min(left, l), max(right, r)
    if top is None:
        return QRect()
    return QRect(left, top, right - left + 1, bottom - top + 1)


@dataclass
class Layer:
    name: str
    visible: bool = True
    locked: bool = False
    opacity: int = 255
    blend: int = 0
    id: int = field(default_factory=lambda: next(_ids))


@dataclass
class Tag:
    name: str
    start: int
    end: int
    direction: int = 0
    color: str = "#D97757"


class Sprite:
    def __init__(self, width=32, height=32, background=None):
        self.width, self.height = int(width), int(height)
        self.layers = [Layer("Фон" if background else "Слой 1")]
        self.durations = [100]
        self.cels = {}  # (layer id, frame) → QImage
        self.tags = []
        self.palette = []  # ARGB ints
        self.grid = QRect(0, 0, 16, 16)
        if background:
            img = blank(self.width, self.height)
            img.fill(QColor(background))
            self.cels[(self.layers[0].id, 0)] = img

    # ------------------------------------------------------------------ access
    @property
    def frames(self):
        return len(self.durations)

    def size(self):
        return QRect(0, 0, self.width, self.height).size()

    def cel(self, layer, frame):
        return self.cels.get((layer.id, frame))

    def set_cel(self, layer, frame, img):
        if img is None or is_empty(img):
            self.cels.pop((layer.id, frame), None)
        else:
            self.cels[(layer.id, frame)] = img

    def layer_index(self, layer):
        return self.layers.index(layer)

    def unique_layer_name(self):
        names = {l.name for l in self.layers}
        n = len(self.layers) + 1
        while f"Слой {n}" in names:
            n += 1
        return f"Слой {n}"

    # ------------------------------------------------------------------ rendering
    def composite(self, frame, only=None, show_hidden=False, background=None):
        """Flattened frame (ARGB32_Premultiplied) — visible layers, bottom to top."""
        out = QImage(self.width, self.height, QImage.Format_ARGB32_Premultiplied)
        out.fill(QColor(background) if background else Qt.transparent)
        p = QPainter(out)
        for layer in self.layers:
            if only is not None and layer not in only:
                continue
            if not layer.visible and not show_hidden:
                continue
            img = self.cel(layer, frame)
            if img is None:
                continue
            p.setOpacity(layer.opacity / 255.0)
            p.setCompositionMode(BLEND_QT.get(layer.blend, QPainter.CompositionMode_SourceOver))
            p.drawImage(0, 0, img)
        p.end()
        return out

    def flat_frame(self, frame, background=None):
        return self.composite(frame, background=background).convertToFormat(FMT)

    # ------------------------------------------------------------------ copies (undo)
    def snapshot(self):
        return {
            "size": (self.width, self.height),
            "layers": [copy.copy(l) for l in self.layers],
            "durations": list(self.durations),
            "cels": dict(self.cels),
            "tags": [copy.copy(t) for t in self.tags],
            "palette": list(self.palette),
        }

    def restore(self, snap):
        self.width, self.height = snap["size"]
        self.layers = [copy.copy(l) for l in snap["layers"]]
        self.durations = list(snap["durations"])
        self.cels = dict(snap["cels"])
        self.tags = [copy.copy(t) for t in snap["tags"]]
        self.palette = list(snap["palette"])

    # ------------------------------------------------------------------ layers
    def add_layer(self, index=None, name=None):
        layer = Layer(name or self.unique_layer_name())
        self.layers.insert(len(self.layers) if index is None else index, layer)
        return layer

    def remove_layer(self, layer):
        if len(self.layers) <= 1:
            return False
        self.layers.remove(layer)
        for key in [k for k in self.cels if k[0] == layer.id]:
            del self.cels[key]
        return True

    def duplicate_layer(self, layer):
        new = Layer(layer.name + " копия", layer.visible, False, layer.opacity, layer.blend)
        self.layers.insert(self.layer_index(layer) + 1, new)
        for f in range(self.frames):
            img = self.cel(layer, f)
            if img is not None:
                self.cels[(new.id, f)] = QImage(img)
        return new

    def merge_down(self, layer):
        i = self.layer_index(layer)
        if i == 0:
            return None
        below = self.layers[i - 1]
        for f in range(self.frames):
            top = self.cel(layer, f)
            if top is None:
                continue
            base = QImage(self.cel(below, f) or blank(self.width, self.height))
            p = QPainter(base)
            p.setOpacity(layer.opacity / 255.0)
            p.setCompositionMode(BLEND_QT.get(layer.blend, QPainter.CompositionMode_SourceOver))
            p.drawImage(0, 0, top)
            p.end()
            self.set_cel(below, f, base)
        self.remove_layer(layer)
        return below

    def move_layer(self, layer, delta):
        i = self.layer_index(layer)
        j = max(0, min(len(self.layers) - 1, i + delta))
        if i != j:
            self.layers.insert(j, self.layers.pop(i))

    # ------------------------------------------------------------------ frames
    def insert_frame(self, at, copy_from=None, duration=None):
        """Insert a frame at index `at` (cels of later frames shift right)."""
        self.durations.insert(at, duration or (self.durations[copy_from] if copy_from is not None else
                                               self.durations[min(at, len(self.durations) - 1)]))
        cels = {}
        for (lid, f), img in self.cels.items():
            cels[(lid, f + 1 if f >= at else f)] = img
        if copy_from is not None:
            src = copy_from + 1 if copy_from >= at else copy_from
            for layer in self.layers:
                img = cels.get((layer.id, src))
                if img is not None:
                    cels[(layer.id, at)] = QImage(img)
        self.cels = cels
        for t in self.tags:
            if t.start >= at:
                t.start += 1
            if t.end >= at:
                t.end += 1

    def remove_frame(self, at):
        if self.frames <= 1:
            return False
        del self.durations[at]
        cels = {}
        for (lid, f), img in self.cels.items():
            if f == at:
                continue
            cels[(lid, f - 1 if f > at else f)] = img
        self.cels = cels
        tags = []
        for t in self.tags:
            if t.start > at:
                t.start -= 1
            if t.end >= at:
                t.end -= 1
            if t.end >= t.start:
                tags.append(t)
        self.tags = tags
        return True

    def move_frame(self, src, dst):
        if src == dst:
            return
        order = list(range(self.frames))
        order.insert(dst, order.pop(src))
        new_index = {old: new for new, old in enumerate(order)}
        self.durations = [self.durations[o] for o in order]
        self.cels = {(lid, new_index[f]): img for (lid, f), img in self.cels.items()}

    # ------------------------------------------------------------------ whole-sprite transforms
    def transform_all(self, fn, new_size=None):
        """Apply fn(QImage) → QImage to every cel."""
        if new_size:
            self.width, self.height = new_size
        self.cels = {k: fn(img) for k, img in self.cels.items()}
        self.cels = {k: v for k, v in self.cels.items() if not is_empty(v)}

    def flip(self, horizontal):
        self.transform_all(lambda img: img.mirrored(horizontal, not horizontal))

    def rotate(self, degrees):
        t = QTransform().rotate(degrees)
        size = (self.height, self.width) if degrees % 180 else (self.width, self.height)
        self.transform_all(lambda img: img.transformed(t).convertToFormat(FMT), size)

    def resize_canvas(self, width, height, ox=0, oy=0):
        """New canvas size; old content placed at (ox, oy)."""
        def place(img):
            out = blank(width, height)
            p = QPainter(out)
            p.setCompositionMode(QPainter.CompositionMode_Source)
            p.drawImage(ox, oy, img)
            p.end()
            return out
        self.transform_all(place, (width, height))

    def scale(self, width, height):
        self.transform_all(lambda img: img.scaled(width, height, Qt.IgnoreAspectRatio, Qt.FastTransformation)
                           .convertToFormat(FMT), (width, height))


class Document:
    """A sprite being edited: file path, current layer / frame, selection, undo history."""

    MAX_UNDO = 120

    def __init__(self, sprite, path=None):
        self.sprite = sprite
        self.path = Path(path) if path else None
        self.layer = sprite.layers[-1]
        self.frame = 0
        self.selection = QRegion()
        self.undo_stack = []
        self.redo_stack = []
        self.saved_at = 0
        self.version = 0
        self.title_hint = None

    @property
    def modified(self):
        return self.version != self.saved_at

    def mark_saved(self):
        self.saved_at = self.version

    def title(self):
        return self.path.name if self.path else (self.title_hint or "Без названия")

    # ------------------------------------------------------------------ undo
    def _state(self):
        return (self.sprite.snapshot(), self.layer.id, self.frame, QRegion(self.selection))

    def _apply(self, state):
        snap, lid, frame, sel = state
        self.sprite.restore(snap)
        self.layer = next((l for l in self.sprite.layers if l.id == lid), self.sprite.layers[-1])
        self.frame = min(frame, self.sprite.frames - 1)
        self.selection = sel

    def push(self, label=""):
        """Call BEFORE a change: remembers the current state for undo."""
        self.undo_stack.append((label, self._state()))
        del self.undo_stack[:-self.MAX_UNDO]
        self.redo_stack.clear()
        self.version += 1

    def undo(self):
        if not self.undo_stack:
            return None
        label, state = self.undo_stack.pop()
        self.redo_stack.append((label, self._state()))
        self._apply(state)
        self.version += 1
        return label

    def redo(self):
        if not self.redo_stack:
            return None
        label, state = self.redo_stack.pop()
        self.undo_stack.append((label, self._state()))
        self._apply(state)
        self.version += 1
        return label

    # ------------------------------------------------------------------ helpers
    def current_image(self):
        return self.sprite.cel(self.layer, self.frame)

    def editable_image(self):
        """A fresh copy of the current cel (or a blank one) to draw on, then store with set_current()."""
        img = self.current_image()
        return img.copy() if img is not None else blank(self.sprite.width, self.sprite.height)

    def set_current(self, img):
        self.sprite.set_cel(self.layer, self.frame, img)

    def has_selection(self):
        return not self.selection.isEmpty()

    def selection_bounds(self):
        return self.selection.boundingRect() if self.has_selection() else QRect(0, 0, self.sprite.width, self.sprite.height)

    def clip_region(self):
        full = QRegion(0, 0, self.sprite.width, self.sprite.height)
        return self.selection.intersected(full) if self.has_selection() else full

    def point_in_sprite(self, pt: QPoint):
        return 0 <= pt.x() < self.sprite.width and 0 <= pt.y() < self.sprite.height
