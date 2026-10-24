"""Meshing: Delaunay triangulation (Bowyer–Watson) and automatic meshes from a layer's alpha channel."""
import math

import numpy as np


def delaunay(points):
    """points: (N, 2) → triangles (M, 3) int32 (counter-clockwise not guaranteed)."""
    pts = np.asarray(points, dtype=float)
    n = len(pts)
    if n < 3:
        return np.zeros((0, 3), dtype=np.int32)
    lo = pts.min(0)
    hi = pts.max(0)
    d = max(hi[0] - lo[0], hi[1] - lo[1]) * 10 + 1
    c = (lo + hi) / 2
    sup = np.array([[c[0] - 2 * d, c[1] - d], [c[0] + 2 * d, c[1] - d], [c[0], c[1] + 2 * d]])
    P = np.vstack([pts, sup])
    tris = [(n, n + 1, n + 2)]
    circ = {}

    def circum(t):
        r = circ.get(t)
        if r is None:
            (ax, ay), (bx, by), (cx, cy) = P[t[0]], P[t[1]], P[t[2]]
            dd = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
            if abs(dd) < 1e-12:
                r = (0.0, 0.0, float("inf"))
            else:
                ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / dd
                uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / dd
                r = (ux, uy, (ax - ux) ** 2 + (ay - uy) ** 2)
            circ[t] = r
        return r

    order = np.lexsort((pts[:, 1], pts[:, 0]))
    for i in order:
        px, py = P[i]
        bad = []
        for t in tris:
            ux, uy, r2 = circum(t)
            if (px - ux) ** 2 + (py - uy) ** 2 <= r2 * (1 + 1e-12):
                bad.append(t)
        edges = {}
        for t in bad:
            for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                k = (min(e), max(e))
                edges[k] = edges.get(k, 0) + 1
        bad_set = set(bad)
        tris = [t for t in tris if t not in bad_set]
        for (a, b), cnt in edges.items():
            if cnt == 1:
                tris.append((a, b, int(i)))
    out = [t for t in tris if max(t) < n]
    return np.array(out, dtype=np.int32).reshape(-1, 3)


def dilate(mask, r):
    out = mask.copy()
    for _ in range(int(r)):
        m = out
        out = m.copy()
        out[1:, :] |= m[:-1, :]
        out[:-1, :] |= m[1:, :]
        out[:, 1:] |= m[:, :-1]
        out[:, :-1] |= m[:, 1:]
    return out


def erode(mask, r=1):
    return ~dilate(~mask, r)


def alpha_of(qimage):
    from PySide6.QtGui import QImage
    img = qimage.convertToFormat(QImage.Format_RGBA8888)
    w, h = img.width(), img.height()
    arr = np.frombuffer(img.constBits(), dtype=np.uint8, count=img.bytesPerLine() * h)
    arr = arr.reshape(h, img.bytesPerLine())[:, :w * 4].reshape(h, w, 4)
    return arr[:, :, 3].copy()


