"""The editor viewport: draws the evaluated model and handles the tools of the «Нарезка» (cutting) and «Риг»
(mesh / deformer / keyform editing) workspaces."""
import math

import numpy as np
from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (QColor, QCursor, QImage, QPainter, QPainterPath, QPen, QPolygonF, QTransform)
from PySide6.QtWidgets import QWidget

from . import art
from .mesh import nearest_vertex, point_in_tris
from .model import ArtMesh, RotationDeformer, WarpDeformer
from .render import draw_grid, draw_wire

CUT_TOOLS = ("pick", "lasso", "polygon", "brush", "wand")
RIG_TOOLS = ("edit", "mesh")


class Canvas(QWidget):
    toolChanged = Signal(str)
    selectionMaskChanged = Signal()
    status = Signal(str)

    def __init__(self, doc, colors, settings, mode="rig", parent=None):
        super().__init__(parent)
        self.doc = doc
        self.c = colors
        self.settings = settings
        self.mode = mode
        self.tool = "edit" if mode == "rig" else "lasso"
        self.zoom = 0.3
        self.pan = QPointF(0, 0)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(320, 240)
        self.drag = None
        self.space = False
        self.vsel = {}           # mesh / warp id → set of selected point indices
        self.marquee = None
        # cutting
        self.sel_mask = None     # bool mask in the texture space of self.sel_layer
        self.sel_layer = None
        self.sel_op = "replace"
        self.lasso = []
        self.poly = []
        self.brush_r = 24.0
        self.wand_tol = 32
        self.wand_contig = True
        self._mask_img = None
        self.hover = None
        self.show_wire = settings.get("show_wire", True)
        self.show_deformers = settings.get("show_deformers", False)
        self.solo = False
        doc.valuesChanged.connect(self.update)
        doc.selectionChanged.connect(self._on_selection)
        doc.modelChanged.connect(self._on_model)
        self._fitted = False

    def set_doc(self, doc):
        self.doc = doc
        self.vsel.clear()
        self.clear_selection_mask()
        doc.valuesChanged.connect(self.update)
        doc.selectionChanged.connect(self._on_selection)
        doc.modelChanged.connect(self._on_model)
        self.fit()

    def set_colors(self, c):
        self.c = c
        self.update()

    def set_tool(self, t):
        self.tool = t
        self.poly = []
        self.lasso = []
        self.setCursor(Qt.CrossCursor if t in ("lasso", "polygon", "wand", "brush") else Qt.ArrowCursor)
        self.toolChanged.emit(t)
        self.update()

    # ------------------------------------------------------------------ view
    def T(self):
        t = QTransform()
        t.translate(self.width() / 2 + self.pan.x(), self.height() / 2 + self.pan.y())
        t.scale(self.zoom, self.zoom)
        t.translate(-self.doc.model.width / 2, -self.doc.model.height / 2)
        return t

    def to_canvas(self, pos):
        inv, _ = self.T().inverted()
        q = inv.map(QPointF(pos))
        return np.array([q.x(), q.y()])

    def fit(self):
        m = self.doc.model
        if self.width() < 50:
            return
        self.zoom = min((self.width() - 60) / max(1, m.width), (self.height() - 60) / max(1, m.height))
        self.pan = QPointF(0, 0)
        self.update()

    def showEvent(self, e):
        if not self._fitted:
            self._fitted = True
            self.fit()
        super().showEvent(e)

    def resizeEvent(self, e):
        if not self._fitted and self.width() > 50:
            self._fitted = True
            self.fit()
        super().resizeEvent(e)

    def zoom_at(self, factor, pos):
        before = self.to_canvas(pos)
        self.zoom = max(0.03, min(16.0, self.zoom * factor))
        after = self.T().map(QPointF(*before))
        self.pan += QPointF(pos) - after
        self.update()

    # ------------------------------------------------------------------ painting
    def paintEvent(self, e):
        p = QPainter(self)
        c = self.c
        p.fillRect(self.rect(), QColor(c["canvas"]))
        T = self.T()
        m = self.doc.model
        r = T.mapRect(QRectF(0, 0, m.width, m.height))
        # checkerboard paper
        p.save()
        p.setClipRect(r)
        p.fillRect(r, QColor(c["checker_a"]))
        step = 16
        col = QColor(c["checker_b"])
        y = int(r.top())
        row = 0
        while y < r.bottom():
            x = int(r.left()) + (step if row % 2 else 0)
            while x < r.right():
                p.fillRect(QRect(x, y, step, step), col)
                x += 2 * step
            y += step
            row += 1
        p.restore()
        p.setPen(QPen(QColor(c["border"]), 1))
        p.drawRect(r)
        frame = self.doc.frame()
        only = None
        if self.solo and self.doc.selected_meshes():
            only = {x.id for x in self.doc.selected_meshes()}
        self.doc.renderer.render(p, frame, T, self.rect(), only=only)
        if self.mode == "cut":
            self.paint_cut(p, T, frame)
        elif self.mode == "rig":
            self.paint_rig(p, T, frame)
        p.end()

    def paint_rig(self, p, T, frame):
        c = self.c
        acc = QColor(c["accent"])
        sel = set(self.doc.selection)
        for d in self.doc.model.deformers():
            active = d.id in sel
            if not active and (not self.show_deformers or not d.visible):
                continue
            if isinstance(d, WarpDeformer):
                g = frame.warps.get(d.id)
                if g is None:
                    continue
                if active:
                    draw_grid(p, g, d.cols, d.rows, T, c["accent"], True, self.vsel.get(d.id, ()))
                else:
                    p.save()
                    p.setOpacity(0.35)
                    draw_grid(p, g, d.cols, d.rows, T, c["muted"], False)
                    p.restore()
            else:
                self.paint_rot(p, T, frame, d, active)
        for mesh in self.doc.selected_meshes():
            data = frame.meshes.get(mesh.id)
            if data is None:
                continue
            draw_wire(p, data[0], mesh.tris, T, c["accent"] if self.show_wire else c["muted"], 1.0,
                      True, self.vsel.get(mesh.id, ()))
        if self.hover is not None and self.hover not in sel:
            data = frame.meshes.get(self.hover)
            mesh = self.doc.model.nodes.get(self.hover)
            if data is not None and isinstance(mesh, ArtMesh):
                p.save()
                p.setOpacity(0.5)
                draw_wire(p, data[0], mesh.tris, T, c["accent"], 0.8, False)
                p.restore()
        if self.marquee is not None:
            p.setPen(QPen(acc, 1, Qt.DashLine))
            col = QColor(acc)
            col.setAlpha(30)
            p.setBrush(col)
            p.drawRect(self.marquee.normalized())

    def paint_rot(self, p, T, frame, d, active):
        rot = frame.rots.get(d.id)
        if rot is None:
            return
        (ox, oy), ang, sc = rot
        o = T.map(QPointF(ox, oy))
        length = d.length * sc * self.zoom
        tip = QPointF(o.x() + math.sin(ang) * length, o.y() - math.cos(ang) * length)
        p.save()
        p.setRenderHint(QPainter.Antialiasing, True)
        col = QColor(self.c["accent"] if active else self.c["muted"])
        if not active:
            p.setOpacity(0.5)
        p.setPen(QPen(col, 2 if active else 1.2))
        p.drawLine(o, tip)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(o, 6 if active else 4, 6 if active else 4)
        p.setBrush(col)
        p.drawEllipse(tip, 4.5 if active else 3, 4.5 if active else 3)
        p.restore()

    def mask_image(self):
        if self.sel_mask is None:
            return None
        if self._mask_img is None:
            h, w = self.sel_mask.shape
            a = np.zeros((h, w, 4), np.uint8)
            col = QColor(self.c["accent"])
            a[self.sel_mask] = (col.red(), col.green(), col.blue(), 110)
            self._mask_img = art.from_rgba(a)
        return self._mask_img

    def paint_cut(self, p, T, frame):
        c = self.c
        acc = QColor(c["accent"])
        layer = self.current_layer()
        if layer is not None:
            data = frame.meshes.get(layer.id)
            img = self.doc.model.textures.get(layer.texture)
            if data is not None and img is not None:
                Tp = art.placement(layer, img)
                p.save()
                p.setTransform(Tp * T)
                p.setPen(QPen(acc, 1.5 / max(0.05, self.zoom), Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                p.drawRect(QRectF(0, 0, img.width(), img.height()))
                mi = self.mask_image()
                if mi is not None and self.sel_layer == layer.id:
                    p.drawImage(0, 0, mi)
                p.restore()
        p.save()
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(acc, 1.5, Qt.DashLine))
        if self.lasso:
            p.drawPolyline(QPolygonF([T.map(QPointF(x, y)) for x, y in self.lasso]))
        if self.poly:
            pts = [T.map(QPointF(x, y)) for x, y in self.poly]
            if self.hover_pt is not None:
                pts.append(T.map(QPointF(*self.hover_pt)))
            p.drawPolyline(QPolygonF(pts))
            p.setBrush(QColor("#FFFFFF"))
            for q in pts[:len(self.poly)]:
                p.drawEllipse(q, 3, 3)
        if self.tool == "brush" and self.hover_pt is not None:
            q = T.map(QPointF(*self.hover_pt))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(q, self.brush_r * self.zoom, self.brush_r * self.zoom)
        p.restore()

    hover_pt = None

    # ------------------------------------------------------------------ picking
    def pick_mesh(self, pt, alpha_min=10):
        frame = self.doc.frame()
        best = None
        for mid, (verts, op, order) in sorted(frame.meshes.items(), key=lambda kv: -kv[1][2]):
            mesh = self.doc.model.nodes.get(mid)
            if op <= 0.02 or mesh is None or mesh.locked or not len(mesh.tris):
                continue
            lo, hi = verts.min(0), verts.max(0)
            if not (lo[0] <= pt[0] <= hi[0] and lo[1] <= pt[1] <= hi[1]):
                continue
            k, w = point_in_tris(pt, verts, mesh.tris)
            if k < 0:
                continue
            t = mesh.tris[k]
            uv = mesh.uvs[t[0]] * w[0] + mesh.uvs[t[1]] * w[1] + mesh.uvs[t[2]] * w[2]
            img = self.doc.model.textures.get(mesh.texture)
            if img is not None:
                x, y = int(uv[0] * img.width()), int(uv[1] * img.height())
                if 0 <= x < img.width() and 0 <= y < img.height() and img.pixelColor(x, y).alpha() < alpha_min:
                    continue
            best = mesh
            break
        return best

    def pick_handle(self, pos):
        """Point / origin / tip handle under the cursor of the selected objects: (node, kind, index)."""
        frame = self.doc.frame()
        T = self.T()
        P = np.array([pos.x(), pos.y()], float)
        for node in self.doc.nodes():
            if isinstance(node, RotationDeformer):
                rot = frame.rots.get(node.id)
                if rot is None:
                    continue
                (ox, oy), ang, sc = rot
                o = T.map(QPointF(ox, oy))
                length = node.length * sc * self.zoom
                tip = (o.x() + math.sin(ang) * length, o.y() - math.cos(ang) * length)
                if math.hypot(tip[0] - P[0], tip[1] - P[1]) < 9:
                    return node, "tip", None
                if math.hypot(o.x() - P[0], o.y() - P[1]) < 9:
                    return node, "origin", None
            elif isinstance(node, WarpDeformer) and node.id in self.doc.selection:
                g = frame.warps.get(node.id)
                if g is None:
                    continue
                dev = self._dev(g, T)
                k, d = nearest_vertex(P, dev)
                if d < 7:
                    return node, "point", k
            elif isinstance(node, ArtMesh):
                data = frame.meshes.get(node.id)
                if data is None:
                    continue
                dev = self._dev(data[0], T)
                k, d = nearest_vertex(P, dev)
                if d < 6:
                    return node, "point", k
        return None

    @staticmethod
    def _dev(pts, T):
        out = np.empty_like(pts)
        out[:, 0] = T.m11() * pts[:, 0] + T.m21() * pts[:, 1] + T.dx()
        out[:, 1] = T.m12() * pts[:, 0] + T.m22() * pts[:, 1] + T.dy()
        return out

    # ------------------------------------------------------------------ cutting helpers
    def current_layer(self):
        ms = self.doc.selected_meshes()
        return ms[0] if ms else None

    def clear_selection_mask(self):
        self.sel_mask = None
        self.sel_layer = None
        self._mask_img = None
        self.selectionMaskChanged.emit()
        self.update()

    def apply_mask(self, mask, op=None):
        layer = self.current_layer()
        if layer is None:
            return
        if self.sel_layer != layer.id:
            self.sel_mask = None
        self.sel_layer = layer.id
        self.sel_mask = art.combine(self.sel_mask, mask, op or self.sel_op)
        if not self.sel_mask.any():
            self.sel_mask = None
        self._mask_img = None
        self.selectionMaskChanged.emit()
        n = 0 if self.sel_mask is None else int(self.sel_mask.sum())
        self.status.emit(f"Выделено пикселей: {n:,}".replace(",", " "))
        self.update()

    def _op_for(self, mods):
        if mods & Qt.AltModifier:
            return "subtract"
        if mods & Qt.ShiftModifier:
            return "add"
        return None

    def finish_path(self, pts, mods):
        layer = self.current_layer()
        img = self.doc.model.textures.get(layer.texture) if layer else None
        if img is None or len(pts) < 3:
            return
        path = QPainterPath(QPointF(*pts[0]))
        for x, y in pts[1:]:
            path.lineTo(QPointF(x, y))
        path.closeSubpath()
        # the path is drawn on the evaluated frame: map it back to the rest pose when the layer is deformed
        path = self._to_rest_path(layer, path)
        self.apply_mask(art.canvas_path_to_mask(layer, img, path), self._op_for(mods))

    def _to_rest_path(self, layer, path):
        frame = self.doc.frame()
        data = frame.meshes.get(layer.id)
        if data is None or np.allclose(data[0], layer.rest, atol=0.5):
            return path
        verts = data[0]
        out = QPainterPath()
        for i in range(path.elementCount()):
            el = path.elementAt(i)
            pt = np.array([el.x, el.y])
            k, w = point_in_tris(pt, verts, layer.tris)
            if k >= 0:
                t = layer.tris[k]
                q = layer.rest[t[0]] * w[0] + layer.rest[t[1]] * w[1] + layer.rest[t[2]] * w[2]
            else:
                j, _ = nearest_vertex(pt, verts)
                q = pt + (layer.rest[j] - verts[j])
            if i == 0 or el.isMoveTo():
                out.moveTo(QPointF(*q))
            else:
                out.lineTo(QPointF(*q))
        out.closeSubpath()
        return out

    def brush_stamp(self, pt, mods):
        layer = self.current_layer()
        img = self.doc.model.textures.get(layer.texture) if layer else None
        if img is None:
            return
        m = art.brush_mask(layer, img, [tuple(pt)], self.brush_r)
        op = self._op_for(mods) or ("add" if self.sel_mask is not None and self.sel_layer == layer.id else "replace")
        self.apply_mask(m, op)

    def wand(self, pt, mods):
        layer = self.current_layer()
        img = self.doc.model.textures.get(layer.texture) if layer else None
        if img is None:
            return
        T = art.placement(layer, img)
        inv, _ = T.inverted()
        q = inv.map(QPointF(*pt))
        m = art.magic_wand(img, (q.x(), q.y()), self.wand_tol, self.wand_contig)
        self.apply_mask(m, self._op_for(mods))

    # ------------------------------------------------------------------ mouse
    def mousePressEvent(self, e):
        self.setFocus()
        pos = e.position()
        pt = self.to_canvas(pos)
        if e.button() == Qt.MiddleButton or (e.button() == Qt.LeftButton and self.space):
            self.drag = ("pan", pos, QPointF(self.pan))
            self.setCursor(Qt.ClosedHandCursor)
            return
        if e.button() != Qt.LeftButton:
            return
        if self.mode == "cut":
            self.press_cut(pt, e)
        elif self.mode == "rig":
            self.press_rig(pos, pt, e)

    def press_cut(self, pt, e):
        mods = e.modifiers()
        if self.tool == "pick" or self.current_layer() is None:
            mesh = self.pick_mesh(pt)
            if mesh is not None:
                self.doc.select([mesh.id])
            return
        if self.tool == "lasso":
            self.lasso = [tuple(pt)]
            self.drag = ("lasso", mods)
        elif self.tool == "polygon":
            if len(self.poly) >= 3 and self._near_first(pt):
                pts, self.poly = self.poly, []
                self.finish_path(pts, mods)
            else:
                self.poly.append(tuple(pt))
            self.update()
        elif self.tool == "brush":
            self.drag = ("brush", mods)
            self.brush_stamp(pt, mods)
        elif self.tool == "wand":
            self.wand(pt, mods)

    def _near_first(self, pt):
        a = self.T().map(QPointF(*self.poly[0]))
        b = self.T().map(QPointF(*pt))
        return math.hypot(a.x() - b.x(), a.y() - b.y()) < 10

    def press_rig(self, pos, pt, e):
        mods = e.modifiers()
        h = self.pick_handle(pos)
        if h is not None:
            node, kind, k = h
            if kind == "point":
                sel = self.vsel.setdefault(node.id, set())
                if mods & Qt.ShiftModifier:
                    sel ^= {k}
                elif k not in sel:
                    self.vsel = {node.id: {k}}
                self.drag = ("points", pos, self.to_canvas(pos), False)
            else:
                self.drag = (kind, node, pos, self.to_canvas(pos), False)
            self.update()
            return
        mesh = self.pick_mesh(pt)
        sel_meshes = {m.id for m in self.doc.selected_meshes()}
        if mesh is not None and mesh.id not in sel_meshes or (mesh is not None and not sel_meshes):
            ids = list(self.doc.selection) + [mesh.id] if mods & Qt.ShiftModifier else [mesh.id]
            self.doc.select(ids)
            self.vsel = {}
            self.drag = ("maybe_move", pos, self.to_canvas(pos), False)
            return
        if mesh is not None and mesh.id in sel_meshes:
            # drag the whole selected layer(s)
            self.drag = ("maybe_move", pos, self.to_canvas(pos), False)
            return
        # empty space: marquee over the vertices of the selected objects (or clear the selection)
        self.drag = ("marquee", pos, mods)
        self.marquee = QRectF(pos, pos)

    def mouseMoveEvent(self, e):
        pos = e.position()
        pt = self.to_canvas(pos)
        self.hover_pt = tuple(pt)
        d = self.drag
        if d is None:
            if self.mode == "rig":
                m = self.pick_mesh(pt)
                hid = m.id if m is not None else None
                if hid != self.hover:
                    self.hover = hid
                    self.update()
            elif self.tool in ("brush", "polygon"):
                self.update()
            return
        kind = d[0]
        if kind == "pan":
            self.pan = d[2] + (pos - d[1])
            self.update()
        elif kind == "lasso":
            last = self.lasso[-1]
            if math.hypot(pt[0] - last[0], pt[1] - last[1]) * self.zoom > 2:
                self.lasso.append(tuple(pt))
                self.update()
        elif kind == "brush":
            self.brush_stamp(pt, d[1])
        elif kind == "marquee":
            self.marquee = QRectF(d[1], pos)
            self.update()
        elif kind == "points":
            delta = pt - d[2]
            frame = self.doc.frame()
            for nid, idx in self.vsel.items():
                node = self.doc.model.nodes.get(nid)
                if node is None or not idx:
                    continue
                self.doc.move_points(node, sorted(idx), delta, frame, slide_uv=self.tool == "mesh")
            self.drag = ("points", d[1], pt, True)
            self.doc.touch()
        elif kind == "maybe_move":
            if not d[3] and (pos - d[1]).manhattanLength() < 4:
                return
            delta = pt - d[2]
            frame = self.doc.frame()
            for node in self.doc.nodes():
                if isinstance(node, ArtMesh):
                    self.doc.move_points(node, range(len(node.rest)), delta, frame)
                elif isinstance(node, WarpDeformer):
                    self.doc.move_points(node, range(node.n_points()), delta, frame)
            self.drag = ("maybe_move", d[1], pt, True)
            self.doc.touch()
        elif kind == "origin":
            node = d[1]
            delta = pt - d[3]
            self.move_origin(node, delta)
            self.drag = ("origin", node, d[2], pt, True)
            self.doc.touch()
        elif kind == "tip":
            node = d[1]
            rot = self.doc.frame().rots.get(node.id)
            if rot is not None:
                (ox, oy), ang, _ = rot
                want = math.atan2(pt[0] - ox, -(pt[1] - oy))
                diff = math.degrees(want - ang)
                diff = (diff + 180) % 360 - 180
                self.rotate_by(node, diff)
                self.drag = ("tip", node, d[2], pt, True)
                self.doc.touch()

    def move_origin(self, node, delta):
        doc = self.doc
        form = doc.geometry_target(node)
        par_frame = doc.frame()
        o = np.array([[node.origin[0], node.origin[1]]])
        d = doc.model.canvas_delta_to_rest(node, o, np.asarray(delta, float)[None], par_frame)[0]
        if form is None:
            node.origin = (node.origin[0] + d[0], node.origin[1] + d[1])
        else:
            form["dx"] = form.get("dx", 0.0) + d[0]
            form["dy"] = form.get("dy", 0.0) + d[1]
        doc._frame = None

    def rotate_by(self, node, deg):
        form = self.doc.geometry_target(node)
        if form is None:
            self.status.emit("Чтобы вращать, выберите параметр и поставьте его не в значение по умолчанию")
            return
        form["angle"] = form.get("angle", 0.0) + deg
        self.doc._frame = None

    def mouseReleaseEvent(self, e):
        d = self.drag
        self.drag = None
        if d is None:
            return
        kind = d[0]
        if kind == "pan":
            self.setCursor(Qt.ArrowCursor if self.mode == "rig" else Qt.CrossCursor)
        elif kind == "lasso":
            pts, self.lasso = self.lasso, []
            if len(pts) > 2:
                self.finish_path(pts, d[1])
            self.update()
        elif kind == "marquee":
            r = self.marquee.normalized() if self.marquee is not None else QRectF()
            self.marquee = None
            if r.width() < 3 and r.height() < 3:
                if not (d[2] & Qt.ShiftModifier):
                    self.doc.select([])
                    self.vsel = {}
            else:
                self.select_points_in(r, d[2] & Qt.ShiftModifier)
            self.update()
        elif kind in ("points", "maybe_move", "origin", "tip") and d[-1]:
            self.doc.commit()

    def select_points_in(self, r, add):
        frame = self.doc.frame()
        T = self.T()
        out = dict(self.vsel) if add else {}
        for node in self.doc.nodes():
            if isinstance(node, ArtMesh):
                data = frame.meshes.get(node.id)
                pts = data[0] if data else None
            elif isinstance(node, WarpDeformer):
                pts = frame.warps.get(node.id)
            else:
                pts = None
            if pts is None:
                continue
            dev = self._dev(pts, T)
            inside = (dev[:, 0] >= r.left()) & (dev[:, 0] <= r.right()) & (dev[:, 1] >= r.top()) & \
                (dev[:, 1] <= r.bottom())
            idx = set(np.nonzero(inside)[0].tolist())
            if idx:
                out[node.id] = out.get(node.id, set()) | idx
        self.vsel = out
        n = sum(len(v) for v in out.values())
        self.status.emit(f"Выбрано точек: {n}")

    def mouseDoubleClickEvent(self, e):
        if self.mode == "cut" and self.tool == "polygon" and len(self.poly) >= 3:
            pts, self.poly = self.poly, []
            self.finish_path(pts, e.modifiers())
            self.update()

    def wheelEvent(self, e):
        dy = e.angleDelta().y()
        if e.modifiers() & (Qt.ControlModifier | Qt.MetaModifier) or not e.pixelDelta().y():
            self.zoom_at(1.0015 ** dy, e.position())
        else:
            self.pan += QPointF(e.pixelDelta().x(), e.pixelDelta().y())
            self.update()

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key_Space and not e.isAutoRepeat():
            self.space = True
            self.setCursor(Qt.OpenHandCursor)
            return
        if k == Qt.Key_Escape:
            if self.poly or self.lasso:
                self.poly, self.lasso = [], []
            elif self.mode == "cut":
                self.clear_selection_mask()
            else:
                self.vsel = {}
            self.update()
            return
        if k in (Qt.Key_Return, Qt.Key_Enter) and self.poly:
            pts, self.poly = self.poly, []
            self.finish_path(pts, e.modifiers())
            return
        if k == Qt.Key_0 and e.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            self.fit()
            return
        if k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down) and self.vsel and self.mode == "rig":
            step = 10.0 if e.modifiers() & Qt.ShiftModifier else 1.0
            dx = {Qt.Key_Left: -step, Qt.Key_Right: step}.get(k, 0.0)
            dy = {Qt.Key_Up: -step, Qt.Key_Down: step}.get(k, 0.0)
            frame = self.doc.frame()
            for nid, idx in self.vsel.items():
                node = self.doc.model.nodes.get(nid)
                if node is not None and idx:
                    self.doc.move_points(node, sorted(idx), np.array([dx, dy]), frame)
            self.doc.commit()
            return
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key_Space and not e.isAutoRepeat():
            self.space = False
            self.setCursor(Qt.ArrowCursor if self.mode == "rig" else Qt.CrossCursor)
            return
        super().keyReleaseEvent(e)

    def leaveEvent(self, e):
        self.hover_pt = None
        if self.hover is not None:
            self.hover = None
        self.update()

    # ------------------------------------------------------------------ doc signals
    def _on_selection(self):
        ids = set(self.doc.selection)
        self.vsel = {k: v for k, v in self.vsel.items() if k in ids}
        if self.mode == "cut" and self.sel_layer is not None and self.sel_layer not in ids:
            self.clear_selection_mask()
        self.update()

    def _on_model(self):
        if self.sel_layer is not None and self.sel_layer not in self.doc.model.nodes:
            self.clear_selection_mask()
        self.update()

    def grab_image(self):
        img = QImage(self.size(), QImage.Format_ARGB32_Premultiplied)
        self.render(img)
        return img

    def cursor_pos_canvas(self):
        return self.to_canvas(self.mapFromGlobal(QCursor.pos()))
