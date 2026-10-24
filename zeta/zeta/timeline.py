"""Timeline: layers (eye, lock, name) × frames (cels), tags above the frame numbers, playback controls."""
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMenu, QScrollArea, QSpinBox, QToolButton, QVBoxLayout, QWidget,
)

from . import icons

NAME_W = 190
CELL_W = 24
ROW_H = 24
HEAD_H = 34   # tags (14) + numbers (20)


class Grid(QWidget):
    def __init__(self, tl):
        super().__init__()
        self.tl = tl
        self.win = tl.win
        self.setMouseTracking(True)
        self._drag_frame = None

    @property
    def doc(self):
        return self.win.doc

    def sizeHint(self):
        doc = self.doc
        if doc is None:
            return QSize(400, 80)
        return QSize(NAME_W + doc.sprite.frames * CELL_W + 40, HEAD_H + len(doc.sprite.layers) * ROW_H + 4)

    def minimumSizeHint(self):
        return self.sizeHint()

    def rows(self):
        return list(reversed(self.doc.sprite.layers))  # top layer first

    def paintEvent(self, e):
        p = QPainter(self)
        c = self.win.theme
        p.fillRect(self.rect(), QColor(c["panel"]))
        doc = self.doc
        if doc is None:
            p.setPen(QColor(c["muted"]))
            p.drawText(self.rect(), Qt.AlignCenter, "Нет открытого спрайта")
            return
        sp = doc.sprite
        small = QFont(self.font())
        small.setPixelSize(10)
        # current frame column
        cx = NAME_W + doc.frame * CELL_W
        p.fillRect(cx, 14, CELL_W, self.height(), QColor(c["frame_current"]))
        # tags
        for t in sp.tags:
            r = QRect(NAME_W + t.start * CELL_W + 1, 1, (t.end - t.start + 1) * CELL_W - 2, 12)
            p.fillRect(r, QColor(t.color))
            p.setPen(QColor(c["tag_text"]))
            p.setFont(small)
            p.drawText(r.adjusted(4, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, t.name)
        # frame numbers
        p.setFont(small)
        for f in range(sp.frames):
            r = QRect(NAME_W + f * CELL_W, 14, CELL_W, 20)
            p.setPen(QColor(c["text"] if f == doc.frame else c["muted"]))
            p.drawText(r, Qt.AlignCenter, str(f + 1))
        p.setPen(QPen(QColor(c["border"])))
        p.drawLine(0, HEAD_H - 1, self.width(), HEAD_H - 1)
        p.setFont(self.font())
        # rows
        for i, layer in enumerate(self.rows()):
            y = HEAD_H + i * ROW_H
            if layer is doc.layer:
                p.fillRect(0, y, NAME_W, ROW_H, QColor(c["selected"]))
            p.setPen(QColor(c["text"] if layer.visible else c["faint"]))
            p.drawText(QRect(6, y, 18, ROW_H), Qt.AlignCenter, "●" if layer.visible else "○")
            p.setPen(QColor(c["muted"] if layer.locked else c["faint"]))
            p.drawText(QRect(26, y, 18, ROW_H), Qt.AlignCenter, "🔒" if layer.locked else "·")
            p.setPen(QColor(c["text"] if layer.visible else c["muted"]))
            extra = "" if layer.opacity == 255 else f"  {round(layer.opacity / 2.55)}%"
            p.drawText(QRect(48, y, NAME_W - 52, ROW_H), Qt.AlignVCenter | Qt.AlignLeft,
                       p.fontMetrics().elidedText(layer.name + extra, Qt.ElideRight, NAME_W - 56))
            for f in range(sp.frames):
                r = QRect(NAME_W + f * CELL_W, y, CELL_W, ROW_H)
                if layer is doc.layer and f == doc.frame:
                    p.fillRect(r.adjusted(1, 1, -1, -1), QColor(c["selected"]))
                has = sp.cel(layer, f) is not None
                p.setRenderHint(QPainter.Antialiasing)
                if has:
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(c["cel"]))
                    p.drawEllipse(r.center(), 4, 4)
                else:
                    p.setPen(QPen(QColor(c["cel_empty"]), 1))
                    p.setBrush(Qt.NoBrush)
                    p.drawEllipse(r.center(), 3, 3)
                p.setRenderHint(QPainter.Antialiasing, False)
            p.setPen(QPen(QColor(c["border"])))
            p.drawLine(0, y + ROW_H - 1, NAME_W + sp.frames * CELL_W, y + ROW_H - 1)
        p.drawLine(NAME_W - 1, 0, NAME_W - 1, self.height())

    def hit(self, pos):
        """→ (kind, layer, frame)"""
        doc = self.doc
        if doc is None:
            return None, None, None
        x, y = pos.x(), pos.y()
        frame = (x - NAME_W) // CELL_W if x >= NAME_W else None
        if frame is not None and frame >= doc.sprite.frames:
            frame = None
        if y < HEAD_H:
            return ("tag" if y < 14 else "header"), None, frame
        row = (y - HEAD_H) // ROW_H
        rows = self.rows()
        layer = rows[row] if 0 <= row < len(rows) else None
        if layer is None:
            return None, None, frame
        if x < 24:
            return "eye", layer, None
        if x < 46:
            return "lock", layer, None
        if x < NAME_W:
            return "name", layer, None
        return "cel", layer, frame

    def mousePressEvent(self, e):
        kind, layer, frame = self.hit(e.position().toPoint())
        doc = self.doc
        if kind is None or doc is None:
            return
        if e.button() == Qt.RightButton:
            if layer is not None and kind in ("name", "eye", "lock"):
                self.win.select(layer=layer)
                self.tl.layer_menu(layer, e.globalPosition().toPoint())
            elif frame is not None:
                self.win.select(frame=frame, layer=layer)
                self.tl.frame_menu(frame, e.globalPosition().toPoint())
            return
        if kind == "eye":
            self.win.toggle_layer(layer, "visible")
        elif kind == "lock":
            self.win.toggle_layer(layer, "locked")
        elif kind == "name":
            self.win.select(layer=layer)
        elif kind in ("cel", "header", "tag") and frame is not None:
            self.win.select(frame=frame, layer=layer)
            self._drag_frame = frame if kind == "header" else None

    def mouseReleaseEvent(self, e):
        if self._drag_frame is not None:
            _k, _l, frame = self.hit(e.position().toPoint())
            if frame is not None and frame != self._drag_frame:
                self.win.move_frame(self._drag_frame, frame)
        self._drag_frame = None

    def mouseDoubleClickEvent(self, e):
        kind, layer, frame = self.hit(e.position().toPoint())
        if kind == "name":
            self.win.layer_properties(layer)
        elif kind == "header" and frame is not None:
            self.win.frame_properties()
        elif kind == "tag" and frame is not None:
            tag = next((t for t in self.doc.sprite.tags if t.start <= frame <= t.end), None)
            if tag:
                self.win.tag_properties(tag)


