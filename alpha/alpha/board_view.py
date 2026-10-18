"""The kanban board: horizontally scrolling lists, each with its own vertical scroll; cards painted by `CardFace`.
Drag and drop: cards between / within lists (placeholder shows where it lands), lists by their header.
Inline composers for new cards and lists, list menus (copy, move all, sort, archive, WIP limit, colour)."""
from PySide6.QtCore import QEvent, QMimeData, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QDrag, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu,
                               QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QToolButton,
                               QVBoxLayout, QWidget, QWidgetAction)

from . import icons, theme
from .widgets import CardFace, paint_background

CARD_MIME = "application/x-alpha-card"
LIST_MIME = "application/x-alpha-list"
COL_W = 272
CARD_W = COL_W - 16


class CardWidget(QWidget):
    clicked = Signal(str)
    menu = Signal(str, QPoint)

    def __init__(self, view, card):
        super().__init__()
        self.view = view
        self.card = card
        self.face = CardFace(view.board, card, CARD_W, compact=view.compact)
        self.setFixedSize(CARD_W, self.face.h)
        self.hover = False
        self.ghost = False
        self._press = None
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.setToolTip("")

    def paintEvent(self, _):
        p = QPainter(self)
        self.face.paint(p, hover=self.hover, ghost=self.ghost)
        p.end()

    def enterEvent(self, e):
        self.hover = True
        self.view.hovered = self.card["id"]
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        if self.view.hovered == self.card["id"]:
            self.view.hovered = None
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press = e.position().toPoint()
        elif e.button() == Qt.RightButton:
            self.menu.emit(self.card["id"], e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if self._press is None or not (e.buttons() & Qt.LeftButton):
            return
        if (e.position().toPoint() - self._press).manhattanLength() < 6:
            return
        self._press = None
        self.start_drag()

    def mouseReleaseEvent(self, e):
        if self._press is not None and e.button() == Qt.LeftButton:
            self._press = None
            self.clicked.emit(self.card["id"])

    def start_drag(self):
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(CARD_MIME, self.card["id"].encode())
        mime.setText(self.card["title"])
        drag.setMimeData(mime)
        pix = self.face.pixmap()
        drag.setPixmap(pix)
        drag.setHotSpot(QPoint(int(self.width() / 2), 16))
        self.view.dragging = self.card["id"]
        col = self.parent().column if hasattr(self.parent(), "column") else None
        if col is not None:   # the card leaves a gap where it was, like Trello
            col.stack.show_placeholder(col.stack.index_at(self.y() + self.height() / 2 - 1), self.height())
        cid = self.card["id"]
        QTimer.singleShot(0, lambda: self.hide() if self.view.dragging == cid else None)
        drag.exec(Qt.MoveAction)
        self.view.dragging = None
        try:
            self.show()
        except RuntimeError:  # the board was rebuilt by the drop
            pass
        self.view.end_drag()


class Placeholder(QWidget):
    def __init__(self, h):
        super().__init__()
        self.setFixedSize(CARD_W, max(36, h))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1), 9, 9)
        p.fillPath(path, QColor(0, 0, 0, 30))
        p.end()


