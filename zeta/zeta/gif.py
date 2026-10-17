"""Animated GIF writer (no external libraries): global palette, transparency, per-frame delays, looping.

Pixel art rarely has more than 255 colours; if it does, the most frequent ones are kept and the rest
are mapped to the nearest kept colour.
"""
import struct
from collections import Counter


def _rgba(img):
    """QImage → (w, h, list of 0xAARRGGBB ints)."""
    from PySide6.QtGui import QImage

    img = img.convertToFormat(QImage.Format_ARGB32)
    w, h = img.width(), img.height()
    raw = bytes(img.constBits())[: w * h * 4]
    px = list(struct.unpack(f"<{w * h}I", raw))
    return w, h, px


def _palette(frames):
    counts = Counter()
    for _w, _h, px in frames:
        counts.update(p for p in px if (p >> 24) >= 128)
    colors = [c & 0xFFFFFF for c, _n in counts.most_common()]
    colors = list(dict.fromkeys(colors))
    return colors[:255]


def _nearest(c, colors, cache):
    hit = cache.get(c)
    if hit is not None:
        return hit
    r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
    best, bi = None, 0
    for i, k in enumerate(colors):
        d = (r - (k >> 16 & 255)) ** 2 * 3 + (g - (k >> 8 & 255)) ** 2 * 4 + (b - (k & 255)) ** 2 * 2
        if best is None or d < best:
            best, bi = d, i
            if d == 0:
                break
    cache[c] = bi
    return bi


def _lzw(indices, min_code_size):
    """GIF LZW compression → sub-blocks."""
    clear = 1 << min_code_size
    eoi = clear + 1
    out = bytearray()
    bitbuf = 0
    bitcount = 0
    code_size = min_code_size + 1

    def emit(code):
        nonlocal bitbuf, bitcount
        bitbuf |= code << bitcount
        bitcount += code_size
        while bitcount >= 8:
            out.append(bitbuf & 255)
            bitbuf >>= 8
            bitcount -= 8

    table = {(i,): i for i in range(clear)}
    next_code = eoi + 1
    emit(clear)
    prefix = ()
    for idx in indices:
        cand = prefix + (idx,)
        if cand in table:
            prefix = cand
            continue
        emit(table[prefix])
        if next_code < 4096:
            table[cand] = next_code
            next_code += 1
            if next_code > (1 << code_size) and code_size < 12:
                code_size += 1
        else:
            emit(clear)
            table = {(i,): i for i in range(clear)}
            next_code = eoi + 1
            code_size = min_code_size + 1
        prefix = (idx,)
    if prefix:
        emit(table[prefix])
    emit(eoi)
    if bitcount:
        out.append(bitbuf & 255)
    blocks = bytearray()
    for i in range(0, len(out), 255):
        chunk = out[i:i + 255]
        blocks.append(len(chunk))
        blocks += chunk
    blocks.append(0)
    return bytes(blocks)


def save_gif(path, images, durations_ms, loop=0):
    frames = [_rgba(img) for img in images]
    w, h = frames[0][0], frames[0][1]
    colors = _palette(frames)
    has_alpha = any((p >> 24) < 128 for _w, _h, px in frames for p in px)
    table = colors + [0] * (256 - len(colors))
    transparent = len(colors) if has_alpha else None
    size_bits = 7  # 256-colour table
    out = bytearray(b"GIF89a")
    out += struct.pack("<HHBBB", w, h, 0x80 | 0x70 | size_bits, 0, 0)
    for c in table:
        out += bytes(((c >> 16) & 255, (c >> 8) & 255, c & 255))
    out += b"\x21\xFF\x0BNETSCAPE2.0\x03\x01" + struct.pack("<H", loop) + b"\x00"
    cache = {}
    exact = {c: i for i, c in enumerate(colors)}
    for (fw, fh, px), ms in zip(frames, durations_ms):
        indices = []
        for p in px:
            if (p >> 24) < 128:
                indices.append(transparent)
            else:
                c = p & 0xFFFFFF
                i = exact.get(c)
                indices.append(i if i is not None else _nearest(c, colors, cache))
        delay = max(2, round(ms / 10))
        flags = 0x08 | (0x01 if transparent is not None else 0)  # dispose: restore to background
        out += b"\x21\xF9\x04" + struct.pack("<BHB", flags, delay, transparent or 0) + b"\x00"
        out += b"\x2C" + struct.pack("<HHHHB", 0, 0, fw, fh, 0)
        out.append(8)
        out += _lzw(indices, 8)
    out.append(0x3B)
    with open(path, "wb") as fh_:
        fh_.write(out)
