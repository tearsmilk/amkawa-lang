"""Document model shared by all four kinds of files.

Document → pages → nodes. A node is a frame, group, shape, vector, text, component / instance, or one of the
FigJam objects (sticky, shape with text, connector, stamp, section). Slides are frames on the page; a site page
is one root frame (role "webpage") laid out with auto layout. Coordinates of a node are relative to its parent;
rotation is around the node's centre."""
import copy
import hashlib
import json
import math
import uuid

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath, QPainterPathStroker, QTransform

from . import text as textlib

KINDS = ("design", "board", "slides", "site")
KIND_TITLES = {"design": "Дизайн", "board": "Доска", "slides": "Презентация", "site": "Сайт"}
KIND_EXT = ".lambda"

FRAMELIKE = {"frame", "component", "instance", "section"}
CONTAINERS = FRAMELIKE | {"group", "page"}
TEXTISH = {"text", "sticky", "shape"}
LAYOUT_KEYS = ("layout", "gap", "pad", "align", "justify", "hug_w", "hug_h", "stack", "clip")


def solid(color, opacity=1.0):
    return {"type": "solid", "color": color, "opacity": opacity}


def new_id():
    return uuid.uuid4().hex[:10]


DEFAULTS = dict(
    name="", x=0.0, y=0.0, w=100.0, h=100.0, rotation=0.0, visible=True, locked=False, opacity=1.0, blend="normal",
    fills=[], strokes=[], stroke_width=1.0, stroke_align="inside", dash=0.0, radius=0.0, effects=[], mask=False,
    # containers and auto layout (pad = [top, right, bottom, left])
    clip=False, layout="none", gap=0.0, pad=[0.0, 0.0, 0.0, 0.0], align="start", justify="start",
    hug_w=False, hug_h=False, stack=False, grow=False, stretch=False, absolute=False, max_w=0.0,
    # text
    text="", font="", size=16.0, weight=400, italic=False, talign="left", valign="top", line_height=0.0,
    letter=0.0, sizing="auto_w", deco="", tag="", text_color="#141413",
    # vectors: paths = [{"pts": [[x, y, in_x, in_y, out_x, out_y], …], "closed": bool}, …]
    paths=[], fill_rule="nonzero", arrow_start="none", arrow_end="none", count=5, ratio=0.38,
    # components
    master="", overrides={},
    # FigJam
    shape="rect", start={}, end={}, route="elbow", glyph="👍",
    # prototype / slides / site
    link={}, notes="", transition="none", href="", hover={}, role="", bg="",
)

TYPE_INIT = {
    "page": dict(name="Страница 1", w=0.0, h=0.0),
    "frame": dict(name="Фрейм", clip=True, fills=[solid("#FFFFFF")]),
    "component": dict(name="Компонент", clip=True, fills=[solid("#FFFFFF")]),
    "instance": dict(name="Экземпляр", clip=True),
    "group": dict(name="Группа"),
    "section": dict(name="Секция", fills=[solid("#F0EEE6")], radius=16.0, w=800.0, h=600.0, size=24.0),
    "rect": dict(name="Прямоугольник", fills=[solid("#D9D9D9")]),
    "ellipse": dict(name="Эллипс", fills=[solid("#D9D9D9")]),
    "polygon": dict(name="Многоугольник", fills=[solid("#D9D9D9")], count=3),
    "star": dict(name="Звезда", fills=[solid("#D9D9D9")], count=5),
    "path": dict(name="Вектор", stroke_align="center"),
    "text": dict(name="Текст", fills=[solid("#141413")], h=20.0),
    "sticky": dict(name="Стикер", w=240.0, h=240.0, fills=[solid("#FFE29A")], size=24.0, sizing="fixed"),
    "shape": dict(name="Фигура", w=200.0, h=120.0, fills=[solid("#FFFFFF")], strokes=[solid("#141413")],
                  stroke_width=2.0, size=18.0, talign="center", valign="center", sizing="fixed"),
    "connector": dict(name="Соединитель", strokes=[solid("#141413")], stroke_width=2.0, stroke_align="center",
                      arrow_end="arrow", size=14.0, w=0.0, h=0.0),
    "stamp": dict(name="Штамп", w=64.0, h=64.0, fills=[solid("#FFFFFF")], strokes=[solid("#E3DFD3")]),
}
TYPE_TITLES = {"page": "Страница", "frame": "Фрейм", "component": "Компонент", "instance": "Экземпляр",
               "group": "Группа", "section": "Секция", "rect": "Прямоугольник", "ellipse": "Эллипс",
               "polygon": "Многоугольник", "star": "Звезда", "path": "Вектор", "text": "Текст", "sticky": "Стикер",
               "shape": "Фигура", "connector": "Соединитель", "stamp": "Штамп"}

