"""Face tracking for «Эфир»: a web camera drives the head, eyes, brows and mouth of the model.

MediaPipe's face models run through onnxruntime (converted from the official `face_landmarker.task`):
  * `face_detector.onnx` — BlazeFace short-range (128×128, 896 anchors): where the face is;
  * `face_landmarks_detector.onnx` — Face Mesh with attention (256×256): 478 landmarks with depth;
  * `face_blendshapes.onnx` — 146 landmarks → 52 ARKit-style blendshapes (blink, jawOpen, smile, brows, gaze…).
The head pose comes from fitting MediaPipe's canonical face (`canonical_face.npy`) to the 3-D landmarks (Kabsch).

`FaceTracker.process(rgb)` is pure numpy + onnxruntime (no Qt), so it runs in a worker thread and in the selftest;
the camera itself lives in `camera.py`."""
import math
from pathlib import Path

import numpy as np

from .paths import resource_path

ASSETS = resource_path("assets", "face")
MODEL_FILES = ("face_detector.onnx", "face_landmarks_detector.onnx", "face_blendshapes.onnx", "canonical_face.npy",
               "blendshape_subset.npy")
BLENDSHAPES = ["_neutral", "browDownLeft", "browDownRight", "browInnerUp", "browOuterUpLeft", "browOuterUpRight",
               "cheekPuff", "cheekSquintLeft", "cheekSquintRight", "eyeBlinkLeft", "eyeBlinkRight", "eyeLookDownLeft",
               "eyeLookDownRight", "eyeLookInLeft", "eyeLookInRight", "eyeLookOutLeft", "eyeLookOutRight",
               "eyeLookUpLeft", "eyeLookUpRight", "eyeSquintLeft", "eyeSquintRight", "eyeWideLeft", "eyeWideRight",
               "jawForward", "jawLeft", "jawOpen", "jawRight", "mouthClose", "mouthDimpleLeft", "mouthDimpleRight",
               "mouthFrownLeft", "mouthFrownRight", "mouthFunnel", "mouthLeft", "mouthLowerDownLeft",
               "mouthLowerDownRight", "mouthPressLeft", "mouthPressRight", "mouthPucker", "mouthRight",
               "mouthRollLower", "mouthRollUpper", "mouthShrugLower", "mouthShrugUpper", "mouthSmileLeft",
               "mouthSmileRight", "mouthStretchLeft", "mouthStretchRight", "mouthUpperUpLeft", "mouthUpperUpRight",
               "noseSneerLeft", "noseSneerRight"]
BS = {n: i for i, n in enumerate(BLENDSHAPES)}
# Face Mesh landmark indices (subject's right eye is on the image's left side)
EYE_R = (33, 160, 158, 133, 153, 144)      # outer corner, top ×2, inner corner, bottom ×2
EYE_L = (362, 385, 387, 263, 373, 380)
LIPS = (13, 14, 78, 308)                   # inner upper, inner lower, corners
BROW_R, BROW_L = 105, 334
IRIS_R, IRIS_L = 468, 473


def models_available(model_dir=None):
    d = Path(model_dir) if model_dir else ASSETS
    if not all((d / f).exists() for f in MODEL_FILES):
        return False
    import importlib.util
    return importlib.util.find_spec("onnxruntime") is not None


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def _anchors():
    """BlazeFace short-range: 128×128 input, strides 8 and 16 with 2 and 6 anchors per cell → 896 anchors."""
    out = []
    for stride, n in ((8, 2), (16, 6)):
        g = 128 // stride
        for y in range(g):
            for x in range(g):
                out.extend([((x + 0.5) / g, (y + 0.5) / g)] * n)
    return np.array(out, np.float32)


def resize_rgb(rgb, w, h):
    """Nearest-neighbour resize of an (H, W, 3) uint8 array (fast; the models are robust to it)."""
    ys = (np.arange(h) * rgb.shape[0] / h).astype(int)
    xs = (np.arange(w) * rgb.shape[1] / w).astype(int)
    return rgb[ys][:, xs]


