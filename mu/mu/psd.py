"""Layered PSD: reading (8-bit RGB / RGBA layers, raw or RLE, groups → name prefixes) for importing artwork
to rig, and writing (one layer per art mesh) for taking a character into Live2D Cubism Editor."""
import struct

import numpy as np
from PySide6.QtGui import QImage


class PsdLayer:
    def __init__(self, name, x, y, image, visible=True, opacity=1.0, group=""):
        self.name, self.x, self.y, self.image = name, x, y, image
        self.visible, self.opacity, self.group = visible, opacity, group


def _rle_decode(data, size):
    out = bytearray()
    i = 0
    n = len(data)
    while len(out) < size and i < n:
        h = data[i]
        i += 1
        if h < 128:
            out += data[i:i + h + 1]
            i += h + 1
        elif h > 128:
            out += bytes([data[i]]) * (257 - h)
            i += 1
    return bytes(out[:size]).ljust(size, b"\0")


def _channel(f, w, h, version=1):
    comp = struct.unpack(">H", f.read(2))[0]
    if comp == 0:
        return np.frombuffer(f.read(w * h), dtype=np.uint8).reshape(h, w)
    if comp == 1:
        counts = struct.unpack(f">{h}" + ("H" if version == 1 else "I"), f.read(h * (2 if version == 1 else 4)))
        rows = [_rle_decode(f.read(c), w) for c in counts]
        return np.frombuffer(b"".join(rows), dtype=np.uint8).reshape(h, w)
    raise ValueError("Сжатие ZIP в PSD не поддерживается — сохраните PSD без сжатия или с RLE")


def read_psd(path):
    """→ (width, height, [PsdLayer…]) in bottom-to-top order."""
    with open(path, "rb") as f:
        if f.read(4) != b"8BPS":
            raise ValueError("Это не PSD")
        version = struct.unpack(">H", f.read(2))[0]
        f.read(6)
        channels, H, W, depth, mode = struct.unpack(">HIIHH", f.read(14))
        if depth != 8 or mode not in (1, 3):
            raise ValueError("Поддерживаются 8-битные PSD в RGB или градациях серого")
        f.read(struct.unpack(">I", f.read(4))[0])        # color mode data
        f.read(struct.unpack(">I", f.read(4))[0])        # image resources
        lm_len = struct.unpack(">I" if version == 1 else ">Q", f.read(4 if version == 1 else 8))[0]
        if lm_len == 0:
            return W, H, []
        f.read(4 if version == 1 else 8)                 # layer info length
        count = struct.unpack(">h", f.read(2))[0]
        count = abs(count)
        recs = []
        for _ in range(count):
            top, left, bottom, right = struct.unpack(">iiii", f.read(16))
            nch = struct.unpack(">H", f.read(2))[0]
            chans = []
            for _ in range(nch):
                cid = struct.unpack(">h", f.read(2))[0]
                ln = struct.unpack(">I" if version == 1 else ">Q", f.read(4 if version == 1 else 8))[0]
                chans.append((cid, ln))
            f.read(4)  # blend signature
            blend = f.read(4)
            opacity, clipping, flags, _ = struct.unpack(">BBBB", f.read(4))
            extra_len = struct.unpack(">I", f.read(4))[0]
            extra = f.read(extra_len)
            # mask data, blending ranges, pascal name, then additional info (luni = unicode name, lsct = group)
            o = 0
            ml = struct.unpack(">I", extra[o:o + 4])[0]
            o += 4 + ml
            bl = struct.unpack(">I", extra[o:o + 4])[0]
            o += 4 + bl
            nl = extra[o]
            name = extra[o + 1:o + 1 + nl].decode("latin-1", "replace")
            o += 1 + nl
            o += (4 - (1 + nl) % 4) % 4
            section = 0
            while o + 12 <= len(extra):
                sig = extra[o:o + 4]
                key = extra[o + 4:o + 8]
                ln = struct.unpack(">I", extra[o + 8:o + 12])[0]
                data = extra[o + 12:o + 12 + ln]
                if sig not in (b"8BIM", b"8B64"):
                    break
                if key == b"luni" and len(data) >= 4:
                    n = struct.unpack(">I", data[:4])[0]
                    name = data[4:4 + n * 2].decode("utf-16-be", "replace")
                elif key in (b"lsct", b"lsdk") and len(data) >= 4:
                    section = struct.unpack(">I", data[:4])[0]
                o += 12 + ln + (ln % 2)
            recs.append(dict(top=top, left=left, bottom=bottom, right=right, chans=chans, opacity=opacity / 255,
                             visible=not (flags & 2), name=name, section=section, blend=blend))
        layers = []
        for r in recs:
            w, h = r["right"] - r["left"], r["bottom"] - r["top"]
            data = {}
            for cid, ln in r["chans"]:
                start = f.tell()
                if w > 0 and h > 0:
                    try:
                        data[cid] = _channel(f, w, h, version)
                    except ValueError:
                        raise
                f.seek(start + ln)
            r["data"] = data
        # groups: section 1/2 = folder start (stored after children, bottom-to-top), 3 = folder end marker
        stack = []
        for r in recs:  # records are bottom-to-top
            if r["section"] == 3:
                stack.append(None)
                continue
            if r["section"] in (1, 2):
                if stack:
                    stack.pop()
                for lay in layers:
                    if lay.group == "\0open":
                        lay.group = r["name"]
                continue
            w, h = r["right"] - r["left"], r["bottom"] - r["top"]
            if w <= 0 or h <= 0:
                continue
            d = r["data"]
            if mode == 3:
                rgb = [d.get(0), d.get(1), d.get(2)]
            else:
                rgb = [d.get(0)] * 3
            if any(c is None for c in rgb):
                continue
            a = d.get(-1, np.full((h, w), 255, np.uint8))
            arr = np.dstack(rgb + [a]).astype(np.uint8).copy()
            img = QImage(arr.data, w, h, w * 4, QImage.Format_RGBA8888).copy()
            lay = PsdLayer(r["name"], r["left"], r["top"],
                           img.convertToFormat(QImage.Format_ARGB32_Premultiplied), r["visible"], r["opacity"],
                           "\0open" if stack else "")
            layers.append(lay)
        for lay in layers:
            if lay.group == "\0open":
                lay.group = ""
        return W, H, layers


