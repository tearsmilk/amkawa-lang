"""Colour panel: HSV picker (saturation/value square, hue and alpha bars, hex), palette grid, preview."""
from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox, QSizePolicy, QToolButton,
    QVBoxLayout, QWidget,
)

from . import palettes


def checker(p, rect, cell=5):
    p.save()
    p.setClipRect(rect)
    p.fillRect(rect, QColor("#FFFFFF"))
    y = rect.top()
    while y < rect.bottom():
        x = rect.left() + (((y - rect.top()) // cell) % 2) * cell
        while x < rect.right():
            p.fillRect(QRectF(x, y, cell, cell), QColor("#D7D3C8"))
            x += cell * 2
        y += cell
    p.restore()


class SVSquare(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.h, self.s, self.v = 0.0, 1.0, 1.0
        self.setMinimumSize(150, 120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, e):
        p = QPainter(self)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.fillRect(r, QColor.fromHsvF(self.h, 1, 1))
        g = QLinearGradient(r.topLeft(), r.topRight())
        g.setColorAt(0, QColor(255, 255, 255, 255))
        g.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(r, g)
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, QColor(0, 0, 0, 0))
        g.setColorAt(1, QColor(0, 0, 0, 255))
        p.fillRect(r, g)
        x = r.left() + self.s * r.width()
        y = r.top() + (1 - self.v) * r.height()
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#FFFFFF" if self.v < 0.6 else "#141413"), 1.5))
        p.drawEllipse(QPointF(x, y), 5, 5)

    def _pick(self, pos):
        self.s = min(1.0, max(0.0, pos.x() / max(1, self.width())))
        self.v = 1 - min(1.0, max(0.0, pos.y() / max(1, self.height())))
        self.update()
        self.changed.emit()

    def mousePressEvent(self, e):
        self._pick(e.position())

    def mouseMoveEvent(self, e):
        if e.buttons():
            self._pick(e.position())


class Bar(QWidget):
    """Horizontal hue or alpha slider."""
    changed = Signal()

    def __init__(self, kind):
        super().__init__()
        self.kind = kind
        self.value = 0.0
        self.color = QColor("#D97757")
        self.setFixedHeight(14)

    def paintEvent(self, e):
        p = QPainter(self)
        r = QRectF(self.rect()).adjusted(0, 2, 0, -2)
        g = QLinearGradient(r.topLeft(), r.topRight())
        if self.kind == "hue":
            for i in range(7):
                g.setColorAt(i / 6, QColor.fromHsvF((i / 6) % 1.0, 1, 1))
        else:
            checker(p, r, 4)
            c0, c1 = QColor(self.color), QColor(self.color)
            c0.setAlpha(0)
            c1.setAlpha(255)
            g.setColorAt(0, c0)
            g.setColorAt(1, c1)
        p.fillRect(r, g)
        x = r.left() + self.value * r.width()
        p.setPen(QPen(QColor("#141413"), 1))
        p.setBrush(QColor("#FFFFFF"))
        p.drawRect(QRectF(x - 2, 0, 4, self.height() - 1))

    def _pick(self, pos):
        self.value = min(1.0, max(0.0, pos.x() / max(1, self.width())))
        self.update()
        self.changed.emit()

    def mousePressEvent(self, e):
        self._pick(e.position())

    def mouseMoveEvent(self, e):
        if e.buttons():
            self._pick(e.position())


class Swatches(QWidget):
    """Primary / secondary colour squares (click — edit, ⇄ — swap)."""
    swap = Signal()
    select = Signal(bool)  # secondary?

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setFixedSize(52, 52)
        self.setToolTip("Основной и второй цвет · X — поменять местами")

    def paintEvent(self, e):
        p = QPainter(self)
        c = self.win.theme
        back = QRect(18, 18, 30, 30)
        front = QRect(2, 2, 30, 30)
        for rect, col in ((back, self.win.secondary), (front, self.win.primary)):
            checker(p, rect, 5)
            p.fillRect(rect, col)
            p.setPen(QPen(QColor(c["border"]), 1))
            p.drawRect(rect.adjusted(0, 0, -1, -1))
        p.setPen(QColor(c["muted"]))
        p.drawText(QRect(34, 0, 18, 16), Qt.AlignCenter, "⇄")

    def mousePressEvent(self, e):
        pos = e.position().toPoint()
        if pos.x() > 34 and pos.y() < 16:
            self.swap.emit()
        else:
            self.select.emit(not QRect(2, 2, 30, 30).contains(pos))


class PaletteGrid(QWidget):
    picked = Signal(QColor, bool)   # colour, secondary?
    edited = Signal()

    CELL = 17

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.colors = []
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

    def set_colors(self, colors):
        self.colors = list(colors)
        self.updateGeometry()
        self.update()

    def cols(self):
        return max(4, self.width() // self.CELL)

    def sizeHint(self):
        rows = (len(self.colors) + 1 + self.cols() - 1) // self.cols()
        return QSize(220, max(1, rows) * self.CELL + 2)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        cols = max(4, w // self.CELL)
        return ((len(self.colors) + cols) // cols) * self.CELL + 2

    def _rect(self, i):
        cols = self.cols()
        return QRect((i % cols) * self.CELL, (i // cols) * self.CELL, self.CELL - 1, self.CELL - 1)

    def index_at(self, pos):
        cols = self.cols()
        i = (pos.y() // self.CELL) * cols + pos.x() // self.CELL
        return i if 0 <= pos.x() < cols * self.CELL and 0 <= i <= len(self.colors) else -1

    def paintEvent(self, e):
        p = QPainter(self)
        c = self.win.theme
        prim = self.win.primary.rgba()
        sec = self.win.secondary.rgba()
        for i, argb in enumerate(self.colors):
            r = self._rect(i)
            col = QColor.fromRgba(argb)
            if col.alpha() < 255:
                checker(p, r, 4)
            p.fillRect(r, col)
            if argb == prim or argb == sec:
                p.setPen(QPen(QColor(c["text"]), 2 if argb == prim else 1))
                p.drawRect(r.adjusted(1, 1, -1, -1))
        r = self._rect(len(self.colors))
        p.setPen(QPen(QColor(c["muted"]), 1, Qt.DashLine))
        p.drawRect(r.adjusted(0, 0, -1, -1))
        p.drawText(r, Qt.AlignCenter, "+")

    def mousePressEvent(self, e):
        i = self.index_at(e.position().toPoint())
        if i < 0:
            return
        if i == len(self.colors):
            if e.button() == Qt.LeftButton:
                self.add(self.win.primary)
            return
        self.picked.emit(QColor.fromRgba(self.colors[i]), e.button() == Qt.RightButton)

    def add(self, color):
        argb = color.rgba()
        if argb not in self.colors:
            self.colors.append(argb)
            self.edited.emit()
            self.updateGeometry()
            self.update()

    def _menu(self, pos):
        i = self.index_at(pos)
        if i < 0 or i >= len(self.colors):
            return
        m = QMenu(self)
        m.addAction("Сделать вторым цветом", lambda: self.picked.emit(QColor.fromRgba(self.colors[i]), True))
        m.addAction("Заменить основным цветом", lambda: self._replace(i))
        m.addAction("Удалить из палитры", lambda: self._remove(i))
        m.exec(self.mapToGlobal(pos))

    def _replace(self, i):
        self.colors[i] = self.win.primary.rgba()
        self.edited.emit()
        self.update()

    def _remove(self, i):
        del self.colors[i]
        self.edited.emit()
        self.updateGeometry()
        self.update()


class Preview(QWidget):
    """The current frame at an integer scale that fits."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.image = None
        self.setMinimumHeight(110)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_image(self, img):
        self.image = img
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        c = self.win.theme
        p.fillRect(self.rect(), QColor(c["canvas"]))
        if self.image is None or self.image.isNull():
            return
        w, h = self.image.width(), self.image.height()
        k = min((self.width() - 12) / w, (self.height() - 12) / h)
        k = int(k) if k >= 1 else k
        rw, rh = w * k, h * k
        r = QRectF((self.width() - rw) / 2, (self.height() - rh) / 2, rw, rh)
        checker(p, r, 4)
        p.drawImage(r, self.image)


class ColorPanel(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setObjectName("SidePanel")
        self.setFixedWidth(250)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        t = QLabel("ЦВЕТ")
        t.setObjectName("Section")
        lay.addWidget(t)
        self.sv = SVSquare()
        lay.addWidget(self.sv, 2)
        self.hue = Bar("hue")
        self.alpha = Bar("alpha")
        lay.addWidget(self.hue)
        lay.addWidget(self.alpha)
        row = QHBoxLayout()
        self.hex = QLineEdit()
        self.hex.setPlaceholderText("#RRGGBB")
        self.hex.setMaxLength(9)
        self.hex.editingFinished.connect(self._hex_entered)
        row.addWidget(self.hex, 1)
        self.rgba = QLabel()
        self.rgba.setObjectName("Muted")
        row.addWidget(self.rgba)
        lay.addLayout(row)
        self.editing_secondary = False
        self.sv.changed.connect(self._from_picker)
        self.hue.changed.connect(self._from_picker)
        self.alpha.changed.connect(self._from_picker)

        lay.addSpacing(6)
        prow = QHBoxLayout()
        t = QLabel("ПАЛИТРА")
        t.setObjectName("Section")
        prow.addWidget(t)
        prow.addStretch(1)
        self.preset = QComboBox()
        self.preset.addItem("Пресет…")
        for name in palettes.PRESETS:
            self.preset.addItem(name)
        self.preset.activated.connect(self._preset)
        prow.addWidget(self.preset)
        more = QToolButton()
        more.setText("···")
        more.clicked.connect(lambda: self._palette_menu(more))
        prow.addWidget(more)
        lay.addLayout(prow)
        self.grid = PaletteGrid(win)
        self.grid.picked.connect(lambda col, sec: win.set_color(col, sec))
        self.grid.edited.connect(self._palette_edited)
        lay.addWidget(self.grid)
        lay.addSpacing(6)
        t = QLabel("ПРЕДПРОСМОТР")
        t.setObjectName("Section")
        lay.addWidget(t)
        self.preview = Preview(win)
        lay.addWidget(self.preview, 3)

    # ------------------------------------------------------------------ picker
    def show_color(self, color, secondary=False):
        self.editing_secondary = secondary
        h, s, v, a = color.getHsvF()
        if h >= 0:
            self.sv.h = h
            self.hue.value = h
        self.sv.s, self.sv.v = s, v
        self.alpha.value = a
        self.alpha.color = color
        self.sv.update()
        self.hue.update()
        self.alpha.update()
        self.hex.setText(color.name(QColor.HexRgb).upper() if color.alpha() == 255 else
                         "#" + f"{color.rgba() & 0xFFFFFF:06X}{color.alpha():02X}")
        self.rgba.setText(f"{color.red()} {color.green()} {color.blue()} · {round(color.alpha() / 2.55)}%")

    def _from_picker(self):
        self.sv.h = self.hue.value
        col = QColor.fromHsvF(self.hue.value, self.sv.s, self.sv.v, self.alpha.value)
        self.sv.update()
        self.win.set_color(col, self.editing_secondary, from_picker=True)
        self.alpha.color = col
        self.alpha.update()
        self.hex.setText(col.name().upper() if col.alpha() == 255 else "#" + f"{col.rgba() & 0xFFFFFF:06X}{col.alpha():02X}")
        self.rgba.setText(f"{col.red()} {col.green()} {col.blue()} · {round(col.alpha() / 2.55)}%")

    def _hex_entered(self):
        t = self.hex.text().strip().lstrip("#")
        try:
            if len(t) == 6:
                col = QColor("#" + t)
            elif len(t) == 8:
                col = QColor("#" + t[:6])
                col.setAlpha(int(t[6:], 16))
            elif len(t) == 3:
                col = QColor("#" + "".join(ch * 2 for ch in t))
            else:
                return
        except ValueError:
            return
        if col.isValid():
            self.win.set_color(col, self.editing_secondary)

    # ------------------------------------------------------------------ palette
    def set_palette(self, colors):
        self.grid.set_colors(colors)

    def _palette_edited(self):
        self.win.palette_edited(self.grid.colors)

    def _preset(self, i):
        if i <= 0:
            return
        name = self.preset.itemText(i)
        self.preset.setCurrentIndex(0)
        self.win.replace_palette(palettes.preset(name), name)

    def _palette_menu(self, button):
        m = QMenu(self)
        m.addAction("Добавить основной цвет", lambda: self.grid.add(self.win.primary))
        m.addAction("Цвета из спрайта", self.win.palette_from_sprite)
        m.addAction("Сортировать по оттенку", self._sort)
        m.addSeparator()
        m.addAction("Загрузить палитру…", self._load)
        m.addAction("Сохранить палитру…", self._save)
        m.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def _sort(self):
        def key(argb):
            c = QColor.fromRgba(argb)
            h, s, v, _a = c.getHsvF()
            return (s < 0.1, h if h >= 0 else 0, v)
        self.win.replace_palette(sorted(self.grid.colors, key=key), "сортировка")

    def _load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Загрузить палитру", "", "Палитры (*.gpl *.hex *.pal *.txt)")
        if path:
            try:
                self.win.replace_palette(palettes.load(path), path)
            except Exception as exc:
                QMessageBox.warning(self, "Дзета", f"Не удалось загрузить палитру: {exc}")

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить палитру", "palette.gpl", "GIMP (*.gpl);;HEX (*.hex)")
        if path:
            palettes.save(path, self.grid.colors)
