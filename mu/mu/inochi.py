"""Inochi2D puppets (.inp / .inx, format of Inochi2D 0.8 — Inochi Creator / Inochi Session, an open VTuber
pipeline with webcam tracking).

Export bakes Мю's deformer rig into what Inochi stores per part: for every parameter key, the vertex offsets
of each affected part (other parameters at rest) plus opacity multipliers; hair physics becomes SimplePhysics
pendulums hanging from a «head motion» node. Import reads parts (meshes, UVs, textures — PNG or TGA),
node transforms, masks, deform / opacity / translation bindings of 1D and 2D parameters."""
import json
import math
import random
import struct

import numpy as np
from PySide6.QtGui import QImage

from .fileio import png_bytes
from .mesh import auto_mesh  # noqa: F401  (kept for parity with PSD import helpers)
from .model import ArtMesh, Binding, Model, Param, PhysGroup, blank_form

MAGIC = b"TRNSRTS\0"
NO_TEXTURE = 4294967295
INOCHI_VERSION = "v0.8.6"


# ====================================================================== export
def _uid(rng, used):
    while True:
        u = rng.randrange(1, 2 ** 32 - 2)
        if u not in used:
            used.add(u)
            return u


def _flat(arr):
    return [round(float(v), 4) for v in np.asarray(arr, dtype=float).ravel()]