SHAPE_KINDS = [("rect", "Прямоугольник"), ("rounded", "Скруглённый"), ("ellipse", "Эллипс"), ("diamond", "Ромб"),
               ("triangle", "Треугольник"), ("parallelogram", "Параллелограмм"), ("hexagon", "Шестиугольник"),
               ("star", "Звезда"), ("arrow", "Стрелка"), ("plus", "Плюс"), ("cylinder", "Цилиндр")]

_type_defaults = {}


def defaults_for(type_):
    d = _type_defaults.get(type_)
    if d is None:
        d = dict(DEFAULTS)
        d.update(TYPE_INIT.get(type_, {}))
        _type_defaults[type_] = d
    return d


def _copy(v):
    return copy.deepcopy(v) if isinstance(v, (list, dict)) else v


class Node:
    def __init__(self, type_, id=None, **kw):
        self.type = type_
        self.id = id or new_id()
        self.parent = None
        self.children = []
        for k, v in defaults_for(type_).items():
            setattr(self, k, _copy(v))
        children = kw.pop("children", ())
        for k, v in kw.items():
            setattr(self, k, v)
        for c in children:
            self.add(c)
        self._path = None  # connector geometry (world), recomputed by Document.update_connectors

    def __repr__(self):
        return f"<{self.type} {self.name!r} {self.id}>"

    # ------------------------------------------------------------------ tree
    def add(self, child, index=None):
        if child.parent is not None:
            child.parent.children.remove(child)
        child.parent = self
        if index is None or index >= len(self.children):
            self.children.append(child)
        else:
            self.children.insert(max(0, index), child)
        return child

    def remove(self):
        if self.parent is not None:
            self.parent.children.remove(self)
            self.parent = None

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def ancestors(self):
        a = self.parent
        while a is not None:
            yield a
            a = a.parent

    def is_ancestor_of(self, other):
        return any(a is self for a in other.ancestors())

    def page(self):
        n = self
        while n.parent is not None:
            n = n.parent
        return n

    @property
    def container(self):
        return self.type in CONTAINERS

    @property
    def auto(self):
        return self.layout in ("row", "column") and self.type in FRAMELIKE

    def in_flow(self):
        return self.parent is not None and self.parent.auto and not self.absolute

    # ------------------------------------------------------------------ (de)serialisation
    def to_dict(self):
        base = defaults_for(self.type)
        d = {"type": self.type, "id": self.id}
        for k in DEFAULTS:
            v = getattr(self, k)
            if v != base[k]:
                d[k] = v
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d

    @classmethod
    def from_dict(cls, d):
        kw = {k: _copy(v) for k, v in d.items() if k in DEFAULTS}
        n = cls(d["type"], id=d.get("id"), **kw)
        for cd in d.get("children", ()):
            n.add(cls.from_dict(cd))
        return n

    def clone(self, keep_ids=False):
        d = self.to_dict()
        if not keep_ids:
            _remap_ids(d)
        return Node.from_dict(d)


