"""The puppet: textures, art meshes, warp / rotation deformers, parameters with keyforms, physics groups, poses.

Geometry is stored in canvas pixels. Every object keeps its *rest* geometry plus, per parameter binding,
keyforms of offsets measured in the rest frame (canvas units). Evaluation sums the keyform offsets of all
bindings (interpolated between keys), then pushes the points through the parent deformer chain:
warp deformers map points bilinearly through their (deformed) control grid, rotation deformers rotate /
scale around their (moved) origin. Because offsets live in the rest frame, re-parenting never breaks keys."""
import copy
import json
import math
import uuid

import numpy as np

PARAM_GROUPS = ["Голова", "Глаза", "Брови", "Рот", "Тело", "Руки", "Ноги", "Волосы", "Прочее"]


def new_id(prefix="n"):
    return prefix + uuid.uuid4().hex[:8]


# ====================================================================== parameters
class Param:
    def __init__(self, pid, name, lo=-1.0, hi=1.0, default=0.0, group="Прочее"):
        self.id, self.name, self.min, self.max, self.default, self.group = pid, name, float(lo), float(hi), \
            float(default), group

    def clamp(self, v):
        return max(self.min, min(self.max, float(v)))

    def norm(self, v):
        """Value scaled to −1…1 (by the larger side of the range)."""
        span = max(abs(self.min - self.default), abs(self.max - self.default)) or 1.0
        return (v - self.default) / span

    def to_dict(self):
        return {"id": self.id, "name": self.name, "min": self.min, "max": self.max, "default": self.default,
                "group": self.group}

    @classmethod
    def from_dict(cls, d):
        return cls(d["id"], d.get("name", d["id"]), d.get("min", -1), d.get("max", 1), d.get("default", 0),
                   d.get("group", "Прочее"))


FORM_KEYS = ("offsets", "opacity", "angle", "dx", "dy", "scale")


def blank_form(n_points=0):
    return {"offsets": np.zeros((n_points, 2)) if n_points else None, "opacity": 1.0, "angle": 0.0, "dx": 0.0,
            "dy": 0.0, "scale": 1.0}


class Binding:
    """Keyforms of one object along one parameter."""

    def __init__(self, param, keys=None, forms=None):
        self.param = param
        self.keys = list(keys or [])
        self.forms = list(forms or [])

    def locate(self, v):
        k = self.keys
        if not k:
            return None
        if v <= k[0] or len(k) == 1:
            return 0, 0, 0.0
        if v >= k[-1]:
            return len(k) - 1, len(k) - 1, 0.0
        for i in range(len(k) - 1):
            if k[i] <= v <= k[i + 1]:
                span = k[i + 1] - k[i]
                return i, i + 1, (v - k[i]) / span if span else 0.0
        return len(k) - 1, len(k) - 1, 0.0

    def key_index(self, v, eps=1e-4):
        for i, k in enumerate(self.keys):
            if abs(k - v) <= eps * max(1.0, abs(k)):
                return i
        return None

    def form_at(self, v):
        loc = self.locate(v)
        if loc is None:
            return None
        i, j, t = loc
        a, b = self.forms[i], self.forms[j]
        if t == 0.0 or i == j:
            return a
        out = {}
        for key in FORM_KEYS:
            va, vb = a.get(key), b.get(key)
            if va is None or vb is None:
                out[key] = va if vb is None else vb
            elif key == "offsets":
                out[key] = va * (1 - t) + vb * t
            else:
                out[key] = va * (1 - t) + vb * t
        return out

    def add_key(self, value, form):
        if self.key_index(value) is not None:
            self.forms[self.key_index(value)] = form
            return self.key_index(value)
        i = 0
        while i < len(self.keys) and self.keys[i] < value:
            i += 1
        self.keys.insert(i, float(value))
        self.forms.insert(i, form)
        return i

    def remove_key(self, i):
        self.keys.pop(i)
        self.forms.pop(i)

    def to_dict(self):
        forms = []
        for f in self.forms:
            d = {k: f[k] for k in ("opacity", "angle", "dx", "dy", "scale") if f.get(k) is not None}
            if f.get("offsets") is not None:
                d["offsets"] = np.round(f["offsets"], 3).tolist()
            forms.append(d)
        return {"param": self.param, "keys": self.keys, "forms": forms}

    @classmethod
    def from_dict(cls, d):
        forms = []
        for f in d.get("forms", []):
            g = blank_form()
            g.update({k: v for k, v in f.items() if k != "offsets"})
            if f.get("offsets") is not None:
                g["offsets"] = np.asarray(f["offsets"], dtype=float).reshape(-1, 2)
            forms.append(g)
        return cls(d["param"], d.get("keys", []), forms)


