"""Aseprite (.ase / .aseprite) files — read (RGBA, grayscale, indexed; linked cels; tags; palettes)
and write (RGBA), following https://github.com/aseprite/aseprite/blob/main/docs/ase-file-specs.md"""
import struct
import zlib

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPainter

from .model import FMT, Layer, Sprite, Tag, blank, content_rect

MAGIC = 0xA5E0
FRAME_MAGIC = 0xF1FA


class _Reader:
    def __init__(self, data, pos=0):
        self.d, self.p = data, pos

    def take(self, fmt):
        vals = struct.unpack_from("<" + fmt, self.d, self.p)
        self.p += struct.calcsize("<" + fmt)
        return vals if len(vals) > 1 else vals[0]

    def string(self):
        n = self.take("H")
        s = self.d[self.p:self.p + n].decode("utf-8", "replace")
        self.p += n
        return s

    def skip(self, n):
        self.p += n


def _pixels_to_image(raw, w, h, depth, palette, transparent_index, is_background):
    if depth == 32:
        img = QImage(raw[: w * h * 4], w, h, w * 4, QImage.Format_RGBA8888).copy()
        return img.convertToFormat(FMT)
    out = bytearray(w * h * 4)
    if depth == 16:
        for i in range(w * h):
            v, a = raw[i * 2], raw[i * 2 + 1]
            out[i * 4:i * 4 + 4] = bytes((v, v, v, a))
    else:  # indexed
        for i in range(w * h):
            idx = raw[i]
            if idx == transparent_index and not is_background:
                continue
            c = palette[idx] if idx < len(palette) else 0xFF000000
            out[i * 4:i * 4 + 4] = bytes(((c >> 16) & 255, (c >> 8) & 255, c & 255, (c >> 24) & 255))
    return QImage(bytes(out), w, h, w * 4, QImage.Format_RGBA8888).copy().convertToFormat(FMT)


def load(path):
    data = open(path, "rb").read()
    r = _Reader(data)
    (_size, magic, frames, width, height, depth, flags, speed, _z1, _z2, transparent_index) = r.take("IHHHHHIHIIB")
    if magic != MAGIC:
        raise ValueError("Это не файл Aseprite")
    r.skip(3)
    r.take("H")  # number of colors
    r.skip(2)    # pixel ratio
    gx, gy, gw, gh = r.take("hhHH")
    r.p = 128
    sprite = Sprite(width, height)
    sprite.layers = []
    sprite.durations = []
    if gw and gh:
        sprite.grid = QRect(gx, gy, gw, gh)
    layer_map = []          # file layer index → Layer or None (groups / tilemaps)
    backgrounds = set()
    palette = []
    have_new_palette = False
    tag_list = []
    expect_tag_data = False   # user data chunks right after a tags chunk belong to the tags
    tag_user_index = 0
    for frame in range(frames):
        start = r.p
        fsize, fmagic, old_chunks, duration = r.take("IHHH")
        r.skip(2)
        new_chunks = r.take("I")
        if fmagic != FRAME_MAGIC:
            raise ValueError("Повреждённый кадр в файле Aseprite")
        nchunks = new_chunks or old_chunks
        sprite.durations.append(duration or speed or 100)
        for _ in range(nchunks):
            cstart = r.p
            csize, ctype = r.take("IH")
            body = _Reader(data, r.p)
            if ctype == 0x2004:  # layer
                lflags, ltype, _child, _dw, _dh, blend, opacity = body.take("HHHHHHB")
                body.skip(3)
                name = body.string()
                if ltype == 0:
                    layer = Layer(name, bool(lflags & 1), not (lflags & 2), opacity if flags & 1 else 255, blend)
                    sprite.layers.append(layer)
                    layer_map.append(layer)
                    if lflags & 8:
                        backgrounds.add(layer.id)
                else:
                    layer_map.append(None)
            elif ctype == 0x2005:  # cel
                lidx, x, y, opacity, ctype2, _z = body.take("HhhBHh")
                body.skip(5)
                layer = layer_map[lidx] if lidx < len(layer_map) else None
                if layer is not None:
                    piece = None
                    if ctype2 in (0, 2):
                        w, h = body.take("HH")
                        raw = data[body.p:cstart + csize]
                        if ctype2 == 2:
                            raw = zlib.decompress(raw)
                        piece = _pixels_to_image(raw, w, h, depth, palette, transparent_index, layer.id in backgrounds)
                        full = blank(width, height)
                        p = QPainter(full)
                        p.setOpacity(opacity / 255.0)
                        p.drawImage(x, y, piece)
                        p.end()
                        sprite.cels[(layer.id, frame)] = full
                    elif ctype2 == 1:
                        src = body.take("H")
                        img = sprite.cels.get((layer.id, src))
                        if img is not None:
                            sprite.cels[(layer.id, frame)] = QImage(img)
            elif ctype == 0x2019:  # palette
                size, first, last = body.take("III")
                body.skip(8)
                if len(palette) < size:
                    palette += [0xFF000000] * (size - len(palette))
                for i in range(first, last + 1):
                    eflags, rr, gg, bb, aa = body.take("HBBBB")
                    if eflags & 1:
                        body.string()
                    palette[i] = (aa << 24) | (rr << 16) | (gg << 8) | bb
                have_new_palette = True
            elif ctype in (0x0004, 0x0011) and not have_new_palette:
                packets = body.take("H")
                idx = 0
                for _p in range(packets):
                    skip, count = body.take("BB")
                    idx += skip
                    count = count or 256
                    for _c in range(count):
                        rr, gg, bb = body.take("BBB")
                        if ctype == 0x0011:
                            rr, gg, bb = rr * 255 // 63, gg * 255 // 63, bb * 255 // 63
                        while len(palette) <= idx:
                            palette.append(0xFF000000)
                        palette[idx] = 0xFF000000 | (rr << 16) | (gg << 8) | bb
                        idx += 1
            elif ctype == 0x2018:  # tags
                n = body.take("H")
                body.skip(8)
                for _t in range(n):
                    f0, f1, direction = body.take("HHB")
                    body.take("H")
                    body.skip(6)
                    rr, gg, bb = body.take("BBB")
                    body.skip(1)
                    name = body.string()
                    tag_list.append(Tag(name, f0, f1, direction if direction < 4 else 0, QColor(rr, gg, bb).name()))
                tag_user_index = len(tag_list) - n
            elif ctype == 0x2020 and expect_tag_data and tag_user_index < len(tag_list):
                uflags = body.take("I")
                if uflags & 1:
                    body.string()
                if uflags & 2:
                    rr, gg, bb, _aa = body.take("BBBB")
                    tag_list[tag_user_index].color = QColor(rr, gg, bb).name()
                tag_user_index += 1
            if ctype != 0x2020:
                expect_tag_data = ctype == 0x2018
            r.p = cstart + csize
        r.p = start + fsize
    if not sprite.layers:
        sprite.layers = [Layer("Слой 1")]
    if not sprite.durations:
        sprite.durations = [100]
    sprite.tags = [t for t in tag_list if t.start < sprite.frames]
    for t in sprite.tags:
        t.end = min(t.end, sprite.frames - 1)
    sprite.palette = palette
    return sprite


