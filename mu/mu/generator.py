"""Character creator: draws an anime character as separate layers (cel shading, outlines) and rigs it
automatically — head turn with depth parallax (warp deformers), head / body tilt, breathing, blinking and
eye smiles, gaze, brows, mouth open / form, blush, arms and legs (rotation chains), hair and skirt sway with
physics. Everything uses the standard Cubism parameter ids, so poses and VTuber tools understand it."""
import math
import random

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPainterPathStroker,
                           QPen, QRadialGradient)

from .mesh import alpha_of, auto_mesh
from .model import ArtMesh, Model, Param, PhysGroup, RotationDeformer, STANDARD_PARAMS, WarpDeformer, blank_form

HAIR_COLORS = [("Розовый", "#F2A7C3"), ("Каштановый", "#8C5B45"), ("Чёрный", "#3A3442"), ("Блонд", "#F0D38A"),
               ("Серебро", "#D8DCE8"), ("Голубой", "#8CC4EE"), ("Лавандовый", "#B9A0E8"), ("Рыжий", "#E8894C"),
               ("Мятный", "#9EDDC6")]
EYE_COLORS = [("Синий", "#4C7BDB"), ("Зелёный", "#47A06C"), ("Янтарный", "#DB9A35"), ("Фиолетовый", "#9A69DB"),
              ("Красный", "#D9504D"), ("Бирюзовый", "#3FB3C9"), ("Розовый", "#E0679E")]
SKINS = [("Светлая", "#FFE8DA"), ("Персиковая", "#F9D6BF"), ("Смуглая", "#D9A783"), ("Бледная", "#FFF1EA")]
OUTFIT_COLORS = [("Тёмно-синий", "#2F3E6B"), ("Терракота", "#D97757"), ("Чёрный", "#2B2A30"), ("Белый", "#F4F1EA"),
                 ("Бордовый", "#7E2E3E"), ("Мятный", "#7DC9B0"), ("Лавандовый", "#A996D8"), ("Розовый", "#EE9FBC")]
HAIR_STYLES = [("long", "Длинные"), ("twintails", "Два хвостика"), ("bob", "Каре"), ("ponytail", "Хвост"),
               ("short", "Короткие")]
OUTFITS = [("sailor", "Матроска"), ("hoodie", "Худи"), ("dress", "Платье"), ("shirt", "Рубашка и брюки")]
ACCESSORIES = [("ribbon", "Бант"), ("cat_ears", "Кошачьи ушки"), ("clip", "Заколка"), ("none", "Нет")]
BODIES = [("girl", "Девушка"), ("boy", "Парень")]

LINE = "#5A3B36"


class Spec:
    def __init__(self, **kw):
        self.name = kw.get("name", "Мика")
        self.body = kw.get("body", "girl")
        self.hair_style = kw.get("hair_style", "long")
        self.hair = kw.get("hair", "#F2A7C3")
        self.eyes = kw.get("eyes", "#4C7BDB")
        self.skin = kw.get("skin", "#FFE8DA")
        self.outfit = kw.get("outfit", "sailor")
        self.outfit_color = kw.get("outfit_color", "#2F3E6B")
        self.accessory = kw.get("accessory", "ribbon")
        self.accent = kw.get("accent", "#D9504D")
        self.eye_size = float(kw.get("eye_size", 1.0))

    def to_dict(self):
        return dict(self.__dict__)

    @classmethod
    def random(cls, seed=None):
        r = random.Random(seed)
        body = r.choice(["girl", "girl", "girl", "boy"])
        styles = ["long", "twintails", "bob", "ponytail"] if body == "girl" else ["short", "bob"]
        outfits = ["sailor", "hoodie", "dress"] if body == "girl" else ["shirt", "hoodie"]
        return cls(name=r.choice(["Мика", "Юки", "Аой", "Сора", "Хина", "Рин", "Кай", "Нао"]), body=body,
                   hair_style=r.choice(styles), hair=r.choice(HAIR_COLORS)[1], eyes=r.choice(EYE_COLORS)[1],
                   skin=r.choice(SKINS)[1], outfit=r.choice(outfits), outfit_color=r.choice(OUTFIT_COLORS)[1],
                   accessory=r.choice(["ribbon", "cat_ears", "clip", "none"]) if body == "girl" else
                   r.choice(["none", "clip"]), accent=r.choice(["#D9504D", "#D97757", "#4C7BDB", "#E0679E"]),
                   eye_size=r.uniform(0.92, 1.12))


# ====================================================================== drawing helpers
def C(c, k=100):
    q = QColor(c)
    return q.darker(k) if k > 100 else (q.lighter(-k) if k < 0 else q)


def shade(c, f):
    """Darken (f < 1) or lighten (f > 1) keeping hue."""
    q = QColor(c)
    h, s, v, a = q.getHsvF()
    if f < 1:
        return QColor.fromHsvF(max(0, h), min(1.0, s * (1 + (1 - f) * 0.6)), max(0.0, v * f), a)
    return QColor.fromHsvF(max(0, h), max(0.0, s * (2 - f)), min(1.0, v * f + (1 - v) * (f - 1)), a)


def smooth(points, closed=True, tension=0.5):
    """Catmull-Rom spline through points → QPainterPath."""
    pts = [QPointF(*p) for p in points]
    n = len(pts)
    path = QPainterPath(pts[0])
    if n < 3:
        for p in pts[1:]:
            path.lineTo(p)
        return path
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p0 = pts[(i - 1) % n] if (closed or i > 0) else pts[i]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if (closed or i + 2 < n) else p2
        c1 = p1 + (p2 - p0) * (tension / 3)
        c2 = p2 - (p3 - p1) * (tension / 3)
        path.cubicTo(c1, c2, p2)
    if closed:
        path.closeSubpath()
    return path


def mirror(points, cx=700):
    return [(2 * cx - x, y) for x, y in reversed(points)]


def ellipse(cx, cy, rx, ry):
    p = QPainterPath()
    p.addEllipse(QPointF(cx, cy), rx, ry)
    return p


def stroke_path(path, w):
    s = QPainterPathStroker()
    s.setWidth(w)
    s.setCapStyle(Qt.RoundCap)
    s.setJoinStyle(Qt.RoundJoin)
    return s.createStroke(path)


