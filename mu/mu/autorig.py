"""Auto-rig for a picture cut into parts (PSD layers or «Нарезка»): every layer gets a *role* (guessed from its
name — Russian, English, Japanese Live2D naming — or set by hand in the inspector); from the roles' bounding
boxes the rig builds the usual Live2D skeleton (body tilt → body warp → head tilt → face / features / hair warps,
arm and leg rotations) and keyforms for the standard parameters: head turn X/Y/Z, blink and eye smile, gaze,
brows, mouth open / form, cheeks, body turn and breathing, arms, legs, hair and skirt sway with physics.

Everything it creates is ordinary keyforms that can be edited afterwards."""
import math
import re

import numpy as np

from .model import (ArtMesh, Param, PhysGroup, RotationDeformer, STANDARD_PARAMS, WarpDeformer, blank_form)

# role id → title (inspector), in rough back-to-front order
ROLES = [
    ("", "— без роли —"),
    ("back_hair", "Волосы сзади"),
    ("leg_l", "Левая нога (бедро)"), ("shin_l", "Левая голень"),
    ("leg_r", "Правая нога (бедро)"), ("shin_r", "Правая голень"),
    ("body", "Тело"), ("chest", "Грудь"), ("neck", "Шея"), ("skirt", "Юбка"),
    ("arm_l", "Левая рука: плечо"), ("forearm_l", "Левое предплечье"), ("hand_l", "Левая кисть"),
    ("arm_r", "Правая рука: плечо"), ("forearm_r", "Правое предплечье"), ("hand_r", "Правая кисть"),
    ("face", "Лицо"), ("ear", "Ухо"), ("blush", "Румянец"), ("nose", "Нос"),
    ("mouth_in", "Рот (внутри)"), ("mouth", "Рот (линия / губы)"),
    ("eye_white_l", "Левый глаз: белок"), ("iris_l", "Левый глаз: радужка"), ("eye_hl_l", "Левый глаз: блик"),
    ("lash_l", "Левый глаз: верхнее веко"), ("lower_lash_l", "Левый глаз: нижнее веко"),
    ("eye_l", "Левый глаз целиком"), ("brow_l", "Левая бровь"),
    ("eye_white_r", "Правый глаз: белок"), ("iris_r", "Правый глаз: радужка"), ("eye_hl_r", "Правый глаз: блик"),
    ("lash_r", "Правый глаз: верхнее веко"), ("lower_lash_r", "Правый глаз: нижнее веко"),
    ("eye_r", "Правый глаз целиком"), ("brow_r", "Правая бровь"),
    ("side_hair", "Боковые пряди"), ("bangs", "Чёлка"), ("hair_acc", "Украшение волос"),
    ("head_acc", "Голова: прочее"), ("body_acc", "Тело: прочее"),
]
ROLE_TITLES = dict(ROLES)

# keyword → base role (sides resolved separately). Order matters: more specific first.
_RULES = [
    (r"блик|highlight|hilight|\bhl\b|ハイライト", "eye_hl"),
    (r"радуж|зрач|iris|pupil|黒目|瞳", "iris"),
    (r"белок|white|白目", "eye_white"),
    (r"нижн.*(век|ресн)|lower.?(lash|lid)|下まつ|下睫", "lower_lash"),
    (r"век|ресниц|lash|lid|まつ|睫|上まぶた", "lash"),
    (r"бров|brow|眉", "brow"),
    (r"глаз|eye|目", "eye"),
    (r"(рот|mouth|口|губ|lip).*(внутр|inner|in\b|中)|(внутр|inner|中).*(рот|mouth|口)|язык|tongue|舌|зуб|teeth|歯",
     "mouth_in"),
    (r"рот|mouth|口|губ|lip", "mouth"),
    (r"румян|blush|cheek|щёк|щек|頬|赤面", "blush"),
    (r"нос|nose|鼻", "nose"),
    (r"чёлк|челк|bang|fringe|前髪", "bangs"),
    (r"(волос|hair|髪).*(сзад|back|後)|(сзад|back|後).*(волос|hair|髪)|хвост|tail|ponytail|後ろ髪", "back_hair"),
    (r"пряд|(волос|hair|髪).*(бок|side|横)|(бок|side|横).*(волос|hair|髪)|横髪|もみあげ", "side_hair"),
    (r"бант|заколк|ribbon|clip|hairpin|ободок|headband|リボン|髪飾り", "hair_acc"),
    (r"уш|ear|耳", "ear"),
    (r"лицо|face|head|голова|顔|輪郭", "face"),
    (r"шея|neck|首", "neck"),
    (r"кист|ладон|hand|palm|手(?!首)", "hand"),
    (r"предплеч|forearm|前腕|ひじ下", "forearm"),
    (r"рук|плеч|arm|shoulder|腕|肩", "arm"),
    (r"голен|shin|calf|ступн|foot|feet|ботин|shoe|boot|足首|すね|靴", "shin"),
    (r"бедр|ног|leg|thigh|脚|太もも|もも", "leg"),
    (r"юбк|skirt|スカート", "skirt"),
    (r"волос|hair|髪", "back_hair"),
    (r"груд|chest|bust|胸", "chest"),
    (r"тело|торс|body|torso|одежд|cloth|shirt|dress|plat|плать|体|胴|服", "body"),
]
_SIDED = {"eye_hl", "iris", "eye_white", "lower_lash", "lash", "brow", "eye", "hand", "forearm", "arm", "shin", "leg"}
_LEFT = r"(^|[^a-zа-я])(л|лев|left|l)([^a-zа-я]|$)|левый|левая|левое|左"
_RIGHT = r"(^|[^a-zа-я])(п|пр|прав|right|r)([^a-zа-я]|$)|правый|правая|правое|右"


