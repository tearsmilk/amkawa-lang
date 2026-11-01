"""The web camera for «Эфир» (Qt Multimedia) and the worker thread that runs the face tracker on its frames.

`CameraFeed` turns QVideoFrames into small RGB numpy arrays; `TrackerThread` owns a `FaceTracker` and processes
one frame at a time (frames that arrive while it is busy are dropped, so the camera never queues up a lag)."""
import time

import numpy as np
from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QImage

MAX_WIDTH = 640   # frames are shrunk to this before tracking (plenty for the 128 / 256 px models)


def multimedia_available():
    import importlib.util
    try:
        return importlib.util.find_spec("PySide6.QtMultimedia") is not None
    except Exception:
        return False


def cameras():
    """[(index, description)] of the video inputs."""
    try:
        from PySide6.QtMultimedia import QMediaDevices
        return [(i, d.description()) for i, d in enumerate(QMediaDevices.videoInputs())]
    except Exception:
        return []


def qimage_to_rgb(img):
    """QImage → (H, W, 3) uint8, shrunk to MAX_WIDTH."""
    if img.width() > MAX_WIDTH:
        img = img.scaledToWidth(MAX_WIDTH, Qt.FastTransformation)
    img = img.convertToFormat(QImage.Format_RGB888)
    h, w = img.height(), img.width()
    buf = np.frombuffer(img.constBits(), dtype=np.uint8, count=img.bytesPerLine() * h)
    return buf.reshape(h, img.bytesPerLine())[:, :w * 3].reshape(h, w, 3).copy()


class CameraFeed(QObject):
    """Starts a camera and emits its frames as RGB arrays (at most ~30 per second)."""
    frame = Signal(object)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self.camera = None
        self.session = None
        self.sink = None
        self.last_t = 0.0
        self.frames = 0

    def start(self, index=None):
        self.stop()
        try:
            from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices, QVideoSink
        except Exception:
            self.error.emit("Qt Multimedia не установлен (PySide6-Addons) — камера недоступна")
            return False
        devices = QMediaDevices.videoInputs()
        if not devices:
            self.error.emit("Камера не найдена")
            return False
        dev = devices[index] if index is not None and 0 <= index < len(devices) else QMediaDevices.defaultVideoInput()
        self.camera = QCamera(dev)
        # a modest resolution is faster to capture and convert; the tracker shrinks frames anyway
        fmts = [f for f in dev.videoFormats() if 320 <= f.resolution().width() <= 1280]
        if fmts:
            fmts.sort(key=lambda f: (abs(f.resolution().width() - 640), -f.maxFrameRate()))
            self.camera.setCameraFormat(fmts[0])
        self.session = QMediaCaptureSession()
        self.sink = QVideoSink()
        self.session.setCamera(self.camera)
        self.session.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self._on_frame)
        self.camera.errorOccurred.connect(lambda err, msg: self.error.emit(msg or "Ошибка камеры"))
        self.camera.start()
        return True

    def _on_frame(self, vf):
        now = time.monotonic()
        if now - self.last_t < 1 / 30:
            return
        self.last_t = now
        img = vf.toImage()
        if img.isNull():
            return
        self.frames += 1
        self.frame.emit(qimage_to_rgb(img))

    def stop(self):
        if self.camera is not None:
            try:
                self.camera.stop()
            except Exception:
                pass
        self.camera = self.session = self.sink = None

    def active(self):
        return self.camera is not None


class TrackerWorker(QObject):
    result = Signal(object)   # dict from FaceTracker.process (or None when no face)
    failed = Signal(str)

    def __init__(self, model_dir=None):
        super().__init__()
        self.tracker = None
        self.model_dir = model_dir
        self.busy = False

    @Slot(object)
    def process(self, rgb):
        if self.busy:
            return
        self.busy = True
        try:
            if self.tracker is None:
                from .tracking import FaceTracker
                self.tracker = FaceTracker(self.model_dir)
            self.result.emit(self.tracker.process(rgb))
        except Exception as e:  # a missing model / onnxruntime — reported once, tracking stays off
            self.failed.emit(str(e)[:160])
        finally:
            self.busy = False


class TrackerThread(QObject):
    """Owns the worker thread; `push(rgb)` is called from the GUI thread, `result` arrives back on it."""
    result = Signal(object)
    failed = Signal(str)
    _go = Signal(object)

    def __init__(self, model_dir=None):
        super().__init__()
        self.thread = QThread()
        self.worker = TrackerWorker(model_dir)
        self.worker.moveToThread(self.thread)
        self._go.connect(self.worker.process, Qt.QueuedConnection)
        self.worker.result.connect(self.result)
        self.worker.failed.connect(self.failed)
        self.thread.start()

    def push(self, rgb):
        if not self.worker.busy:
            self._go.emit(rgb)

    def shutdown(self):
        self.thread.quit()
        self.thread.wait(2000)
