"""Static website export: every site page becomes an .html file; auto layout → flexbox, "stack on mobile" rows →
a media query, fills / strokes / shadows → CSS, vectors → inline SVG, links between pages and hover effects."""
import re
import shutil
from html import escape
from pathlib import Path

from PySide6.QtGui import QColor

from . import text as textlib
from .model import FRAMELIKE

TRANSLIT = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
                    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t",
                     "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))
NARROW = 767


def slugify(name):
    s = "".join(TRANSLIT.get(ch, ch) for ch in name.lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "page"


def page_slugs(doc):
    slugs, used = {}, set()
    for i, page in enumerate(doc.pages):
        s = "index" if i == 0 else slugify(page.name)
        base, k = s, 2
        while s in used:
            s = f"{base}-{k}"
            k += 1
        used.add(s)
        slugs[page.id] = s
    return slugs


def _px(v):
    v = round(float(v), 2)
    return f"{int(v)}px" if v == int(v) else f"{v}px"


def _rgba(color, opacity=1.0):
    q = QColor(color or "#000000")
    a = (q.alphaF() if q.isValid() else 1.0) * opacity
    if a >= 0.999:
        return q.name()
    return f"rgba({q.red()}, {q.green()}, {q.blue()}, {round(a, 3)})"


def _stops(paint):
    op = paint.get("opacity", 1.0)
    return ", ".join(f"{_rgba(c, op)} {round(float(pos) * 100, 1)}%" for pos, c in paint.get("stops") or [])


class SiteWriter:
    def __init__(self, doc, folder):
        self.doc = doc
        self.folder = Path(folder)
        self.slugs = page_slugs(doc)
        self.rules = []
        self.narrow = []
        self.assets = {}

    def cls(self, n):
        return "n" + re.sub(r"[^A-Za-z0-9_-]", "-", n.id)

    def asset(self, ref):
        if ref in self.assets:
            return self.assets[ref]
        data = self.doc.images.get(ref)
        if not data:
            return ""
        ext = "png"
        if data[:3] == b"\xff\xd8\xff":
            ext = "jpg"
        elif data[:4] == b"GIF8":
            ext = "gif"
        elif data[8:12] == b"WEBP":
            ext = "webp"
        rel = f"assets/{ref}.{ext}"
        (self.folder / "assets").mkdir(parents=True, exist_ok=True)
        (self.folder / rel).write_bytes(data)
        self.assets[ref] = rel
        return rel

    # ------------------------------------------------------------------ css pieces
    def background(self, n):
        layers = []
        color = None
        paints = [p for p in n.fills if p.get("visible", True)]
        for i, paint in enumerate(reversed(paints)):  # CSS: first layer is on top
            t = paint.get("type", "solid")
            if t == "solid":
                c = _rgba(paint.get("color"), paint.get("opacity", 1.0))
                if i == len(paints) - 1 and not layers:
                    color = c
                else:
                    layers.append(f"linear-gradient({c}, {c})")
            elif t == "linear":
                layers.append(f"linear-gradient({round(paint.get('angle', 90.0) + 90, 2)}deg, {_stops(paint)})")
            elif t == "radial":
                layers.append(f"radial-gradient(closest-side, {_stops(paint)})")
            elif t == "image":
                rel = self.asset(paint.get("ref"))
                if rel:
                    mode = paint.get("mode", "fill")
                    size = {"fill": "cover", "fit": "contain", "stretch": "100% 100%", "tile": "auto"}[mode]
                    rep = "repeat" if mode == "tile" else "no-repeat"
                    layers.append(f"url('{rel}') center / {size} {rep}")
        css = {}
        if layers:
            css["background"] = ", ".join(layers) + (f", {color}" if color else "")
        elif color:
            css["background-color"] = color
        return css

    def box(self, n, root=False):
        css = {}
        parent = n.parent
        in_flow = parent is not None and parent.auto and not n.absolute and not root
        if root:
            css.update({"width": "100%", "min-height": "100vh"})
        elif in_flow:
            horiz = parent.layout == "row"
            main, cross = ("width", "height") if horiz else ("height", "width")
            autosize = self.auto_size(n)
            if n.grow:
                css["flex"] = "1 1 0"
                css["min-" + main] = "0"
            else:
                css["flex"] = "none"
                if main not in autosize:
                    css[main] = _px(n.w if horiz else n.h)
            if n.stretch and n.max_w and not horiz:
                css["width"] = "100%"
                css["max-width"] = _px(n.max_w)
            elif n.stretch:
                css["align-self"] = "stretch"
            elif cross not in autosize:
                css[cross] = _px(n.h if horiz else n.w)
            if "width" in css and "max-width" not in css:
                css["max-width"] = "100%"
        else:
            if parent is not None and parent.type != "page":
                css.update({"position": "absolute", "left": _px(n.x), "top": _px(n.y)})
            autosize = self.auto_size(n)
            if "width" not in autosize:
                css["width"] = _px(n.w)
            if "height" not in autosize:
                css["height"] = _px(n.h)
        if n.rotation and not in_flow:
            css["transform"] = f"rotate({round(n.rotation, 2)}deg)"
        if n.opacity < 1:
            css["opacity"] = str(round(n.opacity, 3))
        if n.blend != "normal":
            css["mix-blend-mode"] = n.blend
        return css

    def auto_size(self, n):
        """Dimensions the browser should compute from the content."""
        if n.type == "text":
            return {"width", "height"} if n.sizing == "auto_w" else ({"height"} if n.sizing == "auto_h" else set())
        out = set()
        if n.type in FRAMELIKE and n.auto:
            if n.hug_w:
                out.add("width")
            if n.hug_h:
                out.add("height")
        return out

    def decoration(self, n):
        css = {}
        if n.type in FRAMELIKE or n.type in ("rect", "ellipse"):
            css.update(self.background(n))
            if n.type == "ellipse":
                css["border-radius"] = "50%"
            elif n.radius:
                css["border-radius"] = _px(n.radius)
            strokes = [s for s in n.strokes if s.get("visible", True) and s.get("type", "solid") == "solid"]
            if strokes and n.stroke_width > 0:
                c = _rgba(strokes[0].get("color"), strokes[0].get("opacity", 1.0))
                style = "dashed" if n.dash else "solid"
                if n.stroke_align == "outside":
                    css["outline"] = f"{_px(n.stroke_width)} {style} {c}"
                else:
                    css["border"] = f"{_px(n.stroke_width)} {style} {c}"
            shadows = []
            for e in n.effects:
                if e.get("visible", True) and e.get("type") in ("shadow", "inner"):
                    shadows.append(("inset " if e["type"] == "inner" else "") +
                                   f"{_px(e.get('x', 0))} {_px(e.get('y', 4))} {_px(e.get('blur', 8))} "
                                   f"{_px(e.get('spread', 0))} {_rgba(e.get('color', '#000000'), e.get('opacity', .25))}")
            if shadows:
                css["box-shadow"] = ", ".join(shadows)
            if n.clip and n.type in FRAMELIKE:
                css["overflow"] = "hidden"
        return css

    def layout_css(self, n):
        css = {}
        if n.type in FRAMELIKE and n.auto:
            top, right, bottom, left = (list(n.pad) + [0] * 4)[:4]
            css.update({"display": "flex", "flex-direction": n.layout, "position": "relative"})
            if n.gap:
                css["gap"] = _px(n.gap)
            if any((top, right, bottom, left)):
                css["padding"] = " ".join(_px(v) for v in (top, right, bottom, left))
            css["justify-content"] = {"start": "flex-start", "center": "center", "end": "flex-end",
                                      "between": "space-between"}[n.justify]
            css["align-items"] = {"start": "flex-start", "center": "center", "end": "flex-end"}.get(n.align, "flex-start")
            if n.role == "section" and (left > 20 or right > 20):
                self.narrow.append(f".{self.cls(n)} {{ padding-left: {_px(min(left, 20))}; "
                                   f"padding-right: {_px(min(right, 20))}; }}")
            if n.stack and n.layout == "row":
                me = "." + self.cls(n)
                self.narrow.append(f"{me} {{ flex-direction: column; align-items: stretch; }}")
                self.narrow.append(f"{me} > * {{ width: auto; max-width: 100%; flex: none; }}")
        elif n.type in FRAMELIKE or n.type == "group":
            css["position"] = "relative"
        return css

    def text_css(self, n):
        css = {"margin": "0", "font-family": textlib.css_family(n.font), "font-size": _px(n.size),
               "font-weight": str(int(n.weight)), "white-space": "pre" if n.sizing == "auto_w" else "pre-wrap",
               "line-height": str(round(n.line_height / 100, 3)) if n.line_height else "1.2",
               "text-align": n.talign if n.talign in ("left", "center", "right") else "left"}
        if n.italic:
            css["font-style"] = "italic"
        if n.letter:
            css["letter-spacing"] = _px(n.letter)
        if n.deco:
            css["text-decoration"] = "underline" if "underline" in n.deco else "line-through"
        paints = [p for p in n.fills if p.get("visible", True)]
        if paints and paints[0].get("type") in ("linear", "radial"):
            bg = self.background(n)
            css.update(bg)
            css.update({"-webkit-background-clip": "text", "background-clip": "text", "color": "transparent"})
        elif paints and paints[0].get("type", "solid") == "solid":
            css["color"] = _rgba(paints[0].get("color"), paints[0].get("opacity", 1.0))
        if n.sizing == "fixed" and n.valign != "top":
            css.update({"display": "flex", "flex-direction": "column",
                        "justify-content": "center" if n.valign == "center" else "flex-end"})
        return css

    def hover_css(self, n):
        hv = n.hover or {}
        if not hv:
            return
        parts = []
        if hv.get("opacity") is not None and hv.get("opacity") != 1:
            parts.append(f"opacity: {round(hv['opacity'], 3)}")
        if hv.get("scale") and hv.get("scale") != 1:
            parts.append(f"transform: scale({round(hv['scale'], 3)})")
        if hv.get("fill"):
            parts.append(f"background-color: {_rgba(hv['fill'])}" if n.type != "text" else f"color: {_rgba(hv['fill'])}")
        if parts:
            me = "." + self.cls(n)
            self.rules.append(f"{me} {{ transition: opacity .2s ease, transform .2s ease, background-color .2s ease, "
                              f"color .2s ease; }}")
            self.rules.append(f"{me}:hover {{ {'; '.join(parts)}; }}")

    # ------------------------------------------------------------------ html
    def href_of(self, n):
        if n.href:
            return n.href
        target = (n.link or {}).get("target")
        if target and target in self.slugs:
            return self.slugs[target] + ".html"
        if target:
            node = self.doc.find(target)
            if node is not None and node.page().id in self.slugs:
                return self.slugs[node.page().id] + ".html"
        return None

    def element(self, n, root=False):
        if not n.visible:
            return ""
        css = self.box(n, root)
        css.update(self.layout_css(n))
        css.update(self.decoration(n))
        cls = self.cls(n)
        href = self.href_of(n)
        tag = "div"
        content = ""
        if n.type == "text":
            css.update(self.text_css(n))
            tag = n.tag if n.tag in ("h1", "h2", "h3", "h4", "p") else "p"
            content = escape(n.text)
            if href:
                tag = "a"
        elif n.type in FRAMELIKE or n.type == "group":
            content = "".join(self.element(c) for c in n.children if c.type != "connector")
            if root:
                tag = "main"
        elif n.type in ("rect", "ellipse"):
            pass
        else:
            from .svgio import node_svg
            content = node_svg(self.doc, n)
            css.setdefault("line-height", "0")
        if href and tag != "main":
            tag = "a"
        self.rules.append(f".{cls} {{ " + "; ".join(f"{k}: {v}" for k, v in css.items()) + "; }")
        self.hover_css(n)
        attrs = f' class="{cls}"'
        if tag == "a":
            ext = href.startswith(("http://", "https://", "//"))
            attrs += f' href="{escape(href)}"' + (' target="_blank" rel="noopener"' if ext else "")
        label = escape(n.name) if n.type in ("path", "polygon", "star") else ""
        if label:
            attrs += f' aria-label="{label}"'
        return f"<{tag}{attrs}>{content}</{tag}>"

    def write(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        pages_html = {}
        for page in self.doc.pages:
            root = self.doc.site_root(page)
            body = self.element(root, root=True) if root is not None else ""
            pages_html[page.id] = body
        site_name = self.doc.site.get("name", "Сайт")
        css = ["*, *::before, *::after { box-sizing: border-box; }",
               "html, body { margin: 0; padding: 0; }",
               "body { -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }",
               "a { color: inherit; text-decoration: none; }",
               "img, svg { display: block; }"]
        css += self.rules
        if self.narrow:
            css.append(f"@media (max-width: {NARROW}px) {{\n  " + "\n  ".join(self.narrow) + "\n}")
        (self.folder / "style.css").write_text("\n".join(css) + "\n", "utf-8")
        index = None
        for page in self.doc.pages:
            slug = self.slugs[page.id]
            title = escape(page.name if slug != "index" else site_name)
            if slug != "index":
                title = f"{escape(page.name)} — {escape(site_name)}"
            html = (f'<!doctype html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n'
                    f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                    f'<meta name="generator" content="Лямбда">\n<title>{title}</title>\n'
                    f'<link rel="stylesheet" href="style.css">\n</head>\n<body>\n{pages_html[page.id]}\n</body>\n</html>\n')
            out = self.folder / f"{slug}.html"
            out.write_text(html, "utf-8")
            if index is None:
                index = out
        return index


def export_site(doc, folder, clean=False):
    folder = Path(folder)
    if clean and folder.exists():
        for name in ("assets",):
            shutil.rmtree(folder / name, ignore_errors=True)
    # export at the desktop breakpoint so fixed sizes match the widest layout
    bp = doc.site.get("breakpoint", 1440)
    doc.site["breakpoint"] = 1440
    doc.relayout()
    try:
        return SiteWriter(doc, folder).write()
    finally:
        doc.site["breakpoint"] = bp
        doc.relayout()
