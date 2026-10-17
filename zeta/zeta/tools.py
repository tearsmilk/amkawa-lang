"""Tools: pencil, eraser, eyedropper, bucket, line, rectangle, ellipse, marquee, lasso, magic wand, move, hand, zoom.

A tool receives sprite-pixel coordinates from the canvas. Drawing tools keep the cel as it was when the
stroke began (`base`) plus a mask of touched pixels, and re-composite base + mask on every move — so a
semi-transparent colour does not pile up inside one stroke (like Aseprite), and Esc can cancel.
"""
from array import array

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QBitmap, QColor, QImage, QPainter, QPolygon, QRegion

from .model import FMT, blank


# ---------------------------------------------------------------------- geometry helpers
def line_points(a, b):
    """Bresenham line from a to b inclusive (tuples)."""
    x0, y0 = a
    x1, y1 = b
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    out = []
    while True:
        out.append((x0, y0))
        if x0 == x1 and y0 == y1:
            return out
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def brush_offsets(size, shape):
    size = max(1, int(size))
    if size == 1:
        return [(0, 0)]
    lo = -((size - 1) // 2)
    out = []
    r = size / 2.0
    for dy in range(lo, lo + size):
        for dx in range(lo, lo + size):
            if shape == "circle":
                cx, cy = dx - lo + 0.5 - r, dy - lo + 0.5 - r
                if cx * cx + cy * cy > r * r:
                    continue
            out.append((dx, dy))
    return out


def rect_points(a, b, filled):
    x0, x1 = sorted((a[0], b[0]))
    y0, y1 = sorted((a[1], b[1]))
    if filled:
        return [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]
    pts = [(x, y0) for x in range(x0, x1 + 1)] + [(x, y1) for x in range(x0, x1 + 1)]
    pts += [(x0, y) for y in range(y0, y1 + 1)] + [(x1, y) for y in range(y0, y1 + 1)]
    return pts


def ellipse_points(a, b, filled):
    """Pixel ellipse inscribed in the box a–b (inclusive)."""
    x0, x1 = sorted((a[0], b[0]))
    y0, y1 = sorted((a[1], b[1]))
    w, h = x1 - x0 + 1, y1 - y0 + 1
    if w <= 2 or h <= 2:
        return rect_points(a, b, True)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    rx, ry = w / 2.0, h / 2.0
    spans = {}
    for y in range(y0, y1 + 1):
        dy = (y + 0.5 - (cy + 0.5)) / ry
        if abs(dy) > 1:
            continue
        half = rx * (1 - dy * dy) ** 0.5
        xa = int(round(cx + 0.5 - half))
        xb = int(round(cx + 0.5 + half)) - 1
        xa, xb = max(xa, x0), min(max(xb, xa), x1)
        spans[y] = (xa, xb)
    pts = []
    if filled:
        for y, (xa, xb) in spans.items():
            pts += [(x, y) for x in range(xa, xb + 1)]
        return pts
    ys = sorted(spans)
    for i, y in enumerate(ys):
        xa, xb = spans[y]
        # connect to neighbouring rows so the outline has no gaps
        na = min([spans[ys[j]][0] for j in (i - 1, i + 1) if 0 <= j < len(ys)] + [xa])
        nb = max([spans[ys[j]][1] for j in (i - 1, i + 1) if 0 <= j < len(ys)] + [xb])
        if y in (ys[0], ys[-1]):
            pts += [(x, y) for x in range(xa, xb + 1)]
        else:
            pts += [(x, y) for x in range(xa, max(xa, na) + 1)]
            pts += [(x, y) for x in range(min(xb, nb), xb + 1)]
    return pts


def constrain_45(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    adx, ady = abs(dx), abs(dy)
    if adx > 2 * ady:
        return (b[0], a[1])
    if ady > 2 * adx:
        return (a[0], b[1])
    d = max(adx, ady)
    return (a[0] + (d if dx >= 0 else -d), a[1] + (d if dy >= 0 else -d))


def square_box(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = max(abs(dx), abs(dy))
    return (a[0] + (d if dx >= 0 else -d), a[1] + (d if dy >= 0 else -d))


# ---------------------------------------------------------------------- pixel buffers
def to_array(img):
    img = img.convertToFormat(FMT)
    w, h = img.width(), img.height()
    a = array("I")
    a.frombytes(bytes(img.constBits())[: w * h * 4])
    return a


def from_array(a, w, h):
    return QImage(a.tobytes(), w, h, w * 4, FMT).copy()


def _close(c1, c2, tol):
    if tol == 0:
        return c1 == c2
    if (c1 >> 24) == 0 and (c2 >> 24) == 0:
        return True
    return max(abs((c1 >> s & 255) - (c2 >> s & 255)) for s in (0, 8, 16, 24)) <= tol


def flood_mask(img, x, y, contiguous=True, tolerance=0):
    """Bytearray mask (w*h) of pixels similar to (x, y): contiguous (scanline fill) or global."""
    w, h = img.width(), img.height()
    px = to_array(img)
    target = px[y * w + x]
    mask = bytearray(w * h)
    if not contiguous:
        for i, c in enumerate(px):
            if _close(c, target, tolerance):
                mask[i] = 1
        return mask
    stack = [(x, y)]
    while stack:
        sx, sy = stack.pop()
        row = sy * w
        if mask[row + sx] or not _close(px[row + sx], target, tolerance):
            continue
        l = sx
        while l > 0 and not mask[row + l - 1] and _close(px[row + l - 1], target, tolerance):
            l -= 1
        r = sx
        while r < w - 1 and not mask[row + r + 1] and _close(px[row + r + 1], target, tolerance):
            r += 1
        for i in range(l, r + 1):
            mask[row + i] = 1
        for ny in (sy - 1, sy + 1):
            if 0 <= ny < h:
                nrow = ny * w
                i = l
                while i <= r:
                    if not mask[nrow + i] and _close(px[nrow + i], target, tolerance):
                        stack.append((i, ny))
                        while i <= r and _close(px[nrow + i], target, tolerance):
                            i += 1
                    i += 1
    return mask


def mask_image(mask, w, h, argb=0xFF000000):
    a = array("I", (argb if m else 0 for m in mask))
    return from_array(a, w, h)


def region_from_mask(mask, w, h):
    img = mask_image(mask, w, h)
    return QRegion(QBitmap.fromImage(img.createAlphaMask()))


# ---------------------------------------------------------------------- tools
class Tool:
    key = ""
    name = ""
    icon = ""
    shortcut = ""
    cursor = Qt.CrossCursor
    draws = False      # uses brush options
    hint = ""

    def __init__(self, win):
        self.win = win

    def press(self, doc, pt, button, mods):
        pass

    def move(self, doc, pt, buttons, mods):
        pass

    def release(self, doc, pt, button, mods):
        pass

    def cancel(self, doc):
        pass

    def color(self, button):
        return self.win.colors_for(button)


class _StrokeTool(Tool):
    """Shared base / mask compositing for pencil, eraser, line and shapes."""

    erase = False

    def begin(self, doc, button):
        if doc.layer.locked or not doc.layer.visible:
            self.win.status_message("Слой заблокирован или скрыт")
            self.active = False
            return False
        doc.push(self.name)
        self.active = True
        self.base = doc.editable_image()
        self.w, self.h = doc.sprite.width, doc.sprite.height
        self.argb = QColor(self.color(button)).rgba()
        self.mask = blank(self.w, self.h)
        self.clip = doc.clip_region()
        return True

    def stamp(self, points, clear_first=False):
        if clear_first:
            self.mask = blank(self.w, self.h)
        s = self.win.settings
        size = int(s.get("brush_size", 1)) if self.draws else 1
        offsets = brush_offsets(size, s.get("brush_shape", "square"))
        sym_h, sym_v = self.win.symmetry
        p = QPainter(self.mask)
        col = QColor.fromRgba(self.argb | 0xFF000000 if self.erase else self.argb)
        for (x, y) in points:
            centres = [(x, y)]
            if sym_h:
                centres.append((self.w - 1 - x, y))
            if sym_v:
                centres += [(cx, self.h - 1 - cy) for cx, cy in centres]
            for cx, cy in centres:
                if len(offsets) == 1:
                    p.fillRect(cx, cy, 1, 1, col)
                else:
                    for dx, dy in offsets:
                        p.fillRect(cx + dx, cy + dy, 1, 1, col)
        p.end()

    def commit_preview(self, doc):
        out = self.base.copy()
        p = QPainter(out)
        p.setClipRegion(self.clip)
        if self.erase:
            p.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        elif (self.argb >> 24) == 255:
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.drawImage(0, 0, self.mask)
        p.end()
        doc.set_current(out)
        self.win.canvas_changed()

    def cancel(self, doc):
        if getattr(self, "active", False):
            self.active = False
            doc.set_current(self.base)
            doc.undo_stack.pop() if doc.undo_stack else None
            self.win.canvas_changed()


class PencilTool(_StrokeTool):
    key, name, icon, shortcut = "pencil", "Карандаш", "pencil", "B"
    draws = True
    hint = "ПКМ — второй цвет · ⇧ — линия от прошлой точки · Alt — пипетка"

    def press(self, doc, pt, button, mods):
        if not self.begin(doc, button):
            return
        self.points = []
        start = (pt.x(), pt.y())
        if mods & Qt.ShiftModifier and getattr(self.win, "last_point", None):
            self.points = line_points(self.win.last_point, start)
        else:
            self.points = [start]
        self.stamp(self.points)
        self.commit_preview(doc)

    def move(self, doc, pt, buttons, mods):
        if not getattr(self, "active", False):
            return
        last = self.points[-1]
        cur = (pt.x(), pt.y())
        if cur == last:
            return
        new = line_points(last, cur)[1:]
        perfect = self.win.settings.get("pixel_perfect") and int(self.win.settings.get("brush_size", 1)) == 1
        if perfect:
            for c in new:
                self.points.append(c)
                if len(self.points) >= 3:
                    a, b, c2 = self.points[-3], self.points[-2], self.points[-1]
                    if abs(c2[0] - a[0]) == 1 and abs(c2[1] - a[1]) == 1 and (b[0] == a[0] or b[1] == a[1]) \
                            and (b[0] == c2[0] or b[1] == c2[1]):
                        del self.points[-2]  # drop the L-corner pixel
            self.stamp(self.points, clear_first=True)
        else:
            self.points += new
            self.stamp(new)
        self.commit_preview(doc)

    def release(self, doc, pt, button, mods):
        if getattr(self, "active", False):
            self.active = False
            self.win.last_point = self.points[-1]
            self.win.document_changed()


class EraserTool(PencilTool):
    key, name, icon, shortcut = "eraser", "Ластик", "eraser", "E"
    erase = True
    hint = "Стирает до прозрачности · ⇧ — линия"


class LineTool(_StrokeTool):
    key, name, icon, shortcut = "line", "Линия", "line", "L"
    draws = True
    hint = "⇧ — углы по 45°"

    def press(self, doc, pt, button, mods):
        if self.begin(doc, button):
            self.start = (pt.x(), pt.y())
            self.move(doc, pt, button, mods)

    def move(self, doc, pt, buttons, mods):
        if not getattr(self, "active", False):
            return
        end = (pt.x(), pt.y())
        if mods & Qt.ShiftModifier:
            end = constrain_45(self.start, end)
        self.stamp(line_points(self.start, end), clear_first=True)
        self.commit_preview(doc)

    def release(self, doc, pt, button, mods):
        if getattr(self, "active", False):
            self.active = False
            self.win.document_changed()


class RectTool(LineTool):
    key, name, icon, shortcut = "rect", "Прямоугольник", "rect", "U"
    hint = "⇧ — квадрат · «Заливка» в панели — сплошная фигура"
    shape = staticmethod(rect_points)

    def move(self, doc, pt, buttons, mods):
        if not getattr(self, "active", False):
            return
        end = (pt.x(), pt.y())
        if mods & Qt.ShiftModifier:
            end = square_box(self.start, end)
        filled = bool(self.win.settings.get("shape_fill"))
        self.stamp(self.shape(self.start, end, filled), clear_first=True)
        self.commit_preview(doc)


class EllipseTool(RectTool):
    key, name, icon, shortcut = "ellipse", "Эллипс", "ellipse", "⇧U"
    hint = "⇧ — круг · «Заливка» в панели — сплошная фигура"
    shape = staticmethod(ellipse_points)


class BucketTool(Tool):
    key, name, icon, shortcut = "bucket", "Заливка", "bucket", "G"
    hint = "«Смежные» и «Допуск» — в панели сверху"

    def press(self, doc, pt, button, mods):
        if not doc.point_in_sprite(pt):
            return
        if doc.layer.locked or not doc.layer.visible:
            self.win.status_message("Слой заблокирован или скрыт")
            return
        s = self.win.settings
        img = doc.editable_image()
        mask = flood_mask(img, pt.x(), pt.y(), bool(s.get("contiguous", True)), int(s.get("tolerance", 0)))
        argb = QColor(self.color(button)).rgba()
        fill = mask_image(mask, img.width(), img.height(), argb)
        doc.push(self.name)
        p = QPainter(img)
        p.setCompositionMode(QPainter.CompositionMode_Source if (argb >> 24) == 255 else QPainter.CompositionMode_SourceOver)
        # Source mode would wipe unmasked pixels: draw only the masked area
        p.setClipRegion(doc.clip_region().intersected(region_from_mask(mask, img.width(), img.height())))
        p.drawImage(0, 0, fill)
        p.end()
        doc.set_current(img)
        self.win.document_changed()


class EyedropperTool(Tool):
    key, name, icon, shortcut = "eyedropper", "Пипетка", "eyedropper", "I"
    hint = "ЛКМ — основной цвет, ПКМ — второй"

    def press(self, doc, pt, button, mods):
        self.pick(doc, pt, button)

    def move(self, doc, pt, buttons, mods):
        self.pick(doc, pt, Qt.RightButton if buttons & Qt.RightButton else Qt.LeftButton)

    def pick(self, doc, pt, button):
        if not doc.point_in_sprite(pt):
            return
        img = doc.sprite.flat_frame(doc.frame)
        c = QColor.fromRgba(img.pixel(pt))
        if c.alpha() == 0:
            return
        self.win.set_color(c, secondary=button == Qt.RightButton)


class MarqueeTool(Tool):
    key, name, icon, shortcut = "marquee", "Выделение", "marquee", "M"
    hint = "⇧ — добавить · Alt — вычесть · щелчок — снять выделение"

    def press(self, doc, pt, button, mods):
        self.start = pt
        self.mods = mods
        self.before = doc.selection
        self.dragged = False

    def _rect(self, pt):
        r = QRect(self.start, pt).normalized()
        return r.adjusted(0, 0, 0, 0)

    def move(self, doc, pt, buttons, mods):
        if not hasattr(self, "start"):
            return
        self.dragged = self.dragged or pt != self.start
        region = QRegion(self._rect(pt)).intersected(QRegion(0, 0, doc.sprite.width, doc.sprite.height))
        if self.mods & Qt.ShiftModifier:
            region = self.before.united(region)
        elif self.mods & Qt.AltModifier:
            region = self.before.subtracted(region)
        doc.selection = region
        self.win.canvas.update()

    def release(self, doc, pt, button, mods):
        if not hasattr(self, "start"):
            return
        final = doc.selection
        doc.selection = self.before
        doc.push("Выделение")
        doc.selection = final if self.dragged else QRegion()
        del self.start
        self.win.selection_changed()


class LassoTool(MarqueeTool):
    key, name, icon, shortcut = "lasso", "Лассо", "lasso", "Q"
    hint = "Обведите область · ⇧ — добавить · Alt — вычесть"

    def press(self, doc, pt, button, mods):
        super().press(doc, pt, button, mods)
        self.poly = [pt]

    def move(self, doc, pt, buttons, mods):
        if not hasattr(self, "start"):
            return
        if pt != self.poly[-1]:
            self.poly.append(pt)
        self.dragged = len(self.poly) > 2
        region = QRegion(QPolygon(self.poly), Qt.WindingFill) if len(self.poly) > 2 else QRegion()
        region = region.intersected(QRegion(0, 0, doc.sprite.width, doc.sprite.height))
        if self.mods & Qt.ShiftModifier:
            region = self.before.united(region)
        elif self.mods & Qt.AltModifier:
            region = self.before.subtracted(region)
        doc.selection = region
        self.win.canvas.update()


class WandTool(Tool):
    key, name, icon, shortcut = "wand", "Волшебная палочка", "wand", "W"
    hint = "Выделяет пиксели того же цвета · ⇧ — добавить · Alt — вычесть"

    def press(self, doc, pt, button, mods):
        if not doc.point_in_sprite(pt):
            return
        s = self.win.settings
        img = doc.current_image() or blank(doc.sprite.width, doc.sprite.height)
        mask = flood_mask(img, pt.x(), pt.y(), bool(s.get("contiguous", True)), int(s.get("tolerance", 0)))
        region = region_from_mask(mask, img.width(), img.height())
        doc.push("Волшебная палочка")
        if mods & Qt.ShiftModifier:
            region = doc.selection.united(region)
        elif mods & Qt.AltModifier:
            region = doc.selection.subtracted(region)
        doc.selection = region
        self.win.selection_changed()


class MoveTool(Tool):
    key, name, icon, shortcut = "move", "Перемещение", "move", "V"
    cursor = Qt.SizeAllCursor
    hint = "Двигает выделение или весь слой · стрелки — на 1 пиксель"

    def press(self, doc, pt, button, mods):
        if doc.layer.locked:
            self.win.status_message("Слой заблокирован")
            return
        doc.push("Перемещение")
        self.start = pt
        self.base = doc.editable_image()
        self.sel = QRegion(doc.selection)
        if doc.has_selection():
            self.piece = QImage(self.base.size(), FMT)
            self.piece.fill(0)
            p = QPainter(self.piece)
            p.setClipRegion(self.sel)
            p.drawImage(0, 0, self.base)
            p.end()
            hole = self.base.copy()
            p = QPainter(hole)
            p.setClipRegion(self.sel)
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.fillRect(hole.rect(), Qt.transparent)
            p.end()
            self.base = hole
        else:
            self.piece = self.base
            self.base = blank(self.base.width(), self.base.height())

    def move(self, doc, pt, buttons, mods):
        if not hasattr(self, "start"):
            return
        d = pt - self.start
        if mods & Qt.ShiftModifier:
            d = QPoint(d.x(), 0) if abs(d.x()) >= abs(d.y()) else QPoint(0, d.y())
        out = self.base.copy()
        p = QPainter(out)
        p.drawImage(d, self.piece)
        p.end()
        doc.set_current(out)
        if not self.sel.isEmpty():
            doc.selection = self.sel.translated(d)
        self.win.canvas_changed()

    def release(self, doc, pt, button, mods):
        if hasattr(self, "start"):
            del self.start
            self.win.document_changed()


class HandTool(Tool):
    key, name, icon, shortcut = "hand", "Рука", "hand", "H"
    cursor = Qt.OpenHandCursor
    hint = "Двигает холст · также пробел или средняя кнопка"


class ZoomTool(Tool):
    key, name, icon, shortcut = "zoom", "Масштаб", "zoom", "Z"
    cursor = Qt.CrossCursor
    hint = "Щелчок — приблизить · Alt — отдалить"


TOOLS = [PencilTool, EraserTool, EyedropperTool, BucketTool, LineTool, RectTool, EllipseTool,
         MarqueeTool, LassoTool, WandTool, MoveTool, HandTool, ZoomTool]
