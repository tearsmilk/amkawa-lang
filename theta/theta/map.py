"""Slippy map on OpenStreetMap tiles (own widget, no web view): drag, wheel / double-click zoom, a click drops the
guess marker; after the round it also shows the true spot and the line between them. Tiles are cached on disk
(<data>/cache/tiles) and requested with a descriptive User-Agent, as the OSM tile policy requires."""
import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from . import geo, net, theme
from .paths import cache_dir

MIN_ZOOM, MAX_ZOOM = 1, 17


class TileCache:
    def __init__(self, runner):
        self.runner = runner
        self.mem = {}
        self.pending = set()
        self.folder = cache_dir() / "tiles"
        self.listeners = []

    def path(self, z, x, y):
        return self.folder / str(z) / str(x) / f"{y}.png"

    def get(self, z, x, y):
        key = (z, x % (2 ** z), y)
        if y < 0 or y >= 2 ** z:
            return None
        pix = self.mem.get(key)
        if pix is not None:
            return pix
        p = self.path(*key)
        if p.exists():
            pix = QPixmap(str(p))
            if not pix.isNull():
                self.mem[key] = pix
                return pix
        if key not in self.pending and self.runner:
            self.pending.add(key)
            url = geo.tile_url(*key)

            def fetch():
                p.parent.mkdir(parents=True, exist_ok=True)
                net.download(url, p, timeout=20)
                return key

            def done(k):
                self.pending.discard(k)
                pix_ = QPixmap(str(self.path(*k)))
                if not pix_.isNull():
                    self.mem[k] = pix_
                for cb in list(self.listeners):
                    cb()

            self.runner.run(fetch, done, lambda e, k=key: self.pending.discard(k))
        return None


