"""Image operations on numpy arrays: adjustments, blur / sharpen, flood fill masks, screentone, colour
quantisation (for GIF). Arrays are H×W×4 uint8 in B, G, R, A order (QImage ARGB32 memory layout, not
premultiplied)."""
import math

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBitmap, QColor, QImage, QPainter, QPainterPath, QRegion

from .model import FMT

ARGB = QImage.Format_ARGB32


# ---------------------------------------------------------------------- conversions
def to_array(img):
    """QImage → H×W×4 uint8 copy (B,G,R,A, straight alpha)."""
    img = img.convertToFormat(ARGB)
    w, h = img.width(), img.height()
    a = np.frombuffer(img.constBits(), np.uint8, count=img.bytesPerLine() * h)
    return a.reshape(h, img.bytesPerLine() // 4, 4)[:, :w].copy()


def from_array(a):
    a = np.ascontiguousarray(a, dtype=np.uint8)
    h, w = a.shape[:2]
    img = QImage(a.data, w, h, w * 4, ARGB)
    return img.copy().convertToFormat(FMT)


def masked_apply(img, fn, clip=None):
    """Apply fn(array) → array to an image, only inside `clip` (QPainterPath) if given."""
    out = from_array(fn(to_array(img)))
    if clip is None or clip.isEmpty():
        return out
    res = img.copy()
    p = QPainter(res)
    p.setClipPath(clip)
    p.setCompositionMode(QPainter.CompositionMode_Source)
    p.drawImage(0, 0, out)
    p.end()
    return res


# ---------------------------------------------------------------------- adjustments
def brightness_contrast(a, brightness=0, contrast=0):
    """brightness, contrast in -100..100."""
    rgb = a[..., :3].astype(np.float32)
    rgb += brightness * 2.55
    c = (contrast + 100) / 100.0
    c = c * c
    rgb = (rgb - 127.5) * c + 127.5
    out = a.copy()
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    return out


def _rgb_to_hsl(r, g, b):
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    l = (mx + mn) / 2
    d = mx - mn
    s = np.where(d == 0, 0, d / np.maximum(1e-6, 1 - np.abs(2 * l - 1)))
    h = np.zeros_like(l)
    nz = d > 1e-6
    rc = np.where(nz, ((g - b) / np.maximum(d, 1e-6)) % 6, 0)
    gc = np.where(nz, (b - r) / np.maximum(d, 1e-6) + 2, 0)
    bc = np.where(nz, (r - g) / np.maximum(d, 1e-6) + 4, 0)
    h = np.where(mx == r, rc, np.where(mx == g, gc, bc)) * 60
    h = np.where(nz, h, 0)
    return h % 360, np.clip(s, 0, 1), l


def _hsl_to_rgb(h, s, l):
    c = (1 - np.abs(2 * l - 1)) * s
    x = c * (1 - np.abs((h / 60) % 2 - 1))
    m = l - c / 2
    z = np.zeros_like(h)
    seg = (h // 60).astype(np.int32) % 6
    r = np.choose(seg, [c, x, z, z, x, c])
    g = np.choose(seg, [x, c, c, x, z, z])
    b = np.choose(seg, [z, z, x, c, c, x])
    return r + m, g + m, b + m


def hue_saturation(a, hue=0, saturation=0, lightness=0, colorize=False):
    """hue -180..180, saturation / lightness -100..100."""
    b, g, r = (a[..., i].astype(np.float32) / 255 for i in range(3))
    h, s, l = _rgb_to_hsl(r, g, b)
    if colorize:
        h = np.full_like(h, (hue % 360))
        s = np.full_like(s, max(0.0, min(1.0, 0.5 + saturation / 200)))
    else:
        h = (h + hue) % 360
        s = np.clip(s * (1 + saturation / 100), 0, 1)
    if lightness > 0:
        l = l + (1 - l) * lightness / 100
    else:
        l = l * (1 + lightness / 100)
    r, g, b = _hsl_to_rgb(h, s, np.clip(l, 0, 1))
    out = a.copy()
    out[..., 0] = np.clip(b * 255, 0, 255)
    out[..., 1] = np.clip(g * 255, 0, 255)
    out[..., 2] = np.clip(r * 255, 0, 255)
    return out


def levels(a, black=0, white=255, gamma=1.0):
    rgb = a[..., :3].astype(np.float32)
    rgb = np.clip((rgb - black) / max(1, white - black), 0, 1) ** (1 / max(0.05, gamma))
    out = a.copy()
    out[..., :3] = (rgb * 255).astype(np.uint8)
    return out


def grayscale(a):
    b, g, r = a[..., 0].astype(np.float32), a[..., 1].astype(np.float32), a[..., 2].astype(np.float32)
    y = np.clip(0.299 * r + 0.587 * g + 0.114 * b, 0, 255).astype(np.uint8)
    out = a.copy()
    out[..., 0] = out[..., 1] = out[..., 2] = y
    return out


def invert(a):
    out = a.copy()
    out[..., :3] = 255 - out[..., :3]
    return out


def posterize(a, levels_n=4):
    n = max(2, int(levels_n))
    out = a.copy()
    q = np.round(out[..., :3].astype(np.float32) / 255 * (n - 1)) / (n - 1) * 255
    out[..., :3] = q.astype(np.uint8)
    return out


def threshold(a, level=128):
    """Black / white line art (keeps alpha)."""
    y = grayscale(a)[..., 0]
    v = np.where(y >= level, 255, 0).astype(np.uint8)
    out = a.copy()
    out[..., 0] = out[..., 1] = out[..., 2] = v
    return out


def _box_blur_axis(x, r, axis):
    if r <= 0:
        return x
    pad = [(0, 0)] * x.ndim
    pad[axis] = (r + 1, r)
    xp = np.pad(x, pad, mode="edge")
    c = np.cumsum(xp, axis=axis, dtype=np.float32)
    n = x.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return (hi - lo) / (2 * r + 1)


def gaussian_blur(a, radius):
    """Three box blurs ≈ gaussian, on premultiplied colour (no dark halos at transparent edges)."""
    if radius <= 0:
        return a
    f = a.astype(np.float32)
    alpha = f[..., 3:4] / 255
    f[..., :3] *= alpha
    r = max(1, int(round(radius / 1.7)))
    for _ in range(3):
        f = _box_blur_axis(f, r, 0)
        f = _box_blur_axis(f, r, 1)
    out_a = f[..., 3:4]
    rgb = np.where(out_a > 0.5, f[..., :3] / np.maximum(out_a / 255, 1e-6), 0)
    return np.clip(np.concatenate([rgb, out_a], axis=2), 0, 255).astype(np.uint8)


def sharpen(a, amount=50, radius=2):
    blurred = gaussian_blur(a, radius).astype(np.float32)
    f = a.astype(np.float32)
    rgb = f[..., :3] + (f[..., :3] - blurred[..., :3]) * (amount / 50)
    out = a.copy()
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    return out


def noise(a, amount=10, seed=1):
    rng = np.random.default_rng(seed)
    n = rng.normal(0, amount * 1.2, a.shape[:2] + (1,)).astype(np.float32)
    out = a.copy()
    out[..., :3] = np.clip(a[..., :3].astype(np.float32) + n, 0, 255).astype(np.uint8)
    return out


# ---------------------------------------------------------------------- fill
def similar_mask(a, x, y, tolerance=24):
    """Pixels whose colour+alpha is within `tolerance` of the pixel at (x, y) (uint8 maths, no copies)."""
    ref = a[y, x]
    if ref[3] == 0:
        return a[..., 3] <= tolerance
    if tolerance == 0:
        flat = a.reshape(-1, 4).view(np.uint32).reshape(a.shape[:2])
        return flat == ref.view(np.uint32)[0]
    diff = None
    for c in range(4):
        ch = a[..., c]
        d = np.maximum(ch, ref[c]) - np.minimum(ch, ref[c])
        diff = d if diff is None else np.maximum(diff, d, out=diff)
    return diff <= tolerance


def flood_region(mask, x, y):
    """Connected component of `mask` containing (x, y): scanline fill where every run is found with
    bytes.find (C speed), so even a full A4 page fills in well under a second."""
    h, w = mask.shape
    buf = bytearray(mask.astype(np.uint8).tobytes())   # 1 = fillable and not yet filled
    out = np.zeros((h, w), dtype=bool)
    if not buf[y * w + x]:
        return out
    stack = [(x, y)]
    while stack:
        sx, sy = stack.pop()
        base = sy * w
        if not buf[base + sx]:
            continue
        l = buf.rfind(0, base, base + sx) + 1
        l = max(l, base)
        r = buf.find(0, base + sx, base + w)
        r = base + w if r < 0 else r
        buf[l:r] = bytes(r - l)
        out[sy, l - base:r - base] = True
        for ny in (sy - 1, sy + 1):
            if 0 <= ny < h:
                nb = ny * w
                lo, hi = nb + (l - base), nb + (r - base)
                i = buf.find(1, lo, hi)
                while i >= 0:
                    stack.append((i - nb, ny))
                    j = buf.find(0, i, hi)
                    if j < 0:
                        break
                    i = buf.find(1, j, hi)
    return out


def dilate(mask, px):
    m = mask.copy()
    for _ in range(int(px)):
        n = m.copy()
        n[1:] |= m[:-1]
        n[:-1] |= m[1:]
        n[:, 1:] |= m[:, :-1]
        n[:, :-1] |= m[:, 1:]
        m = n
    return m


def mask_to_image(mask, color):
    h, w = mask.shape
    c = QColor(color)
    a = np.zeros((h, w, 4), np.uint8)
    a[mask] = (c.blue(), c.green(), c.red(), c.alpha())
    return from_array(a)


def mask_to_path(mask):
    """Boolean mask → QPainterPath (via a 1-bit region)."""
    img = from_array(np.dstack([np.zeros(mask.shape, np.uint8)] * 3 + [mask.astype(np.uint8) * 255]))
    region = QRegion(QBitmap.fromImage(img.createAlphaMask()))
    path = QPainterPath()
    path.addRegion(region)
    return path.simplified()


# ---------------------------------------------------------------------- screentone
def screentone_tile(spacing=8, dot=50, angle=45, color="#141413"):
    """A seamless tile of halftone dots; dot = % of each cell covered. angle 45 (classic manga) or 0."""
    p_color = QColor(color)
    if angle == 45:
        a = max(2, int(round(spacing / math.sqrt(2))))   # lattice (a, a), (a, -a): pitch a·√2 ≈ spacing
        cell = 2 * a
        pitch = a * math.sqrt(2)
        centres = [(0, 0), (a, a)]
    else:
        cell = max(3, int(spacing))
        pitch = cell
        centres = [(0, 0)]
    size = cell * 4
    img = QImage(size, size, FMT)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(p_color)
    r = pitch * math.sqrt(max(0.0, min(100, dot)) / 100.0 / math.pi)
    for gy in range(-1, 5):
        for gx in range(-1, 5):
            for cx, cy in centres:
                p.drawEllipse(QPointF(gx * cell + cx, gy * cell + cy), r, r)
    p.end()
    return img


def tone_fill(target, clip, spacing, dot, angle, color):
    """Fill `clip` (QPainterPath, layer coords) of `target` with a halftone pattern."""
    from PySide6.QtGui import QBrush

    out = target.copy()
    tile = screentone_tile(spacing, dot, 45 if angle == 45 else 0, color)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing, False)
    p.setClipPath(clip)
    p.fillRect(out.rect(), QBrush(tile))
    p.end()
    return out


# ---------------------------------------------------------------------- quantisation (GIF)
def median_cut(arrays, colors=255):
    """Palette (list of 0xRRGGBB) for several B,G,R,A arrays."""
    px = np.concatenate([a[a[..., 3] >= 128][:, :3] for a in arrays]) if arrays else np.zeros((0, 3), np.uint8)
    if len(px) == 0:
        return [0]
    if len(px) > 200_000:
        idx = np.random.default_rng(3).choice(len(px), 200_000, replace=False)
        px = px[idx]
    if len(px) > 60_000:
        px = px[np.random.default_rng(3).choice(len(px), 60_000, replace=False)]
    boxes = [px]
    spans = [int(np.ptp(px, axis=0).max())]
    while len(boxes) < colors:
        i = int(np.argmax(spans))
        box = boxes[i]
        if spans[i] <= 0 or len(box) < 2:
            break
        ch = int(np.argmax(np.ptp(box, axis=0)))
        box = box[box[:, ch].argsort()]
        mid = len(box) // 2
        parts = [box[:mid], box[mid:]]
        boxes[i:i + 1] = parts
        spans[i:i + 1] = [int(np.ptp(q, axis=0).max()) if len(q) > 1 else 0 for q in parts]
    pal = []
    for box in boxes:
        b, g, r = box.mean(axis=0).astype(int)
        pal.append((r << 16) | (g << 8) | b)
    return pal


def quantize(a, palette):
    """B,G,R,A array → index array (255 = transparent): nearest palette colour through a 15-bit lookup table."""
    pal = np.array([[(c >> 16) & 255, (c >> 8) & 255, c & 255] for c in palette], np.int32)
    grid = np.arange(32, dtype=np.int32) * 8 + 4
    r, g, b = np.meshgrid(grid, grid, grid, indexing="ij")
    cube = np.stack([r.ravel(), g.ravel(), b.ravel()], axis=1)
    lut = np.empty(len(cube), np.uint8)
    for s0 in range(0, len(cube), 4096):
        d = ((cube[s0:s0 + 4096, None, :] - pal[None, :, :]) ** 2).sum(axis=2)
        lut[s0:s0 + 4096] = d.argmin(axis=1)
    key = ((a[..., 2].astype(np.int32) >> 3) << 10) | ((a[..., 1].astype(np.int32) >> 3) << 5) | (a[..., 0].astype(np.int32) >> 3)
    out = lut[key.reshape(-1)]
    out[a[..., 3].reshape(-1) < 128] = 255
    return out