def export_inp(model, path, include_physics=True):
    rng = random.Random(42)
    used = set()
    cx, cy = model.width / 2, model.height / 2
    meshes = [m for m in sorted(model.meshes(), key=lambda m: m.order) if len(m.tris)]
    rest_vals = {p.id: p.default for p in model.params}
    base = model.evaluate(rest_vals)
    uuids = {m.id: _uid(rng, used) for m in meshes}

    # textures: one slot per part texture
    tex_slots = []
    tex_index = {}
    for m in meshes:
        if m.texture not in tex_index and m.texture in model.textures:
            tex_index[m.texture] = len(tex_slots)
            tex_slots.append(model.textures[m.texture])

    n = len(meshes)
    parts = []
    for rank, m in enumerate(meshes):
        verts = base.meshes[m.id][0] - [cx, cy]
        node = {"uuid": uuids[m.id], "name": m.name, "type": "Part", "enabled": bool(m.visible),
                "zsort": float(n - rank),
                "transform": {"trans": [0.0, 0.0, 0.0], "rot": [0.0, 0.0, 0.0], "scale": [1.0, 1.0]},
                "lockToRoot": False,
                "mesh": {"verts": _flat(verts), "uvs": _flat(m.uvs), "indices": [int(i) for i in m.tris.ravel()],
                         "origin": [0.0, 0.0]},
                "textures": [tex_index.get(m.texture, NO_TEXTURE), NO_TEXTURE, NO_TEXTURE],
                "blend_mode": {"normal": "Normal", "add": "LinearDodge", "multiply": "Multiply",
                               "screen": "Screen"}.get(m.blend, "Normal"),
                "tint": [1.0, 1.0, 1.0], "screenTint": [0.0, 0.0, 0.0], "emissionStrength": 1.0,
                "mask_threshold": 0.5, "opacity": float(m.opacity)}
        masks = [{"source": uuids[k], "mode": "DodgeMask" if m.invert_mask else "Mask"} for k in m.masks if k in uuids]
        if masks:
            node["masks"] = masks
        parts.append(node)

    # parameters: bake every key of every parameter (the others at rest)
    params_out = []
    head_node = {"uuid": _uid(rng, used), "name": "Движение головы (для физики)", "type": "Node", "enabled": True,
                 "zsort": 0.0, "transform": {"trans": [0.0, -cy * 0.45, 0.0], "rot": [0.0, 0.0, 0.0], "scale": [1.0, 1.0]},
                 "lockToRoot": False, "children": []}
    phys_outputs = {g.output for g in model.physics} if include_physics else set()
    for p in model.params:
        keys = set()
        for node in model.nodes.values():
            b = node.binding(p.id)
            if b is not None:
                keys.update(b.keys)
        if not keys:
            continue
        keys.update([p.min, p.max, p.default])
        keys = sorted(k for k in keys if p.min <= k <= p.max)
        # rotations baked into vertex offsets interpolate linearly, so add keys every ~1/12 of the range
        if _rotates(model, p.id):
            step = (p.max - p.min) / 12
            dense = set(keys)
            for a, b in zip(keys, keys[1:]):
                n_mid = int((b - a) / step)
                for j in range(1, n_mid + 1):
                    dense.add(round(a + (b - a) * j / (n_mid + 1), 4))
            keys = sorted(dense)
        span = (p.max - p.min) or 1.0
        bindings = []
        frames = []
        for k in keys:
            vals = dict(rest_vals)
            vals[p.id] = k
            frames.append(model.evaluate(vals))
        for m in meshes:
            offs = [frames[i].meshes[m.id][0] - base.meshes[m.id][0] for i in range(len(keys))]
            if max(float(np.abs(o).max()) if len(o) else 0.0 for o in offs) > 0.05:
                bindings.append({"node": uuids[m.id], "param_name": "deform",
                                 "values": [[[[round(float(x), 3), round(float(y), 3)] for x, y in o]] for o in offs],
                                 "isSet": [[True] for _ in keys], "interpolate_mode": "Linear"})
            base_op = base.meshes[m.id][1]
            if base_op > 1e-6:
                ops = [frames[i].meshes[m.id][1] / base_op for i in range(len(keys))]
                emit = max(abs(o - 1.0) for o in ops) > 1e-3
            else:  # hidden at rest: only the parameter that reveals it gets an (absolute) opacity binding
                ops = [frames[i].meshes[m.id][1] for i in range(len(keys))]
                emit = max(ops) > 1e-3
            if emit:
                bindings.append({"node": uuids[m.id], "param_name": "opacity",
                                 "values": [[round(float(o), 4)] for o in ops], "isSet": [[True] for _ in keys],
                                 "interpolate_mode": "Linear"})
        uid = _uid(rng, used)
        p._inp_uuid = uid
        if p.id in ("ParamAngleX", "ParamAngleY", "ParamAngleZ"):  # drive the physics anchor like the head
            prop, amp = {"ParamAngleX": ("transform.t.x", 60.0), "ParamAngleY": ("transform.t.y", -40.0),
                         "ParamAngleZ": ("transform.r.z", math.radians(16))}[p.id]
            bindings.append({"node": head_node["uuid"], "param_name": prop,
                             "values": [[round(amp * (k - p.default) / max(abs(p.max - p.default), 1e-6), 4)]
                                        for k in keys],
                             "isSet": [[True] for _ in keys], "interpolate_mode": "Linear"})
        if not bindings and p.id not in phys_outputs:
            continue
        params_out.append({"uuid": uid, "name": p.id, "is_vec2": False, "min": [p.min, 0.0], "max": [p.max, 1.0],
                           "defaults": [p.default, 0.0],
                           "axis_points": [[round((k - p.min) / span, 6) for k in keys], [0.0]],
                           "merge_mode": "Additive", "bindings": bindings})

    if include_physics:
        for g in model.physics:
            out = model.param(g.output)
            if out is None or not hasattr(out, "_inp_uuid"):
                continue
            span = max(abs(out.max - out.default), abs(out.min - out.default)) or 1.0
            head_node["children"].append({
                "uuid": _uid(rng, used), "name": "Физика: " + g.name, "type": "SimplePhysics", "enabled": True,
                "zsort": 0.0, "transform": {"trans": [0.0, 0.0, 0.0], "rot": [0.0, 0.0, 0.0], "scale": [1.0, 1.0]},
                "lockToRoot": False, "param": out._inp_uuid, "model_type": "pendulum", "map_mode": "angle_length",
                "gravity": 1.0, "length": 120.0, "frequency": round(0.6 + g.stiffness / 80, 3),
                "angle_damping": round(min(1.0, g.damping / 10), 3), "length_damping": 0.5,
                "output_scale": [round(5.0 * g.scale * span, 3), 1.0], "local_only": False})
    for p in model.params:
        if hasattr(p, "_inp_uuid"):
            del p._inp_uuid

    root_children = parts + ([head_node] if head_node["children"] or include_physics else [])
    puppet = {
        "meta": {"name": model.name, "version": INOCHI_VERSION, "rigger": "Мю", "artist": model.meta.get("author", ""),
                 "rights": None, "copyright": "", "licenseURL": "", "contact": "", "reference": "",
                 "thumbnailId": NO_TEXTURE, "preservePixels": False},
        "physics": {"pixelsPerMeter": 1000.0, "gravity": 9.8},
        "nodes": {"uuid": _uid(rng, used), "name": "Root", "type": "Node", "enabled": True, "zsort": 0.0,
                  "transform": {"trans": [0.0, 0.0, 0.0], "rot": [0.0, 0.0, 0.0], "scale": [1.0, 1.0]},
                  "lockToRoot": False, "children": root_children},
        "param": params_out, "automation": None, "animations": None, "groups": []}
    js = json.dumps(puppet, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with open(path, "wb") as f:
        f.write(MAGIC)
        f.write(struct.pack(">I", len(js)))
        f.write(js)
        f.write(b"TEX_SECT")
        f.write(struct.pack(">I", len(tex_slots)))
        for img in tex_slots:
            data = png_bytes(img)
            f.write(struct.pack(">I", len(data)))
            f.write(bytes([0]))  # 0 = PNG
            f.write(data)
    return {"parts": len(parts), "params": len(params_out), "textures": len(tex_slots)}


# ====================================================================== import
def decode_tga(data):
    idlen, cmtype, itype = data[0], data[1], data[2]
    w, h = struct.unpack("<HH", data[12:16])
    bpp, desc = data[16], data[17]
    if cmtype != 0 or itype not in (2, 10, 3, 11) or bpp not in (8, 24, 32):
        return QImage()
    bpp_b = bpp // 8
    pos = 18 + idlen
    n = w * h
    if itype in (2, 3):
        raw = data[pos:pos + n * bpp_b]
    else:
        out = bytearray()
        need = n * bpp_b
        mv = memoryview(data)
        while len(out) < need and pos < len(data):
            hdr = data[pos]
            pos += 1
            count = (hdr & 0x7F) + 1
            if hdr & 0x80:
                out += bytes(mv[pos:pos + bpp_b]) * count
                pos += bpp_b
            else:
                out += mv[pos:pos + count * bpp_b]
                pos += count * bpp_b
        raw = bytes(out[:need])
    arr = np.frombuffer(raw, dtype=np.uint8)
    if bpp_b == 1:
        arr = np.repeat(arr.reshape(h, w, 1), 3, axis=2)
        arr = np.dstack([arr, np.full((h, w), 255, np.uint8)])
    elif bpp_b == 3:
        arr = arr.reshape(h, w, 3)[:, :, ::-1]
        arr = np.dstack([arr, np.full((h, w), 255, np.uint8)])
    else:
        arr = arr.reshape(h, w, 4)[:, :, [2, 1, 0, 3]]
    if not (desc & 0x20):  # bottom-left origin
        arr = arr[::-1]
    arr = np.ascontiguousarray(arr)
    img = QImage(arr.data, w, h, w * 4, QImage.Format_RGBA8888).copy()
    return img.convertToFormat(QImage.Format_ARGB32_Premultiplied)


def read_inp(path):
    data = open(path, "rb").read()
    if data[:8] != MAGIC:
        raise ValueError("Это не модель Inochi2D (.inp / .inx)")
    n = struct.unpack(">I", data[8:12])[0]
    puppet = json.loads(data[12:12 + n].decode("utf-8"))
    off = 12 + n
    textures = []
    if data[off:off + 8] == b"TEX_SECT":
        count = struct.unpack(">I", data[off + 8:off + 12])[0]
        off += 12
        for _ in range(count):
            ln = struct.unpack(">I", data[off:off + 4])[0]
            kind = data[off + 4]
            blob = data[off + 5:off + 5 + ln]
            off += 5 + ln
            img = QImage.fromData(blob)
            if img.isNull() and kind == 1:
                img = decode_tga(blob)
            textures.append(img.convertToFormat(QImage.Format_ARGB32_Premultiplied) if not img.isNull() else None)
    return puppet, textures


def _mat(tr):
    t = tr.get("trans", [0, 0, 0])
    r = tr.get("rot", [0, 0, 0])
    s = tr.get("scale", [1, 1])
    c, si = math.cos(r[2] if len(r) > 2 else 0.0), math.sin(r[2] if len(r) > 2 else 0.0)
    return np.array([[c * s[0], -si * s[1], t[0]], [si * s[0], c * s[1], t[1]], [0, 0, 1.0]])


def import_inp(path):
    puppet, textures = read_inp(path)
    meta = puppet.get("meta") or {}
    parts = []      # (node, world matrix, descendants-of uuids chain)
    nodes_by_uuid = {}
    parents = {}

    def walk(node, M, chain):
        Mi = M @ _mat(node.get("transform") or {})
        nodes_by_uuid[node.get("uuid")] = (node, Mi)
        if node.get("type") in ("Part", "AnimatedPart") and node.get("mesh") and node.get("enabled", True) is not None:
            parts.append((node, Mi, list(chain)))
        for c in node.get("children") or []:
            parents[c.get("uuid")] = node.get("uuid")
            walk(c, Mi, chain + [node.get("uuid")])
    walk(puppet.get("nodes") or {}, np.eye(3), [])
    if not parts:
        raise ValueError("В модели нет частей")
    world = []
    for node, M, chain in parts:
        v = np.asarray(node["mesh"].get("verts", []), dtype=float).reshape(-1, 2)
        o = np.asarray(node["mesh"].get("origin", [0, 0]), dtype=float)
        pts = (M @ np.vstack([(v - o).T, np.ones(len(v))]))[:2].T
        world.append(pts)
    allp = np.vstack(world)
    lo, hi = allp.min(0), allp.max(0)
    pad = 60.0
    W, H = int(hi[0] - lo[0] + 2 * pad), int(hi[1] - lo[1] + 2 * pad)
    shift = pad - lo
    model = Model(meta.get("name") or "Inochi2D", W, H)
    model.meta["author"] = meta.get("artist", "")
    model.meta["source"] = "Inochi2D " + str(meta.get("version", ""))
    for i, img in enumerate(textures):
        if img is not None:
            model.textures[f"inp{i}"] = img
    order = sorted(range(len(parts)), key=lambda i: -float(parts[i][0].get("zsort", 0)))
    by_uuid = {}
    for rank, i in enumerate(order):
        node, M, chain = parts[i]
        mesh = node["mesh"]
        uvs = np.asarray(mesh.get("uvs", []), dtype=float).reshape(-1, 2)
        tris = np.asarray(mesh.get("indices", []), dtype=np.int32).reshape(-1, 3)
        tex = (node.get("textures") or [NO_TEXTURE])[0]
        m = ArtMesh(name=node.get("name", "Часть"), texture=f"inp{tex}" if f"inp{tex}" in model.textures else None,
                    rest=world[i] + shift, uvs=uvs, tris=tris, order=rank * 10)
        m.opacity = float(node.get("opacity", 1.0))
        m.visible = bool(node.get("enabled", True))
        m._lin = M[:2, :2]
        m._chain = chain + [node.get("uuid")]
        m._origin = (M @ np.array([0, 0, 1.0]))[:2] + shift
        model.add(m)
        by_uuid[node.get("uuid")] = m
    for node, M, chain in parts:
        m = by_uuid.get(node.get("uuid"))
        for mk in node.get("masks") or []:
            src = by_uuid.get(mk.get("source"))
            if src is not None:
                m.masks.append(src.id)
                if mk.get("mode") == "DodgeMask":
                    m.invert_mask = True

    def interp_fill(vals, isset):
        """Fill unset keypoints from the nearest set neighbours (linear)."""
        idx = [i for i, s in enumerate(isset) if s]
        if not idx:
            return None
        out = []
        for i in range(len(vals)):
            if isset[i]:
                out.append(vals[i])
                continue
            lo_ = max([j for j in idx if j < i], default=None)
            hi_ = min([j for j in idx if j > i], default=None)
            if lo_ is None or hi_ is None:
                out.append(vals[lo_ if hi_ is None else hi_])
            else:
                t = (i - lo_) / (hi_ - lo_)
                a, b = np.asarray(vals[lo_], dtype=float), np.asarray(vals[hi_], dtype=float)
                out.append(a * (1 - t) + b * t)
        return out

    def targets_of(uuid):
        if uuid in by_uuid:
            return [by_uuid[uuid]]
        return [m for m in by_uuid.values() if uuid in m._chain]

    for prm in puppet.get("param") or []:
        name = prm.get("name") or "Параметр"
        vec2 = bool(prm.get("is_vec2"))
        mn = prm.get("min", [0, 0])
        mx = prm.get("max", [1, 1])
        df = prm.get("defaults", [0, 0])
        ax = prm.get("axis_points") or [[0, 1], [0]]
        axes = [0, 1] if vec2 else [0]
        for a in axes:
            pid = _safe_id(name + ("_X" if (vec2 and a == 0) else ("_Y" if vec2 else "")))
            label = name + (" X" if (vec2 and a == 0) else (" Y" if vec2 else ""))
            P = Param(pid, label, mn[a], mx[a], df[a], "Inochi2D")
            if P.max <= P.min:
                P.max = P.min + 1
            model.add_param(P)
            keys = [P.min + t * (P.max - P.min) for t in ax[a]]
            other = 1 - a
            if vec2:
                dn = (df[other] - mn[other]) / ((mx[other] - mn[other]) or 1)
                fix = int(np.argmin([abs(t - dn) for t in ax[other]]))
            else:
                fix = 0
            for b in prm.get("bindings") or []:
                pname = b.get("param_name")
                vals = b.get("values") or []
                isset = b.get("isSet") or []
                try:
                    if a == 0:
                        line = [vals[i][fix] for i in range(len(ax[0]))]
                        sline = [isset[i][fix] if isset else True for i in range(len(ax[0]))]
                    else:
                        line = [vals[fix][j] for j in range(len(ax[1]))]
                        sline = [isset[fix][j] if isset else True for j in range(len(ax[1]))]
                except (IndexError, TypeError):
                    continue
                line = interp_fill(line, sline)
                if line is None:
                    continue
                for m in targets_of(b.get("node")):
                    bind = m.binding(pid, create=True)
                    for k, v in zip(keys, line):
                        idx = bind.key_index(k)
                        form = bind.forms[idx] if idx is not None else blank_form(len(m.rest))
                        if form.get("offsets") is None:
                            form["offsets"] = np.zeros((len(m.rest), 2))
                        if pname == "deform" and b.get("node") == _uuid_of(m, by_uuid):
                            arr = np.asarray(v, dtype=float).reshape(-1, 2)
                            if len(arr) == len(m.rest):
                                form["offsets"] = form["offsets"] + arr @ m._lin.T
                        elif pname in ("transform.t.x", "transform.t.y"):
                            d = np.array([float(v), 0.0] if pname.endswith("x") else [0.0, float(v)])
                            node_lin = nodes_by_uuid.get(b.get("node"), (None, np.eye(3)))[1][:2, :2]
                            form["offsets"] = form["offsets"] + d @ node_lin.T
                        elif pname == "transform.r.z":
                            node_M = nodes_by_uuid.get(b.get("node"), (None, np.eye(3)))[1]
                            o = (node_M @ np.array([0, 0, 1.0]))[:2] + shift
                            c, s = math.cos(float(v)), math.sin(float(v))
                            d = m.rest - o
                            form["offsets"] = form["offsets"] + np.stack(
                                [c * d[:, 0] - s * d[:, 1], s * d[:, 0] + c * d[:, 1]], axis=1) - d
                        elif pname == "opacity" and b.get("node") == _uuid_of(m, by_uuid):
                            form["opacity"] = float(v)
                        if idx is None:
                            bind.add_key(k, form)
    # physics pendulums → physics groups driven by head-like parameters
    head_inputs = [p for p in model.params if any(s in p.id.lower() for s in ("yaw", "anglex", "head_x", "head"))][:2]
    for uuid, (node, M) in nodes_by_uuid.items():
        if node.get("type") == "SimplePhysics":
            target = next((p for p in puppet.get("param") or [] if p.get("uuid") == node.get("param")), None)
            if target is None:
                continue
            pid = _safe_id(target.get("name", "") + ("_X" if target.get("is_vec2") else ""))
            if model.param(pid) is None:
                continue
            model.physics.append(PhysGroup(name=node.get("name", "Физика"),
                                           inputs=[{"param": p.id, "weight": 0.6, "kind": "x"} for p in head_inputs],
                                           output=pid))
    for m in model.meshes():
        for attr in ("_lin", "_chain", "_origin"):
            if hasattr(m, attr):
                delattr(m, attr)
    model.reset_values()
    return model


def _rotates(model, pid):
    from .model import RotationDeformer
    return any(isinstance(n, RotationDeformer) and n.binding(pid) is not None for n in model.nodes.values())


def _uuid_of(mesh, by_uuid):
    for k, v in by_uuid.items():
        if v is mesh:
            return k
    return None


def _safe_id(name):
    out = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in name)
    return out or "Param"


def binding_summary(model):
    return {p.id: sum(1 for n in model.nodes.values() if n.binding(p.id)) for p in model.params}


__all__ = ["export_inp", "import_inp", "read_inp", "decode_tga", "Binding"]