def _remap_ids(d, mapping=None):
    mapping = {} if mapping is None else mapping

    def walk(x):
        old = x["id"]
        x["id"] = mapping.setdefault(old, new_id())
        for c in x.get("children", ()):
            walk(c)
    walk(d)
    # connectors inside a cloned subtree keep pointing at the cloned endpoints
    def fix(x):
        for key in ("start", "end"):
            e = x.get(key)
            if isinstance(e, dict) and e.get("id") in mapping:
                e["id"] = mapping[e["id"]]
        for c in x.get("children", ()):
            fix(c)
    fix(d)
    return mapping


# ====================================================================== geometry
def local_transform(n):
    t = QTransform()
    if n.type in ("page", "connector"):
        return t
    t.translate(n.x, n.y)
    if n.rotation:
        t.translate(n.w / 2, n.h / 2)
        t.rotate(n.rotation)
        t.translate(-n.w / 2, -n.h / 2)
    return t


def world_transform(n):
    t = local_transform(n)
    a = n.parent
    while a is not None:
        t = t * local_transform(a)
        a = a.parent
    return t


def parent_transform(n):
    return world_transform(n.parent) if n.parent is not None else QTransform()


def build_path(paths):
    p = QPainterPath()
    for sp in paths:
        pts = sp.get("pts") or []
        if not pts:
            continue
        p.moveTo(pts[0][0], pts[0][1])

        def seg(a, b):
            if a[4] == a[0] and a[5] == a[1] and b[2] == b[0] and b[3] == b[1]:
                p.lineTo(b[0], b[1])
            else:
                p.cubicTo(a[4], a[5], b[2], b[3], b[0], b[1])
        for i in range(1, len(pts)):
            seg(pts[i - 1], pts[i])
        if sp.get("closed") and len(pts) > 1:
            seg(pts[-1], pts[0])
            p.closeSubpath()
    return p


def path_to_points(qp, eps=1e-6):
    """QPainterPath → our sub-path list (corner handles equal the anchor)."""
    out = []
    cur = None
    i = 0
    n = qp.elementCount()
    while i < n:
        e = qp.elementAt(i)
        if e.isMoveTo():
            cur = {"pts": [[e.x, e.y, e.x, e.y, e.x, e.y]], "closed": False}
            out.append(cur)
            i += 1
        elif e.isLineTo():
            cur["pts"].append([e.x, e.y, e.x, e.y, e.x, e.y])
            i += 1
        else:  # CurveTo + 2 × CurveToData
            c1, c2 = e, qp.elementAt(i + 1)
            end = qp.elementAt(i + 2)
            prev = cur["pts"][-1]
            prev[4], prev[5] = c1.x, c1.y
            cur["pts"].append([end.x, end.y, c2.x, c2.y, end.x, end.y])
            i += 3
    for sp in out:
        pts = sp["pts"]
        if len(pts) > 2 and abs(pts[0][0] - pts[-1][0]) < eps and abs(pts[0][1] - pts[-1][1]) < eps:
            last = pts.pop()
            pts[0][2], pts[0][3] = last[2], last[3]
            sp["closed"] = True
    return [sp for sp in out if len(sp["pts"]) > 1 or sp["closed"]]


def _poly(points):
    p = QPainterPath()
    p.moveTo(*points[0])
    for q in points[1:]:
        p.lineTo(*q)
    p.closeSubpath()
    return p


def regular_points(count, w, h, star=False, ratio=0.38):
    k = max(3, int(count))
    m = 2 * k if star else k
    raw = []
    for i in range(m):
        a = -math.pi / 2 + i * math.pi * 2 / m
        r = ratio if (star and i % 2) else 1.0
        raw.append((math.cos(a) * r, math.sin(a) * r))
    xs = [q[0] for q in raw]
    ys = [q[1] for q in raw]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    return [((q[0] - x0) / (x1 - x0 or 1) * w, (q[1] - y0) / (y1 - y0 or 1) * h) for q in raw]