def fill_outline(p, path, color, line=LINE, lw=3.2, shade_path=None, shade_color=None, light_path=None,
                 light_color=None):
    p.fillPath(path, QColor(color))
    if shade_path is not None:
        p.save()
        p.setClipPath(path)
        p.fillPath(shade_path, QColor(shade_color or shade(color, 0.86)))
        p.restore()
    if light_path is not None:
        p.save()
        p.setClipPath(path)
        p.fillPath(light_path, QColor(light_color or shade(color, 1.15)))
        p.restore()
    if lw:
        p.setPen(QPen(QColor(line), lw, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)


def capsule(a, b, ra, rb):
    """Tapered limb segment from a to b (radii ra, rb) as a smooth outline."""
    ax, ay = a
    bx, by = b
    ang = math.atan2(by - ay, bx - ax)
    nx, ny = -math.sin(ang), math.cos(ang)
    pts = [(ax + nx * ra, ay + ny * ra), (bx + nx * rb, by + ny * rb)]
    path = QPainterPath(QPointF(*pts[0]))
    path.lineTo(QPointF(*pts[1]))
    path.arcTo(QRectF(bx - rb, by - rb, 2 * rb, 2 * rb), -math.degrees(ang) - 90, 180)
    path.lineTo(QPointF(ax - nx * ra, ay - ny * ra))
    path.arcTo(QRectF(ax - ra, ay - ra, 2 * ra, 2 * ra), -math.degrees(ang) + 90, 180)
    path.closeSubpath()
    return path


# ====================================================================== the builder
class Builder:
    """Collects layers (drawn into their own textures), meshes them and builds the rig."""

    def __init__(self, spec, width=1400, height=2600):
        self.s = spec
        self.model = Model(spec.name, width, height)
        for row in STANDARD_PARAMS:
            self.model.add_param(Param(*row))
        self.order = 0
        self.layers = {}

    def layer(self, name, bounds, draw, parent=None, spacing=40, pad=8, order=None):
        r = bounds.boundingRect() if isinstance(bounds, QPainterPath) else QRectF(bounds)
        r = r.adjusted(-pad, -pad, pad, pad).toAlignedRect()
        img = QImage(max(2, r.width()), max(2, r.height()), QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        p.translate(-r.x(), -r.y())
        draw(p)
        p.end()
        alpha = alpha_of(img)
        if not (alpha > 8).any():
            return None
        pts, tris = auto_mesh(alpha, spacing=spacing, margin=3)
        tex_id = "t_" + name
        self.model.textures[tex_id] = img
        m = ArtMesh(name=name, parent=parent, texture=tex_id, rest=pts + [r.x(), r.y()],
                    uvs=pts / [img.width(), img.height()], tris=tris,
                    order=self.order if order is None else order)
        self.order += 10
        self.model.add(m)
        self.layers[name] = m
        return m

    def warp(self, name, rect, parent=None, rows=5, cols=5):
        w = WarpDeformer(name=name, parent=parent, rect=(rect.x(), rect.y(), rect.width(), rect.height()),
                         rows=rows, cols=cols)
        self.model.add(w)
        return w

    def rot(self, name, origin, parent=None, length=120):
        r = RotationDeformer(name=name, parent=parent, origin=origin, length=length)
        self.model.add(r)
        return r

    # ------------------------------------------------------------------ keyform helpers
    def keys_fn(self, node, pid, keys, fn):
        """fn(points (N,2) rest, key) → offsets (N,2) for meshes / warps."""
        b = node.binding(pid, create=True)
        pts = node.rest if isinstance(node, ArtMesh) else node.rest_grid()
        for k in keys:
            f = blank_form(len(pts))
            f["offsets"] = np.asarray(fn(pts, k), dtype=float).reshape(-1, 2)
            b.add_key(k, f)
        return b

    def keys_rot(self, node, pid, mapping):
        b = node.binding(pid, create=True)
        for k, ang in mapping.items():
            f = blank_form()
            f["angle"] = ang
            b.add_key(k, f)
        return b

    def keys_opacity(self, node, pid, mapping):
        b = node.binding(pid, create=True)
        for k, op in mapping.items():
            f = blank_form(node.n_points())
            f["opacity"] = op
            b.add_key(k, f)
        return b


# ====================================================================== the character
def build(spec=None):
    s = spec or Spec()
    B = Builder(s)
    girl = s.body == "girl"
    cx = 700.0
    skin = s.skin
    skin_sh = shade(skin, 0.9)
    hair = s.hair
    hair_sh = shade(hair, 0.78)
    hair_li = shade(hair, 1.12)
    cloth = s.outfit_color
    es = s.eye_size

    # ---------------------------------------------------------------- key geometry
    head_c = (cx, 470.0)
    face_w = 168.0 if girl else 172.0
    chin_y = 668.0 if girl else 676.0
    neck = (cx, 655.0)
    sh_w = 168.0 if girl else 196.0      # half shoulder width
    sh_y = 770.0
    waist_y, waist_w = 1130.0, (102.0 if girl else 128.0)
    hip_y, hip_w = 1250.0, (150.0 if girl else 140.0)
    shoulderL = (cx + sh_w - 22, 826.0)
    shoulderR = (cx - sh_w + 22, 826.0)
    elbowL = (cx + sh_w + 30, 1118.0)
    elbowR = (cx - sh_w - 30, 1118.0)
    wristL = (cx + sh_w + 46, 1372.0)
    wristR = (cx - sh_w - 46, 1372.0)
    hipL, hipR = (cx + 62, 1290.0), (cx - 62, 1290.0)
    kneeL, kneeR = (cx + 70, 1730.0), (cx - 70, 1730.0)
    ankleL, ankleR = (cx + 66, 2170.0), (cx - 66, 2170.0)

    # ---------------------------------------------------------------- deformer skeleton
    m = B.model
    body_rot = B.rot("Тело: наклон", (cx, hip_y), None, 300)
    torso = B.warp("Тело: поворот и дыхание", QRectF(cx - 330, 600, 660, 720), body_rot.id, 4, 4)
    head_rot = B.rot("Голова: наклон", neck, torso.id, 200)
    face_r = QRectF(cx - 250, 250, 500, 470)
    face_w_ = B.warp("Голова: лицо", face_r, head_rot.id)
    feat = B.warp("Голова: черты лица", QRectF(cx - 200, 380, 400, 280), face_w_.id, 4, 4)
    back_r = QRectF(cx - 330, 170, 660, 1180 if s.hair_style in ("long", "twintails", "ponytail") else 700)
    hair_back_w = B.warp("Волосы сзади", back_r, head_rot.id, 6, 5)
    side_w = B.warp("Пряди", QRectF(cx - 270, 330, 540, 560), head_rot.id, 5, 4)
    bangs_w = B.warp("Чёлка", QRectF(cx - 260, 170, 520, 320), head_rot.id, 5, 5)
    skirt_w = B.warp("Юбка", QRectF(cx - 300, 1080, 600, 470), body_rot.id, 4, 4)
    armL = B.rot("Левая рука: плечо", shoulderL, torso.id, 160)
    elbL = B.rot("Левая рука: локоть", elbowL, armL.id, 140)
    handL = B.rot("Левая кисть", wristL, elbL.id, 90)
    armR = B.rot("Правая рука: плечо", shoulderR, torso.id, 160)
    elbR = B.rot("Правая рука: локоть", elbowR, armR.id, 140)
    handR = B.rot("Правая кисть", wristR, elbR.id, 90)
    legL = B.rot("Левая нога: бедро", hipL, None, 220)
    kneeLr = B.rot("Левая нога: колено", kneeL, legL.id, 200)
    legR = B.rot("Правая нога: бедро", hipR, None, 220)
    kneeRr = B.rot("Правая нога: колено", kneeR, legR.id, 200)

    # ---------------------------------------------------------------- back hair (drawn first)
    def back_hair_path():
        st = s.hair_style
        if st == "long":
            pts = [(cx - 205, 330), (cx - 245, 520), (cx - 262, 800), (cx - 250, 1060), (cx - 205, 1270), (cx - 120, 1235),
                   (cx - 60, 1290), (cx, 1250), (cx + 60, 1290), (cx + 120, 1235), (cx + 205, 1270), (cx + 250, 1060),
                   (cx + 262, 800), (cx + 245, 520), (cx + 205, 330), (cx, 220)]
            return smooth(pts)
        if st == "bob":
            pts = [(cx - 215, 330), (cx - 238, 520), (cx - 236, 690), (cx - 200, 760), (cx - 120, 735), (cx, 760),
                   (cx + 120, 735), (cx + 200, 760), (cx + 236, 690), (cx + 238, 520), (cx + 215, 330), (cx, 220)]
            return smooth(pts)
        if st == "short":
            pts = [(cx - 205, 330), (cx - 222, 500), (cx - 200, 640), (cx - 120, 680), (cx, 690), (cx + 120, 680),
                   (cx + 200, 640), (cx + 222, 500), (cx + 205, 330), (cx, 225)]
            return smooth(pts)
        # twintails / ponytail: back of the head only, tails are separate shapes below
        pts = [(cx - 210, 330), (cx - 232, 520), (cx - 215, 690), (cx - 120, 720), (cx, 730), (cx + 120, 720),
               (cx + 215, 690), (cx + 232, 520), (cx + 210, 330), (cx, 225)]
        return smooth(pts)

    def tails():
        out = []
        if s.hair_style == "twintails":
            for sgn in (-1, 1):
                x0 = cx + sgn * 205
                pts = [(x0, 300), (x0 + sgn * 95, 380), (x0 + sgn * 128, 620), (x0 + sgn * 112, 900),
                       (x0 + sgn * 70, 1160), (x0 + sgn * 38, 1240), (x0 + sgn * 22, 1120), (x0 + sgn * 18, 880),
                       (x0 - sgn * 4, 600), (x0 - sgn * 10, 400)]
                out.append(smooth(pts if sgn > 0 else list(reversed(pts))))
        elif s.hair_style == "ponytail":
            pts = [(cx - 60, 230), (cx + 60, 230), (cx + 120, 420), (cx + 150, 720), (cx + 120, 1020), (cx + 40, 1220),
                   (cx - 20, 1100), (cx - 70, 840), (cx - 90, 560), (cx - 90, 360)]
            out.append(smooth(pts))
        return out

    def draw_back_hair(p):
        path = back_hair_path()
        for t in tails():
            path = path.united(t)
        g = QLinearGradient(QPointF(0, 300), QPointF(0, 1300))
        g.setColorAt(0, hair_sh)
        g.setColorAt(1, shade(hair, 0.66))
        p.fillPath(path, QBrush(g))
        p.setPen(QPen(QColor(LINE), 3.0))
        p.drawPath(path)
        light = QPainterPath()
        p.save()
        p.setClipPath(path)
        p.setPen(QPen(shade(hair, 0.62), 2.2))
        for k in range(-5, 6):  # hair strands
            x = cx + k * 44
            q = QPainterPath(QPointF(x, 520))
            q.cubicTo(QPointF(x + k * 6, 800), QPointF(x - k * 4, 1000), QPointF(x + k * 3, 1300))
            p.drawPath(q)
        p.restore()
        del light

    hb = B.layer("Волосы сзади", back_hair_path().united(_union(tails())), draw_back_hair, hair_back_w.id,
                 spacing=70)

    # ---------------------------------------------------------------- legs
    def leg_draw(hip, knee, ankle, sgn, upper):
        def draw(p):
            if upper:
                path = capsule(hip, knee, 70, 50)
                if girl and s.outfit in ("sailor", "dress"):
                    fill_outline(p, path, skin, shade_path=_side_shade(hip, knee, sgn, 70), shade_color=skin_sh)
                    sock = QPainterPath()
                    sock.addRect(QRectF(knee[0] - 90, knee[1] - 150, 180, 400))
                    p.save()
                    p.setClipPath(path)
                    p.fillPath(sock, QColor("#2B2A30"))
                    p.setPen(QPen(QColor("#4A4850"), 3))
                    p.drawLine(QPointF(knee[0] - 90, knee[1] - 146), QPointF(knee[0] + 90, knee[1] - 146))
                    p.restore()
                    p.setPen(QPen(QColor(LINE), 3.2))
                    p.setBrush(Qt.NoBrush)
                    p.drawPath(path)
                else:
                    pants = "#3A3D52" if s.outfit != "hoodie" else "#4A4E62"
                    fill_outline(p, path, pants, shade_path=_side_shade(hip, knee, sgn, 70), shade_color=shade(pants, 0.8))
            else:
                path = capsule(knee, ankle, 50, 34)
                col = "#2B2A30" if (girl and s.outfit in ("sailor", "dress")) else ("#3A3D52" if s.outfit != "hoodie"
                                                                                    else "#4A4E62")
                fill_outline(p, path, col, shade_path=_side_shade(knee, ankle, sgn, 50), shade_color=shade(col, 0.75))
                shoe = smooth([(ankle[0] - 44, ankle[1] - 10), (ankle[0] + 44, ankle[1] - 14),
                               (ankle[0] + 50 + sgn * 26, ankle[1] + 40), (ankle[0] + sgn * 30, ankle[1] + 70),
                               (ankle[0] - 46, ankle[1] + 62)])
                fill_outline(p, shoe, "#5A3B36" if girl else "#2D2B33", light_path=_band(ankle[1] - 10, ankle[1] + 14),
                             light_color="#7A5650" if girl else "#4A4852")
        return draw

    for side, hip, knee, ankle, sgn, lr, kr in (("L", hipL, kneeL, ankleL, 1, legL, kneeLr),
                                                ("R", hipR, kneeR, ankleR, -1, legR, kneeRr)):
        name = "Левая" if side == "L" else "Правая"
        B.layer(f"{name} голень", capsule(knee, ankle, 50, 34).united(ellipse(ankle[0] + sgn * 20, ankle[1] + 30, 80, 60)),
                leg_draw(hip, knee, ankle, sgn, False), kr.id, spacing=55)
        B.layer(f"{name} бедро", capsule(hip, knee, 70, 50), leg_draw(hip, knee, ankle, sgn, True), lr.id, spacing=55)

    # ---------------------------------------------------------------- torso
    def torso_path():
        pts = [(cx - 44, 690), (cx - 50, 735), (cx - sh_w, sh_y), (cx - sh_w - 22, 860), (cx - sh_w + 8, 980),
               (cx - waist_w, waist_y), (cx - hip_w + (0 if girl else 10), hip_y + 40), (cx, hip_y + 60),
               (cx + hip_w - (0 if girl else 10), hip_y + 40), (cx + waist_w, waist_y), (cx + sh_w - 8, 980),
               (cx + sh_w + 22, 860), (cx + sh_w, sh_y), (cx + 50, 735), (cx + 44, 690)]
        return smooth(pts, tension=0.35)

    def draw_torso(p):
        neck_p = QPainterPath()
        neck_p.addRoundedRect(QRectF(cx - 44, 600, 88, 190), 30, 30)
        fill_outline(p, neck_p, skin, shade_path=_band(600, 700), shade_color=skin_sh)
        tp = torso_path().intersected(_band(732, 2000))  # the neck above the neckline stays skin
        o = s.outfit
        if o == "sailor":
            fill_outline(p, tp, "#F7F5F0", shade_path=_side_shade((cx, 800), (cx, 1250), 1, 160), shade_color="#E3DED6")
            collar = smooth([(cx - 52, 712), (cx - sh_w + 6, sh_y + 4), (cx - sh_w - 4, 905), (cx - 60, 905),
                             (cx, 960), (cx + 60, 905), (cx + sh_w + 4, 905), (cx + sh_w - 6, sh_y + 4), (cx + 52, 712),
                             (cx, 880)], tension=0.25)
            fill_outline(p, collar, cloth, light_path=_band(870, 905), light_color=shade(cloth, 1.35))
            p.setPen(QPen(QColor("#FFFFFF"), 4))
            p.drawPath(smooth([(cx - sh_w + 22, sh_y + 30), (cx - sh_w + 14, 885), (cx - 52, 886), (cx, 935)], False))
            p.drawPath(smooth([(cx + sh_w - 22, sh_y + 30), (cx + sh_w - 14, 885), (cx + 52, 886), (cx, 935)], False))
            bow = smooth([(cx, 905), (cx - 70, 870), (cx - 84, 930), (cx - 30, 940), (cx - 60, 1020), (cx - 20, 1015),
                          (cx, 950), (cx + 20, 1015), (cx + 60, 1020), (cx + 30, 940), (cx + 84, 930), (cx + 70, 870)],
                         tension=0.3)
            fill_outline(p, bow, s.accent, shade_path=_band(940, 1030), shade_color=shade(s.accent, 0.8))
        elif o == "hoodie":
            fill_outline(p, tp, cloth, shade_path=_side_shade((cx, 800), (cx, 1250), 1, 160),
                         shade_color=shade(cloth, 0.85))
            hood = smooth([(cx - 120, 760), (cx - 60, 820), (cx, 832), (cx + 60, 820), (cx + 120, 760), (cx, 790)])
            fill_outline(p, hood, shade(cloth, 0.78))
            p.setPen(QPen(QColor("#F4F1EA"), 6, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(cx - 34, 830), QPointF(cx - 40, 960))
            p.drawLine(QPointF(cx + 34, 830), QPointF(cx + 40, 975))
            pocket = smooth([(cx - 120, 1100), (cx + 120, 1100), (cx + 140, 1210), (cx - 140, 1210)], tension=0.1)
            fill_outline(p, pocket, shade(cloth, 0.9), lw=2.5)
        elif o == "dress":
            fill_outline(p, tp, cloth, shade_path=_side_shade((cx, 800), (cx, 1250), 1, 160),
                         shade_color=shade(cloth, 0.85))
            neckline = smooth([(cx - 70, 760), (cx, 850), (cx + 70, 760), (cx, 790)])
            fill_outline(p, neckline, skin, lw=2.5)
            belt = QPainterPath()
            belt.addRect(QRectF(cx - waist_w - 20, waist_y - 30, 2 * waist_w + 40, 46))
            p.save()
            p.setClipPath(tp)
            p.fillPath(belt, QColor("#F4F1EA"))
            p.restore()
            bow = smooth([(cx, waist_y - 8), (cx - 60, waist_y - 40), (cx - 60, waist_y + 26), (cx, waist_y - 4),
                          (cx + 60, waist_y + 26), (cx + 60, waist_y - 40)], tension=0.3)
            fill_outline(p, bow, "#F4F1EA", lw=2.5)
        else:  # shirt
            fill_outline(p, tp, "#F4F2EE", shade_path=_side_shade((cx, 800), (cx, 1250), 1, 160), shade_color="#DCD8D0")
            collar = smooth([(cx - 50, 745), (cx - 80, 830), (cx, 800), (cx + 80, 830), (cx + 50, 745), (cx, 780)])
            fill_outline(p, collar, "#FFFFFF", lw=2.5)
            tie = smooth([(cx - 18, 800), (cx + 18, 800), (cx + 30, 1040), (cx, 1080), (cx - 30, 1040)], tension=0.1)
            fill_outline(p, tie, cloth)
            belt = QPainterPath()
            belt.addRect(QRectF(cx - 200, 1200, 400, 34))
            p.save()
            p.setClipPath(tp)
            p.fillPath(belt, QColor("#2D2B33"))
            p.restore()
        p.setPen(QPen(QColor(LINE), 3.2))
        p.setBrush(Qt.NoBrush)
        p.drawPath(tp)
    B.layer("Тело", torso_path().united(_rect(cx - 50, 600, 100, 220)), draw_torso, torso.id, spacing=60)

    # ---------------------------------------------------------------- skirt
    if girl and s.outfit in ("sailor", "dress"):
        def skirt_path():
            return smooth([(cx - waist_w - 4, waist_y - 10), (cx + waist_w + 4, waist_y - 10), (cx + 250, 1450),
                           (cx + 120, 1480), (cx, 1470), (cx - 120, 1480), (cx - 250, 1450)], tension=0.25)

        def draw_skirt(p):
            sp = skirt_path()
            col = cloth if s.outfit == "sailor" else shade(cloth, 1.0)
            fill_outline(p, sp, col, shade_path=_side_shade((cx, 1120), (cx, 1480), 1, 220), shade_color=shade(col, 0.82))
            p.save()
            p.setClipPath(sp)
            p.setPen(QPen(shade(col, 0.6), 2.4))
            for k in range(-5, 6):
                p.drawLine(QPointF(cx + k * 20, waist_y), QPointF(cx + k * 46, 1490))
            if s.outfit == "sailor":
                p.setPen(QPen(QColor("#F4F1EA"), 5))
                p.drawPath(smooth([(cx - 260, 1420), (cx, 1440), (cx + 260, 1420)], False))
            p.restore()
            p.setPen(QPen(QColor(LINE), 3.2))
            p.setBrush(Qt.NoBrush)
            p.drawPath(sp)
        B.layer("Юбка", skirt_path(), draw_skirt, skirt_w.id, spacing=60)

    # ---------------------------------------------------------------- arms (upper, fore, hand)
    sleeve = {"sailor": "#F7F5F0", "hoodie": cloth, "dress": cloth, "shirt": "#F4F2EE"}[s.outfit]
    long_sleeve = s.outfit in ("hoodie", "shirt") or (s.outfit == "sailor")

    def arm_layers(side, sh, el, wr, sgn, r_arm, r_elb, r_hand):
        nm = "Левая" if side == "L" else "Правая"

        def upper(p):
            path = capsule(sh, el, 46, 38)
            fill_outline(p, path, sleeve, shade_path=_side_shade(sh, el, -sgn, 46), shade_color=shade(sleeve, 0.86))
            if s.outfit == "dress":  # puffy sleeve over the upper arm
                puff = ellipse(sh[0] + sgn * 8, sh[1] + 50, 60, 72)
                fill_outline(p, puff, cloth, light_path=_band(sh[1], sh[1] + 30), light_color=shade(cloth, 1.15))
                skin_part = capsule((sh[0] + sgn * 10, sh[1] + 110), el, 34, 32)
                fill_outline(p, skin_part, skin)

        def fore(p):
            path = capsule(el, wr, 38, 30)
            col = sleeve if long_sleeve else skin
            fill_outline(p, path, col, shade_path=_side_shade(el, wr, -sgn, 38), shade_color=shade(col, 0.86))
            if long_sleeve:
                cuff = capsule((wr[0] - sgn * 2, wr[1] - 40), (wr[0], wr[1] - 6), 33, 32)
                fill_outline(p, cuff, shade(sleeve, 0.92) if s.outfit != "sailor" else cloth, lw=2.5)

        def hand(p):
            palm = smooth([(wr[0] - 32, wr[1] - 14), (wr[0] + 32, wr[1] - 14), (wr[0] + 38, wr[1] + 52),
                           (wr[0] + 18, wr[1] + 118), (wr[0] - 10, wr[1] + 122), (wr[0] - 32, wr[1] + 70)])
            thumb = capsule((wr[0] - sgn * 22, wr[1] + 22), (wr[0] - sgn * 46, wr[1] + 74), 15, 12)
            fill_outline(p, palm.united(thumb), skin, shade_path=_side_shade(wr, (wr[0], wr[1] + 90), sgn, 30),
                         shade_color=skin_sh, lw=2.8)

        B.layer(f"{nm} кисть", _rect(wr[0] - 75, wr[1] - 30, 150, 170), hand, r_hand.id, spacing=30)
        B.layer(f"{nm} предплечье", capsule(el, wr, 40, 34), fore, r_elb.id, spacing=45)
        B.layer(f"{nm} плечо", capsule(sh, el, 48, 40).united(ellipse(sh[0] + sgn * 8, sh[1] + 50, 64, 76)), upper,
                r_arm.id, spacing=45)

    arm_layers("R", shoulderR, elbowR, wristR, -1, armR, elbR, handR)
    arm_layers("L", shoulderL, elbowL, wristL, 1, armL, elbL, handL)

    # ---------------------------------------------------------------- face
    def face_path():
        w = face_w
        pts = [(cx - w, 380), (cx - w + 4, 470), (cx - w + 22, 560), (cx - 92, 630), (cx - 34, chin_y - 6),
               (cx, chin_y), (cx + 34, chin_y - 6), (cx + 92, 630), (cx + w - 22, 560), (cx + w - 4, 470), (cx + w, 380),
               (cx + w - 30, 270), (cx, 236), (cx - w + 30, 270)]
        return smooth(pts, tension=0.45)

    def draw_face(p):
        fp = face_path()
        sh = QPainterPath()
        sh.addRect(QRectF(cx - 250, 250, 500, 150))
        fill_outline(p, fp, skin, shade_path=sh, shade_color=skin_sh, lw=3.0)
        # soft cheek glow
        g = QRadialGradient(QPointF(cx, 560), 140)
        g.setColorAt(0, QColor(255, 255, 255, 40))
        g.setColorAt(1, QColor(255, 255, 255, 0))
        p.save()
        p.setClipPath(fp)
        p.fillRect(QRectF(cx - 200, 400, 400, 300), QBrush(g))
        p.restore()
    B.layer("Лицо", face_path(), draw_face, face_w_.id, spacing=48)

    # ears (cat ears go with hair, human ears are hidden by hair)

    # blush
    def draw_blush(p):
        for sgn in (-1, 1):
            g = QRadialGradient(QPointF(cx + sgn * 100, 572), 52)
            g.setColorAt(0, QColor(240, 120, 130, 140))
            g.setColorAt(1, QColor(240, 120, 130, 0))
            p.setBrush(QBrush(g))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx + sgn * 100, 572), 62, 34)
            p.setPen(QPen(QColor(220, 90, 100, 160), 2.4, Qt.SolidLine, Qt.RoundCap))
            for k in range(3):
                x = cx + sgn * 80 + k * 16 * sgn
                p.drawLine(QPointF(x, 584), QPointF(x + 8 * sgn, 566))
    blush = B.layer("Румянец", _rect(cx - 170, 530, 340, 90), draw_blush, feat.id, spacing=40)

    # nose
    def draw_nose(p):
        p.setPen(QPen(QColor(skin_sh).darker(118), 3, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(cx + 4, 552), QPointF(cx + 8, 566))
    B.layer("Нос", _rect(cx - 14, 540, 36, 40), draw_nose, feat.id, spacing=20)

    # mouth
    mouth_y = 610.0

    def mouth_inner_path():
        return smooth([(cx - 30, mouth_y), (cx + 30, mouth_y), (cx + 24, mouth_y + 26), (cx, mouth_y + 40),
                       (cx - 24, mouth_y + 26)], tension=0.4)

    def draw_mouth_inner(p):
        mp = mouth_inner_path()
        p.fillPath(mp, QColor("#7A2E36"))
        tongue = ellipse(cx, mouth_y + 34, 20, 13)
        p.save()
        p.setClipPath(mp)
        p.fillPath(tongue, QColor("#E9828C"))
        teeth = QPainterPath()
        teeth.addRect(QRectF(cx - 30, mouth_y - 4, 60, 9))
        p.fillPath(teeth, QColor("#FFFFFF"))
        p.restore()
        p.setPen(QPen(QColor(LINE), 2.6))
        p.drawPath(mp)
    mouth_in = B.layer("Рот (внутри)", mouth_inner_path(), draw_mouth_inner, feat.id, spacing=8)

    def draw_mouth_line(p):
        p.setPen(QPen(QColor(LINE), 3.0, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(smooth([(cx - 26, mouth_y + 1), (cx - 8, mouth_y + 5), (cx + 8, mouth_y + 5), (cx + 26, mouth_y + 1)],
                          False))
    mouth_ln = B.layer("Рот (линия)", _rect(cx - 34, mouth_y - 8, 68, 22), draw_mouth_line, feat.id, spacing=8)

    # eyes
    eye_y = 498.0
    eye_dx = 80.0
    ew, eh = 50.0 * es, 60.0 * es
    eyes = {}

    def eye_white(ex):
        return smooth([(ex - ew, eye_y - eh * 0.45), (ex, eye_y - eh * 0.7), (ex + ew, eye_y - eh * 0.5),
                       (ex + ew * 0.92, eye_y + eh * 0.42), (ex, eye_y + eh * 0.62), (ex - ew * 0.92, eye_y + eh * 0.42)],
                      tension=0.6)

    def lash_curve(ex, sgn):
        outer = sgn  # outer corner side
        return [(ex - ew * 1.08 * outer, eye_y - eh * 0.36), (ex - ew * 0.4 * outer, eye_y - eh * 0.7),
                (ex + ew * 0.5 * outer, eye_y - eh * 0.66), (ex + ew * 1.12 * outer, eye_y - eh * 0.34),
                (ex + ew * 1.28 * outer, eye_y - eh * 0.2)]

    for side, sgn in (("R", -1), ("L", 1)):
        ex = cx + sgn * eye_dx
        nm = "Левый" if side == "L" else "Правый"
        white_p = eye_white(ex)

        def draw_white(p, wp=white_p, ex=ex):
            g = QLinearGradient(QPointF(ex, eye_y - eh), QPointF(ex, eye_y + eh))
            g.setColorAt(0, QColor("#E9EDF5"))
            g.setColorAt(0.45, QColor("#FFFFFF"))
            p.fillPath(wp, QBrush(g))
        white = B.layer(f"{nm} глаз: белок", white_p, draw_white, feat.id, spacing=14)

        def draw_iris(p, ex=ex):
            iris = ellipse(ex, eye_y + eh * 0.04, ew * 0.66, eh * 0.62)
            g = QLinearGradient(QPointF(ex, eye_y - eh * 0.6), QPointF(ex, eye_y + eh * 0.66))
            g.setColorAt(0, shade(s.eyes, 0.45))
            g.setColorAt(0.55, QColor(s.eyes))
            g.setColorAt(1, shade(s.eyes, 1.35))
            p.fillPath(iris, QBrush(g))
            p.fillPath(ellipse(ex, eye_y + eh * 0.02, ew * 0.3, eh * 0.34), shade(s.eyes, 0.3))
            p.setPen(QPen(shade(s.eyes, 0.35), 3))
            p.setBrush(Qt.NoBrush)
            p.drawPath(iris)
        iris = B.layer(f"{nm} глаз: радужка", ellipse(ex, eye_y, ew * 0.7, eh * 0.7), draw_iris, feat.id, spacing=14)
        iris.masks = [white.id]

        def draw_hl(p, ex=ex):
            p.fillPath(ellipse(ex - ew * 0.25, eye_y - eh * 0.22, ew * 0.2, eh * 0.16), QColor("#FFFFFF"))
            p.fillPath(ellipse(ex + ew * 0.24, eye_y + eh * 0.3, ew * 0.09, eh * 0.07), QColor(255, 255, 255, 220))
        hl = B.layer(f"{nm} глаз: блик", _rect(ex - ew * 0.6, eye_y - eh * 0.5, ew * 1.1, eh), draw_hl, feat.id,
                     spacing=12)
        hl.masks = [white.id]

        def draw_lash(p, ex=ex, sgn=sgn):
            pts = lash_curve(ex, sgn)
            path = smooth(pts, False)
            p.setPen(QPen(QColor("#2E2230"), 7.5 if girl else 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)
            if girl:  # flick at the outer corner
                fl = smooth([pts[-2], (pts[-1][0] + sgn * 10, pts[-1][1] - 14), (pts[-1][0] + sgn * 4, pts[-1][1] + 4)],
                            False)
                p.setPen(QPen(QColor("#2E2230"), 4.5, Qt.SolidLine, Qt.RoundCap))
                p.drawPath(fl)
        lash = B.layer(f"{nm} глаз: верхнее веко", _rect(ex - ew * 1.5, eye_y - eh * 0.95, ew * 3, eh * 0.9), draw_lash,
                       feat.id, spacing=12)

        def draw_low(p, ex=ex, sgn=sgn):
            p.setPen(QPen(QColor("#3E2C34"), 3, Qt.SolidLine, Qt.RoundCap))
            p.drawPath(smooth([(ex - ew * 0.5 * sgn, eye_y + eh * 0.6), (ex + ew * 0.35 * sgn, eye_y + eh * 0.58),
                               (ex + ew * 0.86 * sgn, eye_y + eh * 0.42)], False))
        low = B.layer(f"{nm} глаз: нижнее веко", _rect(ex - ew * 1.1, eye_y + eh * 0.25, ew * 2.2, eh * 0.55), draw_low,
                      feat.id, spacing=10)

        def draw_brow(p, ex=ex, sgn=sgn):
            p.setPen(QPen(shade(hair, 0.55), 5 if girl else 7.5, Qt.SolidLine, Qt.RoundCap))
            p.drawPath(smooth([(ex - ew * 0.9 * sgn, eye_y - eh * 1.05), (ex, eye_y - eh * 1.22),
                               (ex + ew * 0.95 * sgn, eye_y - eh * 1.12)], False))
        brow = B.layer(f"{nm}: бровь", _rect(ex - ew * 1.2, eye_y - eh * 1.42, ew * 2.4, eh * 0.55), draw_brow,
                       feat.id, spacing=12)
        eyes[side] = dict(ex=ex, sgn=sgn, white=white, iris=iris, hl=hl, lash=lash, low=low, brow=brow)

    # ---------------------------------------------------------------- side locks + bangs + accessories
    def side_paths():
        out = []
        for sgn in (-1, 1):
            x0 = cx + sgn * 170
            if s.hair_style == "short":
                pts = [(x0 - sgn * 6, 330), (x0 + sgn * 46, 420), (x0 + sgn * 40, 560), (x0 + sgn * 14, 640),
                       (x0 - sgn * 10, 560)]
            elif s.hair_style == "bob":
                pts = [(x0 - sgn * 8, 330), (x0 + sgn * 54, 430), (x0 + sgn * 56, 620), (x0 + sgn * 34, 720),
                       (x0 + sgn * 8, 700), (x0 - sgn * 14, 560)]
            else:
                pts = [(x0 - sgn * 10, 330), (x0 + sgn * 52, 430), (x0 + sgn * 64, 640), (x0 + sgn * 46, 830),
                       (x0 + sgn * 18, 870), (x0 + sgn * 2, 780), (x0 - sgn * 16, 560)]
            out.append(smooth(pts if sgn > 0 else list(reversed(pts)), tension=0.5))
        return out

    def draw_sides(p):
        for path in side_paths():
            sh_p = QPainterPath()
            sh_p.addRect(QRectF(cx - 400, 640, 800, 300))
            fill_outline(p, path, hair, shade_path=sh_p, shade_color=hair_sh)
    B.layer("Пряди", _union(side_paths()), draw_sides, side_w.id, spacing=40)

    def bangs_path():
        top = [(cx - 228, 470), (cx - 236, 360), (cx - 190, 255), (cx - 90, 196), (cx, 186), (cx + 90, 196),
               (cx + 190, 255), (cx + 236, 360), (cx + 228, 470)]
        if s.hair_style == "short" and not girl:
            tips = [(cx + 188, 420), (cx + 150, 360), (cx + 120, 432), (cx + 70, 362), (cx + 30, 440), (cx - 10, 368),
                    (cx - 50, 440), (cx - 100, 360), (cx - 130, 430), (cx - 170, 360), (cx - 200, 430)]
        else:
            tips = [(cx + 196, 460), (cx + 172, 380), (cx + 140, 452), (cx + 104, 372), (cx + 60, 458), (cx + 24, 380),
                    (cx - 10, 456), (cx - 48, 376), (cx - 92, 452), (cx - 128, 372), (cx - 166, 446), (cx - 186, 380),
                    (cx - 206, 456)]
        path = QPainterPath(QPointF(*top[0]))
        sm = smooth(top, False)
        path = sm
        for q in tips:
            path.lineTo(QPointF(*q))
        path.closeSubpath()
        return path

    def draw_bangs(p):
        bp = bangs_path()
        light = QPainterPath()
        light.addEllipse(QPointF(cx, 262), 190, 40)
        inner = QPainterPath()
        inner.addEllipse(QPointF(cx, 262), 172, 26)
        fill_outline(p, bp, hair, shade_path=_band(370, 470), shade_color=hair_sh,
                     light_path=light.subtracted(inner), light_color=hair_li)
        p.save()
        p.setClipPath(bp)
        p.setPen(QPen(shade(hair, 0.7), 2.0, Qt.SolidLine, Qt.RoundCap))
        for k in (-4, -2, -1, 1, 2, 4):
            p.drawPath(smooth([(cx + k * 22, 300), (cx + k * 34, 360), (cx + k * 38, 420)], False))
        p.restore()
    B.layer("Чёлка", bangs_path(), draw_bangs, bangs_w.id, spacing=40)

    acc = s.accessory
    if acc == "cat_ears":
        def ears_path():
            out = []
            for sgn in (-1, 1):
                out.append(smooth([(cx + sgn * 90, 210), (cx + sgn * 190, 100), (cx + sgn * 215, 260)], tension=0.2))
            return _union(out)

        def draw_ears(p):
            ep = ears_path()
            fill_outline(p, ep, hair)
            for sgn in (-1, 1):
                p.fillPath(smooth([(cx + sgn * 120, 215), (cx + sgn * 185, 135), (cx + sgn * 196, 236)], tension=0.2),
                           QColor("#F7B6C8"))
        ears = B.layer("Ушки", ears_path(), draw_ears, bangs_w.id, spacing=30, order=hb.order + 1)
        del ears
    elif acc == "ribbon":
        def ribbon_path():
            x, y = cx + 190, 250
            return smooth([(x, y), (x + 70, y - 60), (x + 96, y + 10), (x + 40, y + 24), (x + 80, y + 90), (x + 30, y + 80),
                           (x, y + 20), (x - 30, y + 80), (x - 80, y + 90), (x - 40, y + 24), (x - 96, y + 10),
                           (x - 70, y - 60)], tension=0.25)

        def draw_ribbon(p):
            fill_outline(p, ribbon_path(), s.accent, shade_path=_band(270, 360), shade_color=shade(s.accent, 0.78))
            p.fillPath(ellipse(cx + 190, 262, 18, 16), shade(s.accent, 0.85))
        B.layer("Бант", ribbon_path(), draw_ribbon, bangs_w.id, spacing=24)
    elif acc == "clip":
        def clip_path():
            q = QPainterPath()
            q.addRoundedRect(QRectF(cx - 200, 300, 70, 22), 10, 10)
            return q

        def draw_clip(p):
            fill_outline(p, clip_path(), s.accent, light_path=_band(300, 308), light_color=shade(s.accent, 1.3), lw=2.5)
        B.layer("Заколка", clip_path(), draw_clip, bangs_w.id, spacing=12)

    # arms are drawn last so a raised hand stays in front of the face and hair
    top = max(x.order for x in m.meshes())
    for k, nm in enumerate(("Правая плечо", "Правая предплечье", "Правая кисть", "Левая плечо", "Левая предплечье",
                            "Левая кисть")):
        lay = B.layers.get(nm)
        if lay is not None:
            lay.order = top + 10 * (k + 1)

    # ================================================================ rig: keyforms
    rig(B, s, dict(cx=cx, eye_y=eye_y, ew=ew, eh=eh, mouth_y=mouth_y, eyes=eyes, blush=blush,
                   mouth_in=mouth_in, mouth_ln=mouth_ln, face=face_w_, feat=feat, bangs=bangs_w, side=side_w,
                   back=hair_back_w, head_rot=head_rot, body_rot=body_rot, torso=torso, skirt=skirt_w,
                   arms=(armL, elbL, handL, armR, elbR, handR), legs=(legL, kneeLr, legR, kneeRr)))
    m.meta.update({"author": "Мю — конструктор персонажа", "spec": s.to_dict()})
    from .poses import add_default_poses
    add_default_poses(m)
    m.reset_values()
    return m


def _rect(x, y, w, h):
    p = QPainterPath()
    p.addRect(QRectF(x, y, w, h))
    return p


def _band(y0, y1):
    return _rect(-5000, y0, 10000, y1 - y0)


def _union(paths):
    out = QPainterPath()
    for p in paths:
        out = out.united(p)
    return out


def _side_shade(a, b, sgn, r):
    """Shadow on one side of a limb / body running from a to b."""
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    nx, ny = -math.sin(ang) * sgn, math.cos(ang) * sgn
    off = r * 0.45
    return capsule((a[0] + nx * (r + off), a[1] + ny * (r + off)), (b[0] + nx * (r + off), b[1] + ny * (r + off)),
                   r, r)


# ====================================================================== rig
def rig(B, s, g):
    cx, eye_y, ew, eh = g["cx"], g["eye_y"], g["ew"], g["eh"]

    def bulge(t):
        return 0.35 + 0.65 * np.sin(np.pi * np.clip(t, 0, 1))

    # head turn: every head warp shifts by its depth, more in the middle (a sphere turning)
    def turn(warp, depth, kx=26.0, ky=22.0):
        uv = warp.uv_of(warp.rest_grid())

        def fx(pts, k):
            out = np.zeros_like(pts)
            out[:, 0] = np.sign(k) * depth * kx * bulge(uv[:, 0]) * (abs(k) / 30)
            out[:, 1] = -np.sign(k) * depth * 4 * (uv[:, 0] - 0.5) * (abs(k) / 30) * 0  # keep level
            return out

        def fy(pts, k):
            out = np.zeros_like(pts)
            out[:, 1] = -np.sign(k) * depth * ky * bulge(uv[:, 1]) * (abs(k) / 30)
            return out
        B.keys_fn(warp, "ParamAngleX", [-30, 0, 30], fx)
        B.keys_fn(warp, "ParamAngleY", [-30, 0, 30], fy)

    turn(g["face"], 1.0)
    turn(g["feat"], 0.55)
    turn(g["bangs"], 1.35)
    turn(g["side"], 1.15)
    turn(g["back"], -0.55)
    B.keys_rot(g["head_rot"], "ParamAngleZ", {-30: -16.0, 0: 0.0, 30: 16.0})

    # hair sway (physics drives these)
    def sway(warp, pid, amp, power=1.6):
        uv = warp.uv_of(warp.rest_grid())

        def f(pts, k):
            out = np.zeros_like(pts)
            out[:, 0] = k * amp * np.clip(uv[:, 1], 0, 1) ** power
            out[:, 1] = -abs(k) * amp * 0.12 * np.clip(uv[:, 1], 0, 1) ** power
            return out
        B.keys_fn(warp, pid, [-1, 0, 1], f)
    sway(g["bangs"], "ParamHairFront", 26)
    sway(g["side"], "ParamHairSide", 44)
    sway(g["back"], "ParamHairBack", 54, 1.3)
    if g["skirt"] is not None and any(isinstance(n, ArtMesh) and n.parent == g["skirt"].id for n in B.model.nodes.values()):
        sway(g["skirt"], "ParamSkirt", 46, 1.8)

    # body
    torso = g["torso"]
    tuv = torso.uv_of(torso.rest_grid())

    def body_x(pts, k):
        out = np.zeros_like(pts)
        out[:, 0] = (k / 10) * 22 * bulge(tuv[:, 0]) * (1 - 0.6 * tuv[:, 1])
        return out

    def body_y(pts, k):
        out = np.zeros_like(pts)
        out[:, 1] = -(k / 10) * 14 * bulge(tuv[:, 1]) * (1 - tuv[:, 1])
        return out

    def breath(pts, k):
        out = np.zeros_like(pts)
        out[:, 1] = -k * 9 * np.clip(1 - tuv[:, 1] * 1.4, 0, 1)
        out[:, 0] = k * 3 * (tuv[:, 0] - 0.5) * np.clip(1 - tuv[:, 1] * 1.4, 0, 1)
        return out
    B.keys_fn(torso, "ParamBodyAngleX", [-10, 0, 10], body_x)
    B.keys_fn(torso, "ParamBodyAngleY", [-10, 0, 10], body_y)
    B.keys_fn(torso, "ParamBreath", [0, 1], breath)
    B.keys_rot(g["body_rot"], "ParamBodyAngleZ", {-10: -5.0, 0: 0.0, 10: 5.0})

    # arms and legs: parameter value = degrees (rest pose hangs down)
    armL, elbL, handL, armR, elbR, handR = g["arms"]
    for node, pid in ((armL, "ParamArmLA"), (elbL, "ParamArmLB"), (handL, "ParamHandL"), (armR, "ParamArmRA"),
                      (elbR, "ParamArmRB"), (handR, "ParamHandR")):
        p = B.model.param(pid)
        B.keys_rot(node, pid, {p.min: p.min, 0.0: 0.0, p.max: p.max})
    legL, kneeL, legR, kneeR = g["legs"]
    for node, pid, sgn in ((legL, "ParamLegL", 1), (legR, "ParamLegR", 1), (kneeL, "ParamKneeL", -1),
                           (kneeR, "ParamKneeR", 1)):
        p = B.model.param(pid)
        B.keys_rot(node, pid, {p.min: p.min * sgn, p.max: p.max * sgn} if p.min != 0 else {0: 0.0, p.max: p.max * sgn})

    # eyes
    for side, e in g["eyes"].items():
        ex = e["ex"]
        sgn = e["sgn"]
        pid_open = "ParamEyeLOpen" if side == "L" else "ParamEyeROpen"
        pid_smile = "ParamEyeLSmile" if side == "L" else "ParamEyeRSmile"
        lid = eye_y + eh * 0.34  # where the closed eye line sits

        def lid_y(x):
            t = np.clip((x - ex) / (ew * 1.1), -1, 1)
            return lid + eh * 0.1 * (1 - t * t)

        def squash(pts, k, strength=0.94):
            out = np.zeros_like(pts)
            if k == 0:
                out[:, 1] = (lid_y(pts[:, 0]) - pts[:, 1]) * strength
            elif k > 1:
                out[:, 1] = (pts[:, 1] - lid) * 0.12 * (k - 1) / 0.2
            return out

        def lash(pts, k):
            out = np.zeros_like(pts)
            if k == 0:
                # the lash keeps its thickness but lies on the closed-eye line
                curve = np.interp(pts[:, 0], *_curve_xy(ex, sgn, ew, eh, eye_y))
                out[:, 1] = lid_y(pts[:, 0]) - curve
                out[:, 0] = (pts[:, 0] - ex) * 0.04
            elif k > 1:
                out[:, 1] = -eh * 0.14 * (k - 1) / 0.2
            return out
        for part in ("white", "iris", "hl"):
            B.keys_fn(e[part], pid_open, [0, 0.15, 1, 1.2],
                      lambda pts, k: squash(pts, 0) * (1 - k / 0.15) * 0.97 if k <= 0.15 else squash(pts, k))
            b = e[part].binding(pid_open)
            b.forms[0]["opacity"] = 0.0
        B.keys_fn(e["lash"], pid_open, [0, 0.15, 1, 1.2],
                  lambda pts, k: lash(pts, 0) * (1 - k / 0.15) * 0.9 if k <= 0.15 else lash(pts, k))

        def smile_low(pts, k):
            out = np.zeros_like(pts)
            t = np.clip((pts[:, 0] - ex) / (ew * 1.1), -1, 1)
            out[:, 1] = -k * eh * (0.5 + 0.22 * (1 - t * t))
            return out

        def smile_white(pts, k):
            out = np.zeros_like(pts)
            below = np.clip((pts[:, 1] - (eye_y - eh * 0.2)) / (eh * 0.8), 0, 1)
            out[:, 1] = -k * eh * 0.55 * below
            return out
        B.keys_fn(e["low"], pid_smile, [0, 1], smile_low)

        def smile_lash(pts, k):
            out = np.zeros_like(pts)
            t = np.clip((pts[:, 0] - ex) / (ew * 1.1), -1, 1)
            out[:, 1] = -k * eh * 0.22 * (1 - t * t)
            return out
        B.keys_fn(e["lash"], pid_smile, [0, 1], smile_lash)
        for part in ("white", "iris", "hl"):
            B.keys_fn(e[part], pid_smile, [0, 1], smile_white)

        def look_x(pts, k):
            out = np.zeros_like(pts)
            out[:, 0] = k * ew * 0.3
            return out

        def look_y(pts, k):
            out = np.zeros_like(pts)
            out[:, 1] = -k * eh * 0.18
            return out
        for part in ("iris", "hl"):
            B.keys_fn(e[part], "ParamEyeBallX", [-1, 0, 1], look_x)
            B.keys_fn(e[part], "ParamEyeBallY", [-1, 0, 1], look_y)

        bc = np.array([ex, eye_y - eh * 1.15])

        def brow_y(pts, k):
            out = np.zeros_like(pts)
            out[:, 1] = -k * 16
            return out

        def brow_ang(pts, k):
            ang = math.radians(k * 16) * (-sgn)  # positive = angry (inner end down)
            c, si = math.cos(ang), math.sin(ang)
            d = pts - bc
            rot = np.stack([c * d[:, 0] - si * d[:, 1], si * d[:, 0] + c * d[:, 1]], axis=1)
            return rot - d
        B.keys_fn(e["brow"], "ParamBrowLY" if side == "L" else "ParamBrowRY", [-1, 0, 1], brow_y)
        B.keys_fn(e["brow"], "ParamBrowLAngle" if side == "L" else "ParamBrowRAngle", [-1, 0, 1], brow_ang)

    # mouth
    my = g["mouth_y"]

    def form(pts, k, amp=12.0):
        out = np.zeros_like(pts)
        t = np.clip((pts[:, 0] - cx) / 30.0, -1.3, 1.3)
        out[:, 1] = -k * amp * (t * t) + k * amp * 0.25
        out[:, 0] = k * 4 * t
        return out

    def inner_open(pts, k):
        out = np.zeros_like(pts)
        if k == 0:
            out[:, 1] = (my - pts[:, 1]) * 0.96
        elif k < 1:
            out[:, 1] = (my - pts[:, 1]) * 0.75
        return out

    def line_open(pts, k):
        out = np.zeros_like(pts)
        out[:, 1] = -k * 4
        return out
    B.keys_fn(g["mouth_in"], "ParamMouthOpenY", [0, 0.1, 1], inner_open)
    B.keys_opacity(g["mouth_in"], "ParamMouthOpenY", {0: 0.0, 0.1: 1.0, 1: 1.0})
    B.keys_fn(g["mouth_in"], "ParamMouthForm", [-1, 0, 1], lambda pts, k: form(pts, k, 10))
    B.keys_fn(g["mouth_ln"], "ParamMouthForm", [-1, 0, 1], form)
    B.keys_fn(g["mouth_ln"], "ParamMouthOpenY", [0, 1], line_open)
    B.keys_opacity(g["blush"], "ParamCheek", {0: 0.0, 1: 1.0})

    # physics
    m = B.model
    m.physics = [
        PhysGroup(name="Чёлка", inputs=[{"param": "ParamAngleX", "weight": 0.6, "kind": "x"},
                                         {"param": "ParamAngleZ", "weight": 0.4, "kind": "angle"},
                                         {"param": "ParamBodyAngleX", "weight": 0.3, "kind": "x"}],
                  output="ParamHairFront", scale=1.1, stiffness=70, damping=8, gravity=0.5),
        PhysGroup(name="Пряди", inputs=[{"param": "ParamAngleX", "weight": 0.6, "kind": "x"},
                                         {"param": "ParamAngleZ", "weight": 0.6, "kind": "angle"},
                                         {"param": "ParamBodyAngleX", "weight": 0.4, "kind": "x"}],
                  output="ParamHairSide", scale=1.3, stiffness=45, damping=5, gravity=0.7),
        PhysGroup(name="Волосы сзади", inputs=[{"param": "ParamAngleX", "weight": 0.5, "kind": "x"},
                                                {"param": "ParamAngleZ", "weight": 0.7, "kind": "angle"},
                                                {"param": "ParamBodyAngleX", "weight": 0.6, "kind": "x"}],
                  output="ParamHairBack", scale=1.2, stiffness=30, damping=4, gravity=0.8),
        PhysGroup(name="Юбка", inputs=[{"param": "ParamBodyAngleX", "weight": 1.0, "kind": "x"},
                                        {"param": "ParamBodyAngleZ", "weight": 0.6, "kind": "angle"}],
                  output="ParamSkirt", scale=1.0, stiffness=40, damping=5, gravity=0.5),
    ]


def _curve_xy(ex, sgn, ew, eh, eye_y):
    """x-sorted samples of the upper lash curve (for np.interp)."""
    pts = [(ex - ew * 1.08 * sgn, eye_y - eh * 0.36), (ex - ew * 0.4 * sgn, eye_y - eh * 0.7),
           (ex + ew * 0.5 * sgn, eye_y - eh * 0.66), (ex + ew * 1.12 * sgn, eye_y - eh * 0.34),
           (ex + ew * 1.28 * sgn, eye_y - eh * 0.2)]
    pts.sort()
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    return xs, ys
