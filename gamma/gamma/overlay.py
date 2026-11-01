"""Windows on top of the screen: region selector (frozen screenshot, loupe, handles, toolbar), recording frame and
bar, countdown, toasts. All of them are excluded from screenshots / recordings when that setting is on."""
import time

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout,
                               QWidget)

from . import icons, macos
from .theme import SERIF

INK = "#141413"
IVORY = "#FAF9F5"
ACCENT = "#D97757"
REC = "#D64545"
HANDLE = 7


def _float(widget, hide_from_capture=True, level=macos.SCREEN_SAVER_LEVEL):
    macos.float_above_all(widget, level)
    if hide_from_capture:
        macos.exclude_from_capture(widget)


def fmt_time(sec):
    sec = int(max(0, sec))
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class RegionSelector(QWidget):
    """Covers one screen with its frozen picture. Drag a rectangle; it can be moved / resized by handles, nudged with
    arrows. Enter / double click accepts (no selection = whole screen), Esc cancels.
    mode "shot": instant=True accepts on mouse release. mode "record": shows a toolbar with sound options."""

    accepted = Signal(QRect, dict)   # rect in points relative to the screen, options
    cancelled = Signal()

    AUDIO = (("none", "Без звука"), ("mic", "Микрофон"), ("system", "Система"), ("both", "Оба"))

    def __init__(self, screen, pixmap, mode="shot", instant=True, audio="none", hide_from_capture=True):
        # a plain window (not Qt.Tool): on macOS borderless panels may refuse to become key → no Esc / Enter
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.screen_ = screen
        self.pix = pixmap
        self.mode = mode
        self.instant = instant and mode == "shot"
        self.audio = audio
        self.hide_from_capture = hide_from_capture
        self.sel = QRect()
        self.drag = None          # ("new", origin) | ("move", offset) | ("resize", handle)
        self.mouse = QPoint(-100, -100)
        self.setGeometry(screen.geometry())
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.bar = self._toolbar()
        self.bar.hide()

    # -- toolbar under the selection
    def _toolbar(self):
        bar = QFrame(self)
        bar.setObjectName("SelBar")
        bar.setStyleSheet(f"""
            #SelBar {{ background: {IVORY}; border: 1px solid #E3DFD3; border-radius: 12px; }}
            #SelBar QPushButton {{ background: transparent; color: {INK}; border: none; border-radius: 7px;
                padding: 5px 9px; font-size: 12px; }}
            #SelBar QPushButton:hover {{ background: #E9E6DC; }}
            #SelBar QPushButton:checked {{ background: #E6E2D6; color: {INK}; }}
            #SelBar QPushButton#Go {{ background: {REC if self.mode == 'record' else ACCENT}; color: white;
                font-weight: 600; padding: 5px 14px; }}
            #SelBar QLabel {{ color: #6F6E69; font-size: 11px; padding: 0 4px; }}""")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(6, 5, 6, 5)
        lay.setSpacing(2)
        self.audio_buttons = {}
        if self.mode == "record":
            lay.addWidget(QLabel("Звук:"))
            for key, title in self.AUDIO:
                b = QPushButton(title)
                b.setCheckable(True)
                b.setChecked(key == self.audio)
                b.setCursor(Qt.PointingHandCursor)
                b.clicked.connect(lambda _=False, k=key: self._set_audio(k))
                lay.addWidget(b)
                self.audio_buttons[key] = b
            lay.addSpacing(8)
            go = QPushButton("●  Начать запись")
        else:
            go = QPushButton("Снимок")
        go.setObjectName("Go")
        go.setCursor(Qt.PointingHandCursor)
        go.clicked.connect(self.accept)
        cancel = QPushButton("Отмена")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.cancel)
        lay.addWidget(cancel)
        lay.addWidget(go)
        self.go_button = go
        return bar

    def _set_audio(self, key):
        self.audio = key
        for k, b in self.audio_buttons.items():
            b.setChecked(k == key)

    def showEvent(self, e):
        super().showEvent(e)
        _float(self, self.hide_from_capture)
        self.activateWindow()
        self.raise_()
        self.setFocus()

    # -- geometry helpers
    def _handles(self):
        r = self.sel
        if r.isNull():
            return {}
        cx, cy = r.center().x(), r.center().y()
        pts = {"tl": (r.left(), r.top()), "t": (cx, r.top()), "tr": (r.right(), r.top()), "r": (r.right(), cy),
               "br": (r.right(), r.bottom()), "b": (cx, r.bottom()), "bl": (r.left(), r.bottom()), "l": (r.left(), cy)}
        return {k: QRect(x - HANDLE, y - HANDLE, HANDLE * 2, HANDLE * 2) for k, (x, y) in pts.items()}

    def _hit(self, pos):
        for k, rr in self._handles().items():
            if rr.contains(pos):
                return k
        if not self.sel.isNull() and self.sel.contains(pos):
            return "move"
        return None

    def _place_bar(self):
        if self.sel.isNull() or (self.instant and self.drag):
            self.bar.hide()
            return
        if self.instant:
            self.bar.hide()
            return
        self.bar.adjustSize()
        w, h = self.bar.width(), self.bar.height()
        x = min(max(8, self.sel.center().x() - w // 2), self.width() - w - 8)
        y = self.sel.bottom() + 12
        if y + h > self.height() - 8:
            y = self.sel.top() - h - 12
        if y < 8:
            y = self.sel.bottom() - h - 12
        self.bar.move(x, y)
        self.bar.show()
        self.bar.raise_()

    # -- mouse
    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.cancel()
            return
        pos = e.position().toPoint()
        hit = self._hit(pos)
        if hit == "move":
            self.drag = ("move", pos - self.sel.topLeft())
        elif hit:
            self.drag = ("resize", hit)
        else:
            self.drag = ("new", pos)
            self.sel = QRect(pos, QSize(0, 0))
        self.bar.hide()
        self.update()

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        self.mouse = pos
        if self.drag:
            kind, data = self.drag
            if kind == "new":
                self.sel = QRect(min(data.x(), pos.x()), min(data.y(), pos.y()), abs(pos.x() - data.x()),
                                 abs(pos.y() - data.y()))
            elif kind == "move":
                tl = pos - data
                tl.setX(min(max(0, tl.x()), self.width() - self.sel.width()))
                tl.setY(min(max(0, tl.y()), self.height() - self.sel.height()))
                self.sel.moveTopLeft(tl)
            else:
                r = QRect(self.sel)
                if "l" in data:
                    r.setLeft(pos.x())
                if "r" in data:
                    r.setRight(pos.x())
                if "t" in data:
                    r.setTop(pos.y())
                if "b" in data:
                    r.setBottom(pos.y())
                self.sel = r.normalized()
        else:
            hit = self._hit(pos)
            cur = {"move": Qt.SizeAllCursor, "tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor,
                   "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor, "t": Qt.SizeVerCursor, "b": Qt.SizeVerCursor,
                   "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor}.get(hit, Qt.CrossCursor)
            self.setCursor(cur)
        self.update()

    def mouseReleaseEvent(self, e):
        if not self.drag:
            return
        kind = self.drag[0]
        self.drag = None
        self.sel = self.sel.intersected(self.rect())
        if kind == "new" and (self.sel.width() < 4 or self.sel.height() < 4):
            self.sel = QRect()
            if self.instant:   # a click = the whole screen
                self.accept()
                return
        elif self.instant:
            self.accept()
            return
        self._place_bar()
        self.update()

    def mouseDoubleClickEvent(self, e):
        self.accept()

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key_Escape:
            self.cancel()
        elif k in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.accept()
        elif k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down) and not self.sel.isNull():
            step = 10 if e.modifiers() & Qt.ShiftModifier else 1
            dx = {Qt.Key_Left: -step, Qt.Key_Right: step}.get(k, 0)
            dy = {Qt.Key_Up: -step, Qt.Key_Down: step}.get(k, 0)
            if e.modifiers() & Qt.AltModifier:   # ⌥ + arrows resize
                self.sel.setWidth(max(4, self.sel.width() + dx))
                self.sel.setHeight(max(4, self.sel.height() + dy))
            else:
                self.sel.translate(dx, dy)
            self._place_bar()
            self.update()
        else:
            super().keyPressEvent(e)

    def accept(self):
        rect = self.sel if not self.sel.isNull() else self.rect()
        rect = rect.intersected(self.rect())
        opts = {"audio": self.audio}
        self.hide()
        self.accepted.emit(QRect(rect), opts)
        self.close()

    def cancel(self):
        self.hide()
        self.cancelled.emit()
        self.close()

    # -- painting
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.drawPixmap(self.rect(), self.pix)
        dim = QColor(20, 20, 19, 115)
        if self.sel.isNull():
            p.fillRect(self.rect(), dim)
        else:
            path = QPainterPath()
            path.addRect(QRectF(self.rect()))
            inner = QPainterPath()
            inner.addRect(QRectF(self.sel))
            p.fillPath(path.subtracted(inner), dim)
            color = QColor(REC if self.mode == "record" else ACCENT)
            p.setPen(QPen(color, 1.5, Qt.DashLine if self.mode == "record" else Qt.SolidLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(self.sel).adjusted(-0.5, -0.5, 0.5, 0.5))
            if not self.drag or self.drag[0] != "new":
                p.setPen(QPen(color, 1.5))
                p.setBrush(QColor(IVORY))
                for rr in self._handles().values():
                    p.drawEllipse(QRectF(rr).adjusted(2.5, 2.5, -2.5, -2.5))
            self._size_label(p)
        if self.sel.isNull() and not self.drag:
            self._hint(p)
        if not self.sel.isNull() and self.drag and self.drag[0] != "move" or self.sel.isNull():
            self._loupe(p)
        p.end()

    def _pill(self, p, text, center, bold=False):
        f = QFont()
        f.setPixelSize(12)
        f.setBold(bold)
        p.setFont(f)
        w = p.fontMetrics().horizontalAdvance(text) + 20
        r = QRectF(center.x() - w / 2, center.y() - 12, w, 24)
        r.moveLeft(min(max(6, r.left()), self.width() - w - 6))
        r.moveTop(min(max(6, r.top()), self.height() - 30))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 20, 19, 215))
        p.drawRoundedRect(r, 12, 12)
        p.setPen(QColor(IVORY))
        p.drawText(r, Qt.AlignCenter, text)

    def _size_label(self, p):
        dpr = self.pix.devicePixelRatio() or 1.0
        text = f"{round(self.sel.width() * dpr)} × {round(self.sel.height() * dpr)}"
        c = QPointF(self.sel.center().x(), self.sel.top() - 18 if self.sel.top() > 34 else self.sel.top() + 18)
        self._pill(p, text, c)

    def _hint(self, p):
        if self.mode == "record":
            t = "Выделите область для записи  ·  Enter — весь экран  ·  Esc — отмена"
        else:
            t = "Выделите область  ·  щелчок — весь экран  ·  Esc — отмена"
        self._pill(p, t, QPointF(self.width() / 2, 60))

    def _loupe(self, p):
        if self.mouse.x() < 0:
            return
        dpr = self.pix.devicePixelRatio() or 1.0
        size, zoom = 116, 8
        src_px = size / zoom
        cx, cy = self.mouse.x() * dpr, self.mouse.y() * dpr
        src = QRectF(cx - src_px / 2, cy - src_px / 2, src_px, src_px)
        x = self.mouse.x() + 24
        y = self.mouse.y() + 24
        if x + size > self.width():
            x = self.mouse.x() - 24 - size
        if y + size + 26 > self.height():
            y = self.mouse.y() - 24 - size - 26
        target = QRectF(x, y, size, size)
        clip = QPainterPath()
        clip.addRoundedRect(target, 12, 12)
        p.save()
        p.setClipPath(clip)
        p.fillRect(target, QColor(INK))
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        src_img = self.pix.copy(src.toRect())
        src_img.setDevicePixelRatio(1.0)
        p.drawPixmap(target.toRect(), src_img)
        p.setPen(QPen(QColor(ACCENT), 1))
        p.drawLine(QPointF(target.center().x(), target.top()), QPointF(target.center().x(), target.bottom()))
        p.drawLine(QPointF(target.left(), target.center().y()), QPointF(target.right(), target.center().y()))
        p.restore()
        p.setPen(QPen(QColor(IVORY), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(target, 12, 12)
        self._pill(p, f"{round(cx)}, {round(cy)}", QPointF(target.center().x(), target.bottom() + 14))


class RecordFrame(QWidget):
    """Dashed red frame just outside the recorded region; click-through."""

    def __init__(self, global_rect, hide_from_capture=True):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool |
                         Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.hide_from_capture = hide_from_capture
        self.setGeometry(global_rect.adjusted(-4, -4, 4, 4))

    def showEvent(self, e):
        super().showEvent(e)
        _float(self, self.hide_from_capture)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(REC), 2, Qt.DashLine))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 3, 3)
        p.end()


