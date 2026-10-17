"""Tools. Each tool gets canvas coordinates (QPointF, float) plus pen pressure from the canvas and may
draw a preview overlay in canvas coordinates (`overlay(p, view_scale)`)."""
import math

from PySide6.QtCore import QLineF, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF,
    QRadialGradient, QTransform,
)

from . import imgops
from .brushes import Brush, Stroke, path_points, stroke_path
from .model import layer_point


def cosmetic(color, width=1.0, style=Qt.SolidLine):
    pen = QPen(QColor(color), width, style)
    pen.setCosmetic(True)
    return pen


class Tool:
    key = name = icon = shortcut = hint = ""
    cursor = Qt.CrossCursor
    paints = False

    def __init__(self, win):
        self.win = win

    @property
    def doc(self):
        return self.win.doc

    def press(self, pt, button, mods, pressure):
        pass

    def move(self, pt, buttons, mods, pressure):
        pass

    def release(self, pt, button, mods, pressure):
        pass

    def hover(self, pt):
        pass

    def overlay(self, p, scale):
        pass

    def cancel(self):
        pass

    def key_press(self, key):
        return False

    def editable(self):
        doc = self.doc
        if doc is None:
            return False
        layer = doc.current
        if layer.locked or not layer.visible:
            self.win.status_message("Слой заблокирован или скрыт")
            return False
        return True


# ====================================================================== painting
class BrushTool(Tool):
    key, name, icon, shortcut = "brush", "Кисть", "brush", "B"
    hint = "ПКМ — второй цвет · ⇧ — прямая от прошлой точки · Alt — пипетка · [ ] — размер"
    paints = True
    eraser = False

    def brush(self):
        return self.win.eraser_brush if self.eraser else self.win.brush

    def press(self, pt, button, mods, pressure):
        if not self.editable():
            return
        doc = self.doc
        layer = doc.current
        doc.push(self.name)
        t = layer.transform(doc.frame, doc.width, doc.height)
        inv, _ok = t.inverted()
        clip = inv.map(doc.selection) if doc.has_selection() else None
        scale = math.sqrt(abs(t.determinant())) or 1.0
        brush = self.brush()
        color = self.win.secondary if button == Qt.RightButton else self.win.primary
        self.stroke = Stroke(brush, layer, color, clip, scale)
        lp = layer_point(doc, layer, pt)
        if mods & Qt.ShiftModifier and self.win.last_point is not None:
            self.stroke.add(layer_point(doc, layer, self.win.last_point), pressure)
        self._apply(self.stroke.add(lp, pressure))

    def move(self, pt, buttons, mods, pressure):
        if getattr(self, "stroke", None) is None:
            return
        self._apply(self.stroke.add(layer_point(self.doc, self.doc.current, pt), pressure))

    def release(self, pt, button, mods, pressure):
        s = getattr(self, "stroke", None)
        if s is None:
            return
        s.finish(layer_point(self.doc, self.doc.current, pt), pressure)
        self.doc.current.image = s.preview
        self.stroke = None
        self.win.last_point = QPointF(pt)
        self.win.canvas.stroke_preview(None, None)
        self.win.document_changed(thumbs=True)

    def _apply(self, dirty):
        self.win.canvas.stroke_preview(self.doc.current, self.stroke.preview, dirty)

    def cancel(self):
        if getattr(self, "stroke", None) is not None:
            self.stroke = None
            self.doc.undo()
            self.doc.redo_stack.clear()
            self.win.canvas.stroke_preview(None, None)
            self.win.document_changed()


class EraserTool(BrushTool):
    key, name, icon, shortcut = "eraser", "Ластик", "eraser", "E"
    hint = "Стирает текущей кистью-ластиком (выберите в «Кистях»)"
    eraser = True


class EyedropperTool(Tool):
    key, name, icon, shortcut = "eyedropper", "Пипетка", "eyedropper", "I"
    hint = "ЛКМ — основной цвет, ПКМ — второй · берёт цвет со всего изображения"

    def press(self, pt, button, mods, pressure):
        self.pick(pt, button)

    def move(self, pt, buttons, mods, pressure):
        self.pick(pt, Qt.RightButton if buttons & Qt.RightButton else Qt.LeftButton)

    def pick(self, pt, button):
        img = self.win.canvas.composite
        if img is None or not img.rect().contains(pt.toPoint()):
            return
        c = img.pixelColor(pt.toPoint())
        if c.alpha():
            c.setAlpha(255)
            self.win.set_color(c, secondary=button == Qt.RightButton)


