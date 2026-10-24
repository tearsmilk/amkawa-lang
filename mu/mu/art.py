"""Artwork operations: turning pictures into layers (art meshes) and cutting a picture into parts — selections
(lasso, polygon, brush, magic wand), «cut to new layer» with automatic filling of the hole left behind
(push-pull inpainting), PNG / JPG / PSD import."""
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QTransform

from .mesh import alpha_of, auto_mesh
from .model import ArtMesh, Model, new_id

DEFAULT_SPACING = 48


# ====================================================================== numpy ↔ QImage
def to_rgba(img):
    """QImage → (H, W, 4) uint8 straight (non-premultiplied) RGBA copy."""
    img = img.convertToFormat(QImage.Format_RGBA8888)
    w, h = img.width(), img.height()
    arr = np.frombuffer(img.constBits(), dtype=np.uint8, count=img.bytesPerLine() * h)
    return arr.reshape(h, img.bytesPerLine())[:, :w * 4].reshape(h, w, 4).copy()


def from_rgba(arr):
    arr = np.ascontiguousarray(arr, dtype=np.uint8)
    h, w = arr.shape[:2]
    img = QImage(arr.data, w, h, w * 4, QImage.Format_RGBA8888).copy()
    return img.convertToFormat(QImage.Format_ARGB32_Premultiplied)


def mask_from_qimage(img):
    return alpha_of(img) > 127


def qimage_from_mask(mask):
    h, w = mask.shape
    a = np.zeros((h, w, 4), np.uint8)
    a[mask] = (255, 255, 255, 255)
    return from_rgba(a)


# ====================================================================== layers ↔ meshes
def placement(mesh, img=None):
    """Affine map (QTransform) texture pixels → rest canvas coordinates, fitted from the mesh's UVs."""
    if img is None:
        return QTransform()
    tw, th = img.width(), img.height()
    U = np.c_[mesh.uvs[:, 0] * tw, mesh.uvs[:, 1] * th, np.ones(len(mesh.uvs))]
    if len(U) < 3:
        return QTransform()
    sol, *_ = np.linalg.lstsq(U, mesh.rest, rcond=None)  # (3, 2)
    a, b = sol[0], sol[1]
    t = sol[2]
    return QTransform(a[0], a[1], b[0], b[1], t[0], t[1])


def add_layer(model, name, img, x, y, parent=None, order=None, spacing=DEFAULT_SPACING, role=""):
    """New art mesh from an image placed with its top-left corner at canvas (x, y)."""
    img = img.convertToFormat(QImage.Format_ARGB32_Premultiplied)
    tid = new_id("t")
    model.textures[tid] = img
    pts, tris = auto_mesh(alpha_of(img), spacing=spacing, margin=3)
    if order is None:
        order = (max([m.order for m in model.meshes()] or [0]) + 10)
    m = ArtMesh(name=name, parent=parent, texture=tid, rest=pts + [x, y],
                uvs=pts / [max(1, img.width()), max(1, img.height())], tris=tris, order=order)
    m.role = role
    model.add(m)
    return m


def remesh(model, mesh, spacing=DEFAULT_SPACING):
    """Rebuild a mesh from its texture's alpha (keeps keyforms by re-sampling them)."""
    from .model import transfer_offsets
    img = model.textures.get(mesh.texture)
    if img is None:
        return
    T = placement(mesh, img)
    pts, tris = auto_mesh(alpha_of(img), spacing=spacing, margin=3)
    new_rest = np.array([[T.map(QPointF(x, y)).x(), T.map(QPointF(x, y)).y()] for x, y in pts]).reshape(-1, 2)
    for b in mesh.bindings:
        for f in b.forms:
            if f.get("offsets") is not None and len(f["offsets"]) == len(mesh.rest):
                f["offsets"] = transfer_offsets(mesh.rest, mesh.tris, f["offsets"], new_rest)
    mesh.rest = new_rest
    mesh.uvs = pts / [max(1, img.width()), max(1, img.height())]
    mesh.tris = tris


