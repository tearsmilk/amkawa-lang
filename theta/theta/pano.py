"""Viewers: a 360° equirectangular panorama (QPainter, piecewise reprojection on a grid of cells — fast enough
without OpenGL) and a flat photo with pan / zoom. Drag to look around, wheel to zoom, arrows too."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

from . import theme


class EquirectView(QWidget):
    """yaw/pitch in degrees, fov horizontal 30–110°. Set `locked` to forbid looking around, `zoomable` for the
    wheel."""

    moved = Signal()

    def __init__(self):
        super().__init__()
        self.image = None          # QImage, doubled horizontally so a cell never wraps
        self.width_px = 0
        self.height_px = 0
        self.yaw = 0.0
        self.pitch = 0.0
        self.fov = 90.0
        self.locked = False
        self.zoomable = True
        self.heading0 = 0.0
        self._drag = None
        self._fine = True
        self.setMouseTracking(False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.OpenHandCursor)

    def set_image(self, img, heading=0.0):
        img = img.convertToFormat(QImage.Format_RGB32)
        w, h = img.width(), img.height()
        if w > 4096:
            img = img.scaledToWidth(4096, Qt.SmoothTransformation)
            w, h = img.width(), img.height()
        doubled = QImage(w * 2, h, QImage.Format_RGB32)
        p = QPainter(doubled)
        p.drawImage(0, 0, img)
        p.drawImage(w, 0, img)
        p.end()
        self.image, self.width_px, self.height_px = doubled, w, h
        self.heading0 = heading or 0.0
        self.yaw, self.pitch, self.fov = 0.0, 0.0, 90.0
        self.update()

    def reset_view(self):
        self.yaw, self.pitch, self.fov = 0.0, 0.0, 90.0
        self.update()

    def compass(self):
        """Direction the view centre points to, degrees from north."""
        return (self.heading0 + self.yaw) % 360

    # -- projection
    def _dir(self, u, v):
        aspect = max(1e-6, self.width() / max(1, self.height()))
        t = math.tan(math.radians(self.fov) / 2)
        x, y, z = (u - 0.5) * 2 * t, (0.5 - v) * 2 * t / aspect, 1.0
        cp, sp = math.cos(math.radians(self.pitch)), math.sin(math.radians(self.pitch))
        y, z = y * cp - z * sp, y * sp + z * cp
        cy, sy = math.cos(math.radians(self.yaw)), math.sin(math.radians(self.yaw))
        x, z = x * cy + z * sy, -x * sy + z * cy
        n = math.sqrt(x * x + y * y + z * z) or 1.0
        lon = math.atan2(x, z)
        lat = math.asin(max(-1.0, min(1.0, y / n)))
        return lon, lat

    def _src(self, u, v):
        lon, lat = self._dir(u, v)
        return (lon / (2 * math.pi) + 0.5) * self.width_px, (0.5 - lat / math.pi) * self.height_px

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#141413"))
        if self.image is None:
            p.setPen(QColor(theme.CURRENT.get("faint", "#A8A59C")))
            p.drawText(self.rect(), Qt.AlignCenter, "Нет изображения")
            return
        p.setRenderHint(QPainter.SmoothPixmapTransform, self._fine)
        cols, rows = (32, 18) if self._fine else (16, 9)
        W, H = self.width(), self.height()
        cw, ch = W / cols, H / rows
        half = self.width_px / 2
        for j in range(rows):
            for i in range(cols):
                corners = [self._src(i / cols, j / rows), self._src((i + 1) / cols, j / rows),
                           self._src(i / cols, (j + 1) / rows), self._src((i + 1) / cols, (j + 1) / rows)]
                xs = [c[0] for c in corners]
                if max(xs) - min(xs) > half:   # straddles the seam: shift the low side onto the doubled copy
                    xs = [x + self.width_px if x < half else x for x in xs]
                ys = [c[1] for c in corners]
                sx0, sx1 = min(xs), max(xs)
                sy0, sy1 = max(0.0, min(ys)), min(float(self.height_px), max(ys))
                if sx1 - sx0 < 0.5 or sy1 - sy0 < 0.5:
                    continue
                p.drawImage(QRectF(i * cw, j * ch, cw + 0.7, ch + 0.7), self.image, QRectF(sx0, sy0, sx1 - sx0, sy1 - sy0))
        self._paint_compass(p)

    def _paint_compass(self, p):
        p.setRenderHint(QPainter.Antialiasing)
        r, cx, cy = 22, self.width() - 36, 36
        p.setPen(QPen(QColor(255, 255, 255, 150), 1.5))
        p.setBrush(QColor(20, 20, 19, 140))
        p.drawEllipse(QPointF(cx, cy), r, r)
        a = math.radians(-self.compass())
        tip = QPointF(cx + math.sin(a) * (r - 5), cy - math.cos(a) * (r - 5))
        p.setPen(QPen(QColor(theme.CURRENT.get("accent", "#D97757")), 2.5))
        p.drawLine(QPointF(cx, cy), tip)
        p.setPen(QColor("#FFFFFF"))
        f = QFont()
        f.setPixelSize(9)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(cx - r, cy - r - 2, r * 2, 12), Qt.AlignCenter, "N")

    # -- input
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and not self.locked:
            self._drag = (e.position(), self.yaw, self.pitch)
            self._fine = False
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if self._drag:
            start, yaw0, pitch0 = self._drag
            d = e.position() - start
            scale = self.fov / max(1, self.width())
            self.yaw = (yaw0 - d.x() * scale) % 360
            self.pitch = max(-85.0, min(85.0, pitch0 + d.y() * scale))
            self.update()

    def mouseReleaseEvent(self, _):
        if self._drag:
            self._drag = None
            self._fine = True
            self.setCursor(Qt.OpenHandCursor)
            self.update()
            self.moved.emit()

    def wheelEvent(self, e):
        if not self.zoomable:
            return
        self.fov = max(30.0, min(110.0, self.fov - e.angleDelta().y() / 120 * 6))
        self.update()

    def keyPressEvent(self, e):
        step = 6
        if self.locked:
            return super().keyPressEvent(e)
        if e.key() == Qt.Key_Left:
            self.yaw = (self.yaw - step) % 360
        elif e.key() == Qt.Key_Right:
            self.yaw = (self.yaw + step) % 360
        elif e.key() == Qt.Key_Up:
            self.pitch = min(85.0, self.pitch + step)
        elif e.key() == Qt.Key_Down:
            self.pitch = max(-85.0, self.pitch - step)
        else:
            return super().keyPressEvent(e)
        self.update()


class FlatView(QWidget):
    """A photo fitted into the widget; wheel zooms (1–4×), drag pans."""

    def __init__(self):
        super().__init__()
        self.image = None
        self.zoom = 1.0
        self.offset = QPointF(0, 0)
        self.zoomable = True
        self.locked = False
        self._drag = None
        self.setCursor(Qt.OpenHandCursor)

    def set_image(self, img):
        self.image = img.convertToFormat(QImage.Format_RGB32)
        self.zoom, self.offset = 1.0, QPointF(0, 0)
        self.update()

    def reset_view(self):
        self.zoom, self.offset = 1.0, QPointF(0, 0)
        self.update()

    def _fit(self):
        iw, ih = self.image.width(), self.image.height()
        k = min(self.width() / iw, self.height() / ih) * self.zoom
        w, h = iw * k, ih * k
        return QRectF((self.width() - w) / 2 + self.offset.x(), (self.height() - h) / 2 + self.offset.y(), w, h)

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#141413"))
        if self.image is None:
            return
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(self._fit(), self.image)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and not self.locked:
            self._drag = (e.position(), QPointF(self.offset))
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if self._drag:
            start, off = self._drag
            self.offset = off + (e.position() - start)
            self.update()

    def mouseReleaseEvent(self, _):
        self._drag = None
        self.setCursor(Qt.OpenHandCursor)

    def wheelEvent(self, e):
        if not self.zoomable:
            return
        self.zoom = max(1.0, min(4.0, self.zoom * (1.15 if e.angleDelta().y() > 0 else 1 / 1.15)))
        if self.zoom == 1.0:
            self.offset = QPointF(0, 0)
        self.update()
