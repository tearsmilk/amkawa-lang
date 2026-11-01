"""Tool icons drawn with QPainter (stroked line icons, accent details), cached per colour."""
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


@lru_cache(maxsize=256)
def icon(name, ink="#141413", accent="#D97757", size=48):
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

    def poly(*pts, close=False, fill=None):
        path = QPainterPath(P(*pts[0]))
        for q in pts[1:]:
            path.lineTo(P(*q))
        if close:
            path.closeSubpath()
        if fill:
            p.fillPath(path, QColor(fill))
        p.drawPath(path)

    if name == "brush":
        poly((19, 3), (21, 5), (11, 15), (9, 13), close=True)
        path = QPainterPath(P(9, 13))
        path.cubicTo(P(5, 13), P(6, 18), P(3, 20))
        path.cubicTo(P(8, 21), P(11, 19), P(11, 15))
        p.fillPath(path, QColor(accent))
        p.drawPath(path)
    elif name == "eraser":
        poly((14, 4), (21, 11), (12, 20), (7, 20), (3, 16), close=True)
        p.setPen(acc)
        poly((8.5, 10.5), (15.5, 17.5))
        p.setPen(pen)
        poly((7, 20), (21, 20))
    elif name == "fill":
        poly((10, 3), (18, 11), (11, 18), (3, 10), close=True)
        p.setPen(acc)
        path = QPainterPath(P(19, 14))
        path.cubicTo(P(17, 17), P(17, 20), P(19, 20))
        path.cubicTo(P(21, 20), P(21, 17), P(19, 14))
        p.fillPath(path, QColor(accent))
        p.drawPath(path)
    elif name == "gradient":
        from PySide6.QtGui import QLinearGradient

        g = QLinearGradient(P(3, 12), P(21, 12))
        g.setColorAt(0, QColor(ink))
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(QRectF(P(3, 5), P(21, 19)), g)
        p.drawRoundedRect(QRectF(P(3, 5), P(21, 19)), 2 * s, 2 * s)
    elif name == "eyedropper":
        poly((5, 19), (13, 11))
        p.setPen(acc)
        poly((12, 8), (16, 12))
        p.setPen(pen)
        p.drawEllipse(P(17, 7), 3 * s, 3 * s)
        poly((4, 20), (5, 19))
    elif name == "line":
        poly((4, 20), (20, 4))
    elif name == "rect":
        p.drawRoundedRect(QRectF(P(4, 5), P(20, 19)), 1 * s, 1 * s)
    elif name == "ellipse":
        p.drawEllipse(QRectF(P(3, 5), P(21, 19)))
    elif name in ("select", "select_ellipse"):
        dash = QPen(QColor(ink), 1.5 * s, Qt.DashLine)
        dash.setDashPattern([2, 1.6])
        p.setPen(dash)
        if name == "select":
            p.drawRect(QRectF(P(4, 5), P(20, 19)))
        else:
            p.drawEllipse(QRectF(P(3, 5), P(21, 19)))
    elif name == "lasso":
        path = QPainterPath(P(12, 4))
        path.cubicTo(P(22, 4), P(22, 15), P(12, 15))
        path.cubicTo(P(3, 15), P(2, 4), P(12, 4))
        dash = QPen(QColor(ink), 1.5 * s, Qt.DashLine)
        dash.setDashPattern([2, 1.6])
        p.setPen(dash)
        p.drawPath(path)
        p.setPen(acc)
        poly((8, 14), (7, 20))
    elif name == "wand":
        poly((4, 20), (15, 9))
        p.setPen(acc)
        for a, b in (((18, 3), (18, 6)), ((18, 12), (18, 15)), ((21, 9), (24, 9)), ((12, 9), (15, 9)), ((20, 5), (21, 4))):
            poly(a, b)
    elif name == "move":
        poly((12, 3), (12, 21))
        poly((3, 12), (21, 12))
        for pts in (((9, 6), (12, 3), (15, 6)), ((9, 18), (12, 21), (15, 18)), ((6, 9), (3, 12), (6, 15)),
                    ((18, 9), (21, 12), (18, 15))):
            poly(*pts)
    elif name == "transform":
        dash = QPen(QColor(ink), 1.4 * s, Qt.DashLine)
        dash.setDashPattern([2, 1.6])
        p.setPen(dash)
        p.drawRect(QRectF(P(5, 5), P(19, 19)))
        p.setPen(acc)
        p.setBrush(QColor(accent))
        for x, y in ((5, 5), (19, 5), (19, 19), (5, 19)):
            p.drawRect(QRectF(P(x - 1.6, y - 1.6), P(x + 1.6, y + 1.6)))
    elif name == "panel":
        p.drawRect(QRectF(P(3, 3), P(21, 21)))
        p.setPen(acc)
        poly((3, 11), (21, 9))
        poly((12, 10), (11, 21))
    elif name == "bubble":
        path = QPainterPath()
        path.addEllipse(QRectF(P(2, 3), P(22, 16)))
        tail = QPainterPath(P(8, 15))
        tail.lineTo(P(5, 21))
        tail.lineTo(P(12, 16))
        path = path.united(tail)
        p.drawPath(path)
        p.setPen(acc)
        poly((7, 9.5), (17, 9.5))
    elif name == "text":
        f = QFont("Georgia")
        f.setPixelSize(int(18 * s))
        p.setFont(f)
        p.drawText(QRectF(P(0, 0), P(24, 24)), Qt.AlignCenter, "A")
        p.setPen(acc)
        poly((5, 21), (19, 21))
    elif name == "tone":
        p.setPen(Qt.NoPen)
        for i in range(5):
            for j in range(5):
                r = 0.4 + (i + j) * 0.18
                p.setBrush(QColor(accent if (i + j) > 5 else ink))
                p.drawEllipse(P(3.5 + i * 4.2 + (j % 2) * 2.1, 3.5 + j * 4.2), r * s, r * s)
    elif name == "hand":
        path = QPainterPath(P(8, 21))
        path.lineTo(P(5, 13))
        path.cubicTo(P(4, 11), P(7, 10), P(8, 12))
        path.lineTo(P(8, 5))
        path.cubicTo(P(8, 3), P(11, 3), P(11, 5))
        path.lineTo(P(11, 11))
        path.lineTo(P(11, 4))
        path.cubicTo(P(11, 2), P(14, 2), P(14, 4))
        path.lineTo(P(14, 11))
        path.lineTo(P(14, 5))
        path.cubicTo(P(14, 3), P(17, 3), P(17, 5))
        path.lineTo(P(17, 12))
        path.lineTo(P(17, 8))
        path.cubicTo(P(17, 6), P(20, 6), P(20, 8))
        path.lineTo(P(20, 15))
        path.cubicTo(P(20, 19), P(18, 21), P(15, 21))
        path.closeSubpath()
        p.drawPath(path)
    elif name == "zoom":
        p.drawEllipse(P(10, 10), 6.5 * s, 6.5 * s)
        poly((15, 15), (21, 21))
        p.setPen(acc)
        poly((7, 10), (13, 10))
        poly((10, 7), (10, 13))
    elif name == "rotate":
        path = QPainterPath()
        path.arcMoveTo(QRectF(P(4, 4), P(20, 20)), 60)
        path.arcTo(QRectF(P(4, 4), P(20, 20)), 60, 280)
        p.drawPath(path)
        p.setPen(acc)
        poly((16, 3), (16, 6.5), (19.5, 6.5))
    elif name == "play":
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(accent))
        p.drawPolygon(QPolygonF([P(7, 4), P(20, 12), P(7, 20)]))
    elif name == "pause":
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(accent))
        p.drawRoundedRect(QRectF(P(6, 5), P(10, 19)), s, s)
        p.drawRoundedRect(QRectF(P(14, 5), P(18, 19)), s, s)
    elif name == "key":
        p.setBrush(QColor(accent))
        p.drawPolygon(QPolygonF([P(12, 3), P(21, 12), P(12, 21), P(3, 12)]))
    elif name == "eye":
        path = QPainterPath(P(2, 12))
        path.cubicTo(P(7, 4), P(17, 4), P(22, 12))
        path.cubicTo(P(17, 20), P(7, 20), P(2, 12))
        p.drawPath(path)
        p.setBrush(QColor(ink))
        p.drawEllipse(P(12, 12), 2.6 * s, 2.6 * s)
    elif name == "lock":
        p.drawRoundedRect(QRectF(P(5, 11), P(19, 21)), 2 * s, 2 * s)
        path = QPainterPath(P(8, 11))
        path.lineTo(P(8, 8))
        path.arcTo(QRectF(P(8, 4), P(16, 12)), 180, -180)
        path.lineTo(P(16, 11))
        p.drawPath(path)
    else:
        f = QFont()
        f.setPixelSize(int(14 * s))
        p.setFont(f)
        p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, name[:2])
    p.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)


def swatch(color, size=14):
    pix = QPixmap(size * 2, size * 2)
    pix.fill(QColor(color))
    pix.setDevicePixelRatio(2)
    return QIcon(pix)
