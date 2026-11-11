"""Line icons drawn with QPainter on a 24-unit grid (ink strokes + terracotta details), cached per colour."""
import math
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


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
        p.setPen(pen if pen_ is None else pen_)
        p.drawPath(path)
        p.setPen(pen)

    def rect(x, y, w, h, r=0, fill=None, pen_=None):
        p.setBrush(QColor(fill) if fill else Qt.NoBrush)
        p.setPen(pen if pen_ is None else pen_)
        p.drawRoundedRect(QRectF(P(x, y), P(x + w, y + h)), r * s, r * s)
        p.setBrush(Qt.NoBrush)
        p.setPen(pen)

    def circle(x, y, r, fill=None, pen_=None):
        p.setBrush(QColor(fill) if fill else Qt.NoBrush)
        p.setPen(pen if pen_ is None else pen_)
        p.drawEllipse(P(x, y), r * s, r * s)
        p.setBrush(Qt.NoBrush)
        p.setPen(pen)

    def line(x1, y1, x2, y2, pen_=None):
        p.setPen(pen if pen_ is None else pen_)
        p.drawLine(P(x1, y1), P(x2, y2))
        p.setPen(pen)

    if name == "home":
        poly((4, 11), (12, 4), (20, 11), (20, 20), (4, 20), close=True)
        rect(10, 14, 4, 6, fill=accent, pen_=acc)
    elif name == "play":
        poly((6, 4), (20, 12), (6, 20), close=True, fill=ink)
    elif name == "trophy":
        poly((7, 4), (17, 4), (17, 10), (12, 15), (7, 10), close=True)
        line(7, 6, 4, 6)
        line(4, 6, 5, 10)
        line(17, 6, 20, 6)
        line(20, 6, 19, 10)
        line(12, 15, 12, 19)
        line(8, 20, 16, 20, acc)
    elif name == "settings":
        circle(12, 12, 7)
        circle(12, 12, 2.6, fill=accent, pen_=acc)
        for k in range(8):
            a = k * math.pi / 4
            line(12 + 7 * math.cos(a), 12 + 7 * math.sin(a), 12 + 9.5 * math.cos(a), 12 + 9.5 * math.sin(a))
    elif name == "map":
        poly((3, 6), (9, 4), (15, 6), (21, 4), (21, 18), (15, 20), (9, 18), (3, 20), close=True)
        line(9, 4, 9, 18)
        line(15, 6, 15, 20)
        circle(12, 11, 1.6, fill=accent, pen_=acc)
    elif name == "globe":
        circle(12, 12, 8)
        line(4, 12, 20, 12)
        path = QPainterPath(P(12, 4))
        path.cubicTo(P(16.5, 8), P(16.5, 16), P(12, 20))
        path.cubicTo(P(7.5, 16), P(7.5, 8), P(12, 4))
        p.drawPath(path)
    elif name == "refresh":
        path = QPainterPath(P(18, 8))
        path.arcTo(QRectF(P(5, 5), P(19, 19)), 60, 270)
        p.drawPath(path)
        poly((18, 4), (18.5, 9), (14, 8.5), fill=accent, pen_=acc)
    elif name == "back":
        poly((14, 5), (7, 12), (14, 19))
        line(7, 12, 20, 12)
    elif name == "pin":
        path = QPainterPath(P(12, 21))
        path.cubicTo(P(5, 13), P(5, 4), P(12, 4))
        path.cubicTo(P(19, 4), P(19, 13), P(12, 21))
        p.fillPath(path, QColor(accent))
        p.setPen(acc)
        p.drawPath(path)
        p.setPen(pen)
        circle(12, 9.5, 2.4, fill="#FFFFFF", pen_=QPen(QColor("#FFFFFF"), 0.5))
    elif name == "pinned":
        line(12, 14, 12, 21)
        poly((8, 4), (16, 4), (15, 9), (18, 14), (6, 14), (9, 9), close=True, fill=accent, pen_=acc)
    elif name == "zoom_in":
        circle(10.5, 10.5, 6)
        line(15, 15, 20, 20)
        line(8, 10.5, 13, 10.5, acc)
        line(10.5, 8, 10.5, 13, acc)
    elif name == "zoom_out":
        circle(10.5, 10.5, 6)
        line(15, 15, 20, 20)
        line(8, 10.5, 13, 10.5, acc)
    elif name == "left":
        poly((14, 6), (8, 12), (14, 18))
    elif name == "right":
        poly((10, 6), (16, 12), (10, 18))
    elif name == "compass":
        circle(12, 12, 8.5)
        poly((12, 5), (14, 12), (12, 19), (10, 12), close=True)
        poly((12, 5), (14, 12), (10, 12), close=True, fill=accent, pen_=acc)
    elif name == "flag":
        line(6, 4, 6, 21)
        poly((6, 5), (18, 5), (15, 9), (18, 13), (6, 13), close=True, fill=accent, pen_=acc)
    elif name == "clock":
        circle(12, 12, 8)
        line(12, 7, 12, 12)
        line(12, 12, 15.5, 14, acc)
    elif name == "check":
        poly((5, 12), (10, 17), (19, 7), pen_=acc)
    elif name == "close":
        line(6, 6, 18, 18)
        line(18, 6, 6, 18)
    elif name == "star":
        pts = []
        for k in range(10):
            r = 8.5 if k % 2 == 0 else 3.8
            a = -math.pi / 2 + k * math.pi / 5
            pts.append((12 + r * math.cos(a), 12.5 + r * math.sin(a)))
        poly(*pts, close=True, fill=accent, pen_=acc)
    elif name == "camera":
        rect(3, 7, 18, 12, 2)
        circle(12, 13, 3.5)
        rect(9, 4, 6, 3, 1, fill=accent, pen_=acc)
    elif name == "calendar":
        rect(4, 6, 16, 14, 2)
        line(4, 10, 20, 10)
        line(8, 4, 8, 8)
        line(16, 4, 16, 8)
        rect(7, 13, 3, 3, fill=accent, pen_=acc)
    elif name == "trash":
        line(5, 7, 19, 7)
        line(10, 4, 14, 4)
        poly((7, 7), (8, 20), (16, 20), (17, 7))
        line(10, 10, 10.5, 17)
        line(14, 10, 13.5, 17)
    elif name == "eye":
        path = QPainterPath(P(3, 12))
        path.cubicTo(P(7, 5), P(17, 5), P(21, 12))
        path.cubicTo(P(17, 19), P(7, 19), P(3, 12))
        p.drawPath(path)
        circle(12, 12, 3, fill=accent, pen_=acc)
    elif name == "move":
        poly((12, 3), (9, 6), (15, 6), close=True, fill=ink)
        poly((12, 21), (9, 18), (15, 18), close=True, fill=ink)
        poly((3, 12), (6, 9), (6, 15), close=True, fill=ink)
        poly((21, 12), (18, 9), (18, 15), close=True, fill=ink)
        circle(12, 12, 2, fill=accent, pen_=acc)
    elif name == "target":
        circle(12, 12, 8)
        circle(12, 12, 4)
        circle(12, 12, 1.2, fill=accent, pen_=acc)
        line(12, 2, 12, 6)
        line(12, 18, 12, 22)
        line(2, 12, 6, 12)
        line(18, 12, 22, 12)
    else:
        circle(12, 12, 6)
    p.end()
    return pix


def icon(name, ink="#141413", accent="#D97757", size=40):
    return QIcon(pixmap(name, ink, accent, size))