def new_model_from_image(img, name="Модель"):
    m = Model(name, img.width(), img.height())
    add_layer(m, "Картинка", img, 0, 0, order=0)
    return m


def new_model_from_psd(path, name=None):
    from pathlib import Path

    from .psd import read_psd
    W, H, layers = read_psd(path)
    m = Model(name or Path(path).stem, W, H)
    order = 0
    for lay in layers:
        if lay.image.isNull() or lay.image.width() < 1:
            continue
        nm = (lay.group + " / " if lay.group else "") + lay.name
        mesh = add_layer(m, nm, lay.image, lay.x, lay.y, order=order)
        mesh.visible = lay.visible
        mesh.opacity = lay.opacity
        order += 10
    if not m.meshes():
        raise ValueError("В PSD нет растровых слоёв")
    from .autorig import guess_roles
    guess_roles(m)
    return m


# ====================================================================== selections (texture pixel space)
def canvas_path_to_mask(mesh, img, path):
    """Rasterise a canvas-space QPainterPath into a bool mask in the mesh texture's pixel space."""
    T = placement(mesh, img)
    inv, ok = T.inverted()
    tex_path = inv.map(path)
    q = QImage(img.width(), img.height(), QImage.Format_ARGB32_Premultiplied)
    q.fill(Qt.transparent)
    p = QPainter(q)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.fillPath(tex_path, QColor(255, 255, 255))
    p.end()
    return mask_from_qimage(q)


def brush_mask(mesh, img, points, radius):
    """Mask of a brush stroke (canvas points + radius in canvas px)."""
    path = QPainterPath()
    for x, y in points:
        path.addEllipse(QPointF(x, y), radius, radius)
    return canvas_path_to_mask(mesh, img, path.simplified())


def magic_wand(img, seed_xy, tolerance=32, contiguous=True):
    """Pixels similar in colour (and alpha) to the seed; flood fill when contiguous."""
    a = to_rgba(img).astype(np.int16)
    h, w = a.shape[:2]
    x, y = int(seed_xy[0]), int(seed_xy[1])
    if not (0 <= x < w and 0 <= y < h):
        return np.zeros((h, w), bool)
    ref = a[y, x]
    diff = np.abs(a - ref).max(axis=2)
    similar = diff <= tolerance
    if not contiguous:
        return similar
    out = np.zeros((h, w), bool)
    stack = [(x, y)]
    while stack:
        cx, cy = stack.pop()
        if not similar[cy, cx] or out[cy, cx]:
            continue
        # scanline fill
        x0 = cx
        while x0 > 0 and similar[cy, x0 - 1] and not out[cy, x0 - 1]:
            x0 -= 1
        x1 = cx
        while x1 < w - 1 and similar[cy, x1 + 1] and not out[cy, x1 + 1]:
            x1 += 1
        out[cy, x0:x1 + 1] = True
        for ny in (cy - 1, cy + 1):
            if 0 <= ny < h:
                row = similar[ny, x0:x1 + 1] & ~out[ny, x0:x1 + 1]
                if row.any():
                    xs = np.nonzero(row)[0] + x0
                    # one seed per run
                    starts = xs[np.r_[True, np.diff(xs) > 1]]
                    stack.extend((int(sx), ny) for sx in starts)
    return out


def combine(old, new, mode):
    if old is None or mode == "replace":
        return new.copy()
    if mode == "add":
        return old | new
    if mode == "subtract":
        return old & ~new
    if mode == "intersect":
        return old & new
    return new.copy()


def grow(mask, r=1):
    from .mesh import dilate
    return dilate(mask, r)


