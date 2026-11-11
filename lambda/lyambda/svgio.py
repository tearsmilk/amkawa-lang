"""SVG export (any node → standalone SVG with gradients, images, clipping, shadows and text) and SVG import
(shapes, paths with arcs, transforms, fills / strokes, simple linear gradients, text) into editable vectors."""
import base64
import math
import re
import xml.etree.ElementTree as ET
from html import escape

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QPainterPath, QTransform

from . import text as textlib
from .model import (FRAMELIKE, Node, is_open, local_transform, normalize_path, path_to_points, shape_path,
                    solid, union_rect, world_bounds, parent_transform)


def _num(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def path_d(qp):
    out = []
    i, n = 0, qp.elementCount()
    start = None
    last = None
    while i < n:
        e = qp.elementAt(i)
        if e.isMoveTo():
            if start is not None and last is not None and abs(last[0] - start[0]) < 1e-6 and abs(last[1] - start[1]) < 1e-6:
                out.append("Z")
            out.append(f"M{_num(e.x)} {_num(e.y)}")
            start = last = (e.x, e.y)
            i += 1
        elif e.isLineTo():
            out.append(f"L{_num(e.x)} {_num(e.y)}")
            last = (e.x, e.y)
            i += 1
        else:
            c2, end = qp.elementAt(i + 1), qp.elementAt(i + 2)
            out.append(f"C{_num(e.x)} {_num(e.y)} {_num(c2.x)} {_num(c2.y)} {_num(end.x)} {_num(end.y)}")
            last = (end.x, end.y)
            i += 3
    if start is not None and last is not None and abs(last[0] - start[0]) < 1e-6 and abs(last[1] - start[1]) < 1e-6 \
            and len(out) > 2:
        out.append("Z")
    return " ".join(out)


def _matrix(t: QTransform):
    if t.isIdentity():
        return ""
    if t.m11() == 1 and t.m22() == 1 and t.m12() == 0 and t.m21() == 0:
        return f' transform="translate({_num(t.dx())} {_num(t.dy())})"'
    return (f' transform="matrix({_num(t.m11())} {_num(t.m12())} {_num(t.m21())} {_num(t.m22())} '
            f'{_num(t.dx())} {_num(t.dy())})"')


def _hex(c):
    q = QColor(c or "#000000")
    return q.name() if q.isValid() else "#000000"


class SvgWriter:
    def __init__(self, doc):
        self.doc = doc
        self.defs = []
        self.k = 0

    def uid(self, prefix):
        self.k += 1
        return f"{prefix}{self.k}"

    # ------------------------------------------------------------------ paints
    def paint_attr(self, paint, rect, attr):
        t = paint.get("type", "solid")
        op = paint.get("opacity", 1.0)
        if t == "solid":
            q = QColor(paint.get("color", "#000000"))
            a = op * (q.alphaF() if q.isValid() else 1)
            s = f'{attr}="{_hex(paint.get("color"))}"'
            if a < 1:
                s += f' {attr}-opacity="{_num(a)}"'
            return s
        if t in ("linear", "radial"):
            gid = self.uid("g")
            stops = "".join(f'<stop offset="{_num(float(pos))}" stop-color="{_hex(col)}" '
                            f'stop-opacity="{_num(op * QColor(col).alphaF())}"/>'
                            for pos, col in paint.get("stops") or [[0, "#FFFFFF"], [1, "#000000"]])
            if t == "linear":
                a = math.radians(paint.get("angle", 90.0))
                c = rect.center()
                half = (abs(rect.width() * math.cos(a)) + abs(rect.height() * math.sin(a))) / 2
                vx, vy = math.cos(a) * half, math.sin(a) * half
                self.defs.append(f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="{_num(c.x() - vx)}" '
                                 f'y1="{_num(c.y() - vy)}" x2="{_num(c.x() + vx)}" y2="{_num(c.y() + vy)}">{stops}'
                                 f'</linearGradient>')
            else:
                c = rect.center()
                r = max(1.0, max(rect.width(), rect.height()) / 2)
                sx = rect.width() / (2 * r) if r else 1
                sy = rect.height() / (2 * r) if r else 1
                tr = (f' gradientTransform="translate({_num(c.x())} {_num(c.y())}) scale({_num(sx)} {_num(sy)}) '
                      f'translate({_num(-c.x())} {_num(-c.y())})"')
                self.defs.append(f'<radialGradient id="{gid}" gradientUnits="userSpaceOnUse" cx="{_num(c.x())}" '
                                 f'cy="{_num(c.y())}" r="{_num(r)}"{tr}>{stops}</radialGradient>')
            return f'{attr}="url(#{gid})"'
        return None

    def image_el(self, paint, d, rect):
        data = self.doc.images.get(paint.get("ref"))
        if not data:
            return ""
        mime = "image/png"
        if data[:3] == b"\xff\xd8\xff":
            mime = "image/jpeg"
        elif data[:4] == b"GIF8":
            mime = "image/gif"
        elif data[8:12] == b"WEBP":
            mime = "image/webp"
        cid = self.uid("c")
        self.defs.append(f'<clipPath id="{cid}"><path d="{d}"/></clipPath>')
        par = {"fill": "xMidYMid slice", "fit": "xMidYMid meet", "stretch": "none"}.get(paint.get("mode", "fill"),
                                                                                     "xMidYMid slice")
        href = f"data:{mime};base64,{base64.b64encode(data).decode()}"
        op = paint.get("opacity", 1.0)
        return (f'<image clip-path="url(#{cid})" x="0" y="0" width="{_num(rect.width())}" '
                f'height="{_num(rect.height())}" preserveAspectRatio="{par}"'
                f'{"" if op >= 1 else f" opacity={chr(34)}{_num(op)}{chr(34)}"} href="{href}"/>')

    # ------------------------------------------------------------------ nodes
    def node(self, n):
        if not n.visible:
            return ""
        t = n.type
        attrs = _matrix(local_transform(n))
        if n.opacity < 1:
            attrs += f' opacity="{_num(n.opacity)}"'
        if n.blend != "normal":
            attrs += f' style="mix-blend-mode:{n.blend}"'
        inner = []
        if t == "group":
            inner.append(self.children(n))
            return f'<g{attrs}>{"".join(inner)}</g>'
        path = shape_path(n)
        d = path_d(path)
        rect = QRectF(0, 0, n.w, n.h) if t != "connector" else path.boundingRect()
        filt = ""
        shadows = [e for e in n.effects if e.get("type") == "shadow" and e.get("visible", True)]
        if shadows:
            fid = self.uid("f")
            parts = "".join(
                f'<feDropShadow dx="{_num(e.get("x", 0))}" dy="{_num(e.get("y", 4))}" '
                f'stdDeviation="{_num(e.get("blur", 8) / 2)}" flood-color="{_hex(e.get("color", "#000000"))}" '
                f'flood-opacity="{_num(e.get("opacity", 0.25))}"/>' for e in shadows)
            self.defs.append(f'<filter id="{fid}" x="-50%" y="-50%" width="200%" height="200%">{parts}</filter>')
            filt = f' filter="url(#{fid})"'
        if not is_open(n):
            for paint in n.fills:
                if not paint.get("visible", True) or t == "text":
                    continue
                if paint.get("type") == "image":
                    inner.append(self.image_el(paint, d, rect))
                    continue
                a = self.paint_attr(paint, rect, "fill")
                if a:
                    rule = ' fill-rule="evenodd"' if n.fill_rule == "evenodd" else ""
                    inner.append(f'<path d="{d}" {a}{rule}{filt}/>')
                    filt = ""
        if t in FRAMELIKE and n.children:
            kids = self.children(n)
            if n.clip:
                cid = self.uid("c")
                self.defs.append(f'<clipPath id="{cid}"><path d="{d}"/></clipPath>')
                inner.append(f'<g clip-path="url(#{cid})">{kids}</g>')
            else:
                inner.append(kids)
        if t == "text":
            inner.append(self.text_el(n))
        elif t in ("sticky", "shape") and n.text:
            block, pad, size = textlib.box_block(n)
            avail_h = n.h - 2 * pad
            y = pad + ((avail_h - block.h) / 2 if n.valign == "center" else 0)
            inner.append(self.lines_el(n, block, pad, y, size, [solid(n.text_color)]))
        elif t == "stamp":
            inner.append(f'<text x="{_num(n.w / 2)}" y="{_num(n.h * 0.7)}" font-size="{_num(n.h * 0.55)}" '
                         f'text-anchor="middle">{escape(n.glyph)}</text>')
        if n.stroke_width > 0:
            for paint in n.strokes:
                if not paint.get("visible", True):
                    continue
                a = self.paint_attr(paint, rect, "stroke")
                if not a:
                    continue
                align = "center" if is_open(n) else n.stroke_align
                w = n.stroke_width * (2 if align != "center" else 1)
                extra = ""
                if n.dash > 0:
                    extra += f' stroke-dasharray="{_num(n.dash)} {_num(n.dash)}"'
                if is_open(n):
                    extra += ' stroke-linecap="round" stroke-linejoin="round"'
                el = f'<path d="{d}" fill="none" {a} stroke-width="{_num(w)}"{extra}{filt}/>'
                filt = ""
                if align == "inside":
                    cid = self.uid("c")
                    self.defs.append(f'<clipPath id="{cid}"><path d="{d}"/></clipPath>')
                    el = f'<g clip-path="url(#{cid})">{el}</g>'
                inner.append(el)
                if is_open(n):
                    inner.append(self.arrows(n, path, paint))
        if filt and inner:  # a shadow with nothing to attach it to (e.g. image fill only)
            inner.insert(0, f'<path d="{d}" fill="#000" fill-opacity="0.001"{filt}/>')
        return f'<g{attrs}>{"".join(inner)}</g>'

    def children(self, n):
        out = []
        masked = 0
        for c in n.children:
            if c.mask and c.visible:
                cid = self.uid("m")
                self.defs.append(f'<clipPath id="{cid}"><path d="{path_d(local_transform(c).map(shape_path(c)))}"/>'
                                 f'</clipPath>')
                out.append(f'<g clip-path="url(#{cid})">')
                masked += 1
                continue
            out.append(self.node(c))
        out.append("</g>" * masked)
        return "".join(out)

    def text_attrs(self, n, size):
        a = (f' font-family="{escape(textlib.css_family(n.font))}" font-size="{_num(size)}"'
             f' font-weight="{int(n.weight)}"')
        if n.italic:
            a += ' font-style="italic"'
        if n.letter:
            a += f' letter-spacing="{_num(n.letter)}"'
        if n.deco:
            a += f' text-decoration="{"underline" if "underline" in n.deco else "line-through"}"'
        return a

    def lines_el(self, n, block, ox, oy, size, paints):
        fill = ""
        for paint in paints:
            if paint.get("visible", True):
                fill = self.paint_attr(paint, QRectF(0, 0, n.w, n.h), "fill") or ""
                break
        spans = "".join(f'<tspan x="{_num(ox + x)}" y="{_num(oy + base)}">{escape(s)}</tspan>'
                        for s, x, base, _ in block.lines if s)
        return f'<text{self.text_attrs(n, size)} {fill} xml:space="preserve">{spans}</text>'

    def text_el(self, n):
        block = textlib.node_block(n, None if n.sizing == "auto_w" else n.w)
        oy = 0.0
        if n.sizing == "fixed" and n.valign != "top":
            oy = (n.h - block.h) / (2 if n.valign == "center" else 1)
        return self.lines_el(n, block, 0, oy, n.size, n.fills)

    def arrows(self, n, path, paint):
        out = []
        size = max(8.0, n.stroke_width * 4)
        col = _hex(paint.get("color"))
        for which, style in (("end", n.arrow_end), ("start", n.arrow_start)):
            if style in ("none", "", None) or path.elementCount() < 2:
                continue
            pct = 1.0 if which == "end" else 0.0
            tip = path.pointAtPercent(pct)
            back = path.pointAtPercent(0.99 if which == "end" else 0.01)
            if n.type == "connector":
                e = path.elementAt(path.elementCount() - 2 if which == "end" else 1)
                back = QPointF(e.x, e.y)
            ang = math.atan2(tip.y() - back.y(), tip.x() - back.x())
            l = (tip.x() + math.cos(ang + 2.6) * size, tip.y() + math.sin(ang + 2.6) * size)
            r = (tip.x() + math.cos(ang - 2.6) * size, tip.y() + math.sin(ang - 2.6) * size)
            if style == "line":
                out.append(f'<polyline points="{_num(l[0])},{_num(l[1])} {_num(tip.x())},{_num(tip.y())} '
                           f'{_num(r[0])},{_num(r[1])}" fill="none" stroke="{col}" '
                           f'stroke-width="{_num(n.stroke_width)}" stroke-linecap="round"/>')
            elif style == "circle":
                out.append(f'<circle cx="{_num(tip.x())}" cy="{_num(tip.y())}" r="{_num(size / 2.2)}" fill="{col}"/>')
            else:
                out.append(f'<polygon points="{_num(tip.x())},{_num(tip.y())} {_num(l[0])},{_num(l[1])} '
                           f'{_num(r[0])},{_num(r[1])}" fill="{col}"/>')
        return "".join(out)


def export_svg(doc, nodes, bounds=None):
    b = bounds or union_rect(world_bounds(n) for n in nodes)
    w = SvgWriter(doc)
    body = []
    for n in nodes:
        pt = parent_transform(n)
        body.append(f'<g{_matrix(pt)}>{w.node(n)}</g>' if not pt.isIdentity() else w.node(n))
    defs = f"<defs>{''.join(w.defs)}</defs>" if w.defs else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{_num(b.width())}" height="{_num(b.height())}" '
            f'viewBox="{_num(b.x())} {_num(b.y())} {_num(b.width())} {_num(b.height())}" fill="none">'
            f'{defs}{"".join(body)}</svg>')