# ---------------------------------------------------------------------- writing
def _string(s):
    b = s.encode("utf-8")
    return struct.pack("<H", len(b)) + b


def _chunk(ctype, body):
    return struct.pack("<IH", len(body) + 6, ctype) + body


def _cel_chunk(layer_index, img):
    rect = content_rect(img)
    if rect.isEmpty():
        return None
    piece = img.copy(rect).convertToFormat(QImage.Format_RGBA8888)
    w, h = piece.width(), piece.height()
    raw = bytes(piece.constBits())[: w * h * 4]
    body = struct.pack("<HhhBHh5x", layer_index, rect.x(), rect.y(), 255, 2, 0)
    body += struct.pack("<HH", w, h) + zlib.compress(raw, 6)
    return _chunk(0x2005, body)


def save(sprite, path):
    frames_data = []
    for f in range(sprite.frames):
        chunks = []
        if f == 0:
            pal = sprite.palette or [0xFF000000]
            body = struct.pack("<III8x", len(pal), 0, len(pal) - 1)
            for c in pal:
                body += struct.pack("<HBBBB", 0, (c >> 16) & 255, (c >> 8) & 255, c & 255, (c >> 24) & 255)
            chunks.append(_chunk(0x2019, body))
            for layer in sprite.layers:
                lflags = (1 if layer.visible else 0) | (0 if layer.locked else 2)
                body = struct.pack("<HHHHHHB3x", lflags, 0, 0, 0, 0, layer.blend, layer.opacity) + _string(layer.name)
                chunks.append(_chunk(0x2004, body))
            if sprite.tags:
                body = struct.pack("<H8x", len(sprite.tags))
                for t in sprite.tags:
                    c = QColor(t.color)
                    body += struct.pack("<HHBH6xBBBx", t.start, t.end, t.direction, 0, c.red(), c.green(), c.blue())
                    body += _string(t.name)
                chunks.append(_chunk(0x2018, body))
                for t in sprite.tags:
                    c = QColor(t.color)
                    chunks.append(_chunk(0x2020, struct.pack("<IBBBB", 2, c.red(), c.green(), c.blue(), 255)))
        for i, layer in enumerate(sprite.layers):
            img = sprite.cel(layer, f)
            if img is not None:
                ch = _cel_chunk(i, img)
                if ch:
                    chunks.append(ch)
        body = b"".join(chunks)
        header = struct.pack("<IHHH2xI", 16 + len(body), FRAME_MAGIC, min(len(chunks), 0xFFFF),
                             int(sprite.durations[f]), len(chunks))
        frames_data.append(header + body)
    frames_blob = b"".join(frames_data)
    g = sprite.grid
    header = struct.pack("<IHHHHHIHIIB3xHBBhhHH", 128 + len(frames_blob), MAGIC, sprite.frames, sprite.width, sprite.height,
                         32, 1, 100, 0, 0, 0, min(len(sprite.palette), 0xFFFF), 1, 1, g.x(), g.y(), g.width(), g.height())
    header += b"\0" * (128 - len(header))
    tmp = str(path) + ".zeta-tmp"
    with open(tmp, "wb") as fh:
        fh.write(header + frames_blob)
    import os

    os.replace(tmp, path)