class _Floating(QFrame):
    """Rounded ivory card in its own frameless window, draggable."""

    def __init__(self, hide_from_capture=True):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.hide_from_capture = hide_from_capture
        self._drag = None
        self.card = QFrame(self)
        self.card.setObjectName("FloatCard")
        self.card.setStyleSheet(f"""
            #FloatCard {{ background: {IVORY}; border: 1px solid #E3DFD3; border-radius: 14px; }}
            #FloatCard QLabel {{ color: {INK}; }}
            #FloatCard QLabel#Muted {{ color: #6F6E69; font-size: 11px; }}
            #FloatCard QLabel#Time {{ font-family: {SERIF}; font-size: 17px; }}
            #FloatCard QLabel#Big {{ font-family: {SERIF}; font-size: 15px; }}
            #FloatCard QPushButton {{ background: #FFFFFF; color: {INK}; border: 1px solid #E3DFD3; border-radius: 7px;
                padding: 4px 10px; font-size: 12px; }}
            #FloatCard QPushButton:hover {{ background: #E9E6DC; }}
            #FloatCard QPushButton#Stop {{ background: {REC}; color: white; border: none; font-weight: 600; }}
            #FloatCard QToolButton {{ border: none; border-radius: 6px; padding: 3px; }}
            #FloatCard QToolButton:hover {{ background: #E9E6DC; }}""")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.card)

    def showEvent(self, e):
        super().showEvent(e)
        _float(self, self.hide_from_capture, macos.STATUS_LEVEL + 2)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None


