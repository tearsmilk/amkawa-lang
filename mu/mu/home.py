"""Start screen: new model from a layered PSD or from a single picture, open a .mu project, import an Inochi2D
puppet; recent projects with thumbnails."""
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)

from . import APP_NAME, LOGO, icons
from .fileio import read_thumb

ACTIONS = [
    ("image", "Модель из PSD", "Слои PSD становятся частями модели: сетки, роли и авто-риг готовы за минуту",
     "new_from_psd"),
    ("cut", "Модель из картинки", "Одна иллюстрация PNG / JPG — нарежьте её на части прямо в Мю", "new_from_image"),
    ("folder", "Открыть проект", "Файл Мю (.mu) со всеми текстурами, ригом, позами и сценами", "open_dialog"),
    ("export", "Импорт Inochi2D", "Готовая модель .inp из Inochi Creator", "import_inp"),
    ("pose", "Пример: Школьница", "Готовая модель из одной картинки — нарезка, риг, позы, физика. Откройте и запустите "
     "Эфир с камерой", "open_example"),
]


class Card(QFrame):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()


class Home(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setObjectName("Home")
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        side = QFrame()
        side.setObjectName("HomeSide")
        side.setFixedWidth(230)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(18, 22, 18, 18)
        sv.setSpacing(6)
        top = QHBoxLayout()
        logo = QLabel(LOGO)
        logo.setObjectName("Mu")
        top.addWidget(logo)
        name = QLabel(APP_NAME)
        name.setObjectName("Title")
        top.addWidget(name)
        top.addStretch(1)
        sv.addLayout(top)
        sv.addSpacing(16)
        c = win.colors
        for ic, title, _, slot in ACTIONS:
            b = QPushButton("  " + title)
            b.setIcon(icons.icon(ic, c["text"], c["accent"]))
            b.setIconSize(QSize(18, 18))
            b.clicked.connect(getattr(win, slot))
            sv.addWidget(b)
        sv.addStretch(1)
        g = QPushButton("  Гайдбук")
        g.setIcon(icons.icon("book", c["text"], c["accent"]))
        g.setIconSize(QSize(18, 18))
        g.clicked.connect(win.open_guide)
        sv.addWidget(g)
        h.addWidget(side)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setObjectName("Home")
        self.body = QVBoxLayout(body)
        self.body.setContentsMargins(48, 40, 48, 40)
        self.body.setSpacing(14)
        scroll.setWidget(body)
        h.addWidget(scroll, 1)
        self.rebuild()

    def rebuild(self):
        while self.body.count():
            it = self.body.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                self._clear(it.layout())
        c = self.win.colors
        hello = QLabel("Что оживим сегодня?")
        hello.setObjectName("Title")
        self.body.addWidget(hello)
        sub = QLabel("Возьмите 2D-иллюстрацию — PSD со слоями или одну картинку — и превратите её в модель "
                     "для витубинга: нарезка, сетки, риг, физика, позы и эфир.")
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        self.body.addWidget(sub)
        grid = QGridLayout()
        grid.setSpacing(14)
        for k, (ic, title, text, slot) in enumerate(ACTIONS):
            card = Card()
            card.setMinimumHeight(118)
            v = QVBoxLayout(card)
            v.setContentsMargins(16, 14, 16, 14)
            iconl = QLabel()
            iconl.setPixmap(icons.pixmap(ic, c["text"], c["accent"], 30))
            v.addWidget(iconl)
            t = QLabel(title)
            t.setObjectName("CardTitle")
            v.addWidget(t)
            d = QLabel(text)
            d.setObjectName("Muted")
            d.setWordWrap(True)
            v.addWidget(d)
            card.clicked.connect(getattr(self.win, slot))
            grid.addWidget(card, k // 2, k % 2)
        self.body.addLayout(grid)
        recent = [p for p in self.win.settings.get("recent", []) if Path(p).exists()]
        if recent:
            lab = QLabel("НЕДАВНИЕ")
            lab.setObjectName("Section")
            self.body.addSpacing(10)
            self.body.addWidget(lab)
            rg = QGridLayout()
            rg.setSpacing(14)
            for k, path in enumerate(recent[:12]):
                card = Card()
                card.setFixedSize(176, 214)
                v = QVBoxLayout(card)
                v.setContentsMargins(10, 10, 10, 10)
                th = QLabel()
                th.setFixedSize(156, 156)
                th.setAlignment(Qt.AlignCenter)
                img = read_thumb(path)
                if img is not None and not img.isNull():
                    th.setPixmap(QPixmap.fromImage(img).scaled(156, 156, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                else:
                    th.setPixmap(icons.pixmap("logo", c["text"], c["accent"], 80))
                v.addWidget(th)
                n = QLabel(Path(path).stem)
                n.setToolTip(path)
                v.addWidget(n)
                card.clicked.connect(lambda p=path: self.win.open_path(p))
                rg.addWidget(card, k // 4, k % 4)
            rg.setColumnStretch(4, 1)
            self.body.addLayout(rg)
        self.body.addStretch(1)

    def _clear(self, lay):
        while lay.count():
            it = lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                self._clear(it.layout())