def guess_role(name):
    low = name.lower().replace("_", " ").replace("-", " ").replace(".", " ")
    for rx, role in _RULES:
        if re.search(rx, low):
            if role not in _SIDED:
                return role, None
            side = "l" if re.search(_LEFT, low) else ("r" if re.search(_RIGHT, low) else None)
            return role, side
    return "", None


def guess_roles(model, overwrite=False):
    """Fill mesh.role from layer names; sides without a hint come from the position against the face centre
    (the character's left is on the viewer's right)."""
    pending = []
    for m in model.meshes():
        if m.role and not overwrite:
            continue
        role, side = guess_role(m.name)
        if role in _SIDED:
            pending.append((m, role, side))
        else:
            m.role = role
    cx = _centre_x(model)
    for m, role, side in pending:
        if side is None:
            if role == "eye" and _is_both_eyes(m, cx):
                m.role = "head_acc"  # both eyes in one layer: cut them apart to rig blinking
                continue
            mx = m.rest[:, 0].mean() if len(m.rest) else cx
            side = "l" if mx >= cx else "r"
        if role == "eye":
            m.role = "eye_" + side
        else:
            m.role = f"{role}_{side}"
    return {m.id: m.role for m in model.meshes()}


def _is_both_eyes(m, cx):
    if not len(m.rest):
        return False
    return m.rest[:, 0].min() < cx - 10 and m.rest[:, 0].max() > cx + 10


def _centre_x(model):
    face = [m for m in model.meshes() if m.role == "face" or guess_role(m.name)[0] == "face"]
    pts = np.concatenate([m.rest for m in face if len(m.rest)]) if face else None
    if pts is None or not len(pts):
        allp = [m.rest for m in model.meshes() if len(m.rest)]
        if not allp:
            return model.width / 2
        pts = np.concatenate(allp)
    return float((pts[:, 0].min() + pts[:, 0].max()) / 2)


# ====================================================================== geometry helpers
class Box:
    def __init__(self, pts):
        self.x0, self.y0 = pts.min(0)
        self.x1, self.y1 = pts.max(0)

    @property
    def cx(self):
        return (self.x0 + self.x1) / 2

    @property
    def cy(self):
        return (self.y0 + self.y1) / 2

    @property
    def w(self):
        return self.x1 - self.x0

    @property
    def h(self):
        return self.y1 - self.y0

    def rect(self, pad=0.0, padx=None, pady=None):
        px = pad if padx is None else padx
        py = pad if pady is None else pady
        return (self.x0 - px, self.y0 - py, self.w + 2 * px, self.h + 2 * py)


def _box(meshes):
    pts = [m.rest for m in meshes if len(m.rest)]
    return Box(np.concatenate(pts)) if pts else None


def _keys_fn(node, pid, keys, fn):
    b = node.binding(pid, create=True)
    pts = node.rest if isinstance(node, ArtMesh) else node.rest_grid()
    for k in keys:
        f = blank_form(len(pts))
        f["offsets"] = np.asarray(fn(pts, k), dtype=float).reshape(-1, 2)
        b.add_key(k, f)
    return b


def _keys_rot(node, pid, mapping):
    b = node.binding(pid, create=True)
    for k, ang in mapping.items():
        f = blank_form()
        f["angle"] = ang
        b.add_key(k, f)


def _keys_opacity(node, pid, mapping):
    b = node.binding(pid, create=True)
    for k, op in mapping.items():
        f = b.forms[b.key_index(k)] if b.key_index(k) is not None else blank_form(node.n_points())
        f["opacity"] = op
        b.add_key(k, f)


def _bulge(t):
    return 0.35 + 0.65 * np.sin(np.pi * np.clip(t, 0, 1))


# ====================================================================== the rig
def strip_rig(model):
    """Remove deformers, keyforms and physics (art meshes stay where they are)."""
    for d in list(model.deformers()):
        model.remove(d.id)
    for m in model.meshes():
        m.parent = None
        m.bindings = []
    model.physics = []
    model.invalidate()


