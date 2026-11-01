"""The .mu project file: zip with model.json, textures/<id>.png and thumbnail.png."""
import json
import zipfile
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage

from .model import Model

EXT = ".mu"


def png_bytes(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def thumbnail(model, size=420):
    from .render import Renderer
    scale = min(size / model.width, size / model.height)
    return Renderer(model).render_image(model.evaluate(), scale)


def save(model, path):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    used = {n.texture for n in model.meshes()}
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("model.json", json.dumps(model.to_dict(), ensure_ascii=False))
        for tid, img in model.textures.items():
            if tid in used:
                z.writestr(f"textures/{tid}.png", png_bytes(img), compress_type=zipfile.ZIP_STORED)
        for sc in model.scenes:
            bg = sc.get("_bg_bytes")
            if bg:
                z.writestr(f"scenes/{sc['id']}.img", bg, compress_type=zipfile.ZIP_STORED)
        try:
            z.writestr("thumbnail.png", png_bytes(thumbnail(model)))
        except Exception:
            pass
    tmp.replace(path)


def load(path):
    with zipfile.ZipFile(path) as z:
        d = json.loads(z.read("model.json").decode("utf-8"))
        if d.get("format") != "mu":
            raise ValueError("Это не файл Мю")
        textures = {}
        for name in z.namelist():
            if name.startswith("textures/") and name.endswith(".png"):
                img = QImage.fromData(z.read(name))
                textures[name[9:-4]] = img.convertToFormat(QImage.Format_ARGB32_Premultiplied)
        m = Model.from_dict(d, textures)
        for sc in m.scenes:
            key = f"scenes/{sc.get('id')}.img"
            if key in z.namelist():
                sc["_bg_bytes"] = z.read(key)
    return m


def read_thumb(path):
    try:
        with zipfile.ZipFile(path) as z:
            return QImage.fromData(z.read("thumbnail.png"))
    except Exception:
        return None
