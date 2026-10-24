"""«Эфир»: the model moves by itself for streaming — follows the mouse (head, eyes, body), blinks, breathes,
opens the mouth with the microphone (lip sync) and swings its hair with physics. Emotions on number keys.
A separate borderless window (chroma key / transparent) can be captured by OBS."""
import math
import random
import time

import numpy as np
from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QCursor, QGuiApplication, QKeySequence, QPainter, QPixmap, QShortcut,
                           QTransform)
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget, QProgressBar,
                               QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget)

from .camera import CameraFeed, TrackerThread, cameras, multimedia_available
from .panels import section
from .physics import PhysicsSim
from .tracking import models_available, to_params

BACKGROUNDS = [("#00FF00", "Хромакей зелёный"), ("#0000FF", "Хромакей синий"), ("#FF00FF", "Пурпурный"),
               ("transparent", "Прозрачный"), ("theme", "Как в приложении")]


class Mic(QObject):
    """Microphone level via sounddevice (PortAudio). Fails quietly when there is no audio input."""

    def __init__(self):
        super().__init__()
        self.stream = None
        self.level = 0.0
        self.error = ""

    @staticmethod
    def devices():
        try:
            import sounddevice as sd
            return [(i, d["name"]) for i, d in enumerate(sd.query_devices()) if d.get("max_input_channels", 0) > 0]
        except Exception:
            return []

    def start(self, device=None):
        self.stop()
        try:
            import sounddevice as sd

            def cb(indata, frames, t, status):
                rms = float(np.sqrt(np.mean(np.square(indata[:, 0])))) if len(indata) else 0.0
                self.level = max(rms, self.level * 0.85)

            self.stream = sd.InputStream(device=device, channels=1, samplerate=None, blocksize=512, callback=cb)
            self.stream.start()
            self.error = ""
            return True
        except Exception as e:  # no PortAudio / permission denied / no device
            self.stream = None
            self.error = str(e)
            return False

    def stop(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
        self.stream = None
        self.level = 0.0


# how fast the live values chase the camera (per second); eyes and mouth snap, the head glides
TRACK_SPEED = {"ParamAngleX": 9.0, "ParamAngleY": 9.0, "ParamAngleZ": 9.0, "ParamBodyAngleX": 5.0,
               "ParamBodyAngleY": 5.0, "ParamBodyAngleZ": 5.0, "ParamEyeLOpen": 24.0, "ParamEyeROpen": 24.0,
               "ParamMouthOpenY": 24.0, "ParamMouthForm": 12.0, "ParamEyeBallX": 14.0, "ParamEyeBallY": 14.0,
               "ParamBrowLY": 12.0, "ParamBrowRY": 12.0, "ParamEyeLSmile": 10.0, "ParamEyeRSmile": 10.0,
               "ParamCheek": 6.0}


class CameraPreview(QLabel):
    """A small mirror of the camera with the tracked landmarks drawn over it."""

    def __init__(self, colors):
        super().__init__()
        self.c = colors
        self.setFixedSize(266, 150)
        self.setAlignment(Qt.AlignCenter)
        self.setObjectName("CameraPreview")
        self.clear_frame()

    def clear_frame(self):
        self.setText("Камера выключена")
        self.setPixmap(QPixmap())

    def show_frame(self, rgb, res, mirror):
        from .art import from_rgba
        h, w = rgb.shape[:2]
        rgba = np.dstack([rgb, np.full((h, w, 1), 255, np.uint8)])
        img = from_rgba(rgba)
        if mirror:
            img = img.mirrored(True, False)
        k = min(self.width() / w, self.height() / h)
        img = img.scaled(int(w * k), int(h * k), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        if res is not None:
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(self.c["accent"]))
            for x, y, _ in res["landmarks"][::3]:
                if mirror:
                    x = w - x
                p.drawEllipse(QPointF(x * k, y * k), 1.2, 1.2)
            p.end()
        self.setPixmap(QPixmap.fromImage(img))


class LiveDriver(QObject):
    """Computes live parameter values ~60 times per second."""
    tick = Signal()

    def __init__(self, model):
        super().__init__()
        self.model = model
        self.values = {p.id: p.default for p in model.params}
        self.physics = PhysicsSim(model)
        self.mic = Mic()
        self.follow = True
        self.blink = True
        self.breath = True
        self.use_mic = False
        self.use_physics = True
        self.idle = True
        self.own = True        # the model's own idle animation (model.meta['idle'])
        self.gain = 1.0
        self.emotion = {}
        self.emotion_t = 0.0
        self.smooth = {}
        self.next_blink = time.monotonic() + 2.5
        self.blink_t = None
        self.blinks = []          # [(eye param id, start time)] — planned single / double / triple blinks
        self.clip = None          # animation clip being played (model.meta['clips'])
        self.clip_t0 = 0.0
        self.t0 = time.monotonic()
        self.last = time.monotonic()
        self.target_rect = None   # screen rect the mouse is measured against (None → primary screen)
        # face tracking from the camera (see tracking.py): the latest features and when they arrived
        self.track = False
        self.face = None
        self.face_t = 0.0
        self.mirror = True
        self.head_gain = 1.0
        self.expr_gain = 1.0
        self.calib = (0.0, 0.0, 0.0)   # yaw / pitch / roll that count as «looking straight»
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.step)
        self._frame = None

    def set_model(self, model):
        self.model = model
        self.values = {p.id: p.default for p in model.params}
        self.physics = PhysicsSim(model)
        self._frame = None

    def start(self):
        self.last = time.monotonic()
        self.timer.start(16)

    def stop(self):
        self.timer.stop()
        self.mic.stop()

    def play_clip(self, clip):
        """Play an animation clip: {'name', 'duration', 'tracks': {param: [[t, v], …]}}."""
        self.clip = clip
        self.clip_t0 = time.monotonic()

    @staticmethod
    def track_value(track, t):
        if not track:
            return None
        if t <= track[0][0]:
            return float(track[0][1])
        for (t0, v0), (t1, v1) in zip(track, track[1:]):
            if t0 <= t <= t1:
                u = (t - t0) / (t1 - t0) if t1 > t0 else 1.0
                u = u * u * (3 - 2 * u)
                return float(v0) + (float(v1) - float(v0)) * u
        return float(track[-1][1])

    def plan_blinks(self, now):
        """Next blink burst: 1–3 blinks, each eye a little apart, settings in model.meta['blink']."""
        cfg = self.model.meta.get("blink", {}) or {}
        n = 1
        r = random.random()
        if r < cfg.get("triple", 0.0):
            n = 3
        elif r < cfg.get("triple", 0.0) + cfg.get("double", 0.12):
            n = 2
        off = cfg.get("offset", 0.0)
        eyes = ["ParamEyeLOpen", "ParamEyeROpen"]
        random.shuffle(eyes)
        for i in range(n):
            start = now + i * cfg.get("gap", 0.38)
            self.blinks.append((eyes[0], start))
            self.blinks.append((eyes[1], start + random.uniform(0.0, off)))
        lo, hi = cfg.get("interval", (2.0, 5.5))
        self.next_blink = now + (n - 1) * cfg.get("gap", 0.38) + random.uniform(lo, hi)

    def set_face(self, f):
        self.face = f
        if f is not None:
            self.face_t = time.monotonic()

    def tracked(self, now=None):
        now = time.monotonic() if now is None else now
        return self.track and self.face is not None and now - self.face_t < 0.7

    def calibrate(self):
        """The current head pose becomes the neutral one."""
        if self.face is not None:
            self.calib = (self.face["yaw"], self.face["pitch"], self.face["roll"])

    def face_params(self):
        f = dict(self.face)
        f["yaw"] -= self.calib[0]
        f["pitch"] -= self.calib[1]
        f["roll"] -= self.calib[2]
        return to_params(f, self.mirror, self.head_gain, self.expr_gain)

    def set_emotion(self, values):
        self.emotion = dict(values or {})
        self.emotion_t = time.monotonic()

    def _p(self, pid):
        return self.model.param(pid)

    def _set(self, target, pid, v, speed=10.0, dt=0.016):
        p = self._p(pid)
        if p is None:
            return
        cur = self.smooth.get(pid, self.values.get(pid, p.default))
        cur += (v - cur) * min(1.0, speed * dt)
        self.smooth[pid] = cur
        target[pid] = p.clamp(cur)

    def step(self):
        now = time.monotonic()
        dt = max(0.001, min(0.05, now - self.last))
        self.last = now
        t = now - self.t0
        m = self.model
        vals = {p.id: p.default for p in m.params}
        # emotion (pose of kind «Эмоция») is the base
        for pid, v in self.emotion.items():
            if m.param(pid) is not None:
                vals[pid] = v
        tracked = self.tracked(now)
        if tracked:
            for pid, v in self.face_params().items():
                self._set(vals, pid, v, TRACK_SPEED.get(pid, 10.0), dt)
        elif self.follow:
            cur = QCursor.pos()
            rect = self.target_rect
            if rect is None:
                scr = QGuiApplication.screenAt(cur) or QGuiApplication.primaryScreen()
                rect = scr.geometry() if scr else None
            if rect is not None and rect.width() > 0:
                nx = max(-1.0, min(1.0, (cur.x() - rect.center().x()) / (rect.width() / 2)))
                ny = max(-1.0, min(1.0, (cur.y() - rect.center().y()) / (rect.height() / 2)))
                self._set(vals, "ParamAngleX", nx * 30, 6, dt)
                self._set(vals, "ParamAngleY", -ny * 30, 6, dt)
                self._set(vals, "ParamAngleZ", -nx * ny * 10, 4, dt)
                self._set(vals, "ParamEyeBallX", nx, 14, dt)
                self._set(vals, "ParamEyeBallY", -ny, 14, dt)
                self._set(vals, "ParamBodyAngleX", nx * 10 * 0.6, 3, dt)
                self._set(vals, "ParamBodyAngleY", -ny * 10 * 0.4, 3, dt)
        if self.own:
            for loop in m.meta.get("idle", []) or []:
                p = self._p(loop.get("param"))
                if p is None:
                    continue
                w = math.sin(2 * math.pi * t / max(0.2, float(loop.get("period", 4.0))) + float(loop.get("phase", 0.0)))
                pw = float(loop.get("power", 1.0))
                if pw != 1.0:
                    w = math.copysign(abs(w) ** pw, w)
                dev = vals.get(p.id, p.default) - p.default  # mouse follow / emotion stay on top
                vals[p.id] = p.clamp(float(loop.get("center", p.default)) + float(loop.get("amp", 0.0)) * w + dev)
        if self.idle and not tracked:
            for pid, amp, f in (("ParamAngleZ", 3.0, 0.21), ("ParamBodyAngleZ", 2.0, 0.17)):
                p = self._p(pid)
                if p is not None:
                    vals[pid] = p.clamp(vals[pid] + amp * math.sin(t * f * 2 * math.pi))
        if self.breath and self._p("ParamBreath") is not None:
            vals["ParamBreath"] = 0.5 + 0.5 * math.sin(t * 2 * math.pi / 3.4)
        if self.clip is not None:
            tc = now - self.clip_t0
            if tc > float(self.clip.get("duration", 3.0)):
                self.clip = None
            else:
                for pid, track in self.clip.get("tracks", {}).items():
                    p = self._p(pid)
                    v = self.track_value(track, tc)
                    if p is not None and v is not None:
                        vals[pid] = p.clamp(v)
        if self.blink and not tracked:   # the camera sees the real blinks
            if not self.blinks and now >= self.next_blink:
                self.plan_blinks(now)
            ks = {"ParamEyeLOpen": 1.0, "ParamEyeROpen": 1.0}
            keep = []
            for pid, start in self.blinks:
                ph = (now - start) / 0.15
                if ph < 2:
                    keep.append((pid, start))
                    if ph > 0:
                        ks[pid] = min(ks[pid], abs(1 - ph))
            self.blinks = keep
            for pid, k in ks.items():
                p = self._p(pid)
                if p is not None:
                    vals[pid] = p.clamp(vals.get(pid, p.default) * k)
        if self.use_mic and self.mic.stream is not None:
            lvl = min(1.0, self.mic.level * 12.0 * self.gain)
            lvl = 0.0 if lvl < 0.06 else lvl
            self._set(vals, "ParamMouthOpenY", max(vals.get("ParamMouthOpenY", 0.0), lvl), 22, dt)
            self.mic.level *= 0.9
        if self.use_physics:
            self.physics.step(dt, vals)
        self.values = vals
        self._frame = None
        self.tick.emit()

    def frame(self):
        if self._frame is None:
            self._frame = self.model.evaluate(self.values)
        return self._frame