def autorig(model, replace=True):
    """Build deformers + keyforms from the mesh roles. Returns a list of human-readable notes (Russian)."""
    notes = []
    if replace:
        strip_rig(model)
    for row in STANDARD_PARAMS:
        model.add_param(Param(*row))
    if not any(m.role for m in model.meshes()):
        guess_roles(model)
    R = {}
    for m in model.meshes():
        R.setdefault(m.role, []).append(m)

    def box(*roles):
        return _box([m for r in roles for m in R.get(r, [])])

    all_box = _box(model.meshes())
    if all_box is None:
        return ["Нет слоёв"]
    face = box("face")
    head_parts = ("face", "ear", "blush", "nose", "mouth_in", "mouth", "bangs", "side_hair", "hair_acc", "head_acc",
                  "brow_l", "brow_r") + tuple(r for r, _ in ROLES if r.startswith(("eye", "iris", "lash", "lower")))
    if face is None:
        face = box(*head_parts)
    if face is None:
        notes.append("Лицо не найдено: сделан только риг тела и дыхания. Назначьте роли слоям (Инспектор → Роль) "
                      "и запустите авто-риг ещё раз.")
    S = (face.w / 336.0) if face else max(0.3, all_box.w / 700.0)
    cx = face.cx if face else all_box.cx

    def add(node):
        model.add(node)
        return node

    # ---------------------------------------------------------------- skeleton
    body = box("body", "neck", "skirt", "body_acc", "arm_l", "arm_r", "forearm_l", "forearm_r", "hand_l", "hand_r")
    legs = box("leg_l", "leg_r", "shin_l", "shin_r")
    if body is None:
        top = (face.y1 if face else all_box.y0)
        body = Box(np.array([[all_box.x0, top], [all_box.x1, all_box.y1]]))
    hip_y = body.y0 + body.h * 0.75 if legs is None else legs.y0 + 20 * S
    body_rot = add(RotationDeformer(name="Тело: наклон", origin=(cx, hip_y), length=300 * S))
    t_top = (face.y1 - face.h * 0.25) if face else body.y0
    trect = (min(body.x0, cx - 200 * S) - 40 * S, t_top, 0, body.y1 - t_top + 20 * S)
    trect = (trect[0], trect[1], max(body.x1, cx + 200 * S) + 40 * S - trect[0], trect[3])
    torso = add(WarpDeformer(name="Тело: поворот и дыхание", parent=body_rot.id, rect=trect, rows=4, cols=4))
    for r in ("body", "neck", "body_acc"):
        for m in R.get(r, []):
            m.parent = torso.id
    if face is None and not R.get("body"):
        for m in model.meshes():
            if m.parent is None:
                m.parent = torso.id
    chest_w = None
    if R.get("chest"):
        cb = box("chest")
        chest_w = add(WarpDeformer(name="Грудь", parent=torso.id, rect=cb.rect(16 * S), rows=4, cols=4))
        for m in R["chest"]:
            m.parent = chest_w.id
    skirt_w = None
    if R.get("skirt"):
        sb = box("skirt")
        skirt_w = add(WarpDeformer(name="Юбка", parent=body_rot.id, rect=sb.rect(20 * S), rows=4, cols=4))
        for m in R["skirt"]:
            m.parent = skirt_w.id

    head = {}
    if face is not None:
        neck_y = face.y1 - face.h * 0.05
        head_rot = add(RotationDeformer(name="Голова: наклон", parent=torso.id, origin=(cx, neck_y),
                                        length=200 * S))
        face_w = add(WarpDeformer(name="Голова: лицо", parent=head_rot.id, rect=face.rect(50 * S), rows=5, cols=5))
        feat_roles = [r for r in R if r.startswith(("eye", "iris", "lash", "lower", "brow")) or
                      r in ("mouth", "mouth_in", "nose", "blush")]
        fb = box(*feat_roles) or face
        feat = add(WarpDeformer(name="Голова: черты лица", parent=face_w.id, rect=fb.rect(30 * S), rows=4, cols=4))
        head = {"rot": head_rot, "face": face_w, "feat": feat}
        for r in ("face", "ear", "head_acc"):
            for m in R.get(r, []):
                m.parent = face_w.id
        for r in feat_roles:
            for m in R.get(r, []):
                m.parent = feat.id
        for role, title, depth, rows, cols in (("back_hair", "Волосы сзади", -0.55, 6, 5),
                                               ("side_hair", "Пряди", 1.15, 5, 4),
                                               ("bangs", "Чёлка", 1.35, 5, 5)):
            hb = box(role) if role != "bangs" else box("bangs", "hair_acc")
            if hb is None:
                continue
            w = add(WarpDeformer(name=title, parent=head_rot.id, rect=hb.rect(30 * S), rows=rows, cols=cols))
            head[role] = (w, depth)
            for m in R.get(role, []) + (R.get("hair_acc", []) if role == "bangs" else []):
                m.parent = w.id
        if "bangs" not in head:
            for m in R.get("hair_acc", []):
                m.parent = face_w.id
        notes.append("Голова: поворот X/Y/Z, " + ("волосы с физикой" if any(k in head for k in
                                                                           ("bangs", "side_hair", "back_hair"))
                                                   else "без волос"))

    # arms: shoulder → elbow → wrist rotations, joints from the part boxes
    for side, sgn, nm in (("l", 1, "Левая"), ("r", -1, "Правая")):
        up, fo, ha = box("arm_" + side), box("forearm_" + side), box("hand_" + side)
        if up is None and fo is None and ha is None:
            continue
        first = up or fo or ha
        shoulder = (first.cx - sgn * first.w * 0.15, first.y0 + min(first.w, first.h) * 0.3)
        a = add(RotationDeformer(name=f"{nm} рука: плечо", parent=torso.id, origin=shoulder, length=first.h))
        for m in R.get("arm_" + side, []):
            m.parent = a.id
        parent = a
        if fo is not None:
            elbow = (fo.cx, fo.y0 + min(fo.w, fo.h) * 0.3) if up is None else \
                ((up.cx + fo.cx) / 2, (up.y1 + fo.y0) / 2)
            e = add(RotationDeformer(name=f"{nm} рука: локоть", parent=a.id, origin=elbow, length=fo.h))
            for m in R.get("forearm_" + side, []):
                m.parent = e.id
            parent = e
        if ha is not None:
            src = fo or up
            wrist = (ha.cx, ha.y0 + ha.h * 0.15) if src is None else ((src.cx + ha.cx) / 2, (src.y1 + ha.y0) / 2)
            h = add(RotationDeformer(name=f"{nm} кисть", parent=parent.id, origin=wrist, length=ha.h))
            for m in R.get("hand_" + side, []):
                m.parent = h.id
            _keys_rot(h, "ParamHand" + side.upper(), {-60: -60.0, 0: 0.0, 60: 60.0})
        pa = model.param("ParamArm%sA" % side.upper())
        _keys_rot(a, pa.id, {pa.min: pa.min, 0.0: 0.0, pa.max: pa.max})
        if parent is not a:
            pb = model.param("ParamArm%sB" % side.upper())
            _keys_rot(parent, pb.id, {pb.min: pb.min, 0.0: 0.0, pb.max: pb.max})
        notes.append(f"{nm} рука: суставы и вращение")

    for side, ksgn, nm in (("l", -1, "Левая"), ("r", 1, "Правая")):
        th, sh = box("leg_" + side), box("shin_" + side)
        if th is None and sh is None:
            continue
        first = th or sh
        hip = (first.cx, first.y0 + min(first.w, first.h) * 0.25)
        lg = add(RotationDeformer(name=f"{nm} нога: бедро", origin=hip, length=first.h))
        for m in R.get("leg_" + side, []):
            m.parent = lg.id
        _keys_rot(lg, "ParamLeg" + side.upper(), {-45: -45.0, 45: 45.0})
        if sh is not None:
            knee = (sh.cx, sh.y0 + min(sh.w, sh.h) * 0.25) if th is None else ((th.cx + sh.cx) / 2, (th.y1 + sh.y0) / 2)
            kn = add(RotationDeformer(name=f"{nm} нога: колено", parent=lg.id, origin=knee, length=sh.h))
            for m in R.get("shin_" + side, []):
                m.parent = kn.id
            _keys_rot(kn, "ParamKnee" + side.upper(), {0: 0.0, 90: 90.0 * ksgn})
        notes.append(f"{nm} нога")
    for m in model.meshes():  # anything left follows the body
        if m.parent is None:
            m.parent = torso.id if m.role not in ("leg_l", "leg_r", "shin_l", "shin_r") else None
    model.invalidate()

    # ---------------------------------------------------------------- body keyforms
    tuv = torso.uv_of(torso.rest_grid())

    def body_x(pts, k):
        out = np.zeros_like(pts)
        out[:, 0] = (k / 10) * 22 * S * _bulge(tuv[:, 0]) * (1 - 0.6 * tuv[:, 1])
        return out

    def body_y(pts, k):
        out = np.zeros_like(pts)
        out[:, 1] = -(k / 10) * 14 * S * _bulge(tuv[:, 1]) * (1 - tuv[:, 1])
        return out

    def breath(pts, k):
        out = np.zeros_like(pts)
        lift = np.clip(1 - tuv[:, 1] * 1.4, 0, 1)
        out[:, 1] = -k * 9 * S * lift
        out[:, 0] = k * 3 * S * (tuv[:, 0] - 0.5) * lift
        return out
    _keys_fn(torso, "ParamBodyAngleX", [-10, 0, 10], body_x)
    _keys_fn(torso, "ParamBodyAngleY", [-10, 0, 10], body_y)
    _keys_fn(torso, "ParamBreath", [0, 1], breath)
    _keys_rot(body_rot, "ParamBodyAngleZ", {-10: -5.0, 0: 0.0, 10: 5.0})
    notes.append("Тело: поворот, наклон, дыхание")

    def sway(warp, pid, amp, power=1.6):
        uv = warp.uv_of(warp.rest_grid())

        def f(pts, k):
            out = np.zeros_like(pts)
            out[:, 0] = k * amp * S * np.clip(uv[:, 1], 0, 1) ** power
            out[:, 1] = -abs(k) * amp * S * 0.12 * np.clip(uv[:, 1], 0, 1) ** power
            return out
        _keys_fn(warp, pid, [-1, 0, 1], f)

    physics = []
    if skirt_w is not None:
        ids = ["ParamSkirt", "ParamSkirt2"]
        model.add_param(Param("ParamSkirt2", "Юбка 2", -1, 1, 0, "Тело"))
        x0, y0, ww, hh = skirt_w.rect
        chain_keys(skirt_w, (x0 + ww / 2, y0), (x0 + ww / 2, y0 + hh), ids, 12.0)
        physics.append(strand_group("Юбка", ids, stiffness=40, damping=5, gravity=0.5, body=True))

    if chest_w is not None:
        # breathing lifts the chest a little; a soft bounce follows the body with a stiff pendulum
        model.add_param(Param("ParamChest", "Грудь (колебание)", -1, 1, 0, "Тело"))
        cuv = chest_w.uv_of(chest_w.rest_grid())

        def chest_breath(pts, k):
            out = np.zeros_like(pts)
            w = _bulge(cuv[:, 0]) * _bulge(cuv[:, 1])
            out[:, 1] = -k * 4 * S * w
            out[:, 0] = k * 3 * S * (cuv[:, 0] - 0.5) * w
            return out

        def chest_bounce(pts, k):
            out = np.zeros_like(pts)
            w = np.clip(cuv[:, 1], 0, 1) ** 1.3 * _bulge(cuv[:, 0])
            out[:, 1] = k * 9 * S * w
            out[:, 0] = k * 2 * S * (cuv[:, 0] - 0.5) * w
            return out
        _keys_fn(chest_w, "ParamBreath", [0, 1], chest_breath)
        _keys_fn(chest_w, "ParamChest", [-1, 0, 1], chest_bounce)
        physics.append(PhysGroup(name="Грудь", inputs=[{"param": "ParamBodyAngleY", "weight": 1.0, "kind": "x"},
                                                       {"param": "ParamBodyAngleX", "weight": 0.5, "kind": "x"},
                                                       {"param": "ParamAngleY", "weight": 0.3, "kind": "x"}],
                                 output="ParamChest", scale=1.0, stiffness=70, damping=6, gravity=0.3))
        notes.append("Грудь: дыхание и мягкое колебание")

    if face is not None:
        _rig_head(model, R, head, face, S, cx, sway, physics)
        notes.append("Лицо: моргание, улыбка глаз, взгляд, брови, рот" if any(r.startswith(("eye", "lash", "iris"))
                                                                         for r in R) else "Лицо: без глаз")
    model.physics = physics
    model.reset_values()
    model.invalidate()
    return notes


