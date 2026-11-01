"""Files: native .delta (zip: project.json + layer PNGs), OpenRaster .ora (Krita / MyPaint / GIMP), layered
Photoshop .psd export, flattened images, PNG sequence, animated GIF, MP4 (through ffmpeg when installed)."""
import io
import json
import os
import shutil
import struct
import subprocess
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QColor, QImage, QImageReader

from . import __version__, imgops
from .model import FMT, Document, Key, Layer, blank

IMAGE_FILTER = "Изображения (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff)"
OPEN_FILTER = "Все поддерживаемые (*.delta *.ora *.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff);;Дельта (*.delta);;" \
              "OpenRaster (*.ora);;" + IMAGE_FILTER


def png_bytes(img):
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def image_from_bytes(data):
    img = QImage()
    img.loadFromData(data)
    return img.convertToFormat(FMT)


# ---------------------------------------------------------------------- .delta
def save_delta(doc, path):
    meta = {"app": "Дельта", "version": __version__, "width": doc.width, "height": doc.height, "dpi": doc.dpi,
            "background": doc.background, "fps": doc.fps, "length": doc.length, "frame": doc.frame,
            "current": doc.layers.index(doc.current), "layers": []}
    tmp = str(path) + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for i, l in enumerate(doc.layers):
            name = f"layers/{i:03d}.png"
            z.writestr(name, png_bytes(l.image), compress_type=zipfile.ZIP_STORED)
            meta["layers"].append({
                "name": l.name, "file": name, "visible": l.visible, "locked": l.locked, "alpha_lock": l.alpha_lock,
                "clip": l.clip, "opacity": l.opacity, "blend": l.blend, "start": l.start, "end": l.end,
                "keys": {p: [[k.frame, k.value, k.ease] for k in ks] for p, ks in l.keys.items()},
            })
        z.writestr("project.json", json.dumps(meta, ensure_ascii=False, indent=1))
        thumb = doc.render().scaled(512, 512, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        z.writestr("preview.png", png_bytes(thumb))
    os.replace(tmp, path)


def load_delta(path):
    with zipfile.ZipFile(path) as z:
        meta = json.loads(z.read("project.json").decode("utf-8"))
        doc = Document(meta["width"], meta["height"], meta.get("background"), meta.get("dpi", 150))
        doc.fps = meta.get("fps", 24)
        doc.length = meta.get("length", 48)
        doc.frame = min(meta.get("frame", 0), doc.length - 1)
        doc.layers = []
        for d in meta["layers"]:
            img = image_from_bytes(z.read(d["file"]))
            if img.size() != doc.rect().size().toSize():
                fixed = blank(doc.width, doc.height)
                from PySide6.QtGui import QPainter

                p = QPainter(fixed)
                p.drawImage(0, 0, img)
                p.end()
                img = fixed
            layer = Layer(d["name"], img, d.get("visible", True), d.get("locked", False), d.get("alpha_lock", False),
                          d.get("clip", False), d.get("opacity", 1.0), d.get("blend", "normal"))
            layer.start, layer.end = d.get("start", 0), d.get("end", -1)
            layer.keys = {p: [Key(int(f), float(v), e) for f, v, e in ks] for p, ks in d.get("keys", {}).items()}
            doc.layers.append(layer)
        doc.current = doc.layers[min(meta.get("current", 0), len(doc.layers) - 1)]
    doc.path = Path(path)
    return doc


# ---------------------------------------------------------------------- images
def load_image_document(path):
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    img = reader.read()
    if img.isNull():
        raise ValueError(reader.errorString() or "Не удалось прочитать изображение")
    img = img.convertToFormat(FMT)
    doc = Document(img.width(), img.height(), None)
    doc.layers[0].name = "Фон"
    doc.layers[0].image = img
    doc.title_hint = Path(path).stem
    return doc


def save_flat(doc, path, scale=1.0, frame=None):
    ext = Path(path).suffix.lower()
    img = doc.render(frame)
    if scale != 1:
        img = img.scaled(int(doc.width * scale), int(doc.height * scale), Qt.KeepAspectRatio, Qt.SmoothTransformation)
    if ext in (".jpg", ".jpeg", ".bmp"):
        flat = QImage(img.size(), QImage.Format_RGB32)
        flat.fill(QColor(doc.background or "#FFFFFF"))
        from PySide6.QtGui import QPainter

        p = QPainter(flat)
        p.drawImage(0, 0, img)
        p.end()
        img = flat
    if not img.save(str(path), None, 92):
        raise IOError("Не удалось записать файл")


# ---------------------------------------------------------------------- OpenRaster
def save_ora(doc, path):
    tmp = str(path) + ".tmp"
    with zipfile.ZipFile(tmp, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "image/openraster", compress_type=zipfile.ZIP_STORED)
        stack = [f'<?xml version="1.0" encoding="UTF-8"?>\n<image version="0.0.5" w="{doc.width}" h="{doc.height}" '
                 f'xres="{doc.dpi}" yres="{doc.dpi}"><stack>']
        ops = {"multiply": "svg:multiply", "screen": "svg:screen", "overlay": "svg:overlay", "darken": "svg:darken",
               "lighten": "svg:lighten", "dodge": "svg:color-dodge", "burn": "svg:color-burn", "hard": "svg:hard-light",
               "soft": "svg:soft-light", "difference": "svg:difference", "exclusion": "svg:exclusion", "add": "svg:plus"}
        for i, l in reversed(list(enumerate(doc.layers))):
            name = f"data/layer{i:03d}.png"
            z.writestr(name, png_bytes(l.image))
            stack.append(f'<layer name="{escape(l.name, {chr(34): "&quot;"})}" src="{name}" x="0" y="0" '
                         f'opacity="{l.opacity:.3f}" visibility="{"visible" if l.visible else "hidden"}" '
                         f'composite-op="{ops.get(l.blend, "svg:src-over")}"' + (' alpha-preserve="true"' if l.alpha_lock else "")
                         + (' clipping="true"' if l.clip else "") + "/>")
        stack.append("</stack></image>")
        z.writestr("stack.xml", "\n".join(stack))
        merged = doc.render()
        z.writestr("mergedimage.png", png_bytes(merged))
        z.writestr("Thumbnails/thumbnail.png", png_bytes(merged.scaled(256, 256, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
    os.replace(tmp, path)


def load_ora(path):
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("stack.xml"))
        w, h = int(root.get("w")), int(root.get("h"))
        doc = Document(w, h, None)
        doc.layers = []
        inv = {"svg:multiply": "multiply", "svg:screen": "screen", "svg:overlay": "overlay", "svg:darken": "darken",
               "svg:lighten": "lighten", "svg:color-dodge": "dodge", "svg:color-burn": "burn", "svg:hard-light": "hard",
               "svg:soft-light": "soft", "svg:difference": "difference", "svg:exclusion": "exclusion", "svg:plus": "add"}
        for el in reversed(list(root.iter("layer"))):
            img = image_from_bytes(z.read(el.get("src")))
            full = blank(w, h)
            from PySide6.QtGui import QPainter

            p = QPainter(full)
            p.drawImage(int(float(el.get("x", 0))), int(float(el.get("y", 0))), img)
            p.end()
            layer = Layer(el.get("name", "Слой"), full, el.get("visibility", "visible") != "hidden")
            layer.opacity = float(el.get("opacity", 1))
            layer.blend = inv.get(el.get("composite-op", ""), "normal")
            layer.alpha_lock = el.get("alpha-preserve") == "true"
            layer.clip = el.get("clipping") == "true"
            doc.layers.append(layer)
        if not doc.layers:
            doc.layers = [Layer("Слой 1", blank(w, h))]
        doc.current = doc.layers[-1]
    doc.title_hint = Path(path).stem
    return doc


# ---------------------------------------------------------------------- Photoshop
PSD_BLEND = {"normal": b"norm", "multiply": b"mul ", "screen": b"scrn", "overlay": b"over", "darken": b"dark",
             "lighten": b"lite", "dodge": b"div ", "burn": b"idiv", "hard": b"hLit", "soft": b"sLit",
             "difference": b"diff", "exclusion": b"smud", "add": b"lddg"}


def _pascal(name, pad=4):
    b = name.encode("mac_roman", "replace")[:255]
    s = bytes([len(b)]) + b
    while len(s) % pad:
        s += b"\0"
    return s


def save_psd(doc, path):
    """Layered PSD (8-bit RGB, raw channels): layers with names, opacity, visibility, blend modes, clipping."""
    w, h = doc.width, doc.height
    records = b""
    channel_data = b""
    for l in doc.layers:
        a = imgops.to_array(l.image)  # B,G,R,A straight
        chans = [(-1, a[..., 3]), (0, a[..., 2]), (1, a[..., 1]), (2, a[..., 0])]
        rec = struct.pack(">iiiiH", 0, 0, h, w, len(chans))
        for cid, plane in chans:
            rec += struct.pack(">hI", cid, 2 + plane.size)
        flags = 0 if l.visible else 2
        if l.alpha_lock:
            flags |= 1
        rec += b"8BIM" + PSD_BLEND.get(l.blend, b"norm") + struct.pack(">BBBB", round(l.opacity * 255), 1 if l.clip else 0, flags, 0)
        name = _pascal(l.name)
        uni = l.name.encode("utf-16-be")
        luni = b"8BIMluni" + struct.pack(">I", 4 + len(uni) + (2 if len(uni) % 4 else 0)) + struct.pack(">I", len(l.name)) + uni
        if len(uni) % 4:
            luni += b"\0\0"
        extra = struct.pack(">I", 0) + struct.pack(">I", 0) + name + luni
        rec += struct.pack(">I", len(extra)) + extra
        records += rec
        for _cid, plane in chans:
            channel_data += struct.pack(">H", 0) + plane.tobytes()
    layer_info = struct.pack(">h", len(doc.layers)) + records + channel_data
    if len(layer_info) % 2:
        layer_info += b"\0"
    layer_info = struct.pack(">I", len(layer_info)) + layer_info
    lmi = layer_info + struct.pack(">I", 0)  # global layer mask info: empty
    merged = imgops.to_array(doc.render())
    out = io.BytesIO()
    out.write(b"8BPS" + struct.pack(">H6xHIIHH", 1, 4, h, w, 8, 3))
    out.write(struct.pack(">I", 0))                  # colour mode data
    out.write(struct.pack(">I", 0))                  # image resources
    out.write(struct.pack(">I", len(lmi)) + lmi)
    out.write(struct.pack(">H", 0))                  # raw merged image
    for ch in (2, 1, 0, 3):
        out.write(merged[..., ch].tobytes())
    Path(path).write_bytes(out.getvalue())


# ---------------------------------------------------------------------- animation
def frames(doc, start=0, end=None, scale=1.0):
    end = doc.length - 1 if end is None else end
    for f in range(start, end + 1):
        img = doc.render(f)
        if scale != 1:
            img = img.scaled(int(doc.width * scale), int(doc.height * scale), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        yield f, img


def save_sequence(doc, path, scale=1.0, progress=None):
    path = Path(path)
    digits = max(3, len(str(doc.length)))
    for f, img in frames(doc, scale=scale):
        img.save(str(path.with_name(f"{path.stem}_{f:0{digits}d}.png")), "PNG")
        if progress and not progress(f):
            return False
    return True


def save_gif(doc, path, scale=1.0, loop=True, progress=None):
    from .gif import write_gif

    imgs = []
    for f, img in frames(doc, scale=scale):
        imgs.append(img)
        if progress and not progress(f):
            return False
    write_gif(path, imgs, 1000.0 / doc.fps, loop)
    return True


def find_ffmpeg():
    for cand in (shutil.which("ffmpeg"), "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"):
        if cand and Path(cand).exists():
            return cand
    return None


def save_mp4(doc, path, scale=1.0, progress=None):
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("Для MP4 нужен ffmpeg (brew install ffmpeg). Можно экспортировать GIF или PNG-последовательность.")
    w = int(doc.width * scale) // 2 * 2
    h = int(doc.height * scale) // 2 * 2
    cmd = [ffmpeg, "-y", "-f", "image2pipe", "-framerate", str(doc.fps), "-i", "-", "-vf", f"scale={w}:{h}",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        for f, img in frames(doc, scale=scale):
            flat = QImage(img.size(), QImage.Format_RGB32)
            flat.fill(QColor(doc.background or "#FFFFFF"))
            from PySide6.QtGui import QPainter

            p = QPainter(flat)
            p.drawImage(0, 0, img)
            p.end()
            proc.stdin.write(png_bytes(flat))
            if progress and not progress(f):
                proc.kill()
                return False
        proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "replace")
        if proc.wait() != 0:
            raise RuntimeError(err.strip().splitlines()[-1] if err.strip() else "ffmpeg завершился с ошибкой")
    finally:
        if proc.poll() is None:
            proc.kill()
    return True
