"""Text layout shared by the canvas, auto layout and the exporters: QTextLayout lines with CSS-like line boxes
(half-leading), manual alignment and an LRU cache."""
import sys
from collections import OrderedDict

from PySide6.QtCore import QPointF
from PySide6.QtGui import QFont, QFontMetricsF, QTextLayout, QTextOption

DEFAULT_FONT = "Helvetica Neue" if sys.platform == "darwin" else "DejaVu Sans"
SERIF_FONT = "Georgia"
WEIGHTS = [(100, "Thin"), (200, "ExtraLight"), (300, "Light"), (400, "Regular"), (500, "Medium"),
           (600, "SemiBold"), (700, "Bold"), (800, "ExtraBold"), (900, "Black")]
_QW = {100: QFont.Thin, 200: QFont.ExtraLight, 300: QFont.Light, 400: QFont.Normal, 500: QFont.Medium,
       600: QFont.DemiBold, 700: QFont.Bold, 800: QFont.ExtraBold, 900: QFont.Black}
CSS_FONTS = {"Helvetica Neue": "'Helvetica Neue', Helvetica, Arial, sans-serif",
             "Georgia": "Georgia, 'Times New Roman', serif"}


def css_family(family):
    family = family or DEFAULT_FONT
    return CSS_FONTS.get(family, f"'{family}', 'Helvetica Neue', Arial, sans-serif")


def make_font(family, size, weight=400, italic=False, letter=0.0, deco=""):
    f = QFont(family or DEFAULT_FONT)
    f.setPixelSize(max(1, int(round(size))))
    f.setWeight(_QW[min(_QW, key=lambda k: abs(k - int(weight)))])
    f.setItalic(bool(italic))
    if letter:
        f.setLetterSpacing(QFont.AbsoluteSpacing, float(letter))
    f.setUnderline("underline" in deco)
    f.setStrikeOut("strike" in deco)
    f.setHintingPreference(QFont.PreferNoHinting)
    return f


class Block:
    """Laid-out text: QTextLayouts positioned in a box of size w × h (line box height lh)."""
    __slots__ = ("layouts", "w", "h", "lh", "lines")

    def __init__(self, layouts, w, h, lh, lines):
        self.layouts, self.w, self.h, self.lh, self.lines = layouts, w, h, lh, lines

    def draw(self, painter, origin=QPointF(0, 0)):
        for tl in self.layouts:
            tl.draw(painter, origin)


_cache = OrderedDict()


def layout(text, font, width=None, align="left", line_height=0.0):
    """Lay out `text` (paragraphs split on \\n). width=None → no wrapping (auto width)."""
    key = (text, font.key(), None if width is None else round(width, 2), align, round(line_height, 3))
    hit = _cache.get(key)
    if hit is not None:
        _cache.move_to_end(key)
        return hit
    fm = QFontMetricsF(font)
    lh = line_height if line_height > 0 else fm.lineSpacing()
    wrap = width is not None
    opt = QTextOption()
    opt.setWrapMode(QTextOption.WordWrap if wrap else QTextOption.NoWrap)
    pending = []  # (QTextLine, natural width)
    layouts = []
    for par in (text or "").split("\n"):
        tl = QTextLayout(par, font)
        tl.setTextOption(opt)
        tl.setCacheEnabled(True)
        tl.beginLayout()
        got = False
        while True:
            line = tl.createLine()
            if not line.isValid():
                break
            line.setLineWidth(max(1.0, width) if wrap else 1e7)
            pending.append((line, line.naturalTextWidth(), par[line.textStart():line.textStart() + line.textLength()]))
            got = True
        tl.endLayout()
        if not got:
            pending.append((None, 0.0, ""))
        layouts.append(tl)
    box_w = max(1.0, width) if wrap else max([1.0] + [nat for _, nat, _ in pending])
    y = 0.0
    lines = []
    for line, nat, s in pending:
        if line is not None:
            x = 0.0
            if align == "center":
                x = (box_w - nat) / 2
            elif align == "right":
                x = box_w - nat
            glyph_h = line.ascent() + line.descent()
            line.setPosition(QPointF(x, y + (lh - glyph_h) / 2))
            lines.append((s.rstrip("\n"), x, y + (lh - glyph_h) / 2 + line.ascent(), nat))
        y += lh
    block = Block(layouts, box_w if wrap else max(1.0, box_w), max(lh, y), lh, lines)
    _cache[key] = block
    if len(_cache) > 1500:
        _cache.popitem(last=False)
    return block


def node_font(n, size=None):
    return make_font(n.font, size or n.size, n.weight, n.italic, n.letter, n.deco)


def node_line_height(n, size=None):
    return (size or n.size) * n.line_height / 100.0 if n.line_height else 0.0


def node_block(n, width=None, size=None):
    return layout(n.text, node_font(n, size), width, n.talign, node_line_height(n, size))


BOX_PAD = {"sticky": 22.0, "shape": 14.0}


def box_block(n):
    """Text inside a sticky note / FigJam shape: wraps to the box, stickies shrink the font to fit."""
    pad = BOX_PAD.get(n.type, 12.0)
    avail_w = max(8.0, n.w - 2 * pad)
    avail_h = max(8.0, n.h - 2 * pad)
    size = n.size
    block = node_block(n, avail_w, size)
    if n.type == "sticky":
        while block.h > avail_h and size > 9:
            size = max(9.0, size * 0.88)
            block = node_block(n, avail_w, size)
    return block, pad, size