def figjam_shape(kind, w, h):
    p = QPainterPath()
    if kind == "ellipse":
        p.addEllipse(QRectF(0, 0, w, h))
    elif kind == "rounded":
        r = min(w, h) * 0.22
        p.addRoundedRect(QRectF(0, 0, w, h), r, r)
    elif kind == "diamond":
        p = _poly([(w / 2, 0), (w, h / 2), (w / 2, h), (0, h / 2)])
    elif kind == "triangle":
        p = _poly([(w / 2, 0), (w, h), (0, h)])
    elif kind == "parallelogram":
        p = _poly([(w * 0.2, 0), (w, 0), (w * 0.8, h), (0, h)])
    elif kind == "hexagon":
        p = _poly([(w * 0.25, 0), (w * 0.75, 0), (w, h / 2), (w * 0.75, h), (w * 0.25, h), (0, h / 2)])
    elif kind == "star":
        p = _poly(regular_points(5, w, h, True, 0.45))
    elif kind == "arrow":
        p = _poly([(0, h * 0.28), (w * 0.62, h * 0.28), (w * 0.62, 0), (w, h / 2), (w * 0.62, h), (w * 0.62, h * 0.72),
                   (0, h * 0.72)])
    elif kind == "plus":
        a, b = 0.32, 0.68
        p = _poly([(w * a, 0), (w * b, 0), (w * b, h * a), (w, h * a), (w, h * b), (w * b, h * b), (w * b, h),
                   (w * a, h), (w * a, h * b), (0, h * b), (0, h * a), (w * a, h * a)])
    elif kind == "cylinder":
        e = min(h * 0.16, 28.0)
        p.moveTo(0, e)
        p.arcTo(QRectF(0, 0, w, 2 * e), 180, -180)
        p.lineTo(w, h - e)
        p.arcTo(QRectF(0, h - 2 * e, w, 2 * e), 0, -180)
        p.closeSubpath()
    else:
        p.addRect(QRectF(0, 0, w, h))
    return p


def shape_path(n):
    """Outline of a node in its local coordinates (connectors: world coordinates)."""
    t = n.type
    w, h = n.w, n.h
    if t == "connector":
        return n._path if n._path is not None else QPainterPath()
    if t == "path":
        p = build_path(n.paths)
        if n.fill_rule == "evenodd":
            from PySide6.QtCore import Qt
            p.setFillRule(Qt.OddEvenFill)
        return p
    if t in ("ellipse", "stamp"):
        p = QPainterPath()
        p.addEllipse(QRectF(0, 0, w, h))
        return p
    if t == "polygon":
        return _poly(regular_points(n.count, w, h))
    if t == "star":
        return _poly(regular_points(n.count, w, h, True, n.ratio))
    if t == "shape":
        return figjam_shape(n.shape, w, h)
    p = QPainterPath()
    r = min(n.radius, w / 2, h / 2)
    if r > 0:
        p.addRoundedRect(QRectF(0, 0, w, h), r, r)
    else:
        p.addRect(QRectF(0, 0, w, h))
    return p


def is_open(n):
    return n.type == "connector" or (n.type == "path" and not all(sp.get("closed") for sp in n.paths))


def world_bounds(n):
    if n.type == "connector":
        return shape_path(n).boundingRect()
    if n.type == "page":
        r = None
        for c in n.children:
            b = world_bounds(c)
            r = b if r is None else r.united(b)
        return r or QRectF()
    return world_transform(n).mapRect(QRectF(0, 0, n.w, n.h))


def world_shape(n):
    if n.type == "connector":
        return shape_path(n)
    return world_transform(n).map(shape_path(n))


def stroke_outline(n, width=None):
    s = QPainterPathStroker()
    s.setWidth(max(0.5, width if width is not None else n.stroke_width))
    from PySide6.QtCore import Qt
    s.setCapStyle(Qt.RoundCap)
    s.setJoinStyle(Qt.RoundJoin)
    return s.createStroke(shape_path(n))


def union_rect(rects):
    r = None
    for b in rects:
        r = QRectF(b) if r is None else r.united(b)
    return r or QRectF()


