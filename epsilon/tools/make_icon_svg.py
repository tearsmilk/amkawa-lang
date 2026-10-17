"""Write assets/icon.svg — vector source of the app icon (ε converted to outlines)."""
import sys
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QPainterPath

app = QGuiApplication(sys.argv[:1] + ["-platform", "offscreen"])
size = 1024
families = set(QFontDatabase.families())
family = next((f for f in ("Georgia", "Times New Roman", "DejaVu Serif", "Liberation Serif", "Noto Serif")
               if f in families), "serif")
font = QFont(family)
font.setItalic(True)
font.setPixelSize(720)
glyph = QPainterPath()
glyph.addText(0, 0, font, "ε")
box = glyph.boundingRect()
glyph.translate(size / 2 - box.center().x(), size / 2 - box.center().y() + 10)

cmds, i = [], 0
while i < glyph.elementCount():
    e = glyph.elementAt(i)
    if e.isMoveTo():
        cmds.append(f"M{e.x:.1f} {e.y:.1f}")
        i += 1
    elif e.isLineTo():
        cmds.append(f"L{e.x:.1f} {e.y:.1f}")
        i += 1
    else:  # cubic: CurveTo + 2 CurveToData
        c1, c2 = glyph.elementAt(i + 1), glyph.elementAt(i + 2)
        cmds.append(f"C{e.x:.1f} {e.y:.1f} {c1.x:.1f} {c1.y:.1f} {c2.x:.1f} {c2.y:.1f}")
        i += 3
d = " ".join(cmds) + " Z"
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
  <!-- Epsilon app icon. Background: terracotta #D97757 squircle (100 px margin, 185 px corners). -->
  <rect id="background" x="100" y="100" width="824" height="824" rx="185" ry="185" fill="#D97757"/>
  <!-- Greek small letter epsilon, {family} Italic, converted to outlines -->
  <path id="epsilon" d="{d}" fill="#FFFFFF" fill-rule="nonzero"/>
</svg>
'''
out = Path(__file__).resolve().parent.parent / "assets" / "icon.svg"
out.write_text(svg)
print(out, len(d))
