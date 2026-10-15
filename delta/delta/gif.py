"""Animated GIF writer for full-colour art: one median-cut palette (255 colours + transparency) for the whole
animation, LZW-compressed frames, looping."""
import struct

from . import imgops


def _lzw(data, min_code_size=8):
    """GIF LZW: dictionary keyed by (prefix code, next byte) — integer keys keep it fast."""
    clear = 1 << min_code_size
    eoi = clear + 1
    out = bytearray()
    bitbuf = bitcount = 0
    code_size = min_code_size + 1
    table = {}
    next_code = eoi + 1

    bitbuf |= clear << bitcount
    bitcount += code_size
    prefix = -1
    for byte in data:
        if prefix < 0:
            prefix = byte
            continue
        key = (prefix << 8) | byte
        code = table.get(key)
        if code is not None:
            prefix = code
            continue
        bitbuf |= prefix << bitcount
        bitcount += code_size
        while bitcount >= 8:
            out.append(bitbuf & 255)
            bitbuf >>= 8
            bitcount -= 8
        if next_code < 4096:
            table[key] = next_code
            next_code += 1
            if next_code > (1 << code_size) and code_size < 12:
                code_size += 1
        else:
            bitbuf |= clear << bitcount
            bitcount += code_size
            while bitcount >= 8:
                out.append(bitbuf & 255)
                bitbuf >>= 8
                bitcount -= 8
            table = {}
            next_code = eoi + 1
            code_size = min_code_size + 1
        prefix = byte
    if prefix >= 0:
        bitbuf |= prefix << bitcount
        bitcount += code_size
    bitbuf |= eoi << bitcount
    bitcount += code_size
    while bitcount > 0:
        out.append(bitbuf & 255)
        bitbuf >>= 8
        bitcount -= 8
    blocks = bytearray()
    for i in range(0, len(out), 255):
        chunk = out[i:i + 255]
        blocks.append(len(chunk))
        blocks += chunk
    blocks.append(0)
    return bytes(blocks)


def write_gif(path, images, frame_ms, loop=True):
    arrays = [imgops.to_array(img) for img in images]
    palette = imgops.median_cut(arrays[:: max(1, len(arrays) // 12)], 255)
    h, w = arrays[0].shape[:2]
    table = palette + [0] * (256 - len(palette))
    out = bytearray(b"GIF89a")
    out += struct.pack("<HHBBB", w, h, 0xF7, 0, 0)
    for c in table:
        out += bytes(((c >> 16) & 255, (c >> 8) & 255, c & 255))
    if loop:
        out += b"\x21\xFF\x0BNETSCAPE2.0\x03\x01\x00\x00\x00"
    delay = max(2, round(frame_ms / 10))
    for a in arrays:
        idx = imgops.quantize(a, palette)
        out += b"\x21\xF9\x04" + struct.pack("<BHB", 0x09, delay, 255) + b"\x00"
        out += b"\x2C" + struct.pack("<HHHHB", 0, 0, w, h, 0)
        out.append(8)
        out += _lzw(idx.tobytes())
    out.append(0x3B)
    with open(path, "wb") as fh:
        fh.write(out)