class Composer(QFrame):
    """Inline text box with «Добавить» / ✕ (new card, new list, checklist item…)."""

    submitted = Signal(str)
    closed = Signal()

    def __init__(self, placeholder, button="Добавить карточку", single_line=False):
        super().__init__()
        self.setObjectName("Composer")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        if single_line:
            self.edit = QLineEdit()
            self.edit.returnPressed.connect(self._submit)
        else:
            self.edit = QPlainTextEdit()
            self.edit.setFixedHeight(62)
            self.edit.installEventFilter(self)
        self.edit.setPlaceholderText(placeholder)
        self.edit.setObjectName("ComposerEdit")
        lay.addWidget(self.edit)
        row = QHBoxLayout()
        ok = QPushButton(button)
        ok.setObjectName("Accent")
        ok.clicked.connect(self._submit)
        row.addWidget(ok)
        x = QToolButton()
        x.setIcon(icons.icon("close", theme.CURRENT["text"]))
        x.clicked.connect(self.closed)
        row.addWidget(x)
        row.addStretch(1)
        lay.addLayout(row)

    def text(self):
        return self.edit.text() if isinstance(self.edit, QLineEdit) else self.edit.toPlainText()

    def _submit(self):
        t = self.text().strip()
        if t:
            self.submitted.emit(t)
        if isinstance(self.edit, QLineEdit):
            self.edit.clear()
        else:
            self.edit.setPlainText("")
        self.edit.setFocus()

    def eventFilter(self, obj, e):
        if obj is self.edit and e.type() == e.Type.KeyPress:
            if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not e.modifiers() & Qt.ShiftModifier:
                self._submit()
                return True
            if e.key() == Qt.Key_Escape:
                self.closed.emit()
                return True
        return False

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.closed.emit()
        else:
            super().keyPressEvent(e)


class CardStack(QWidget):
    """The cards of one list, plus a drop placeholder while dragging."""

    def __init__(self, column):
        super().__init__()
        self.column = column
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(8, 2, 8, 4)
        self.lay.setSpacing(8)
        self.lay.setAlignment(Qt.AlignTop)
        self.placeholder = None
        self._ph_idx = -1

    def cards(self):
        return [self.lay.itemAt(i).widget() for i in range(self.lay.count())
                if isinstance(self.lay.itemAt(i).widget(), CardWidget)]

    def _eligible(self):
        """(layout index, widget) of the cards a drop can go between: visible and not the dragged one."""
        out = []
        for i in range(self.lay.count()):
            w = self.lay.itemAt(i).widget()
            if isinstance(w, CardWidget) and not w.isHidden() and w.card["id"] != self.column.view.dragging:
                out.append((i, w))
        return out

    def index_at(self, y):
        """Insertion index among the eligible cards for a y in stack coordinates (placeholder-independent)."""
        ph_i = self.lay.indexOf(self.placeholder) if self.placeholder is not None else -1
        ph_h = self.placeholder.height() + self.lay.spacing() if ph_i >= 0 else 0
        idx = 0
        for i, w in self._eligible():
            center = w.y() + w.height() / 2 - (ph_h if 0 <= ph_i < i else 0)
            if y > center:
                idx += 1
        return idx

    def show_placeholder(self, idx, h):
        if self.placeholder is None:
            self.placeholder = Placeholder(h)
        else:
            if self.lay.indexOf(self.placeholder) >= 0 and self._ph_idx == idx:
                return
            self.lay.removeWidget(self.placeholder)
        self._ph_idx = idx
        eligible = self._eligible()
        pos = eligible[idx][0] if idx < len(eligible) else self.lay.count()
        self.lay.insertWidget(pos, self.placeholder)
        self.placeholder.show()

    def hide_placeholder(self):
        if self.placeholder is not None:
            self.lay.removeWidget(self.placeholder)
            self.placeholder.deleteLater()
            self.placeholder = None