class FillTool(Tool):
    key, name, icon, shortcut = "fill", "Заливка", "fill", "G"
    hint = "Заливает замкнутую область · допуск и «по всем слоям» — в панели сверху"
    tone = False

    def press(self, pt, button, mods, pressure):
        if not self.editable():
            return
        doc = self.doc
        layer = doc.current
        s = self.win.settings
        lp = layer_point(doc, layer, pt).toPoint()
        if not layer.image.rect().contains(lp):
            return
        ref = doc.render(background=False) if s.get("fill_all_layers") else layer.image
        if s.get("fill_all_layers"):
            ref_pt = pt.toPoint()
            if not ref.rect().contains(ref_pt):
                return
        else:
            ref_pt = lp
        a = imgops.to_array(ref)
        mask = imgops.flood_region(imgops.similar_mask(a, ref_pt.x(), ref_pt.y(), int(s.get("fill_tolerance", 24))),
                                   ref_pt.x(), ref_pt.y())
        if int(s.get("fill_expand", 1)):
            mask = imgops.dilate(mask, int(s.get("fill_expand", 1)))
        path = imgops.mask_to_path(mask)
        if s.get("fill_all_layers"):
            inv, _ = layer.transform(doc.frame, doc.width, doc.height).inverted()
            path = inv.map(path)
        if doc.has_selection():
            inv, _ = layer.transform(doc.frame, doc.width, doc.height).inverted()
            path = path.intersected(inv.map(doc.selection))
        color = self.win.secondary if button == Qt.RightButton else self.win.primary
        doc.push(self.name)
        if self.tone:
            layer.image = imgops.tone_fill(layer.image, path, int(s.get("tone_spacing", 8)), int(s.get("tone_size", 50)),
                                           int(s.get("tone_angle", 45)), color)
        else:
            img = layer.image.copy()
            p = QPainter(img)
            p.setClipPath(path)
            p.setCompositionMode(QPainter.CompositionMode_SourceAtop if layer.alpha_lock else QPainter.CompositionMode_SourceOver)
            p.fillRect(img.rect(), color)
            p.end()
            layer.image = img
        self.win.document_changed(thumbs=True)


class ToneTool(FillTool):
    key, name, icon, shortcut = "tone", "Скринтон", "tone", "T"
    hint = "Щелчок в замкнутой области — заливка точечным скринтоном (шаг, размер точки — сверху)"
    tone = True


class GradientTool(Tool):
    key, name, icon, shortcut = "gradient", "Градиент", "gradient", "⇧G"
    hint = "Протяните: основной → второй цвет · «Радиальный», «В прозрачность» — сверху"

    def press(self, pt, button, mods, pressure):
        if self.editable():
            self.a = self.b = QPointF(pt)

    def move(self, pt, buttons, mods, pressure):
        if getattr(self, "a", None) is not None:
            self.b = QPointF(pt)
            self.win.canvas.update()

    def overlay(self, p, scale):
        if getattr(self, "a", None) is not None:
            p.setPen(cosmetic(self.win.theme["text"], 1.5))
            p.drawLine(QLineF(self.a, self.b))

    def release(self, pt, button, mods, pressure):
        if getattr(self, "a", None) is None:
            return
        doc, layer, s = self.doc, self.doc.current, self.win.settings
        a, b = layer_point(doc, layer, self.a), layer_point(doc, layer, self.b)
        self.a = None
        c1 = QColor(self.win.primary)
        c2 = QColor(self.win.secondary)
        if s.get("gradient_to_transparent") or c2.alpha() == 0:
            c2 = QColor(c1)
            c2.setAlpha(0)
        if s.get("gradient_radial"):
            g = QRadialGradient(a, max(1.0, QLineF(a, b).length()))
        else:
            g = QLinearGradient(a, b)
        g.setColorAt(0, c1)
        g.setColorAt(1, c2)
        doc.push(self.name)
        img = layer.image.copy()
        p = QPainter(img)
        if doc.has_selection():
            inv, _ = layer.transform(doc.frame, doc.width, doc.height).inverted()
            p.setClipPath(inv.map(doc.selection))
        p.setCompositionMode(QPainter.CompositionMode_SourceAtop if layer.alpha_lock else QPainter.CompositionMode_SourceOver)
        p.fillRect(img.rect(), QBrush(g))
        p.end()
        layer.image = img
        self.win.document_changed(thumbs=True)


