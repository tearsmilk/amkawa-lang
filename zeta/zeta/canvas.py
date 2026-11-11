"""Canvas: the sprite at integer zoom with checkerboard, onion skin, pixel / tile grid, selection outline,
brush preview; routes mouse input to the active tool (space / middle button pan, Alt = eyedropper)."""
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QTransform
from PySide6.QtWidgets import QWidget

from .tools import HandTool, ZoomTool, brush_offsets

ZOOMS = [0.25, 0.5, 1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96]


class Canvas(QWidget):
    hovered = Signal(object)   # QPoint in sprite coords or None
    zoom_changed = Signal(float)

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.doc = None
        self.zoom = 8.0
        self.origin = QPointF(0, 0)   # widget position of the sprite's top-left
        self.hover = None
        self._pan = None
        self._space = False
        self._temp_tool = None
        self._active_tool = None
        self.cache = None
        self.onion = []  # (image, tint colour)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMinimumSize(200, 200)

    # ------------------------------------------------------------------ document
    def set_document(self, doc):
        self.doc = doc
        self.refresh()
        self.fit()

    def refresh(self):
        """Re-composite the current frame (+ onion skin)."""
        if self.doc is None:
            self.cache = None
            self.update()
            return
        sp, f = self.doc.sprite, self.doc.frame
        self.cache = sp.composite(f)
        self.onion = []
        s = self.win.settings
        if s.get("onion") and sp.frames > 1:
            for k in range(1, int(s.get("onion_prev", 1)) + 1):
                if f - k >= 0:
                    self.onion.append((sp.composite(f - k, only=[self.doc.layer]), QColor(200, 70, 60), 0.24 / k))
            for k in range(1, int(s.get("onion_next", 1)) + 1):
                if f + k < sp.frames:
                    self.onion.append((sp.composite(f + k, only=[self.doc.layer]), QColor(60, 110, 200), 0.24 / k))
        self.update()

    # ------------------------------------------------------------------ view
    def fit(self):
        if self.doc is None:
            return
        sp = self.doc.sprite
        avail_w, avail_h = max(100, self.width() - 60), max(100, self.height() - 60)
        z = min(avail_w / sp.width, avail_h / sp.height)
        candidates = [x for x in ZOOMS if x <= z] or [ZOOMS[0]]
        self.zoom = candidates[-1]
        self.center()

    def center(self):
        sp = self.doc.sprite
        self.origin = QPointF((self.width() - sp.width * self.zoom) / 2, (self.height() - sp.height * self.zoom) / 2)
        self.origin = QPointF(round(self.origin.x()), round(self.origin.y()))
        self.zoom_changed.emit(self.zoom)
        self.update()

    def set_zoom(self, z, anchor=None):
        if self.doc is None:
            return
        anchor = anchor if anchor is not None else QPointF(self.width() / 2, self.height() / 2)
        sx = (anchor.x() - self.origin.x()) / self.zoom
        sy = (anchor.y() - self.origin.y()) / self.zoom
        self.zoom = max(ZOOMS[0], min(ZOOMS[-1], z))
        self.origin = QPointF(round(anchor.x() - sx * self.zoom), round(anchor.y() - sy * self.zoom))
        self.zoom_changed.emit(self.zoom)
        self.update()

    def step_zoom(self, direction, anchor=None):
        if direction > 0:
            z = next((x for x in ZOOMS if x > self.zoom), ZOOMS[-1])
        else:
            z = next((x for x in reversed(ZOOMS) if x < self.zoom), ZOOMS[0])
        self.set_zoom(z, anchor)

    def to_sprite(self, pos):
        x = (pos.x() - self.origin.x()) / self.zoom
        y = (pos.y() - self.origin.y()) / self.zoom
        return QPoint(int(x // 1), int(y // 1))

    def sprite_rect(self):
        sp = self.doc.sprite
        return QRectF(self.origin.x(), self.origin.y(), sp.width * self.zoom, sp.height * self.zoom)

    def resizeEvent(self, e):
        if self.doc is not None and e.oldSize().width() > 0:
            d = QPointF((e.size().width() - e.oldSize().width()) / 2, (e.size().height() - e.oldSize().height()) / 2)
            self.origin += d
        super().resizeEvent(e)

    # ------------------------------------------------------------------ painting
    def paintEvent(self, e):
        p = QPainter(self)
        c = self.win.theme
        p.fillRect(self.rect(), QColor(c["canvas"]))
        if self.doc is None or self.cache is None:
            p.end()
            return
        sp = self.doc.sprite
        r = self.sprite_rect()
        # drop shadow
        p.fillRect(r.translated(0, 3).adjusted(-1, 0, 1, 1), QColor(0, 0, 0, 28))
        # checkerboard (screen-space 8 px cells, like Aseprite)
        if self.win.settings.get("checker", True):
            cell = 8
            p.save()
            p.setClipRect(r)
            a, b = QColor(c["checker_a"]), QColor(c["checker_b"])
            x0, y0 = int(r.left()), int(r.top())
            left, top = max(x0, 0), max(y0, 0)
            right, bottom = min(int(r.right()) + 1, self.width()), min(int(r.bottom()) + 1, self.height())
            p.fillRect(QRect(left, top, right - left, bottom - top), a)
            yy = top - ((top - y0) % cell)
            while yy < bottom:
                xx = left - ((left - x0) % cell)
                while xx < right:
                    if ((xx - x0) // cell + (yy - y0) // cell) % 2:
                        p.fillRect(xx, yy, cell, cell, b)
                    xx += cell
                yy += cell
            p.restore()
        else:
            p.fillRect(r, QColor("#FFFFFF"))
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawImage(r, self.cache)
        # onion skin: neighbouring frames of the current layer, tinted red (before) / blue (after), in front
        for img, tint, alpha in self.onion:
            tinted = QImage(img)
            tp = QPainter(tinted)
            tp.setCompositionMode(QPainter.CompositionMode_SourceIn)
            tp.fillRect(tinted.rect(), tint)
            tp.end()
            p.setOpacity(alpha)
            p.drawImage(r, tinted)
        p.setOpacity(1.0)
        # pixel grid
        z = self.zoom
        if self.win.settings.get("pixel_grid", True) and z >= 8:
            pen = QPen(QColor(c["pixel_grid"]))
            pen.setWidth(1)
            p.setPen(pen)
            x_start = max(0, int(-r.left() // z))
            x_end = min(sp.width, int((self.width() - r.left()) // z) + 1)
            y_start = max(0, int(-r.top() // z))
            y_end = min(sp.height, int((self.height() - r.top()) // z) + 1)
            for x in range(x_start, x_end + 1):
                X = int(r.left() + x * z)
                p.drawLine(X, int(max(r.top(), 0)), X, int(min(r.bottom(), self.height())))
            for y in range(y_start, y_end + 1):
                Y = int(r.top() + y * z)
                p.drawLine(int(max(r.left(), 0)), Y, int(min(r.right(), self.width())), Y)
        if self.win.settings.get("grid"):
            g = int(self.win.settings.get("grid_size", 16)) or 16
            pen = QPen(QColor(c["accent"]))
            pen.setWidth(1)
            p.setPen(pen)
            p.setOpacity(0.55)
            for x in range(0, sp.width + 1, g):
                X = int(r.left() + x * z)
                p.drawLine(X, int(r.top()), X, int(r.bottom()))
            for y in range(0, sp.height + 1, g):
                Y = int(r.top() + y * z)
                p.drawLine(int(r.left()), Y, int(r.right()), Y)
            p.setOpacity(1.0)
        # sprite border
        p.setPen(QPen(QColor(c["border"])))
        p.setBrush(Qt.NoBrush)
        p.drawRect(r.adjusted(-0.5, -0.5, 0.5, 0.5))
        # selection outline: white + dashed charcoal
        if self.doc.has_selection():
            self._draw_selection(p)
        # brush preview
        tool = self.current_tool()
        if self.hover is not None and getattr(tool, "draws", False) and self.underMouse():
            size = int(self.win.settings.get("brush_size", 1))
            offs = brush_offsets(size, self.win.settings.get("brush_shape", "square"))
            col = QColor(self.win.colors_for(Qt.LeftButton))
            col.setAlpha(140)
            for dx, dy in offs:
                px = self.hover.x() + dx
                py = self.hover.y() + dy
                p.fillRect(QRectF(r.left() + px * z, r.top() + py * z, z, z), col)
        elif self.hover is not None and self.underMouse() and tool.key in ("bucket", "eyedropper", "wand"):
            pen = QPen(QColor(c["text"]))
            p.setPen(pen)
            p.drawRect(QRectF(r.left() + self.hover.x() * z, r.top() + self.hover.y() * z, z, z))
        p.end()

    def _draw_selection(self, p):
        r = self.sprite_rect()
        path = QPainterPath()
        path.addRegion(self.doc.selection)
        path = path.simplified()
        t = QTransform(self.zoom, 0, 0, self.zoom, r.left(), r.top())
        path = t.map(path)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 230), 1))
        p.drawPath(path)
        dash = QPen(QColor(20, 20, 19), 1)
        dash.setDashPattern([3, 3])
        p.setPen(dash)
        p.drawPath(path)

    # ------------------------------------------------------------------ input
    def current_tool(self):
        if self._temp_tool is not None:
            return self._temp_tool
        if self._space:
            return self.win.tool_by_key("hand")
        return self.win.tool

    def mousePressEvent(self, e):
        if self.doc is None:
            return
        self.setFocus()
        if e.button() == Qt.MiddleButton or (self._space and e.button() == Qt.LeftButton):
            self._pan = (e.position(), QPointF(self.origin))
            self.setCursor(Qt.ClosedHandCursor)
            return
        tool = self.current_tool()
        if e.modifiers() & Qt.AltModifier and (getattr(tool, "draws", False) or tool.key == "bucket"):
            tool = self._temp_tool = self.win.tool_by_key("eyedropper")
        if isinstance(tool, HandTool):
            self._pan = (e.position(), QPointF(self.origin))
            self.setCursor(Qt.ClosedHandCursor)
            return
        if isinstance(tool, ZoomTool):
            self.step_zoom(-1 if e.modifiers() & Qt.AltModifier or e.button() == Qt.RightButton else 1, e.position())
            return
        if e.button() not in (Qt.LeftButton, Qt.RightButton):
            return
        self._active_tool = tool
        tool.press(self.doc, self.to_sprite(e.position()), e.button(), e.modifiers())

    def mouseMoveEvent(self, e):
        if self.doc is None:
            return
        if self._pan is not None:
            start, origin = self._pan
            d = e.position() - start
            self.origin = QPointF(round(origin.x() + d.x()), round(origin.y() + d.y()))
            self.update()
            return
        pt = self.to_sprite(e.position())
        if pt != self.hover:
            self.hover = pt
            self.hovered.emit(pt if self.doc.point_in_sprite(pt) else None)
            self.update()
        if self._active_tool is not None and e.buttons() & (Qt.LeftButton | Qt.RightButton):
            self._active_tool.move(self.doc, pt, e.buttons(), e.modifiers())

    def mouseReleaseEvent(self, e):
        if self._pan is not None:
            self._pan = None
            self.setCursor(self.current_tool().cursor)
            return
        if self._active_tool is not None:
            self._active_tool.release(self.doc, self.to_sprite(e.position()), e.button(), e.modifiers())
            self._active_tool = None
        self._temp_tool = None
        self.setCursor(self.current_tool().cursor)

    def leaveEvent(self, e):
        self.hover = None
        self.hovered.emit(None)
        self.update()

    def wheelEvent(self, e):
        if self.doc is None:
            return
        pd = e.pixelDelta()
        mods = e.modifiers()
        if not pd.isNull() and not (mods & (Qt.ControlModifier | Qt.MetaModifier)):
            # trackpad: two-finger scroll pans, pinch / ⌘ zooms
            self.origin += QPointF(pd.x(), pd.y())
            self.update()
            return
        if mods & Qt.ShiftModifier:
            self.origin += QPointF(e.angleDelta().y() / 2, 0)
            self.update()
            return
        self.step_zoom(1 if e.angleDelta().y() > 0 else -1, e.position())

    def event(self, e):
        # arrows nudge with the Move tool instead of switching frames
        if e.type() == e.Type.ShortcutOverride and e.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down) \
                and self.win.tool.key == "move":
            e.accept()
            return True
        return super().event(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Space and not e.isAutoRepeat():
            self._space = True
            self.setCursor(Qt.OpenHandCursor)
            return
        if e.key() == Qt.Key_Escape and self._active_tool is not None:
            self._active_tool.cancel(self.doc)
            self._active_tool = None
            return
        if e.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down) and self.win.tool.key == "move":
            d = {Qt.Key_Left: QPoint(-1, 0), Qt.Key_Right: QPoint(1, 0), Qt.Key_Up: QPoint(0, -1), Qt.Key_Down: QPoint(0, 1)}[e.key()]
            self.win.nudge(d * (8 if e.modifiers() & Qt.ShiftModifier else 1))
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
