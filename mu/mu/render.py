"""Software renderer for the puppet: every triangle is filled with the part texture through an affine brush
transform (QPainter raster engine → bilinear sampling, no seams), clipping masks via offscreen layers,
blend modes, plus editor overlays (wireframes, deformer grids)."""
import numpy as np
from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPolygonF, QTransform

from .model import ArtMesh

BLENDS = {"normal": QPainter.CompositionMode_SourceOver, "add": QPainter.CompositionMode_Plus,
          "multiply": QPainter.CompositionMode_Multiply, "screen": QPainter.CompositionMode_Screen}
BLEND_TITLES = [("normal", "Обычный"), ("add", "Сложение"), ("multiply", "Умножение"), ("screen", "Экран")]


def affines(uv_px, dev, tris):
    """Per-triangle affine maps texture pixels → device: returns (M, 2, 3)."""
    U = np.ones((len(tris), 3, 3))
    U[:, 0, :] = uv_px[tris, 0]
    U[:, 1, :] = uv_px[tris, 1]
    D = np.empty((len(tris), 2, 3))
    D[:, 0, :] = dev[tris, 0]
    D[:, 1, :] = dev[tris, 1]
    det = np.linalg.det(U)
    ok = np.abs(det) > 1e-9
    A = np.zeros((len(tris), 2, 3))
    if ok.any():
        A[ok] = D[ok] @ np.linalg.inv(U[ok])
    return A, ok


class Renderer:
    def __init__(self, model):
        self.model = model
        self.brushes = {}

    def brush(self, tex_id):
        b = self.brushes.get(tex_id)
        if b is None:
            img = self.model.textures.get(tex_id)
            if img is None:
                return None
            b = self.brushes[tex_id] = (QBrush(img), img.width(), img.height())
        return b

    def reset(self):
        self.brushes.clear()

    def draw_mesh(self, p, mesh, verts, T):
        tex = self.brush(mesh.texture)
        if tex is None or not len(mesh.tris):
            return
        brush, tw, th = tex
        dev = np.empty_like(verts)
        dev[:, 0] = T.m11() * verts[:, 0] + T.m21() * verts[:, 1] + T.dx()
        dev[:, 1] = T.m12() * verts[:, 0] + T.m22() * verts[:, 1] + T.dy()
        uv_px = mesh.uvs * (tw, th)
        A, ok = affines(uv_px, dev, mesh.tris)
        p.setPen(Qt.NoPen)
        tris = mesh.tris
        for k in np.nonzero(ok)[0]:
            a = A[k]
            brush.setTransform(QTransform(a[0, 0], a[1, 0], a[0, 1], a[1, 1], a[0, 2], a[1, 2]))
            p.setBrush(brush)
            i, j, l = tris[k]
            p.drawConvexPolygon([QPointF(dev[i, 0], dev[i, 1]), QPointF(dev[j, 0], dev[j, 1]),
                                 QPointF(dev[l, 0], dev[l, 1])])

    def device_rect(self, verts, T, clip):
        if not len(verts):
            return QRect()
        xs = T.m11() * verts[:, 0] + T.m21() * verts[:, 1] + T.dx()
        ys = T.m12() * verts[:, 0] + T.m22() * verts[:, 1] + T.dy()
        r = QRect(int(xs.min()) - 2, int(ys.min()) - 2, int(xs.max() - xs.min()) + 5, int(ys.max() - ys.min()) + 5)
        return r.intersected(clip)

    def render(self, p, frame, T, clip=None, hidden=(), only=None):
        """Draw all meshes of `frame` with canvas→device transform T."""
        model = self.model
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.setRenderHint(QPainter.Antialiasing, False)
        dev_clip = clip or QRect(-100000, -100000, 200000, 200000)
        order = sorted(frame.meshes.items(), key=lambda kv: kv[1][2])
        mask_cache = {}
        for mid, (verts, op, _) in order:
            if mid in hidden or op <= 0.004 or (only is not None and mid not in only):
                continue
            mesh = model.nodes.get(mid)
            if not isinstance(mesh, ArtMesh):
                continue
            masks = [m for m in mesh.masks if m in frame.meshes and m in model.nodes]
            if not masks:
                p.setOpacity(min(1.0, op))
                p.setCompositionMode(BLENDS.get(mesh.blend, QPainter.CompositionMode_SourceOver))
                self.draw_mesh(p, mesh, verts, T)
                continue
            r = self.device_rect(verts, T, dev_clip)
            if r.isEmpty():
                continue
            key = (tuple(masks), mesh.invert_mask)
            ml = mask_cache.get(key)
            if ml is None:
                mr = QRect()
                for m in masks:
                    mr = mr.united(self.device_rect(frame.meshes[m][0], T, dev_clip))
                ml = (QImage(max(1, mr.width()), max(1, mr.height()), QImage.Format_ARGB32_Premultiplied), mr)
                ml[0].fill(Qt.transparent)
                mp = QPainter(ml[0])
                mp.setRenderHint(QPainter.SmoothPixmapTransform, True)
                mt = QTransform(T)
                mt = mt * QTransform.fromTranslate(-mr.x(), -mr.y())
                for m in masks:
                    self.draw_mesh(mp, model.nodes[m], frame.meshes[m][0], mt)
                mp.end()
                mask_cache[key] = ml
            mimg, mr = ml
            layer = QImage(max(1, r.width()), max(1, r.height()), QImage.Format_ARGB32_Premultiplied)
            layer.fill(Qt.transparent)
            lp = QPainter(layer)
            lp.setRenderHint(QPainter.SmoothPixmapTransform, True)
            self.draw_mesh(lp, mesh, verts, T * QTransform.fromTranslate(-r.x(), -r.y()))
            lp.setCompositionMode(QPainter.CompositionMode_DestinationOut if mesh.invert_mask
                                  else QPainter.CompositionMode_DestinationIn)
            if not mesh.invert_mask:
                # pixels of the layer outside the mask image must vanish too
                full = QImage(layer.size(), QImage.Format_ARGB32_Premultiplied)
                full.fill(Qt.transparent)
                fp = QPainter(full)
                fp.drawImage(mr.x() - r.x(), mr.y() - r.y(), mimg)
                fp.end()
                lp.drawImage(0, 0, full)
            else:
                lp.drawImage(mr.x() - r.x(), mr.y() - r.y(), mimg)
            lp.end()
            p.setOpacity(min(1.0, op))
            p.setCompositionMode(BLENDS.get(mesh.blend, QPainter.CompositionMode_SourceOver))
            p.drawImage(r.x(), r.y(), layer)
        p.restore()

    def render_image(self, frame, scale=1.0, background=None, size=None, offset=(0, 0)):
        w = int(round((size or (self.model.width, self.model.height))[0] * scale))
        h = int(round((size or (self.model.width, self.model.height))[1] * scale))
        img = QImage(max(1, w), max(1, h), QImage.Format_ARGB32_Premultiplied)
        img.fill(QColor(background) if background else Qt.transparent)
        p = QPainter(img)
        T = QTransform.fromScale(scale, scale)
        T.translate(-offset[0], -offset[1])
        self.render(p, frame, T, QRect(0, 0, w, h))
        p.end()
        return img