class RecordBar(_Floating):
    """● 00:12 · sound · [Стоп] [✕]"""

    stop_clicked = Signal()
    cancel_clicked = Signal()

    def __init__(self, title="Запись", audio_text="", hide_from_capture=True):
        super().__init__(hide_from_capture)
        lay = QHBoxLayout(self.card)
        lay.setContentsMargins(12, 7, 8, 7)
        lay.setSpacing(8)
        self.dot = QLabel()
        self.dot.setFixedSize(12, 12)
        lay.addWidget(self.dot)
        self.time = QLabel("00:00")
        self.time.setObjectName("Time")
        lay.addWidget(self.time)
        info = QLabel(title + (f" · {audio_text}" if audio_text else ""))
        info.setObjectName("Muted")
        lay.addWidget(info)
        stop = QPushButton("Стоп")
        stop.setObjectName("Stop")
        stop.setCursor(Qt.PointingHandCursor)
        stop.clicked.connect(self.stop_clicked)
        lay.addWidget(stop)
        cancel = QToolButton()
        cancel.setIcon(icons.icon("trash"))
        cancel.setToolTip("Отменить запись (файл не сохранится)")
        cancel.clicked.connect(self.cancel_clicked)
        lay.addWidget(cancel)
        self._on = True
        self._paint_dot()

    def _paint_dot(self):
        pix = QPixmap(24, 24)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(REC)
        c.setAlpha(255 if self._on else 90)
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(2, 2, 20, 20))
        p.end()
        pix.setDevicePixelRatio(2)
        self.dot.setPixmap(pix)

    def set_time(self, sec):
        self.time.setText(fmt_time(sec))
        on = int(sec * 2) % 2 == 0   # slow blink, once a second
        if on != self._on:
            self._on = on
            self._paint_dot()

    def place(self, region_global, screen_geom):
        """Under the recorded region, or at the top centre of the screen for a full-screen recording."""
        self.adjustSize()
        w, h = self.width(), self.height()
        if region_global is not None and region_global != screen_geom:
            x = region_global.center().x() - w // 2
            y = region_global.bottom() + 12
            if y + h > screen_geom.bottom() - 4:
                y = region_global.top() - h - 12
            if y < screen_geom.top() + 28:
                y = region_global.bottom() - h - 12
        else:
            x = screen_geom.center().x() - w // 2
            y = screen_geom.top() + 34
        x = min(max(screen_geom.left() + 6, x), screen_geom.right() - w - 6)
        self.move(x, y)