class SlippyMap(QWidget):
    guessed = Signal(float, float)
    interacted = Signal()

    def __init__(self, tiles):
        super().__init__()
        self.tiles = tiles
        tiles.listeners.append(self.update)
        self.zoom = 1
        self.center = [0.0, 20.0]       # lon, lat
        self.guess = None               # (lat, lon)
        self.truth = None
        self.locked = False
        self._drag = None
        self.setMouseTracking(True)
        self.setMinimumSize(120, 90)

    # -- coordinates
    def _world(self, lon, lat):
        return geo.lonlat_to_world(lon, lat, self.zoom)

    def _origin(self):
        cx, cy = self._world(*self.center)
        return cx - self.width() / 2, cy - self.height() / 2

    def to_screen(self, lat, lon):
        ox, oy = self._origin()
        x, y = self._world(lon, lat)
        return QPointF(x - ox, y - oy)

    def to_lonlat(self, pos):
        ox, oy = self._origin()
        return geo.world_to_lonlat(pos.x() + ox, pos.y() + oy, self.zoom)

    def set_view(self, lat, lon, zoom):
        self.center = [lon, lat]
        self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, int(zoom)))
        self.update()

    def fit(self, points, pad=0.15):
        """Zoom so that all (lat, lon) points fit."""
        if not points:
            return
        lats = [p[0] for p in points]
        lons = [p[1] for p in points]
        self.center = [(min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2]
        for z in range(MAX_ZOOM, MIN_ZOOM - 1, -1):
            self.zoom = z
            xs, ys = zip(*(self._world(lon, lat) for lat, lon in points))
            if (max(xs) - min(xs)) <= self.width() * (1 - 2 * pad) and (max(ys) - min(ys)) <= self.height() * (1 - 2 * pad):
                break
        self.update()

    def reset(self):
        self.guess = self.truth = None
        self.locked = False
        self.set_view(20.0, 0.0, 1)

    # -- painting
    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#D9E6EF"))
        ox, oy = self._origin()
        n = 2 ** self.zoom
        x0, y0 = int(math.floor(ox / geo.TILE)), int(math.floor(oy / geo.TILE))
        x1, y1 = int(math.floor((ox + self.width()) / geo.TILE)), int(math.floor((oy + self.height()) / geo.TILE))
        for ty in range(y0, y1 + 1):
            if ty < 0 or ty >= n:
                continue
            for tx in range(x0, x1 + 1):
                pix = self.tiles.get(self.zoom, tx, ty)
                target = QRectF(tx * geo.TILE - ox, ty * geo.TILE - oy, geo.TILE, geo.TILE)
                if pix is not None:
                    p.drawPixmap(target.toRect(), pix)
                else:
                    p.fillRect(target, QColor("#E6ECF0"))
        p.setRenderHint(QPainter.Antialiasing)
        if self.guess and self.truth:
            a, b = self.to_screen(*self.guess), self.to_screen(*self.truth)
            pen = QPen(QColor("#141413"), 2, Qt.DashLine)
            p.setPen(pen)
            p.drawLine(a, b)
        if self.truth:
            self._pin(p, self.to_screen(*self.truth), QColor("#141413"))
        if self.guess:
            self._pin(p, self.to_screen(*self.guess), QColor(theme.CURRENT.get("accent", "#D97757")))
        f = QFont()
        f.setPixelSize(9)
        p.setFont(f)
        p.setPen(QColor(20, 20, 19, 170))
        p.fillRect(QRectF(self.width() - 96, self.height() - 14, 96, 14), QColor(255, 255, 255, 170))
        p.drawText(QRectF(self.width() - 94, self.height() - 14, 94, 14), Qt.AlignVCenter | Qt.AlignLeft, "© OpenStreetMap")

    def _pin(self, p, pt, color):
        path = QPainterPath(QPointF(pt.x(), pt.y()))
        path.cubicTo(QPointF(pt.x() - 9, pt.y() - 10), QPointF(pt.x() - 9, pt.y() - 22), QPointF(pt.x(), pt.y() - 22))
        path.cubicTo(QPointF(pt.x() + 9, pt.y() - 22), QPointF(pt.x() + 9, pt.y() - 10), QPointF(pt.x(), pt.y()))
        p.setPen(QPen(QColor("#FFFFFF"), 1.5))
        p.setBrush(color)
        p.drawPath(path)
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(pt.x(), pt.y() - 14), 3, 3)

    # -- input
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = (e.position(), list(self.center), False)
        self.interacted.emit()

    def mouseMoveEvent(self, e):
        if self._drag:
            start, center, _ = self._drag
            d = e.position() - start
            if abs(d.x()) + abs(d.y()) > 3:
                self._drag = (start, center, True)
                cx, cy = geo.lonlat_to_world(center[0], center[1], self.zoom)
                lon, lat = geo.world_to_lonlat(cx - d.x(), cy - d.y(), self.zoom)
                self.center = [lon, max(-85, min(85, lat))]
                self.update()

    def mouseReleaseEvent(self, e):
        if self._drag:
            start, _, moved = self._drag
            self._drag = None
            if not moved and e.button() == Qt.LeftButton and not self.locked:
                lon, lat = self.to_lonlat(e.position())
                self.guess = (lat, lon)
                self.update()
                self.guessed.emit(lat, lon)

    def mouseDoubleClickEvent(self, e):
        self.zoom_at(e.position(), 1)

    def wheelEvent(self, e):
        self.zoom_at(e.position(), 1 if e.angleDelta().y() > 0 else -1)
        self.interacted.emit()

    def zoom_at(self, pos, delta):
        z = max(MIN_ZOOM, min(MAX_ZOOM, self.zoom + delta))
        if z == self.zoom:
            return
        lon, lat = self.to_lonlat(pos)
        self.zoom = z
        ox, oy = geo.lonlat_to_world(lon, lat, z)
        cx, cy = ox - (pos.x() - self.width() / 2), oy - (pos.y() - self.height() / 2)
        clon, clat = geo.world_to_lonlat(cx, cy, z)
        self.center = [clon, max(-85, min(85, clat))]
        self.update()

    def zoom_in(self):
        self.zoom_at(QPointF(self.width() / 2, self.height() / 2), 1)

    def zoom_out(self):
        self.zoom_at(QPointF(self.width() / 2, self.height() / 2), -1)


def tile_count_on_disk():
    folder = cache_dir() / "tiles"
    return sum(1 for _ in folder.rglob("*.png")) if folder.exists() else 0


def tiles_size():
    folder = Path(cache_dir() / "tiles")
    return sum(f.stat().st_size for f in folder.rglob("*.png")) if folder.exists() else 0