class ListColumn(QFrame):
    def __init__(self, view, lst):
        super().__init__()
        self.view = view
        self.lst = lst
        b = view.board
        self.setObjectName("ListCol")
        self.setFixedWidth(COL_W)
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Maximum)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 8)
        lay.setSpacing(4)
        # header
        head = QWidget()
        head.setObjectName("ListHead")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(12, 0, 6, 0)
        hl.setSpacing(4)
        if lst.get("color"):
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(f"background: {theme.label_hex(lst['color'])}; border-radius: 5px;")
            hl.addWidget(dot)
        self.title = QLabel(lst["name"])
        self.title.setObjectName("ListTitle")
        self.title.setWordWrap(True)
        hl.addWidget(self.title, 1)
        self.title_edit = QLineEdit(lst["name"])
        self.title_edit.setObjectName("ListTitleEdit")
        self.title_edit.hide()
        self.title_edit.editingFinished.connect(self._rename_done)
        hl.addWidget(self.title_edit, 1)
        cards = [c for c in b.cards(lst["id"])]
        visible = [c for c in cards if view.visible(c)]
        n = len(cards)
        wip = int(lst.get("wip") or 0)
        cnt = QLabel(f"{len(visible)}/{n}" if len(visible) != n else (f"{n}/{wip}" if wip else str(n)))
        cnt.setObjectName("ListCountOver" if wip and n > wip else "ListCount")
        cnt.setToolTip("Лимит карточек превышен" if wip and n > wip else "Карточек в списке")
        hl.addWidget(cnt)
        more = QToolButton()
        more.setIcon(icons.icon("dots", theme.CURRENT["list_text"]))
        more.setCursor(Qt.PointingHandCursor)
        more.clicked.connect(lambda: self.list_menu(more.mapToGlobal(more.rect().bottomLeft())))
        hl.addWidget(more)
        head.installEventFilter(self)
        self.title.installEventFilter(self)
        self.head = head
        lay.addWidget(head)
        # cards
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setObjectName("ListScroll")
        self.stack = CardStack(self)
        self.stack.setObjectName("CardStack")
        for c in cards:
            w = CardWidget(view, c)
            w.clicked.connect(view.open_card)
            w.menu.connect(view.card_menu)
            w.setVisible(view.visible(c))
            self.stack.lay.addWidget(w)
        self.scroll.setWidget(self.stack)
        lay.addWidget(self.scroll)
        # composer
        self.add_btn = QPushButton("+  Добавить карточку")
        self.add_btn.setObjectName("AddCard")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.clicked.connect(self.open_composer)
        foot = QWidget()
        fl = QVBoxLayout(foot)
        fl.setContentsMargins(8, 0, 8, 0)
        fl.addWidget(self.add_btn)
        self.composer = Composer("Введите название карточки…")
        self.composer.submitted.connect(self._add_card)
        self.composer.closed.connect(self.close_composer)
        self.composer.hide()
        fl.addWidget(self.composer)
        lay.addWidget(foot)
        self._press = None
        self._fit()

    def _fit(self):
        """Grow with the content up to the board height (then the list scrolls)."""
        content = sum(w.height() + 8 for w in self.stack.cards() if w.isVisible()) + 8
        self.scroll.setMinimumHeight(min(content, 60) if content > 8 else 0)
        self.scroll.setMaximumHeight(max(content, 4))

    # -- header: rename on double click, drag the list
    def eventFilter(self, obj, e):
        t = e.type()
        if obj in (self.head, self.title):
            if t == e.Type.MouseButtonDblClick:
                self.title.hide()
                self.title_edit.show()
                self.title_edit.setFocus()
                self.title_edit.selectAll()
                return True
            if t == e.Type.MouseButtonPress and e.button() == Qt.LeftButton:
                self._press = e.globalPosition().toPoint()
                return True
            elif t == e.Type.MouseMove and self._press is not None and e.buttons() & Qt.LeftButton:
                if (e.globalPosition().toPoint() - self._press).manhattanLength() > 8:
                    self._press = None
                    self.drag_list()
                    return True
            elif t == e.Type.MouseButtonRelease:
                self._press = None
        return False

    def _rename_done(self):
        name = self.title_edit.text().strip()
        self.title_edit.hide()
        self.title.show()
        if name and name != self.lst["name"]:
            self.view.board.rename_list(self.lst["id"], name)
            QTimer.singleShot(0, self.view.changed.emit)

    def drag_list(self):
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(LIST_MIME, self.lst["id"].encode())
        drag.setMimeData(mime)
        pix = self.grab()
        drag.setPixmap(pix)
        drag.setHotSpot(QPoint(COL_W // 2, 16))
        self.view.dragging_list = self.lst["id"]
        self.setGraphicsEffect(None)
        drag.exec(Qt.MoveAction)
        self.view.dragging_list = None
        self.view.lane.hide_marker()

    # -- composer
    def open_composer(self):
        self.view.close_composers()
        self.add_btn.hide()
        self.composer.show()
        self.composer.edit.setFocus()
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()))

    def close_composer(self):
        self.composer.hide()
        self.add_btn.show()

    def _add_card(self, text):
        for line in [t.strip() for t in text.splitlines() if t.strip()] if "\n" in text else [text]:
            self.view.board.add_card(self.lst["id"], line)
        self.view.reopen_composer = self.lst["id"]
        self.view.changed.emit()

    # -- drops
    def _stack_y(self, pos):
        return self.stack.mapFrom(self, pos).y()

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(CARD_MIME) or e.mimeData().hasFormat(LIST_MIME) or image_from_mime(e.mimeData()):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        md = e.mimeData()
        pos = e.position().toPoint()
        if image_from_mime(md):
            e.acceptProposedAction()
        elif md.hasFormat(CARD_MIME):
            cid = bytes(md.data(CARD_MIME)).decode()
            card = self.view.board.card(cid)
            h = CardFace(self.view.board, card, CARD_W).h if card else 40
            idx = self.stack.index_at(self._stack_y(pos))
            self.view.clear_placeholders(except_col=self)
            self.stack.show_placeholder(idx, h)
            self.scroll.setMaximumHeight(16777215)
            # autoscroll inside the list and across the board
            vy = self.scroll.viewport().mapFrom(self, pos).y()
            bar = self.scroll.verticalScrollBar()
            if vy < 30:
                bar.setValue(bar.value() - 14)
            elif vy > self.scroll.viewport().height() - 30:
                bar.setValue(bar.value() + 14)
            self.view.autoscroll(self.mapTo(self.view, pos))
            e.acceptProposedAction()
        elif md.hasFormat(LIST_MIME):
            self.view.lane.dragMoveEvent_at(self.mapTo(self.view.lane, pos))
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        pass

    def dropEvent(self, e):
        md = e.mimeData()
        if image_from_mime(md):
            e.acceptProposedAction()
            self.view.background_dropped.emit(image_from_mime(md))
        elif md.hasFormat(CARD_MIME):
            cid = bytes(md.data(CARD_MIME)).decode()
            idx = self.stack.index_at(self._stack_y(e.position().toPoint()))
            eligible = self.stack._eligible()
            before = eligible[idx][1].card["id"] if idx < len(eligible) else None
            e.acceptProposedAction()
            self.view.drop_card(cid, self.lst["id"], before=before)
        elif md.hasFormat(LIST_MIME):
            e.acceptProposedAction()
            self.view.lane.drop_list_at(self.mapTo(self.view.lane, e.position().toPoint()))

    # -- list menu
    def list_menu(self, pos):
        b = self.view.board
        lid = self.lst["id"]
        m = QMenu(self)
        m.addAction("Добавить карточку", self.open_composer)
        templates = [c for c in b.cards() if c.get("template")]
        if templates:
            tm = m.addMenu("Карточка из шаблона")
            for t in templates:
                tm.addAction(t["title"], lambda t_=t: self._from_template(t_))
        m.addAction("Копировать список", lambda: self._copy())
        mv = m.addMenu("Переместить все карточки в…")
        for other in b.lists():
            if other["id"] != lid:
                mv.addAction(other["name"], lambda o=other["id"]: (b.move_all_cards(lid, o), self.view.changed.emit()))
        so = m.addMenu("Сортировать")
        for key, title in (("title", "По названию"), ("due", "По сроку"), ("created", "По дате создания (сначала старые)"),
                           ("votes", "По голосам")):
            so.addAction(title, lambda k=key: (b.sort_list(lid, k), self.view.changed.emit()))
        m.addSeparator()
        wip = QWidgetAction(m)
        wbox = QWidget()
        wl = QHBoxLayout(wbox)
        wl.setContentsMargins(10, 2, 10, 2)
        wl.addWidget(QLabel("Лимит карточек"))
        spin = QSpinBox()
        spin.setRange(0, 99)
        spin.setSpecialValueText("нет")
        spin.setValue(int(self.lst.get("wip") or 0))
        spin.valueChanged.connect(lambda v: (b.set_list(lid, wip=v), self.view.changed_later()))
        wl.addWidget(spin)
        wip.setDefaultWidget(wbox)
        m.addAction(wip)
        col = m.addMenu("Цвет списка")
        col.addAction("Без цвета", lambda: (b.set_list(lid, color=""), self.view.changed.emit()))
        for key, (hexv, name) in theme.LABEL_COLORS.items():
            a = col.addAction(name, lambda k=key: (b.set_list(lid, color=k), self.view.changed.emit()))
            a.setIcon(_dot_icon(hexv))
        m.addSeparator()
        m.addAction("Архивировать все карточки списка", lambda: (b.archive_all_cards(lid), self.view.changed.emit()))
        m.addAction("Архивировать список", lambda: (b.set_list(lid, closed=True), self.view.changed.emit()))
        m.exec(pos)

    def _from_template(self, t):
        c = self.view.board.copy_card(t["id"], self.lst["id"], len(self.view.board.cards(self.lst["id"])))
        if c:
            self.view.board.update_card(c["id"], template=False, text="")
        self.view.changed.emit()

    def _copy(self):
        name, ok = QInputDialog.getText(self, "Копировать список", "Название:", text=self.lst["name"])
        if ok:
            self.view.board.copy_list(self.lst["id"], name.strip() or self.lst["name"])
            self.view.changed.emit()