class Countdown(QWidget):
    """3 · 2 · 1 in a terracotta circle; a click cancels."""

    finished = Signal()
    cancelled = Signal()

    def __init__(self, seconds, center, hide_from_capture=True):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.hide_from_capture = hide_from_capture
        self.left = int(seconds)
        self.resize(150, 170)
        self.move(int(center.x() - 75), int(center.y() - 75))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.setCursor(Qt.PointingHandCursor)

    def start(self):
        if self.left <= 0:
            QTimer.singleShot(0, self, self.finished.emit)
            return
        self.show()
        self.timer.start(1000)

    def showEvent(self, e):
        super().showEvent(e)
        _float(self, self.hide_from_capture)

    def _tick(self):
        self.left -= 1
        if self.left <= 0:
            self.timer.stop()
            self.hide()
            # let the window disappear from the screen before the capture starts
            QTimer.singleShot(120, self, self.finished.emit)
            QTimer.singleShot(200, self, self.deleteLater)
        else:
            self.update()

    def mousePressEvent(self, e):
        self.timer.stop()
        self.hide()
        self.cancelled.emit()
        self.deleteLater()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(217, 119, 87, 235))
        p.drawEllipse(QRectF(5, 5, 140, 140))
        f = QFont(SERIF.split(",")[0].strip('" '))
        f.setPixelSize(76)
        p.setFont(f)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(QRectF(5, 0, 140, 145), Qt.AlignCenter, str(self.left))
        f.setPixelSize(11)
        p.setFont(QFont())
        p.setPen(QColor(IVORY))
        p.drawText(QRectF(0, 148, 150, 20), Qt.AlignCenter, "щелчок — отмена")
        p.end()


