"""Line icons drawn with QPainter on a 24-unit grid (ink strokes + terracotta details), cached per colour."""
import math
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap


@lru_cache(maxsize=512)
def pixmap(name, ink="#141413", accent="#D97757", size=40):
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 24.0
    P = lambda x, y: QPointF(x * s, y * s)  # noqa: E731
    pen = QPen(QColor(ink), 1.6 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    acc = QPen(QColor(accent), 1.6 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    def poly(*pts, close=False, fill=None, pen_=None):
        path = QPainterPath(P(*pts[0]))
        for q in pts[1:]:
            path.lineTo(P(*q))
        if close:
            path.closeSubpath()
        if fill:
            p.fillPath(path, QColor(fill))
        if pen_ is not None:
            p.setPen(pen_)
        p.drawPath(path)
        p.setPen(pen)

    def rect(x, y, w, h, r=0, fill=None, pen_=None):
        if fill:
            p.setBrush(QColor(fill))
        if pen_ is not None:
            p.setPen(pen_)
        p.drawRoundedRect(QRectF(P(x, y), P(x + w, y + h)), r * s, r * s)
        p.setBrush(Qt.NoBrush)
        p.setPen(pen)

    def circle(x, y, r, fill=None, pen_=None):
        if fill:
            p.setBrush(QColor(fill))
        if pen_ is not None:
            p.setPen(pen_)
        p.drawEllipse(P(x, y), r * s, r * s)
        p.setBrush(Qt.NoBrush)
        p.setPen(pen)

    def text(t, x, y, w, h, px, bold=False, italic=False, color=None, family=None):
        f = QFont(family or "Georgia")
        f.setPixelSize(max(1, int(px * s)))
        f.setBold(bold)
        f.setItalic(italic)
        p.setFont(f)
        p.setPen(QColor(color or ink))
        p.drawText(QRectF(P(x, y), P(x + w, y + h)), Qt.AlignCenter, t)
        p.setPen(pen)

    if name == "select":
        poly((5, 3), (5, 19), (9.5, 14.5), (12.5, 21), (15, 20), (12, 13.5), (18.5, 13.5), close=True, fill=ink)
    elif name == "hand":
        path = QPainterPath(P(8, 20))
        path.cubicTo(P(5, 17), P(4, 14), P(4.5, 12))
        path.cubicTo(P(5, 10.5), P(6.5, 10.5), P(7.5, 12))
        path.lineTo(P(8, 13))
        path.lineTo(P(8, 5))
        path.cubicTo(P(8, 3.5), P(10.5, 3.5), P(10.5, 5))
        path.lineTo(P(10.5, 11))
        path.lineTo(P(10.5, 4))
        path.cubicTo(P(10.5, 2.5), P(13, 2.5), P(13, 4))
        path.lineTo(P(13, 11))
        path.lineTo(P(13, 5))
        path.cubicTo(P(13, 3.5), P(15.5, 3.5), P(15.5, 5))
        path.lineTo(P(15.5, 11.5))
        path.lineTo(P(15.5, 7.5))
        path.cubicTo(P(15.5, 6), P(18, 6), P(18, 7.5))
        path.lineTo(P(18, 14))
        path.cubicTo(P(18, 18), P(16, 20), P(13, 20))
        path.closeSubpath()
        p.drawPath(path)
    elif name == "frame":
        for a in ((7, 3, 7, 21), (17, 3, 17, 21), (3, 7, 21, 7), (3, 17, 21, 17)):
            poly(a[:2], a[2:])
        poly((7, 7), (17, 7), (17, 17), (7, 17), close=True, pen_=acc)
    elif name == "section":
        rect(3, 6, 18, 14, 2.5)
        rect(4.5, 3, 8, 4, 1.5, fill=accent, pen_=acc)
    elif name == "rect":
        rect(4, 5, 16, 14, 1.5)
    elif name == "ellipse":
        circle(12, 12, 8)
    elif name == "line":
        poly((5, 19), (19, 5))
    elif name == "arrow":
        poly((5, 19), (19, 5))
        poly((11, 5), (19, 5), (19, 13))
    elif name == "polygon":
        poly((12, 4), (20.5, 19), (3.5, 19), close=True)
    elif name == "star":
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            r = 8.5 if i % 2 == 0 else 3.8
            pts.append((12 + math.cos(a) * r, 12.8 + math.sin(a) * r))
        poly(*pts, close=True)
    elif name == "image":
        rect(3, 5, 18, 14, 2)
        poly((5, 17), (10, 11), (13.5, 15), (15.5, 13), (19, 17), pen_=acc)
        circle(15.5, 9, 1.6, fill=accent, pen_=acc)
    elif name == "pen":
        poly((12, 3), (18, 13), (15, 20), (9, 20), (6, 13), close=True)
        poly((12, 3), (12, 12))
        circle(12, 13, 1.4, fill=accent, pen_=acc)
    elif name == "pencil":
        poly((15, 4), (20, 9), (9, 20), (4, 20), (4, 15), close=True)
        poly((13, 6), (18, 11), pen_=acc)
    elif name == "text":
        text("T", 2, 2, 20, 20, 19, family="Georgia")
    elif name == "sticky":
        poly((4, 4), (20, 4), (20, 15), (15, 20), (4, 20), close=True, fill="#FFE29A")
        poly((20, 15), (15, 15), (15, 20))
    elif name == "shape":
        rect(3, 9, 10, 10, 1.5)
        circle(15.5, 8.5, 5.5, fill=accent, pen_=acc)
    elif name == "connector":
        circle(5, 18, 2)
        path = QPainterPath(P(7, 16.5))
        path.cubicTo(P(12, 13), P(10, 7), P(17, 6))
        p.setPen(acc)
        p.drawPath(path)
        p.setPen(pen)
        poly((14.5, 3.5), (18.5, 6), (15, 9))
    elif name == "marker":
        poly((14, 3), (21, 10), (12, 19), (5, 12), close=True)
        poly((5, 12), (3, 21), (12, 19), fill=accent, pen_=acc)
    elif name == "highlighter":
        poly((14, 3), (21, 10), (13, 18), (6, 11), close=True)
        poly((6, 11), (4, 17), (7, 20), (13, 18))
        poly((3, 21), (12, 21), pen_=QPen(QColor("#F2D15B"), 3 * s, Qt.SolidLine, Qt.RoundCap))
    elif name == "stamp":
        circle(12, 12, 8.5)
        text("☺", 3, 3, 18, 18, 13, family="Helvetica", color=accent)
    elif name == "comment":
        path = QPainterPath(P(5, 19))
        path.lineTo(P(5, 12))
        path.cubicTo(P(5, 7), P(8, 4), P(12, 4))
        path.cubicTo(P(16.5, 4), P(19.5, 7), P(19.5, 11.5))
        path.cubicTo(P(19.5, 16), P(16.5, 19), P(12, 19))
        path.closeSubpath()
        p.drawPath(path)
    elif name == "play":
        poly((7, 4.5), (19, 12), (7, 19.5), close=True, fill=ink)
    elif name == "present":
        rect(3, 4, 18, 12, 1.5)
        poly((12, 16), (12, 20))
        poly((8, 20), (16, 20))
        poly((10, 7.5), (14.5, 10), (10, 12.5), close=True, fill=accent, pen_=acc)
    elif name == "plus":
        poly((12, 5), (12, 19))
        poly((5, 12), (19, 12))
    elif name == "minus":
        poly((5, 12), (19, 12))
    elif name == "eye":
        path = QPainterPath(P(2.5, 12))
        path.cubicTo(P(6, 5.5), P(18, 5.5), P(21.5, 12))
        path.cubicTo(P(18, 18.5), P(6, 18.5), P(2.5, 12))
        p.drawPath(path)
        circle(12, 12, 2.8)
    elif name == "eye_off":
        path = QPainterPath(P(2.5, 12))
        path.cubicTo(P(6, 5.5), P(18, 5.5), P(21.5, 12))
        path.cubicTo(P(18, 18.5), P(6, 18.5), P(2.5, 12))
        p.drawPath(path)
        poly((4, 20), (20, 4), pen_=acc)
    elif name == "lock":
        rect(5, 10.5, 14, 10, 2)
        path = QPainterPath(P(8, 10.5))
        path.lineTo(P(8, 7.5))
        path.cubicTo(P(8, 3.5), P(16, 3.5), P(16, 7.5))
        path.lineTo(P(16, 10.5))
        p.drawPath(path)
    elif name == "unlock":
        rect(5, 10.5, 14, 10, 2)
        path = QPainterPath(P(8, 10.5))
        path.lineTo(P(8, 7.5))
        path.cubicTo(P(8, 3.5), P(16, 3.5), P(16, 7))
        p.drawPath(path)
    elif name == "component":
        for cx, cy in ((12, 6), (18, 12), (12, 18), (6, 12)):
            poly((cx, cy - 3.2), (cx + 3.2, cy), (cx, cy + 3.2), (cx - 3.2, cy), close=True, fill=accent, pen_=acc)
    elif name == "instance":
        poly((12, 3.5), (20.5, 12), (12, 20.5), (3.5, 12), close=True, pen_=acc)
    elif name == "group":
        for x, y in ((4, 4), (14, 4), (4, 14), (14, 14)):
            rect(x, y, 6, 6, 1)
    elif name == "page":
        poly((6, 3), (14, 3), (19, 8), (19, 21), (6, 21), close=True)
        poly((14, 3), (14, 8), (19, 8))
    elif name == "slide":
        rect(3, 6, 18, 12, 2)
        poly((7, 10), (15, 10), pen_=acc)
        poly((7, 14), (12, 14))
    elif name == "globe":
        circle(12, 12, 8.5)
        p.drawEllipse(QRectF(P(8, 3.5), P(16, 20.5)))
        poly((3.5, 12), (20.5, 12))
    elif name == "design":
        poly((12, 3), (19, 14), (12, 21), (5, 14), close=True)
        circle(12, 13.5, 2.2, fill=accent, pen_=acc)
        poly((12, 3), (12, 11.3))
    elif name == "board":
        poly((4, 4), (20, 4), (20, 15), (15, 20), (4, 20), close=True, fill="#FFE29A")
        poly((20, 15), (15, 15), (15, 20))
        poly((7.5, 9), (16, 9), pen_=acc)
        poly((7.5, 12.5), (13, 12.5))
    elif name == "slides":
        rect(2.5, 5, 19, 13, 2)
        rect(6, 8.5, 7, 6, 1, fill=accent, pen_=acc)
        poly((15, 9.5), (18.5, 9.5))
        poly((15, 13), (18.5, 13))
    elif name == "site":
        rect(2.5, 4, 19, 16, 2)
        poly((2.5, 8.5), (21.5, 8.5))
        for x in (5.2, 7.6, 10):
            circle(x, 6.3, 0.6, fill=accent, pen_=acc)
        poly((6, 13), (18, 13), pen_=acc)
        poly((6, 16.5), (13, 16.5))
    elif name == "folder":
        poly((3, 6), (9, 6), (11, 8), (21, 8), (21, 19), (3, 19), close=True)
    elif name == "clock":
        circle(12, 12, 8.5)
        poly((12, 7), (12, 12), (15.5, 14))
    elif name == "trash":
        poly((4, 7), (20, 7))
        poly((9, 7), (9, 4.5), (15, 4.5), (15, 7))
        poly((6, 7), (7, 20), (17, 20), (18, 7))
    elif name == "more":
        for x in (6, 12, 18):
            circle(x, 12, 1.4, fill=ink)
    elif name == "chevron_down":
        poly((7, 10), (12, 15), (17, 10))
    elif name == "close":
        poly((6, 6), (18, 18))
        poly((18, 6), (6, 18))
    elif name == "export":
        poly((12, 15), (12, 3))
        poly((7.5, 7.5), (12, 3), (16.5, 7.5))
        poly((5, 13), (5, 20), (19, 20), (19, 13))
    elif name == "link":
        p.drawRoundedRect(QRectF(P(3, 9), P(13, 15)), 3 * s, 3 * s)
        p.setPen(acc)
        p.drawRoundedRect(QRectF(P(11, 9), P(21, 15)), 3 * s, 3 * s)
        p.setPen(pen)
    elif name in ("align_left", "align_hcenter", "align_right"):
        x = {"align_left": 4, "align_hcenter": 12, "align_right": 20}[name]
        poly((x, 3), (x, 21), pen_=acc)
        if name == "align_left":
            rect(6, 6, 12, 4, 1, fill=ink)
            rect(6, 13, 7, 4, 1, fill=ink)
        elif name == "align_right":
            rect(6, 6, 12, 4, 1, fill=ink)
            rect(11, 13, 7, 4, 1, fill=ink)
        else:
            rect(5, 6, 14, 4, 1, fill=ink)
            rect(8, 13, 8, 4, 1, fill=ink)
    elif name in ("align_top", "align_vcenter", "align_bottom"):
        y = {"align_top": 4, "align_vcenter": 12, "align_bottom": 20}[name]
        poly((3, y), (21, y), pen_=acc)
        if name == "align_top":
            rect(6, 6, 4, 12, 1, fill=ink)
            rect(13, 6, 4, 7, 1, fill=ink)
        elif name == "align_bottom":
            rect(6, 6, 4, 12, 1, fill=ink)
            rect(13, 11, 4, 7, 1, fill=ink)
        else:
            rect(6, 5, 4, 14, 1, fill=ink)
            rect(13, 8, 4, 8, 1, fill=ink)
    elif name == "dist_h":
        poly((3, 4), (3, 20), pen_=acc)
        poly((21, 4), (21, 20), pen_=acc)
        rect(9.5, 7, 5, 10, 1, fill=ink)
    elif name == "dist_v":
        poly((4, 3), (20, 3), pen_=acc)
        poly((4, 21), (20, 21), pen_=acc)
        rect(7, 9.5, 10, 5, 1, fill=ink)
    elif name == "row":
        for x in (3, 10, 17):
            rect(x, 7, 4.5, 10, 1)
        poly((8, 12), (9.5, 12), pen_=acc)
        poly((15, 12), (16.5, 12), pen_=acc)
    elif name == "column":
        for y in (3, 10, 17):
            rect(7, y, 10, 4.5, 1)
        poly((12, 8), (12, 9.5), pen_=acc)
        poly((12, 15), (12, 16.5), pen_=acc)
    elif name == "no_layout":
        rect(4, 4, 16, 16, 2)
        rect(7, 7, 5, 5, 1, fill=accent, pen_=acc)
    elif name == "union":
        rect(3, 3, 12, 12, 1.5, fill=ink)
        rect(9, 9, 12, 12, 1.5, fill=ink)
    elif name == "subtract":
        rect(3, 3, 12, 12, 1.5, fill=ink)
        rect(9, 9, 12, 12, 1.5, fill="#00000000")
    elif name == "intersect":
        rect(3, 3, 12, 12, 1.5)
        rect(9, 9, 12, 12, 1.5)
        rect(9, 9, 6, 6, 0, fill=ink)
    elif name == "exclude":
        rect(3, 3, 12, 12, 1.5, fill=ink)
        rect(9, 9, 12, 12, 1.5, fill=ink)
        rect(9, 9, 6, 6, 0, fill="#FFFFFF")
    elif name == "fit":
        poly((4, 9), (4, 4), (9, 4))
        poly((15, 4), (20, 4), (20, 9))
        poly((20, 15), (20, 20), (15, 20))
        poly((9, 20), (4, 20), (4, 15))
    elif name == "notes":
        rect(4, 3, 16, 18, 2)
        poly((8, 8), (16, 8))
        poly((8, 12), (16, 12))
        poly((8, 16), (12, 16), pen_=acc)
    elif name == "lambda":
        text("λ", 0, 0, 24, 24, 21, italic=True, color=accent)
    else:
        circle(12, 12, 3, fill=accent, pen_=acc)
    p.end()
    return pix


def icon(name, ink="#141413", accent="#D97757", size=40):
    return QIcon(pixmap(name, ink, accent, size))


NODE_ICONS = {"frame": "frame", "component": "component", "instance": "instance", "group": "group",
              "section": "section", "rect": "rect", "ellipse": "ellipse", "polygon": "polygon", "star": "star",
              "path": "pen", "text": "text", "sticky": "sticky", "shape": "shape", "connector": "connector",
              "stamp": "stamp", "page": "page"}
