"""Brush engine: round dabs (hardness, grain, scatter) stamped along the stroke with spacing, pen pressure
(size / opacity), stabiliser smoothing, and modes: paint, erase, smudge, blur.

Paint / erase dabs go into a stroke buffer (flow builds up inside it, opacity caps it), which is laid over
the layer as it was when the stroke started — so a marker never gets darker than its opacity within one
stroke, exactly like Clip Studio / Krita. Smudge and blur work on the layer pixels directly.
"""
import math
import random
from dataclasses import asdict, dataclass, fields
from functools import lru_cache

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QRadialGradient

from .model import FMT, blank


@dataclass
class Brush:
    name: str
    size: float = 8.0
    opacity: float = 1.0
    flow: float = 1.0
    hardness: float = 0.9
    spacing: float = 0.12
    min_size: float = 0.2        # size at zero pressure (fraction)
    pressure_size: bool = True
    pressure_opacity: bool = False
    smoothing: float = 0.3
    grain: float = 0.0           # 0..1 paper texture
    scatter: float = 0.0         # 0..1 dab jitter (× size)
    mode: str = "paint"          # paint | erase | smudge | blur
    icon: str = "✎"

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})


PRESETS = [
    Brush("Карандаш", 4, 0.9, 0.75, 0.85, 0.12, 0.35, True, True, 0.25, 0.55, 0.0, "paint", "✏"),
    Brush("G-перо (тушь)", 6, 1.0, 1.0, 1.0, 0.06, 0.08, True, False, 0.55, 0.0, 0.0, "paint", "✒"),
    Brush("Кисть-ручка", 14, 1.0, 1.0, 0.95, 0.06, 0.03, True, False, 0.45, 0.0, 0.0, "paint", "🖌"),
    Brush("Маркер", 22, 0.55, 1.0, 0.92, 0.08, 0.6, True, False, 0.2, 0.0, 0.0, "paint", "▮"),
    Brush("Аэрограф", 80, 1.0, 0.07, 0.0, 0.08, 0.5, False, True, 0.15, 0.0, 0.0, "paint", "☁"),
    Brush("Акварель", 44, 0.65, 0.18, 0.25, 0.1, 0.4, True, True, 0.2, 0.35, 0.04, "paint", "💧"),
    Brush("Мел", 18, 0.9, 0.6, 0.7, 0.18, 0.5, True, True, 0.15, 0.85, 0.12, "paint", "▧"),
    Brush("Плоская заливка", 30, 1.0, 1.0, 1.0, 0.05, 1.0, False, False, 0.1, 0.0, 0.0, "paint", "■"),
    Brush("Ластик", 24, 1.0, 1.0, 0.9, 0.08, 0.4, True, False, 0.2, 0.0, 0.0, "erase", "⌫"),
    Brush("Мягкий ластик", 70, 1.0, 0.25, 0.0, 0.08, 0.5, False, True, 0.15, 0.0, 0.0, "erase", "◌"),
    Brush("Палец", 36, 0.8, 1.0, 0.4, 0.1, 0.5, True, False, 0.2, 0.0, 0.0, "smudge", "☝"),
    Brush("Размытие", 40, 0.8, 1.0, 0.3, 0.15, 0.5, True, False, 0.2, 0.0, 0.0, "blur", "◎"),
]


@lru_cache(maxsize=1)
def grain_tile():
    rnd = random.Random(7)
    img = QImage(64, 64, QImage.Format_ARGB32_Premultiplied)
    for y in range(64):
        for x in range(64):
            a = int(255 * (0.35 + 0.65 * rnd.random() ** 0.7))
            img.setPixel(x, y, (a << 24))
    return img


@lru_cache(maxsize=256)
def dab_image(diameter_q, hardness, rgba):
    """Round dab of diameter diameter_q/4 px (quantised for the cache)."""
    d = diameter_q / 4.0
    size = max(1, int(math.ceil(d)) + 2)
    img = QImage(size, size, FMT)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    c = QColor.fromRgba(rgba)
    r = d / 2.0
    centre = QPointF(size / 2.0, size / 2.0)
    if d <= 1.5:
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawEllipse(centre, max(r, 0.5), max(r, 0.5))
    else:
        g = QRadialGradient(centre, r)
        transparent = QColor(c)
        transparent.setAlpha(0)
        g.setColorAt(0, c)
        g.setColorAt(max(0.0, min(0.999, hardness)), c)
        g.setColorAt(1, transparent)
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(centre, r, r)
    p.end()
    return img


