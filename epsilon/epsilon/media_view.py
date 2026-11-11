"""Attachment viewer: photos (zoom), animated GIFs, video and audio (QtMultimedia), other files.

← / → walk through the attachments of the note, Esc closes, Space plays / pauses.
"""
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QImageReader, QKeySequence, QMovie, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QSlider, QStackedWidget,
    QVBoxLayout, QWidget,
)

from . import attachments as att

try:  # video / audio playback; the app still works (opens files externally) without it
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget
    HAVE_MEDIA = True
except Exception:  # pragma: no cover - depends on the PySide6 build
    HAVE_MEDIA = False


def open_external(path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def quick_look(path):
    if sys.platform == "darwin":
        subprocess.Popen(["qlmanage", "-p", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        open_external(path)


def fmt_time(ms):
    s = max(0, int(ms // 1000))
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


class ImageView(QScrollArea):
    """Fits the picture to the window; Ctrl/⌘ + wheel, +/− buttons zoom."""

    def __init__(self):
        super().__init__()
        self.setObjectName("MediaStage")
        self.setAlignment(Qt.AlignCenter)
        self.setWidgetResizable(False)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.setWidget(self.label)
        self.pixmap = QPixmap()
        self.movie = None
        self.zoom = None  # None = fit

    def show_file(self, path):
        self.stop()
        self.zoom = None
        if att.kind_of(path) == "gif":
            self.movie = QMovie(str(path))
            self.movie.setCacheMode(QMovie.CacheAll)
            self.movie.frameChanged.connect(self._frame)
            self.movie.start()
            self.pixmap = self.movie.currentPixmap()
        else:
            reader = QImageReader(str(path))
            reader.setAutoTransform(True)  # EXIF rotation of phone photos
            self.pixmap = QPixmap.fromImage(reader.read())
        self._apply()
        return not self.pixmap.isNull()

    def stop(self):
        if self.movie is not None:
            self.movie.stop()
            self.movie.deleteLater()
            self.movie = None

    def toggle(self):
        if self.movie is not None:
            self.movie.setPaused(self.movie.state() == QMovie.Running)

    def _frame(self, _n):
        self.pixmap = self.movie.currentPixmap()
        self._apply()

    def scale(self):
        if self.pixmap.isNull():
            return 1.0
        if self.zoom is not None:
            return self.zoom
        vp = self.viewport().size()
        return min(1.0, (vp.width() - 24) / self.pixmap.width(), (vp.height() - 24) / self.pixmap.height())

    def set_zoom(self, factor):
        self.zoom = None if factor is None else max(0.05, min(8.0, factor))
        self._apply()

    def _apply(self):
        if self.pixmap.isNull():
            self.label.clear()
            return
        k = self.scale()
        size = QSize(max(1, int(self.pixmap.width() * k)), max(1, int(self.pixmap.height() * k)))
        dpr = self.devicePixelRatioF()
        shown = self.pixmap if k == 1.0 else self.pixmap.scaled(size * dpr, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if k != 1.0:
            shown.setDevicePixelRatio(dpr)
        self.label.setPixmap(shown)
        self.label.resize(size)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.zoom is None:
            self._apply()

    def wheelEvent(self, e):
        if e.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            self.set_zoom(self.scale() * (1.15 if e.angleDelta().y() > 0 else 1 / 1.15))
            return
        super().wheelEvent(e)


class PlayerView(QWidget):
    """Video / audio with play-pause, a seek bar, time and volume."""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.video = QVideoWidget()
        self.video.setObjectName("MediaStage")
        self.video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.cover = QLabel("🎵")
        self.cover.setObjectName("MediaCover")
        self.cover.setAlignment(Qt.AlignCenter)
        self.stage = QStackedWidget()
        self.stage.addWidget(self.video)
        self.stage.addWidget(self.cover)
        lay.addWidget(self.stage, 1)
        bar = QHBoxLayout()
        self.play = QPushButton("▶")
        self.play.setObjectName("PlayButton")
        self.play.setFixedSize(38, 38)
        self.play.clicked.connect(self.toggle)
        self.seek = QSlider(Qt.Horizontal)
        self.seek.sliderMoved.connect(lambda v: self.player.setPosition(v))
        self.time = QLabel("0:00 / 0:00")
        self.time.setObjectName("Muted")
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(80)
        self.volume.setFixedWidth(90)
        self.volume.valueChanged.connect(lambda v: self.audio.setVolume(v / 100))
        bar.addWidget(self.play)
        bar.addWidget(self.seek, 1)
        bar.addWidget(self.time)
        bar.addWidget(QLabel("🔈"))
        bar.addWidget(self.volume)
        lay.addLayout(bar)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.8)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.durationChanged.connect(self._duration)
        self.player.positionChanged.connect(self._position)
        self.player.playbackStateChanged.connect(self._state)
        self.player.errorOccurred.connect(lambda *_: self.failed and self.failed(self.player.errorString()))
        self.failed = None

    def show_file(self, path):
        self.player.stop()
        self.stage.setCurrentWidget(self.video if att.kind_of(path) == "video" else self.cover)
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()

    def stop(self):
        self.player.stop()
        self.player.setSource(QUrl())

    def toggle(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _duration(self, ms):
        self.seek.setRange(0, ms)
        self._position(self.player.position())

    def _position(self, ms):
        if not self.seek.isSliderDown():
            self.seek.setValue(ms)
        self.time.setText(f"{fmt_time(ms)} / {fmt_time(self.player.duration())}")

    def _state(self, state):
        self.play.setText("❚❚" if state == QMediaPlayer.PlayingState else "▶")


class FileView(QWidget):
    """Files the app does not show itself: big icon, info, open / Quick Look."""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addStretch(1)
        self.icon = QLabel()
        self.icon.setObjectName("MediaCover")
        self.icon.setAlignment(Qt.AlignCenter)
        self.info = QLabel()
        self.info.setObjectName("Muted")
        self.info.setAlignment(Qt.AlignCenter)
        self.info.setWordWrap(True)
        lay.addWidget(self.icon)
        lay.addWidget(self.info)
        row = QHBoxLayout()
        row.addStretch(1)
        self.open_btn = QPushButton("Открыть")
        self.open_btn.setObjectName("Accent")
        self.look_btn = QPushButton("Быстрый просмотр")
        row.addWidget(self.open_btn)
        row.addWidget(self.look_btn)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
        self.path = None
        self.open_btn.clicked.connect(lambda: self.path and open_external(self.path))
        self.look_btn.clicked.connect(lambda: self.path and quick_look(self.path))

    def show_file(self, path, thumb=None, note=""):
        self.path = Path(path)
        pix = QPixmap(str(thumb)) if thumb else QPixmap()
        if not pix.isNull():
            dpr = self.devicePixelRatioF()
            pix = pix.scaled(QSize(300, 300) * dpr, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pix.setDevicePixelRatio(dpr)
            self.icon.setPixmap(pix)
        else:
            self.icon.setText(att.icon_of(path))
        self.info.setText((note + "\n\n" if note else "") + att.describe(path))


class MediaViewer(QDialog):
    def __init__(self, parent, items, index=0, thumbs=None, reveal=None):
        super().__init__(parent)
        self.setObjectName("MediaViewer")
        self.setWindowTitle("Вложение")
        self.resize(980, 680)
        self.items = [Path(p) for p in items] or []
        self.index = index
        self.thumbs = thumbs
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 18)
        lay.setSpacing(12)

        head = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(2)
        self.name = QLabel()
        self.name.setObjectName("CardTitle")
        self.meta = QLabel()
        self.meta.setObjectName("Muted")
        col.addWidget(self.name)
        col.addWidget(self.meta)
        head.addLayout(col, 1)
        self.zoom_box = QFrame()
        self.zoom_box.setObjectName("Segment")
        zl = QHBoxLayout(self.zoom_box)
        zl.setContentsMargins(0, 0, 0, 0)
        zl.setSpacing(0)
        for text, fn in (("−", lambda: self.image.set_zoom(self.image.scale() / 1.25)),
                         ("Вписать", lambda: self.image.set_zoom(None)), ("100%", lambda: self.image.set_zoom(1.0)),
                         ("+", lambda: self.image.set_zoom(self.image.scale() * 1.25))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            zl.addWidget(b)
        head.addWidget(self.zoom_box)
        self.prev_btn = QPushButton("‹")
        self.next_btn = QPushButton("›")
        for b, step in ((self.prev_btn, -1), (self.next_btn, 1)):
            b.setObjectName("Link")
            b.setToolTip("Предыдущее" if step < 0 else "Следующее")
            b.clicked.connect(lambda _=False, s=step: self.go(s))
            head.addWidget(b)
        ext = QPushButton("Открыть в программе")
        ext.clicked.connect(lambda: open_external(self.path))
        head.addWidget(ext)
        finder = QPushButton("Показать в Finder")
        finder.setObjectName("Link")
        finder.clicked.connect(lambda: (reveal or open_external)(self.path))
        head.addWidget(finder)
        lay.addLayout(head)

        self.stack = QStackedWidget()
        self.image = ImageView()
        self.file = FileView()
        self.stack.addWidget(self.image)
        self.stack.addWidget(self.file)
        self.player = None
        if HAVE_MEDIA:
            self.player = PlayerView()
            self.player.failed = self._media_failed
            self.stack.addWidget(self.player)
        lay.addWidget(self.stack, 1)

        QShortcut(QKeySequence(Qt.Key_Left), self, activated=lambda: self.go(-1))
        QShortcut(QKeySequence(Qt.Key_Right), self, activated=lambda: self.go(1))
        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self._toggle)
        self.show_current()

    @property
    def path(self):
        return self.items[self.index]

    def go(self, step):
        if len(self.items) > 1:
            self.index = (self.index + step) % len(self.items)
            self.show_current()

    def _toggle(self):
        if self.stack.currentWidget() is self.player:
            self.player.toggle()
        elif self.stack.currentWidget() is self.image:
            self.image.toggle()

    def _stop_all(self):
        self.image.stop()
        if self.player is not None:
            self.player.stop()

    def show_current(self):
        self._stop_all()
        path = self.path
        kind = att.kind_of(path)
        self.name.setText(path.name)
        self.meta.setText(att.describe(path) + (f"   ·   {self.index + 1} из {len(self.items)}" if len(self.items) > 1 else ""))
        self.setWindowTitle(path.name)
        for b in (self.prev_btn, self.next_btn):
            b.setVisible(len(self.items) > 1)
        self.zoom_box.setVisible(kind in ("image", "gif"))
        if not path.exists():
            self._show_file("Файл не найден — возможно, он перемещён или удалён")
        elif kind in ("image", "gif") and self.image.show_file(path):
            self.stack.setCurrentWidget(self.image)
        elif kind in ("video", "audio") and self.player is not None:
            self.stack.setCurrentWidget(self.player)
            self.player.show_file(path)
        else:
            self._show_file()

    def _show_file(self, note=""):
        thumb = self.thumbs.cached(self.path) if self.thumbs and self.path.exists() else None
        self.file.show_file(self.path, thumb, note)
        self.stack.setCurrentWidget(self.file)

    def _media_failed(self, message):
        QTimer.singleShot(0, lambda: self._show_file(f"Не удалось воспроизвести: {message or 'формат не поддерживается'}"))

    def done(self, result):
        self._stop_all()
        super().done(result)
