"""Home screen: create a design file, a board, a presentation or a site; templates with live previews;
recent files with thumbnails."""
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPixmap
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from . import APP_NAME, LOGO, icons
from . import templates as tpl
from .fileio import make_thumbnail, read_meta
from .model import KIND_TITLES

KIND_TEXT = {
    "design": "Интерфейсы, макеты, иконки: фреймы, автолейаут, компоненты, прототипы",
    "board": "Доска для идей: стикеры, фигуры, соединители, маркер, штампы",
    "slides": "Слайды с темами и макетами, заметки докладчика, показ и PDF",
    "site": "Страницы из блоков, адаптивность, ссылки и экспорт в HTML",
}


class Card(QFrame):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()


def rounded(pix, radius=10):
    out = QPixmap(pix.size())
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    from PySide6.QtGui import QBrush, QPainterPath
    path = QPainterPath()
    path.addRoundedRect(0, 0, pix.width(), pix.height(), radius, radius)
    p.fillPath(path, QBrush(pix))
    p.end()
    return out


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
        side.setFixedWidth(220)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(18, 22, 18, 18)
        sv.setSpacing(6)
        top = QHBoxLayout()
        logo = QLabel(LOGO)
        logo.setObjectName("Lambda")
        top.addWidget(logo)
        name = QLabel(APP_NAME)
        name.setObjectName("Title")
        top.addWidget(name)
        top.addStretch(1)
        sv.addLayout(top)
        sv.addSpacing(16)
        for kind in ("design", "board", "slides", "site"):
            b = QPushButton(f"  Новый: {KIND_TITLES[kind].lower()}")
            b.setIconSize(QSize(18, 18))
            b.setProperty("kind", kind)
            b.clicked.connect(lambda _=False, k=kind: win.new_document(k))
            sv.addWidget(b)
            setattr(self, f"side_{kind}", b)
        sv.addSpacing(10)
        ob = QPushButton("  Открыть файл…")
        ob.clicked.connect(win.open_dialog)
        self.side_open = ob
        sv.addWidget(ob)
        sv.addStretch(1)
        note = QLabel("Всё работает без интернета.\nФайлы .lambda хранятся\nу вас на компьютере.")
        note.setObjectName("Muted")
        sv.addWidget(note)
        h.addWidget(side)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        h.addWidget(self.scroll, 1)
        self.thumbs = {}
        self._build()

    def set_theme(self, th):
        for kind in ("design", "board", "slides", "site"):
            getattr(self, f"side_{kind}").setIcon(icons.icon(kind, th["text"], th["accent"]))
        self.side_open.setIcon(icons.icon("folder", th["text"], th["accent"]))
        self.refresh()

    def _build(self):
        body = QWidget()
        body.setObjectName("Home")
        v = QVBoxLayout(body)
        v.setContentsMargins(40, 32, 40, 40)
        v.setSpacing(14)
        title = QLabel("Что создадим?")
        title.setObjectName("Title")
        v.addWidget(title)
        th = self.win.theme
        row = QHBoxLayout()
        row.setSpacing(16)
        for kind in ("design", "board", "slides", "site"):
            c = Card()
            c.setMinimumHeight(150)
            c.setMinimumWidth(150)
            c.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            cv = QVBoxLayout(c)
            cv.setContentsMargins(18, 16, 18, 16)
            ic = QLabel()
            ic.setPixmap(icons.pixmap(kind, th["text"], th["accent"], 44))
            cv.addWidget(ic)
            t = QLabel(KIND_TITLES[kind])
            t.setObjectName("CardTitle")
            cv.addWidget(t)
            d = QLabel(KIND_TEXT[kind])
            d.setObjectName("Muted")
            d.setWordWrap(True)
            cv.addWidget(d)
            cv.addStretch(1)
            c.clicked.connect(lambda k=kind: self.win.new_document(k))
            row.addWidget(c)
        v.addLayout(row)
        self.recent_title = QLabel("Недавние файлы")
        self.recent_title.setObjectName("Title")
        self.recent_title.setStyleSheet("font-size: 21px; padding-top: 14px;")
        v.addWidget(self.recent_title)
        self.recent_box = QWidget()
        self.recent_grid = QGridLayout(self.recent_box)
        self.recent_grid.setContentsMargins(0, 0, 0, 0)
        self.recent_grid.setSpacing(16)
        v.addWidget(self.recent_box)
        t = QLabel("Шаблоны")
        t.setObjectName("Title")
        t.setStyleSheet("font-size: 21px; padding-top: 14px;")
        v.addWidget(t)
        self.tpl_rows = {}
        for kind in ("design", "board", "slides", "site"):
            lbl = QLabel(KIND_TITLES[kind].upper())
            lbl.setObjectName("Section")
            v.addWidget(lbl)
            r = QGridLayout()
            r.setSpacing(16)
            for k, (key, name, _) in enumerate(tpl.TEMPLATES[kind]):
                c = Card()
                c.setFixedSize(236, 186)
                cv = QVBoxLayout(c)
                cv.setContentsMargins(10, 10, 10, 10)
                img = QLabel()
                img.setFixedSize(216, 132)
                img.setAlignment(Qt.AlignCenter)
                cv.addWidget(img)
                tl = QLabel(name)
                cv.addWidget(tl)
                c.clicked.connect(lambda k=kind, kk=key: self.win.new_document(k, kk))
                r.addWidget(c, k // 4, k % 4)
                self.thumbs[(kind, key)] = img
            r.setColumnStretch(4, 1)
            v.addLayout(r)
        v.addStretch(1)
        self.scroll.setWidget(body)
        QTimer.singleShot(50, self._render_templates)

    def _render_templates(self):
        pending = [k for k, lbl in self.thumbs.items() if lbl.pixmap() is None or lbl.pixmap().isNull()]
        if not pending:
            return
        kind, key = pending[0]
        try:
            doc = tpl.new_document(kind, key)
            img = make_thumbnail(doc, size=432)
            pix = QPixmap.fromImage(img).scaled(QSize(432, 264), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pix.setDevicePixelRatio(2.0)
            self.thumbs[(kind, key)].setPixmap(rounded(pix, 16))
        except Exception:
            pix = QPixmap(216, 132)
            pix.fill(QColor("#E3DFD3"))
            self.thumbs[(kind, key)].setPixmap(pix)
        QTimer.singleShot(10, self._render_templates)

    def refresh(self):
        while self.recent_grid.count():
            it = self.recent_grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        recent = [p for p in self.win.settings.get("recent", []) if Path(p).exists()][:12]
        self.recent_title.setVisible(bool(recent))
        self.recent_box.setVisible(bool(recent))
        for i, p in enumerate(recent):
            kind, thumb = read_meta(p)
            c = Card()
            c.setFixedSize(236, 200)
            cv = QVBoxLayout(c)
            cv.setContentsMargins(10, 10, 10, 10)
            img = QLabel()
            img.setFixedSize(216, 132)
            img.setAlignment(Qt.AlignCenter)
            if thumb is not None and not thumb.isNull():
                pix = QPixmap.fromImage(thumb).scaled(QSize(432, 264), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                pix.setDevicePixelRatio(2.0)
                img.setPixmap(rounded(pix, 16))
            cv.addWidget(img)
            name = QLabel(Path(p).stem)
            cv.addWidget(name)
            sub = QLabel(f"{KIND_TITLES.get(kind or 'design', '')} · {Path(p).parent.name}")
            sub.setObjectName("Muted")
            cv.addWidget(sub)
            c.clicked.connect(lambda path=p: self.win.open_path(path))
            c.setContextMenuPolicy(Qt.CustomContextMenu)
            c.customContextMenuRequested.connect(lambda pos, path=p, card=c: self._menu(card, pos, path))
            self.recent_grid.addWidget(c, i // 4, i % 4)
        self.recent_grid.setColumnStretch(4, 1)

    def _menu(self, card, pos, path):
        m = QMenu(self)
        m.addAction("Открыть", lambda: self.win.open_path(path))
        m.addAction("Показать в Finder", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent))))
        m.addAction("Убрать из списка", lambda: self._forget(path))
        m.exec(card.mapToGlobal(pos))

    def _forget(self, path):
        self.win.settings["recent"] = [p for p in self.win.settings.get("recent", []) if p != path]
        self.win.settings.save()
        self.refresh()