# ====================================================================== shapes
class ShapeTool(Tool):
    key, name, icon, shortcut = "line", "Линия", "line", "L"
    hint = "⇧ — углы по 45° · толщина и цвет — текущей кисти"
    kind = "line"

    def press(self, pt, button, mods, pressure):
        if self.editable():
            self.a = self.b = QPointF(pt)
            self.button = button

    def move(self, pt, buttons, mods, pressure):
        if getattr(self, "a", None) is None:
            return
        b = QPointF(pt)
        if mods & Qt.ShiftModifier:
            d = b - self.a
            if self.kind == "line":
                ang = round(math.atan2(d.y(), d.x()) / (math.pi / 4)) * (math.pi / 4)
                ln = math.hypot(d.x(), d.y())
                b = self.a + QPointF(math.cos(ang) * ln, math.sin(ang) * ln)
            else:
                m = max(abs(d.x()), abs(d.y()))
                b = self.a + QPointF(math.copysign(m, d.x() or 1), math.copysign(m, d.y() or 1))
        self.b = b
        self.win.canvas.update()

    def path(self, a, b):
        path = QPainterPath()
        if self.kind == "line":
            path.moveTo(a)
            path.lineTo(b)
        elif self.kind == "rect":
            path.addRect(QRectF(a, b).normalized())
        else:
            path.addEllipse(QRectF(a, b).normalized())
        return path

    def overlay(self, p, scale):
        if getattr(self, "a", None) is not None:
            p.setPen(cosmetic(self.win.primary, 1.0))
            p.setBrush(Qt.NoBrush)
            p.drawPath(self.path(self.a, self.b))

    def release(self, pt, button, mods, pressure):
        if getattr(self, "a", None) is None:
            return
        doc, layer = self.doc, self.doc.current
        a, b = layer_point(doc, layer, self.a), layer_point(doc, layer, self.b)
        self.a = None
        color = self.win.secondary if self.button == Qt.RightButton else self.win.primary
        path = self.path(a, b)
        doc.push(self.name)
        if self.kind != "line" and self.win.settings.get("shape_fill"):
            img = layer.image.copy()
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawPath(path)
            p.end()
            layer.image = img
        else:
            brush = Brush(**{**self.win.brush.to_dict(), "pressure_size": False, "smoothing": 0, "scatter": 0})
            if brush.mode not in ("paint",):
                brush.mode = "paint"
            if self.kind != "line":
                path.closeSubpath()
            layer.image = stroke_path(brush, layer, color, path_points(path, max(0.5, brush.size * brush.spacing)))
        self.win.document_changed(thumbs=True)


class RectTool(ShapeTool):
    key, name, icon, shortcut, kind = "rect", "Прямоугольник", "rect", "U", "rect"
    hint = "⇧ — квадрат · «Залить» сверху — сплошная фигура"


class EllipseTool(ShapeTool):
    key, name, icon, shortcut, kind = "ellipse", "Эллипс", "ellipse", "⇧U", "ellipse"
    hint = "⇧ — круг · «Залить» сверху — сплошная фигура"