def image_from_mime(md):
    """Local picture file dragged from Finder, or None."""
    if not md.hasUrls():
        return None
    from pathlib import Path

    from .backgrounds import IMAGE_EXT

    for url in md.urls():
        if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in IMAGE_EXT:
            return url.toLocalFile()
    return None


def _safe(fn):
    """Deferred UI tweaks may outlive the widgets of a board that was rebuilt again meanwhile."""
    try:
        fn()
    except RuntimeError:
        pass


def _dot_icon(hexv):
    from PySide6.QtGui import QIcon, QPixmap

    pix = QPixmap(24, 24)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(hexv))
    p.setPen(Qt.NoPen)
    p.drawEllipse(3, 3, 18, 18)
    p.end()
    return QIcon(pix)


class AddListColumn(QFrame):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.setObjectName("AddList")
        self.setFixedWidth(COL_W)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Maximum)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        self.btn = QPushButton("+  Добавить ещё один список")
        self.btn.setObjectName("AddListBtn")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.clicked.connect(self.open)
        lay.addWidget(self.btn)
        self.composer = Composer("Название списка…", "Добавить список", single_line=True)
        self.composer.submitted.connect(self._add)
        self.composer.closed.connect(self.close_composer)
        self.composer.hide()
        lay.addWidget(self.composer)

    def open(self):
        self.view.close_composers()
        self.btn.hide()
        self.setObjectName("AddListOpen")
        self.style().unpolish(self)
        self.style().polish(self)
        self.composer.show()
        self.composer.edit.setFocus()

    def close_composer(self):
        self.composer.hide()
        self.btn.show()
        self.setObjectName("AddList")
        self.style().unpolish(self)
        self.style().polish(self)

    def _add(self, name):
        self.view.board.add_list(name)
        self.view.reopen_list_composer = True
        self.view.changed.emit()


