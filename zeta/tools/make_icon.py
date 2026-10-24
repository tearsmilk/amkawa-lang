"""Render assets/icon.png (1024×1024): terracotta squircle with a pixel-art Greek zeta (ζ).

The ζ is a hand-drawn pixel sprite (2-px strokes), scaled up with nearest neighbour; a 1-px darker shadow gives it the classic pixel-art look. Also writes
assets/zeta-sprite.png — the 1× sprite itself.
"""
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath

app = QGuiApplication(sys.argv[:1] + ["-platform", "offscreen"])

# 1) the sprite: a hand-drawn 16×20 ζ with 2-px strokes
ZETA = """
................
...##########...
...##########...
.......####.....
......###.......
.....###........
....###.........
...###..........
...##...........
..###...........
..##............
..##............
..###...........
...#########....
....#########...
..........###...
...........##...
..........###...
.........###....
........##......
"""
rows = [r for r in ZETA.strip("\n").split("\n")]
GRID = 22
sprite = QImage(GRID, GRID, QImage.Format_ARGB32)
sprite.fill(Qt.transparent)
ox, oy = (GRID - len(rows[0])) // 2, (GRID - len(rows)) // 2
for y, row in enumerate(rows):
    for x, ch in enumerate(row):
        if ch == "#":
            sprite.setPixelColor(ox + x, oy + y, QColor("#FFFFFF"))
# pixel shadow (down-right, terracotta dark) under the white glyph
shaded = QImage(GRID, GRID, QImage.Format_ARGB32)
shaded.fill(Qt.transparent)
for y in range(GRID):
    for x in range(GRID):
        if sprite.pixelColor(x, y).alpha() > 0 and x + 1 < GRID and y + 1 < GRID:
            shaded.setPixelColor(x + 1, y + 1, QColor("#9A3F24"))
for y in range(GRID):
    for x in range(GRID):
        if sprite.pixelColor(x, y).alpha() > 0:
            shaded.setPixelColor(x, y, QColor("#FFFFFF"))
out_dir = Path(__file__).resolve().parent.parent / "assets"
shaded.save(str(out_dir / "zeta-sprite.png"))

# 2) the icon
size = 1024
img = QImage(size, size, QImage.Format_ARGB32)
img.fill(Qt.transparent)
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)
margin = 100
bg = QPainterPath()
bg.addRoundedRect(QRectF(margin, margin, size - 2 * margin, size - 2 * margin), 185, 185)
p.fillPath(bg, QColor("#D97757"))
cell = 28
art = shaded.scaled(GRID * cell, GRID * cell, Qt.IgnoreAspectRatio, Qt.FastTransformation)
p.setRenderHint(QPainter.SmoothPixmapTransform, False)
p.drawImage((size - art.width()) // 2, (size - art.height()) // 2, art)
p.end()
img.save(str(out_dir / "icon.png"))
print(out_dir / "icon.png")