# ====================================================================== resizing / normalising
def resize_node(n, w, h):
    w, h = max(0.0, w), max(0.0, h)
    sx = w / n.w if n.w else 1.0
    sy = h / n.h if n.h else 1.0
    if n.type == "path":
        for sp in n.paths:
            for pt in sp["pts"]:
                pt[0] *= sx; pt[2] *= sx; pt[4] *= sx
                pt[1] *= sy; pt[3] *= sy; pt[5] *= sy
    elif n.type == "group":
        for c in n.children:
            c.x *= sx
            c.y *= sy
            resize_node(c, c.w * sx, c.h * sy)
    elif n.type == "text":
        if n.sizing == "auto_w" and abs(w - n.w) > 0.01:
            n.sizing = "auto_h"
        if n.sizing == "auto_h" and abs(h - n.h) > 0.01 and abs(w - n.w) <= 0.01:
            n.sizing = "fixed"
    n.w, n.h = w, h


def normalize_path(n):
    """Shift the points so that the path's bounds start at (0, 0) and fit w × h."""
    b = build_path(n.paths).boundingRect()
    dx, dy = b.x(), b.y()
    for sp in n.paths:
        for pt in sp["pts"]:
            pt[0] -= dx; pt[2] -= dx; pt[4] -= dx
            pt[1] -= dy; pt[3] -= dy; pt[5] -= dy
    # keep the drawing in place: x' = x + c - c' + R(d + c' - c)  (rotation is around the centre c)
    c, s = math.cos(math.radians(n.rotation)), math.sin(math.radians(n.rotation))
    vx = dx + b.width() / 2 - n.w / 2
    vy = dy + b.height() / 2 - n.h / 2
    n.x += n.w / 2 - b.width() / 2 + c * vx - s * vy
    n.y += n.h / 2 - b.height() / 2 + s * vx + c * vy
    n.w, n.h = b.width(), b.height()


def normalize_group(g):
    if not g.children:
        return
    r = union_rect(local_transform(c).mapRect(QRectF(0, 0, c.w, c.h)) for c in g.children if c.type != "connector")
    dx, dy = r.x(), r.y()
    if abs(dx) > 1e-9 or abs(dy) > 1e-9:
        for c in g.children:
            c.x -= dx
            c.y -= dy
        g.x += dx
        g.y += dy
    g.w, g.h = r.width(), r.height()


# ====================================================================== auto layout
def fit_text(n, forced_width=False):
    if n.sizing == "fixed":
        return
    if n.sizing == "auto_w" and not forced_width:
        b = textlib.node_block(n)
        n.w, n.h = b.w, b.h
    else:
        n.h = textlib.node_block(n, n.w).h


def arrange(n, w=None, h=None, ctx=None):
    """Size and lay out `n` (and everything inside). w / h force a size coming from the parent."""
    if w is not None:
        n.w = max(0.0, w)
    if h is not None:
        n.h = max(0.0, h)
    t = n.type
    if t == "text":
        fit_text(n, forced_width=w is not None)
        return
    if t == "group":
        for c in n.children:
            arrange(c, ctx=ctx)
        normalize_group(n)
        return
    if t in FRAMELIKE:
        if n.auto:
            _auto_layout(n, ctx or {})
        else:
            for c in n.children:
                if c.type != "connector":
                    arrange(c, ctx=ctx)


