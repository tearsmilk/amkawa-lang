"""Prototype player and slide show: renders frames / slides fitted to the window, follows prototype links with
transitions (dissolve, slide, push), keyboard navigation; presenter view with notes, next slide and a timer."""
import time

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPixmap
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from . import text as textlib
from .model import world_bounds, world_transform
from .render import render_image


class Player(QWidget):
    changed = Signal(int)
    closed = Signal()

    def __init__(self, editor, frames, start=0, slides=False):
        super().__init__(None, Qt.Window)
        self.ed = editor
        self.frames = frames
        self.slides = slides
        self.cur = max(0, min(start, len(frames) - 1))
        self.history = []
        self.prev_pix = None
        self.t = 1.0
        self.transition = "none"
        self.show_notes = False
        self.cache = {}
        self.setWindowTitle(("Показ слайдов — " if slides else "Прототип — ") + editor.title())
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.resize(1280, 800)
        self.anim = QVariantAnimation(self, duration=320, startValue=0.0, endValue=1.0)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.valueChanged.connect(self._tick)
        self.hint_timer = QTimer(self, singleShot=True, interval=2500, timeout=self.update)
        self.hint_until = time.time() + 2.5
        self.hint_timer.start()

    # ------------------------------------------------------------------ rendering
    def frame_rect(self, i):
        f = self.frames[i]
        b = world_bounds(f)
        W, H = self.width(), self.height()
        k = min(W / max(1.0, b.width()), H / max(1.0, b.height()))
        if not self.slides:
            k = min(k, 1.0 if b.width() > 500 else 2.0)
        w, h = b.width() * k, b.height() * k
        return QRectF((W - w) / 2, (H - h) / 2, w, h), k, b

    def pixmap(self, i):
        r, k, b = self.frame_rect(i)
        dpr = self.devicePixelRatioF()
        key = (i, int(r.width()), int(r.height()), dpr)
        pix = self.cache.get(key)
        if pix is None:
            img = render_image(self.ed.renderer, [self.frames[i]], k * dpr, None, b)
            pix = QPixmap.fromImage(img)
            pix.setDevicePixelRatio(dpr)
            if len(self.cache) > 24:
                self.cache.clear()
            self.cache[key] = pix
        return pix, r

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#141413"))
        if not self.frames:
            return
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        pix, r = self.pixmap(self.cur)
        t = self.t
        W = self.width()
        if self.prev_pix is not None and t < 1.0:
            old, orect = self.prev_pix
            tr = self.transition
            if tr == "dissolve":
                p.drawPixmap(orect.topLeft(), old)
                p.setOpacity(t)
                p.drawPixmap(r.topLeft(), pix)
                p.setOpacity(1.0)
            elif tr in ("slide_left", "push", "slide_right"):
                sign = -1 if tr in ("slide_left", "push") else 1
                if tr == "push" or tr == "slide_left" or tr == "slide_right":
                    p.drawPixmap(orect.topLeft() + QPointF(sign * W * t, 0), old)
                p.drawPixmap(r.topLeft() + QPointF(-sign * W * (1 - t), 0), pix)
            else:
                p.drawPixmap(r.topLeft(), pix)
        else:
            p.drawPixmap(r.topLeft(), pix)
        if self.show_notes and self.slides:
            notes = self.frames[self.cur].notes or "Заметок нет"
            f = QFont(textlib.DEFAULT_FONT)
            f.setPixelSize(18)
            p.setFont(f)
            box = QRectF(40, self.height() - 200, self.width() - 80, 160)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(20, 20, 19, 220))
            p.drawRoundedRect(box, 12, 12)
            p.setPen(QColor("#F4F2EC"))
            p.drawText(box.adjusted(20, 14, -20, -14), Qt.TextWordWrap, notes)
        if time.time() < self.hint_until:
            f = QFont(textlib.DEFAULT_FONT)
            f.setPixelSize(13)
            p.setFont(f)
            hint = ("← → — листать · N — заметки · Esc — выход" if self.slides
                    else "Щёлкайте по элементам со ссылками · ← → — между фреймами · Esc — выход")
            w = p.fontMetrics().horizontalAdvance(hint) + 28
            box = QRectF((self.width() - w) / 2, self.height() - 52, w, 32)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(20, 20, 19, 200))
            p.drawRoundedRect(box, 16, 16)
            p.setPen(QColor("#F4F2EC"))
            p.drawText(box, Qt.AlignCenter, hint)
        f = QFont(textlib.DEFAULT_FONT)
        f.setPixelSize(12)
        p.setFont(f)
        p.setPen(QColor(255, 255, 255, 90))
        p.drawText(QRectF(0, self.height() - 26, self.width() - 16, 20), Qt.AlignRight,
                   f"{self.cur + 1} / {len(self.frames)}")

    def _tick(self, v):
        self.t = float(v)
        self.update()

    # ------------------------------------------------------------------ navigation
    def go(self, i, transition="none", remember=True):
        if not self.frames or i == self.cur or not (0 <= i < len(self.frames)):
            return
        if remember:
            self.history.append(self.cur)
        self.prev_pix = self.pixmap(self.cur)
        self.cur = i
        self.transition = transition or "none"
        if self.transition == "none":
            self.t = 1.0
            self.update()
        else:
            self.anim.stop()
            self.t = 0.0
            self.anim.start()
        self.changed.emit(i)

    def step(self, d):
        i = self.cur + d
        if 0 <= i < len(self.frames):
            tr = self.frames[i].transition if self.slides and d > 0 else (
                self.frames[self.cur].transition if self.slides else "none")
            if self.slides and d < 0 and tr in ("slide_left", "push"):
                tr = "slide_right"
            self.go(i, tr)

    def back(self):
        if self.history:
            self.go(self.history.pop(), "dissolve", remember=False)

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key_Escape:
            self.close()
        elif k in (Qt.Key_Right, Qt.Key_Down, Qt.Key_Space, Qt.Key_PageDown, Qt.Key_Return, Qt.Key_Enter):
            self.step(1)
        elif k in (Qt.Key_Left, Qt.Key_Up, Qt.Key_PageUp, Qt.Key_Backspace):
            self.step(-1)
        elif k == Qt.Key_Home:
            self.go(0)
        elif k == Qt.Key_End:
            self.go(len(self.frames) - 1)
        elif k == Qt.Key_N:
            self.show_notes = not self.show_notes
            self.update()
        elif k == Qt.Key_F:
            self.setWindowState(self.windowState() ^ Qt.WindowFullScreen)
        else:
            super().keyPressEvent(e)

    def link_at(self, pos):
        if not self.frames:
            return None
        r, k, b = self.frame_rect(self.cur)
        if not r.contains(pos):
            return None
        w = QPointF(b.x() + (pos.x() - r.x()) / k, b.y() + (pos.y() - r.y()) / k)
        frame = self.frames[self.cur]
        found = None

        def visit(n):
            nonlocal found
            if not n.visible:
                return
            if n.link and n.link.get("target") and n.type != "connector":
                inv, ok = world_transform(n).inverted()
                if ok and QRectF(0, 0, n.w, n.h).contains(inv.map(w)):
                    found = n
            for c in n.children:
                visit(c)
        for c in frame.children:
            visit(c)
        return found

    def mouseMoveEvent(self, e):
        if not self.slides:
            self.setCursor(Qt.PointingHandCursor if self.link_at(e.position()) is not None else Qt.ArrowCursor)

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            if e.button() == Qt.RightButton and self.slides:
                self.step(-1)
            return
        if self.slides:
            self.step(1)
            return
        n = self.link_at(e.position())
        if n is None:
            self.hint_until = time.time() + 2.5
            self.hint_timer.start()
            self.update()
            return
        target = n.link.get("target")
        if target == "__back":
            self.back()
            return
        for i, f in enumerate(self.frames):
            if f.id == target:
                self.go(i, n.link.get("transition", "dissolve"))
                return

    def resizeEvent(self, e):
        self.cache.clear()
        super().resizeEvent(e)

    def closeEvent(self, e):
        self.closed.emit()
        super().closeEvent(e)


