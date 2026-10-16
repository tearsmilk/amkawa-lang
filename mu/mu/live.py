"""«Эфир»: the model moves by itself for streaming — follows the mouse (head, eyes, body), blinks, breathes,
opens the mouth with the microphone (lip sync) and swings its hair with physics. Emotions on number keys.
A separate borderless window (chroma key / transparent) can be captured by OBS."""
import math
import random
import time

import numpy as np
from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QKeySequence, QPainter, QShortcut, QTransform
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget, QProgressBar,
                               QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget)

from .panels import section
from .physics import PhysicsSim

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
        self.gain = 1.0
        self.emotion = {}
        self.emotion_t = 0.0
        self.smooth = {}
        self.next_blink = time.monotonic() + 2.5
        self.blink_t = None
        self.t0 = time.monotonic()
        self.last = time.monotonic()
        self.target_rect = None   # screen rect the mouse is measured against (None → primary screen)
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
        if self.follow:
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
        if self.idle:
            for pid, amp, f in (("ParamAngleZ", 3.0, 0.21), ("ParamBodyAngleZ", 2.0, 0.17)):
                p = self._p(pid)
                if p is not None:
                    vals[pid] = p.clamp(vals[pid] + amp * math.sin(t * f * 2 * math.pi))
        if self.breath and self._p("ParamBreath") is not None:
            vals["ParamBreath"] = 0.5 + 0.5 * math.sin(t * 2 * math.pi / 3.4)
        if self.blink:
            if self.blink_t is None and now >= self.next_blink:
                self.blink_t = now
            k = 1.0
            if self.blink_t is not None:
                ph = (now - self.blink_t) / 0.16
                if ph >= 2:
                    self.blink_t = None
                    self.next_blink = now + random.uniform(2.0, 5.5) * (0.4 if random.random() < 0.15 else 1)
                else:
                    k = abs(1 - ph)
            for pid in ("ParamEyeLOpen", "ParamEyeROpen"):
                p = self._p(pid)
                if p is not None:
                    base = self.emotion.get(pid, p.default)
                    vals[pid] = p.clamp(base * k)
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
                          ("idle", "Лёгкое покачивание"), ("use_physics", "Физика волос и одежды")):
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
        v.addWidget(section("Эмоции (клавиши 1–9)"))
        self.emotions = QListWidget()
        self.emotions.setMaximumHeight(180)
        self.emotions.itemClicked.connect(self.pick_emotion)
        v.addWidget(self.emotions)
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
        self.meter_timer = QTimer(self)
        self.meter_timer.timeout.connect(self._meter)
        for i in range(9):
            QShortcut(QKeySequence(str(i + 1)), self, lambda i=i: self.emotion_key(i))
        QShortcut(QKeySequence("0"), self, lambda: self.emotion_key(-1))

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
        self.fill_emotions()
        self.driver.step()

    def fill_emotions(self):
        self.emotions.clear()
        self.emotions.addItem("0 · Без эмоции")
        from .poses import add_default_poses
        add_default_poses(self.doc.model)
        self._emos = [p for p in self.doc.model.poses if p.get("kind") == "Эмоция"]
        for i, p in enumerate(self._emos):
            self.emotions.addItem(f"{i + 1} · {p['name']}" if i < 9 else p["name"])

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
        if self.obs is not None:
            self.obs.close()
            self.obs = None