# ====================================================================== inpainting
def inpaint(rgba, hole, known=None):
    """Fill `hole` pixels from their surroundings (push-pull pyramid on premultiplied colour)."""
    if not hole.any():
        return rgba
    a = rgba.astype(np.float32) / 255.0
    alpha = a[:, :, 3:4]
    pre = np.concatenate([a[:, :, :3] * alpha, alpha], axis=2)
    known = (alpha[:, :, 0] > 0.02) & ~hole if known is None else known & ~hole
    w = known.astype(np.float32)[:, :, None]
    levels = []
    cur_c, cur_w = pre * w, w.copy()
    while min(cur_c.shape[:2]) > 1:
        levels.append((cur_c, cur_w))
        h2, w2 = (cur_c.shape[0] + 1) // 2, (cur_c.shape[1] + 1) // 2
        pc = np.zeros((h2 * 2, w2 * 2, 4), np.float32)
        pw = np.zeros((h2 * 2, w2 * 2, 1), np.float32)
        pc[:cur_c.shape[0], :cur_c.shape[1]] = cur_c
        pw[:cur_w.shape[0], :cur_w.shape[1]] = cur_w
        cur_c = pc.reshape(h2, 2, w2, 2, 4).sum(axis=(1, 3))
        cur_w = pw.reshape(h2, 2, w2, 2, 1).sum(axis=(1, 3))
    levels.append((cur_c, cur_w))
    # pull back up: unknown pixels take the (normalised) coarser estimate, upsampled smoothly — a plain 2×
    # repeat leaves a visible mosaic of blocks
    est = levels[-1][0] / np.maximum(levels[-1][1], 1e-6)
    for c, wt in reversed(levels[:-1]):
        up = _blur3(np.repeat(np.repeat(est, 2, axis=0), 2, axis=1)[:c.shape[0], :c.shape[1]])
        local = c / np.maximum(wt, 1e-6)
        k = np.clip(wt, 0, 1)
        est = local * k + up * (1 - k)
    est = _relax(est, pre, hole, known)
    out_pre = est
    res = a.copy()
    fill_alpha = np.clip(out_pre[:, :, 3], 0, 1)
    rgb = out_pre[:, :, :3] / np.maximum(fill_alpha[:, :, None], 1e-6)
    res[hole, :3] = np.clip(rgb[hole], 0, 1)
    res[hole, 3] = 1.0  # the hole was opaque artwork: keep the silhouette solid
    return (res * 255 + 0.5).astype(np.uint8)


def _blur3(x):
    """3×3 box blur with edge padding (H, W, C)."""
    p = np.pad(x, ((1, 1), (1, 1), (0, 0)), mode="edge")
    v = p[:-2] + p[1:-1] + p[2:]
    return (v[:, :-2] + v[:, 1:-1] + v[:, 2:]) / 9.0


def _relax(est, pre, hole, known, iters=60):
    """Membrane smoothing of the filled pixels (known pixels fixed) — removes the last pyramid seams."""
    ys, xs = np.nonzero(hole)
    if not len(ys):
        return est
    y0, y1 = max(0, ys.min() - 2), min(hole.shape[0], ys.max() + 3)
    x0, x1 = max(0, xs.min() - 2), min(hole.shape[1], xs.max() + 3)
    e = est[y0:y1, x0:x1].copy()
    kn = known[y0:y1, x0:x1]
    e[kn] = pre[y0:y1, x0:x1][kn]
    h = hole[y0:y1, x0:x1]
    for _ in range(iters):
        p = np.pad(e, ((1, 1), (1, 1), (0, 0)), mode="edge")
        avg = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) * 0.25
        e[h] = avg[h]
    out = est.copy()
    out[y0:y1, x0:x1][h] = e[h]
    return out