def letterbox(rgb, size):
    """Pad the frame into a square of `size` keeping its aspect; returns (square, scale, dx, dy)."""
    h, w = rgb.shape[:2]
    k = size / max(h, w)
    nw, nh = max(1, int(round(w * k))), max(1, int(round(h * k)))
    small = resize_rgb(rgb, nw, nh)
    out = np.zeros((size, size, 3), np.uint8)
    dx, dy = (size - nw) // 2, (size - nh) // 2
    out[dy:dy + nh, dx:dx + nw] = small
    return out, k, dx, dy


def warp_crop(rgb, center, size, angle, out=256):
    """Rotated square crop (bilinear) → (out, out, 3) float32 in 0…1, plus the 2×3 matrix output px → frame px."""
    h, w = rgb.shape[:2]
    c, s = math.cos(angle), math.sin(angle)
    k = size / out
    # output pixel (u, v) → frame: center + R · ((u, v) − out/2) · k
    M = np.array([[c * k, -s * k, center[0] - (c - s) * k * out / 2],
                  [s * k, c * k, center[1] - (s + c) * k * out / 2]], np.float32)
    u, v = np.meshgrid(np.arange(out, dtype=np.float32), np.arange(out, dtype=np.float32))
    sx = M[0, 0] * u + M[0, 1] * v + M[0, 2]
    sy = M[1, 0] * u + M[1, 1] * v + M[1, 2]
    x0 = np.clip(np.floor(sx).astype(int), 0, w - 2)
    y0 = np.clip(np.floor(sy).astype(int), 0, h - 2)
    fx = np.clip(sx - x0, 0, 1)[:, :, None]
    fy = np.clip(sy - y0, 0, 1)[:, :, None]
    img = rgb.astype(np.float32)
    top = img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx
    bot = img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx
    crop = (top * (1 - fy) + bot * fy) / 255.0
    inside = (sx >= 0) & (sx <= w - 1) & (sy >= 0) & (sy <= h - 1)
    crop[~inside] = 0.0
    return crop.astype(np.float32), M


def kabsch(P, Q):
    """Rotation R (3×3) with P ≈ R·Q (both centred), by SVD."""
    Pc = P - P.mean(0)
    Qc = Q - Q.mean(0)
    H = Qc.T @ Pc
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1.0, 1.0, d])
    return Vt.T @ D @ U.T


def euler_deg(R):
    """Head angles (degrees) in the image convention: yaw > 0 — the face turns to the image's right, pitch > 0 —
    looks up, roll > 0 — the image-right eye is lower (the head leans to the subject's left)."""
    fwd = R[:, 2]            # the canonical face looks along +z (towards the camera)
    yaw = math.degrees(math.atan2(-fwd[0], fwd[2]))
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, fwd[1]))))
    right = R[:, 0]          # the canonical +x axis (subject's left … image right)
    roll = math.degrees(math.atan2(-right[1], right[0]))
    return yaw, pitch, roll