# ====================================================================== nodes
class Node:
    kind = "node"

    def __init__(self, nid=None, name="", parent=None):
        self.id = nid or new_id()
        self.name = name
        self.parent = parent
        self.visible = True
        self.locked = False
        self.bindings = []

    def binding(self, pid, create=False):
        for b in self.bindings:
            if b.param == pid:
                return b
        if create:
            b = Binding(pid)
            self.bindings.append(b)
            return b
        return None

    def n_points(self):
        return 0

    def base_dict(self):
        return {"kind": self.kind, "id": self.id, "name": self.name, "parent": self.parent, "visible": self.visible,
                "locked": self.locked, "bindings": [b.to_dict() for b in self.bindings]}

    def load_base(self, d):
        self.visible = d.get("visible", True)
        self.locked = d.get("locked", False)
        self.bindings = [Binding.from_dict(b) for b in d.get("bindings", [])]


class ArtMesh(Node):
    kind = "mesh"

    def __init__(self, nid=None, name="", parent=None, texture=None, rest=None, uvs=None, tris=None, order=0):
        super().__init__(nid, name, parent)
        self.texture = texture
        self.rest = np.asarray(rest if rest is not None else np.zeros((0, 2)), dtype=float).reshape(-1, 2)
        self.uvs = np.asarray(uvs if uvs is not None else np.zeros((0, 2)), dtype=float).reshape(-1, 2)
        self.tris = np.asarray(tris if tris is not None else np.zeros((0, 3)), dtype=np.int32).reshape(-1, 3)
        self.order = order
        self.opacity = 1.0
        self.blend = "normal"
        self.masks = []
        self.invert_mask = False
        self.role = ""          # auto-rig role (eye_white_l, bangs, …)

    def n_points(self):
        return len(self.rest)

    def to_dict(self):
        d = self.base_dict()
        d.update({"texture": self.texture, "rest": np.round(self.rest, 3).tolist(), "uvs": np.round(self.uvs, 6).tolist(),
                  "tris": self.tris.tolist(), "order": self.order, "opacity": self.opacity, "blend": self.blend,
                  "masks": list(self.masks), "invert_mask": self.invert_mask, "role": self.role})
        return d

    @classmethod
    def from_dict(cls, d):
        m = cls(d["id"], d.get("name", ""), d.get("parent"), d.get("texture"), d.get("rest"), d.get("uvs"),
                d.get("tris"), d.get("order", 0))
        m.opacity = d.get("opacity", 1.0)
        m.blend = d.get("blend", "normal")
        m.masks = list(d.get("masks", []))
        m.invert_mask = d.get("invert_mask", False)
        m.role = d.get("role", "")
        m.load_base(d)
        return m


