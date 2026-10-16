"""The open project: model + selection + active parameter + undo history, with Qt signals for the panels."""
from pathlib import Path

import numpy as np

from PySide6.QtCore import QObject, Signal

from .model import ArtMesh, RotationDeformer, WarpDeformer
from .physics import PhysicsSim
from .render import Renderer


class Doc(QObject):
    modelChanged = Signal()       # structure / geometry / keys changed (panels rebuild)
    valuesChanged = Signal()      # parameter values changed (canvas redraw, sliders)
    selectionChanged = Signal()
    activeParamChanged = Signal()
    titleChanged = Signal()

    def __init__(self, model, path=None):
        super().__init__()
        self.model = model
        self.path = Path(path) if path else None
        self.renderer = Renderer(model)
        self.physics = PhysicsSim(model)
        self.selection = []
        self.active_param = model.params[0].id if model.params else None
        self.history = [model.state()]
        self.hist_i = 0
        self.saved_i = 0
        self._frame = None

    # ------------------------------------------------------------------ frames
    def frame(self):
        if self._frame is None:
            self._frame = self.model.evaluate()
        return self._frame

    def touch(self, structure=False):
        """Values or geometry changed: drop the cached frame and notify."""
        self._frame = None
        if structure:
            self.model.invalidate()
            self.modelChanged.emit()
        self.valuesChanged.emit()

    def set_value(self, pid, v, active=True):
        self.model.set_value(pid, v)
        if active and pid != self.active_param:
            self.active_param = pid
            self.activeParamChanged.emit()
        self.touch()

    def set_values(self, values):
        for k, v in values.items():
            self.model.set_value(k, v)
        self.touch()

    # ------------------------------------------------------------------ selection
    def nodes(self):
        return [self.model.nodes[i] for i in self.selection if i in self.model.nodes]

    def select(self, ids):
        ids = [i for i in dict.fromkeys(ids) if i in self.model.nodes]
        if ids != self.selection:
            self.selection = ids
            self.selectionChanged.emit()

    def selected_meshes(self):
        return [n for n in self.nodes() if isinstance(n, ArtMesh)]

    def selected_deformers(self):
        return [n for n in self.nodes() if isinstance(n, (WarpDeformer, RotationDeformer))]

    # ------------------------------------------------------------------ undo
    def commit(self, label=""):
        self.history = self.history[:self.hist_i + 1]
        self.history.append(self.model.state())
        if len(self.history) > 80:
            self.history.pop(0)
            self.saved_i -= 1
        self.hist_i = len(self.history) - 1
        self.touch(structure=True)
        self.titleChanged.emit()

    def undo(self):
        if self.hist_i > 0:
            self.hist_i -= 1
            self._restore()

    def redo(self):
        if self.hist_i < len(self.history) - 1:
            self.hist_i += 1
            self._restore()

    def _restore(self):
        self.model.set_state(self.history[self.hist_i])
        self.renderer.reset()
        self.selection = [i for i in self.selection if i in self.model.nodes]
        self.touch(structure=True)
        self.selectionChanged.emit()
        self.titleChanged.emit()

    def dirty(self):
        return self.hist_i != self.saved_i

    def mark_saved(self):
        self.saved_i = self.hist_i
        self.titleChanged.emit()

    def title(self):
        return self.path.stem if self.path else self.model.name

    # ------------------------------------------------------------------ editing helpers
    def edit_target(self, node):
        """Where geometry edits of `node` go: ('key', binding, index) at a key of the active parameter,
        ('rest', None, None) when the node has no binding for it, ('between', b, None) otherwise."""
        pid = self.active_param
        b = node.binding(pid) if pid else None
        if b is None or not b.keys:
            return "rest", None, None
        i = b.key_index(self.model.values.get(pid, self.model.param(pid).default))
        if i is None:
            return "between", b, None
        return "key", b, i

    def geometry_target(self, node):
        """Like edit_target, but creates the keys needed so an edit can land: when the active parameter is
        away from its default and the node has no key there, a binding with keys at the default and at the
        current value is created (the Cubism «add 2 keys» step done for you)."""
        pid = self.active_param
        p = self.model.param(pid) if pid else None
        kind, b, i = self.edit_target(node)
        if kind == "key":
            return b.forms[i]
        if p is None:
            return None
        v = self.model.values.get(pid, p.default)
        if kind == "rest" and abs(v - p.default) < 1e-6:
            return None  # edit the rest geometry
        b, i = self.model.ensure_key(node, pid, v)
        return b.forms[i]

    def move_points(self, node, idx, canvas_delta, frame=None, slide_uv=False):
        """Move points of a mesh (vertices) or warp (grid points) by a canvas-space delta, into the current key
        or the rest geometry. With slide_uv the texture stays put (mesh editing) — rest only."""
        frame = frame or self.frame()
        idx = np.asarray(idx, dtype=int)
        if not len(idx):
            return
        pts_rest = node.rest if isinstance(node, ArtMesh) else node.rest_grid()
        form = None if slide_uv else self.geometry_target(node)
        base = pts_rest[idx]
        cur = self.model.own_form(node)["offsets"]
        if cur is not None:
            base = base + cur[idx]
        d = self.model.canvas_delta_to_rest(node, base, np.repeat(np.asarray(canvas_delta, float)[None], len(idx), 0),
                                            frame)
        if form is None:
            if isinstance(node, ArtMesh):
                if slide_uv:
                    img = self.model.textures.get(node.texture)
                    if img is not None:
                        from .art import placement
                        T = placement(node, img)
                        inv, ok = T.inverted()
                        if ok:
                            sx = inv.m11(), inv.m21()
                            sy = inv.m12(), inv.m22()
                            du = (d[:, 0] * sx[0] + d[:, 1] * sx[1]) / max(1, img.width())
                            dv = (d[:, 0] * sy[0] + d[:, 1] * sy[1]) / max(1, img.height())
                            node.uvs[idx, 0] += du
                            node.uvs[idx, 1] += dv
                node.rest[idx] += d
            else:  # warp rest grid: move the whole rect when every point moves, else nothing sensible
                x, y, w, h = node.rect
                if len(idx) == node.n_points():
                    node.rect = (x + d[0, 0], y + d[0, 1], w, h)
                else:
                    form = self.model.ensure_key(node, self.active_param, self.model.param(self.active_param).default)
                    b, i = form
                    form = b.forms[i]
        if form is not None:
            if form.get("offsets") is None or len(form["offsets"]) != node.n_points():
                form["offsets"] = np.zeros((node.n_points(), 2))
            form["offsets"][idx] += d
        self._frame = None