class FaceTracker:
    """Detects a face, then follows it from frame to frame (the detector runs again only when the face is lost)."""

    def __init__(self, model_dir=None, threads=2):
        import onnxruntime as ort
        d = Path(model_dir) if model_dir else ASSETS
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        so.log_severity_level = 3
        prov = ["CPUExecutionProvider"]
        self.det = ort.InferenceSession(str(d / "face_detector.onnx"), so, providers=prov)
        self.lmk = ort.InferenceSession(str(d / "face_landmarks_detector.onnx"), so, providers=prov)
        self.bsh = ort.InferenceSession(str(d / "face_blendshapes.onnx"), so, providers=prov)
        self.canon = np.load(d / "canonical_face.npy").astype(np.float32)
        self.subset = np.load(d / "blendshape_subset.npy")
        self.anchors = _anchors()
        self.roi = None            # (cx, cy, size, angle) in frame px, from the previous frame's landmarks
        self.last = None           # last result dict
        self.misses = 0

    # ------------------------------------------------------------------ detector
    def detect(self, rgb):
        sq, k, dx, dy = letterbox(rgb, 128)
        x = sq.astype(np.float32) / 127.5 - 1.0
        reg, cls = self.det.run(None, {self.det.get_inputs()[0].name: x[None]})
        scores = _sigmoid(cls[0, :, 0])
        best = scores > 0.5
        if not best.any():
            return None
        # weighted average of the overlapping candidates (MediaPipe's "blending" NMS)
        idx = np.nonzero(best)[0]
        top = idx[np.argmax(scores[idx])]
        r = reg[0]
        boxes = np.c_[self.anchors[idx] + r[idx, :2] / 128, r[idx, 2:4] / 128]
        tb = np.r_[self.anchors[top] + r[top, :2] / 128, r[top, 2:4] / 128]
        ov = (np.abs(boxes[:, 0] - tb[0]) < tb[2] * 0.5) & (np.abs(boxes[:, 1] - tb[1]) < tb[3] * 0.5)
        w = scores[idx][ov][:, None]
        box = (boxes[ov] * w).sum(0) / w.sum()
        kps = (self.anchors[idx][ov][:, None, :] + r[idx][ov][:, 4:16].reshape(-1, 6, 2) / 128)
        kps = (kps * w[:, :, None]).sum(0) / w.sum()
        to_frame = lambda p: ((p * 128 - [dx, dy]) / k)
        cx, cy = to_frame(box[:2])
        bw, bh = box[2] * 128 / k, box[3] * 128 / k
        return (cx, cy, bw, bh), to_frame(kps), float(scores[top])

    @staticmethod
    def roi_from_detection(box, kps):
        cx, cy, bw, bh = box
        angle = math.atan2(kps[1][1] - kps[0][1], kps[1][0] - kps[0][0])   # eye line → horizontal
        return cx, cy, max(bw, bh) * 1.5, angle

    @staticmethod
    def roi_from_landmarks(lm):
        xy = lm[:468, :2]
        lo, hi = xy.min(0), xy.max(0)
        angle = math.atan2(lm[263][1] - lm[33][1], lm[263][0] - lm[33][0])
        return (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, max(hi - lo) * 1.5, angle

    # ------------------------------------------------------------------ landmarks
    def landmarks(self, rgb, roi):
        cx, cy, size, angle = roi
        crop, M = warp_crop(rgb, (cx, cy), size, angle, 256)
        outs = self.lmk.run(None, {self.lmk.get_inputs()[0].name: crop[None]})
        raw = outs[0].reshape(-1, 3)[:478]
        score = float(_sigmoid(outs[1].reshape(-1)[0]))
        pts = np.empty_like(raw)
        pts[:, 0] = M[0, 0] * raw[:, 0] + M[0, 1] * raw[:, 1] + M[0, 2]
        pts[:, 1] = M[1, 0] * raw[:, 0] + M[1, 1] * raw[:, 1] + M[1, 2]
        pts[:, 2] = raw[:, 2] * size / 256
        return pts, score

    def blendshapes(self, lm):
        pts = lm[self.subset, :2].astype(np.float32)[None]
        return self.bsh.run(None, {self.bsh.get_inputs()[0].name: pts})[0].reshape(-1)

    def pose(self, lm):
        P = lm[:468].copy()
        P[:, 1] *= -1          # image y goes down, the canonical face's y goes up
        P[:, 2] *= -1          # landmark z grows away from the camera, the canonical z towards it
        return euler_deg(kabsch(P, self.canon))

    # ------------------------------------------------------------------ one frame
    def process(self, rgb):
        """rgb: (H, W, 3) uint8. Returns a dict (see `features`) or None when there is no face."""
        roi = self.roi
        if roi is None:
            det = self.detect(rgb)
            if det is None:
                self.last = None
                return None
            roi = self.roi_from_detection(det[0], det[1])
        lm, score = self.landmarks(rgb, roi)
        if score < 0.5:
            self.roi = None
            self.misses += 1
            if self.misses == 1:     # the tracked ROI drifted off: try a fresh detection right away
                return self.process(rgb)
            self.last = None
            return None
        self.misses = 0
        self.roi = self.roi_from_landmarks(lm)
        bs = self.blendshapes(lm)
        yaw, pitch, roll = self.pose(lm)
        out = self.features(lm, bs)
        out.update(yaw=yaw, pitch=pitch, roll=roll, score=score, landmarks=lm, blendshapes=bs,
                   roi=self.roi, frame=(rgb.shape[1], rgb.shape[0]))
        self.last = out
        return out

    @staticmethod
    def features(lm, bs):
        """Blendshapes → simple 0…1 / −1…1 values. Sides are the *subject's* (Left = image right); x values follow
        the image (+ = image right). The live driver mirrors them for the model."""
        b = lambda n: float(bs[BS[n]])
        eye_l = max(0.0, 1.0 - b("eyeBlinkLeft") * 1.15) * (1 + 0.2 * b("eyeWideLeft"))
        eye_r = max(0.0, 1.0 - b("eyeBlinkRight") * 1.15) * (1 + 0.2 * b("eyeWideRight"))
        gaze_x = (b("eyeLookOutLeft") - b("eyeLookInLeft") + b("eyeLookInRight") - b("eyeLookOutRight")) / 2
        gaze_y = (b("eyeLookUpLeft") + b("eyeLookUpRight") - b("eyeLookDownLeft") - b("eyeLookDownRight")) / 2
        brow_l = b("browInnerUp") * 0.6 + b("browOuterUpLeft") * 0.8 - b("browDownLeft")
        brow_r = b("browInnerUp") * 0.6 + b("browOuterUpRight") * 0.8 - b("browDownRight")
        mouth_open = min(1.0, b("jawOpen") * 1.4)
        smile = (b("mouthSmileLeft") + b("mouthSmileRight")) / 2
        frown = (b("mouthFrownLeft") + b("mouthFrownRight")) / 2 + b("mouthPucker") * 0.6
        mouth_form = max(-1.0, min(1.0, smile * 1.3 - frown))
        return {"eye_l": min(1.2, eye_l), "eye_r": min(1.2, eye_r),
                "smile_l": min(1.0, b("eyeSquintLeft") * 1.2 + b("cheekSquintLeft") * 0.5),
                "smile_r": min(1.0, b("eyeSquintRight") * 1.2 + b("cheekSquintRight") * 0.5),
                "gaze_x": max(-1.0, min(1.0, gaze_x * 1.6)), "gaze_y": max(-1.0, min(1.0, gaze_y * 1.6)),
                "brow_l": max(-1.0, min(1.0, brow_l)), "brow_r": max(-1.0, min(1.0, brow_r)),
                "mouth_open": mouth_open, "mouth_form": mouth_form, "cheek": min(1.0, b("cheekPuff") * 1.5)}


def to_params(f, mirror=True, head_gain=1.0, expr_gain=1.0):
    """Tracking features → Cubism-style parameter values for the model. With `mirror` the model behaves like a
    mirror of the user (turn left → it turns to the viewer's left), as VTube Studio does by default."""
    s = -1.0 if mirror else 1.0
    g, e = head_gain, expr_gain
    eye_l, eye_r = (f["eye_r"], f["eye_l"]) if mirror else (f["eye_l"], f["eye_r"])
    sm_l, sm_r = (f["smile_r"], f["smile_l"]) if mirror else (f["smile_l"], f["smile_r"])
    br_l, br_r = (f["brow_r"], f["brow_l"]) if mirror else (f["brow_l"], f["brow_r"])
    return {"ParamAngleX": s * f["yaw"] * g, "ParamAngleY": f["pitch"] * g, "ParamAngleZ": s * f["roll"] * g,
            "ParamEyeLOpen": eye_l, "ParamEyeROpen": eye_r, "ParamEyeLSmile": sm_l * e, "ParamEyeRSmile": sm_r * e,
            "ParamEyeBallX": s * f["gaze_x"], "ParamEyeBallY": f["gaze_y"],
            "ParamBrowLY": br_l * e, "ParamBrowRY": br_r * e,
            "ParamMouthOpenY": f["mouth_open"] * e, "ParamMouthForm": f["mouth_form"] * e, "ParamCheek": f["cheek"],
            "ParamBodyAngleX": s * f["yaw"] * g * 0.25, "ParamBodyAngleY": f["pitch"] * g * 0.15,
            "ParamBodyAngleZ": s * f["roll"] * g * 0.2}