# ====================================================================== selection
class SelectTool(Tool):
    key, name, icon, shortcut = "select", "Выделение", "select", "M"
    hint = "⇧ — добавить · Alt — вычесть · щелчок — снять выделение"
    shape = "rect"

    def press(self, pt, button, mods, pressure):
        if self.doc is None:
            return
        self.a = self.b = QPointF(pt)
        self.mods = mods
        self.poly = [QPointF(pt)]

    def move(self, pt, buttons, mods, pressure):
        if getattr(self, "a", None) is None:
            return
        self.b = QPointF(pt)
        if self.shape == "lasso":
            self.poly.append(QPointF(pt))
        self.win.canvas.update()

    def path(self):
        path = QPainterPath()
        if self.shape == "lasso":
            if len(self.poly) > 2:
                path.addPolygon(QPolygonF(self.poly))
                path.closeSubpath()
        elif self.shape == "ellipse":
            path.addEllipse(QRectF(self.a, self.b).normalized())
        else:
            path.addRect(QRectF(self.a, self.b).normalized())
        return path

    def overlay(self, p, scale):
        if getattr(self, "a", None) is not None:
            p.setBrush(Qt.NoBrush)
            p.setPen(cosmetic("#FFFFFF", 1))
            p.drawPath(self.path())
            p.setPen(cosmetic("#141413", 1, Qt.DashLine))
            p.drawPath(self.path())

    def release(self, pt, button, mods, pressure):
        if getattr(self, "a", None) is None:
            return
        doc = self.doc
        moved = QLineF(self.a, self.b).length() > 2
        path = self.path()
        self.a = None
        doc.push("Выделение")
        if not moved:
            doc.selection = QPainterPath()
        elif self.mods & Qt.ShiftModifier and doc.has_selection():
            doc.selection = doc.selection.united(path)
        elif self.mods & Qt.AltModifier and doc.has_selection():
            doc.selection = doc.selection.subtracted(path)
        else:
            doc.selection = path
        self.win.selection_changed()


class EllipseSelectTool(SelectTool):
    key, name, icon, shortcut, shape = "select_ellipse", "Овальное выделение", "select_ellipse", "⇧M", "ellipse"


class LassoTool(SelectTool):
    key, name, icon, shortcut, shape = "lasso", "Лассо", "lasso", "Q", "lasso"
    hint = "Обведите область · ⇧ — добавить · Alt — вычесть"


class WandTool(Tool):
    key, name, icon, shortcut = "wand", "Волшебная палочка", "wand", "W"
    hint = "Выделяет область похожего цвета (допуск, «по всем слоям» — сверху)"

    def press(self, pt, button, mods, pressure):
        doc = self.doc
        if doc is None:
            return
        s = self.win.settings
        ref = doc.render(background=False) if s.get("fill_all_layers") else doc.current.image
        p = pt.toPoint()
        if not ref.rect().contains(p):
            return
        a = imgops.to_array(ref)
        mask = imgops.flood_region(imgops.similar_mask(a, p.x(), p.y(), int(s.get("fill_tolerance", 24))), p.x(), p.y())
        path = imgops.mask_to_path(mask)
        doc.push("Волшебная палочка")
        if mods & Qt.ShiftModifier and doc.has_selection():
            path = doc.selection.united(path)
        elif mods & Qt.AltModifier and doc.has_selection():
            path = doc.selection.subtracted(path)
        doc.selection = path
        self.win.selection_changed()