def _rig_head(model, R, head, face, S, cx, sway, physics):
    def turn(warp, depth, kx=26.0, ky=22.0):
        uv = warp.uv_of(warp.rest_grid())

        def fx(pts, k):
            out = np.zeros_like(pts)
            out[:, 0] = np.sign(k) * depth * kx * S * _bulge(uv[:, 0]) * (abs(k) / 30)
            return out

        def fy(pts, k):
            out = np.zeros_like(pts)
            out[:, 1] = -np.sign(k) * depth * ky * S * _bulge(uv[:, 1]) * (abs(k) / 30)
            return out
        _keys_fn(warp, "ParamAngleX", [-30, 0, 30], fx)
        _keys_fn(warp, "ParamAngleY", [-30, 0, 30], fy)

    turn(head["face"], 1.0)
    turn(head["feat"], 0.55)
    _keys_rot(head["rot"], "ParamAngleZ", {-30: -16.0, 0: 0.0, 30: 16.0})
    phys = {"bangs": ("Чёлка", "ParamHairFront", 12, 70, 8, 0.5, 1.0),
            "side_hair": ("Пряди", "ParamHairSide", 16, 45, 5, 0.7, 1.1),
            "back_hair": ("Волосы сзади", "ParamHairBack", 14, 30, 4, 0.8, 1.0)}
    for role, (w, depth) in ((k, v) for k, v in head.items() if k in phys):
        turn(w, depth)
        title, pid, amp, stiff, damp, grav, scale = phys[role]
        # Cubism-style: X1 near the roots … X3 at the tips, driven by a 3-link pendulum
        ids = [pid, pid + "2", pid + "3"]
        for i, q in enumerate(ids[1:], 2):
            model.add_param(Param(q, f"{title} {i}", -1, 1, 0, "Волосы"))
        x0, y0, ww, hh = w.rect
        chain_keys(w, (x0 + ww / 2, y0), (x0 + ww / 2, y0 + hh), ids, amp)
        physics.append(strand_group(title, ids, stiffness=stiff, damping=damp, gravity=grav, scale=scale))

    # ---------------------------------------------------------------- eyes
    for side in ("l", "r"):
        S_ = side.upper()
        parts = {k: R.get(f"{k}_{side}", []) for k in ("eye_white", "iris", "eye_hl", "lash", "lower_lash", "eye", "brow")}
        eb = _box(parts["eye_white"] + parts["iris"] + parts["eye"]) or _box(parts["lash"])
        if eb is None:
            continue
        ex, ey = eb.cx, eb.cy
        ew, eh = eb.w / 2.2, eb.h / 2
        lid = eb.y0 + eb.h * 0.72  # the closed eye line
        sgn = 1 if side == "l" else -1
        pid_open, pid_smile = f"ParamEye{S_}Open", f"ParamEye{S_}Smile"

        def lid_y(x, ex=ex, ew=ew, eh=eh, lid=lid):
            t = np.clip((x - ex) / (ew * 1.1), -1, 1)
            return lid + eh * 0.08 * (1 - t * t)

        def squash(pts, k, lid=lid, lid_y=lid_y):
            out = np.zeros_like(pts)
            if k == 0:
                out[:, 1] = (lid_y(pts[:, 0]) - pts[:, 1]) * 0.94
            elif k > 1:
                out[:, 1] = (pts[:, 1] - lid) * 0.12 * (k - 1) / 0.2
            return out

        def blink(pts, k, squash=squash):
            return squash(pts, 0) * (1 - k / 0.15) * 0.97 if k <= 0.15 else squash(pts, k)
        inner = parts["eye_white"] + parts["iris"] + parts["eye_hl"]
        for m in inner:
            _keys_fn(m, pid_open, [0, 0.15, 1, 1.2], blink)
            m.binding(pid_open).forms[0]["opacity"] = 0.0
        for m in parts["eye"]:  # the whole eye in one layer: squash to a thin line
            _keys_fn(m, pid_open, [0, 1, 1.2], lambda pts, k, squash=squash: squash(pts, k) * (0.9 if k == 0 else 1))
        for m in parts["lash"]:
            prof_x, prof_y = _lower_profile(m.rest)

            def lash(pts, k, prof_x=prof_x, prof_y=prof_y, lid_y=lid_y, ex=ex, eh=eh):
                out = np.zeros_like(pts)
                if k == 0:
                    edge = np.interp(pts[:, 0], prof_x, prof_y)
                    out[:, 1] = lid_y(pts[:, 0]) - edge
                    out[:, 0] = (pts[:, 0] - ex) * 0.04
                elif k > 1:
                    out[:, 1] = -eh * 0.14 * (k - 1) / 0.2
                return out
            _keys_fn(m, pid_open, [0, 0.15, 1, 1.2],
                     lambda pts, k, lash=lash: lash(pts, 0) * (1 - k / 0.15) * 0.9 if k <= 0.15 else lash(pts, k))

            def smile_lash(pts, k, ex=ex, ew=ew, eh=eh):
                out = np.zeros_like(pts)
                t = np.clip((pts[:, 0] - ex) / (ew * 1.1), -1, 1)
                out[:, 1] = -k * eh * 0.22 * (1 - t * t)
                return out
            _keys_fn(m, pid_smile, [0, 1], smile_lash)

        def smile_low(pts, k, ex=ex, ew=ew, eh=eh):
            out = np.zeros_like(pts)
            t = np.clip((pts[:, 0] - ex) / (ew * 1.1), -1, 1)
            out[:, 1] = -k * eh * (0.5 + 0.22 * (1 - t * t))
            return out
        for m in parts["lower_lash"]:
            _keys_fn(m, pid_smile, [0, 1], smile_low)

        def smile_white(pts, k, ey=ey, eh=eh):
            out = np.zeros_like(pts)
            below = np.clip((pts[:, 1] - (ey - eh * 0.2)) / (eh * 0.8), 0, 1)
            out[:, 1] = -k * eh * 0.55 * below
            return out
        for m in inner + parts["eye"]:
            _keys_fn(m, pid_smile, [0, 1], smile_white)

        def look_x(pts, k, ew=ew):
            out = np.zeros_like(pts)
            out[:, 0] = k * ew * 0.3
            return out

        def look_y(pts, k, eh=eh):
            out = np.zeros_like(pts)
            out[:, 1] = -k * eh * 0.18
            return out
        for m in parts["iris"] + parts["eye_hl"]:
            _keys_fn(m, "ParamEyeBallX", [-1, 0, 1], look_x)
            _keys_fn(m, "ParamEyeBallY", [-1, 0, 1], look_y)
        # clip the iris / highlight by the eye white (Live2D clipping mask)
        if parts["eye_white"]:
            for m in parts["iris"] + parts["eye_hl"]:
                m.masks = [w.id for w in parts["eye_white"]]

        bb = _box(parts["brow"])
        if bb is not None:
            bc = np.array([bb.cx, bb.cy])

            def brow_y(pts, k):
                out = np.zeros_like(pts)
                out[:, 1] = -k * 16 * S
                return out

            def brow_ang(pts, k, bc=bc, sgn=sgn):
                ang = math.radians(k * 16) * (-sgn)
                c, si = math.cos(ang), math.sin(ang)
                d = pts - bc
                rot = np.stack([c * d[:, 0] - si * d[:, 1], si * d[:, 0] + c * d[:, 1]], axis=1)
                return rot - d
            for m in parts["brow"]:
                _keys_fn(m, f"ParamBrow{S_}Y", [-1, 0, 1], brow_y)
                _keys_fn(m, f"ParamBrow{S_}Angle", [-1, 0, 1], brow_ang)

    # ---------------------------------------------------------------- mouth
    mb = _box(R.get("mouth", []) + R.get("mouth_in", []))
    if mb is not None:
        mcx, my, mw = mb.cx, mb.cy, max(8.0, mb.w / 2)

        def form(pts, k, amp=12.0):
            out = np.zeros_like(pts)
            t = np.clip((pts[:, 0] - mcx) / mw, -1.3, 1.3)
            out[:, 1] = (-k * amp * (t * t) + k * amp * 0.25) * S
            out[:, 0] = k * 4 * t * S
            return out

        def inner_open(pts, k):
            out = np.zeros_like(pts)
            if k == 0:
                out[:, 1] = (my - pts[:, 1]) * 0.96
            elif k < 1:
                out[:, 1] = (my - pts[:, 1]) * 0.75
            return out
        for m in R.get("mouth_in", []):
            _keys_fn(m, "ParamMouthOpenY", [0, 0.1, 1], inner_open)
            _keys_opacity(m, "ParamMouthOpenY", {0: 0.0, 0.1: 1.0, 1: 1.0})
            _keys_fn(m, "ParamMouthForm", [-1, 0, 1], lambda pts, k: form(pts, k, 10))
        has_inner = bool(R.get("mouth_in"))
        for m in R.get("mouth", []):
            if has_inner:
                def line_open(pts, k):
                    out = np.zeros_like(pts)
                    out[:, 1] = -k * 4 * S
                    return out
                _keys_fn(m, "ParamMouthOpenY", [0, 1], line_open)
            else:  # a single mouth layer: stretch it open downwards from its top edge
                top = mb.y0

                def stretch(pts, k, top=top):
                    out = np.zeros_like(pts)
                    out[:, 1] = (pts[:, 1] - top) * 1.6 * k
                    return out
                _keys_fn(m, "ParamMouthOpenY", [0, 1], stretch)
            _keys_fn(m, "ParamMouthForm", [-1, 0, 1], form)
    for m in R.get("blush", []):
        _keys_opacity(m, "ParamCheek", {0: 0.0, 1: 1.0})


