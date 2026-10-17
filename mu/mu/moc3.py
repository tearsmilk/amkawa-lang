"""Experimental export to the Live2D Cubism runtime format: .moc3 + .model3.json + .physics3.json + .cdi3.json +
texture atlases — what VTube Studio and other Cubism-SDK apps load.

The .moc3 layout (MOC3 version 3.00, little-endian) was written from the publicly documented structure of the
format: a 64-byte header, a section offset table, count / canvas info and typed arrays for parts, deformers,
art meshes, parameters, keyforms and keyform bindings. Мю's model maps onto it directly:

* every object's per-parameter bindings become Cubism keyform bindings; an object with several bindings gets
  the full grid of keyforms (the sum of the individual offsets — exactly what Мю evaluates);
* coordinates: root objects in canvas units (pixels / PixelsPerUnit, y down like the editor — the Core flips
  them on output), children of a warp deformer in its 0…1 grid space, children of a rotation deformer in pixels
  around its origin, rotation keyform scales carry the pixel → unit factor;
* every art mesh is double-sided; textures are packed into 2048 / 4096 atlases.

Mu-specific things Cubism has no equivalent for are approximated: blend modes other than add / multiply
become normal. Physics groups become Cubism physics settings (a vertex per chain link, an output per parameter)."""
import itertools
import json
import math
import struct
from pathlib import Path

import numpy as np
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPainter

from .model import ArtMesh, RotationDeformer, WarpDeformer

MOC_VERSION = 1           # 1 = MOC3 3.00 (read by every Cubism 3/4/5 Core)
SOT_COUNT = 160
BODY_OFFSET = 1984        # header 64 + SOT 640 → body starts at the first aligned offset Cubism uses
COUNT_INFO_SIZE = 128
CANVAS_INFO_SIZE = 64
RUNTIME_UNIT = 8
FLIP_Y = False            # stored y-down like the editor; the Core flips to y-up on output
MAX_KEYFORMS = 512        # cap for the keyform grid of a single object

(C_PARTS, C_DEFORMERS, C_WARPS, C_ROTS, C_MESHES, C_PARAMS, C_PART_KF, C_WARP_KF, C_ROT_KF, C_MESH_KF, C_KF_POS,
 C_KB_INDICES, C_KB_BANDS, C_KBS, C_KEYS, C_UVS, C_POS_INDICES, C_MASKS, C_DOGS, C_DOG_OBJECTS, C_GLUES,
 C_GLUE_INFOS, C_GLUE_KF) = range(23)


# ====================================================================== low-level writer
class _Body:
    def __init__(self):
        self.buf = bytearray()
        self.sot = []

    def pad(self, n=64):
        r = len(self.buf) % n
        if r:
            self.buf.extend(b"\0" * (n - r))

    def section(self, kind, data, count=None, align=64):
        """Append one typed array and record its offset in the section table."""
        if align:
            self.pad(align)
        self.sot.append(BODY_OFFSET + len(self.buf))
        if kind == "rt":
            self.buf.extend(b"\0" * (RUNTIME_UNIT * count))
        elif kind == "id":
            for s in data:
                b = s.encode("utf-8")[:63]
                self.buf.extend(b + b"\0" * (64 - len(b)))
        elif kind in ("i32", "bool"):
            self.buf.extend(struct.pack(f"<{len(data)}i", *[int(v) for v in data]))
        elif kind == "f32":
            self.buf.extend(struct.pack(f"<{len(data)}f", *[float(v) for v in data]))
        elif kind == "i16":
            self.buf.extend(struct.pack(f"<{len(data)}h", *[int(v) for v in data]))
        elif kind == "u8":
            self.buf.extend(bytes(int(v) & 0xFF for v in data))
        else:
            raise ValueError(kind)


_TR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
               ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t",
                "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))


def _translit(s):
    out = []
    for ch in s:
        t = _TR.get(ch.lower())
        if t is None:
            out.append(ch)
        else:
            out.append(t.capitalize() if ch.isupper() else t)
    return "".join(out)


