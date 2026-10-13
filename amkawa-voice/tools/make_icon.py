"""Render assets/icon.png (1024x1024): terracotta squircle with a spark and a sound wave."""
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

cx, cy = size / 2, size / 2 - 60
pen = QPen(QColor("#FFFFFF"))
pen.setCapStyle(Qt.RoundCap)
for i in range(12):
    a = i * math.pi / 6
    length = 210 if i % 2 == 0 else 150
    pen.setWidthF(58 if i % 2 == 0 else 44)
    p.setPen(pen)
    p.drawLine(QPointF(cx + math.cos(a) * 40, cy + math.sin(a) * 40),
               QPointF(cx + math.cos(a) * length, cy + math.sin(a) * length))

pen.setWidthF(30)
pen.setColor(QColor("#FBE8DF"))
p.setPen(pen)
wave = QPainterPath()
y0 = cy + 300
wave.moveTo(300, y0)
for x in range(300, 725, 4):
    wave.lineTo(x, y0 + math.sin((x - 300) / 425 * 4 * math.pi) * 28)
p.drawPath(wave)
p.end()
out = Path(__file__).resolve().parent.parent / "assets" / "icon.png"
img.save(str(out))
print(out)