class Presenter(QWidget):
    """Presenter view: current slide, next slide, speaker notes, timer; drives the audience window."""

    def __init__(self, editor, player):
        super().__init__(None, Qt.Window)
        self.ed = editor
        self.player = player
        self.setWindowTitle("Режим докладчика — " + editor.title())
        self.setObjectName("Main")
        self.resize(1200, 760)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        top = QHBoxLayout()
        self.timer_lbl = QLabel("00:00")
        self.timer_lbl.setObjectName("Title")
        top.addWidget(self.timer_lbl)
        reset = QPushButton("Сбросить таймер")
        reset.clicked.connect(self.reset_timer)
        top.addWidget(reset)
        top.addStretch(1)
        self.count = QLabel()
        self.count.setObjectName("Muted")
        top.addWidget(self.count)
        prev = QPushButton("◀")
        prev.clicked.connect(lambda: player.step(-1))
        nxt = QPushButton("▶")
        nxt.setObjectName("Accent")
        nxt.clicked.connect(lambda: player.step(1))
        end = QPushButton("Завершить")
        end.clicked.connect(self.close)
        for b in (prev, nxt, end):
            top.addWidget(b)
        lay.addLayout(top)
        mid = QHBoxLayout()
        self.current = QLabel()
        self.current.setAlignment(Qt.AlignCenter)
        self.current.setMinimumSize(480, 270)
        mid.addWidget(self.current, 3)
        right = QVBoxLayout()
        lbl = QLabel("ДАЛЕЕ")
        lbl.setObjectName("Section")
        right.addWidget(lbl)
        self.next = QLabel()
        self.next.setAlignment(Qt.AlignCenter)
        self.next.setMinimumSize(240, 135)
        right.addWidget(self.next)
        lbl = QLabel("ЗАМЕТКИ")
        lbl.setObjectName("Section")
        right.addWidget(lbl)
        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        f = self.notes.font()
        f.setPixelSize(18)
        self.notes.setFont(f)
        right.addWidget(self.notes, 1)
        mid.addLayout(right, 2)
        lay.addLayout(mid, 1)
        self.start = time.time()
        self.clock = QTimer(self, interval=500, timeout=self._clock)
        self.clock.start()
        player.changed.connect(lambda i: self.refresh())
        player.closed.connect(self.close)
        self.refresh()

    def reset_timer(self):
        self.start = time.time()
        self._clock()

    def _clock(self):
        s = int(time.time() - self.start)
        self.timer_lbl.setText(f"{s // 60:02d}:{s % 60:02d}")

    def _pix(self, i, size):
        if not (0 <= i < len(self.player.frames)):
            pix = QPixmap(size)
            pix.fill(QColor("#30302E"))
            return pix
        f = self.player.frames[i]
        b = world_bounds(f)
        k = min(size.width() / b.width(), size.height() / b.height())
        return QPixmap.fromImage(render_image(self.ed.renderer, [f], k))

    def refresh(self):
        i = self.player.cur
        self.count.setText(f"Слайд {i + 1} из {len(self.player.frames)}")
        self.current.setPixmap(self._pix(i, self.current.size()))
        self.next.setPixmap(self._pix(i + 1, self.next.size()))
        self.notes.setPlainText(self.player.frames[i].notes or "Заметок нет")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, self.refresh)

    def keyPressEvent(self, e):
        self.player.keyPressEvent(e)

    def closeEvent(self, e):
        self.clock.stop()
        if self.player.isVisible():
            self.player.close()
        super().closeEvent(e)


def open_player(editor, frames, start=0, slides=False, presenter=False):
    player = Player(editor, frames, start, slides)
    screens = QGuiApplication.screens()
    if presenter:
        pres = Presenter(editor, player)
        if len(screens) > 1:
            other = next((s for s in screens if s is not editor.screen()), screens[-1])
            player.setScreen(other)
            player.setGeometry(other.geometry())
            player.showFullScreen()
        else:
            player.show()
        pres.show()
        pres.raise_()
        return player, pres
    if slides:
        player.showFullScreen()
    else:
        player.show()
    player.raise_()
    player.activateWindow()
    return player, None
