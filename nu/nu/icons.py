"""Icons painted in code (no image assets): file badges by language, folders, activity-bar glyphs."""
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap

from . import languages

SIZE = 32  # drawn at 2× for Retina


def _canvas(size=SIZE):
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    return pix, p


@lru_cache(maxsize=512)
def badge(text, color):
    pix, p = _canvas()
    font = QFont()
    font.setBold(True)
    n = len(text)
    font.setPixelSize(19 if n == 1 else 15 if n == 2 else 11)
    p.setFont(font)
    p.setPen(QColor(color))
    p.drawText(QRectF(0, 0, SIZE, SIZE), Qt.AlignCenter, text)
    p.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)


def file_icon(path):
    lang = languages.detect(path)
    name = str(path).lower()
    if name.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".icns", ".tiff", ".heic")):
        return badge("▣", "#3A97A8")
    if name.endswith((".zip", ".tar", ".gz", ".7z", ".rar", ".dmg")):
        return badge("▤", "#8A6A4A")
    if name.endswith(".pdf"):
        return badge("P", "#C2453E")
    return badge(lang.badge or "·", lang.color)


@lru_cache(maxsize=8)
def folder_icon(color, open_=False):
    pix, p = _canvas()
    path = QPainterPath()
    path.moveTo(4, 9)
    path.lineTo(12, 9)
    path.lineTo(14.5, 11.5)
    path.lineTo(28, 11.5)
    path.lineTo(28, 25)
    path.lineTo(4, 25)
    path.closeSubpath()
    p.setPen(QPen(QColor(color), 2.2))
    p.setBrush(QColor(color) if open_ else Qt.NoBrush)
    p.drawPath(path)
    p.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)


@lru_cache(maxsize=64)
def glyph(name, color, size=48):
    """Activity bar / toolbar glyphs, stroked like the rest of the UI."""
    pix, p = _canvas(size)
    s = size / 24.0
    pen = QPen(QColor(color), 1.7 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    P = lambda x, y: QPointF(x * s, y * s)  # noqa: E731
    if name == "files":
        p.drawRoundedRect(QRectF(7 * s, 3 * s, 11 * s, 14 * s), 2 * s, 2 * s)
        path = QPainterPath(P(4, 7))
        path.lineTo(P(4, 21))
        path.lineTo(P(14, 21))
        p.drawPath(path)
    elif name == "search":
        p.drawEllipse(QRectF(4 * s, 4 * s, 12 * s, 12 * s))
        p.drawLine(P(14.5, 14.5), P(20, 20))
    elif name == "git":
        for x, y in ((7, 5), (7, 19), (17, 9)):
            p.drawEllipse(QRectF((x - 2.3) * s, (y - 2.3) * s, 4.6 * s, 4.6 * s))
        p.drawLine(P(7, 7.3), P(7, 16.7))
        path = QPainterPath(P(17, 11.3))
        path.cubicTo(P(17, 15), P(10, 13), P(8, 16.8))
        p.drawPath(path)
    elif name == "run":
        path = QPainterPath(P(7, 4.5))
        path.lineTo(P(19, 12))
        path.lineTo(P(7, 19.5))
        path.closeSubpath()
        p.drawPath(path)
    elif name == "gear":
        p.drawEllipse(QRectF(9 * s, 9 * s, 6 * s, 6 * s))
        import math

        for i in range(8):
            a = i * math.pi / 4
            p.drawLine(P(12 + 6.2 * math.cos(a), 12 + 6.2 * math.sin(a)), P(12 + 8.6 * math.cos(a), 12 + 8.6 * math.sin(a)))
        p.drawEllipse(QRectF(5.8 * s, 5.8 * s, 12.4 * s, 12.4 * s))
    elif name == "terminal":
        p.drawRoundedRect(QRectF(3 * s, 5 * s, 18 * s, 14 * s), 2 * s, 2 * s)
        path = QPainterPath(P(7, 9.5))
        path.lineTo(P(10, 12))
        path.lineTo(P(7, 14.5))
        p.drawPath(path)
        p.drawLine(P(12, 15), P(16, 15))
    elif name == "split":
        p.drawRoundedRect(QRectF(3 * s, 4 * s, 18 * s, 16 * s), 2 * s, 2 * s)
        p.drawLine(P(12, 4), P(12, 20))
    elif name == "plus":
        p.drawLine(P(12, 5), P(12, 19))
        p.drawLine(P(5, 12), P(19, 12))
    elif name == "close":
        p.drawLine(P(7, 7), P(17, 17))
        p.drawLine(P(17, 7), P(7, 17))
    elif name == "refresh":
        path = QPainterPath(P(18.5, 8))
        path.arcTo(QRectF(5 * s, 5 * s, 14 * s, 14 * s), 30, 300)
        p.drawPath(path)
        p.drawLine(P(18.5, 8), P(18.5, 3.5))
        p.drawLine(P(18.5, 8), P(14, 8))
    elif name == "collapse":
        p.drawRoundedRect(QRectF(4 * s, 4 * s, 16 * s, 16 * s), 2 * s, 2 * s)
        p.drawLine(P(8, 12), P(16, 12))
    elif name == "newfile":
        p.drawRoundedRect(QRectF(5 * s, 3 * s, 12 * s, 17 * s), 2 * s, 2 * s)
        p.drawLine(P(17, 15), P(17, 22))
        p.drawLine(P(13.5, 18.5), P(20.5, 18.5))
    elif name == "newfolder":
        path = QPainterPath(P(3, 6))
        path.lineTo(P(9, 6))
        path.lineTo(P(11, 8))
        path.lineTo(P(19, 8))
        path.lineTo(P(19, 12))
        path.moveTo(P(14, 19))
        path.lineTo(P(3, 19))
        path.lineTo(P(3, 6))
        p.drawPath(path)
        p.drawLine(P(18, 14), P(18, 21))
        p.drawLine(P(14.5, 17.5), P(21.5, 17.5))
    elif name == "check":
        path = QPainterPath(P(5, 12.5))
        path.lineTo(P(10, 17.5))
        path.lineTo(P(19, 7))
        p.drawPath(path)
    elif name == "chevron-up":
        path = QPainterPath(P(6, 15))
        path.lineTo(P(12, 9))
        path.lineTo(P(18, 15))
        p.drawPath(path)
    elif name == "chevron-down":
        path = QPainterPath(P(6, 9))
        path.lineTo(P(12, 15))
        path.lineTo(P(18, 9))
        p.drawPath(path)
    elif name == "trash":
        p.drawLine(P(4, 7), P(20, 7))
        p.drawRoundedRect(QRectF(6.5 * s, 7 * s, 11 * s, 13 * s), 1.5 * s, 1.5 * s)
        p.drawLine(P(10, 4), P(14, 4))
    p.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)