def _lower_profile(pts, bins=12):
    """x-sorted samples of the lowest y of a lash layer (its lower edge)."""
    if not len(pts):
        return np.array([0.0, 1.0]), np.array([0.0, 0.0])
    x0, x1 = pts[:, 0].min(), pts[:, 0].max()
    edges = np.linspace(x0, x1 + 1e-6, bins + 1)
    xs, ys = [], []
    for i in range(bins):
        sel = (pts[:, 0] >= edges[i]) & (pts[:, 0] < edges[i + 1])
        if sel.any():
            xs.append((edges[i] + edges[i + 1]) / 2)
            ys.append(pts[sel, 1].max())
    if len(xs) < 2:
        return np.array([x0, x1 + 1]), np.array([pts[:, 1].max()] * 2)
    return np.array(xs), np.array(ys)


# ====================================================================== strand rig (Cubism-style hair physics)
DIRECTIONS = {"down": "вниз", "up": "вверх", "left": "влево", "right": "вправо"}


def chain_keys(warp, root, tip, ids, amp_deg=22.0, y_id=None, s_id=None):
    """Keyforms on `warp` for a strand running from `root` to `tip`: ids[i] bends everything below link i (−1…1
    ⇒ ±amp_deg), y_id stretches the strand, s_id waves it into an S. Bends add up, so driving X1…Xn from a
    pendulum chain gives the wave that runs down the hair."""
    root = np.asarray(root, float)
    tip = np.asarray(tip, float)
    axis = tip - root
    length = float(np.hypot(*axis)) or 1.0
    u = axis / length
    nrm = np.array([-u[1], u[0]])
    n = len(ids)

    def along(p):
        return ((p - root) @ u) / length

    for i, pid in enumerate(ids):
        lo = i / n
        piv = root + u * length * lo

        def bend(p, k, lo=lo, piv=piv):
            s = along(p)
            w = np.clip((s - lo) / (0.6 / n), 0, 1)
            w = w * w * (3 - 2 * w)
            ang = math.radians(amp_deg) * k
            c, si = math.cos(ang), math.sin(ang)
            d = p - piv
            r = np.stack([c * d[:, 0] - si * d[:, 1], si * d[:, 0] + c * d[:, 1]], 1)
            return (r - d) * w[:, None]
        _keys_fn(warp, pid, [-1, 0, 1], bend)
    if y_id:
        def stretch(p, k):
            s = np.clip(along(p), 0, 1.3)
            return np.outer(k * 0.12 * length * s ** 1.5, u)
        _keys_fn(warp, y_id, [-1, 0, 1], stretch)
    if s_id:
        def swave(p, k):
            s = np.clip(along(p), 0, 1.3)
            return np.outer(k * 0.06 * length * np.sin(2 * np.pi * s) * s, nrm)
        _keys_fn(warp, s_id, [-1, 0, 1], swave)


