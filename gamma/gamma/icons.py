"""Line icons drawn with QPainter on a 24-unit grid (ink strokes + terracotta details, recording red), cached
per colour. Same drawing style as Мю."""
import math
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap


@lru_cache(maxsize=512)
def pixmap(name, ink="#141413", accent="#D97757", size=40, rec="#D64545"):
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

    def corners(x0, y0, x1, y1, L=4, pen_=None):
        for a, b, c in (((x0, y0 + L), (x0, y0), (x0 + L, y0)), ((x1 - L, y0), (x1, y0), (x1, y0 + L)),
                        ((x1, y1 - L), (x1, y1), (x1 - L, y1)), ((x0 + L, y1), (x0, y1), (x0, y1 - L))):
            poly(a, b, c, pen_=pen_)

    if name == "shot_region":
        corners(3, 4, 21, 20)
        rect(8, 9, 8, 6, 1.5, pen_=acc)
        circle(12, 12, 1.2, fill=accent, pen_=acc)
    elif name == "shot_screen":
        rect(3, 4, 18, 13, 2)
        poly((9, 21), (15, 21))
        poly((12, 17), (12, 21))
        rect(9, 8, 6, 5, 1, pen_=acc)
    elif name == "rec_region":
        corners(3, 4, 21, 20, pen_=dash)
        circle(12, 12, 3.5, fill=rec, pen_=QPen(QColor(rec), 1.6 * s))
    elif name == "rec_screen":
        rect(3, 4, 18, 13, 2)
        poly((9, 21), (15, 21))
        poly((12, 17), (12, 21))
        circle(12, 10.5, 3, fill=rec, pen_=QPen(QColor(rec), 1.6 * s))
    elif name == "replay":
        p.drawArc(QRectF(P(4, 4), P(20, 20)), 100 * 16, 290 * 16)
        poly((4.5, 6.5), (6.5, 9.8), (10, 8.3), pen_=acc)
        poly((12, 8), (12, 12), (15, 14), pen_=acc)
    elif name == "stop":
        rect(6, 6, 12, 12, 2.5, fill=rec, pen_=QPen(QColor(rec), 1.6 * s))
    elif name == "record":
        circle(12, 12, 6, fill=rec, pen_=QPen(QColor(rec), 1.6 * s))
    elif name == "home":
        poly((4, 11), (12, 4), (20, 11))
        poly((6, 9.5), (6, 20), (18, 20), (18, 9.5))
        rect(10, 14, 4, 6, 1, pen_=acc)
    elif name == "settings":
        for k in range(8):
            a = k * math.pi / 4
            poly((12 + 6.5 * math.cos(a), 12 + 6.5 * math.sin(a)), (12 + 9 * math.cos(a), 12 + 9 * math.sin(a)))
        circle(12, 12, 6)
        circle(12, 12, 2.5, pen_=acc)
    elif name == "folder":
        poly((3, 6), (9, 6), (11, 8), (21, 8), (21, 19), (3, 19), close=True)
        poly((3, 11), (21, 11), pen_=acc)
    elif name == "mic":
        rect(9, 3, 6, 11, 3)
        curve((6, 11), (6, 17), (12, 17), (18, 17), (18, 11), pen_=acc)
        poly((12, 17), (12, 21))
    elif name == "mic_off":
        rect(9, 3, 6, 11, 3)
        curve((6, 11), (6, 17), (12, 17), (18, 17), (18, 11))
        poly((12, 17), (12, 21))
        poly((4, 4), (20, 20), pen_=acc)
    elif name == "speaker":
        poly((4, 9), (8, 9), (13, 5), (13, 19), (8, 15), (4, 15), close=True)
        p.drawArc(QRectF(P(10, 8), P(18, 16)), -60 * 16, 120 * 16)
        p.setPen(acc)
        p.drawArc(QRectF(P(9, 5), P(21, 19)), -60 * 16, 120 * 16)
        p.setPen(pen)
    elif name == "cursor":
        poly((6, 4), (6, 18), (10, 14.5), (13, 20), (15.5, 19), (12.5, 13), (17.5, 13), close=True)
    elif name == "clipboard":
        rect(5, 5, 14, 16, 2)
        rect(9, 3, 6, 4, 1, fill=accent, pen_=acc)
    elif name == "timer":
        circle(12, 13, 7.5)
        poly((10, 3), (14, 3))
        poly((12, 13), (12, 8.5), pen_=acc)
    elif name == "keyboard":
        rect(2.5, 6, 19, 12, 2)
        for x in (6, 9.5, 13, 16.5):
            circle(x, 10, 0.5, fill=ink)
        poly((8, 14.5), (16, 14.5), pen_=acc)
    elif name == "image":
        rect(3, 5, 18, 14, 2)
        poly((3, 17), (9, 11), (13, 15), (16, 12), (21, 17))
        circle(16, 9, 1.6, fill=accent, pen_=acc)
    elif name == "video":
        rect(3, 6, 13, 12, 2)
        poly((16, 10), (21, 7), (21, 17), (16, 14), pen_=acc)
    elif name == "play":
        poly((7, 4), (19, 12), (7, 20), close=True, fill=accent, pen_=acc)
    elif name == "trash":
        poly((4, 7), (20, 7))
        poly((9, 7), (9, 4), (15, 4), (15, 7))
        poly((6, 7), (7, 20), (17, 20), (18, 7))
        poly((10, 11), (10, 17), pen_=acc)
        poly((14, 11), (14, 17), pen_=acc)
    elif name == "close":
        poly((6, 6), (18, 18))
        poly((18, 6), (6, 18))
    elif name == "check":
        poly((5, 12.5), (10, 17), (19, 7), pen_=acc)
    elif name == "shield":
        poly((12, 3), (19, 6), (19, 12), (12, 21), (5, 12), (5, 6), close=True)
        poly((9, 12), (11.5, 14.5), (15.5, 9.5), pen_=acc)
    elif name == "copy":
        rect(4, 7, 11, 13, 2)
        rect(9, 3, 11, 13, 2, pen_=acc)
    elif name == "open":
        poly((14, 4), (20, 4), (20, 10), pen_=acc)
        poly((20, 4), (11, 13), pen_=acc)
        poly((17, 14), (17, 20), (4, 20), (4, 7), (10, 7))
    elif name == "screens":
        rect(2.5, 5, 11, 8, 1.5)
        rect(10.5, 10, 11, 8, 1.5, pen_=acc)
    elif name == "logo":
        text("γ", 0, -1, 24, 24, 20, italic=True, color=accent)
    else:
        circle(12, 12, 6)
    p.end()
    return pix


def icon(name, ink="#141413", accent="#D97757", size=40):
    return QIcon(pixmap(name, ink, accent, size))


def tray_icon(recording=False, size=44):
    """Menu-bar icon: template γ (macOS tints it), a red dot while recording."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    f = QFont("Georgia")
    f.setItalic(True)
    f.setPixelSize(int(size * 0.8))
    p.setFont(f)
    p.setPen(QColor("#000000"))
    p.drawText(QRectF(0, -size * 0.06, size, size), Qt.AlignCenter, "γ")
    if recording:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#D64545"))
        p.drawEllipse(QPointF(size * 0.8, size * 0.22), size * 0.17, size * 0.17)
    p.end()
    ic = QIcon(pix)
    ic.setIsMask(not recording)
    return ic