class WarpDeformer(Node):
    kind = "warp"

    def __init__(self, nid=None, name="", parent=None, rect=(0, 0, 100, 100), rows=4, cols=4):
        super().__init__(nid, name, parent)
        self.rect = tuple(float(v) for v in rect)
        self.rows, self.cols = int(rows), int(cols)

    def n_points(self):
        return (self.rows + 1) * (self.cols + 1)

    def rest_grid(self):
        x, y, w, h = self.rect
        u = np.linspace(0, 1, self.cols + 1)
        v = np.linspace(0, 1, self.rows + 1)
        gu, gv = np.meshgrid(u, v)  # (rows+1, cols+1)
        return np.stack([x + gu * w, y + gv * h], axis=-1).reshape(-1, 2)

    def uv_of(self, pts):
        """Rest-frame points → grid coordinates (u, v in 0…1)."""
        x, y, w, h = self.rect
        return np.stack([(pts[:, 0] - x) / (w or 1), (pts[:, 1] - y) / (h or 1)], axis=1)

    def to_dict(self):
        d = self.base_dict()
        d.update({"rect": list(self.rect), "rows": self.rows, "cols": self.cols})
        return d

    @classmethod
    def from_dict(cls, d):
        w = cls(d["id"], d.get("name", ""), d.get("parent"), d.get("rect", (0, 0, 100, 100)), d.get("rows", 4),
                d.get("cols", 4))
        w.load_base(d)
        return w


class RotationDeformer(Node):
    kind = "rot"

    def __init__(self, nid=None, name="", parent=None, origin=(0, 0), length=120.0):
        super().__init__(nid, name, parent)
        self.origin = (float(origin[0]), float(origin[1]))
        self.length = float(length)

    def to_dict(self):
        d = self.base_dict()
        d.update({"origin": list(self.origin), "length": self.length})
        return d

    @classmethod
    def from_dict(cls, d):
        r = cls(d["id"], d.get("name", ""), d.get("parent"), d.get("origin", (0, 0)), d.get("length", 120))
        r.load_base(d)
        return r


NODE_TYPES = {"mesh": ArtMesh, "warp": WarpDeformer, "rot": RotationDeformer}


# ====================================================================== physics / poses
class PhysGroup:
    def __init__(self, gid=None, name="Физика", inputs=None, output="", scale=1.0, stiffness=60.0, damping=7.0,
                 gravity=0.6, enabled=True):
        self.id = gid or new_id("ph")
        self.name = name
        self.inputs = list(inputs or [])   # [{"param": id, "weight": 1.0, "kind": "x" | "angle"}]
        self.output = output
        self.scale, self.stiffness, self.damping, self.gravity, self.enabled = scale, stiffness, damping, gravity, enabled

    def to_dict(self):
        return {"id": self.id, "name": self.name, "inputs": self.inputs, "output": self.output, "scale": self.scale,
                "stiffness": self.stiffness, "damping": self.damping, "gravity": self.gravity, "enabled": self.enabled}

    @classmethod
    def from_dict(cls, d):
        return cls(d.get("id"), d.get("name", "Физика"), d.get("inputs"), d.get("output", ""), d.get("scale", 1.0),
                   d.get("stiffness", 60.0), d.get("damping", 7.0), d.get("gravity", 0.6), d.get("enabled", True))


# ====================================================================== evaluation helpers
def bilinear(grid, cols, rows, uv):
    """grid: ((rows+1)*(cols+1), 2) canvas points; uv: (N, 2) → (N, 2). Extrapolates past the edges."""
    g = grid.reshape(rows + 1, cols + 1, 2)
    fu = uv[:, 0] * cols
    fv = uv[:, 1] * rows
    i = np.clip(np.floor(fu).astype(int), 0, cols - 1)
    j = np.clip(np.floor(fv).astype(int), 0, rows - 1)
    tx = (fu - i)[:, None]
    ty = (fv - j)[:, None]
    p00 = g[j, i]
    p10 = g[j, i + 1]
    p01 = g[j + 1, i]
    p11 = g[j + 1, i + 1]
    return (p00 * (1 - tx) * (1 - ty) + p10 * tx * (1 - ty) + p01 * (1 - tx) * ty + p11 * tx * ty)


