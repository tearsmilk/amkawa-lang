"""Render assets/icon.png (1024x1024): terracotta squircle with a milk drop and a spark."""
import math
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen

app = QGuiApplication(sys.argv[:1] + ["-platform", "offscreen"])
size = 1024
img = QImage(size, size, QImage.Format_ARGB32)
img.fill(Qt.transparent)
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)
margin = 100
rect = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
path = QPainterPath()
path.addRoundedRect(rect, 185, 185)
p.fillPath(path, QColor("#D97757"))

# milk drop with a spark: notes hub
drop = QPainterPath()
cx = size / 2
drop.moveTo(cx, 230)
drop.cubicTo(cx + 40, 330, cx + 230, 480, cx + 230, 600)
drop.cubicTo(cx + 230, 740, cx + 120, 820, cx, 820)
drop.cubicTo(cx - 120, 820, cx - 230, 740, cx - 230, 600)
drop.cubicTo(cx - 230, 480, cx - 40, 330, cx, 230)
p.fillPath(drop, QColor("#FFFFFF"))
pen = QPen(QColor("#D97757"))
pen.setCapStyle(Qt.RoundCap)
sx, sy = cx, 610
for i in range(8):
    a = i * math.pi / 4
    pen.setWidthF(34 if i % 2 == 0 else 26)
    p.setPen(pen)
    length = 105 if i % 2 == 0 else 75
    p.drawLine(QPointF(sx + math.cos(a) * 22, sy + math.sin(a) * 22),
               QPointF(sx + math.cos(a) * length, sy + math.sin(a) * length))
p.end()
out = Path(__file__).resolve().parent.parent / "assets" / "icon.png"
img.save(str(out))
print(out)