def auto_mesh(alpha, spacing=48, margin=4, threshold=8):
    """Mesh covering the opaque area of `alpha` (H, W). Returns (points (N,2) in pixels, tris (M,3))."""
    h, w = alpha.shape
    mask = alpha > threshold
    if not mask.any():
        pts = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=float)
        return pts, np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int32)
    ys, xs = np.nonzero(mask)
    bw, bh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
    spacing = max(6.0, min(float(spacing), min(bw, bh) / 2.5))
    big = dilate(mask, margin)
    edge = big & ~erode(big, 1)
    pts = []
    cell = spacing * 0.7
    taken = {}

    def try_add(x, y, minsep):
        key = (int(x // cell), int(y // cell))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for (qx, qy) in taken.get((key[0] + dx, key[1] + dy), ()):
                    if (qx - x) ** 2 + (qy - y) ** 2 < minsep * minsep:
                        return
        taken.setdefault(key, []).append((x, y))
        pts.append((x, y))
    # boundary points first (they define the silhouette)
    ey, ex = np.nonzero(edge)
    if len(ex):
        order = np.argsort(np.arctan2(ey - ey.mean(), ex - ex.mean()))
        step = max(1, len(order) // 4000)
        for k in order[::step]:
            try_add(float(ex[k]) + 0.5, float(ey[k]) + 0.5, spacing * 0.6)
    # interior grid
    inner = erode(big, max(2, int(spacing * 0.3)))
    y = ys.min() + spacing / 2
    row = 0
    while y < ys.max():
        x = xs.min() + spacing / 2 + (spacing / 2 if row % 2 else 0)
        while x < xs.max():
            xi, yi = int(x), int(y)
            if 0 <= xi < w and 0 <= yi < h and inner[yi, xi]:
                try_add(x, y, spacing * 0.75)
            x += spacing
        y += spacing * 0.87
        row += 1
    pts = np.array(pts, dtype=float)
    if len(pts) < 3:
        x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
        pts = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=float)
        return pts, np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int32)
    tris = delaunay(pts)
    keep = []
    big_d = dilate(big, 2)
    for t in tris:
        a, b, c = pts[t[0]], pts[t[1]], pts[t[2]]
        longest = max(np.hypot(*(a - b)), np.hypot(*(b - c)), np.hypot(*(c - a)))
        if longest > spacing * 2.6:
            # long edges are fine only if they stay inside the shape (convex parts)
            ok = all(_inside(big_d, a + (b - a) * s) and _inside(big_d, b + (c - b) * s) and
                     _inside(big_d, c + (a - c) * s) for s in (0.25, 0.5, 0.75))
            if not ok:
                continue
        cen = (a + b + c) / 3
        if not _inside(big_d, cen):
            continue
        keep.append(t)
    tris = np.array(keep, dtype=np.int32).reshape(-1, 3)
    used = np.unique(tris)
    remap = -np.ones(len(pts), dtype=np.int32)
    remap[used] = np.arange(len(used))
    return pts[used], remap[tris]


def _inside(mask, p):
    x, y = int(p[0]), int(p[1])
    h, w = mask.shape
    return 0 <= x < w and 0 <= y < h and bool(mask[y, x])


def grid_mesh(x, y, w, h, cols, rows):
    """A regular grid mesh (used for simple rectangular parts)."""
    xs = np.linspace(x, x + w, cols + 1)
    ys = np.linspace(y, y + h, rows + 1)
    gx, gy = np.meshgrid(xs, ys)
    pts = np.stack([gx.ravel(), gy.ravel()], axis=1)
    tris = []
    for j in range(rows):
        for i in range(cols):
            a = j * (cols + 1) + i
            b, c, d = a + 1, a + cols + 1, a + cols + 2
            tris += [(a, b, d), (a, d, c)]
    return pts, np.array(tris, dtype=np.int32)


def point_in_tris(p, verts, tris):
    """Index of the first triangle containing p, or -1 (+ barycentric weights)."""
    a = verts[tris[:, 0]]
    b = verts[tris[:, 1]]
    c = verts[tris[:, 2]]
    v0, v1 = b - a, c - a
    v2 = np.asarray(p) - a
    den = v0[:, 0] * v1[:, 1] - v1[:, 0] * v0[:, 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        l1 = (v2[:, 0] * v1[:, 1] - v1[:, 0] * v2[:, 1]) / den
        l2 = (v0[:, 0] * v2[:, 1] - v2[:, 0] * v0[:, 1]) / den
    l0 = 1 - l1 - l2
    inside = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6) & np.isfinite(l1)
    idx = np.nonzero(inside)[0]
    if not len(idx):
        return -1, None
    k = int(idx[0])
    return k, (l0[k], l1[k], l2[k])


def nearest_vertex(p, verts):
    if not len(verts):
        return -1, math.inf
    d = ((verts - np.asarray(p)) ** 2).sum(1)
    k = int(np.argmin(d))
    return k, math.sqrt(d[k])