class Frame:
    """Result of evaluating the model at the current parameter values."""

    def __init__(self):
        self.meshes = {}     # id → (verts (N,2) canvas, opacity, order)
        self.warps = {}      # id → grid (n,2) canvas
        self.rots = {}       # id → (origin (2,), angle rad, scale)
        self.opacity = {}    # node id → inherited opacity


class Model:
    def __init__(self, name="Модель", width=1400, height=2400):
        self.name = name
        self.width, self.height = int(width), int(height)
        self.textures = {}   # id → QImage
        self.nodes = {}      # id → Node (insertion order = tree order)
        self.params = []
        self.values = {}
        self.physics = []
        self.poses = []      # [{"name": str, "values": {pid: v}}]
        self.meta = {"author": "", "created_with": "Мю"}
        self.scenes = []     # studio scenes (dicts)
        self._order_cache = None

    # ------------------------------------------------------------------ structure
    def add(self, node):
        self.nodes[node.id] = node
        self._order_cache = None
        return node

    def remove(self, nid):
        node = self.nodes.pop(nid, None)
        if node is None:
            return
        for n in self.nodes.values():
            if n.parent == nid:
                n.parent = node.parent
            if isinstance(n, ArtMesh) and nid in n.masks:
                n.masks.remove(nid)
        self._order_cache = None

    def children(self, nid):
        return [n for n in self.nodes.values() if n.parent == nid]

    def meshes(self):
        return [n for n in self.nodes.values() if isinstance(n, ArtMesh)]

    def deformers(self):
        return [n for n in self.nodes.values() if not isinstance(n, ArtMesh)]

    def depth(self, node):
        d = 0
        p = node.parent
        seen = set()
        while p and p in self.nodes and p not in seen:
            seen.add(p)
            d += 1
            p = self.nodes[p].parent
        return d

    def ancestors(self, node):
        out = []
        p = node.parent
        while p and p in self.nodes:
            out.append(self.nodes[p])
            p = self.nodes[p].parent
        return out

    def eval_order(self):
        if self._order_cache is None:
            self._order_cache = sorted(self.nodes.values(), key=self.depth)
        return self._order_cache

    def invalidate(self):
        self._order_cache = None

    def param(self, pid):
        return next((p for p in self.params if p.id == pid), None)

    def add_param(self, p):
        if self.param(p.id) is None:
            self.params.append(p)
            self.values.setdefault(p.id, p.default)
        return self.param(p.id)

    def reset_values(self):
        self.values = {p.id: p.default for p in self.params}

    def set_value(self, pid, v):
        p = self.param(pid)
        if p is not None:
            self.values[pid] = p.clamp(v)

    # ------------------------------------------------------------------ evaluation
    def own_form(self, node, values=None):
        """Sum of the node's keyforms at the current values."""
        values = self.values if values is None else values
        n = node.n_points()
        off = np.zeros((n, 2)) if n else None
        opacity, angle, dx, dy, scale = 1.0, 0.0, 0.0, 0.0, 1.0
        for b in node.bindings:
            p = self.param(b.param)
            if p is None or not b.keys:
                continue
            f = b.form_at(values.get(b.param, p.default))
            if f is None:
                continue
            if off is not None and f.get("offsets") is not None and len(f["offsets"]) == n:
                off = off + f["offsets"]
            opacity *= f.get("opacity", 1.0)
            angle += f.get("angle", 0.0)
            dx += f.get("dx", 0.0)
            dy += f.get("dy", 0.0)
            scale *= f.get("scale", 1.0)
        return {"offsets": off, "opacity": opacity, "angle": angle, "dx": dx, "dy": dy, "scale": scale}

    def transform_points(self, pts, parent_id, frame):
        """Rest-frame points under `parent_id` → canvas points (parents already evaluated in `frame`)."""
        if not parent_id or parent_id not in self.nodes:
            return pts
        parent = self.nodes[parent_id]
        if isinstance(parent, WarpDeformer):
            grid = frame.warps.get(parent.id)
            if grid is None:
                return pts
            return bilinear(grid, parent.cols, parent.rows, parent.uv_of(pts))
        if isinstance(parent, RotationDeformer):
            rot = frame.rots.get(parent.id)
            if rot is None:
                return pts
            origin, ang, sc = rot
            local = pts - np.asarray(parent.origin)
            c, s = math.cos(ang) * sc, math.sin(ang) * sc
            return np.stack([origin[0] + c * local[:, 0] - s * local[:, 1],
                             origin[1] + s * local[:, 0] + c * local[:, 1]], axis=1)
        return pts

    def evaluate(self, values=None):
        frame = Frame()
        saved = None
        if values is not None:
            saved, self.values = self.values, values
        try:
            for node in self.eval_order():
                form = self.own_form(node)
                pop = frame.opacity.get(node.parent, 1.0) if node.parent else 1.0
                vis_parent = node.parent is None or node.parent not in self.nodes or self.nodes[node.parent].visible
                frame.opacity[node.id] = pop * form["opacity"] * (1.0 if vis_parent else 0.0)
                if isinstance(node, WarpDeformer):
                    pts = node.rest_grid()
                    if form["offsets"] is not None:
                        pts = pts + form["offsets"]
                    frame.warps[node.id] = self.transform_points(pts, node.parent, frame)
                elif isinstance(node, RotationDeformer):
                    o = np.array([[node.origin[0] + form["dx"], node.origin[1] + form["dy"]]])
                    oc = self.transform_points(o, node.parent, frame)[0]
                    ang = math.radians(form["angle"])
                    sc = form["scale"]
                    par = self.nodes.get(node.parent) if node.parent else None
                    if isinstance(par, RotationDeformer) and par.id in frame.rots:
                        ang += frame.rots[par.id][1]
                        sc *= frame.rots[par.id][2]
                    elif isinstance(par, WarpDeformer):  # follow the warp's local rotation
                        probe = np.array([[o[0, 0], o[0, 1]], [o[0, 0], o[0, 1] - 20.0]])
                        q = self.transform_points(probe, node.parent, frame)
                        v = q[1] - q[0]
                        ang += math.atan2(v[0], -v[1])
                    frame.rots[node.id] = (oc, ang, sc)
                    if not node.visible:
                        frame.opacity[node.id] = 0.0
                elif isinstance(node, ArtMesh):
                    pts = node.rest
                    if form["offsets"] is not None:
                        pts = pts + form["offsets"]
                    verts = self.transform_points(pts, node.parent, frame)
                    op = frame.opacity[node.id] * node.opacity * (1.0 if node.visible else 0.0)
                    frame.meshes[node.id] = (verts, op, node.order)
                if not node.visible and not isinstance(node, ArtMesh):
                    frame.opacity[node.id] = 0.0
        finally:
            if saved is not None:
                self.values = saved
        return frame

    def jacobian(self, node, pts, frame, eps=1.0):
        """Per-point 2×2 Jacobians of the parent chain (canvas delta ↔ rest delta)."""
        base = self.transform_points(pts, node.parent, frame)
        dx = self.transform_points(pts + [eps, 0], node.parent, frame) - base
        dy = self.transform_points(pts + [0, eps], node.parent, frame) - base
        J = np.stack([dx / eps, dy / eps], axis=2)  # (N, 2, 2): columns = d/dx, d/dy
        return J

    def canvas_delta_to_rest(self, node, pts, delta, frame):
        """Convert canvas-space displacements of points into rest-frame offsets."""
        J = self.jacobian(node, pts, frame)
        out = np.zeros_like(delta)
        for i in range(len(pts)):
            try:
                out[i] = np.linalg.solve(J[i], delta[i])
            except np.linalg.LinAlgError:
                out[i] = delta[i]
        return out

    # ------------------------------------------------------------------ keyform editing helpers
    def current_form_for(self, node, binding):
        """The binding's form interpolated at the current value (a copy, for creating new keys)."""
        p = self.param(binding.param)
        f = binding.form_at(self.values.get(binding.param, p.default if p else 0.0))
        if f is None:
            return blank_form(node.n_points())
        g = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in f.items()}
        if g.get("offsets") is None and node.n_points():
            g["offsets"] = np.zeros((node.n_points(), 2))
        return g

    def ensure_key(self, node, pid, value=None):
        """Make sure `node` has a keyform at `value` of `pid` (adds the default key too). Returns binding, index."""
        p = self.param(pid)
        value = self.values.get(pid, p.default) if value is None else value
        b = node.binding(pid, create=True)
        if not b.keys:
            b.add_key(p.default, blank_form(node.n_points()))
        i = b.key_index(value)
        if i is None:
            i = b.add_key(value, self.current_form_for(node, b))
        return b, i

    # ------------------------------------------------------------------ (de)serialisation
    def to_dict(self):
        return {"format": "mu", "version": 1, "name": self.name, "width": self.width, "height": self.height,
                "nodes": [n.to_dict() for n in self.nodes.values()], "params": [p.to_dict() for p in self.params],
                "values": self.values, "physics": [g.to_dict() for g in self.physics], "poses": self.poses,
                "meta": self.meta, "textures": sorted(self.textures),
                "scenes": [{k: v for k, v in sc.items() if not k.startswith("_")} for sc in self.scenes]}

    @classmethod
    def from_dict(cls, d, textures=None):
        m = cls(d.get("name", "Модель"), d.get("width", 1400), d.get("height", 2400))
        for nd in d.get("nodes", []):
            m.add(NODE_TYPES[nd["kind"]].from_dict(nd))
        m.params = [Param.from_dict(p) for p in d.get("params", [])]
        m.reset_values()
        m.values.update({k: v for k, v in d.get("values", {}).items() if m.param(k) is not None})
        m.physics = [PhysGroup.from_dict(g) for g in d.get("physics", [])]
        m.poses = d.get("poses", [])
        m.meta.update(d.get("meta", {}))
        m.scenes = d.get("scenes", [])
        m.textures = dict(textures or {})
        return m

    def state(self):
        """Fast snapshot for undo (no JSON, arrays copied)."""
        return copy.deepcopy({"nodes": list(self.nodes.values()), "params": self.params, "values": self.values,
                              "physics": self.physics, "poses": self.poses, "name": self.name, "meta": self.meta,
                              "scenes": self.scenes, "size": (self.width, self.height),
                              "textures": list(self.textures)})

    def set_state(self, st):
        st = copy.deepcopy(st)
        self.nodes = {n.id: n for n in st["nodes"]}
        self.params = st["params"]
        self.values = st["values"]
        self.physics = st["physics"]
        self.poses = st["poses"]
        self.name = st["name"]
        self.meta = st["meta"]
        self.scenes = st["scenes"]
        self.width, self.height = st["size"]
        self._order_cache = None

    def json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)