def strand_ends(box, direction):
    if direction == "up":
        return (box.cx, box.y1), (box.cx, box.y0)
    if direction == "left":
        return (box.x1, box.cy), (box.x0, box.cy)
    if direction == "right":
        return (box.x0, box.cy), (box.x1, box.cy)
    return (box.cx, box.y0), (box.cx, box.y1)


def strand_group(title, ids, stiffness=40.0, damping=4.5, gravity=0.6, scale=1.0, body=False):
    inputs = [{"param": "ParamAngleX", "weight": 0.6, "kind": "x"},
              {"param": "ParamAngleZ", "weight": 0.6, "kind": "angle"},
              {"param": "ParamBodyAngleX", "weight": 0.4, "kind": "x"},
              {"param": "ParamBodyAngleZ", "weight": 0.4, "kind": "angle"}]
    if body:
        inputs = inputs[2:]
    return PhysGroup(name=title, inputs=inputs, output=ids[0], scale=scale, stiffness=stiffness, damping=damping,
                     gravity=gravity, segments=len(ids),
                     outputs=[{"param": pid, "vertex": i + 1, "kind": "angle", "scale": 1.0} for i, pid in enumerate(ids)])


def _strand_ids(model, prefix, title, segments, group="Волосы"):
    base = "Param" + "".join(ch for ch in prefix if ch.isalnum())
    ids = []
    for i in range(segments):
        pid = f"{base}X{i + 1}"
        model.add_param(Param(pid, f"{title} X{i + 1}", -1, 1, 0, group))
        ids.append(pid)
    y_id, s_id = f"{base}Y", f"{base}S"
    model.add_param(Param(y_id, f"{title} Y (длина)", -1, 1, 0, group))
    model.add_param(Param(s_id, f"{title} S (изгиб)", -1, 1, 0, group))
    return ids, y_id, s_id