def _auto_layout(n, ctx):
    top, right, bottom, left = (list(n.pad) + [0, 0, 0, 0])[:4]
    direction = n.layout
    stacked = direction == "row" and n.stack and ctx.get("narrow", False)
    if stacked:
        direction = "column"
    horiz = direction == "row"
    flow = [c for c in n.children if c.visible and not c.absolute and c.type != "connector"]
    for c in n.children:
        if c.absolute and c.type != "connector":
            arrange(c, ctx=ctx)

    def main_of(c):
        return c.w if horiz else c.h

    def cross_of(c):
        return c.h if horiz else c.w

    def sized(c, main=None, cross=None):
        if horiz:
            arrange(c, main, cross, ctx)
        else:
            arrange(c, cross, main, ctx)

    hug_main = n.hug_w if horiz else n.hug_h
    hug_cross = n.hug_h if horiz else n.hug_w
    pad_main = (left + right) if horiz else (top + bottom)
    pad_cross = (top + bottom) if horiz else (left + right)
    inner_main = (n.w if horiz else n.h) - pad_main
    inner_cross = (n.h if horiz else n.w) - pad_cross
    gaps = n.gap * max(0, len(flow) - 1)

    growers = []
    fixed_total = 0.0
    if ctx.get("narrow") and n.role == "section":  # sections breathe less on phones
        left, right = min(left, 20.0), min(right, 20.0)
        pad_main = (left + right) if horiz else (top + bottom)
        pad_cross = (top + bottom) if horiz else (left + right)
        inner_main = (n.w if horiz else n.h) - pad_main
        inner_cross = (n.h if horiz else n.w) - pad_cross

    def cross_limit(c, v):
        return min(v, c.max_w) if (v is not None and c.max_w and not horiz) else v
    for c in flow:
        stretch = c.stretch or (stacked and c.grow)
        cross = cross_limit(c, inner_cross) if (stretch and not hug_cross) else None
        if c.grow and not stacked and not hug_main:
            growers.append((c, cross))
            continue
        sized(c, None, cross)
        fixed_total += main_of(c)
    if growers:
        each = max(0.0, (inner_main - fixed_total - gaps) / len(growers))
        for c, cross in growers:
            sized(c, each, cross)
    total_main = sum(main_of(c) for c in flow) + gaps
    max_cross = max([cross_of(c) for c in flow] or [0.0])
    if hug_main:
        if horiz:
            n.w = total_main + pad_main
        else:
            n.h = total_main + pad_main
    if hug_cross:
        if horiz:
            n.h = max_cross + pad_cross
        else:
            n.w = max_cross + pad_cross
        inner_cross = max_cross
        for c in flow:  # "fill" children in a hugging parent take the widest sibling's size
            if (c.stretch or (stacked and c.grow)) and abs(cross_of(c) - cross_limit(c, inner_cross)) > 0.01:
                sized(c, None if not c.grow or stacked else main_of(c), cross_limit(c, inner_cross))
    inner_main = (n.w if horiz else n.h) - pad_main
    inner_cross = (n.h if horiz else n.w) - pad_cross
    free = inner_main - total_main
    gap = n.gap
    pos = 0.0
    if n.justify == "between" and len(flow) > 1:
        gap = n.gap + max(0.0, free) / (len(flow) - 1)
    elif n.justify == "center":
        pos = free / 2
    elif n.justify == "end":
        pos = free
    pos += left if horiz else top
    cross_start = top if horiz else left
    for c in flow:
        cf = inner_cross - cross_of(c)
        cpos = cross_start + {"center": cf / 2, "end": cf}.get(n.align, 0.0)
        c.rotation = 0.0
        if horiz:
            c.x, c.y = pos, cpos
        else:
            c.x, c.y = cpos, pos
        pos += main_of(c) + gap


# ====================================================================== connectors
SIDES = ("top", "right", "bottom", "left")


def side_point(r, side):
    return {"top": QPointF(r.center().x(), r.top()), "bottom": QPointF(r.center().x(), r.bottom()),
            "left": QPointF(r.left(), r.center().y()), "right": QPointF(r.right(), r.center().y())}[side]


def _normal(side):
    return {"top": QPointF(0, -1), "bottom": QPointF(0, 1), "left": QPointF(-1, 0), "right": QPointF(1, 0)}[side]


def auto_side(r, toward):
    c = r.center()
    dx, dy = toward.x() - c.x(), toward.y() - c.y()
    if abs(dx) * max(r.height(), 1) >= abs(dy) * max(r.width(), 1):
        return "right" if dx >= 0 else "left"
    return "bottom" if dy >= 0 else "top"