class LiveCanvas(QWidget):
    """Draws the live model fitted into the widget on the chosen background."""

    def __init__(self, driver, renderer, colors, parent=None):
        super().__init__(parent)
        self.driver = driver
        self.renderer = renderer
        self.c = colors
        self.bg = "#00FF00"
        self.zoom = 1.0
        self.offset = QPointF(0, 0)
        self.crop = "upper"   # "upper" (bust shot) | "full"
        driver.tick.connect(self.update)
        self._drag = None

    def view_T(self):
        m = self.driver.model
        if self.crop == "upper":
            src = QRectF(m.width * 0.12, 0, m.width * 0.76, m.height * 0.55)
        else:
            src = QRectF(0, 0, m.width, m.height)
        k = min(self.width() / src.width(), self.height() / src.height()) * self.zoom
        t = QTransform()
        t.translate(self.width() / 2 + self.offset.x(), self.height() / 2 + self.offset.y())
        t.scale(k, k)
        t.translate(-src.center().x(), -src.center().y())
        return t

    def paintEvent(self, e):
        p = QPainter(self)
        if self.bg == "transparent":
            if self.testAttribute(Qt.WA_TranslucentBackground):
                p.setCompositionMode(QPainter.CompositionMode_Source)
                p.fillRect(self.rect(), Qt.transparent)
                p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            else:
                p.fillRect(self.rect(), QColor(self.c["checker_a"]))
                col = QColor(self.c["checker_b"])
                for y in range(0, self.height(), 16):
                    for x in range((y // 16 % 2) * 16, self.width(), 32):
                        p.fillRect(x, y, 16, 16, col)
        elif self.bg == "theme":
            p.fillRect(self.rect(), QColor(self.c["canvas"]))
        else:
            p.fillRect(self.rect(), QColor(self.bg))
        self.renderer.render(p, self.driver.frame(), self.view_T(), self.rect())
        p.end()

    def wheelEvent(self, e):
        self.zoom = max(0.2, min(6.0, self.zoom * 1.0015 ** e.angleDelta().y()))
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and not (self.window().windowFlags() & Qt.FramelessWindowHint):
            self._drag = (e.position(), QPointF(self.offset))
        elif e.button() == Qt.LeftButton:
            self._drag = ("win", e.globalPosition() - QPointF(self.window().pos()))

    def mouseMoveEvent(self, e):
        if self._drag is None:
            return
        if self._drag[0] == "win":
            self.window().move((e.globalPosition() - self._drag[1]).toPoint())
        else:
            self.offset = self._drag[1] + (e.position() - self._drag[0])
            self.update()

    def mouseReleaseEvent(self, e):
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        self.zoom = 1.0
        self.offset = QPointF(0, 0)
        self.update()


class OBSWindow(QWidget):
    """Borderless window for window capture in OBS (chroma key or real transparency)."""

    def __init__(self, driver, renderer, colors, bg):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint)
        self.setWindowTitle("Мю — окно для OBS")
        self.resize(560, 720)
        if bg == "transparent":
            self.setAttribute(Qt.WA_TranslucentBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = LiveCanvas(driver, renderer, colors)
        self.view.bg = bg
        if bg == "transparent":
            self.view.setAttribute(Qt.WA_TranslucentBackground, True)
        lay.addWidget(self.view)
        QShortcut(QKeySequence(Qt.Key_Escape), self, self.close)
        self.setToolTip("Перетаскивайте окно мышью, колесо — масштаб, Esc — закрыть")


class LivePage(QWidget):
    status = Signal(str)

    def __init__(self, win, colors):
        super().__init__()
        self.win = win
        self.c = colors
        self.doc = None
        self.driver = None
        self.obs = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.host = QVBoxLayout()
        holder = QWidget()
        holder.setLayout(self.host)
        lay.addWidget(holder, 1)
        side = QWidget()
        side.setObjectName("RightPanel")
        side.setFixedWidth(290)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        sv.addWidget(scroll)
        body = QWidget()
        body.setObjectName("InspectorBody")
        v = QVBoxLayout(body)
        v.setContentsMargins(12, 10, 12, 12)
        scroll.setWidget(body)
        self.b_run = QPushButton("Запустить эфир")
        self.b_run.setObjectName("Accent")
        self.b_run.clicked.connect(self.toggle)
        v.addWidget(self.b_run)
        v.addSpacing(6)
        v.addWidget(section("Движение"))
        self.cb = {}
        for key, text in (("follow", "Следить за мышью"), ("blink", "Моргать"), ("breath", "Дышать"),
                          ("idle", "Лёгкое покачивание"), ("own", "Своя анимация модели"),
                          ("use_physics", "Физика волос и одежды")):
            cb = QCheckBox(text)
            cb.setChecked(True)
            cb.toggled.connect(lambda on, k=key: self._flag(k, on))
            self.cb[key] = cb
            v.addWidget(cb)
        v.addSpacing(6)
        v.addWidget(section("Микрофон → рот"))
        self.mic_on = QCheckBox("Липсинк с микрофона")
        self.mic_on.toggled.connect(self.toggle_mic)
        v.addWidget(self.mic_on)
        self.mic_dev = QComboBox()
        self.mic_dev.addItem("Системный по умолчанию", None)
        for i, name in Mic.devices():
            self.mic_dev.addItem(name, i)
        self.mic_dev.currentIndexChanged.connect(lambda _: self.toggle_mic(self.mic_on.isChecked()))
        v.addWidget(self.mic_dev)
        g = QHBoxLayout()
        g.addWidget(QLabel("Чувствительность"))
        self.gain = QSlider(Qt.Horizontal)
        self.gain.setRange(20, 400)
        self.gain.setValue(int(100 * float(win.settings.get("mic_gain", 1.0))))
        self.gain.valueChanged.connect(self._gain)
        g.addWidget(self.gain)
        v.addLayout(g)
        self.meter = QProgressBar()
        self.meter.setRange(0, 100)
        self.meter.setTextVisible(False)
        self.meter.setMaximumHeight(6)
        v.addWidget(self.meter)
        v.addSpacing(6)
        v.addWidget(section("Камера → лицо"))
        self.cam_on = QCheckBox("Отслеживать лицо по камере")
        self.cam_on.toggled.connect(self.toggle_camera)
        v.addWidget(self.cam_on)
        self.cam_dev = QComboBox()
        self.cam_dev.addItem("Камера по умолчанию", None)
        for i, name in cameras():
            self.cam_dev.addItem(name, i)
        self.cam_dev.currentIndexChanged.connect(lambda _: self.toggle_camera(self.cam_on.isChecked()))
        v.addWidget(self.cam_dev)
        self.preview = CameraPreview(colors)
        v.addWidget(self.preview, 0, Qt.AlignHCenter)
        self.cam_status = QLabel("Голова, глаза, брови и рот повторяют ваши — как в VTube Studio.")
        self.cam_status.setWordWrap(True)
        self.cam_status.setObjectName("Muted")
        v.addWidget(self.cam_status)
        self.mirror = QCheckBox("Зеркально (как в зеркале)")
        self.mirror.setChecked(bool(win.settings.get("track_mirror", True)))
        self.mirror.toggled.connect(self._mirror)
        v.addWidget(self.mirror)
        for key, text, lo, hi, default in (("track_head", "Чувствительность головы", 50, 250, 1.0),
                                           ("track_expr", "Выразительность", 50, 200, 1.0)):
            g = QHBoxLayout()
            g.addWidget(QLabel(text))
            sl = QSlider(Qt.Horizontal)
            sl.setRange(lo, hi)
            sl.setValue(int(100 * float(win.settings.get(key, default))))
            sl.valueChanged.connect(lambda val, k=key: self._track_gain(k, val))
            g.addWidget(sl)
            v.addLayout(g)
            setattr(self, key, sl)
        cal = QPushButton("Запомнить центр (калибровка)")
        cal.setToolTip("Посмотрите прямо в камеру и нажмите: эта поза головы станет нейтральной")
        cal.clicked.connect(self.calibrate)
        v.addWidget(cal)
        v.addSpacing(6)
        v.addWidget(section("Эмоции (клавиши 1–9)"))
        self.emotions = QListWidget()
        self.emotions.setMaximumHeight(180)
        self.emotions.itemClicked.connect(self.pick_emotion)
        v.addWidget(self.emotions)
        v.addSpacing(6)
        v.addWidget(section("Анимации (клавиши Q W E R T…)"))
        self.clips = QListWidget()
        self.clips.setMaximumHeight(160)
        self.clips.itemClicked.connect(lambda it: self.clip_key(self.clips.row(it)))
        v.addWidget(self.clips)
        v.addSpacing(6)
        v.addWidget(section("Кадр и фон"))
        self.crop = QComboBox()
        self.crop.addItem("По пояс", "upper")
        self.crop.addItem("В полный рост", "full")
        self.crop.currentIndexChanged.connect(self._crop)
        v.addWidget(self.crop)
        self.bg = QComboBox()
        for k, t in BACKGROUNDS:
            self.bg.addItem(t, k)
        self.bg.currentIndexChanged.connect(self._bg)
        v.addWidget(self.bg)
        ob = QPushButton("Открыть окно для OBS")
        ob.clicked.connect(self.open_obs)
        v.addWidget(ob)
        hint = QLabel("В OBS: «Захват окна» → «Мю — окно для OBS», затем фильтр «Хромакей» "
                      "(или прозрачный фон на macOS 12+).")
        hint.setWordWrap(True)
        hint.setObjectName("Muted")
        v.addWidget(hint)
        v.addStretch(1)
        lay.addWidget(side)
        self.canvas = None
        self.feed = None
        self.tracker = None
        self.last_rgb = None
        self.fps_t = time.monotonic()
        self.fps_n = 0
        self.meter_timer = QTimer(self)
        self.meter_timer.timeout.connect(self._meter)
        for i in range(9):
            QShortcut(QKeySequence(str(i + 1)), self, lambda i=i: self.emotion_key(i))
        QShortcut(QKeySequence("0"), self, lambda: self.emotion_key(-1))
        for i, key in enumerate("QWERTYUIOP"):
            QShortcut(QKeySequence(key), self, lambda i=i: self.clip_key(i))

    def set_doc(self, doc):
        self.doc = doc
        if self.driver is None:
            self.driver = LiveDriver(doc.model)
            self.canvas = LiveCanvas(self.driver, doc.renderer, self.c)
            self.host.addWidget(self.canvas)
        else:
            self.driver.set_model(doc.model)
            self.canvas.renderer = doc.renderer
        self.canvas.bg = self.bg.currentData()
        self.driver.mirror = self.mirror.isChecked()
        self.driver.head_gain = self.track_head.value() / 100
        self.driver.expr_gain = self.track_expr.value() / 100
        self.fill_emotions()
        self.fill_clips()
        self.driver.step()

    def fill_emotions(self):
        self.emotions.clear()
        self.emotions.addItem("0 · Без эмоции")
        from .poses import add_default_poses
        add_default_poses(self.doc.model)
        self._emos = [p for p in self.doc.model.poses if p.get("kind") == "Эмоция"]
        for i, p in enumerate(self._emos):
            self.emotions.addItem(f"{i + 1} · {p['name']}" if i < 9 else p["name"])

    def fill_clips(self):
        self.clips.clear()
        self._clips = list(self.doc.model.meta.get("clips", []) or [])
        for i, c in enumerate(self._clips):
            key = "QWERTYUIOP"[i] if i < 10 else ""
            self.clips.addItem(f"{key} · {c.get('name', 'Анимация')}" if key else c.get("name", "Анимация"))
        if not self._clips:
            self.clips.addItem("У модели нет анимаций")

    def clip_key(self, i):
        if self.driver is None or not (0 <= i < len(getattr(self, "_clips", []))):
            return
        if not self.driver.timer.isActive():
            self.toggle()
        self.driver.play_clip(self._clips[i])
        self.clips.setCurrentRow(i)

    def pick_emotion(self, it):
        row = self.emotions.row(it)
        self.emotion_key(row - 1)

    def emotion_key(self, i):
        if self.driver is None:
            return
        if 0 <= i < len(getattr(self, "_emos", [])):
            self.driver.set_emotion(self._emos[i].get("values", {}))
            self.emotions.setCurrentRow(i + 1)
        else:
            self.driver.set_emotion({})
            self.emotions.setCurrentRow(0)

    # ------------------------------------------------------------------ camera → face
    def toggle_camera(self, on):
        if self.driver is None:
            return
        if not on:
            if self.feed is not None:
                self.feed.stop()
            self.driver.track = False
            self.driver.set_face(None)
            self.preview.clear_frame()
            return
        if not models_available():
            return self._camera_failed("Модели трекинга не найдены (assets/face) или нет onnxruntime")
        if not multimedia_available():
            return self._camera_failed("Qt Multimedia не установлен (PySide6-Addons) — камера недоступна")
        if self.tracker is None:
            self.tracker = TrackerThread()
            self.tracker.result.connect(self._tracked)
            self.tracker.failed.connect(self._camera_failed)
        if self.feed is None:
            self.feed = CameraFeed()
            self.feed.frame.connect(self._frame)
            self.feed.error.connect(self._camera_failed)
        if not self.feed.start(self.cam_dev.currentData()):
            return
        self.driver.track = True
        self.driver.mirror = self.mirror.isChecked()
        self.cam_status.setText("Камера включена, ищу лицо…")
        self.fps_t, self.fps_n = time.monotonic(), 0
        if not self.driver.timer.isActive():
            self.toggle()

    def _camera_failed(self, msg):
        self.status.emit("Камера: " + msg)
        self.cam_status.setText(msg)
        if self.feed is not None:
            self.feed.stop()
        if self.driver is not None:
            self.driver.track = False
        self.cam_on.blockSignals(True)
        self.cam_on.setChecked(False)
        self.cam_on.blockSignals(False)

    def _frame(self, rgb):
        self.last_rgb = rgb
        if self.tracker is not None:
            self.tracker.push(rgb)

    def _tracked(self, res):
        if self.driver is None:
            return
        self.driver.set_face(res)
        self.fps_n += 1
        now = time.monotonic()
        if now - self.fps_t >= 1.0:
            fps = self.fps_n / (now - self.fps_t)
            self.fps_t, self.fps_n = now, 0
            self.cam_status.setText((f"Лицо найдено · {fps:.0f} к/с" if res is not None else "Лицо не найдено"))
        if self.last_rgb is not None:
            self.preview.show_frame(self.last_rgb, res, self.mirror.isChecked())

    def _mirror(self, on):
        if self.driver is not None:
            self.driver.mirror = on
        self.win.settings["track_mirror"] = on

    def _track_gain(self, key, val):
        self.win.settings[key] = val / 100
        if self.driver is not None:
            setattr(self.driver, "head_gain" if key == "track_head" else "expr_gain", val / 100)

    def calibrate(self):
        if self.driver is not None:
            self.driver.calibrate()
            self.status.emit("Центр запомнен")

    def _flag(self, key, on):
        if self.driver is not None:
            setattr(self.driver, key, on)

    def _gain(self, v):
        if self.driver is not None:
            self.driver.gain = v / 100
        self.win.settings["mic_gain"] = v / 100

    def _crop(self, _):
        if self.canvas is not None:
            self.canvas.crop = self.crop.currentData()
            self.canvas.update()
        if self.obs is not None:
            self.obs.view.crop = self.crop.currentData()

    def _bg(self, _):
        if self.canvas is not None:
            self.canvas.bg = self.bg.currentData()
            self.canvas.update()

    def toggle(self):
        if self.driver is None:
            return
        if self.driver.timer.isActive():
            self.stop()
        else:
            self.driver.start()
            self.meter_timer.start(50)
            self.b_run.setText("Остановить эфир")

    def stop(self):
        if self.driver is not None:
            self.driver.stop()
        self.meter_timer.stop()
        self.mic_on.setChecked(False)
        self.cam_on.setChecked(False)
        self.b_run.setText("Запустить эфир")

    def toggle_mic(self, on):
        if self.driver is None:
            return
        self.driver.use_mic = on
        if on:
            ok = self.driver.mic.start(self.mic_dev.currentData())
            if not ok:
                self.status.emit("Микрофон недоступен: " + (self.driver.mic.error or "нет устройства")[:120])
                self.mic_on.blockSignals(True)
                self.mic_on.setChecked(False)
                self.mic_on.blockSignals(False)
                self.driver.use_mic = False
            elif not self.driver.timer.isActive():
                self.toggle()
        else:
            self.driver.mic.stop()

    def _meter(self):
        if self.driver is not None:
            self.meter.setValue(int(min(1.0, self.driver.mic.level * 12 * self.driver.gain) * 100))

    def open_obs(self):
        if self.driver is None:
            return
        if self.obs is not None:
            self.obs.close()
        self.obs = OBSWindow(self.driver, self.doc.renderer, self.c, self.bg.currentData())
        self.obs.view.crop = self.crop.currentData()
        self.obs.show()
        if not self.driver.timer.isActive():
            self.toggle()

    def shutdown(self):
        self.stop()
        if self.tracker is not None:
            self.tracker.shutdown()
            self.tracker = None
        if self.obs is not None:
            self.obs.close()
            self.obs = None