def node_svg(doc, n):
    """Inline SVG for one node drawn at its own origin (used by the site exporter for vectors)."""
    w = SvgWriter(doc)
    saved = (n.x, n.y, n.rotation)
    n.x = n.y = 0.0
    n.rotation = 0.0
    try:
        body = w.node(n)
    finally:
        n.x, n.y, n.rotation = saved
    defs = f"<defs>{''.join(w.defs)}</defs>" if w.defs else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{_num(n.w)}" height="{_num(n.h)}" '
            f'viewBox="0 0 {_num(n.w)} {_num(n.h)}" fill="none" style="overflow:visible">{defs}{body}</svg>')


# ====================================================================== import
_TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def _arc(p, x0, y0, rx, ry, phi, large, sweep, x, y):
    """SVG elliptical arc → cubic beziers (endpoint → centre parameterisation, spec F.6.5)."""
    if rx == 0 or ry == 0:
        p.lineTo(x, y)
        return
    rx, ry = abs(rx), abs(ry)
    cp, sp = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (x0 - x) / 2, (y0 - y) / 2
    x1 = cp * dx + sp * dy
    y1 = -sp * dx + cp * dy
    lam = (x1 * x1) / (rx * rx) + (y1 * y1) / (ry * ry)
    if lam > 1:
        rx *= math.sqrt(lam)
        ry *= math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    co = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large == sweep:
        co = -co
    cx1 = co * rx * y1 / ry
    cy1 = -co * ry * x1 / rx
    cx = cp * cx1 - sp * cy1 + (x0 + x) / 2
    cy = sp * cx1 + cp * cy1 + (y0 + y) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a
    t1 = ang(1, 0, (x1 - cx1) / rx, (y1 - cy1) / ry)
    dt = ang((x1 - cx1) / rx, (y1 - cy1) / ry, (-x1 - cx1) / rx, (-y1 - cy1) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    segs = max(1, int(math.ceil(abs(dt) / (math.pi / 2))))
    step = dt / segs
    k = 4 / 3 * math.tan(step / 4)

    def pt(t):
        return (cx + rx * math.cos(t) * cp - ry * math.sin(t) * sp, cy + rx * math.cos(t) * sp + ry * math.sin(t) * cp)

    def deriv(t):
        return (-rx * math.sin(t) * cp - ry * math.cos(t) * sp, -rx * math.sin(t) * sp + ry * math.cos(t) * cp)
    t = t1
    for _ in range(segs):
        a, b = pt(t), pt(t + step)
        da, db = deriv(t), deriv(t + step)
        p.cubicTo(a[0] + k * da[0], a[1] + k * da[1], b[0] - k * db[0], b[1] - k * db[1], b[0], b[1])
        t += step


def parse_path_d(d):
    toks = _TOKEN.findall(d or "")
    p = QPainterPath()
    i = 0
    cmd = None
    cx = cy = sx = sy = 0.0
    last_c = None  # previous control point for S / T
    last_q = None

    def num():
        nonlocal i
        v = float(toks[i])
        i += 1
        return v
    while i < len(toks):
        if toks[i].isalpha():
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                p.closeSubpath()
                cx, cy = sx, sy
                last_c = last_q = None
                continue
        if cmd is None:
            break
        rel = cmd.islower()
        c = cmd.upper()
        ox, oy = (cx, cy) if rel else (0.0, 0.0)
        try:
            if c == "M":
                cx, cy = ox + num(), oy + num()
                p.moveTo(cx, cy)
                sx, sy = cx, cy
                cmd = "l" if rel else "L"
                last_c = last_q = None
            elif c == "L":
                cx, cy = ox + num(), oy + num()
                p.lineTo(cx, cy)
                last_c = last_q = None
            elif c == "H":
                cx = (cx if rel else 0.0) + num()
                p.lineTo(cx, cy)
                last_c = last_q = None
            elif c == "V":
                cy = (cy if rel else 0.0) + num()
                p.lineTo(cx, cy)
                last_c = last_q = None
            elif c == "C":
                x1, y1, x2, y2, x, y = ox + num(), oy + num(), ox + num(), oy + num(), ox + num(), oy + num()
                p.cubicTo(x1, y1, x2, y2, x, y)
                last_c, last_q = (x2, y2), None
                cx, cy = x, y
            elif c == "S":
                x1, y1 = (2 * cx - last_c[0], 2 * cy - last_c[1]) if last_c else (cx, cy)
                x2, y2, x, y = ox + num(), oy + num(), ox + num(), oy + num()
                p.cubicTo(x1, y1, x2, y2, x, y)
                last_c, last_q = (x2, y2), None
                cx, cy = x, y
            elif c == "Q":
                qx, qy, x, y = ox + num(), oy + num(), ox + num(), oy + num()
                p.quadTo(qx, qy, x, y)
                last_q, last_c = (qx, qy), None
                cx, cy = x, y
            elif c == "T":
                qx, qy = (2 * cx - last_q[0], 2 * cy - last_q[1]) if last_q else (cx, cy)
                x, y = ox + num(), oy + num()
                p.quadTo(qx, qy, x, y)
                last_q, last_c = (qx, qy), None
                cx, cy = x, y
            elif c == "A":
                rx, ry, phi, large, sweep = num(), num(), num(), num(), num()
                x, y = ox + num(), oy + num()
                _arc(p, cx, cy, rx, ry, phi, int(large), int(sweep), x, y)
                cx, cy = x, y
                last_c = last_q = None
            else:
                i += 1
        except (IndexError, ValueError):
            break
    return p


def parse_transform(s):
    t = QTransform()
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", s or ""):
        v = [float(a) for a in re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?", args)]
        m = QTransform()
        if name == "matrix" and len(v) == 6:
            m = QTransform(v[0], v[1], v[2], v[3], v[4], v[5])
        elif name == "translate" and v:
            m.translate(v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale" and v:
            m.scale(v[0], v[1] if len(v) > 1 else v[0])
        elif name == "rotate" and v:
            if len(v) == 3:
                m.translate(v[1], v[2])
                m.rotate(v[0])
                m.translate(-v[1], -v[2])
            else:
                m.rotate(v[0])
        elif name == "skewX" and v:
            m.shear(math.tan(math.radians(v[0])), 0)
        elif name == "skewY" and v:
            m.shear(0, math.tan(math.radians(v[0])))
        t = m * t  # later transforms in the list apply first
    return t


def _color(v):
    if not v or v in ("none", "transparent"):
        return None
    v = v.strip()
    m = re.match(r"rgba?\(([^)]*)\)", v)
    if m:
        parts = [x.strip() for x in m.group(1).split(",")]
        try:
            vals = [float(x[:-1]) * 2.55 if x.endswith("%") else float(x) for x in parts[:3]]
            q = QColor(int(vals[0]), int(vals[1]), int(vals[2]))
            if len(parts) > 3:
                q.setAlphaF(float(parts[3]))
            return q
        except ValueError:
            return QColor("#000000")
    if v == "currentColor":
        return QColor("#000000")
    q = QColor(v)
    return q if q.isValid() else QColor("#000000")


def _len(v, default=0.0):
    if v is None:
        return default
    m = re.match(r"\s*([-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?)", str(v))
    return float(m.group(1)) if m else default


def import_svg(data, name="SVG"):
    """Parse SVG bytes into a group of vector nodes (world coordinates = SVG user units)."""
    root = ET.fromstring(data)
    grads = {}
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag in ("linearGradient", "radialGradient") and el.get("id"):
            stops = []
            for s in el:
                if s.tag.split("}")[-1] == "stop":
                    st = dict(x.split(":", 1) for x in (s.get("style") or "").split(";") if ":" in x)
                    col = _color(st.get("stop-color", s.get("stop-color", "#000000"))) or QColor("#000000")
                    off = s.get("offset", "0")
                    pos = float(off[:-1]) / 100 if off.endswith("%") else _len(off)
                    stops.append([pos, col.name()])
            href = el.get("{http://www.w3.org/1999/xlink}href") or el.get("href")
            if not stops and href and href[1:] in grads:
                stops = grads[href[1:]]["stops"]
            ang = 90.0
            if tag == "linearGradient":
                x1, y1 = _len(el.get("x1"), 0), _len(el.get("y1"), 0)
                x2, y2 = _len(el.get("x2"), 1), _len(el.get("y2"), 0)
                ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
            grads[el.get("id")] = {"type": "linear" if tag == "linearGradient" else "radial", "stops": stops,
                                   "angle": ang, "opacity": 1.0}
    base = QTransform()
    vb = root.get("viewBox")
    if vb:
        try:
            vx, vy, vw, vh = [float(x) for x in re.split(r"[\s,]+", vb.strip())]
            w = _len(root.get("width"), vw)
            h = _len(root.get("height"), vh)
            if vw and vh:
                base.scale(w / vw, h / vh)
                base.translate(-vx, -vy)
        except ValueError:
            pass
    group = Node("group", name=name)

    def style_of(el, inherited):
        st = dict(inherited)
        for k in ("fill", "stroke", "stroke-width", "opacity", "fill-opacity", "stroke-opacity", "fill-rule",
                  "font-size", "font-family", "font-weight", "display", "visibility"):
            if el.get(k) is not None:
                st[k] = el.get(k)
        for part in (el.get("style") or "").split(";"):
            if ":" in part:
                k, v = part.split(":", 1)
                st[k.strip()] = v.strip()
        st["opacity"] = str(_len(inherited.get("opacity", "1"), 1) * _len(el.get("opacity", "1"), 1)) \
            if el.get("opacity") is not None else inherited.get("opacity", "1")
        return st

    def paints(st):
        fills, strokes = [], []
        f = st.get("fill", "#000000")
        m = re.match(r"url\(#([^)]+)\)", f or "")
        if m and m.group(1) in grads:
            fills.append(dict(grads[m.group(1)]))
        else:
            q = _color(f)
            if q is not None:
                fills.append(solid(q.name(), q.alphaF() * _len(st.get("fill-opacity", "1"), 1)))
        s = st.get("stroke")
        m = re.match(r"url\(#([^)]+)\)", s or "")
        if m and m.group(1) in grads:
            strokes.append(dict(grads[m.group(1)]))
        else:
            q = _color(s)
            if q is not None:
                strokes.append(solid(q.name(), q.alphaF() * _len(st.get("stroke-opacity", "1"), 1)))
        return fills, strokes

    def add_shape(qp, t, st, label):
        if qp.isEmpty():
            return
        fills, strokes = paints(st)
        if not fills and not strokes:
            return
        world = t.map(qp)
        n = Node("path", name=label, paths=path_to_points(world), fills=fills, strokes=strokes,
                 stroke_width=_len(st.get("stroke-width", "1"), 1) * math.sqrt(abs(t.determinant()) or 1),
                 stroke_align="center", opacity=_len(st.get("opacity", "1"), 1),
                 fill_rule="evenodd" if st.get("fill-rule") == "evenodd" else "nonzero")
        if not n.paths:
            return
        normalize_path(n)
        group.add(n)

    def walk(el, t, inherited):
        tag = el.tag.split("}")[-1]
        if tag in ("defs", "clipPath", "mask", "linearGradient", "radialGradient", "style", "title", "desc",
                   "metadata", "symbol", "pattern", "filter", "marker"):
            return
        st = style_of(el, inherited)
        if st.get("display") == "none" or st.get("visibility") == "hidden":
            return
        t = parse_transform(el.get("transform")) * t
        qp = QPainterPath()
        if tag in ("svg", "g", "a", "switch"):
            for c in el:
                walk(c, t, st)
            return
        if tag == "rect":
            x, y = _len(el.get("x")), _len(el.get("y"))
            w, h = _len(el.get("width")), _len(el.get("height"))
            rx = _len(el.get("rx"), _len(el.get("ry"), 0))
            ry = _len(el.get("ry"), rx)
            if rx or ry:
                qp.addRoundedRect(QRectF(x, y, w, h), rx, ry)
            else:
                qp.addRect(QRectF(x, y, w, h))
        elif tag == "circle":
            r = _len(el.get("r"))
            qp.addEllipse(QPointF(_len(el.get("cx")), _len(el.get("cy"))), r, r)
        elif tag == "ellipse":
            qp.addEllipse(QPointF(_len(el.get("cx")), _len(el.get("cy"))), _len(el.get("rx")), _len(el.get("ry")))
        elif tag == "line":
            qp.moveTo(_len(el.get("x1")), _len(el.get("y1")))
            qp.lineTo(_len(el.get("x2")), _len(el.get("y2")))
            st.setdefault("fill", "none")
            st["fill"] = "none"
        elif tag in ("polyline", "polygon"):
            v = [float(a) for a in re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?", el.get("points", ""))]
            if len(v) >= 4:
                qp.moveTo(v[0], v[1])
                for k in range(2, len(v) - 1, 2):
                    qp.lineTo(v[k], v[k + 1])
                if tag == "polygon":
                    qp.closeSubpath()
        elif tag == "path":
            qp = parse_path_d(el.get("d"))
        elif tag == "text":
            content = "".join(el.itertext()).strip()
            if content:
                fills, _ = paints(st)
                pos = t.map(QPointF(_len(el.get("x")), _len(el.get("y"))))
                size = _len(st.get("font-size", "16"), 16) * math.sqrt(abs(t.determinant()) or 1)
                fam = (st.get("font-family") or "").split(",")[0].strip(" '\"")
                weight = st.get("font-weight", "400")
                weight = 700 if weight == "bold" else int(_len(weight, 400)) or 400
                n = Node("text", name=content[:30], text=content, size=size, font=fam, weight=weight,
                         fills=fills or [solid("#000000")])
                from .model import fit_text
                fit_text(n)
                n.x, n.y = pos.x(), pos.y() - size * 0.8
                group.add(n)
            return
        else:
            return
        add_shape(qp, t, st, {"rect": "Прямоугольник", "circle": "Эллипс", "ellipse": "Эллипс", "line": "Линия",
                              "path": "Вектор", "polygon": "Многоугольник", "polyline": "Линия"}.get(tag, tag))

    walk(root, base, {"fill": "#000000", "opacity": "1"})
    from .model import normalize_group
    normalize_group(group)
    return group