def _safe_id(s, prefix, used):
    s = _translit(s)
    base = "".join(c if c.isascii() and (c.isalnum() or c == "_") else "_" for c in s)[:48] or prefix
    if not base[0].isalpha():
        base = prefix + base
    out, i = base, 1
    while out in used:
        i += 1
        out = f"{base}{i}"
    used.add(out)
    return out


# ====================================================================== texture atlas
def pack_atlases(model, meshes, pad=4):
    """2048 atlases when everything fits in one at full resolution, 4096 otherwise."""
    small = _pack(model, meshes, 2048, pad)
    if len(small[0]) == 1 and small[2] >= 0.999:
        return small[:2]
    return _pack(model, meshes, 4096, pad)[:2]


def _pack(model, meshes, max_size, pad):
    """Shelf-pack every mesh texture into ≤ max_size atlases. Returns (atlases [QImage], placement {tex id:
    (atlas index, x, y, scale)})."""
    texs = []
    for m in meshes:
        img = model.textures.get(m.texture)
        if img is not None and m.texture not in [t[0] for t in texs]:
            texs.append((m.texture, img))
    total = sum((i.width() + pad) * (i.height() + pad) for _, i in texs) or 1
    scale = 1.0
    if total > max_size * max_size * 0.8 * 3:      # more than three full atlases: shrink everything
        scale = math.sqrt(max_size * max_size * 0.8 * 3 / total)
    order = sorted(texs, key=lambda t: -t[1].height())
    atlases, place = [], {}
    shelves = []  # per atlas: (x, y, shelf_h)
    for tid, img in order:
        w = max(1, int(img.width() * scale))
        h = max(1, int(img.height() * scale))
        s = scale
        if w + pad > max_size or h + pad > max_size:
            k = (max_size - 2 * pad) / max(w, h)
            w, h, s = max(1, int(w * k)), max(1, int(h * k)), s * k
        for ai, (x, y, sh) in enumerate(shelves):
            if x + w + pad > max_size:
                x, y, sh = 0, y + sh + pad, 0
            if y + h + pad <= max_size:
                place[tid] = (ai, x, y, w / img.width(), h / img.height())
                shelves[ai] = (x + w + pad, y, max(sh, h))
                break
        else:
            shelves.append((w + pad, 0, h))
            place[tid] = (len(shelves) - 1, 0, 0, w / img.width(), h / img.height())
    for ai in range(len(shelves)):
        atlases.append(QImage(max_size, max_size, QImage.Format_ARGB32_Premultiplied))
        atlases[-1].fill(Qt.transparent)
    painters = [QPainter(a) for a in atlases]
    for p in painters:
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    for tid, img in texs:
        ai, x, y, sx, sy = place[tid]
        painters[ai].drawImage(QRect(x, y, max(1, round(img.width() * sx)), max(1, round(img.height() * sy))), img)
    for p in painters:
        p.end()
    min_scale = min([v[3] for v in place.values()] or [1.0])
    return atlases, place, min_scale