class Lane(QWidget):
    """Row of columns; handles list drops and draws the insertion marker."""

    def __init__(self, view):
        super().__init__()
        self.view = view
        self.setAcceptDrops(True)
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(12, 12, 12, 12)
        self.lay.setSpacing(12)
        self.lay.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.marker_x = None

    def columns(self):
        return [self.lay.itemAt(i).widget() for i in range(self.lay.count())
                if isinstance(self.lay.itemAt(i).widget(), ListColumn)]

    def list_index_at(self, x):
        idx = 0
        for col in self.columns():
            if col.lst["id"] == self.view.dragging_list:
                continue
            if x > col.x() + col.width() / 2:
                idx += 1
        return idx

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(LIST_MIME) or e.mimeData().hasFormat(CARD_MIME) or image_from_mime(e.mimeData()):
            e.acceptProposedAction()

    def dragMoveEvent_at(self, pos):
        idx = self.list_index_at(pos.x())
        cols = [c for c in self.columns() if c.lst["id"] != self.view.dragging_list]
        if idx < len(cols):
            self.marker_x = cols[idx].x() - 7
        elif cols:
            self.marker_x = cols[-1].x() + cols[-1].width() + 5
        else:
            self.marker_x = 6
        self.view.autoscroll(self.mapTo(self.view, pos))
        self.update()

    def dragMoveEvent(self, e):
        if image_from_mime(e.mimeData()):
            e.acceptProposedAction()
        elif e.mimeData().hasFormat(LIST_MIME):
            self.dragMoveEvent_at(e.position().toPoint())
            e.acceptProposedAction()
        elif e.mimeData().hasFormat(CARD_MIME):
            self.view.autoscroll(self.mapTo(self.view, e.position().toPoint()))
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.hide_marker()

    def hide_marker(self):
        self.marker_x = None
        self.update()

    def drop_list_at(self, pos):
        lid = self.view.dragging_list
        self.hide_marker()
        if lid:
            self.view.board.move_list(lid, self.list_index_at(pos.x()))
            QTimer.singleShot(0, self.view.changed.emit)

    def dropEvent(self, e):
        if image_from_mime(e.mimeData()):
            e.acceptProposedAction()
            self.view.background_dropped.emit(image_from_mime(e.mimeData()))
        elif e.mimeData().hasFormat(LIST_MIME):
            e.acceptProposedAction()
            self.drop_list_at(e.position().toPoint())
        elif e.mimeData().hasFormat(CARD_MIME):
            # dropped between columns: to the bottom of the nearest list
            x = e.position().toPoint().x()
            cols = self.columns()
            if cols:
                col = min(cols, key=lambda c: abs(c.x() + c.width() / 2 - x))
                e.acceptProposedAction()
                self.view.drop_card(bytes(e.mimeData().data(CARD_MIME)).decode(), col.lst["id"])

    def paintEvent(self, _):
        if self.marker_x is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#FFFFFF"), 4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(self.marker_x, 16, self.marker_x, self.height() - 16)
        p.end()