# ====================================================================== move / transform
class MoveTool(Tool):
    key, name, icon, shortcut = "move", "Перемещение", "move", "V"
    cursor = Qt.SizeAllCursor
    hint = "Двигает слой или выделенное · у анимированного слоя ставит ключ позиции на текущем кадре"

    def press(self, pt, button, mods, pressure):
        if not self.editable():
            return
        doc, layer = self.doc, self.doc.current
        self.start = QPointF(pt)
        doc.push("Перемещение")
        self.animated = bool(layer.keys.get("x") or layer.keys.get("y"))
        if self.animated:
            self.x0, self.y0 = layer.value("x", doc.frame), layer.value("y", doc.frame)
            return
        self.base = layer.image
        self.sel = QPainterPath(doc.selection)
        if doc.has_selection():
            inv, _ = layer.transform(doc.frame, doc.width, doc.height).inverted()
            lclip = inv.map(doc.selection)
            self.piece = self.base.copy()
            p = QPainter(self.piece)
            p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            p.fillPath(lclip, QColor(0, 0, 0))
            p.end()
            hole = self.base.copy()
            p = QPainter(hole)
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.fillPath(lclip, QColor(0, 0, 0))
            p.end()
            self.hole = hole
        else:
            self.piece = self.base
            self.hole = None

    def move(self, pt, buttons, mods, pressure):
        if getattr(self, "start", None) is None:
            return
        doc, layer = self.doc, self.doc.current
        d = QPointF(pt) - self.start
        if mods & Qt.ShiftModifier:
            d = QPointF(d.x(), 0) if abs(d.x()) >= abs(d.y()) else QPointF(0, d.y())
        if self.animated:
            layer.set_key("x", doc.frame, round(self.x0 + d.x(), 1))
            layer.set_key("y", doc.frame, round(self.y0 + d.y(), 1))
            self.win.canvas.refresh()
            self.win.timeline.update_view()
            return
        t = layer.transform(doc.frame, doc.width, doc.height)
        inv, _ = t.inverted()
        ld = inv.map(QPointF(pt)) - inv.map(self.start)
        if mods & Qt.ShiftModifier:
            ld = QPointF(ld.x(), 0) if abs(ld.x()) >= abs(ld.y()) else QPointF(0, ld.y())
        out = self.hole.copy() if self.hole is not None else imgops_blank_like(self.base)
        p = QPainter(out)
        p.drawImage(ld, self.piece)
        p.end()
        layer.image = out
        if not self.sel.isEmpty():
            doc.selection = self.sel.translated(d)
        self.win.canvas.refresh()

    def release(self, pt, button, mods, pressure):
        if getattr(self, "start", None) is not None:
            self.start = None
            self.win.document_changed(thumbs=True)


def imgops_blank_like(img):
    from .model import blank

    return blank(img.width(), img.height())