# ====================================================================== export
class _Exporter:
    def __init__(self, model):
        self.m = model
        self.ppu = float(max(model.width, model.height))
        self.ox, self.oy = model.width / 2.0, model.height / 2.0

    # ---- coordinate spaces -------------------------------------------------------------------------------
    def to_space(self, parent_id, pts):
        """Rest-frame canvas pixels → the moc3 coordinate space of children of `parent_id`."""
        pts = np.asarray(pts, dtype=float).reshape(-1, 2)
        par = self.m.nodes.get(parent_id) if parent_id else None
        if isinstance(par, WarpDeformer):
            uv = par.uv_of(pts)
            return uv
        if isinstance(par, RotationDeformer):
            loc = pts - np.asarray(par.origin)
            if FLIP_Y:
                loc[:, 1] = -loc[:, 1]
            return loc
        out = np.empty_like(pts)
        out[:, 0] = (pts[:, 0] - self.ox) / self.ppu
        out[:, 1] = ((self.oy - pts[:, 1]) if FLIP_Y else (pts[:, 1] - self.oy)) / self.ppu
        return out

    def rot_out_scale(self, rot):
        """Units of the space a rotation deformer's output lands in, per pixel (Cubism stores that in the
        keyform scale): the root space is canvas units, a rotation's local space is pixels; a warp parent is
        looked through (its children are mapped straight into the warp's own output space)."""
        p = self.m.nodes.get(rot.parent) if rot.parent else None
        while isinstance(p, WarpDeformer):
            p = self.m.nodes.get(p.parent) if p.parent else None
        return 1.0 if isinstance(p, RotationDeformer) else 1.0 / self.ppu

    # ---- keyform grid ------------------------------------------------------------------------------------
    def grid(self, node):
        """[(param id, keys)] of the node's usable bindings and the list of keyform index tuples
        (first binding fastest)."""
        bs = [b for b in node.bindings if b.keys and self.m.param(b.param) is not None]
        total = 1
        kept = []
        for b in bs:
            if total * len(b.keys) > MAX_KEYFORMS:
                continue
            total *= len(b.keys)
            kept.append(b)
        ranges = [range(len(b.keys)) for b in reversed(kept)]
        combos = [tuple(reversed(c)) for c in itertools.product(*ranges)]
        return kept, combos

    @staticmethod
    def combined(node, kept, combo):
        n = node.n_points()
        off = np.zeros((n, 2)) if n else None
        opacity, angle, dx, dy, scale = 1.0, 0.0, 0.0, 0.0, 1.0
        for b, i in zip(kept, combo):
            f = b.forms[i]
            if off is not None and f.get("offsets") is not None and len(f["offsets"]) == n:
                off = off + f["offsets"]
            opacity *= f.get("opacity", 1.0)
            angle += f.get("angle", 0.0)
            dx += f.get("dx", 0.0)
            dy += f.get("dy", 0.0)
            scale *= f.get("scale", 1.0)
        return off, opacity, angle, dx, dy, scale

    def run(self):
        m = self.m
        used = set()
        # objects, parents before children
        order = m.eval_order()
        defs = [n for n in order if isinstance(n, (WarpDeformer, RotationDeformer))]
        warps = [d for d in defs if isinstance(d, WarpDeformer)]
        rots = [d for d in defs if isinstance(d, RotationDeformer)]
        meshes = [n for n in m.nodes.values() if isinstance(n, ArtMesh) and len(n.tris) and m.textures.get(n.texture)
                  is not None]
        dindex = {d.id: i for i, d in enumerate(defs)}
        mindex = {x.id: i for i, x in enumerate(meshes)}
        params = list(m.params)
        pindex = {p.id: i for i, p in enumerate(params)}

        # ---- keyform bindings: unique (param, keys); grouped by parameter
        binding_keys = {}   # (pid, keys tuple) → provisional
        object_bands = {}   # node id → [ (pid, keys) ]
        object_grid = {}
        for node in defs + meshes:
            kept, combos = self.grid(node)
            object_grid[node.id] = (kept, combos)
            object_bands[node.id] = [(b.param, tuple(round(k, 6) for k in b.keys)) for b in kept]
            for key in object_bands[node.id]:
                binding_keys[key] = None
        kb_list = sorted(binding_keys, key=lambda k: (pindex[k[0]], k[1]))
        kb_index = {k: i for i, k in enumerate(kb_list)}
        keys_values, kb_keys_begin, kb_keys_count = [], [], []
        for pid, keys in kb_list:
            kb_keys_begin.append(len(keys_values))
            kb_keys_count.append(len(keys))
            keys_values.extend(keys)
        p_kb_begin, p_kb_count = [], []
        for p in params:
            idx = [i for i, k in enumerate(kb_list) if k[0] == p.id]
            p_kb_begin.append(idx[0] if idx else 0)
            p_kb_count.append(len(idx))
        bands, band_index, kbi = [], {}, []

        def band_of(node_id):
            key = tuple(kb_index[k] for k in object_bands.get(node_id, []))
            if key not in band_index:
                band_index[key] = len(bands)
                bands.append((len(kbi), len(key)))
                kbi.extend(key)
            return band_index[key]
        part_band = band_of("__part__")

        # ---- deformers / keyforms / positions
        kf_pos = []

        def push_positions(xy):
            begin = len(kf_pos)
            flat = np.asarray(xy, dtype=float).reshape(-1).tolist()
            kf_pos.extend(flat)
            pad = (-len(flat)) % 16
            kf_pos.extend([0.0] * pad)
            return begin

        def_ids, def_band, def_vis, def_en, def_ppart, def_pdef, def_type, def_spec = [], [], [], [], [], [], [], []
        w_band, w_kb, w_kc, w_vc, w_rows, w_cols = [], [], [], [], [], []
        r_band, r_kb, r_kc, r_base = [], [], [], []
        wkf_op, wkf_pos = [], []
        rkf = {k: [] for k in ("op", "ang", "ox", "oy", "sc", "rx", "ry")}
        warp_specific = {d.id: i for i, d in enumerate(warps)}
        rot_specific = {d.id: i for i, d in enumerate(rots)}
        for d in defs:
            def_ids.append(_safe_id(d.name, "Deformer", used))
            b = band_of(d.id)
            def_band.append(b)
            def_vis.append(1 if d.visible else 0)
            def_en.append(1)
            def_ppart.append(0)
            def_pdef.append(dindex.get(d.parent, -1) if d.parent else -1)
            kept, combos = object_grid[d.id]
            if isinstance(d, WarpDeformer):
                def_type.append(0)
                def_spec.append(warp_specific[d.id])
                w_band.append(b)
                w_kb.append(len(wkf_op))
                w_kc.append(len(combos))
                w_vc.append(d.n_points())
                w_rows.append(d.rows)
                w_cols.append(d.cols)
                rest = d.rest_grid()
                for c in combos:
                    off, op, *_ = self.combined(d, kept, c)
                    pts = rest + (off if off is not None else 0)
                    wkf_op.append(op)
                    wkf_pos.append(push_positions(self.to_space(d.parent, pts)))
            else:
                def_type.append(1)
                def_spec.append(rot_specific[d.id])
                r_band.append(b)
                r_kb.append(len(rkf["op"]))
                r_kc.append(len(combos))
                r_base.append(0.0)
                unit = self.rot_out_scale(d)
                for c in combos:
                    _off, op, ang, dx, dy, sc = self.combined(d, kept, c)
                    o = self.to_space(d.parent, [[d.origin[0] + dx, d.origin[1] + dy]])[0]
                    rkf["op"].append(op)
                    rkf["ang"].append(-ang if FLIP_Y else ang)
                    rkf["ox"].append(o[0])
                    rkf["oy"].append(o[1])
                    rkf["sc"].append(sc * unit)
                    rkf["rx"].append(0)
                    rkf["ry"].append(0)

        # ---- art meshes
        atlases, place = pack_atlases(m, meshes)
        ranked = sorted(meshes, key=lambda x: x.order)
        n_m = max(1, len(meshes))
        draw_order = {x.id: (round(100 + 800 * r / n_m) if n_m <= 800 else r) for r, x in enumerate(ranked)}
        am = {k: [] for k in ("ids", "band", "kb", "kc", "vis", "en", "ppart", "pdef", "tex", "flags", "vc", "uvb",
                               "pib", "pic", "mb", "mc")}
        mkf_op, mkf_do, mkf_pos = [], [], []
        uvs, pidx, masks = [], [], []
        for x in meshes:
            am["ids"].append(_safe_id(x.name, "ArtMesh", used))
            b = band_of(x.id)
            am["band"].append(b)
            kept, combos = object_grid[x.id]
            am["kb"].append(len(mkf_op))
            am["kc"].append(len(combos))
            am["vis"].append(1 if x.visible else 0)
            am["en"].append(1)
            am["ppart"].append(0)
            am["pdef"].append(dindex.get(x.parent, -1) if x.parent else -1)
            ai, tx, ty, sx, sy = place[x.texture]
            img = m.textures[x.texture]
            aw = atlases[ai].width()
            am["tex"].append(ai)
            flags = 4  # double-sided
            if x.blend == "add":
                flags |= 1
            elif x.blend == "multiply":
                flags |= 2
            if x.masks and x.invert_mask:
                flags |= 8
            am["flags"].append(flags)
            am["vc"].append(len(x.rest))
            am["uvb"].append(len(uvs))
            for u, v in x.uvs:
                au = (tx + u * img.width() * sx) / aw
                av = (ty + v * img.height() * sy) / aw
                uvs.extend([au, av])
            am["pib"].append(len(pidx))
            tris = x.tris.reshape(-1).tolist()
            am["pic"].append(len(tris))
            pidx.extend(tris)
            mk = [mindex[i] for i in x.masks if i in mindex]
            am["mb"].append(len(masks))
            am["mc"].append(len(mk))
            masks.extend(mk)
            for c in combos:
                off, op, *_ = self.combined(x, kept, c)
                pts = x.rest + (off if off is not None else 0)
                mkf_op.append(op * x.opacity)
                mkf_do.append(draw_order[x.id])
                mkf_pos.append(push_positions(self.to_space(x.parent, pts)))
        if len(pidx) and max(pidx) > 32767:
            raise ValueError("Слишком плотная сетка для .moc3 (больше 32767 вершин в одном слое)")

        # ---- draw order group: one group with every art mesh
        dog_objects = [mindex[x.id] for x in sorted(meshes, key=lambda x: x.order)]

        counts = [0] * 23
        counts[C_PARTS] = 1
        counts[C_DEFORMERS] = len(defs)
        counts[C_WARPS] = len(warps)
        counts[C_ROTS] = len(rots)
        counts[C_MESHES] = len(meshes)
        counts[C_PARAMS] = len(params)
        counts[C_PART_KF] = 1
        counts[C_WARP_KF] = len(wkf_op)
        counts[C_ROT_KF] = len(rkf["op"])
        counts[C_MESH_KF] = len(mkf_op)
        counts[C_KF_POS] = len(kf_pos)
        counts[C_KB_INDICES] = len(kbi)
        counts[C_KB_BANDS] = len(bands)
        counts[C_KBS] = len(kb_list)
        counts[C_KEYS] = len(keys_values)
        counts[C_UVS] = len(uvs)
        counts[C_POS_INDICES] = len(pidx)
        counts[C_MASKS] = len(masks)
        counts[C_DOGS] = 1
        counts[C_DOG_OBJECTS] = len(dog_objects)

        B = _Body()
        B.sot.append(BODY_OFFSET)
        B.buf.extend(struct.pack("<23i", *counts))
        B.pad(COUNT_INFO_SIZE)
        B.sot.append(BODY_OFFSET + len(B.buf))
        B.buf.extend(struct.pack("<5fB", self.ppu, self.ox, self.oy, float(m.width), float(m.height), 0))
        B.pad(CANVAS_INFO_SIZE)
        n_p = 1
        # parts
        B.section("rt", None, n_p)
        B.section("id", ["PartRoot"], align=0)
        B.section("i32", [part_band])
        B.section("i32", [0])
        B.section("i32", [1])
        B.section("bool", [1])
        B.section("bool", [1])
        B.section("i32", [-1])
        # deformers
        B.section("rt", None, len(defs))
        B.section("id", def_ids, align=0)
        B.section("i32", def_band)
        B.section("bool", def_vis)
        B.section("bool", def_en)
        B.section("i32", def_ppart)
        B.section("i32", def_pdef)
        B.section("i32", def_type)
        B.section("i32", def_spec)
        # warp deformers
        for arr in (w_band, w_kb, w_kc, w_vc, w_rows, w_cols):
            B.section("i32", arr)
        # rotation deformers
        for arr in (r_band, r_kb, r_kc):
            B.section("i32", arr)
        B.section("f32", r_base)
        # art meshes
        for _ in range(4):
            B.section("rt", None, len(meshes))
        B.section("id", am["ids"], align=0)
        for k in ("band", "kb", "kc"):
            B.section("i32", am[k])
        B.section("bool", am["vis"])
        B.section("bool", am["en"])
        for k in ("ppart", "pdef", "tex"):
            B.section("i32", am[k])
        B.section("u8", am["flags"])
        for k in ("vc", "uvb", "pib", "pic", "mb", "mc"):
            B.section("i32", am[k])
        # parameters
        B.section("rt", None, len(params))
        B.section("id", [p.id for p in params], align=0)
        B.section("f32", [p.max for p in params])
        B.section("f32", [p.min for p in params])
        B.section("f32", [p.default for p in params])
        B.section("bool", [0] * len(params))
        B.section("i32", [3] * len(params))
        B.section("i32", p_kb_begin)
        B.section("i32", p_kb_count)
        # keyforms
        B.section("f32", [500.0])
        B.section("f32", wkf_op)
        B.section("i32", wkf_pos)
        for k in ("op", "ang", "ox", "oy", "sc"):
            B.section("f32", rkf[k])
        B.section("bool", rkf["rx"])
        B.section("bool", rkf["ry"])
        B.section("f32", mkf_op)
        B.section("f32", mkf_do)
        B.section("i32", mkf_pos)
        B.section("f32", kf_pos)
        B.section("i32", kbi)
        B.section("i32", [b[0] for b in bands])
        B.section("i32", [b[1] for b in bands])
        B.section("i32", kb_keys_begin)
        B.section("i32", kb_keys_count)
        B.section("f32", keys_values)
        B.section("f32", uvs)
        B.section("i16", pidx)
        B.section("i32", masks)
        # draw order group
        B.section("i32", [0])
        B.section("i32", [len(dog_objects)])
        B.section("i32", [len(dog_objects)])
        B.section("i32", [1000])
        B.section("i32", [0])
        B.section("i32", [0] * len(dog_objects))
        B.section("i32", dog_objects)
        B.section("i32", [-1] * len(dog_objects))
        # glues (none)
        B.section("rt", None, 0)
        B.section("id", [], align=0)
        for _ in range(7):
            B.section("i32", [])
        B.section("f32", [])
        B.section("i16", [])
        B.section("f32", [])
        B.pad(64)

        head = bytearray(b"MOC3" + bytes([MOC_VERSION, 0]))
        head.extend(b"\0" * (64 - len(head)))
        sot = B.sot + [0] * (SOT_COUNT - len(B.sot))
        head.extend(struct.pack(f"<{SOT_COUNT}I", *sot[:SOT_COUNT]))
        head.extend(b"\0" * (BODY_OFFSET - len(head)))
        self.ids = {"meshes": am["ids"], "deformers": def_ids}
        return bytes(head) + bytes(B.buf), atlases