class AnchorMark(QWidget):
    """The ✥ mark shown where the wheel was clicked (autoscroll origin)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(255, 255, 255, 220))
        p.setPen(QPen(QColor("#141413"), 1.4))
        p.drawEllipse(2, 2, 28, 28)
        p.setBrush(QColor("#141413"))
        p.setPen(Qt.NoPen)
        for a, b, c in (((16, 6), (12, 11), (20, 11)), ((16, 26), (12, 21), (20, 21)),
                        ((6, 16), (11, 12), (11, 20)), ((26, 16), (21, 12), (21, 20))):
            from PySide6.QtGui import QPolygon

            p.drawPolygon(QPolygon([QPoint(*a), QPoint(*b), QPoint(*c)]))
        p.drawEllipse(14, 14, 4, 4)
        p.end()


class BoardView(QScrollArea):
    """Shows one board. Emits `changed` after any edit (the window saves, refreshes the other views)."""

    changed = Signal()
    open_card_requested = Signal(str)
    card_menu_requested = Signal(str, QPoint)
    background_dropped = Signal(str)

    def __init__(self, board, settings=None):
        super().__init__()
        self.board = board
        self.settings = settings or {}
        self.filter = {}
        self.compact = bool(self.settings.get("compact"))
        self.hovered = None
        self.dragging = None
        self.dragging_list = None
        self.reopen_composer = None
        self.reopen_list_composer = False
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setObjectName("BoardScroll")
        self.viewport().setAutoFillBackground(False)
        self._pan = None          # {"last": QPoint, "start": QPoint, "col": ListColumn | None, "button"}
        self._auto = None         # autoscroll anchor (global QPoint) after a wheel click
        self._auto_col = None
        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(self._autoscroll_step)
        self._anchor = AnchorMark(self.viewport())
        self._anchor.hide()
        QApplication.instance().installEventFilter(self)
        self.rebuild()

    # -- navigation with the mouse wheel: press-and-drag pans, a click starts autoscroll; left-drag on empty board
    def _column_at(self, gpos):
        w = QApplication.widgetAt(gpos)
        while w is not None and not isinstance(w, ListColumn):
            if w is self:
                return None
            w = w.parentWidget()
        return w

    def eventFilter(self, obj, e):
        t = e.type()
        if t not in (QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.MouseButtonRelease, QEvent.KeyPress,
                     QEvent.Wheel):
            return False
        try:
            if not self.isVisible():
                return False
        except RuntimeError:
            return False
        if self._auto is not None:
            if t in (QEvent.MouseButtonPress, QEvent.Wheel) or (t == QEvent.KeyPress and e.key() == Qt.Key_Escape):
                self.stop_autoscroll()
                return t != QEvent.Wheel
            return False
        if t == QEvent.MouseButtonPress and isinstance(obj, QWidget) and (obj is self or self.isAncestorOf(obj)):
            if obj.window() is not self.window():
                return False
            middle = e.button() == Qt.MiddleButton
            empty = e.button() == Qt.LeftButton and obj in (self.viewport(), self.lane)
            if middle or empty:
                g = e.globalPosition().toPoint()
                self._pan = {"last": g, "start": g, "col": self._column_at(g), "button": e.button()}
                QApplication.setOverrideCursor(Qt.ClosedHandCursor)
                return True
        elif t == QEvent.MouseMove and self._pan is not None:
            g = e.globalPosition().toPoint()
            d = g - self._pan["last"]
            self._pan["last"] = g
            self.scroll_by(-d.x(), -d.y(), self._pan["col"])
            return True
        elif t == QEvent.MouseButtonRelease and self._pan is not None and e.button() == self._pan["button"]:
            pan, self._pan = self._pan, None
            QApplication.restoreOverrideCursor()
            if pan["button"] == Qt.MiddleButton and (pan["last"] - pan["start"]).manhattanLength() < 4:
                self.start_autoscroll(pan["start"], pan["col"])
            return True
        return False

    def scroll_by(self, dx, dy, col=None):
        bar = self.horizontalScrollBar()
        bar.setValue(int(bar.value() + dx))
        if col is not None and dy:
            try:
                vb = col.scroll.verticalScrollBar()
                vb.setValue(int(vb.value() + dy))
            except RuntimeError:
                pass

    def start_autoscroll(self, gpos, col):
        self._auto = gpos
        self._auto_col = col
        self._anchor.move(self.viewport().mapFromGlobal(gpos) - QPoint(16, 16))
        self._anchor.show()
        self._anchor.raise_()
        QApplication.setOverrideCursor(Qt.SizeAllCursor)
        self._auto_timer.start(16)

    def stop_autoscroll(self):
        if self._auto is None:
            return
        self._auto = None
        self._auto_timer.stop()
        self._anchor.hide()
        QApplication.restoreOverrideCursor()

    def _autoscroll_step(self):
        from PySide6.QtGui import QCursor

        if self._auto is None:
            return
        d = QCursor.pos() - self._auto

        def speed(v):
            dead = 14
            if abs(v) <= dead:
                return 0
            return (1 if v > 0 else -1) * ((abs(v) - dead) / 7.0) ** 1.35

        self.scroll_by(speed(d.x()), speed(d.y()), self._auto_col)

    def hideEvent(self, e):
        self.stop_autoscroll()
        if self._pan is not None:
            self._pan = None
            QApplication.restoreOverrideCursor()
        super().hideEvent(e)

    def visible(self, card):
        return self.board.matches(card, self.filter)

    def paintEvent(self, e):
        p = QPainter(self.viewport())
        paint_background(p, self.viewport().rect(), self.board.d.get("bg"), self.board.d["prefs"].get("bg_dim", 0))
        p.end()

    def rebuild(self):
        h = self.horizontalScrollBar().value()
        vs = {}
        old = self.widget()
        if old is not None:
            for col in old.columns():
                vs[col.lst["id"]] = col.scroll.verticalScrollBar().value()
        self.lane = Lane(self)
        self.lane.setObjectName("Lane")
        self.lane.setAttribute(Qt.WA_TranslucentBackground)
        for lst in self.board.lists():
            col = ListColumn(self, lst)
            self.lane.lay.addWidget(col, 0, Qt.AlignTop)
            if lst["id"] in vs:
                QTimer.singleShot(0, lambda c=col, v=vs[lst["id"]]: _safe(lambda: c.scroll.verticalScrollBar().setValue(v)))
        self.add_list = AddListColumn(self)
        self.lane.lay.addWidget(self.add_list, 0, Qt.AlignTop)
        self.lane.lay.addStretch(1)
        self.setWidget(self.lane)
        self.lane.setStyleSheet("#Lane { background: transparent; }")
        QTimer.singleShot(0, lambda: _safe(lambda: self.horizontalScrollBar().setValue(h)))
        if self.reopen_composer:
            lid, self.reopen_composer = self.reopen_composer, None
            col = self.column(lid)
            if col:
                QTimer.singleShot(0, lambda: _safe(col.open_composer))
        if self.reopen_list_composer:
            self.reopen_list_composer = False
            QTimer.singleShot(0, lambda: _safe(self.add_list.open))
        self._fit_heights()
        QTimer.singleShot(0, self._fit_heights)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit_heights()

    def _fit_heights(self):
        try:
            avail = self.viewport().height() - 24 - 110
        except RuntimeError:
            return
        if not hasattr(self, "lane"):
            return
        for col in self.lane.columns():
            content = sum(w.height() + 8 for w in col.stack.cards() if w.isVisible()) + 6
            col.scroll.setMaximumHeight(max(4, min(content, avail)))
            col.scroll.setMinimumHeight(max(0, min(content, avail)) if content > 6 else 0)

    def column(self, lid):
        return next((c for c in self.lane.columns() if c.lst["id"] == lid), None)

    def close_composers(self):
        for col in self.lane.columns():
            col.close_composer()
        self.add_list.close_composer()

    def clear_placeholders(self, except_col=None):
        for col in self.lane.columns():
            if col is not except_col:
                col.stack.hide_placeholder()

    def end_drag(self):
        try:
            self.clear_placeholders()
            self._fit_heights()
        except RuntimeError:
            pass

    def drop_card(self, cid, lid, before=None):
        """Drop `cid` into list `lid` right above card `before` (None = at the bottom)."""
        self.clear_placeholders()
        others = [c["id"] for c in self.board.cards(lid) if c["id"] != cid]
        idx = others.index(before) if before in others else None
        card = self.board.card(cid)
        if card and card["list"] == lid:
            cur = [c["id"] for c in self.board.cards(lid)]
            if (idx is None and cur and cur[-1] == cid) or (idx is not None and cur.index(cid) == idx):
                return  # dropped where it was
        self.board.move_card(cid, lid, idx)
        QTimer.singleShot(0, self.changed.emit)

    def autoscroll(self, pos):
        bar = self.horizontalScrollBar()
        if pos.x() < 40:
            bar.setValue(bar.value() - 18)
        elif pos.x() > self.viewport().width() - 40:
            bar.setValue(bar.value() + 18)

    def changed_later(self):
        QTimer.singleShot(400, self.changed.emit)

    def open_card(self, cid):
        self.open_card_requested.emit(cid)

    def card_menu(self, cid, pos):
        self.card_menu_requested.emit(cid, pos)

    def set_filter(self, flt):
        self.filter = flt
        self.rebuild()

    def wheelEvent(self, e):
        # vertical wheel over empty board space scrolls sideways (like Trello with ⇧)
        if abs(e.angleDelta().y()) > abs(e.angleDelta().x()):
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() - e.angleDelta().y())
            e.accept()
        else:
            super().wheelEvent(e)


