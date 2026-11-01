"""The infinite canvas: view transform, hit testing, selection, move with smart guides, resize / rotate handles,
drawing tools (frames, shapes, lines, pen, pencil, marker, text, stickies, FigJam shapes, connectors, stamps),
vector point editing, inline text editing, zoom / pan, drag & drop."""
import math

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QCursor, QFont, QPainter, QPainterPath, QPainterPathStroker, QPen, QPixmap,
                           QPolygonF, QTextOption, QTransform)
from PySide6.QtWidgets import QPlainTextEdit, QWidget

from . import text as textlib
from .model import (FRAMELIKE, TEXTISH, Node, build_path, is_open, local_transform, normalize_path, resize_node,
                    shape_path, solid, union_rect, world_bounds, world_transform, parent_transform)

HANDLE = 7.0
CYR = dict(zip("йцукенгшщзхъфывапролджэячсмитьбю", "qwertyuiop[]asdfghjkl;'zxcvbnm,."))
CONTAINER_TOOLS = ("frame", "section")


def _rotate_cursor():
    pix = QPixmap(24, 24)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    for color, width in ((QColor("#FFFFFF"), 4.0), (QColor("#141413"), 1.6)):
        p.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        path = QPainterPath(QPointF(6, 17))
        path.arcTo(QRectF(6, 6, 22, 22), 180, -90)
        p.drawPath(path)
        p.drawPolyline(QPolygonF([QPointF(3, 14), QPointF(6, 17.5), QPointF(9.5, 14.5)]))
        p.drawPolyline(QPolygonF([QPointF(14.5, 3.5), QPointF(17.5, 6), QPointF(14.5, 9.5)]))
    p.end()
    return QCursor(pix, 12, 12)


class TextOverlay(QPlainTextEdit):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.setFrameStyle(0)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.document().setDocumentMargin(0)
        self.setStyleSheet("QPlainTextEdit { background: transparent; border: none; padding: 0; }")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape or (e.key() in (Qt.Key_Return, Qt.Key_Enter) and e.modifiers() & Qt.ControlModifier):
            self.canvas.finish_text_edit()
            return
        super().keyPressEvent(e)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        QTimer.singleShot(0, self.canvas.finish_text_edit_if_unfocused)