def physics3(model):
    """Cubism physics: one setting per group, a vertex per chain link, an output per parameter."""
    settings, names, n_in, n_out, n_v = [], [], 0, 0, 0
    for g in model.physics:
        outs = [o for o in g.out_list() if model.param(o.get("param")) is not None]
        if not outs or not g.enabled:
            continue
        sid = f"PhysicsSetting{len(settings) + 1}"
        names.append({"Id": sid, "Name": g.name})
        inputs = []
        for inp in g.inputs:
            if model.param(inp.get("param")) is None:
                continue
            inputs.append({"Source": {"Target": "Parameter", "Id": inp["param"]},
                           "Weight": round(min(100.0, 100 * inp.get("weight", 1.0)), 1),
                           "Type": "Angle" if inp.get("kind") == "angle" else "X", "Reflect": False})
        # softer springs swing longer: map Мю's stiffness / damping onto the pendulum's delay / mobility
        delay = max(0.5, min(1.2, 0.6 + 12.0 / max(10.0, g.stiffness)))
        mobility = max(0.8, min(0.98, 1.0 - g.damping / 80.0))
        n = max(1, int(g.segments))
        seg = (3 + 6 * g.gravity) / n
        vertices = [{"Position": {"X": 0, "Y": 0}, "Mobility": 1, "Delay": 1, "Acceleration": 1, "Radius": 0}]
        for i in range(1, n + 1):
            vertices.append({"Position": {"X": 0, "Y": round(seg * i, 3)}, "Mobility": round(mobility, 3),
                             "Delay": round(delay, 3), "Acceleration": 1.5, "Radius": round(seg, 3)})
        outputs = []
        for o in outs:
            p = model.param(o["param"])
            span = max(abs(p.max - p.default), abs(p.min - p.default)) or 1.0
            outputs.append({"Destination": {"Target": "Parameter", "Id": p.id},
                            "VertexIndex": max(1, min(n, int(o.get("vertex", n)))),
                            "Scale": round(1.5 * g.scale * float(o.get("scale", 1.0)) * span, 3), "Weight": 100,
                            "Type": "X" if o.get("kind") == "x" else "Angle", "Reflect": False})
        settings.append({
            "Id": sid, "Input": inputs, "Output": outputs, "Vertices": vertices,
            "Normalization": {"Position": {"Minimum": -10, "Default": 0, "Maximum": 10},
                              "Angle": {"Minimum": -10, "Default": 0, "Maximum": 10}}})
        n_in += len(inputs)
        n_out += len(outputs)
        n_v += len(vertices)
    return {"Version": 3,
            "Meta": {"PhysicsSettingCount": len(settings), "TotalInputCount": n_in, "TotalOutputCount": n_out,
                     "VertexCount": n_v, "EffectiveForces": {"Gravity": {"X": 0, "Y": -1}, "Wind": {"X": 0, "Y": 0}},
                     "PhysicsDictionary": names},
            "PhysicsSettings": settings}


