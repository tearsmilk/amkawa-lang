"""Canvas view: zoom / pan / rotate / mirror, pen tablet pressure, trackpad pinch & rotate, partial re-composite
while painting (only the dirty rectangle is re-rendered), selection outline and tool overlays."""
import math

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QRegion, QTransform
from PySide6.QtWidgets import QWidget

ZOOM_MIN, ZOOM_MAX = 0.03, 32.0


class Canvas(QWidget):
    hovered = Signal(object)
    view_changed = Signal()

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.doc = None
        self.zoom = 1.0
        self.angle = 0.0
        self.mirror = False
        self.pan = QPointF(0, 0)
        self.composite = None
        self._scaled = None   # (zoom, image): area-averaged copy for zoomed-out display
        self.hover = None
        self._pan_drag = None
        self._rot_drag = None
        self._space = False
        self._tool = None
        self._temp = None
        self._tablet = False
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WA_TabletTracking)
        self.setAttribute(Qt.WA_AcceptTouchEvents, False)
        self.setMinimumSize(200, 200)

    # ------------------------------------------------------------------ document / rendering
    def set_document(self, doc):
        self.doc = doc
        self.refresh()
        if doc is not None:
            self.fit()

    def refresh(self):
        self.composite = self.doc.render() if self.doc is not None else None
        self._scaled = None
        self.update()

    def stroke_preview(self, layer, image, dirty=None):
        """Re-composite only `dirty` (layer coords) with `image` standing in for `layer`."""
        if self.doc is None:
            return
        if layer is None:
            self.refresh()
            return
        if dirty is None or dirty.isEmpty():
            return
        doc = self.doc
        r = layer.transform(doc.frame, doc.width, doc.height).mapRect(QRectF(dirty)).toAlignedRect().adjusted(-2, -2, 2, 2)
        r = r.intersected(QRect(0, 0, doc.width, doc.height))
        if r.isEmpty():
            return
        part = doc.render(override={layer.id: image}, rect=r)
        p = QPainter(self.composite)
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.drawImage(r.topLeft(), part)
        p.end()
        self._scaled = None
        self.update(self.view().mapRect(QRectF(r)).toAlignedRect().adjusted(-2, -2, 2, 2))

    # ------------------------------------------------------------------ view transform
    def view(self):
        doc = self.doc
        t = QTransform()
        t.translate(self.width() / 2 + self.pan.x(), self.height() / 2 + self.pan.y())
        t.rotate(self.angle)
        t.scale(-self.zoom if self.mirror else self.zoom, self.zoom)
        if doc is not None:
            t.translate(-doc.width / 2, -doc.height / 2)
        return t

    def to_canvas(self, pos):
        inv, _ = self.view().inverted()
        return inv.map(QPointF(pos))

    def fit(self):
        if self.doc is None:
            return
        d = self.doc
        self.angle, self.pan, self.mirror = 0.0, QPointF(0, 0), self.mirror
        self.zoom = max(ZOOM_MIN, min((self.width() - 60) / d.width, (self.height() - 60) / d.height, 4.0))
        self.view_changed.emit()
        self.update()

    def set_zoom(self, z, anchor=None):
        if self.doc is None:
            return
        anchor = QPointF(anchor) if anchor is not None else QPointF(self.width() / 2, self.height() / 2)
        before = self.to_canvas(anchor)
        self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, z))
        after = self.view().map(before)
        self.pan += anchor - after
        self.view_changed.emit()
        self.update()

    def step_zoom(self, direction, anchor=None):
        steps = [0.05, 0.1, 0.125, 0.167, 0.25, 0.333, 0.5, 0.667, 1, 1.5, 2, 3, 4, 6, 8, 12, 16, 24, 32]
        if direction > 0:
            z = next((s for s in steps if s > self.zoom * 1.01), steps[-1])
        else:
            z = next((s for s in reversed(steps) if s < self.zoom * 0.99), steps[0])
        self.set_zoom(z, anchor)

    def rotate_view(self, deg, absolute=False):
        centre = QPointF(self.width() / 2, self.height() / 2)
        before = self.to_canvas(centre)
        self.angle = (deg if absolute else self.angle + deg) % 360
        self.pan += centre - self.view().map(before)
        self.view_changed.emit()
        self.update()

    def flip_view(self):
        self.mirror = not self.mirror
        self.view_changed.emit()
        self.update()

    # ------------------------------------------------------------------ painting
    def paintEvent(self, e):
        p = QPainter(self)
        c = self.win.theme
        p.fillRect(self.rect(), QColor(c["canvas"]))
        if self.doc is None or self.composite is None:
            p.end()
            return
        doc = self.doc
        v = self.view()
        p.setTransform(v)
        page = QRectF(0, 0, doc.width, doc.height)
        # shadow + checkerboard for transparent documents
        p.fillRect(page.translated(3 / self.zoom, 4 / self.zoom), QColor(0, 0, 0, 30))
        if not doc.background:
            # checkerboard in screen space (constant cell size at any zoom)
            p.fillRect(page, QColor(c["checker_a"]))
            p.save()
            p.resetTransform()
            poly = v.map(page)
            p.setClipRegion(QRegion(poly.toPolygon()))
            br = poly.boundingRect().toAlignedRect().intersected(self.rect())
            cell = 10
            dark = QColor(c["checker_b"])
            for yy in range(br.top() - br.top() % cell, br.bottom() + cell, cell):
                for xx in range(br.left() - br.left() % cell, br.right() + cell, cell):
                    if (xx // cell + yy // cell) % 2:
                        p.fillRect(xx, yy, cell, cell, dark)
            p.restore()
        p.setRenderHint(QPainter.SmoothPixmapTransform, self.zoom < 2)
        if self.zoom < 0.75:
            # thin lines survive zooming out: draw a smoothly downscaled copy (cached per zoom)
            k = self.zoom
            if self._scaled is None or abs(self._scaled[0] - k) > 1e-6:
                w = max(1, round(doc.width * k))
                h = max(1, round(doc.height * k))
                self._scaled = (k, self.composite.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
            img = self._scaled[1]
            p.save()
            p.scale(doc.width / img.width(), doc.height / img.height())
            p.drawImage(QPointF(0, 0), img)
            p.restore()
        else:
            p.drawImage(QPointF(0, 0), self.composite)
        # selection outline
        if doc.has_selection():
            p.setBrush(Qt.NoBrush)
            pen = QPen(QColor(255, 255, 255, 230), 1)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.drawPath(doc.selection)
            dash = QPen(QColor(20, 20, 19), 1, Qt.DashLine)
            dash.setCosmetic(True)
            p.setPen(dash)
            p.drawPath(doc.selection)
        p.setRenderHint(QPainter.Antialiasing)
        tool = self.current_tool()
        tool.overlay(p, self.zoom)
        # brush outline
        if self.hover is not None and tool.paints and self.underMouse() and not self._pan_drag:
            brush = self.win.eraser_brush if tool.key == "eraser" else self.win.brush
            pen = QPen(QColor(c["text"]), 1)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            r = max(0.5, brush.size / 2)
            p.drawEllipse(self.hover, r, r)
            pen2 = QPen(QColor(255, 255, 255, 160), 1)
            pen2.setCosmetic(True)
            p.setPen(pen2)
            p.drawEllipse(self.hover, r + 1 / self.zoom, r + 1 / self.zoom)
        p.end()

    # ------------------------------------------------------------------ input
    def current_tool(self):
        if self._temp is not None:
            return self._temp
        if self._space:
            return self.win.tool_by_key("hand")
        return self.win.tool

    def _press(self, pos, button, mods, pressure):
        if self.doc is None:
            return
        self.setFocus()
        tool = self.current_tool()
        if button == Qt.MiddleButton or tool.key == "hand":
            self._pan_drag = (QPointF(pos), QPointF(self.pan))
            self.setCursor(Qt.ClosedHandCursor)
            return
        if tool.key == "rotate":
            c = QPointF(self.width() / 2, self.height() / 2)
            self._rot_drag = (math.degrees(math.atan2(pos.y() - c.y(), pos.x() - c.x())), self.angle)
            return
        if tool.key == "zoom":
            self.step_zoom(-1 if mods & Qt.AltModifier or button == Qt.RightButton else 1, pos)
            return
        if mods & Qt.AltModifier and tool.key in ("brush", "fill", "gradient", "line", "rect", "ellipse", "tone"):
            tool = self._temp = self.win.tool_by_key("eyedropper")
        self._tool = tool
        tool.press(self.to_canvas(pos), button, mods, pressure)

    def _move(self, pos, buttons, mods, pressure):
        if self.doc is None:
            return
        if self._pan_drag is not None:
            start, pan = self._pan_drag
            self.pan = pan + (QPointF(pos) - start)
            self.view_changed.emit()
            self.update()
            return
        if self._rot_drag is not None:
            c = QPointF(self.width() / 2, self.height() / 2)
            a0, base = self._rot_drag
            a = math.degrees(math.atan2(pos.y() - c.y(), pos.x() - c.x()))
            ang = base + a - a0
            if mods & Qt.ShiftModifier:
                ang = round(ang / 15) * 15
            self.rotate_view(ang, absolute=True)
            return
        pt = self.to_canvas(pos)
        old = self.hover
        self.hover = pt
        self.hovered.emit(pt)
        if self._tool is not None and buttons & (Qt.LeftButton | Qt.RightButton):
            self._tool.move(pt, buttons, mods, pressure)
        else:
            self.current_tool().hover(pt)
        if self.current_tool().paints:
            r = max(4.0, self.win.brush.size / 2 + 3)
            v = self.view()
            for q in (old, pt):
                if q is not None:
                    self.update(v.mapRect(QRectF(q.x() - r, q.y() - r, 2 * r, 2 * r)).toAlignedRect().adjusted(-3, -3, 3, 3))

    def _release(self, pos, button, mods, pressure):
        if self._pan_drag is not None:
            self._pan_drag = None
            self.setCursor(self.current_tool().cursor)
            return
        if self._rot_drag is not None:
            self._rot_drag = None
            return
        if self._tool is not None:
            self._tool.release(self.to_canvas(pos), button, mods, pressure)
            self._tool = None
        self._temp = None

    def mousePressEvent(self, e):
        if not self._tablet:
            self._press(e.position(), e.button(), e.modifiers(), 1.0)

    def mouseMoveEvent(self, e):
        if not self._tablet:
            self._move(e.position(), e.buttons(), e.modifiers(), 1.0)

    def mouseReleaseEvent(self, e):
        if not self._tablet:
            self._release(e.position(), e.button(), e.modifiers(), 1.0)

    def mouseDoubleClickEvent(self, e):
        if self.current_tool().key == "rotate":
            self.rotate_view(0, absolute=True)
        else:
            self.mousePressEvent(e)

    def tabletEvent(self, e):
        t = e.type()
        pressure = max(0.02, e.pressure())
        if t == e.Type.TabletPress:
            self._tablet = True
            self._press(e.position(), e.button(), e.modifiers(), pressure)
        elif t == e.Type.TabletMove:
            self._move(e.position(), e.buttons(), e.modifiers(), pressure)
        elif t == e.Type.TabletRelease:
            self._release(e.position(), e.button(), e.modifiers(), pressure)
            self._tablet = False
        e.accept()

    def wheelEvent(self, e):
        if self.doc is None:
            return
        pd = e.pixelDelta()
        mods = e.modifiers()
        if not pd.isNull() and not (mods & (Qt.ControlModifier | Qt.MetaModifier)):
            self.pan += QPointF(pd.x(), pd.y())
            self.view_changed.emit()
            self.update()
            return
        if mods & Qt.ShiftModifier:
            self.pan += QPointF(e.angleDelta().y() / 2, 0)
            self.update()
            return
        factor = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        self.set_zoom(self.zoom * factor, e.position())

    def event(self, e):
        if e.type() == e.Type.NativeGesture and self.doc is not None:
            g = e.gestureType()
            if g == Qt.ZoomNativeGesture:
                self.set_zoom(self.zoom * (1 + e.value()), e.position())
                return True
            if g == Qt.RotateNativeGesture:
                self.rotate_view(e.value())
                return True
        if e.type() == e.Type.ShortcutOverride and e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape):
            if self.current_tool().key in ("transform", "bubble"):
                e.accept()
                return True
        return super().event(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Space and not e.isAutoRepeat():
            self._space = True
            self.setCursor(Qt.OpenHandCursor)
            return
        if self.current_tool().key_press(e.key()):
            return
        if e.key() == Qt.Key_Escape and self._tool is not None:
            self._tool.cancel()
            self._tool = None
            return
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key_Space and not e.isAutoRepeat():
            self._space = False
            self.setCursor(self.current_tool().cursor)
            return
        super().keyReleaseEvent(e)

    def enterEvent(self, e):
        self.setCursor(self.current_tool().cursor)

    def leaveEvent(self, e):
        self.hover = None
        self.hovered.emit(None)
        self.update()
