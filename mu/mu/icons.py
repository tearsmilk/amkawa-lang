"""Line icons drawn with QPainter on a 24-unit grid (ink strokes + terracotta details), cached per colour."""
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
    dash = QPen(QColor(ink), 1.4 * s, Qt.DashLine, Qt.RoundCap, Qt.RoundJoin)
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

    def curve(*pts, pen_=None):
        path = QPainterPath(P(*pts[0]))
        for i in range(1, len(pts) - 1, 2):
            path.quadTo(P(*pts[i]), P(*pts[i + 1]))
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

    def text(t, x, y, w, h, px, italic=False, color=None):
        f = QFont("Georgia")
        f.setPixelSize(max(1, int(px * s)))
        f.setItalic(italic)
        p.setFont(f)
        p.setPen(QColor(color or ink))
        p.drawText(QRectF(P(x, y), P(x + w, y + h)), Qt.AlignCenter, t)
        p.setPen(pen)

    if name == "select":
        poly((6, 4), (6, 18), (10, 14.5), (13, 20), (15.5, 19), (12.5, 13), (17.5, 13), close=True)
    elif name == "move":
        poly((12, 3), (12, 21))
        poly((3, 12), (21, 12))
        for a, b, c in (((9.5, 5.5), (12, 3), (14.5, 5.5)), ((9.5, 18.5), (12, 21), (14.5, 18.5)),
                        ((5.5, 9.5), (3, 12), (5.5, 14.5)), ((18.5, 9.5), (21, 12), (18.5, 14.5))):
            poly(a, b, c, pen_=acc)
    elif name == "lasso":
        curve((12, 5), (21, 5), (19, 11), (16, 16), (9, 15), (2, 13), (5, 8), (7, 5), (12, 5), pen_=dash)
        poly((9, 15), (8, 19), (10, 21), pen_=acc)
    elif name == "polygon":
        poly((5, 6), (18, 4), (20, 15), (11, 20), (4, 15), close=True, pen_=dash)
        for x, y in ((5, 6), (18, 4), (20, 15), (11, 20), (4, 15)):
            circle(x, y, 1.6, fill=accent, pen_=acc)
    elif name == "brush":
        poly((19, 4), (11, 13))
        poly((11, 13), (14, 16))
        poly((14, 16), (20, 5), (19, 4))
        curve((10, 14), (6, 14), (6, 18), (5, 20), (9, 20), (12, 19), (13, 16), pen_=acc)
    elif name == "wand":
        poly((4, 20), (15, 9))
        poly((15, 9), (17, 11), pen_=acc)
        for x, y, r in ((17, 4, 1.6), (21, 8, 1.2), (12, 4, 1.0), (20, 13, 1.0)):
            circle(x, y, r, fill=accent, pen_=acc)
    elif name == "cut":
        circle(7, 17, 3)
        circle(17, 17, 3)
        poly((9, 15), (18, 4))
        poly((15, 15), (6, 4))
        poly((3, 11), (21, 11), pen_=QPen(QColor(accent), 1.2 * s, Qt.DashLine))
    elif name == "copy_layer":
        rect(4, 7, 11, 13, 2)
        rect(9, 3, 11, 13, 2, fill=accent, pen_=acc)
    elif name == "deselect":
        rect(4, 4, 16, 16, 2, pen_=dash)
        poly((8, 8), (16, 16), pen_=acc)
        poly((16, 8), (8, 16), pen_=acc)
    elif name == "mesh":
        pts = [(4, 18), (12, 4), (20, 18), (12, 13)]
        for a, b in ((0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3)):
            poly(pts[a], pts[b])
        for x, y in pts:
            circle(x, y, 1.6, fill=accent, pen_=acc)
    elif name == "automesh":
        pts = [(4, 18), (12, 4), (20, 18), (12, 13)]
        for a, b in ((0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3)):
            poly(pts[a], pts[b])
        text("A", 13, 13, 10, 10, 9, color=accent)
    elif name == "warp":
        curve((4, 6), (12, 3), (20, 6))
        curve((4, 12), (12, 9), (20, 12))
        curve((4, 18), (12, 15), (20, 18))
        poly((4, 6), (4, 18))
        curve((12, 4.5), (13, 11), (12, 16.5))
        poly((20, 6), (20, 18))
        circle(12, 10.5, 1.6, fill=accent, pen_=acc)
    elif name == "rotate":
        circle(12, 14, 2, fill=accent, pen_=acc)
        poly((12, 14), (12, 4))
        p.drawArc(QRectF(P(4, 6), P(20, 22)), 30 * 16, 120 * 16)
        poly((17.5, 6.5), (19.8, 8.6), (17, 10))
    elif name == "pin":
        circle(12, 9, 4.5)
        poly((12, 13.5), (12, 21), pen_=acc)
    elif name == "eye":
        curve((3, 12), (12, 4), (21, 12))
        curve((3, 12), (12, 20), (21, 12))
        circle(12, 12, 3, fill=accent, pen_=acc)
    elif name == "eye_off":
        curve((3, 12), (12, 4), (21, 12))
        curve((3, 12), (12, 20), (21, 12))
        poly((4, 20), (20, 4), pen_=acc)
    elif name == "lock":
        rect(5, 11, 14, 10, 2)
        p.drawArc(QRectF(P(8, 4), P(16, 15)), 0, 180 * 16)
        circle(12, 16, 1.4, fill=accent, pen_=acc)
    elif name == "key":
        poly((12, 4), (19, 12), (12, 20), (5, 12), close=True, fill=accent, pen_=acc)
    elif name == "key_off":
        poly((12, 4), (19, 12), (12, 20), (5, 12), close=True)
    elif name == "plus":
        poly((12, 5), (12, 19))
        poly((5, 12), (19, 12))
    elif name == "minus":
        poly((5, 12), (19, 12))
    elif name == "trash":
        poly((4, 7), (20, 7))
        poly((9, 7), (9, 4), (15, 4), (15, 7))
        poly((6, 7), (7, 20), (17, 20), (18, 7))
        poly((10, 11), (10, 17), pen_=acc)
        poly((14, 11), (14, 17), pen_=acc)
    elif name == "play":
        poly((7, 4), (19, 12), (7, 20), close=True, fill=accent, pen_=acc)
    elif name == "pause":
        rect(6, 4, 4, 16, 1, fill=accent, pen_=acc)
        rect(14, 4, 4, 16, 1, fill=accent, pen_=acc)
    elif name == "camera":
        rect(3, 7, 18, 13, 3)
        poly((8, 7), (10, 4), (14, 4), (16, 7))
        circle(12, 13.5, 3.5, pen_=acc)
    elif name == "image":
        rect(3, 5, 18, 14, 2)
        poly((3, 17), (9, 11), (13, 15), (16, 12), (21, 17))
        circle(16, 9, 1.6, fill=accent, pen_=acc)
    elif name == "pose":
        circle(12, 4.5, 2.2, fill=accent, pen_=acc)
        poly((12, 7), (12, 14))
        poly((5, 6), (12, 9.5), (19, 5))
        poly((8, 21), (12, 14), (16, 21))
    elif name == "physics":
        poly((12, 3), (12, 8))
        curve((12, 8), (8, 13), (13, 16), (18, 19), (12, 21), pen_=acc)
        circle(12, 3, 1.5, fill=ink)
    elif name == "mic":
        rect(9, 3, 6, 11, 3)
        curve((6, 11), (6, 17), (12, 17), (18, 17), (18, 11), pen_=acc)
        poly((12, 17), (12, 21))
    elif name == "mouse":
        rect(7, 3, 10, 18, 5)
        poly((12, 3), (12, 9), pen_=acc)
    elif name == "book":
        poly((12, 6), (12, 20))
        curve((12, 6), (8, 4), (3, 5))
        poly((3, 5), (3, 19))
        curve((3, 19), (8, 18), (12, 20))
        curve((12, 6), (16, 4), (21, 5), pen_=acc)
        poly((21, 5), (21, 19), pen_=acc)
        curve((21, 19), (16, 18), (12, 20), pen_=acc)
    elif name == "undo":
        curve((8, 9), (19, 8), (19, 14), (19, 19), (10, 19))
        poly((11, 5), (7, 9), (11, 13), pen_=acc)
    elif name == "redo":
        curve((16, 9), (5, 8), (5, 14), (5, 19), (14, 19))
        poly((13, 5), (17, 9), (13, 13), pen_=acc)
    elif name == "export":
        poly((12, 15), (12, 3), pen_=acc)
        poly((8, 7), (12, 3), (16, 7), pen_=acc)
        poly((5, 12), (5, 20), (19, 20), (19, 12))
    elif name == "save":
        rect(4, 4, 16, 16, 2)
        rect(8, 4, 8, 5, 0)
        rect(7, 13, 10, 7, 1, pen_=acc)
    elif name == "folder":
        poly((3, 6), (9, 6), (11, 8), (21, 8), (21, 19), (3, 19), close=True)
        poly((3, 11), (21, 11), pen_=acc)
    elif name == "wire":
        rect(4, 4, 16, 16, 1)
        poly((4, 4), (20, 20))
        poly((12, 4), (20, 12), pen_=acc)
        poly((4, 12), (12, 20), pen_=acc)
    elif name == "auto":
        poly((12, 3), (14, 9), (20, 10), (15, 14), (17, 20), (12, 16.5), (7, 20), (9, 14), (4, 10), (10, 9),
             close=True, fill=accent, pen_=acc)
    elif name == "mirror":
        poly((12, 3), (12, 21), pen_=dash)
        poly((9, 6), (3, 18), (9, 18), close=True)
        poly((15, 6), (21, 18), (15, 18), close=True, fill=accent, pen_=acc)
    elif name == "merge":
        rect(4, 4, 10, 10, 2)
        rect(10, 10, 10, 10, 2, fill=accent, pen_=acc)
    elif name == "up":
        poly((6, 14), (12, 8), (18, 14))
    elif name == "down":
        poly((6, 10), (12, 16), (18, 10))
    elif name == "fit":
        for a, b, c in (((4, 9), (4, 4), (9, 4)), ((15, 4), (20, 4), (20, 9)), ((20, 15), (20, 20), (15, 20)),
                        ((9, 20), (4, 20), (4, 15))):
            poly(a, b, c)
        rect(9, 9, 6, 6, 1, pen_=acc)
    elif name == "studio":
        rect(3, 4, 18, 13, 2)
        poly((3, 14), (8, 10), (12, 13))
        circle(16, 9, 2, fill=accent, pen_=acc)
        poly((14, 17), (14, 13), (18, 13), (18, 17), pen_=acc)
        poly((8, 21), (16, 21))
    elif name == "live":
        circle(12, 12, 3, fill=accent, pen_=acc)
        p.drawArc(QRectF(P(5, 5), P(19, 19)), -50 * 16, 100 * 16)
        p.drawArc(QRectF(P(5, 5), P(19, 19)), 130 * 16, 100 * 16)
        p.drawArc(QRectF(P(1.5, 1.5), P(22.5, 22.5)), -45 * 16, 90 * 16)
        p.drawArc(QRectF(P(1.5, 1.5), P(22.5, 22.5)), 135 * 16, 90 * 16)
    elif name == "window":
        rect(3, 5, 18, 14, 2)
        poly((3, 9), (21, 9))
        circle(6, 7, 0.6, fill=accent, pen_=acc)
    elif name == "dice":
        rect(4, 4, 16, 16, 3)
        for x, y in ((8.5, 8.5), (15.5, 15.5), (12, 12)):
            circle(x, y, 1.3, fill=accent, pen_=acc)
    elif name == "reset":
        p.drawArc(QRectF(P(5, 5), P(19, 19)), 60 * 16, 300 * 16)
        poly((15, 3.5), (15.5, 7.5), (19.5, 6), pen_=acc)
    elif name == "flip":
        poly((12, 3), (12, 21), pen_=dash)
        poly((9, 6), (3, 18), (9, 18), close=True)
        poly((15, 6), (21, 18), (15, 18), close=True, pen_=acc)
    elif name == "front":
        rect(4, 4, 11, 11, 2)
        rect(9, 9, 11, 11, 2, fill=accent, pen_=acc)
    elif name == "back":
        rect(9, 9, 11, 11, 2)
        rect(4, 4, 11, 11, 2, fill=accent, pen_=acc)
    elif name == "logo":
        text("μ", 0, 0, 24, 24, 20, italic=True, color=accent)
    else:
        circle(12, 12, 6)
    p.end()
    return pix


def icon(name, ink="#141413", accent="#D97757", size=40):
    return QIcon(pixmap(name, ink, accent, size))

