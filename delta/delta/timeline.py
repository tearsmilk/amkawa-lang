"""After Effects-style timeline: a ruler with the playhead, one row per layer (its in / out bar) and,
for expanded layers, rows for Position X / Y, Scale, Rotation and Opacity with keyframe diamonds.

◆ at the left of a property row adds or removes a key at the playhead; drag diamonds to retime them,
right-click a diamond for easing; drag the ends of a layer bar to trim it; double-click a value to type it."""
from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QMenu, QScrollArea, QSpinBox, QToolButton, QVBoxLayout, QWidget,
)

from . import icons
from .model import EASINGS, PROPS

NAME_W = 230
ROW = 22
RULER = 26


class Track(QWidget):
    def __init__(self, tl):
        super().__init__()
        self.tl = tl
        self.win = tl.win
        self.expanded = set()
        self.drag = None
        self.setMouseTracking(True)

    @property
    def doc(self):
        return self.win.doc

    # ------------------------------------------------------------------ layout
    def rows(self):
        """[(kind, layer, prop)] top to bottom."""
        out = []
        doc = self.doc
        if doc is None:
            return out
        for layer in reversed(doc.layers):
            out.append(("layer", layer, None))
            if layer.id in self.expanded or layer is doc.current:
                for key, _name, _d in PROPS:
                    out.append(("prop", layer, key))
        return out

    def sizeHint(self):
        return QSize(600, RULER + max(1, len(self.rows())) * ROW + 6)

    def px(self):
        doc = self.doc
        return max(3.0, (self.width() - NAME_W - 16) / max(1, doc.length)) if doc else 6.0

    def x_of(self, frame):
        return NAME_W + 8 + frame * self.px()

    def frame_at(self, x):
        doc = self.doc
        return max(0, min(doc.length - 1, int(round((x - NAME_W - 8) / self.px()))))

    # ------------------------------------------------------------------ painting
    def paintEvent(self, e):
        p = QPainter(self)
        c = self.win.theme
        p.fillRect(self.rect(), QColor(c["panel"]))
        doc = self.doc
        if doc is None:
            p.setPen(QColor(c["muted"]))
            p.drawText(self.rect(), Qt.AlignCenter, "Нет открытого документа")
            return
        small = QFont(self.font())
        small.setPixelSize(10)
        p.setFont(small)
        px = self.px()
        # ruler
        p.fillRect(QRect(NAME_W, 0, self.width() - NAME_W, RULER), QColor(c["bg"]))
        step = max(1, int(round(44 / px)))
        nice = [1, 2, 5, 10, 12, 24, 25, 30, 48, 50, 60, 100, 120, 240, 480]
        step = next((n for n in nice if n >= step), step)
        for f in range(0, doc.length + 1):
            x = self.x_of(f)
            second = doc.fps and f % doc.fps == 0
            if f % step and not (second and px * doc.fps >= 30):
                if px >= 5:
                    p.setPen(QColor(c["track"]))
                    p.drawLine(int(x), RULER - 3, int(x), RULER)
                continue
            p.setPen(QColor(c["accent"] if second and f else c["muted"]))
            p.drawLine(int(x), RULER - 7, int(x), RULER)
            label = f"{f // doc.fps}с" if second and f else str(f)
            p.drawText(QRectF(x + 3, 2, 44, RULER - 8), Qt.AlignLeft | Qt.AlignVCenter, label)
        p.setPen(QColor(c["border"]))
        p.drawLine(0, RULER - 1, self.width(), RULER - 1)
        # rows
        for i, (kind, layer, prop) in enumerate(self.rows()):
            y = RULER + i * ROW
            selected = layer is doc.current
            if kind == "layer":
                if selected:
                    p.fillRect(0, y, self.width(), ROW, QColor(c["selected"]))
                p.setPen(QColor(c["text"] if layer.visible else c["faint"]))
                arrow = "▾" if (layer.id in self.expanded or selected) else "▸"
                p.drawText(QRect(6, y, 14, ROW), Qt.AlignCenter, arrow)
                p.drawText(QRect(22, y, NAME_W - 30, ROW), Qt.AlignVCenter | Qt.AlignLeft,
                           p.fontMetrics().elidedText(layer.name, Qt.ElideRight, NAME_W - 34))
                end = layer.end if layer.end >= 0 else doc.length - 1
                bar = QRectF(self.x_of(layer.start) - px / 2, y + 5, (end - layer.start + 1) * px, ROW - 10)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(c["accent"] if selected else c["layer_bar"]))
                p.setOpacity(0.55 if selected else 1.0)
                p.drawRoundedRect(bar, 3, 3)
                p.setOpacity(1.0)
                # keys summary
                frames = sorted({k.frame for ks in layer.keys.values() for k in ks})
                p.setBrush(QColor(c["text"]))
                for f in frames:
                    self._diamond(p, self.x_of(f), y + ROW / 2, 3.5)
            else:
                name = dict((k, n) for k, n, _d in PROPS)[prop]
                keys = layer.keys.get(prop, [])
                has_key_now = layer.key_at(prop, doc.frame) is not None
                p.setPen(QColor(c["accent"] if has_key_now else (c["text"] if keys else c["faint"])))
                p.drawText(QRect(26, y, 16, ROW), Qt.AlignCenter, "◆" if keys else "◇")
                p.setPen(QColor(c["muted"]))
                p.drawText(QRect(44, y, 110, ROW), Qt.AlignVCenter | Qt.AlignLeft, name)
                val = layer.value(prop, doc.frame)
                unit = {"scale": " %", "opacity": " %", "rotation": "°"}.get(prop, "")
                p.setPen(QColor(c["accent"]))
                p.drawText(QRect(150, y, NAME_W - 156, ROW), Qt.AlignVCenter | Qt.AlignRight, f"{val:.1f}{unit}")
                p.setPen(QPen(QColor(c["track"]), 1))
                p.drawLine(NAME_W, y + ROW - 1, self.width(), y + ROW - 1)
                for k in keys:
                    hold = k.ease == "hold"
                    p.setPen(QPen(QColor(c["text"]), 1))
                    p.setBrush(QColor(c["key"]) if k.frame != doc.frame else QColor(c["text"]))
                    if hold:
                        p.drawRect(QRectF(self.x_of(k.frame) - 4, y + ROW / 2 - 4, 8, 8))
                    else:
                        self._diamond(p, self.x_of(k.frame), y + ROW / 2, 5)
                for a, b in zip(keys, keys[1:]):
                    p.setPen(QPen(QColor(c["key"]), 1, Qt.DotLine))
                    p.drawLine(QPointF(self.x_of(a.frame) + 6, y + ROW / 2), QPointF(self.x_of(b.frame) - 6, y + ROW / 2))
        p.setPen(QColor(c["border"]))
        p.drawLine(NAME_W, 0, NAME_W, self.height())
        # playhead
        x = self.x_of(doc.frame)
        p.setPen(QPen(QColor(c["accent"]), 1.5))
        p.drawLine(QPointF(x, 0), QPointF(x, self.height()))
        p.setBrush(QColor(c["accent"]))
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(x - 6, 0), QPointF(x + 6, 0), QPointF(x + 6, 8), QPointF(x, 14), QPointF(x - 6, 8)]))

    @staticmethod
    def _diamond(p, x, y, r):
        p.drawPolygon(QPolygonF([QPointF(x, y - r), QPointF(x + r, y), QPointF(x, y + r), QPointF(x - r, y)]))

    # ------------------------------------------------------------------ hit testing
    def hit(self, pos):
        doc = self.doc
        if pos.y() < RULER:
            return ("ruler", None, None, None)
        i = int((pos.y() - RULER) // ROW)
        rows = self.rows()
        if not 0 <= i < len(rows):
            return (None, None, None, None)
        kind, layer, prop = rows[i]
        x = pos.x()
        if kind == "layer":
            if x < 20:
                return ("expand", layer, None, None)
            if x < NAME_W:
                return ("layer", layer, None, None)
            end = layer.end if layer.end >= 0 else doc.length - 1
            for which, f in (("start", layer.start), ("end", end)):
                if abs(x - self.x_of(f)) <= max(4, self.px() / 2):
                    return ("trim", layer, which, f)
            return ("bar", layer, None, self.frame_at(x))
        if x < 44:
            return ("toggle", layer, prop, None)
        if x < NAME_W:
            return ("value", layer, prop, None)
        for k in layer.keys.get(prop, []):
            if abs(x - self.x_of(k.frame)) <= 6:
                return ("key", layer, prop, k)
        return ("track", layer, prop, self.frame_at(x))

    def mousePressEvent(self, e):
        doc = self.doc
        if doc is None:
            return
        kind, layer, a, b = self.hit(e.position())
        w = self.win
        if e.button() == Qt.RightButton and kind == "key":
            self._key_menu(layer, a, b, e.globalPosition().toPoint())
            return
        if kind in ("ruler", "bar", "track"):
            w.goto_frame(self.frame_at(e.position().x()))
            self.drag = ("scrub", None, None)
            if kind in ("bar", "track") and layer is not doc.current:
                w.select_layer(layer)
            return
        if kind == "expand":
            self.expanded ^= {layer.id}
            self.tl.relayout()
            return
        if kind == "layer":
            w.select_layer(layer)
            return
        if kind == "toggle":
            w.toggle_key(layer, a)
            return
        if kind == "key":
            doc.push("Ключ")
            self.drag = ("key", layer, (a, b))
            w.goto_frame(b.frame)
            return
        if kind == "trim":
            doc.push("Длительность слоя")
            self.drag = ("trim", layer, a)

    def mouseMoveEvent(self, e):
        if self.drag is None:
            kind = self.hit(e.position())[0]
            self.setCursor(Qt.SizeHorCursor if kind == "trim" else Qt.PointingHandCursor if kind in ("key", "toggle") else Qt.ArrowCursor)
            return
        doc = self.doc
        f = self.frame_at(e.position().x())
        kind, layer, info = self.drag
        if kind == "scrub":
            self.win.goto_frame(f)
        elif kind == "key":
            prop, key = info
            if f != key.frame and layer.key_at(prop, f) is None:
                key.frame = f
                layer.keys[prop].sort(key=lambda k: k.frame)
                self.win.goto_frame(f)
        elif kind == "trim":
            if info == "start":
                end = layer.end if layer.end >= 0 else doc.length - 1
                layer.start = min(f, end)
            else:
                layer.end = max(f, layer.start)
            self.win.canvas.refresh()
            self.update()

    def mouseReleaseEvent(self, e):
        if self.drag is not None and self.drag[0] in ("key", "trim"):
            self.win.document_changed()
        self.drag = None

    def mouseDoubleClickEvent(self, e):
        kind, layer, a, b = self.hit(e.position())
        if kind == "value":
            self.win.edit_key_value(layer, a)
        elif kind == "layer":
            self.win.select_layer(layer)
            self.win.rename_layer()

    def _key_menu(self, layer, prop, key, pos):
        m = QMenu(self)
        for k, label in EASINGS:
            a = m.addAction(label, lambda k=k: self.win.set_key_ease(layer, prop, key, k))
            a.setCheckable(True)
            a.setChecked(key.ease == k)
        m.addSeparator()
        m.addAction("Изменить значение…", lambda: (self.win.goto_frame(key.frame), self.win.edit_key_value(layer, prop)))
        m.addAction("Удалить ключ", lambda: self.win.remove_key(layer, prop, key.frame))
        m.exec(pos)


class Timeline(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 4, 8, 4)
        bar.setSpacing(4)

        def btn(text, tip, fn, icon=None, checkable=False):
            b = QToolButton()
            if icon:
                b.setIcon(icons.icon(icon))
            else:
                b.setText(text)
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.clicked.connect(fn)
            bar.addWidget(b)
            return b

        btn("⏮", "К началу (Home)", lambda: win.goto_frame(0))
        btn("◀", "Кадр назад (,)", lambda: win.step_frame(-1))
        self.play = btn("", "Проиграть / пауза (пробел в таймлайне, Enter)", win.toggle_play, "play", True)
        btn("▶", "Кадр вперёд (.)", lambda: win.step_frame(1))
        btn("⏭", "К концу (End)", lambda: win.goto_frame(-1))
        self.loop = QCheckBox("Повтор")
        self.loop.setChecked(True)
        bar.addWidget(self.loop)
        bar.addSpacing(12)
        self.keybtn = btn("◆ Ключ", "Ключи всех свойств текущего слоя на этом кадре (⇧K)", win.key_all)
        btn("Удалить ключи", "Удалить ключи текущего слоя на этом кадре", win.remove_keys_here)
        bar.addStretch(1)
        self.time = QLabel()
        self.time.setObjectName("Muted")
        bar.addWidget(self.time)
        bar.addSpacing(10)
        lab = QLabel("к/с")
        lab.setObjectName("Muted")
        self.fps = QSpinBox()
        self.fps.setRange(1, 120)
        self.fps.editingFinished.connect(lambda: win.set_comp(fps=self.fps.value()))
        bar.addWidget(self.fps)
        bar.addWidget(lab)
        lab2 = QLabel("Длительность")
        lab2.setObjectName("Muted")
        bar.addWidget(lab2)
        self.length = QSpinBox()
        self.length.setRange(1, 100000)
        self.length.setSuffix(" к.")
        self.length.editingFinished.connect(lambda: win.set_comp(length=self.length.value()))
        bar.addWidget(self.length)
        lay.addLayout(bar)
        self.track = Track(self)
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.track)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        lay.addWidget(self.scroll, 1)

    def relayout(self):
        self.track.setMinimumHeight(self.track.sizeHint().height())
        self.track.updateGeometry()
        self.track.update()

    def update_view(self):
        doc = self.win.doc
        if doc is not None:
            secs = doc.frame / max(1, doc.fps)
            self.time.setText(f"кадр {doc.frame} из {doc.length - 1}  ·  {int(secs // 60)}:{secs % 60:05.2f}")
            for box, val in ((self.fps, doc.fps), (self.length, doc.length)):
                box.blockSignals(True)
                box.setValue(val)
                box.blockSignals(False)
        else:
            self.time.setText("")
        self.relayout()


