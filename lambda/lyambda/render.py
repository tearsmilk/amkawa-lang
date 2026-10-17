"""Painting nodes with QPainter: fills (solid, gradients, images), strokes with inside / outside alignment,
arrowheads, drop shadows, blend modes, masks, text, FigJam objects and connectors."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF,
                           QRadialGradient, QTransform)

from . import text as textlib
from .model import FRAMELIKE, is_open, local_transform, shape_path

BLEND = {
    "normal": QPainter.CompositionMode_SourceOver, "multiply": QPainter.CompositionMode_Multiply,
    "screen": QPainter.CompositionMode_Screen, "overlay": QPainter.CompositionMode_Overlay,
    "darken": QPainter.CompositionMode_Darken, "lighten": QPainter.CompositionMode_Lighten,
    "difference": QPainter.CompositionMode_Difference,
}
BLEND_TITLES = [("normal", "Обычный"), ("multiply", "Умножение"), ("screen", "Экран"), ("overlay", "Перекрытие"),
                ("darken", "Затемнение"), ("lighten", "Осветление"), ("difference", "Разница")]


def qcolor(c, opacity=1.0):
    q = QColor(c or "#000000")
    if not q.isValid():
        q = QColor("#000000")
    q.setAlphaF(max(0.0, min(1.0, q.alphaF() * opacity)))
    return q


def gradient_brush(paint, rect):
    stops = paint.get("stops") or [[0, "#FFFFFF"], [1, "#000000"]]
    op = paint.get("opacity", 1.0)
    if paint["type"] == "radial":
        g = QRadialGradient(rect.center(), max(1.0, max(rect.width(), rect.height()) / 2))
        # stretch the circle into the node's aspect ratio
        brush_t = QTransform()
        if rect.width() and rect.height():
            c = rect.center()
            sx = rect.width() / max(rect.width(), rect.height())
            sy = rect.height() / max(rect.width(), rect.height())
            brush_t.translate(c.x(), c.y())
            brush_t.scale(sx, sy)
            brush_t.translate(-c.x(), -c.y())
    else:
        a = math.radians(paint.get("angle", 90.0))
        c = rect.center()
        half = (abs(rect.width() * math.cos(a)) + abs(rect.height() * math.sin(a))) / 2
        v = QPointF(math.cos(a) * half, math.sin(a) * half)
        g = QLinearGradient(c - v, c + v)
        brush_t = None
    for pos, col in stops:
        g.setColorAt(max(0.0, min(1.0, float(pos))), qcolor(col, op))
    b = QBrush(g)
    if brush_t is not None:
        b.setTransform(brush_t)
    return b


def paint_brush(paint, rect):
    t = paint.get("type", "solid")
    if t == "solid":
        return QBrush(qcolor(paint.get("color"), paint.get("opacity", 1.0)))
    if t in ("linear", "radial"):
        return gradient_brush(paint, rect)
    return None


def first_color(paints, default="#000000"):
    for p in paints:
        if p.get("visible", True) and p.get("type", "solid") == "solid":
            return p.get("color", default)
    return default


def blur_image(img, radius):
    """Cheap gaussian-ish blur: down-scale then smooth up-scale (twice)."""
    if radius < 1:
        return img
    w, h = img.width(), img.height()
    f = max(1.0, radius / 2.0)
    small = img.scaled(max(1, int(w / f)), max(1, int(h / f)), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    small = small.scaled(max(1, int(w / f / 2)), max(1, int(h / f / 2)), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


class Renderer:
    def __init__(self, doc):
        self.doc = doc
        self._images = {}
        self._shadows = {}

    # ------------------------------------------------------------------ resources
    def image(self, ref):
        img = self._images.get(ref)
        if img is None:
            data = self.doc.images.get(ref)
            img = QImage.fromData(data) if data else QImage()
            if img.isNull():
                img = QImage(2, 2, QImage.Format_ARGB32)
                img.fill(QColor("#C9C4B6"))
            self._images[ref] = img
        return img

    def drop_caches(self):
        self._shadows.clear()

    # ------------------------------------------------------------------ painting
    def paint_children(self, p, parent, hidden=()):
        clip_saved = 0
        for c in parent.children:
            if c.id in hidden or not c.visible:
                continue
            if c.mask:
                p.save()
                clip_saved += 1
                p.setClipPath(local_transform(c).map(shape_path(c)), Qt.IntersectClip)
                continue
            self.paint(p, c, hidden)
        for _ in range(clip_saved):
            p.restore()

    def paint(self, p, n, hidden=()):
        if not n.visible or n.id in hidden:
            return
        p.save()
        p.setTransform(local_transform(n), True)
        if n.opacity < 1:
            p.setOpacity(p.opacity() * max(0.0, n.opacity))
        if n.blend != "normal":
            p.setCompositionMode(BLEND.get(n.blend, QPainter.CompositionMode_SourceOver))
        t = n.type
        if t == "group":
            self.paint_children(p, n, hidden)
            p.restore()
            return
        path = shape_path(n)
        rect = QRectF(0, 0, n.w, n.h)
        for e in n.effects:
            if e.get("type") == "shadow" and e.get("visible", True):
                self.draw_shadow(p, n, path, e)
        if t == "sticky":
            self.draw_sticky_shadow(p, rect)
        if not (t == "path" and is_open(n)) and t not in ("connector", "text"):
            self.draw_fills(p, n, path, rect)
        if t in FRAMELIKE:
            p.save()
            if n.clip:
                p.setClipPath(path, Qt.IntersectClip)
            self.paint_children(p, n, hidden)
            p.restore()
        elif t == "text":
            self.draw_text(p, n)
        elif t in ("sticky", "shape"):
            self.draw_box_text(p, n)
        elif t == "stamp":
            self.draw_stamp(p, n)
        self.draw_strokes(p, n, path)
        if t == "section":
            self.draw_section_title(p, n)
        if t == "connector" and n.text:
            self.draw_connector_label(p, n, path)
        for e in n.effects:
            if e.get("type") == "inner" and e.get("visible", True):
                self.draw_inner_shadow(p, path, e)
        p.restore()

    def draw_fills(self, p, n, path, rect):
        for paint in n.fills:
            if not paint.get("visible", True):
                continue
            if paint.get("type") == "image":
                self.draw_image_fill(p, paint, path, rect)
                continue
            b = paint_brush(paint, rect)
            if b is not None:
                p.fillPath(path, b)

    def draw_image_fill(self, p, paint, path, rect):
        img = self.image(paint.get("ref"))
        if img.isNull() or rect.width() <= 0 or rect.height() <= 0:
            return
        p.save()
        p.setClipPath(path, Qt.IntersectClip)
        p.setOpacity(p.opacity() * paint.get("opacity", 1.0))
        mode = paint.get("mode", "fill")
        iw, ih = img.width(), img.height()
        if mode == "tile":
            b = QBrush(img)
            s = paint.get("scale", 1.0)
            b.setTransform(QTransform.fromScale(s, s))
            p.fillRect(rect, b)
        elif mode == "stretch":
            p.drawImage(rect, img)
        else:
            k = (max if mode == "fill" else min)(rect.width() / iw, rect.height() / ih)
            tw, th = iw * k, ih * k
            p.drawImage(QRectF(rect.center().x() - tw / 2, rect.center().y() - th / 2, tw, th), img)
        p.restore()

    def stroke_pen(self, n, paint, path_rect, width):
        b = paint_brush(paint, path_rect)
        if b is None:
            return None
        pen = QPen(b, width)
        pen.setJoinStyle(Qt.MiterJoin if n.type in ("rect", "frame", "component", "instance", "polygon", "star")
                         else Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap if is_open(n) else Qt.FlatCap)
        if n.dash > 0 and width > 0:
            pen.setDashPattern([max(0.1, n.dash / width), max(0.1, n.dash / width)])
            pen.setCapStyle(Qt.FlatCap)
        return pen

    def draw_strokes(self, p, n, path):
        if n.stroke_width <= 0:
            return
        paints = [s for s in n.strokes if s.get("visible", True)]
        if not paints:
            return
        rect = QRectF(0, 0, n.w, n.h) if n.type != "connector" else path.boundingRect()
        align = "center" if is_open(n) or n.type in ("text", "group") else n.stroke_align
        w = n.stroke_width
        for paint in paints:
            pen = self.stroke_pen(n, paint, rect, w * (2 if align != "center" else 1))
            if pen is None:
                continue
            p.save()
            if align == "inside":
                p.setClipPath(path, Qt.IntersectClip)
            elif align == "outside":
                outer = QPainterPath()
                outer.addRect(path.boundingRect().adjusted(-w * 2 - 2, -w * 2 - 2, w * 2 + 2, w * 2 + 2))
                p.setClipPath(outer.subtracted(path), Qt.IntersectClip)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
            p.restore()
            if is_open(n):
                self.draw_arrows(p, n, path, paint)

    def draw_arrows(self, p, n, path, paint):
        if path.elementCount() < 2:
            return
        col = qcolor(paint.get("color", "#000000"), paint.get("opacity", 1.0))
        size = max(8.0, n.stroke_width * 4)
        for which, style in (("end", n.arrow_end), ("start", n.arrow_start)):
            if style in ("none", "", None):
                continue
            pct = 1.0 if which == "end" else 0.0
            tip = path.pointAtPercent(pct)
            back = path.pointAtPercent(max(0.0, min(1.0, pct - 0.01 if which == "end" else 0.01)))
            if n.type == "connector" and path.length() > 0:  # last segment direction is exact for polylines
                i = path.elementCount() - 2 if which == "end" else 1
                e = path.elementAt(i)
                back = QPointF(e.x, e.y)
            ang = math.atan2(tip.y() - back.y(), tip.x() - back.x())
            l = QPointF(math.cos(ang + 2.6) * size, math.sin(ang + 2.6) * size)
            r = QPointF(math.cos(ang - 2.6) * size, math.sin(ang - 2.6) * size)
            p.save()
            if style == "arrow":
                p.setPen(Qt.NoPen)
                p.setBrush(col)
                p.drawPolygon(QPolygonF([tip, tip + l, tip + r]))
            elif style == "line":
                pen = QPen(col, n.stroke_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                p.setPen(pen)
                p.drawPolyline(QPolygonF([tip + l, tip, tip + r]))
            elif style == "circle":
                p.setPen(Qt.NoPen)
                p.setBrush(col)
                p.drawEllipse(tip, size / 2.2, size / 2.2)
            elif style == "square":
                p.setPen(Qt.NoPen)
                p.setBrush(col)
                p.drawRect(QRectF(tip.x() - size / 2.5, tip.y() - size / 2.5, size / 1.25, size / 1.25))
            p.restore()

    def draw_shadow(self, p, n, path, e):
        blur = max(0.0, float(e.get("blur", 8)))
        spread = float(e.get("spread", 0))
        col = qcolor(e.get("color", "#000000"), e.get("opacity", 0.25))
        sp = path
        if spread:
            from PySide6.QtGui import QPainterPathStroker
            st = QPainterPathStroker()
            st.setWidth(abs(spread) * 2)
            sp = path.united(st.createStroke(path)) if spread > 0 else path.subtracted(st.createStroke(path))
        r = sp.boundingRect().adjusted(-blur * 1.5 - 2, -blur * 1.5 - 2, blur * 1.5 + 2, blur * 1.5 + 2)
        if r.width() <= 0 or r.height() <= 0:
            return
        key = (n.id, n.type, round(n.w, 1), round(n.h, 1), n.radius, n.shape, len(n.paths), n.count,
               blur, spread, col.rgba())
        img = self._shadows.get(key)
        if img is None:
            scale = min(1.0, 600.0 / max(r.width(), r.height()))
            img = QImage(max(1, int(r.width() * scale)), max(1, int(r.height() * scale)),
                         QImage.Format_ARGB32_Premultiplied)
            img.fill(Qt.transparent)
            q = QPainter(img)
            q.setRenderHint(QPainter.Antialiasing)
            q.scale(scale, scale)
            q.translate(-r.x(), -r.y())
            q.fillPath(sp, col)
            q.end()
            img = blur_image(img, blur * scale)
            if len(self._shadows) > 400:
                self._shadows.clear()
            self._shadows[key] = img
        p.drawImage(r.translated(e.get("x", 0), e.get("y", 4)), img)

    def draw_inner_shadow(self, p, path, e):
        col = qcolor(e.get("color", "#000000"), e.get("opacity", 0.25))
        p.save()
        p.setClipPath(path, Qt.IntersectClip)
        pen = QPen(col, max(1.0, e.get("blur", 6)))
        p.setPen(pen)
        p.translate(e.get("x", 0), e.get("y", 2))
        p.drawPath(path)
        p.restore()

    def draw_sticky_shadow(self, p, rect):
        p.save()
        p.setPen(Qt.NoPen)
        for i, a in enumerate((26, 16, 8)):
            p.setBrush(QColor(0, 0, 0, a))
            p.drawRect(rect.adjusted(2 + i, 4 + i * 2, -2 - i, 3 + i * 2))
        p.restore()

    def draw_text(self, p, n):
        width = None if n.sizing == "auto_w" else n.w
        block = textlib.node_block(n, width)
        origin = QPointF(0, 0)
        if n.sizing == "fixed" and n.valign != "top":
            origin = QPointF(0, (n.h - block.h) / (2 if n.valign == "center" else 1))
        self._text_with_paints(p, n, block, origin, n.fills)

    def _text_with_paints(self, p, n, block, origin, paints):
        rect = QRectF(0, 0, n.w, n.h)
        drew = False
        for paint in paints:
            if not paint.get("visible", True):
                continue
            b = paint_brush(paint, rect)
            if b is None:
                continue
            p.setPen(QPen(b, 1))
            block.draw(p, origin)
            drew = True
        if not drew and not paints:
            pass

    def draw_box_text(self, p, n):
        if not n.text:
            return
        block, pad, _ = textlib.box_block(n)
        avail_h = n.h - 2 * pad
        y = pad
        if n.valign == "center":
            y = pad + (avail_h - block.h) / 2
        elif n.valign == "bottom":
            y = pad + avail_h - block.h
        p.setPen(QPen(qcolor(n.text_color), 1))
        block.draw(p, QPointF(pad, y))

    def draw_stamp(self, p, n):
        f = textlib.make_font("", n.h * 0.55)
        p.setFont(f)
        p.setPen(QColor("#141413"))
        p.drawText(QRectF(0, 0, n.w, n.h), Qt.AlignCenter, n.glyph)

    def draw_section_title(self, p, n):
        f = textlib.make_font(textlib.SERIF_FONT, max(12.0, n.size), 500)
        block = textlib.layout(n.name, f)
        pad = 10.0
        r = QRectF(16, 16, block.w + pad * 2, block.h + pad)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 200))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setPen(QColor("#141413"))
        block.draw(p, QPointF(r.x() + pad, r.y() + pad / 2))

    def draw_connector_label(self, p, n, path):
        mid = path.pointAtPercent(0.5)
        f = textlib.make_font("", n.size)
        block = textlib.layout(n.text, f)
        r = QRectF(mid.x() - block.w / 2 - 8, mid.y() - block.h / 2 - 4, block.w + 16, block.h + 8)
        p.setPen(QPen(QColor("#E3DFD3"), 1))
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(r, 6, 6)
        p.setPen(QColor("#141413"))
        block.draw(p, QPointF(r.x() + 8, r.y() + 4))


def render_image(renderer, nodes, scale=1.0, background=None, bounds=None):
    """Render nodes (in world coordinates) into a QImage cropped to their bounds."""
    from .model import parent_transform, union_rect, world_bounds
    b = bounds or union_rect(world_bounds(n) for n in nodes)
    w = max(1, int(math.ceil(b.width() * scale)))
    h = max(1, int(math.ceil(b.height() * scale)))
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor(background) if background else Qt.transparent)
    p = QPainter(img)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
    base = QTransform.fromScale(scale, scale)
    base.translate(-b.x(), -b.y())
    for n in nodes:
        p.setTransform(parent_transform(n) * base)
        renderer.paint(p, n)
    p.end()
    return img