# ====================================================================== cutting
def cut_to_layer(model, mesh, mask, name, fill_hole=True, copy=False, spacing=DEFAULT_SPACING, role=""):
    """Move (or copy) the selected pixels of `mesh` into a new layer placed exactly on top."""
    img = model.textures[mesh.texture]
    src = to_rgba(img)
    sel = mask & (src[:, :, 3] > 0)
    if not sel.any():
        return None
    ys, xs = np.nonzero(sel)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    piece = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
    region = sel[y0:y1, x0:x1]
    piece[region] = src[y0:y1, x0:x1][region]
    T = placement(mesh, img)
    if not copy:
        rest = src.copy()
        if fill_hole:
            # repaint a thin ring too: the anti-aliased edge of the cut outline would otherwise stay behind as
            # a dark ghost line when the new layer moves
            hole = grow(sel, 2) & (src[:, :, 3] > 0)
            rest = inpaint(rest, hole)
            rest[hole & ~sel, 3] = src[hole & ~sel, 3]
        else:
            rest[sel] = 0
        # a new texture id (the old image stays for undo)
        rid = new_id("t")
        model.textures[rid] = from_rgba(rest)
        mesh.texture = rid
        remesh(model, mesh, spacing)
    # the new layer keeps the source texture's pixel scale / placement
    tid = new_id("t")
    model.textures[tid] = from_rgba(piece)
    pts, tris = auto_mesh(alpha_of(model.textures[tid]), spacing=spacing, margin=3)
    rest_pts = []
    for x, y in pts:
        q = T.map(QPointF(x + x0, y + y0))
        rest_pts.append((q.x(), q.y()))
    for m in model.meshes():  # make room in the draw order right above the source
        if m.order > mesh.order:
            m.order += 1
    new = ArtMesh(name=name, parent=mesh.parent, texture=tid, rest=np.array(rest_pts),
                  uvs=pts / [max(1, piece.shape[1]), max(1, piece.shape[0])], tris=tris, order=mesh.order + 1)
    new.role = role
    model.add(new)
    return new


def merge_down(model, upper, lower):
    """Paint `upper` into `lower`'s texture (both at rest) and delete `upper`."""
    li = model.textures[lower.texture]
    ui = model.textures[upper.texture]
    Tl = placement(lower, li)
    Tu = placement(upper, ui)
    inv, _ = Tl.inverted()
    # grow the lower texture to fit both
    corners = [Tu.map(QPointF(0, 0)), Tu.map(QPointF(ui.width(), ui.height())),
               Tl.map(QPointF(0, 0)), Tl.map(QPointF(li.width(), li.height()))]
    tc = [inv.map(c) for c in corners]
    x0 = min(c.x() for c in tc)
    y0 = min(c.y() for c in tc)
    x1 = max(c.x() for c in tc)
    y1 = max(c.y() for c in tc)
    out = QImage(int(np.ceil(x1 - x0)), int(np.ceil(y1 - y0)), QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QPointF(-x0, -y0), li)
    p.setTransform(Tu * inv * QTransform.fromTranslate(-x0, -y0))
    p.drawImage(0, 0, ui)
    p.end()
    lower.texture = new_id("t")
    model.textures[lower.texture] = out
    # placement of the grown texture: same scale, shifted origin
    shift = Tl.map(QPointF(x0, y0)) - Tl.map(QPointF(0, 0))
    pts, tris = auto_mesh(alpha_of(out), spacing=DEFAULT_SPACING, margin=3)
    lower.rest = np.array([[Tl.map(QPointF(x, y)).x() + shift.x(), Tl.map(QPointF(x, y)).y() + shift.y()]
                           for x, y in pts]).reshape(-1, 2)
    lower.uvs = pts / [out.width(), out.height()]
    lower.tris = tris
    for b in lower.bindings:
        for f in b.forms:
            if f.get("offsets") is not None:
                f["offsets"] = np.zeros((len(lower.rest), 2))
    model.remove(upper.id)


def flip_copy(model, mesh, axis_x):
    """Mirrored copy of a layer around the vertical line x = axis_x (for the other eye / ear …)."""
    img = model.textures[mesh.texture]
    tid = new_id("t")
    model.textures[tid] = img.mirrored(True, False)
    new = ArtMesh(name=mesh.name + " (зеркало)", parent=mesh.parent, texture=tid,
                  rest=np.c_[2 * axis_x - mesh.rest[:, 0], mesh.rest[:, 1]],
                  uvs=np.c_[1 - mesh.uvs[:, 0], mesh.uvs[:, 1]], tris=mesh.tris[:, ::-1].copy(), order=mesh.order + 1)
    model.add(new)
    return new


def rest_bounds(mesh):
    if not len(mesh.rest):
        return QRectF()
    lo, hi = mesh.rest.min(0), mesh.rest.max(0)
    return QRectF(lo[0], lo[1], hi[0] - lo[0], hi[1] - lo[1])