class TransformTool(Tool):
    """Free transform of the current layer (or selection): drag inside — move, corners — scale
    (⇧ — proportionally), outside — rotate. Enter applies, Esc cancels."""
    key, name, icon, shortcut = "transform", "Трансформация", "transform", "⌘T"
    hint = "Внутри — двигать · углы — масштаб (⇧ — пропорц.) · снаружи — поворот · Enter — применить · Esc — отмена"
    HANDLE = 7

    def activate(self):
        doc = self.doc
        self.t = None
        if doc is None or not self.editable():
            return
        layer = doc.current
        from .model import blank

        if doc.has_selection():
            inv, _ = layer.transform(doc.frame, doc.width, doc.height).inverted()
            lclip = inv.map(doc.selection)
            piece = layer.image.copy()
            p = QPainter(piece)
            p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            p.fillPath(lclip, QColor(0, 0, 0))
            p.end()
            hole = layer.image.copy()
            p = QPainter(hole)
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.fillPath(lclip, QColor(0, 0, 0))
            p.end()
        else:
            piece, hole = layer.image, blank(layer.image.width(), layer.image.height())
        bounds = content_bounds(piece)
        if bounds.isEmpty():
            self.win.status_message("Слой пуст — нечего трансформировать")
            return
        doc.push("Трансформация")
        self.piece, self.hole, self.box = piece, hole, QRectF(bounds)
        self.t = QTransform()
        self.drag = None
        self._render()

    def _render(self):
        out = self.hole.copy()
        p = QPainter(out)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setTransform(self.t)
        p.drawImage(0, 0, self.piece)
        p.end()
        self.doc.current.image = out
        self.win.canvas.refresh()

    def _corners(self):
        b = self.box
        return [self.t.map(q) for q in (b.topLeft(), b.topRight(), b.bottomRight(), b.bottomLeft())]

    def _lp(self, pt):
        return layer_point(self.doc, self.doc.current, pt)

    def press(self, pt, button, mods, pressure):
        if getattr(self, "t", None) is None:
            self.activate()
            if getattr(self, "t", None) is None:
                return
        lp = self._lp(pt)
        corners = self._corners()
        scale = self.win.canvas.zoom
        tol = self.HANDLE * 1.6 / scale
        self.drag = None
        for i, c in enumerate(corners):
            if QLineF(c, lp).length() <= tol:
                self.drag = ("scale", i)
                break
        if self.drag is None:
            poly = QPolygonF(corners)
            self.drag = ("move", None) if poly.containsPoint(lp, Qt.OddEvenFill) else ("rotate", None)
        self.start, self.t0 = lp, QTransform(self.t)

    def move(self, pt, buttons, mods, pressure):
        if getattr(self, "drag", None) is None or self.t is None:
            return
        lp = self._lp(pt)
        kind, idx = self.drag
        if kind == "move":
            d = lp - self.start
            self.t = self.t0 * QTransform.fromTranslate(d.x(), d.y())
        elif kind == "rotate":
            c = self.t0.map(self.box.center())
            a0 = math.degrees(math.atan2(self.start.y() - c.y(), self.start.x() - c.x()))
            a1 = math.degrees(math.atan2(lp.y() - c.y(), lp.x() - c.x()))
            ang = a1 - a0
            if mods & Qt.ShiftModifier:
                ang = round(ang / 15) * 15
            self.t = self.t0 * QTransform().translate(c.x(), c.y()).rotate(ang).translate(-c.x(), -c.y())
        else:
            inv, _ = self.t0.inverted()
            local = inv.map(lp)
            b = self.box
            corner = [b.topLeft(), b.topRight(), b.bottomRight(), b.bottomLeft()][idx]
            opposite = [b.bottomRight(), b.bottomLeft(), b.topLeft(), b.topRight()][idx]
            sx = (local.x() - opposite.x()) / ((corner.x() - opposite.x()) or 1)
            sy = (local.y() - opposite.y()) / ((corner.y() - opposite.y()) or 1)
            if mods & Qt.ShiftModifier:
                sx = sy = max(sx, sy, key=abs)
            s = QTransform().translate(opposite.x(), opposite.y()).scale(sx or 0.01, sy or 0.01).translate(-opposite.x(), -opposite.y())
            self.t = s * self.t0
        self._render()

    def release(self, pt, button, mods, pressure):
        self.drag = None

    def overlay(self, p, scale):
        if getattr(self, "t", None) is None:
            return
        lt = self.doc.current.transform(self.doc.frame, self.doc.width, self.doc.height)
        corners = [lt.map(c) for c in self._corners()]
        p.setBrush(Qt.NoBrush)
        p.setPen(cosmetic(self.win.theme["accent"], 1.5))
        p.drawPolygon(QPolygonF(corners))
        p.setBrush(QColor("#FFFFFF"))
        h = self.HANDLE / scale
        for c in corners:
            p.drawRect(QRectF(c.x() - h / 2, c.y() - h / 2, h, h))

    def apply(self):
        if getattr(self, "t", None) is not None:
            self.t = None
            self.win.document_changed(thumbs=True)

    def cancel(self):
        if getattr(self, "t", None) is not None:
            self.t = None
            self.doc.undo()
            self.doc.redo_stack.clear()
            self.win.document_changed(thumbs=True)

    def key_press(self, key):
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self.apply()
            return True
        if key == Qt.Key_Escape:
            self.cancel()
            return True
        return False


def content_bounds(img):
    import numpy as np

    a = imgops.to_array(img)[..., 3]
    ys, xs = np.nonzero(a)
    if len(xs) == 0:
        return QRect()
    return QRect(int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))


# ====================================================================== manga
class PanelTool(Tool):
    key, name, icon, shortcut = "panel", "Кадр манги", "panel", "F"
    hint = "Протяните прямоугольник — рамка кадра на слое «Кадры» (толщина — сверху) · ⇧ — квадрат"

    def press(self, pt, button, mods, pressure):
        if self.doc is not None:
            self.a = self.b = QPointF(pt)

    def move(self, pt, buttons, mods, pressure):
        if getattr(self, "a", None) is not None:
            self.b = QPointF(pt)
            self.win.canvas.update()

    def overlay(self, p, scale):
        if getattr(self, "a", None) is not None:
            p.setBrush(Qt.NoBrush)
            p.setPen(cosmetic("#141413", 2))
            p.drawRect(QRectF(self.a, self.b).normalized())

    def release(self, pt, button, mods, pressure):
        if getattr(self, "a", None) is None:
            return
        r = QRectF(self.a, self.b).normalized()
        self.a = None
        if r.width() < 4 or r.height() < 4:
            return
        self.win.draw_panels([r])