def draw_wire(p, verts, tris, T, color, width=1.0, points=True, selected=()):
    if not len(verts):
        return
    dev = np.empty_like(verts)
    dev[:, 0] = T.m11() * verts[:, 0] + T.m21() * verts[:, 1] + T.dx()
    dev[:, 1] = T.m12() * verts[:, 0] + T.m22() * verts[:, 1] + T.dy()
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setOpacity(1.0)
    col = QColor(color)
    col.setAlpha(150)
    p.setPen(QPen(col, width))
    p.setBrush(Qt.NoBrush)
    edges = set()
    for t in tris:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            edges.add((min(a, b), max(a, b)))
    from PySide6.QtCore import QLineF
    p.drawLines([QLineF(dev[a, 0], dev[a, 1], dev[b, 0], dev[b, 1]) for a, b in edges])
    if points:
        p.setPen(QPen(QColor(color), 1))
        p.setBrush(QColor("#FFFFFF"))
        sel = set(selected)
        for i, (x, y) in enumerate(dev):
            if i in sel:
                p.setBrush(QColor(color))
            p.drawEllipse(QPointF(x, y), 3.2, 3.2)
            if i in sel:
                p.setBrush(QColor("#FFFFFF"))
    p.restore()
    return dev


def draw_grid(p, grid, cols, rows, T, color, handles=True, selected=()):
    g = grid.reshape(rows + 1, cols + 1, 2)
    dev = np.empty_like(g)
    dev[..., 0] = T.m11() * g[..., 0] + T.m21() * g[..., 1] + T.dx()
    dev[..., 1] = T.m12() * g[..., 0] + T.m22() * g[..., 1] + T.dy()
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setOpacity(1.0)
    p.setPen(QPen(QColor(color), 1.2))
    p.setBrush(Qt.NoBrush)
    for j in range(rows + 1):
        p.drawPolyline(QPolygonF([QPointF(*dev[j, i]) for i in range(cols + 1)]))
    for i in range(cols + 1):
        p.drawPolyline(QPolygonF([QPointF(*dev[j, i]) for j in range(rows + 1)]))
    if handles:
        sel = set(selected)
        for j in range(rows + 1):
            for i in range(cols + 1):
                k = j * (cols + 1) + i
                p.setBrush(QColor(color) if k in sel else QColor("#FFFFFF"))
                p.drawRect(QRectF(dev[j, i, 0] - 3.5, dev[j, i, 1] - 3.5, 7, 7))
    p.restore()
    return dev.reshape(-1, 2)