class Toast(_Floating):
    """Bottom-right card: thumbnail, title, file name, actions. Hides after a while unless hovered."""

    def __init__(self, title, text="", thumb=None, actions=(), timeout=6.0, hide_from_capture=True):
        super().__init__(hide_from_capture)
        self.setFixedWidth(340)
        lay = QHBoxLayout(self.card)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)
        self.thumb = QLabel()
        self.thumb.setFixedSize(96, 64)
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setStyleSheet("background: #E9E6DC; border-radius: 8px;")
        if thumb is not None and not thumb.isNull():
            self.set_thumb(thumb)
        else:
            self.thumb.setPixmap(icons.pixmap("logo", size=40))
        lay.addWidget(self.thumb)
        col = QVBoxLayout()
        col.setSpacing(3)
        self.title = QLabel(title)
        self.title.setObjectName("Big")
        col.addWidget(self.title)
        self.text = QLabel(text)
        self.text.setObjectName("Muted")
        self.text.setWordWrap(True)
        col.addWidget(self.text)
        row = QHBoxLayout()
        row.setSpacing(4)
        for name, fn in actions:
            b = QPushButton(name)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            b.clicked.connect(self.close)
            row.addWidget(b)
        row.addStretch(1)
        col.addLayout(row)
        lay.addLayout(col, 1)
        close = QToolButton(self.card)
        close.setIcon(icons.icon("close"))
        close.setIconSize(QSize(12, 12))
        close.clicked.connect(self.close)
        close.move(340 - 26, 6)
        self.deadline = None
        self.timeout = timeout
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(250)
        self._hover = False
        self.setAttribute(Qt.WA_DeleteOnClose)

    def set_thumb(self, pix):
        pix = pix.scaled(QSize(96, 64) * 2, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pix.setDevicePixelRatio(2)
        self.thumb.setPixmap(pix)

    def set_text(self, title=None, text=None):
        if title is not None:
            self.title.setText(title)
        if text is not None:
            self.text.setText(text)

    def keep(self, on=True):
        """Stay on screen until keep(False) (progress toasts)."""
        self.deadline = None if on else time.monotonic() + self.timeout

    def popup(self):
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        g = screen.availableGeometry()
        self.adjustSize()
        self.move(g.right() - self.width() - 14, g.bottom() - self.height() - 14)
        self.show()
        if self.timeout:
            self.deadline = time.monotonic() + self.timeout

    def enterEvent(self, e):
        self._hover = True

    def leaveEvent(self, e):
        self._hover = False
        if self.deadline is not None:
            self.deadline = max(self.deadline, time.monotonic() + 2.0)

    def _tick(self):
        if self.deadline is not None and not self._hover and time.monotonic() > self.deadline:
            self.close()
