"""The .lambda file (zip: document.json + images/ + thumbnail.png) and exports: PNG / JPG / WebP / SVG / PDF."""
import json
import zipfile
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMarginsF, QSizeF
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QTransform

from .model import Document, parent_transform, union_rect, world_bounds
from .render import Renderer, render_image


def image_bytes(img: QImage, fmt="PNG", quality=-1) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, fmt, quality)
    buf.close()
    return bytes(ba)


def thumbnail_nodes(doc):
    page = doc.pages[0]
    if doc.kind == "slides":
        return [c for c in page.children if c.visible][:1]
    if doc.kind == "site":
        root = doc.site_root(page)
        return [root] if root is not None else []
    return [c for c in page.children if c.visible]


def make_thumbnail(doc, renderer=None, size=480):
    nodes = thumbnail_nodes(doc)
    if not nodes:
        img = QImage(size, int(size * 0.62), QImage.Format_ARGB32)
        img.fill(QColor("#F0EEE6"))
        return img
    b = union_rect(world_bounds(n) for n in nodes)
    if doc.kind == "site":  # the top of the page, like a browser window
        b.setHeight(min(b.height(), b.width() * 0.62))
    scale = min(size / max(1.0, b.width()), size / max(1.0, b.height()))
    bg = "#F7F5EF" if doc.kind == "board" else ("#E9E6DC" if doc.kind == "design" else None)
    return render_image(renderer or Renderer(doc), nodes, scale, bg, b)


def save(doc, path, renderer=None):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    used = doc.used_images()
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("document.json", json.dumps(doc.to_dict(), ensure_ascii=False, indent=1))
        for key, data in doc.images.items():
            if key in used:
                z.writestr(f"images/{key}", data, compress_type=zipfile.ZIP_STORED)
        try:
            z.writestr("thumbnail.png", image_bytes(make_thumbnail(doc, renderer)))
        except Exception:
            pass
    tmp.replace(path)


def load(path):
    with zipfile.ZipFile(path) as z:
        d = json.loads(z.read("document.json").decode("utf-8"))
        if d.get("format") != "lambda":
            raise ValueError("Это не файл Лямбды")
        doc = Document.from_dict(d)
        for name in z.namelist():
            if name.startswith("images/") and len(name) > 7:
                doc.images[name[7:]] = z.read(name)
    return doc


def read_meta(path):
    """(kind, thumbnail QImage or None) without loading the whole document."""
    try:
        with zipfile.ZipFile(path) as z:
            d = json.loads(z.read("document.json").decode("utf-8"))
            img = None
            if "thumbnail.png" in z.namelist():
                img = QImage.fromData(z.read("thumbnail.png"))
            return d.get("kind", "design"), img
    except Exception:
        return None, None


# ====================================================================== exports
EXPORT_FORMATS = ["PNG", "JPG", "WEBP", "SVG", "PDF"]


def export_nodes(doc, nodes, path, fmt="PNG", scale=1.0, renderer=None):
    renderer = renderer or Renderer(doc)
    fmt = fmt.upper()
    path = Path(path)
    if fmt == "SVG":
        from .svgio import export_svg
        path.write_text(export_svg(doc, nodes), "utf-8")
    elif fmt == "PDF":
        export_pdf(doc, nodes, path, renderer)
    else:
        bg = "#FFFFFF" if fmt == "JPG" else None
        img = render_image(renderer, nodes, scale, bg)
        if fmt == "JPG":
            img = img.convertToFormat(QImage.Format_RGB32)
        img.save(str(path), "JPEG" if fmt == "JPG" else fmt, 92 if fmt in ("JPG", "WEBP") else -1)
    return path


def export_pdf(doc, nodes, path, renderer=None):
    """One PDF page per node (frames, slides). Vector output: text stays text."""
    renderer = renderer or Renderer(doc)
    nodes = [n for n in nodes if n.visible]
    if not nodes:
        return
    pdf = QPdfWriter(str(path))
    pdf.setResolution(72)
    pdf.setCreator("Лямбда")
    pdf.setTitle(Path(path).stem)
    p = None
    for i, n in enumerate(nodes):
        b = world_bounds(n)
        size = QPageSize(QSizeF(max(1.0, b.width()), max(1.0, b.height())), QPageSize.Point, "", QPageSize.ExactMatch)
        pdf.setPageLayout(QPageLayout(size, QPageLayout.Portrait, QMarginsF(0, 0, 0, 0)))
        if i == 0:
            p = QPainter(pdf)
        else:
            pdf.newPage()
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        base = QTransform.fromTranslate(-b.x(), -b.y())
        p.setTransform(parent_transform(n) * base)
        renderer.paint(p, n)
    p.end()