def _rgba(img):
    img = img.convertToFormat(QImage.Format_RGBA8888)
    w, h = img.width(), img.height()
    arr = np.frombuffer(img.constBits(), dtype=np.uint8, count=img.bytesPerLine() * h)
    return arr.reshape(h, img.bytesPerLine())[:, :w * 4].reshape(h, w, 4).copy()


def _pascal(name, pad=4):
    b = name.encode("latin-1", "replace")[:255]
    s = bytes([len(b)]) + b
    while len(s) % pad:
        s += b"\0"
    return s


def write_psd(path, width, height, layers, composite=None):
    """layers: [(name, x, y, QImage)] bottom-to-top. Raw (uncompressed) channels, Unicode names."""
    recs = b""
    chan_data = b""
    for name, x, y, img in layers:
        a = _rgba(img)
        h, w = a.shape[:2]
        uname = name.encode("utf-16-be")
        luni = struct.pack(">I", len(name)) + uname
        if len(luni) % 2:
            luni += b"\0"
        extra = struct.pack(">I", 0) + struct.pack(">I", 0) + _pascal(name) + b"8BIMluni" + struct.pack(">I", len(luni)) + luni
        rec = struct.pack(">iiiiH", y, x, y + h, x + w, 4)
        for cid in (-1, 0, 1, 2):
            rec += struct.pack(">hI", cid, 2 + w * h)
        rec += b"8BIMnorm" + struct.pack(">BBBB", 255, 0, 8, 0) + struct.pack(">I", len(extra)) + extra
        recs += rec
        for idx in (3, 0, 1, 2):
            chan_data += struct.pack(">H", 0) + a[:, :, idx].tobytes()
    layer_info = struct.pack(">h", len(layers)) + recs + chan_data
    if len(layer_info) % 2:
        layer_info += b"\0"
    layer_info = struct.pack(">I", len(layer_info)) + layer_info
    lm = layer_info + struct.pack(">I", 0)
    with open(path, "wb") as f:
        f.write(b"8BPS" + struct.pack(">H", 1) + b"\0" * 6 + struct.pack(">HIIHH", 4, height, width, 8, 3))
        f.write(struct.pack(">I", 0) + struct.pack(">I", 0))
        f.write(struct.pack(">I", len(lm)) + lm)
        comp = np.zeros((height, width, 4), np.uint8)
        if composite is not None:
            comp = _rgba(composite.scaled(width, height))
        f.write(struct.pack(">H", 0))
        for idx in (0, 1, 2, 3):
            f.write(comp[:, :, idx].tobytes())


def export_model_psd(model, path):
    """One PSD layer per art mesh at its rest position, in draw order (for Cubism Editor)."""
    from .render import Renderer
    layers = []
    for mesh in sorted(model.meshes(), key=lambda m: m.order):
        img = model.textures.get(mesh.texture)
        if img is None or not len(mesh.rest):
            continue
        # rest position of the texture's top-left corner
        u0 = mesh.uvs[:, 0].argmin()
        v0 = mesh.uvs[:, 1].argmin()
        sx = (mesh.rest[:, 0].max() - mesh.rest[:, 0].min()) / max(1e-6, (mesh.uvs[:, 0].max() - mesh.uvs[:, 0].min())
                                                                   * img.width())
        x = mesh.rest[u0, 0] - mesh.uvs[u0, 0] * img.width() * sx
        y = mesh.rest[v0, 1] - mesh.uvs[v0, 1] * img.height() * sx
        layers.append((mesh.name, int(round(x)), int(round(y)), img))
    comp = Renderer(model).render_image(model.evaluate({p.id: p.default for p in model.params}))
    write_psd(path, model.width, model.height, layers, comp)
    return len(layers)