def export_moc3(model, folder, name=None):
    """Write <folder>/<name>.moc3, .model3.json, .physics3.json, .cdi3.json and <name>.<size>/texture_NN.png.
    Returns the path of the .model3.json (the file VTube Studio imports)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    name = name or _safe_id(model.name, "Model", set()) or "Model"
    ex = _Exporter(model)
    data, atlases = ex.run()
    (folder / f"{name}.moc3").write_bytes(data)
    tex_dir = f"{name}.{atlases[0].width() if atlases else 2048}"
    (folder / tex_dir).mkdir(exist_ok=True)
    tex_files = []
    for i, a in enumerate(atlases):
        rel = f"{tex_dir}/texture_{i:02d}.png"
        a.convertToFormat(QImage.Format_ARGB32).save(str(folder / rel), "PNG")
        tex_files.append(rel)
    refs = {"Moc": f"{name}.moc3", "Textures": tex_files}
    phys = physics3(model)
    if phys["PhysicsSettings"]:
        (folder / f"{name}.physics3.json").write_text(json.dumps(phys, ensure_ascii=False, indent="\t"), "utf-8")
        refs["Physics"] = f"{name}.physics3.json"
    cdi = {"Version": 3,
           "Parameters": [{"Id": p.id, "GroupId": "", "Name": p.name} for p in model.params],
           "ParameterGroups": [], "Parts": [{"Id": "PartRoot", "Name": model.name}]}
    (folder / f"{name}.cdi3.json").write_text(json.dumps(cdi, ensure_ascii=False, indent="\t"), "utf-8")
    refs["DisplayInfo"] = f"{name}.cdi3.json"
    groups = [{"Target": "Parameter", "Name": "EyeBlink",
               "Ids": [p for p in ("ParamEyeLOpen", "ParamEyeROpen") if model.param(p) is not None]},
              {"Target": "Parameter", "Name": "LipSync",
               "Ids": [p for p in ("ParamMouthOpenY",) if model.param(p) is not None]}]
    m3 = {"Version": 3, "FileReferences": refs, "Groups": groups}
    path = folder / f"{name}.model3.json"
    path.write_text(json.dumps(m3, ensure_ascii=False, indent="\t"), "utf-8")
    return path