def connector_points(doc, n):
    """World points of a connector's polyline (straight / elbow) or its two ends + controls (curved)."""
    def anchor(end):
        tid = end.get("id")
        target = doc.find(tid) if tid else None
        if target is not None and target.visible:
            return world_bounds(target), end.get("side")
        return None, QPointF(end.get("x", 0.0), end.get("y", 0.0))

    ra, sa = anchor(n.start)
    rb, sb = anchor(n.end)
    ca = ra.center() if ra is not None else sa
    cb = rb.center() if rb is not None else sb
    side_a = side_b = None
    if ra is not None:
        side_a = sa if sa in SIDES else auto_side(ra, cb)
        pa = side_point(ra, side_a)
    else:
        pa = sa
    if rb is not None:
        side_b = sb if sb in SIDES else auto_side(rb, ca)
        pb = side_point(rb, side_b)
    else:
        pb = sb
    if n.route == "straight":
        return [pa, pb], side_a, side_b
    if n.route == "curved":
        d = max(40.0, math.hypot(pb.x() - pa.x(), pb.y() - pa.y()) / 2.5)
        c1 = pa + (_normal(side_a) * d if side_a else (pb - pa) * 0.33)
        c2 = pb + (_normal(side_b) * d if side_b else (pa - pb) * 0.33)
        return [pa, c1, c2, pb], side_a, side_b
    # elbow
    off = 24.0
    a1 = pa + _normal(side_a) * off if side_a else pa
    b1 = pb + _normal(side_b) * off if side_b else pb
    horiz_a = side_a in ("left", "right") if side_a else abs(pb.x() - pa.x()) >= abs(pb.y() - pa.y())
    horiz_b = side_b in ("left", "right") if side_b else horiz_a
    pts = [pa, a1]
    if horiz_a and horiz_b:
        mx = (a1.x() + b1.x()) / 2
        pts += [QPointF(mx, a1.y()), QPointF(mx, b1.y())]
    elif not horiz_a and not horiz_b:
        my = (a1.y() + b1.y()) / 2
        pts += [QPointF(a1.x(), my), QPointF(b1.x(), my)]
    elif horiz_a:
        pts += [QPointF(b1.x(), a1.y())]
    else:
        pts += [QPointF(a1.x(), b1.y())]
    pts += [b1, pb]
    clean = [pts[0]]
    for q in pts[1:]:
        if abs(q.x() - clean[-1].x()) > 0.01 or abs(q.y() - clean[-1].y()) > 0.01:
            clean.append(q)
    return clean, side_a, side_b


def connector_path(doc, n):
    pts, _, _ = connector_points(doc, n)
    p = QPainterPath(pts[0])
    if n.route == "curved" and len(pts) == 4:
        p.cubicTo(pts[1], pts[2], pts[3])
    else:
        for q in pts[1:]:
            p.lineTo(q)
    return p


# ====================================================================== document
SLIDE_W, SLIDE_H = 1920.0, 1080.0
BREAKPOINTS = [(1440, "Компьютер"), (768, "Планшет"), (375, "Телефон")]