class Timeline(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setObjectName("Timeline")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 4, 8, 4)
        bar.setSpacing(2)
        t = QLabel("ТАЙМЛАЙН")
        t.setObjectName("Section")
        bar.addWidget(t)
        bar.addSpacing(10)
        self.buttons = {}

        def btn(key, text, tip, fn, checkable=False):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.clicked.connect(fn)
            bar.addWidget(b)
            self.buttons[key] = b
            return b

        btn("first", "⏮", "Первый кадр (Home)", lambda: win.goto_frame(0))
        btn("prev", "◀", "Предыдущий кадр (,)", lambda: win.step_frame(-1))
        self.play = btn("play", "", "Проиграть / пауза (Enter)", win.toggle_play, True)
        self.play.setIcon(icons.icon("play"))
        btn("next", "▶", "Следующий кадр (.)", lambda: win.step_frame(1))
        btn("last", "⏭", "Последний кадр (End)", lambda: win.goto_frame(-1))
        bar.addSpacing(8)
        self.onion = btn("onion", "◐", "Кальки — соседние кадры (F3)", win.toggle_onion, True)
        bar.addSpacing(8)
        btn("addframe", "＋ кадр", "Новый кадр (Alt+N)", lambda: win.new_frame(copy=False))
        btn("dupframe", "⧉ кадр", "Дублировать кадр (Alt+D)", lambda: win.new_frame(copy=True))
        btn("delframe", "− кадр", "Удалить кадр (Alt+C)", win.delete_frame)
        bar.addSpacing(8)
        btn("addlayer", "＋ слой", "Новый слой (⇧N)", win.new_layer)
        btn("dellayer", "− слой", "Удалить слой", win.delete_layer)
        bar.addStretch(1)
        self.dur_label = QLabel("Длительность")
        self.dur_label.setObjectName("Muted")
        bar.addWidget(self.dur_label)
        self.duration = QSpinBox()
        self.duration.setRange(1, 65535)
        self.duration.setSuffix(" мс")
        self.duration.setFixedWidth(92)
        self.duration.editingFinished.connect(lambda: win.set_duration(self.duration.value()))
        bar.addWidget(self.duration)
        self.fps = QLabel("")
        self.fps.setObjectName("Muted")
        bar.addWidget(self.fps)
        lay.addLayout(bar)
        self.grid = Grid(self)
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.grid)
        self.scroll.setWidgetResizable(False)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        lay.addWidget(self.scroll, 1)

    def refresh(self):
        doc = self.win.doc
        self.grid.resize(max(self.scroll.viewport().width(), self.grid.sizeHint().width()),
                         max(self.scroll.viewport().height(), self.grid.sizeHint().height()))
        self.grid.update()
        if doc is not None:
            d = doc.sprite.durations[doc.frame]
            self.duration.blockSignals(True)
            self.duration.setValue(d)
            self.duration.blockSignals(False)
            self.fps.setText(f"  {1000 / d:.1f} к/с · кадр {doc.frame + 1} из {doc.sprite.frames}")
            self.scroll.ensureVisible(NAME_W + doc.frame * CELL_W + CELL_W, 0, CELL_W * 2, 0)
        for b in self.buttons.values():
            b.setEnabled(doc is not None)
        self.duration.setEnabled(doc is not None)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.refresh()

    def layer_menu(self, layer, pos):
        w = self.win
        m = QMenu(self)
        m.addAction("Свойства слоя…", lambda: w.layer_properties(layer))
        m.addAction("Новый слой", w.new_layer)
        m.addAction("Дублировать слой", w.duplicate_layer)
        m.addAction("Объединить с нижним", w.merge_down)
        m.addSeparator()
        m.addAction("Поднять", lambda: w.move_layer(1))
        m.addAction("Опустить", lambda: w.move_layer(-1))
        m.addSeparator()
        m.addAction("Удалить слой", w.delete_layer)
        m.exec(pos)

    def frame_menu(self, frame, pos):
        w = self.win
        m = QMenu(self)
        m.addAction("Свойства кадра…", w.frame_properties)
        m.addAction("Новый кадр", lambda: w.new_frame(copy=False))
        m.addAction("Дублировать кадр", lambda: w.new_frame(copy=True))
        m.addAction("Удалить кадр", w.delete_frame)
        m.addSeparator()
        m.addAction("Новая метка…", w.new_tag)
        m.addAction("Очистить ячейку", w.clear_cel)
        m.exec(pos)