def transfer_offsets(old_rest, old_tris, offsets, new_pts):
    """Re-sample a per-vertex field (keyform offsets) after a mesh edit: barycentric inside old triangles,
    nearest old vertex outside."""
    out = np.zeros((len(new_pts), offsets.shape[1]))
    for k, p in enumerate(new_pts):
        done = False
        for t in old_tris:
            a, b, c = old_rest[t[0]], old_rest[t[1]], old_rest[t[2]]
            v0, v1, v2 = b - a, c - a, p - a
            den = v0[0] * v1[1] - v1[0] * v0[1]
            if abs(den) < 1e-9:
                continue
            l1 = (v2[0] * v1[1] - v1[0] * v2[1]) / den
            l2 = (v0[0] * v2[1] - v2[0] * v0[1]) / den
            l0 = 1 - l1 - l2
            if l0 >= -1e-6 and l1 >= -1e-6 and l2 >= -1e-6:
                out[k] = l0 * offsets[t[0]] + l1 * offsets[t[1]] + l2 * offsets[t[2]]
                done = True
                break
        if not done and len(old_rest):
            j = int(np.argmin(((old_rest - p) ** 2).sum(1)))
            out[k] = offsets[j]
    return out


# ====================================================================== standard parameters (Cubism-compatible ids)
STANDARD_PARAMS = [
    ("ParamAngleX", "Поворот головы X", -30, 30, 0, "Голова"),
    ("ParamAngleY", "Поворот головы Y", -30, 30, 0, "Голова"),
    ("ParamAngleZ", "Наклон головы", -30, 30, 0, "Голова"),
    ("ParamEyeLOpen", "Левый глаз открыт", 0, 1.2, 1, "Глаза"),
    ("ParamEyeLSmile", "Левый глаз — улыбка", 0, 1, 0, "Глаза"),
    ("ParamEyeROpen", "Правый глаз открыт", 0, 1.2, 1, "Глаза"),
    ("ParamEyeRSmile", "Правый глаз — улыбка", 0, 1, 0, "Глаза"),
    ("ParamEyeBallX", "Взгляд X", -1, 1, 0, "Глаза"),
    ("ParamEyeBallY", "Взгляд Y", -1, 1, 0, "Глаза"),
    ("ParamBrowLY", "Левая бровь вверх", -1, 1, 0, "Брови"),
    ("ParamBrowRY", "Правая бровь вверх", -1, 1, 0, "Брови"),
    ("ParamBrowLAngle", "Левая бровь — угол", -1, 1, 0, "Брови"),
    ("ParamBrowRAngle", "Правая бровь — угол", -1, 1, 0, "Брови"),
    ("ParamMouthForm", "Форма рта", -1, 1, 0, "Рот"),
    ("ParamMouthOpenY", "Рот открыт", 0, 1, 0, "Рот"),
    ("ParamCheek", "Румянец", 0, 1, 0, "Рот"),
    ("ParamBodyAngleX", "Поворот тела X", -10, 10, 0, "Тело"),
    ("ParamBodyAngleY", "Поворот тела Y", -10, 10, 0, "Тело"),
    ("ParamBodyAngleZ", "Наклон тела", -10, 10, 0, "Тело"),
    ("ParamBreath", "Дыхание", 0, 1, 0, "Тело"),
    ("ParamArmLA", "Левая рука: плечо", -180, 100, 0, "Руки"),
    ("ParamArmLB", "Левая рука: локоть", -160, 160, 0, "Руки"),
    ("ParamHandL", "Левая кисть", -60, 60, 0, "Руки"),
    ("ParamArmRA", "Правая рука: плечо", -100, 180, 0, "Руки"),
    ("ParamArmRB", "Правая рука: локоть", -160, 160, 0, "Руки"),
    ("ParamHandR", "Правая кисть", -60, 60, 0, "Руки"),
    ("ParamLegL", "Левая нога", -45, 45, 0, "Ноги"),
    ("ParamLegR", "Правая нога", -45, 45, 0, "Ноги"),
    ("ParamKneeL", "Левое колено", 0, 90, 0, "Ноги"),
    ("ParamKneeR", "Правое колено", 0, 90, 0, "Ноги"),
    ("ParamHairFront", "Волосы спереди", -1, 1, 0, "Волосы"),
    ("ParamHairSide", "Волосы по бокам", -1, 1, 0, "Волосы"),
    ("ParamHairBack", "Волосы сзади", -1, 1, 0, "Волосы"),
    ("ParamSkirt", "Юбка", -1, 1, 0, "Тело"),
]


def standard_param(pid):
    for row in STANDARD_PARAMS:
        if row[0] == pid:
            return Param(*row)
    return None