def rig_strand(model, meshes, title="Прядь", direction="down", segments=3, amp_deg=22.0, physics=True,
               stiffness=40.0, damping=4.5, gravity=0.6):
    """Wrap layers into a warp deformer and give it a Cubism-style strand rig: X1…Xn bends, Y length, S curve and a
    pendulum chain driving X1…Xn. Returns (warp, ids, group)."""
    meshes = [m for m in meshes if isinstance(m, ArtMesh) and len(m.rest)]
    if not meshes:
        raise ValueError("Выберите слои пряди")
    box = _box(meshes)
    pad = 0.12 * max(box.w, box.h)
    parents = {m.parent for m in meshes}
    parent = parents.pop() if len(parents) == 1 else None
    longer = box.h >= box.w if direction in ("down", "up") else box.w > box.h
    rows, cols = (8, 4) if (direction in ("down", "up")) or not longer else (4, 8)
    w = WarpDeformer(name=f"{title}: физика", parent=parent, rect=box.rect(pad), rows=rows, cols=cols)
    model.add(w)
    for m in meshes:
        m.parent = w.id
    used = {p.id for p in model.params}
    prefix = title
    k = 2
    while any(p.startswith("Param" + "".join(ch for ch in prefix if ch.isalnum()) + "X") for p in used):
        prefix = f"{title}{k}"
        k += 1
    ids, y_id, s_id = _strand_ids(model, prefix, title, segments)
    root, tip = strand_ends(box, direction)
    chain_keys(w, root, tip, ids, amp_deg, y_id, s_id)
    g = None
    if physics:
        g = strand_group(title, ids, stiffness, damping, gravity)
        model.physics.append(g)
    model.invalidate()
    return w, ids, g