class Canvas(QWidget):
    zoomChanged = Signal(float)
    resized = Signal()

    def __init__(self, editor):
        super().__init__()
        self.ed = editor
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAcceptDrops(True)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMinimumSize(200, 200)
        self.zoom = 1.0
        self.off = QPointF(40, 40)
        self.drag = None
        self.hover = None
        self.guides = []
        self.marquee = None
        self.pen = None          # pen tool: {"pts": [...world...], "cursor": QPointF}
        self.vec = None          # vector editing: {"node": n, "sel": (sp, i) | None}
        self.editing = None      # node being text-edited
        self.overlay = None
        self.hidden = set()
        self.space = False
        self.insert_marker = None
        self.auto_fit = editor.doc.kind == "slides"
        self._titles = []
        self._last_pos = QPointF()
        self.rot_cursor = _rotate_cursor()

    # ================================================================== view transform
    def vt(self):
        return QTransform(self.zoom, 0, 0, self.zoom, self.off.x(), self.off.y())

    def to_world(self, pt):
        return QPointF((pt.x() - self.off.x()) / self.zoom, (pt.y() - self.off.y()) / self.zoom)

    def to_view(self, pt):
        return QPointF(pt.x() * self.zoom + self.off.x(), pt.y() * self.zoom + self.off.y())

    def view_rect(self, r):
        return self.vt().mapRect(r)

    def set_zoom(self, z, anchor=None):
        z = max(0.02, min(256.0, z))
        anchor = anchor if anchor is not None else QPointF(self.width() / 2, self.height() / 2)
        w = self.to_world(anchor)
        self.zoom = z
        self.off = QPointF(anchor.x() - w.x() * z, anchor.y() - w.y() * z)
        self.zoomChanged.emit(self.zoom)
        self.reposition_overlay()
        self.update()

    def fit(self, rect=None, margin=60, max_zoom=None):
        if rect is None:
            rect = union_rect(world_bounds(n) for n in self.ed.visible_roots() if n.visible)
        if rect is None or rect.width() <= 0 and rect.height() <= 0:
            self.zoom = 1.0
            self.off = QPointF(self.width() / 2, self.height() / 2)
            self.zoomChanged.emit(self.zoom)
            self.update()
            return
        aw, ah = max(10, self.width() - 2 * margin), max(10, self.height() - 2 * margin)
        z = min(aw / max(1.0, rect.width()), ah / max(1.0, rect.height()))
        if max_zoom:
            z = min(z, max_zoom)
        self.zoom = max(0.02, min(256.0, z))
        c = rect.center()
        self.off = QPointF(self.width() / 2 - c.x() * self.zoom, self.height() / 2 - c.y() * self.zoom)
        self.zoomChanged.emit(self.zoom)
        self.reposition_overlay()
        self.update()

    def fit_width(self, node, margin=48):
        r = world_bounds(node)
        z = max(0.05, min(1.0, (self.width() - 2 * margin) / max(1.0, r.width())))
        self.zoom = z
        self.off = QPointF(self.width() / 2 - r.center().x() * z, margin - r.y() * z + 24)
        self.zoomChanged.emit(self.zoom)
        self.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.auto_fit and self.ed.doc.kind == "slides":
            self.fit(margin=40)
        self.resized.emit()

    def theme(self):
        return self.ed.theme

    # ================================================================== painting
    def paintEvent(self, e):
        c = self.theme()
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        kind = self.ed.doc.kind
        page = self.ed.page
        if kind == "board":
            p.fillRect(self.rect(), QColor(page.bg or c["board"]))
            self.paint_dots(p, c)
        else:
            p.fillRect(self.rect(), QColor(page.bg or c["canvas"]))
        roots = self.ed.visible_roots()
        if kind in ("slides", "site"):
            for n in roots:
                r = self.view_rect(world_bounds(n))
                for i, a in enumerate((18, 10, 5)):
                    p.fillRect(r.adjusted(-i - 1, -i, i + 1, i + 2), QColor(0, 0, 0, a))
        p.save()
        p.setTransform(self.vt())
        renderer = self.ed.renderer
        for n in roots:
            renderer.paint(p, n, self.hidden)
        if self.drag and self.drag.get("mode") == "pencil" and len(self.drag["pts"]) > 1:
            st = self.drag["style"]
            pen = QPen(QColor(st["color"]), st["width"], Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            p.setOpacity(st.get("opacity", 1.0))
            p.setPen(pen)
            p.drawPolyline(QPolygonF(self.drag["pts"]))
            p.setOpacity(1.0)
        p.restore()
        self.paint_overlays(p, c)
        p.end()

    def paint_dots(self, p, c):
        sp = 24.0 * self.zoom
        while sp < 12:
            sp *= 2
        if sp > 200:
            return
        col = QColor(c["dot"])
        p.setPen(QPen(col, 1.6 if self.zoom > 0.6 else 1.2, Qt.SolidLine, Qt.RoundCap))
        ox = self.off.x() % sp
        oy = self.off.y() % sp
        pts = []
        y = oy
        while y < self.height():
            x = ox
            while x < self.width():
                pts.append(QPointF(x, y))
                x += sp
            y += sp
        p.drawPoints(QPolygonF(pts))

    def node_poly(self, n):
        if n.type == "connector":
            return QPolygonF(self.view_rect(world_bounds(n)))
        t = world_transform(n) * self.vt()
        return t.map(QPolygonF(QRectF(0, 0, n.w, n.h)))

    def selection_box(self):
        sel = self.ed.top_selection()
        if not sel:
            return None
        if len(sel) == 1 and sel[0].type != "connector":
            n = sel[0]
            poly = self.node_poly(n)
            return {"poly": [poly[i] for i in range(4)], "single": n}
        r = self.view_rect(union_rect(world_bounds(n) for n in sel))
        return {"poly": [r.topLeft(), r.topRight(), r.bottomRight(), r.bottomLeft()], "single": None}

    def handles(self, box):
        p0, p1, p2, p3 = box["poly"]
        mid = lambda a, b: (a + b) / 2  # noqa: E731
        hs = {"nw": p0, "ne": p1, "se": p2, "sw": p3}
        if QLineF(p0, p1).length() > 24 and QLineF(p1, p2).length() > 24:
            hs.update({"n": mid(p0, p1), "e": mid(p1, p2), "s": mid(p2, p3), "w": mid(p3, p0)})
        n = box["single"]
        if n is not None and n.type == "path" and len(n.paths) == 1 and len(n.paths[0]["pts"]) == 2 \
                and not n.paths[0].get("closed"):
            return {}  # a straight line: endpoints are edited in vector mode
        return hs

    def paint_overlays(self, p, c):
        acc = QColor(c["accent"])
        kind = self.ed.doc.kind
        sel = self.ed.selection
        self._titles = []
        # frame titles
        if kind in ("design", "board"):
            f = QFont(textlib.DEFAULT_FONT)
            f.setPixelSize(11)
            p.setFont(f)
            for n in self.ed.page.children:
                if n.type in ("frame", "component", "instance") and n.visible:
                    tl = self.to_view(world_transform(n).map(QPointF(0, 0)))
                    label = ("❖ " if n.type == "component" else ("◇ " if n.type == "instance" else "")) + n.name
                    w = min(p.fontMetrics().horizontalAdvance(label) + 4, max(30.0, n.w * self.zoom))
                    r = QRectF(tl.x(), tl.y() - 18, w, 16)
                    is_sel = n in sel
                    col = acc if (is_sel or n.type == "component") else QColor(c["muted"])
                    p.setPen(col)
                    p.drawText(r, Qt.AlignLeft | Qt.AlignVCenter,
                               p.fontMetrics().elidedText(label, Qt.ElideRight, int(r.width())))
                    self._titles.append((r, n))
        elif kind == "site":
            root = self.ed.scope_root()
            if root is not None and root.type != "page":
                f = QFont(textlib.DEFAULT_FONT)
                f.setPixelSize(11)
                p.setFont(f)
                tl = self.to_view(QPointF(0, 0))
                bp = int(self.ed.doc.site.get("breakpoint", 1440))
                name = dict((b, t) for b, t in ((1440, "Компьютер"), (768, "Планшет"), (375, "Телефон"))).get(bp, "")
                p.setPen(QColor(c["muted"]))
                p.drawText(QRectF(tl.x(), tl.y() - 20, 400, 16), Qt.AlignLeft | Qt.AlignVCenter,
                           f"{self.ed.page.name} · {name} {bp}")
        # hover
        if self.hover is not None and self.hover not in sel and not self.drag and self.hover.page() is self.ed.page:
            p.setPen(QPen(acc, 1.5))
            p.setBrush(Qt.NoBrush)
            if self.hover.type == "connector":
                p.drawPath(self.vt().map(shape_path(self.hover)))
            else:
                p.drawPolygon(self.node_poly(self.hover))
        # selection outlines
        p.setPen(QPen(acc, 1))
        p.setBrush(Qt.NoBrush)
        for n in sel:
            if n.page() is not self.ed.page:
                continue
            if n.type == "connector":
                p.setPen(QPen(acc, 2))
                p.drawPath(self.vt().map(shape_path(n)))
                p.setPen(QPen(acc, 1))
            else:
                p.drawPolygon(self.node_poly(n))
        if self.ed.tool == "select" and self.editing is None and self.vec is None and self.pen is None:
            box = self.selection_box()
            if box is not None and all(n.page() is self.ed.page for n in sel):
                if not box["single"] and len(sel) > 1:
                    p.drawPolygon(QPolygonF(box["poly"]))
                p.setBrush(QColor(c["handle"]))
                p.setPen(QPen(acc, 1.2))
                for name, pt in self.handles(box).items():
                    p.drawRect(QRectF(pt.x() - HANDLE / 2, pt.y() - HANDLE / 2, HANDLE, HANDLE))
                # connector endpoints
                for n in sel:
                    if n.type == "connector" and n._path is not None and n._path.elementCount() > 1:
                        for q in (n._path.elementAt(0), n._path.elementAt(n._path.elementCount() - 1)):
                            p.drawEllipse(self.to_view(QPointF(q.x, q.y)), 5, 5)
                self.paint_size_label(p, c, box)
        # guides
        if self.guides:
            p.setPen(QPen(QColor(c["guide"]), 1))
            for g in self.guides:
                if g[0] == "v":
                    a, b = self.to_view(QPointF(g[1], g[2])), self.to_view(QPointF(g[1], g[3]))
                else:
                    a, b = self.to_view(QPointF(g[2], g[1])), self.to_view(QPointF(g[3], g[1]))
                p.drawLine(a, b)
        if self.marquee is not None:
            r = self.view_rect(self.marquee)
            fill = QColor(acc)
            fill.setAlpha(28)
            p.setBrush(fill)
            p.setPen(QPen(acc, 1))
            p.drawRect(r)
        if self.insert_marker is not None:
            p.setPen(QPen(acc, 2.5))
            p.drawLine(self.to_view(self.insert_marker.p1()), self.to_view(self.insert_marker.p2()))
        if self.pen is not None:
            self.paint_pen(p, c)
        if self.vec is not None:
            self.paint_vec(p, c)
        if self.ed.tool == "connector" and self.hover is not None and self.hover.type != "connector":
            r = world_bounds(self.hover)
            p.setBrush(QColor(c["handle"]))
            p.setPen(QPen(acc, 1.5))
            for side_pt in (QPointF(r.center().x(), r.top()), QPointF(r.right(), r.center().y()),
                            QPointF(r.center().x(), r.bottom()), QPointF(r.left(), r.center().y())):
                p.drawEllipse(self.to_view(side_pt), 4.5, 4.5)

    def paint_size_label(self, p, c, box):
        sel = self.ed.top_selection()
        if not sel or self.drag and self.drag.get("mode") not in ("resize", "move", "create"):
            return
        if box["single"] is not None:
            n = box["single"]
            w, h = n.w, n.h
        else:
            b = union_rect(world_bounds(n) for n in sel)
            w, h = b.width(), b.height()
        label = f"{_fmt(w)} × {_fmt(h)}"
        pts = box["poly"]
        bottom = max(pts, key=lambda q: q.y()).y()
        cx = sum(q.x() for q in pts) / 4
        f = QFont(textlib.DEFAULT_FONT)
        f.setPixelSize(11)
        p.setFont(f)
        tw = p.fontMetrics().horizontalAdvance(label) + 12
        r = QRectF(cx - tw / 2, bottom + 8, tw, 18)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(c["accent"]))
        p.drawRoundedRect(r, 4, 4)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(r, Qt.AlignCenter, label)

    def paint_pen(self, p, c):
        pts = self.pen["pts"]
        acc = QColor(c["accent"])
        if pts:
            path = build_path([{"pts": pts, "closed": False}])
            p.save()
            p.setTransform(self.vt())
            p.setPen(QPen(QColor("#141413"), 1.5 / self.zoom))
            p.drawPath(path)
            cur = self.pen.get("cursor")
            if cur is not None and not self.drag:
                last = pts[-1]
                p.setPen(QPen(acc, 1 / self.zoom, Qt.DashLine))
                q = QPainterPath(QPointF(last[0], last[1]))
                q.cubicTo(QPointF(last[4], last[5]), cur, cur)
                p.drawPath(q)
            p.restore()
        p.setPen(QPen(acc, 1.2))
        p.setBrush(QColor(c["handle"]))
        for i, pt in enumerate(pts):
            v = self.to_view(QPointF(pt[0], pt[1]))
            p.drawEllipse(v, 4, 4)
            if (pt[4], pt[5]) != (pt[0], pt[1]):
                for hx, hy in ((pt[2], pt[3]), (pt[4], pt[5])):
                    hv = self.to_view(QPointF(hx, hy))
                    p.drawLine(v, hv)
                    p.drawEllipse(hv, 3, 3)

    def paint_vec(self, p, c):
        n = self.vec["node"]
        t = world_transform(n) * self.vt()
        acc = QColor(c["accent"])
        p.setPen(QPen(acc, 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(t.map(build_path(n.paths)))
        for si, sp in enumerate(n.paths):
            for i, pt in enumerate(sp["pts"]):
                v = t.map(QPointF(pt[0], pt[1]))
                selected = self.vec.get("sel") == (si, i)
                for hx, hy in ((pt[2], pt[3]), (pt[4], pt[5])):
                    if (hx, hy) != (pt[0], pt[1]):
                        hv = t.map(QPointF(hx, hy))
                        p.setPen(QPen(acc, 1))
                        p.drawLine(v, hv)
                        p.setBrush(QColor(c["handle"]))
                        p.drawEllipse(hv, 3, 3)
                p.setPen(QPen(acc, 1.5))
                p.setBrush(acc if selected else QColor(c["handle"]))
                p.drawRect(QRectF(v.x() - 4, v.y() - 4, 8, 8))

    # ================================================================== hit testing
    def hit_chain(self, w, roots=None):
        tol = 4.0 / self.zoom
        roots = roots if roots is not None else self.ed.scope_children()
        base = world_transform(self.ed.scope_root()) if self.ed.scope_root().type != "page" else QTransform()
        for n in reversed(roots):
            ch = self._hit(n, w, base, tol)
            if ch:
                return ch
        return []

    def _hit(self, n, w, parent_t, tol):
        if not n.visible or n.locked or n.id in self.hidden:
            return None
        if n.type == "connector":
            st = QPainterPathStroker()
            st.setWidth(max(n.stroke_width, 2 * tol + 4))
            return [n] if st.createStroke(shape_path(n)).contains(w) else None
        t = local_transform(n) * parent_t
        inv, ok = t.inverted()
        if not ok:
            return None
        lp = inv.map(w)
        if n.type in FRAMELIKE or n.type == "group":
            inside = QRectF(0, 0, n.w, n.h).adjusted(-tol, -tol, tol, tol).contains(lp)
            if n.clip and not inside and n.type != "group":
                return None
            for c in reversed(n.children):
                if c.mask:
                    continue
                r = self._hit(c, w, t, tol)
                if r:
                    return [n] + r
            if n.type == "group":
                return None
            return [n] if inside else None
        if n.type in ("text", "sticky", "shape", "stamp", "rect", "ellipse", "polygon", "star"):
            r = QRectF(0, 0, n.w, n.h).adjusted(-tol, -tol, tol, tol)
            if n.type in ("ellipse", "polygon", "star", "shape") and n.fills:
                if shape_path(n).contains(lp):
                    return [n]
            elif r.contains(lp):
                return [n]
        path = shape_path(n)
        if not is_open(n) and n.fills and path.contains(lp):
            return [n]
        st = QPainterPathStroker()
        scale = math.sqrt(abs(t.determinant())) or 1.0
        st.setWidth(max(n.stroke_width, (2 * tol + 2) / scale))
        if st.createStroke(path).contains(lp):
            return [n]
        return None

    def attachable(self):
        """Objects a connector end can stick to (everything on the page except connectors)."""
        return [c for c in self.ed.page.children if c.type != "connector"]

    def pick(self, chain, deep=False):
        if not chain:
            return None
        if deep:
            return chain[-1]
        for s in self.ed.selection:  # stay on the level the user is working at
            if s.parent in chain[:-1]:
                d = chain.index(s.parent) + 1
                if d < len(chain):
                    return chain[d]
            if s in chain:
                return s
        top = chain[0]
        if top.type in ("frame", "component", "section") and len(chain) > 1:
            return chain[1]
        return top

    def container_at(self, w, exclude=()):
        root = self.ed.scope_root()
        best = root
        base = world_transform(root) if root.type != "page" else QTransform()

        def visit(node, t):
            nonlocal best
            for c in reversed(node.children):
                if not c.visible or c.locked or any(c is x for x in exclude) or c.type not in ("frame", "component",
                                                                                              "section"):
                    continue
                ct = local_transform(c) * t
                inv, ok = ct.inverted()
                if ok and QRectF(0, 0, c.w, c.h).contains(inv.map(w)):
                    best = c
                    visit(c, ct)
                    return
        visit(root, base)
        return best

    def title_at(self, pos):
        for r, n in reversed(self._titles):
            if r.contains(pos):
                return n
        return None

    def handle_at(self, pos):
        if self.ed.tool != "select" or self.editing is not None:
            return None
        box = self.selection_box()
        if box is None:
            return None
        hs = self.handles(box)
        for name, pt in hs.items():
            if QLineF(pos, pt).length() <= HANDLE:
                return name
        poly = QPolygonF(box["poly"])
        if not poly.containsPoint(pos, Qt.OddEvenFill) and hs:
            for name in ("nw", "ne", "se", "sw"):
                d = QLineF(pos, hs[name]).length()
                if HANDLE < d <= 20:
                    return "rot"
        return None

    def connector_end_at(self, pos):
        for n in self.ed.selection:
            if n.type == "connector" and n._path is not None and n._path.elementCount() > 1:
                a = n._path.elementAt(0)
                b = n._path.elementAt(n._path.elementCount() - 1)
                if QLineF(pos, self.to_view(QPointF(a.x, a.y))).length() <= 8:
                    return n, "start"
                if QLineF(pos, self.to_view(QPointF(b.x, b.y))).length() <= 8:
                    return n, "end"
        return None

    # ================================================================== snapping
    def snap_targets(self, moving):
        xs, ys = [], []
        ids = set()
        for m in moving:
            for d in m.walk():
                ids.add(d.id)
        parents = {m.parent for m in moving if m.parent is not None}
        pool = []
        for par in parents:
            pool.extend(par.children)
            if par.type != "page":
                pool.append(par)
        pool.extend(self.ed.scope_children())
        seen = set()
        for n in pool:
            if n.id in ids or n.id in seen or not n.visible or n.type == "connector":
                continue
            seen.add(n.id)
            r = world_bounds(n)
            for x in (r.left(), r.center().x(), r.right()):
                xs.append((x, r))
            for y in (r.top(), r.center().y(), r.bottom()):
                ys.append((y, r))
        return xs, ys

    def snap_rect(self, r, xs, ys, edges_x=(0, 1, 2), edges_y=(0, 1, 2)):
        """Return (dx, dy) that snaps r to the nearest guide, and fill self.guides."""
        th = 6.0 / self.zoom
        mine_x = [r.left(), r.center().x(), r.right()]
        mine_y = [r.top(), r.center().y(), r.bottom()]
        best_dx, best_dy = None, None
        for i in edges_x:
            for x, _ in xs:
                d = x - mine_x[i]
                if abs(d) <= th and (best_dx is None or abs(d) < abs(best_dx)):
                    best_dx = d
        for i in edges_y:
            for y, _ in ys:
                d = y - mine_y[i]
                if abs(d) <= th and (best_dy is None or abs(d) < abs(best_dy)):
                    best_dy = d
        dx, dy = best_dx or 0.0, best_dy or 0.0
        rr = r.translated(dx, dy)
        self.guides = []
        if best_dx is not None:
            mx = [rr.left(), rr.center().x(), rr.right()]
            for i in edges_x:
                for x, o in xs:
                    if abs(x - mx[i]) < 0.01:
                        self.guides.append(("v", x, min(o.top(), rr.top()), max(o.bottom(), rr.bottom())))
        if best_dy is not None:
            my = [rr.top(), rr.center().y(), rr.bottom()]
            for i in edges_y:
                for y, o in ys:
                    if abs(y - my[i]) < 0.01:
                        self.guides.append(("h", y, min(o.left(), rr.left()), max(o.right(), rr.right())))
        return dx, dy

    # ================================================================== mouse
    def mousePressEvent(self, e):
        self.setFocus()
        pos = e.position()
        w = self.to_world(pos)
        self._last_pos = pos
        if self.editing is not None:
            self.finish_text_edit()
        if e.button() == Qt.MiddleButton or (e.button() == Qt.LeftButton and (self.space or self.ed.tool == "hand")):
            self.drag = {"mode": "pan", "start": pos, "off": QPointF(self.off)}
            self.setCursor(Qt.ClosedHandCursor)
            return
        if e.button() == Qt.RightButton:
            chain = self.hit_chain(w)
            target = self.pick(chain)
            if target is not None and target not in self.ed.selection:
                self.ed.select([target])
            elif target is None and self.ed.selection:
                self.ed.select([])
            self.ed.context_menu(e.globalPosition().toPoint(), w)
            return
        if e.button() != Qt.LeftButton:
            return
        tool = self.ed.tool
        if self.vec is not None:
            if self.vec_press(pos, w):
                return
            self.exit_vector_edit()
        if tool == "pen":
            self.pen_press(w, e)
            return
        if tool in ("pencil", "marker", "highlighter"):
            self.drag = {"mode": "pencil", "pts": [w], "style": self.ed.freehand_style(tool)}
            return
        if tool == "connector":
            self.connector_press(w)
            return
        if tool in ("text", "sticky", "shape", "stamp") or tool in self.ed.CREATE_TOOLS:
            self.create_press(w, tool, e)
            return
        # select tool
        ce = self.connector_end_at(pos)
        if ce is not None:
            self.drag = {"mode": "conn_end", "node": ce[0], "which": ce[1]}
            return
        h = self.handle_at(pos)
        if h is not None:
            self.begin_resize(h, w, e)
            return
        title = self.title_at(pos)
        if title is not None:
            if e.modifiers() & Qt.ShiftModifier:
                self.ed.toggle_select(title)
            elif title not in self.ed.selection:
                self.ed.select([title])
            self.begin_move(w, e)
            return
        chain = self.hit_chain(w)
        deep = bool(e.modifiers() & Qt.ControlModifier)
        target = self.pick(chain, deep)
        if target is not None:
            top_frame_area = (len(chain) == 1 and target.type in ("frame", "component", "section")
                              and target.parent is self.ed.scope_root() and target not in self.ed.selection
                              and target.children and not e.modifiers() & Qt.ShiftModifier)
            if top_frame_area:  # drag inside an empty part of a top-level frame → marquee among its children
                self.drag = {"mode": "marquee", "start": w, "within": target, "add": [], "click_select": target}
                self.marquee = QRectF(w, w)
                return
            if e.modifiers() & Qt.ShiftModifier:
                self.ed.toggle_select(target)
                if target not in self.ed.selection:
                    return
            elif target not in self.ed.selection:
                self.ed.select([target])
            self.begin_move(w, e)
            return
        add = list(self.ed.selection) if e.modifiers() & Qt.ShiftModifier else []
        if not add:
            self.ed.select([])
        self.drag = {"mode": "marquee", "start": w, "within": None, "add": add}
        self.marquee = QRectF(w, w)

    def mouseMoveEvent(self, e):
        pos = e.position()
        w = self.to_world(pos)
        self.ed.show_cursor_pos(w)
        d = self.drag
        if d is None:
            self.update_hover(pos, w, e)
            if self.pen is not None:
                self.pen["cursor"] = w
                self.update()
            return
        m = d["mode"]
        if m == "pan":
            self.off = d["off"] + (pos - d["start"])
            self.auto_fit = False
            self.reposition_overlay()
            self.update()
        elif m == "move":
            self.drag_move(w, e)
        elif m == "resize":
            self.drag_resize(w, e)
        elif m == "rotate":
            self.drag_rotate(w, e)
        elif m == "marquee":
            self.marquee = QRectF(d["start"], w).normalized()
            self.marquee_select()
            self.update()
        elif m == "create":
            self.drag_create(w, e)
        elif m == "pencil":
            if QLineF(d["pts"][-1], w).length() * self.zoom > 1.5:
                d["pts"].append(w)
                self.update()
        elif m == "pen_handle":
            pt = self.pen["pts"][-1]
            pt[4], pt[5] = w.x(), w.y()
            pt[2], pt[3] = 2 * pt[0] - w.x(), 2 * pt[1] - w.y()
            self.update()
        elif m == "connector":
            n = d["node"]
            n.end = {"x": w.x(), "y": w.y()}
            chain = self.hit_chain(w, self.attachable())
            self.hover = next((c for c in reversed(chain) if c.type != "connector" and c is not d.get("from")), None)
            self.ed.doc.update_connectors(self.ed.page)
            self.update()
        elif m == "conn_end":
            n = d["node"]
            setattr(n, d["which"], {"x": w.x(), "y": w.y()})
            chain = self.hit_chain(w, self.attachable())
            self.hover = next((c for c in reversed(chain) if c.type != "connector"), None)
            self.ed.doc.update_connectors(self.ed.page)
            self.update()
        elif m == "vec_point":
            self.vec_drag(w, e)

    def mouseReleaseEvent(self, e):
        d = self.drag
        self.drag = None
        self.guides = []
        self.insert_marker = None
        if d is None:
            return
        m = d["mode"]
        w = self.to_world(e.position())
        if m == "pan":
            self.setCursor(Qt.OpenHandCursor if (self.space or self.ed.tool == "hand") else Qt.ArrowCursor)
        elif m == "move":
            self.end_move(d, w)
        elif m in ("resize", "rotate"):
            if d.get("changed"):
                self.ed.commit("Размер" if m == "resize" else "Поворот")
        elif m == "marquee":
            if self.marquee is not None and self.marquee.width() * self.zoom < 3 and d.get("click_select") is not None:
                self.ed.select([d["click_select"]])
            self.marquee = None
        elif m == "create":
            self.end_create(d, w)
        elif m == "pencil":
            self.end_pencil(d)
        elif m == "pen_handle":
            pass
        elif m == "connector":
            self.end_connector(d, w)
        elif m == "conn_end":
            n = d["node"]
            chain = self.hit_chain(w, self.attachable())
            target = next((c for c in reversed(chain) if c.type != "connector"), None)
            if target is not None:
                setattr(n, d["which"], {"id": target.id})
            self.ed.doc.update_connectors(self.ed.page)
            self.ed.commit("Соединитель")
        elif m == "vec_point":
            self.ed.live_changed()
        self.update()

    def mouseDoubleClickEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        w = self.to_world(e.position())
        if self.pen is not None:
            self.finish_pen(False)
            return
        if self.ed.tool != "select":
            return
        title = self.title_at(e.position())
        if title is not None:
            self.ed.rename(title)
            return
        chain = self.hit_chain(w)
        if not chain:
            return
        sel = self.ed.selection[0] if len(self.ed.selection) == 1 else None
        if sel is not None and sel in chain and chain.index(sel) < len(chain) - 1 and sel.container:
            nxt = chain[chain.index(sel) + 1]
            self.ed.select([nxt])
            if nxt.type in TEXTISH and len(chain) == chain.index(nxt) + 1 and nxt.type != "text":
                self.start_text_edit(nxt)
            return
        target = sel if (sel is not None and sel in chain) else self.pick(chain)
        if target is None:
            return
        if target.type in TEXTISH or target.type == "connector":
            self.ed.select([target])
            self.start_text_edit(target)
        elif target.type == "path":
            self.ed.select([target])
            self.enter_vector_edit(target)
        elif target.container and len(chain) > 1:
            idx = chain.index(target) if target in chain else 0
            if idx + 1 < len(chain):
                self.ed.select([chain[idx + 1]])

    def wheelEvent(self, e):
        mods = e.modifiers()
        pd = e.pixelDelta()
        ad = e.angleDelta()
        if mods & (Qt.ControlModifier | Qt.MetaModifier):
            dy = pd.y() if not pd.isNull() else ad.y() / 4
            self.auto_fit = False
            self.set_zoom(self.zoom * math.pow(1.01, dy), e.position())
            return
        if not pd.isNull():
            dx, dy = pd.x(), pd.y()
        else:
            dx, dy = ad.x() / 2, ad.y() / 2
            if mods & Qt.ShiftModifier:
                dx, dy = dy, dx
        self.off += QPointF(dx, dy)
        self.auto_fit = False
        self.reposition_overlay()
        self.update()

    def event(self, e):
        if e.type() == e.Type.NativeGesture:
            if e.gestureType() == Qt.ZoomNativeGesture:
                self.auto_fit = False
                self.set_zoom(self.zoom * (1 + e.value()), e.position())
                return True
        return super().event(e)

    def update_hover(self, pos, w, e):
        tool = self.ed.tool
        if self.space or tool == "hand":
            self.setCursor(Qt.OpenHandCursor)
            return
        if tool == "connector":
            chain = self.hit_chain(w, self.attachable())
            hov = next((c for c in reversed(chain) if c.type != "connector"), None)
        elif tool == "select":
            h = self.handle_at(pos)
            box = self.selection_box()
            if h == "rot":
                self.setCursor(self.rot_cursor)
            elif h is not None:
                self.setCursor(self._resize_cursor(h, box))
            elif self.connector_end_at(pos) is not None:
                self.setCursor(Qt.CrossCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
            title = self.title_at(pos)
            hov = title if title is not None else self.pick(self.hit_chain(w), bool(e.modifiers() & Qt.ControlModifier))
        else:
            self.setCursor(Qt.IBeamCursor if tool == "text" else Qt.CrossCursor)
            hov = None
        if hov is not self.hover:
            self.hover = hov
            self.update()

    def _resize_cursor(self, h, box):
        base = {"n": 90, "s": 90, "e": 0, "w": 0, "ne": 45, "sw": 45, "nw": 135, "se": 135}[h]
        rot = box["single"].rotation if box and box["single"] is not None else 0
        a = (base - rot) % 180
        return [Qt.SizeHorCursor, Qt.SizeBDiagCursor, Qt.SizeVerCursor, Qt.SizeFDiagCursor][int(((a + 22.5) % 180) // 45)]

    def leaveEvent(self, e):
        if self.hover is not None and not self.drag:
            self.hover = None
            self.update()

    # ================================================================== move
    def begin_move(self, w, e):
        nodes = self.ed.top_selection()
        nodes = [n for n in nodes if not n.locked and n.type != "connector"]
        if not nodes:
            return
        self.drag = {"mode": "move", "start": w, "nodes": nodes, "moved": False,
                     "alt": bool(e.modifiers() & Qt.AltModifier)}

    def _start_move(self, d):
        if d["alt"]:
            d["nodes"] = self.ed.duplicate_in_place(d["nodes"])
        nodes = d["nodes"]
        d["orig"] = {n.id: (n.x, n.y) for n in nodes}
        d["bounds"] = union_rect(world_bounds(n) for n in nodes)
        d["targets"] = self.snap_targets(nodes)
        flow = len(nodes) == 1 and nodes[0].in_flow()
        d["reorder"] = flow
        if flow:
            d["parent_rect"] = world_bounds(nodes[0].parent)
        d["moved"] = True

    def drag_move(self, w, e):
        d = self.drag
        if not d["moved"]:
            if QLineF(self.to_view(d["start"]), self.to_view(w)).length() < 3:
                return
            self._start_move(d)
        delta = w - d["start"]
        if e.modifiers() & Qt.ShiftModifier:  # constrain to an axis
            if abs(delta.x()) > abs(delta.y()):
                delta.setY(0)
            else:
                delta.setX(0)
        if not d["reorder"] and not (e.modifiers() & Qt.ControlModifier):
            dx, dy = self.snap_rect(d["bounds"].translated(delta), *d["targets"])
            delta += QPointF(dx, dy)
        else:
            self.guides = []
        snap = self.ed.settings.get("snap_pixels", True)
        for n in d["nodes"]:
            ox, oy = d["orig"][n.id]
            pinv, _ = parent_transform(n).inverted()
            ld = pinv.map(d["start"] + delta) - pinv.map(d["start"])
            n.x, n.y = ox + ld.x(), oy + ld.y()
            if snap and n.rotation == 0 and not d["reorder"]:
                n.x, n.y = round(n.x), round(n.y)
        if d["reorder"]:
            self.insert_marker = self._reorder_marker(d["nodes"][0], w)
        self.ed.doc.update_connectors(self.ed.page)
        self.ed.live_changed(relayout=False)

    def _flow_index(self, n, w):
        par = n.parent
        horiz = par.layout == "row"
        pinv, _ = world_transform(par).inverted()
        lp = pinv.map(w)
        flow = [c for c in par.children if c is not n and c.visible and not c.absolute and c.type != "connector"]
        idx = 0
        for c in flow:
            mid = (c.x + c.w / 2) if horiz else (c.y + c.h / 2)
            if (lp.x() if horiz else lp.y()) > mid:
                idx += 1
        return idx, flow, horiz

    def _reorder_marker(self, n, w):
        par = n.parent
        if not world_bounds(par).contains(w):
            return None
        idx, flow, horiz = self._flow_index(n, w)
        t = world_transform(par)
        if horiz:
            if idx < len(flow):
                x = flow[idx].x - par.gap / 2
            elif flow:
                x = flow[-1].x + flow[-1].w + par.gap / 2
            else:
                x = par.pad[3]
            return QLineF(t.map(QPointF(x, par.pad[0])), t.map(QPointF(x, par.h - par.pad[2])))
        if idx < len(flow):
            y = flow[idx].y - par.gap / 2
        elif flow:
            y = flow[-1].y + flow[-1].h + par.gap / 2
        else:
            y = par.pad[0]
        return QLineF(t.map(QPointF(par.pad[3], y)), t.map(QPointF(par.w - par.pad[1], y)))

    def end_move(self, d, w):
        if not d.get("moved"):
            return
        nodes = d["nodes"]
        if d["reorder"]:
            n = nodes[0]
            par = n.parent
            if world_bounds(par).contains(w):
                idx, flow, _ = self._flow_index(n, w)
                if idx < len(flow):
                    full = par.children.index(flow[idx])
                else:
                    full = (par.children.index(flow[-1]) + 1) if flow else 0
                cur = par.children.index(n)
                if full > cur:
                    full -= 1
                par.children.remove(n)
                par.children.insert(full, n)
                self.ed.commit("Порядок")
                return
            # dropped outside the auto layout parent: free it
            target = self.container_at(w, exclude=nodes)
            self.ed.reparent_keep_world(n, target, center=w)
            self.ed.commit("Перемещение")
            return
        center = d["bounds"].translated(w - d["start"]).center()
        target = self.container_at(center, exclude=nodes)
        for n in nodes:
            if target is not n.parent and not n.is_ancestor_of(target) and target is not n:
                if not (n.parent.type == "group" and target is self.container_at(world_bounds(n.parent).center())):
                    self.ed.reparent_keep_world(n, target)
        self.ed.commit("Перемещение")

    # ================================================================== resize / rotate
    def begin_resize(self, h, w, e):
        sel = [n for n in self.ed.top_selection() if not n.locked]
        if not sel:
            return
        if h == "rot":
            b = union_rect(world_bounds(n) for n in sel)
            c = b.center() if len(sel) > 1 else world_transform(sel[0]).map(QPointF(sel[0].w / 2, sel[0].h / 2))
            self.drag = {"mode": "rotate", "nodes": sel, "center": c,
                         "a0": math.atan2(w.y() - c.y(), w.x() - c.x()),
                         "orig": {n.id: (n.x, n.y, n.rotation) for n in sel},
                         "centers": {n.id: world_transform(n).map(QPointF(n.w / 2, n.h / 2)) for n in sel}}
            return
        if len(sel) == 1:
            n = sel[0]
            T0 = world_transform(n)
            W, H = n.w, n.h
        else:
            b = union_rect(world_bounds(n) for n in sel)
            T0 = QTransform.fromTranslate(b.x(), b.y())
            W, H = b.width(), b.height()
        inv, _ = T0.inverted()
        self.drag = {"mode": "resize", "handle": h, "nodes": sel, "T0": T0, "inv": inv, "W": W, "H": H,
                     "orig": {n.id: n.to_dict() for n in sel},
                     "bounds": {n.id: world_bounds(n) for n in sel},
                     "targets": self.snap_targets(sel), "changed": False}

    def drag_resize(self, w, e):
        d = self.drag
        h = d["handle"]
        W, H = d["W"], d["H"]
        lp = d["inv"].map(w)
        x0, y0, x1, y1 = 0.0, 0.0, W, H
        if "w" in h:
            x0 = lp.x()
        if "e" in h:
            x1 = lp.x()
        if "n" in h:
            y0 = lp.y()
        if "s" in h:
            y1 = lp.y()
        alt = bool(e.modifiers() & Qt.AltModifier)
        if alt:
            if "w" in h:
                x1 = W - x0
            if "e" in h:
                x0 = W - x1
            if "n" in h:
                y1 = H - y0
            if "s" in h:
                y0 = H - y1
        single = d["nodes"][0] if len(d["nodes"]) == 1 else None
        axis_aligned = single is None or (abs(world_transform(single).m12()) < 1e-9 and
                                          abs(world_transform(single).m21()) < 1e-9)
        if axis_aligned and not (e.modifiers() & Qt.ControlModifier):
            r = d["T0"].mapRect(QRectF(QPointF(x0, y0), QPointF(x1, y1)).normalized())
            ex = tuple(i for i, k in ((0, "w"), (2, "e")) if k in h)
            ey = tuple(i for i, k in ((0, "n"), (2, "s")) if k in h)
            dx, dy = self.snap_rect(r, *d["targets"], edges_x=ex, edges_y=ey)
            sx = d["T0"].m11() or 1
            sy = d["T0"].m22() or 1
            if "w" in h:
                x0 += dx / sx
            if "e" in h:
                x1 += dx / sx
            if "n" in h:
                y0 += dy / sy
            if "s" in h:
                y1 += dy / sy
        keep = bool(e.modifiers() & Qt.ShiftModifier) or (single is not None and single.type in ("image",))
        if keep and W > 0 and H > 0:
            nw, nh = x1 - x0, y1 - y0
            if h in ("n", "s"):
                k = nh / H
                cx = W / 2
                x0, x1 = cx - W * k / 2, cx + W * k / 2
            elif h in ("e", "w"):
                k = nw / W
                cy = H / 2
                y0, y1 = cy - H * k / 2, cy + H * k / 2
            else:
                k = max(abs(nw) / W, abs(nh) / H)
                if "w" in h:
                    x0 = x1 - W * k * (1 if nw >= 0 else -1)
                else:
                    x1 = x0 + W * k * (1 if nw >= 0 else -1)
                if "n" in h:
                    y0 = y1 - H * k * (1 if nh >= 0 else -1)
                else:
                    y1 = y0 + H * k * (1 if nh >= 0 else -1)
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        nw, nh = max(x1 - x0, 1.0 if W else 0.0), max(y1 - y0, 1.0 if H else 0.0)
        snap = self.ed.settings.get("snap_pixels", True)
        if single is not None:
            self._restore(single, d["orig"][single.id])
            if snap and single.rotation == 0:
                nw, nh = max(1.0, round(nw)) if W else nw, max(1.0, round(nh)) if H else nh
            cw = d["T0"].map(QPointF(x0 + nw / 2, y0 + nh / 2))
            pinv, _ = parent_transform(single).inverted()
            cl = pinv.map(cw)
            resize_node(single, nw, nh)
            single.x, single.y = cl.x() - nw / 2, cl.y() - nh / 2
            if snap and single.rotation == 0:
                single.x, single.y = round(single.x), round(single.y)
        else:
            sx = nw / W if W else 1.0
            sy = nh / H if H else 1.0
            for n in d["nodes"]:
                self._restore(n, d["orig"][n.id])
                b = d["bounds"][n.id]
                lx, ly = b.x() - d["T0"].dx(), b.y() - d["T0"].dy()
                target = QRectF(d["T0"].dx() + x0 + lx * sx, d["T0"].dy() + y0 + ly * sy, b.width() * sx,
                                b.height() * sy)
                resize_node(n, n.w * sx, n.h * sy)
                cur = world_bounds(n).center()
                pinv, _ = parent_transform(n).inverted()
                dl = pinv.map(target.center()) - pinv.map(cur)
                n.x += dl.x()
                n.y += dl.y()
        d["changed"] = True
        self.ed.live_changed()

    def _restore(self, n, d):
        """Reset a node's geometry (and vector points / group children) to the drag-start snapshot."""
        n.x, n.y, n.w, n.h = d.get("x", 0.0), d.get("y", 0.0), d.get("w", 100.0), d.get("h", 100.0)
        if n.type == "path":
            from .model import _copy
            n.paths = _copy(d.get("paths", []))
        if n.type == "text":
            n.sizing = d.get("sizing", "auto_w")
        if n.type == "group":
            for c, cd in zip(n.children, d.get("children", [])):
                self._restore(c, cd)

    def drag_rotate(self, w, e):
        d = self.drag
        c = d["center"]
        a = math.atan2(w.y() - c.y(), w.x() - c.x())
        delta = math.degrees(a - d["a0"])
        for n in d["nodes"]:
            ox, oy, orot = d["orig"][n.id]
            r = orot + delta
            if e.modifiers() & Qt.ShiftModifier:
                r = round(r / 15) * 15
            r = (r + 180) % 360 - 180
            real = r - orot
            n.rotation = round(r, 2)
            if len(d["nodes"]) > 1:
                oc = d["centers"][n.id]
                t = QTransform()
                t.translate(c.x(), c.y())
                t.rotate(real)
                t.translate(-c.x(), -c.y())
                nc = t.map(oc)
                pinv, _ = parent_transform(n).inverted()
                lc = pinv.map(nc)
                n.x, n.y = lc.x() - n.w / 2, lc.y() - n.h / 2
        d["changed"] = True
        self.ed.live_changed()

    # ================================================================== marquee
    def marquee_select(self):
        d = self.drag
        r = self.marquee
        pool = d["within"].children if d.get("within") is not None else self.ed.scope_children()
        hits = [n for n in pool if n.visible and not n.locked and world_bounds(n).intersects(r)]
        if r.width() * self.zoom < 3 and r.height() * self.zoom < 3:
            hits = []
        self.ed.select(d["add"] + [n for n in hits if n not in d["add"]], quiet=True)

    # ================================================================== creating
    def create_press(self, w, tool, e):
        ed = self.ed
        if tool == "text":
            parent = self.container_at(w)
            pinv, _ = world_transform(parent).inverted() if parent.type != "page" else (QTransform(), True)
            lp = pinv.map(w)
            n = Node("text", x=round(lp.x()), y=round(lp.y()), size=ed.default_text_size(), sizing="auto_w",
                     fills=[solid(ed.tool_opts.get("text_color", "#141413"))])
            self.drag = {"mode": "create", "node": n, "parent": parent, "start": w, "pinv": pinv, "tool": tool,
                         "pending": True}
            return
        if tool == "sticky":
            n = Node("sticky", fills=[solid(ed.tool_opts["sticky"])])
            n.x, n.y = round(w.x() - n.w / 2), round(w.y() - n.h / 2)
            self._place_simple(n, edit=True)
            return
        if tool == "stamp":
            n = Node("stamp", glyph=ed.tool_opts.get("stamp", "👍"))
            n.x, n.y = w.x() - n.w / 2, w.y() - n.h / 2
            self._place_simple(n, edit=False, keep_tool=True)
            return
        parent = self.container_at(w) if tool != "section" or ed.doc.kind != "board" else ed.page
        if tool in ("frame", "section") and parent.type == "section" and tool == "section":
            parent = ed.scope_root()
        pinv, _ = world_transform(parent).inverted() if parent.type != "page" else (QTransform(), True)
        lp = pinv.map(w)
        n = ed.make_tool_node(tool)
        n.x, n.y, n.w, n.h = lp.x(), lp.y(), 0.0, 0.0
        if n.type == "path":
            n.paths = [{"pts": [[lp.x(), lp.y()] * 3, [lp.x(), lp.y()] * 3], "closed": False}]
            n.x = n.y = 0.0
        ed.add_node(n, parent)
        self.drag = {"mode": "create", "node": n, "parent": parent, "start": w, "pinv": pinv, "tool": tool,
                     "lp0": lp}

    def _place_simple(self, n, edit=False, keep_tool=False):
        parent = self.container_at(QPointF(n.x + n.w / 2, n.y + n.h / 2))
        if parent.type != "page":
            pinv, _ = world_transform(parent).inverted()
            lp = pinv.map(QPointF(n.x, n.y))
            n.x, n.y = lp.x(), lp.y()
        self.ed.add_node(n, parent)
        self.ed.select([n])
        if not keep_tool:
            self.ed.set_tool("select")
        self.ed.commit("Новый объект")
        if edit:
            self.start_text_edit(n, new=True)

    def drag_create(self, w, e):
        d = self.drag
        n = d["node"]
        if d.get("pending"):  # text tool: dragging makes a fixed-width box
            if QLineF(self.to_view(d["start"]), self.to_view(w)).length() < 4:
                return
            d.pop("pending")
            n.sizing = "auto_h"
            self.ed.add_node(n, d["parent"])
            d["lp0"] = QPointF(n.x, n.y)
        a = d["start"]
        b = QPointF(w)
        if n.type == "path":
            if e.modifiers() & Qt.ShiftModifier:
                ang = math.atan2(b.y() - a.y(), b.x() - a.x())
                ang = round(ang / (math.pi / 4)) * (math.pi / 4)
                ln = QLineF(a, b).length()
                b = QPointF(a.x() + math.cos(ang) * ln, a.y() + math.sin(ang) * ln)
            p0 = d["pinv"].map(a)
            p1 = d["pinv"].map(b)
            n.x = n.y = 0.0
            n.paths = [{"pts": [[p0.x(), p0.y()] * 3, [p1.x(), p1.y()] * 3], "closed": False}]
            normalize_path(n)
        else:
            if e.modifiers() & Qt.ShiftModifier:
                s = max(abs(b.x() - a.x()), abs(b.y() - a.y()))
                b = QPointF(a.x() + math.copysign(s, b.x() - a.x() or 1), a.y() + math.copysign(s, b.y() - a.y() or 1))
            if e.modifiers() & Qt.AltModifier:
                a = QPointF(2 * a.x() - b.x(), 2 * a.y() - b.y())
            r = QRectF(d["pinv"].map(a), d["pinv"].map(b)).normalized()
            n.x, n.y = round(r.x()), round(r.y())
            if n.type == "text":
                n.w = max(20.0, round(r.width()))
            else:
                n.w, n.h = round(r.width()), round(r.height())
        self.ed.live_changed()

    def end_create(self, d, w):
        n = d["node"]
        ed = self.ed
        if d.get("pending"):  # plain click with the text tool
            ed.add_node(n, d["parent"])
            ed.select([n])
            ed.set_tool("select")
            ed.live_changed()
            self.start_text_edit(n, new=True)
            return
        tiny = QLineF(self.to_view(d["start"]), self.to_view(w)).length() < 4
        if tiny:
            dw, dh = ed.default_size(d["tool"])
            if n.type == "path":
                p0 = d["pinv"].map(d["start"])
                n.x = n.y = 0.0
                n.paths = [{"pts": [[p0.x(), p0.y()] * 3, [p0.x() + dw, p0.y()] * 3], "closed": False}]
                normalize_path(n)
            elif n.type != "text":
                n.w, n.h = dw, dh
                if d["tool"] in ("frame", "section", "shape") or ed.doc.kind == "board":
                    n.x, n.y = round(n.x - dw / 2), round(n.y - dh / 2)
        if n.type in ("frame", "section"):
            ed.adopt_contained(n)
        ed.select([n])
        ed.set_tool("select")
        ed.commit("Новый объект")
        if n.type in ("text", "shape") and ed.doc.kind == "board" or n.type == "text":
            self.start_text_edit(n, new=n.type == "text")

    # ================================================================== freehand
    def end_pencil(self, d):
        pts = d["pts"]
        if len(pts) < 2:
            return
        pts = _rdp(pts, 0.8 / self.zoom)
        st = d["style"]
        parent = self.container_at(pts[0])
        pinv, _ = world_transform(parent).inverted() if parent.type != "page" else (QTransform(), True)
        local = [pinv.map(q) for q in pts]
        n = Node("path", name=st.get("name", "Карандаш"), paths=[{"pts": _smooth(local), "closed": False}],
                 strokes=[solid(st["color"])], stroke_width=st["width"], stroke_align="center",
                 opacity=st.get("opacity", 1.0))
        normalize_path(n)
        self.ed.add_node(n, parent)
        self.ed.commit("Рисование")

    # ================================================================== pen
    def pen_press(self, w, e):
        if self.pen is None:
            self.pen = {"pts": [], "cursor": w}
        pts = self.pen["pts"]
        if len(pts) > 2 and QLineF(self.to_view(QPointF(pts[0][0], pts[0][1])), self.to_view(w)).length() <= 8:
            self.finish_pen(True)
            return
        pts.append([w.x(), w.y()] * 3)
        self.drag = {"mode": "pen_handle"}
        self.update()

    def finish_pen(self, closed):
        pen, self.pen = self.pen, None
        if not pen or len(pen["pts"]) < 2:
            self.update()
            return
        pts = pen["pts"]
        parent = self.container_at(QPointF(pts[0][0], pts[0][1]))
        pinv, _ = world_transform(parent).inverted() if parent.type != "page" else (QTransform(), True)
        local = []
        for pt in pts:
            a = pinv.map(QPointF(pt[0], pt[1]))
            b = pinv.map(QPointF(pt[2], pt[3]))
            c = pinv.map(QPointF(pt[4], pt[5]))
            local.append([a.x(), a.y(), b.x(), b.y(), c.x(), c.y()])
        n = Node("path", paths=[{"pts": local, "closed": closed}], strokes=[solid("#141413")], stroke_width=1.5,
                 fills=[solid("#D9D9D9")] if closed else [])
        normalize_path(n)
        self.ed.add_node(n, parent)
        self.ed.select([n])
        self.ed.set_tool("select")
        self.ed.commit("Перо")

    # ================================================================== vector editing
    def enter_vector_edit(self, n):
        self.vec = {"node": n, "sel": None}
        self.ed.status(f"Редактирование точек «{n.name}» — перетаскивайте точки и рычаги, Delete удаляет точку, "
                       f"Esc — готово")
        self.update()

    def exit_vector_edit(self):
        if self.vec is None:
            return
        n = self.vec["node"]
        self.vec = None
        if n.paths and any(sp["pts"] for sp in n.paths):
            normalize_path(n)
        self.ed.commit("Точки")
        self.ed.status("")
        self.update()

    def vec_press(self, pos, w):
        n = self.vec["node"]
        t = world_transform(n) * self.vt()
        for si, sp in enumerate(n.paths):
            for i, pt in enumerate(sp["pts"]):
                for kind, (x, y) in (("anchor", (pt[0], pt[1])), ("in", (pt[2], pt[3])), ("out", (pt[4], pt[5]))):
                    if kind != "anchor" and (x, y) == (pt[0], pt[1]):
                        continue
                    if QLineF(pos, t.map(QPointF(x, y))).length() <= 6:
                        self.vec["sel"] = (si, i)
                        inv, _ = world_transform(n).inverted()
                        self.drag = {"mode": "vec_point", "kind": kind, "si": si, "i": i, "inv": inv,
                                     "orig": list(pt), "start": inv.map(w)}
                        self.update()
                        return True
        return False

    def vec_drag(self, w, e):
        d = self.drag
        n = self.vec["node"]
        pt = n.paths[d["si"]]["pts"][d["i"]]
        lp = d["inv"].map(w)
        o = d["orig"]
        if d["kind"] == "anchor":
            dx, dy = lp.x() - d["start"].x(), lp.y() - d["start"].y()
            pt[:] = [o[0] + dx, o[1] + dy, o[2] + dx, o[3] + dy, o[4] + dx, o[5] + dy]
        else:
            mine, other = (2, 4) if d["kind"] == "in" else (4, 2)
            pt[mine], pt[mine + 1] = lp.x(), lp.y()
            if not (e.modifiers() & Qt.AltModifier):  # smooth point: mirror the opposite handle
                pt[other], pt[other + 1] = 2 * pt[0] - lp.x(), 2 * pt[1] - lp.y()
        self.ed.live_changed(relayout=False)

    def vec_delete(self):
        sel = self.vec.get("sel")
        if sel is None:
            return
        n = self.vec["node"]
        si, i = sel
        pts = n.paths[si]["pts"]
        if len(pts) <= 2:
            n.paths.pop(si)
        else:
            pts.pop(i)
        self.vec["sel"] = None
        if not n.paths:
            self.vec = None
            self.ed.delete_nodes([n])
            return
        self.ed.live_changed(relayout=False)

    # ================================================================== connectors
    def connector_press(self, w):
        chain = self.hit_chain(w, self.attachable())
        src = next((c for c in reversed(chain) if c.type != "connector"), None)
        start = {"id": src.id} if src is not None else {"x": w.x(), "y": w.y()}
        n = Node("connector", start=start, end={"x": w.x(), "y": w.y()},
                 strokes=[solid(self.ed.tool_opts.get("line_color", "#141413"))],
                 route=self.ed.tool_opts.get("route", "elbow"))
        self.ed.add_node(n, self.ed.page)
        self.drag = {"mode": "connector", "node": n, "start": w, "from": src}

    def end_connector(self, d, w):
        n = d["node"]
        chain = self.hit_chain(w, self.attachable())
        target = next((c for c in reversed(chain) if c.type != "connector" and c is not d.get("from")), None)
        if target is not None:
            n.end = {"id": target.id}
        elif QLineF(self.to_view(d["start"]), self.to_view(w)).length() < 6:
            self.ed.remove_node(n)
            self.ed.live_changed()
            return
        self.ed.doc.update_connectors(self.ed.page)
        self.ed.select([n])
        self.ed.set_tool("select")
        self.ed.commit("Соединитель")

    # ================================================================== text editing
    def start_text_edit(self, n, new=False):
        self.finish_text_edit()
        if n.locked:
            return
        self.editing = n
        self.editing_new = new
        self.hidden = {n.id} if n.type != "connector" else set()
        ov = TextOverlay(self)
        self.overlay = ov
        ov.setPlainText(n.text)
        self._style_overlay()
        ov.textChanged.connect(self._overlay_changed)
        ov.show()
        ov.setFocus()
        if not new:
            ov.selectAll()
        self.reposition_overlay()
        self.update()

    def _style_overlay(self):
        n = self.editing
        ov = self.overlay
        if n.type in ("sticky", "shape"):
            _, _, size = textlib.box_block(n)
        else:
            size = n.size
        f = textlib.node_font(n, size * self.zoom)
        ov.setFont(f)
        if n.type == "text":
            from .render import first_color
            color = first_color(n.fills, "#141413")
        elif n.type == "connector":
            color = "#141413"
        else:
            color = n.text_color
        ov.setStyleSheet(f"QPlainTextEdit {{ background: transparent; border: none; padding: 0; color: {color}; "
                         f"selection-background-color: rgba(217,119,87,0.35); }}")
        opt = QTextOption()
        opt.setAlignment({"center": Qt.AlignHCenter, "right": Qt.AlignRight}.get(n.talign, Qt.AlignLeft))
        opt.setWrapMode(QTextOption.NoWrap if (n.type == "text" and n.sizing == "auto_w") else
                        QTextOption.WrapAtWordBoundaryOrAnywhere)
        ov.document().setDefaultTextOption(opt)

    def _overlay_changed(self):
        n = self.editing
        if n is None:
            return
        n.text = self.overlay.toPlainText()
        self.ed.live_changed()
        self.reposition_overlay()

    def reposition_overlay(self):
        if self.overlay is None or self.editing is None:
            return
        n = self.editing
        z = self.zoom
        if n.type == "connector":
            mid = shape_path(n).pointAtPercent(0.5) if n._path is not None else QPointF()
            v = self.to_view(mid)
            self.overlay.setGeometry(int(v.x() - 100), int(v.y() - 14 * z), 200, int(max(24, 30 * z)))
            return
        r = self.view_rect(world_bounds(n))
        if n.type in ("sticky", "shape"):
            block, pad, size = textlib.box_block(n)
            inner = QRectF(r.x() + pad * z, r.y() + pad * z, max(10.0, r.width() - 2 * pad * z),
                           max(10.0, r.height() - 2 * pad * z))
            bh = block.h * z
            top = inner.y() + (inner.height() - bh) / 2 if n.valign == "center" else inner.y()
            self.overlay.setGeometry(int(inner.x()), int(top), int(inner.width()) + 2,
                                     int(max(bh, size * z * 1.4)) + 4)
            return
        extra = 40 if n.sizing == "auto_w" else 2
        x = r.x()
        if n.sizing == "auto_w" and n.talign == "center":
            x -= extra / 2
        elif n.sizing == "auto_w" and n.talign == "right":
            x -= extra
        self.overlay.setGeometry(int(x), int(r.y()), int(r.width() + extra), int(max(r.height(), n.size * z * 1.3)) + 4)

    def finish_text_edit_if_unfocused(self):
        if self.overlay is not None and not self.overlay.hasFocus() and self.isVisible():
            fw = self.window().focusWidget() if self.window() else None
            if fw is not None and fw is not self.overlay:
                self.finish_text_edit()

    def finish_text_edit(self):
        n = self.editing
        if n is None:
            return
        ov = self.overlay
        self.editing = None
        self.overlay = None
        self.hidden = set()
        text = ov.toPlainText()
        ov.hide()
        ov.deleteLater()
        if n.type == "text" and not text.strip():
            self.ed.delete_nodes([n], commit=False)
            self.ed.commit("Текст")
        else:
            n.text = text
            if n.type == "text" and getattr(self, "editing_new", False):
                n.name = text.split("\n")[0][:40] or n.name
            self.ed.set_attr([n], "text", text)
        self.setFocus()
        self.update()

    # ================================================================== keyboard
    def keyPressEvent(self, e):
        key = e.key()
        mods = e.modifiers()
        ed = self.ed
        if self.pen is not None and key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape):
            self.finish_pen(False)
            return
        if self.vec is not None:
            if key in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter):
                self.exit_vector_edit()
                return
            if key in (Qt.Key_Delete, Qt.Key_Backspace):
                self.vec_delete()
                return
        if key == Qt.Key_Space and not e.isAutoRepeat():
            self.space = True
            self.setCursor(Qt.OpenHandCursor)
            return
        if key in (Qt.Key_Delete, Qt.Key_Backspace):
            ed.delete_selection()
            return
        if key == Qt.Key_Escape:
            if ed.tool != "select":
                ed.set_tool("select")
            elif ed.selection:
                parents = [n.parent for n in ed.selection if n.parent is not None and n.parent.type != "page"
                           and n.parent is not ed.scope_root()]
                ed.select(list(dict.fromkeys(parents)))
            return
        if key in (Qt.Key_Return, Qt.Key_Enter) and len(ed.selection) == 1:
            n = ed.selection[0]
            if n.type in TEXTISH:
                self.start_text_edit(n)
            elif n.type == "path":
                self.enter_vector_edit(n)
            elif n.container and n.children:
                ed.select([c for c in n.children if c.visible])
            return
        arrows = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0), Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}
        if key in arrows and not (mods & Qt.ControlModifier):
            if ed.doc.kind == "slides" and not ed.selection:
                ed.step_slide(1 if key in (Qt.Key_Right, Qt.Key_Down) else -1)
                return
            dx, dy = arrows[key]
            k = 10 if mods & Qt.ShiftModifier else 1
            ed.nudge(dx * k, dy * k)
            return
        if mods & Qt.ShiftModifier and key in (Qt.Key_1, Qt.Key_Exclam):
            self.auto_fit = ed.doc.kind == "slides"
            self.fit()
            return
        if mods & Qt.ShiftModifier and key in (Qt.Key_2, Qt.Key_At, Qt.Key_QuoteDbl):
            if ed.selection:
                self.fit(union_rect(world_bounds(n) for n in ed.selection), 80)
            return
        if mods & Qt.ShiftModifier and key in (Qt.Key_0, Qt.Key_ParenRight):
            self.set_zoom(1.0)
            return
        if mods & Qt.AltModifier and not (mods & (Qt.ControlModifier | Qt.MetaModifier)):
            align = {Qt.Key_A: "align_left", Qt.Key_H: "align_hcenter", Qt.Key_D: "align_right",
                     Qt.Key_W: "align_top", Qt.Key_V: "align_vcenter", Qt.Key_S: "align_bottom"}.get(key)
            if align and ed.selection:
                ed.align(align)
                return
        if not (mods & (Qt.ControlModifier | Qt.MetaModifier | Qt.AltModifier)):
            ch = (e.text() or "").lower()
            ch = CYR.get(ch, ch)
            if ch and ed.shortcut(ch, bool(mods & Qt.ShiftModifier)):
                return
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key_Space and not e.isAutoRepeat():
            self.space = False
            self.setCursor(Qt.ArrowCursor)
            return
        super().keyReleaseEvent(e)

    # ================================================================== drag & drop
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasImage():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        w = self.to_world(e.position())
        md = e.mimeData()
        if md.hasUrls():
            paths = [u.toLocalFile() for u in md.urls() if u.isLocalFile()]
            self.ed.import_files(paths, w)
        elif md.hasImage():
            self.ed.insert_qimage(md.imageData(), w)
        e.acceptProposedAction()


def _fmt(v):
    v = round(v, 2)
    return str(int(v)) if v == int(v) else f"{v:g}"


def _rdp(points, eps):
    if len(points) < 3:
        return points
    a, b = points[0], points[-1]
    line = QLineF(a, b)
    best, idx = -1.0, 0
    for i in range(1, len(points) - 1):
        p = points[i]
        if line.length() == 0:
            d = QLineF(a, p).length()
        else:
            d = abs((b.x() - a.x()) * (a.y() - p.y()) - (a.x() - p.x()) * (b.y() - a.y())) / line.length()
        if d > best:
            best, idx = d, i
    if best > eps:
        return _rdp(points[:idx + 1], eps)[:-1] + _rdp(points[idx:], eps)
    return [a, b]


def _smooth(pts):
    """Catmull-Rom through the points → cubic handles."""
    out = []
    n = len(pts)
    for i, p in enumerate(pts):
        prev = pts[i - 1] if i > 0 else p
        nxt = pts[i + 1] if i < n - 1 else p
        tx, ty = (nxt.x() - prev.x()) / 6, (nxt.y() - prev.y()) / 6
        if i == 0 or i == n - 1:
            tx = ty = 0.0
        out.append([p.x(), p.y(), p.x() - tx, p.y() - ty, p.x() + tx, p.y() + ty])
    return out