class Document:
    def __init__(self, kind="design"):
        self.kind = kind
        self.pages = [Node("page", name="Страница 1")]
        self.images = {}
        self.theme = {}
        self.site = {"name": "Мой сайт", "breakpoint": 1440}
        self._index = None

    # ------------------------------------------------------------------ lookup
    def find(self, nid):
        if not nid:
            return None
        if self._index is None or nid not in self._index or self._index[nid].page() not in self.pages:
            self._index = {n.id: n for p in self.pages for n in p.walk()}
        return self._index.get(nid)

    def invalidate(self):
        self._index = None

    def walk(self):
        for p in self.pages:
            yield from p.walk()

    def components(self):
        return [n for n in self.walk() if n.type == "component"]

    def add_image(self, data: bytes):
        key = hashlib.sha1(data).hexdigest()[:16]
        self.images.setdefault(key, data)
        return key

    def used_images(self):
        used = set()
        for n in self.walk():
            for paint in n.fills:
                if paint.get("type") == "image":
                    used.add(paint.get("ref"))
        return used

    # ------------------------------------------------------------------ state (undo snapshots, files)
    def state(self):
        return {"pages": [p.to_dict() for p in self.pages], "theme": self.theme, "site": self.site}

    def set_state(self, st):
        self.pages = [Node.from_dict(p) for p in st["pages"]] or [Node("page", name="Страница 1")]
        self.theme = copy.deepcopy(st.get("theme", {}))
        self.site = copy.deepcopy(st.get("site", self.site))
        self.invalidate()
        self.relayout()

    def snapshot(self):
        return json.dumps(self.state(), ensure_ascii=False, separators=(",", ":"))

    def to_dict(self):
        d = {"format": "lambda", "version": 1, "kind": self.kind}
        d.update(self.state())
        return d

    @classmethod
    def from_dict(cls, d):
        doc = cls(d.get("kind", "design"))
        doc.set_state(d)
        return doc

    # ------------------------------------------------------------------ layout
    def site_root(self, page):
        return next((c for c in page.children if c.role == "webpage"), None)

    def relayout(self, sync=True):
        if sync:
            self.sync_instances()
        for page in self.pages:
            ctx = {}
            if self.kind == "site":
                root = self.site_root(page)
                if root is not None:
                    bp = float(self.site.get("breakpoint", 1440))
                    ctx = {"narrow": bp < 768}
                    root.x, root.y = 0.0, 0.0
                    arrange(root, w=bp, ctx=ctx)
            for c in page.children:
                if c.type != "connector" and not (self.kind == "site" and c.role == "webpage"):
                    arrange(c, ctx=ctx)
        self.update_connectors()

    def update_connectors(self, page=None):
        for p in ([page] if page is not None else self.pages):
            for n in p.children:
                if n.type == "connector":
                    n._path = connector_path(self, n)
                    b = n._path.boundingRect()
                    n.x, n.y, n.w, n.h = b.x(), b.y(), b.width(), b.height()

    # ------------------------------------------------------------------ components
    def sync_instances(self):
        comps = {n.id: n for n in self.walk() if n.type == "component"}
        if not comps:
            return
        for _ in range(3):  # nested instances settle in a few passes
            for page in self.pages:
                for n in list(page.walk()):
                    if n.type == "instance" and n.master in comps and n.page() is page:
                        sync_instance(n, comps[n.master])
        self.invalidate()


def sync_instance(inst, master):
    for c in inst.children:
        c.parent = None
    inst.children = []
    for c in master.children:
        d = c.to_dict()

        def remap(x):
            orig = x["id"]
            x["id"] = f"{inst.id}:{orig}"
            ov = inst.overrides.get(orig)
            if ov:
                x.update(copy.deepcopy(ov))
            for cc in x.get("children", ()):
                remap(cc)
        remap(d)
        inst.add(Node.from_dict(d))
    for k in LAYOUT_KEYS:
        setattr(inst, k, _copy(getattr(master, k)))
    if not master.auto and master.w and master.h and (abs(inst.w - master.w) > 0.01 or abs(inst.h - master.h) > 0.01):
        sx, sy = inst.w / master.w, inst.h / master.h
        for c in inst.children:
            c.x *= sx
            c.y *= sy
            resize_node(c, c.w * sx, c.h * sy)


def owning_instance(n):
    """The instance whose synced copy `n` is (None for ordinary nodes)."""
    if ":" not in n.id:
        return None
    for a in n.ancestors():
        if a.type == "instance" and n.id.startswith(a.id + ":"):
            return a
    return None


def make_instance(component):
    inst = Node("instance", name=component.name, master=component.id, w=component.w, h=component.h,
                fills=copy.deepcopy(component.fills), strokes=copy.deepcopy(component.strokes),
                stroke_width=component.stroke_width, radius=component.radius, effects=copy.deepcopy(component.effects),
                hug_w=component.hug_w, hug_h=component.hug_h)
    sync_instance(inst, component)
    return inst