class BubbleTool(Tool):
    key, name, icon, shortcut = "bubble", "Реплика", "bubble", "K"
    hint = "Протяните овал реплики, затем щёлкните, куда указывает хвостик (Esc — без хвоста)"

    def press(self, pt, button, mods, pressure):
        if self.doc is None:
            return
        if getattr(self, "pending", None) is not None:
            rect = self.pending
            self.pending = None
            self.win.make_bubble(rect, QPointF(pt))
            return
        self.a = self.b = QPointF(pt)

    def move(self, pt, buttons, mods, pressure):
        if getattr(self, "a", None) is not None:
            self.b = QPointF(pt)
            self.win.canvas.update()
        self.mouse = QPointF(pt)
        if getattr(self, "pending", None) is not None:
            self.win.canvas.update()

    def hover(self, pt):
        self.mouse = QPointF(pt)
        if getattr(self, "pending", None) is not None:
            self.win.canvas.update()

    def overlay(self, p, scale):
        rect = getattr(self, "pending", None)
        if getattr(self, "a", None) is not None:
            rect = QRectF(self.a, self.b).normalized()
        if rect is None:
            return
        tail = getattr(self, "mouse", None) if getattr(self, "pending", None) is not None else None
        p.setPen(cosmetic("#141413", 1.5))
        p.setBrush(QColor(255, 255, 255, 200))
        p.drawPath(bubble_path(rect, tail))

    def release(self, pt, button, mods, pressure):
        if getattr(self, "a", None) is None:
            return
        rect = QRectF(self.a, self.b).normalized()
        self.a = None
        if rect.width() < 12 or rect.height() < 12:
            return
        self.pending = rect
        self.win.status_message("Щёлкните, куда указывает хвостик реплики")

    def key_press(self, key):
        if key == Qt.Key_Escape and getattr(self, "pending", None) is not None:
            rect = self.pending
            self.pending = None
            self.win.make_bubble(rect, None)
            return True
        return False


def bubble_path(rect, tail=None):
    path = QPainterPath()
    path.addEllipse(rect)
    if tail is not None and not rect.contains(tail):
        c = rect.center()
        ang = math.atan2(tail.y() - c.y(), tail.x() - c.x())
        w = max(8.0, min(rect.width(), rect.height()) * 0.16)
        rx, ry = rect.width() / 2 * 0.8, rect.height() / 2 * 0.8
        base = QPointF(c.x() + math.cos(ang) * rx, c.y() + math.sin(ang) * ry)
        normal = QPointF(-math.sin(ang), math.cos(ang)) * w
        tri = QPainterPath()
        tri.moveTo(base + normal)
        tri.quadTo(base + (tail - base) * 0.5 + normal * 0.3, tail)
        tri.quadTo(base + (tail - base) * 0.5 - normal * 0.1, base - normal)
        tri.closeSubpath()
        path = path.united(tri)
    return path.simplified()


class TextTool(Tool):
    key, name, icon, shortcut = "text", "Текст", "text", "⇧T"
    cursor = Qt.IBeamCursor
    hint = "Щелчок — новый текстовый слой (шрифт, размер, вертикально — в диалоге)"

    def press(self, pt, button, mods, pressure):
        if self.doc is not None:
            self.win.add_text(QPointF(pt))


# ====================================================================== view
class HandTool(Tool):
    key, name, icon, shortcut = "hand", "Рука", "hand", "H"
    cursor = Qt.OpenHandCursor
    hint = "Двигает холст · также пробел или средняя кнопка"


class ZoomTool(Tool):
    key, name, icon, shortcut = "zoom", "Масштаб", "zoom", "Z"
    hint = "Щелчок — приблизить · Alt — отдалить"


class RotateViewTool(Tool):
    key, name, icon, shortcut = "rotate", "Поворот холста", "rotate", "R"
    hint = "Тяните — повернуть вид (⇧ — по 15°) · двойной щелчок — сброс"


TOOLS = [BrushTool, EraserTool, FillTool, GradientTool, EyedropperTool, ShapeTool, RectTool, EllipseTool,
         SelectTool, EllipseSelectTool, LassoTool, WandTool, MoveTool, TransformTool,
         PanelTool, BubbleTool, TextTool, ToneTool, HandTool, ZoomTool, RotateViewTool]