class Stroke:
    """One stroke on one layer. Points are in layer coordinates."""

    def __init__(self, brush, layer, color, clip=None, scale=1.0):
        self.b = brush
        self.layer = layer
        self.base = layer.image
        self.preview = QImage(layer.image)       # shares pixels until first composite
        self.buffer = None
        if brush.mode in ("paint", "erase"):
            self.buffer = blank(self.base.width(), self.base.height())
        self.color = QColor(color)
        self.clip = clip                          # QPainterPath in layer coordinates or None
        self.scale = max(1e-3, scale)             # layer scale: keep the on-screen size
        self.last = None                          # (point, pressure) of the last dab
        self.smooth = None
        self.residual = 0.0
        self.dirty = QRect()
        self.rnd = random.Random(1)
        self.smudge_patch = None

    # ------------------------------------------------------------------ input
    def add(self, pt, pressure=1.0, final=False):
        """Add an input point; returns the dirty rect (layer coords) to repaint."""
        pt = QPointF(pt)
        if self.smooth is None:
            self.smooth = pt
        else:
            k = 1.0 - min(0.95, self.b.smoothing * 0.92)
            self.smooth = self.smooth + (pt - self.smooth) * (1.0 if final else k)
        target = self.smooth
        self.dirty = QRect()
        if self.last is None:
            self._dab(target, pressure)
            self.last = (target, pressure)
        else:
            self._segment(self.last[0], self.last[1], target, pressure)
        self._composite()
        return self.dirty

    def finish(self, pt=None, pressure=1.0):
        if pt is not None and self.smooth is not None:
            self.add(pt, pressure, final=True)
        if self.buffer is not None:
            self.dirty = QRect(0, 0, self.base.width(), self.base.height())
        return self.preview

    # ------------------------------------------------------------------ dabs
    def _size(self, pressure):
        s = self.b.size / self.scale
        if self.b.pressure_size:
            s *= self.b.min_size + (1 - self.b.min_size) * pressure
        return max(1.0 if self.b.mode == "paint" else 0.6, s)

    def _segment(self, a, pa, b, pb):
        dist = math.hypot(b.x() - a.x(), b.y() - a.y())
        if dist < 1e-6:
            return
        pos = -self.residual
        while True:
            step = max(0.5, self._size(pa + (pb - pa) * max(0.0, pos) / dist) * self.b.spacing)
            pos += step
            if pos > dist:
                self.residual = dist - (pos - step)
                break
            t = pos / dist
            self._dab(a + (b - a) * t, pa + (pb - pa) * t)
        self.last = (b, pb)

    def _dab(self, pt, pressure):
        b = self.b
        size = self._size(pressure)
        if b.scatter:
            j = b.scatter * size
            pt = QPointF(pt.x() + self.rnd.uniform(-j, j), pt.y() + self.rnd.uniform(-j, j))
        alpha = b.flow * (pressure if b.pressure_opacity else 1.0)
        if b.mode == "smudge":
            self._smudge(pt, size, b.opacity * (0.35 + 0.65 * pressure))
            return
        if b.mode == "blur":
            self._blur(pt, size, b.opacity)
            return
        col = QColor(self.color) if b.mode == "paint" else QColor(0, 0, 0)
        col.setAlphaF(max(0.0, min(1.0, alpha * (col.alphaF() if b.mode == "paint" else 1.0))))
        dab = dab_image(max(2, int(size * 4)), round(b.hardness, 2), col.rgba())
        if b.grain:
            dab = dab.copy()
            gp = QPainter(dab)
            gp.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            gp.setOpacity(b.grain)
            # grain tile anchored to the canvas so the paper texture stays put
            tile = grain_tile()
            ox = int(pt.x()) % 64
            oy = int(pt.y()) % 64
            for ty in range(-oy - 64, dab.height() + 64, 64):
                for tx in range(-ox - 64, dab.width() + 64, 64):
                    gp.drawImage(tx, ty, tile)
            gp.end()
        x = pt.x() - dab.width() / 2.0
        y = pt.y() - dab.height() / 2.0
        p = QPainter(self.buffer)
        p.drawImage(QPointF(x, y), dab)
        p.end()
        self.dirty = self.dirty.united(QRect(int(x) - 1, int(y) - 1, dab.width() + 3, dab.height() + 3))

    def _circle_mask(self, d):
        return dab_image(max(2, int(d * 4)), 0.5, QColor(0, 0, 0).rgba())

    def _smudge(self, pt, size, strength):
        d = int(size) + 2
        rect = QRect(int(pt.x() - d / 2), int(pt.y() - d / 2), d, d)
        current = self.preview.copy(rect)
        if self.smudge_patch is not None and self.smudge_patch.size() == current.size():
            patch = self.smudge_patch.copy()
            mp = QPainter(patch)
            mp.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            mp.drawImage(0, 0, self._circle_mask(d).scaled(patch.size()))
            mp.end()
            p = QPainter(self.preview)
            if self.clip is not None:
                p.setClipPath(self.clip)
            p.setOpacity(strength)
            p.drawImage(rect.topLeft(), patch)
            p.end()
            self.dirty = self.dirty.united(rect.adjusted(-1, -1, 1, 1))
            # carry a mix of what we had and what is here now
            mix = QPainter(self.smudge_patch)
            mix.setOpacity(0.25)
            mix.drawImage(0, 0, current)
            mix.end()
        else:
            self.smudge_patch = current

    def _blur(self, pt, size, strength):
        d = int(size) + 4
        rect = QRect(int(pt.x() - d / 2), int(pt.y() - d / 2), d, d)
        patch = self.preview.copy(rect)
        small = patch.scaled(max(1, d // 4), max(1, d // 4), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        blurred = small.scaled(patch.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(FMT)
        mp = QPainter(blurred)
        mp.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        mp.drawImage(0, 0, self._circle_mask(d).scaled(blurred.size()))
        mp.end()
        p = QPainter(self.preview)
        if self.clip is not None:
            p.setClipPath(self.clip)
        p.setOpacity(strength * 0.5)
        p.drawImage(rect.topLeft(), blurred)
        p.end()
        self.dirty = self.dirty.united(rect.adjusted(-1, -1, 1, 1))

    # ------------------------------------------------------------------ compositing
    def _composite(self):
        if self.buffer is None or self.dirty.isEmpty():
            return
        r = self.dirty.intersected(QRect(0, 0, self.base.width(), self.base.height()))
        if r.isEmpty():
            return
        p = QPainter(self.preview)
        p.setClipRect(r)
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.drawImage(r.topLeft(), self.base, r)
        if self.clip is not None:
            p.setClipPath(self.clip, Qt.IntersectClip)
        if self.b.mode == "erase":
            p.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        elif self.layer.alpha_lock:
            p.setCompositionMode(QPainter.CompositionMode_SourceAtop)
        else:
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.setOpacity(self.b.opacity)
        p.drawImage(r.topLeft(), self.buffer, r)
        p.end()


def stroke_path(brush, layer, color, path_points, clip=None):
    """Draw a whole polyline (shapes, «обвести выделение») with a brush; returns the new layer image."""
    s = Stroke(brush, layer, color, clip)
    for pt in path_points:
        s.add(pt, 1.0, final=True)
    s.dirty = QRect(0, 0, layer.image.width(), layer.image.height())
    s._composite()
    return s.preview


def path_points(path: QPainterPath, step=1.0):
    """Points along a QPainterPath every `step` px."""
    length = path.length()
    n = max(2, int(length / step))
    return [path.pointAtPercent(min(1.0, i / n)) for i in range(n + 1)]


def brush_rect(pt, size):
    return QRectF(pt.x() - size / 2, pt.y() - size / 2, size, size)
