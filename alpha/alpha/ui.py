"""Main window: boards home, board page (views, filter, search, automation, menu), notifications, settings."""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QKeySequence, QPainter, QPainterPath, QShortcut
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
                               QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu,
                               QMessageBox, QPlainTextEdit, QPushButton, QRadioButton, QScrollArea, QSpinBox,
                               QStackedWidget, QSystemTrayIcon, QTabWidget, QToolButton, QVBoxLayout, QWidget)

from . import APP_NAME, LOGO, __version__, icons, theme
from .automation import Automation
from .automation_ui import AutomationDialog
from .board_view import BoardView
from .card_dialog import DatesPopup, LabelEditor, LabelsPopup, MembersPopup, MovePopup
from .exchange import TEMPLATES, export_csv, export_json, export_markdown, from_template, import_trello
from .model import Store, due_state, fmt_dt, parse_dt
from .paths import Settings, resource_path
from .views import CalendarView, DashboardView, TableView
from .widgets import avatar_pixmap, bg_is_light, color_swatch, font, paint_background

IS_MAC = sys.platform == "darwin"


def label(text, name=None, wrap=False):
    w = QLabel(text)
    if name:
        w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


def clear_layout(lay):
    """Remove everything from a layout right away (hidden now, deleted later)."""
    while lay.count():
        it = lay.takeAt(0)
        if it.widget():
            it.widget().hide()
            it.widget().deleteLater()
        elif it.layout():
            clear_layout(it.layout())


def ic(name, color=None):
    return icons.icon(name, color or theme.CURRENT["text"])


class BoardTile(QPushButton):
    def __init__(self, board=None, text=None, template=None):
        super().__init__()
        self.board = board
        self.text_ = text
        self.template = template
        self.setFixedSize(196, 104)
        self.setCursor(Qt.PointingHandCursor)
        self.hover = False

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()

    def paintEvent(self, _):
        c = theme.CURRENT
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r, 12, 12)
        p.setClipPath(path)
        if self.board is not None or self.template is not None:
            bg = self.board.d.get("bg") if self.board is not None else TEMPLATES[self.template]["bg"]
            paint_background(p, self.rect(), bg)
            if self.hover:
                p.fillRect(self.rect(), QColor(0, 0, 0, 40))
            light = bg_is_light(bg)
            p.setPen(QColor("#141413" if light else "#FFFFFF"))
            p.setFont(font(16, serif=True))
            name = self.board.name if self.board is not None else self.template
            p.drawText(r.adjusted(12, 10, -30, -10), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, name)
            p.setFont(font(11))
            if self.board is not None:
                n = len(self.board.cards())
                p.drawText(r.adjusted(12, 10, -12, -10), Qt.AlignLeft | Qt.AlignBottom,
                           f"{len(self.board.lists())} списков · {n} карточек")
                if self.board.d.get("starred"):
                    p.drawPixmap(int(r.right()) - 26, 10, icons.pixmap("star_on", size=36).scaled(
                        18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                p.drawText(r.adjusted(12, 10, -12, -10), Qt.AlignLeft | Qt.AlignBottom, "Шаблон")
        else:
            p.fillPath(path, QColor(c["hover"] if self.hover else c["panel"]))
            p.setPen(QColor(c["text"]))
            p.setFont(font(13))
            p.drawText(r, Qt.AlignCenter, self.text_ or "Создать доску")
        p.end()


class CreateBoardDialog(QDialog):
    def __init__(self, parent=None, template=None):
        super().__init__(parent)
        self.setWindowTitle("Создать доску")
        self.setFixedWidth(420)
        lay = QVBoxLayout(self)
        lay.addWidget(label("Создать доску", "Title"))
        self.preview = QLabel()
        self.preview.setFixedHeight(120)
        lay.addWidget(self.preview)
        lay.addWidget(label("Фон"))
        grid = QGridLayout()
        self.bg = TEMPLATES[template]["bg"] if template else "terracotta"
        self.bg_btns = {}
        for i, key in enumerate(theme.BACKGROUNDS):
            b = QToolButton()
            b.setIconSize(QSize(64, 40))
            b.clicked.connect(lambda _=False, k=key: self.pick(k))
            grid.addWidget(b, i // 5, i % 5)
            self.bg_btns[key] = b
        lay.addLayout(grid)
        lay.addWidget(label("Название доски"))
        self.name = QLineEdit(template or "")
        self.name.setPlaceholderText("Например, «Учёба» или «Проект»")
        lay.addWidget(self.name)
        lay.addWidget(label("Шаблон"))
        self.tpl = QComboBox()
        for t in TEMPLATES:
            self.tpl.addItem(t, t)
        self.tpl.setCurrentIndex(max(0, self.tpl.findData(template or "Пустая")))
        lay.addWidget(self.tpl)
        ok = QPushButton("Создать")
        ok.setObjectName("Accent")
        ok.clicked.connect(self.accept)
        lay.addWidget(ok)
        self.pick(self.bg)

    def pick(self, key):
        self.bg = key
        for k, b in self.bg_btns.items():
            b.setIcon(color_swatch(k, 64, 40, k == key))
        from PySide6.QtGui import QPixmap

        pix = QPixmap(760, 240)
        p = QPainter(pix)
        paint_background(p, pix.rect(), key)
        p.setRenderHint(QPainter.Antialiasing)
        for i, h in enumerate((150, 100, 180)):
            path = QPainterPath()
            path.addRoundedRect(QRectF(40 + i * 230, 30, 200, h), 12, 12)
            p.fillPath(path, QColor(255, 255, 255, 200))
        p.end()
        pix.setDevicePixelRatio(2)
        self.preview.setPixmap(pix)


class HomePage(QScrollArea):
    open_board = Signal(str)

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.rebuild()

    def rebuild(self):
        body = QWidget()
        body.setObjectName("Page")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(36, 28, 36, 28)
        lay.setSpacing(12)
        head = QHBoxLayout()
        head.addWidget(label("Ваши доски", "Title"))
        head.addStretch(1)
        imp = QPushButton("Импорт из Trello…")
        imp.setIcon(ic("import"))
        imp.clicked.connect(self.win.import_trello)
        head.addWidget(imp)
        lay.addLayout(head)
        lay.addWidget(label("Всё хранится на этом Mac. Перетаскивайте карточки, настраивайте автоматизацию — "
                            "как в Trello, только локально.", "Muted", wrap=True))
        store = self.win.store
        starred = [b for b in store.all() if b.d.get("starred")]
        if starred:
            lay.addWidget(label("ОТМЕЧЕННЫЕ", "Section"))
            lay.addLayout(self._grid(starred))
        lay.addWidget(label("ВСЕ ДОСКИ", "Section"))
        lay.addLayout(self._grid(store.all(), create=True))
        lay.addSpacing(8)
        lay.addWidget(label("ШАБЛОНЫ", "Section"))
        grid = QGridLayout()
        grid.setSpacing(14)
        for i, t in enumerate(TEMPLATES):
            tile = BoardTile(template=t)
            tile.clicked.connect(lambda _=False, t_=t: self.win.create_board(t_))
            grid.addWidget(tile, i // 5, i % 5)
        grid.setColumnStretch(5, 1)
        lay.addLayout(grid)
        closed = store.all(closed=True)
        if closed:
            lay.addSpacing(8)
            lay.addWidget(label("ЗАКРЫТЫЕ ДОСКИ", "Section"))
            for b in closed:
                row = QHBoxLayout()
                row.addWidget(label(b.name), 1)
                re = QPushButton("Открыть снова")
                re.clicked.connect(lambda _=False, b_=b: (b_.set_board(closed=False), self.win.save(b_),
                                                          self.rebuild()))
                row.addWidget(re)
                rm = QPushButton("Удалить навсегда")
                rm.clicked.connect(lambda _=False, b_=b: self.win.delete_board(b_))
                row.addWidget(rm)
                lay.addLayout(row)
        lay.addStretch(1)
        self.setWidget(body)

    def _grid(self, boards, create=False):
        grid = QGridLayout()
        grid.setSpacing(14)
        items = list(boards)
        n = 0
        for b in items:
            tile = BoardTile(board=b)
            tile.clicked.connect(lambda _=False, i=b.id: self.open_board.emit(i))
            tile.setContextMenuPolicy(Qt.CustomContextMenu)
            tile.customContextMenuRequested.connect(lambda pos, b_=b, t=tile: self.win.board_tile_menu(
                b_, t.mapToGlobal(pos)))
            grid.addWidget(tile, n // 5, n % 5)
            n += 1
        if create:
            tile = BoardTile(text="+  Создать доску")
            tile.clicked.connect(lambda: self.win.create_board())
            grid.addWidget(tile, n // 5, n % 5)
        grid.setColumnStretch(5, 1)
        return grid


class FilterPopup(QDialog):
    applied = Signal(dict)

    def __init__(self, board, flt, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.b = board
        frame = QFrame(self)
        frame.setObjectName("Popup")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.addWidget(label("Фильтр", "PopupTitle"))
        lay.addWidget(label("Ключевое слово", "Section"))
        self.text = QLineEdit(flt.get("text", ""))
        self.text.setPlaceholderText("Название, описание, метка, пункт чек-листа…")
        self.text.textChanged.connect(self.apply)
        lay.addWidget(self.text)
        lay.addWidget(label("Участники", "Section"))
        self.members = {}
        for m in board.d["members"]:
            cb = QCheckBox(m["name"])
            cb.setIcon(QIcon(avatar_pixmap(m, 18)))
            cb.setChecked(m["id"] in (flt.get("members") or ()))
            cb.toggled.connect(self.apply)
            lay.addWidget(cb)
            self.members[m["id"]] = cb
        lay.addWidget(label("Срок", "Section"))
        self.due = {}
        group = QButtonGroup(self)
        for key, text in (("", "Любой"), ("none", "Без срока"), ("overdue", "Просрочено"), ("today", "Сегодня"),
                          ("week", "На этой неделе")):
            rb = QRadioButton(text)
            rb.setChecked((flt.get("due") or "") == key)
            rb.toggled.connect(self.apply)
            group.addButton(rb)
            lay.addWidget(rb)
            self.due[key] = rb
        self.done = QComboBox()
        self.done.addItem("Все карточки", None)
        self.done.addItem("Только выполненные", True)
        self.done.addItem("Только невыполненные", False)
        self.done.setCurrentIndex(max(0, self.done.findData(flt.get("done"))))
        self.done.currentIndexChanged.connect(self.apply)
        lay.addWidget(self.done)
        lay.addWidget(label("Метки", "Section"))
        self.labels = {}
        for lb in board.d["labels"]:
            cb = QCheckBox(lb["name"] or theme.LABEL_COLORS.get(lb["color"], ("", lb["color"]))[1])
            cb.setIcon(QIcon(color_swatch(lb["color"], 28, 14)))
            cb.setIconSize(QSize(28, 14))
            cb.setChecked(lb["id"] in (flt.get("labels") or ()))
            cb.toggled.connect(self.apply)
            lay.addWidget(cb)
            self.labels[lb["id"]] = cb
        clear = QPushButton("Сбросить фильтр")
        clear.clicked.connect(self.clear)
        lay.addWidget(clear)
        self.setFixedWidth(300)

    def value(self):
        return {"text": self.text.text(), "members": {k for k, cb in self.members.items() if cb.isChecked()},
                "labels": {k for k, cb in self.labels.items() if cb.isChecked()},
                "due": next((k for k, rb in self.due.items() if rb.isChecked()), ""),
                "done": self.done.currentData()}

    def apply(self, *_):
        self.applied.emit(self.value())

    def clear(self):
        self.applied.emit({})
        self.close()


def filter_count(flt):
    if not flt:
        return 0
    return (bool(flt.get("text"))) + len(flt.get("members") or ()) + len(flt.get("labels") or ()) + \
        bool(flt.get("due")) + (flt.get("done") is not None)


class BoardPage(QWidget):
    def __init__(self, win, board):
        super().__init__()
        self.win = win
        self.b = board
        self.filter = {}
        self.view_key = board.d.get("prefs", {}).get("view", "board")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.bar = QFrame()
        self.bar.setObjectName("BoardBar")
        bl = QHBoxLayout(self.bar)
        bl.setContentsMargins(14, 8, 14, 8)
        bl.setSpacing(6)
        self.name_btn = QPushButton(board.name)
        self.name_btn.setObjectName("BoardName")
        self.name_btn.setStyleSheet(f"QPushButton {{ background: transparent; border: none; color: #FFFFFF;"
                                    f" font-family: {theme.SERIF}; font-size: 20px; padding: 2px 6px; }}"
                                    f"QPushButton:hover {{ background: rgba(255, 255, 255, 0.18); }}")
        self.name_btn.setToolTip("Переименовать доску")
        self.name_btn.clicked.connect(self.rename)
        bl.addWidget(self.name_btn)
        self.star = QToolButton()
        self.star.clicked.connect(self.toggle_star)
        bl.addWidget(self.star)
        bl.addSpacing(8)
        self.view_btns = {}
        group = QButtonGroup(self)
        for key, text, icon in (("board", "Доска", "board"), ("table", "Таблица", "table"),
                                ("calendar", "Календарь", "calendar"), ("dashboard", "Дашборд", "dashboard")):
            b = QPushButton(text)
            b.setProperty("full", text)
            b.setProperty("icon_name", icon)
            b.setToolTip(text)
            b.setIconSize(QSize(14, 14))
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self.set_view(k))
            group.addButton(b)
            bl.addWidget(b)
            self.view_btns[key] = b
        bl.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск карточек  ⌘F")
        self.search.setFixedWidth(170)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.search_changed)
        bl.addWidget(self.search)
        self.filter_btn = QPushButton("Фильтр")
        self.filter_btn.setIcon(ic("filter", "#FFFFFF"))
        self.filter_btn.setIconSize(QSize(14, 14))
        self.filter_btn.clicked.connect(self.open_filter)
        bl.addWidget(self.filter_btn)
        self.avatars = QHBoxLayout()
        self.avatars.setSpacing(-6)
        bl.addLayout(self.avatars)
        self.buttons_box = QHBoxLayout()
        self.buttons_box.setSpacing(4)
        bl.addLayout(self.buttons_box)
        auto = QPushButton("Автоматизация")
        auto.setToolTip("Правила, кнопки, расписание и сроки")
        auto.setIcon(ic("bolt", "#FFFFFF"))
        auto.setIconSize(QSize(14, 14))
        auto.clicked.connect(lambda: win.open_automation())
        bl.addWidget(auto)
        menu = QToolButton()
        menu.setIcon(ic("dots", "#FFFFFF"))
        menu.clicked.connect(lambda: self.board_menu(menu.mapToGlobal(menu.rect().bottomLeft())))
        bl.addWidget(menu)
        lay.addWidget(self.bar)
        self.stack = QStackedWidget()
        self.stack.setObjectName("BoardStack")
        lay.addWidget(self.stack, 1)
        self.board_view = BoardView(board, win.settings)
        self.board_view.changed.connect(win.board_changed)
        self.board_view.open_card_requested.connect(win.open_card)
        self.board_view.card_menu_requested.connect(self.card_menu)
        self.table = TableView(board)
        self.table.open_card_requested.connect(win.open_card)
        self.calendar = CalendarView(board)
        self.calendar.open_card_requested.connect(win.open_card)
        self.calendar.changed.connect(win.board_changed)
        self.dashboard = DashboardView(board)
        for w in (self.board_view, self.table, self.calendar, self.dashboard):
            self.stack.addWidget(w)
        self._shortcuts()
        self.refresh_bar()
        self.set_view(self.view_key)

    def paintEvent(self, _):
        p = QPainter(self)
        paint_background(p, self.rect(), self.b.d.get("bg"))
        p.end()

    # -- bar
    def refresh_bar(self):
        b = self.b
        self.name_btn.setText(b.name)
        self.star.setIcon(ic("star_on" if b.d.get("starred") else "star", "#FFFFFF"))
        self.star.setToolTip("Убрать из отмеченных" if b.d.get("starred") else "Отметить доску")
        n = filter_count(self.filter)
        self.filter_btn.setText(f"Фильтр · {n}" if n else "Фильтр")
        while self.avatars.count():
            it = self.avatars.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for m in b.d["members"][:4]:
            a = QToolButton()
            a.setIcon(QIcon(avatar_pixmap(m, 26)))
            a.setIconSize(QSize(26, 26))
            a.setToolTip(f"{m['name']} — показать только его карточки")
            a.clicked.connect(lambda _=False, i=m["id"]: self.only_member(i))
            self.avatars.addWidget(a)
        while self.buttons_box.count():
            it = self.buttons_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for r in b.d.get("rules", []):
            if r.get("kind") == "board_button" and r.get("enabled", True):
                name = r.get("name") or "Кнопка"
                btn = QPushButton(name if len(name) <= 14 else name[:13] + "…")
                btn.setToolTip(f"Кнопка доски: {name}")
                btn.setIcon(ic(r.get("icon") or "button", "#FFFFFF"))
                btn.setIconSize(QSize(14, 14))
                btn.clicked.connect(lambda _=False, r_=r: self.win.press_board_button(r_))
                self.buttons_box.addWidget(btn)

    def set_view(self, key):
        self.view_key = key
        self.b.d.setdefault("prefs", {})["view"] = key
        for k, btn in self.view_btns.items():   # only the active view shows its name
            btn.setChecked(k == key)
            btn.setText(btn.property("full") if k == key else "")
            btn.setIcon(ic(btn.property("icon_name"), "#141413" if k == key else "#FFFFFF"))
        w = {"board": self.board_view, "table": self.table, "calendar": self.calendar,
             "dashboard": self.dashboard}[key]
        self.stack.setCurrentWidget(w)
        self.refresh_views()

    def refresh_views(self):
        key = self.view_key
        if key == "board":
            self.board_view.filter = self.filter
            self.board_view.rebuild()
        elif key == "table":
            self.table.filter = self.filter
            self.table.rebuild()
        elif key == "calendar":
            self.calendar.set_filter(self.filter)
        else:
            self.dashboard.filter = self.filter
            self.dashboard.rebuild()
        self.update()

    def rename(self):
        name, ok = QInputDialog.getText(self, "Доска", "Название доски:", text=self.b.name)
        if ok and name.strip():
            self.b.set_board(name=name.strip())
            self.win.board_changed()

    def toggle_star(self):
        self.b.set_board(starred=not self.b.d.get("starred"))
        self.win.board_changed()

    # -- filter / search
    def search_changed(self, text):
        self.filter = dict(self.filter, text=text)
        if not text and filter_count(self.filter) == 0:
            self.filter = {}
        self.refresh_bar()
        self.refresh_views()

    def open_filter(self):
        p = FilterPopup(self.b, self.filter, self)
        p.applied.connect(self.apply_filter)
        p.adjustSize()
        pt = self.filter_btn.mapToGlobal(QPoint(self.filter_btn.width() - p.width(), self.filter_btn.height() + 4))
        p.move(pt)
        p.show()

    def apply_filter(self, flt):
        self.filter = flt
        self.search.blockSignals(True)
        self.search.setText(flt.get("text", ""))
        self.search.blockSignals(False)
        self.refresh_bar()
        self.refresh_views()

    def only_member(self, mid):
        cur = set(self.filter.get("members") or ())
        self.apply_filter(dict(self.filter, members=set() if cur == {mid} else {mid}))

    # -- shortcuts (Trello-like)
    def _shortcuts(self):
        def sc(keys, fn):
            s = QShortcut(QKeySequence(keys), self)
            s.setContext(Qt.WidgetWithChildrenShortcut)
            s.activated.connect(fn)

        sc("N", self.new_card)
        sc("F", self.open_filter)
        sc("Q", lambda: self.only_member("me"))
        sc("Ctrl+F", lambda: (self.search.setFocus(), self.search.selectAll()))
        sc("/", lambda: (self.search.setFocus(), self.search.selectAll()))
        sc("Return", lambda: self._hovered(lambda cid: self.win.open_card(cid)))
        sc("C", lambda: self._hovered(lambda cid: (self.b.update_card(cid, closed=True), self.win.board_changed())))
        sc("Space", lambda: self._hovered(lambda cid: (self.b.toggle_member(cid, "me"), self.win.board_changed())))
        sc("D", lambda: self._hovered(lambda cid: DatesPopup(self.b, cid, self, self.win.board_changed).show_at(
            QCursorPos())))
        sc("L", lambda: self._hovered(lambda cid: LabelsPopup(self.b, cid, self, self.win.board_changed).show_at(
            QCursorPos())))
        sc("Escape", lambda: self.apply_filter({}) if self.filter else self.board_view.close_composers())
        for i in range(1, 10):
            sc(str(i), lambda k=i: self._hovered(lambda cid: self._label_n(cid, k)))

    def _label_n(self, cid, k):
        labels = self.b.d["labels"]
        if k <= len(labels):
            self.b.toggle_label(cid, labels[k - 1]["id"])
            self.win.board_changed()

    def _hovered(self, fn):
        cid = self.board_view.hovered if self.view_key == "board" else None
        if cid and self.b.card(cid):
            fn(cid)

    def new_card(self):
        if self.view_key != "board":
            self.set_view("board")
        cid = self.board_view.hovered
        lid = self.b.card(cid)["list"] if cid and self.b.card(cid) else (self.b.lists()[0]["id"] if self.b.lists()
                                                                         else None)
        col = self.board_view.column(lid) if lid else None
        if col:
            col.open_composer()
        else:
            self.board_view.add_list.open()

    # -- menus
    def card_menu(self, cid, pos):
        b = self.b
        m = QMenu(self)
        m.addAction(ic("eye"), "Открыть карточку", lambda: self.win.open_card(cid))
        m.addAction(ic("label"), "Изменить метки", lambda: LabelsPopup(b, cid, self, self.win.board_changed).show_at(pos))
        m.addAction(ic("member"), "Участники", lambda: MembersPopup(b, cid, self, self.win.board_changed).show_at(pos))
        m.addAction(ic("clock"), "Даты", lambda: DatesPopup(b, cid, self, self.win.board_changed).show_at(pos))
        m.addAction(ic("move"), "Переместить", lambda: MovePopup(self.win.store, b, cid, self,
                                                                self.win.board_changed).show_at(pos))
        m.addAction(ic("copy"), "Копировать", lambda: MovePopup(self.win.store, b, cid, self, self.win.board_changed,
                                                               copy=True).show_at(pos))
        card = b.card(cid)
        m.addAction(ic("check"), "Снять отметку выполнения" if card.get("due_done") else "Отметить выполненной",
                    lambda: (b.update_card(cid, due_done=not card.get("due_done")), self.win.board_changed()))
        buttons = [r for r in b.d.get("rules", []) if r.get("kind") == "card_button" and r.get("enabled", True)]
        if buttons:
            sub = m.addMenu(ic("button"), "Кнопки")
            for r in buttons:
                sub.addAction(ic(r.get("icon") or "button"), r.get("name") or "Кнопка",
                              lambda r_=r: (self.win.automation.press_card_button(b, r_, cid),
                                            self.win.board_changed()))
        m.addSeparator()
        m.addAction(ic("archive"), "Архивировать", lambda: (b.update_card(cid, closed=True), self.win.board_changed()))
        m.exec(pos)

    def board_menu(self, pos):
        b = self.b
        m = QMenu(self)
        m.addAction(ic("desc"), "О доске…", self.about_board)
        m.addAction(ic("cover"), "Сменить фон…", self.change_bg)
        m.addAction(ic("label"), "Метки…", self.manage_labels)
        m.addAction(ic("members"), "Участники…", self.manage_members)
        m.addAction(ic("field"), "Пользовательские поля…", self.manage_fields)
        m.addAction(ic("archive"), "Архив…", self.archive)
        m.addAction(ic("list"), "Активность…", self.activity)
        m.addSeparator()
        m.addAction(ic("check"), "Скрывать выполненные карточки" if not b.d["prefs"].get("hide_done") else
                    "Показывать выполненные карточки", self.toggle_hide_done)
        m.addAction(ic("copy"), "Копировать доску…", lambda: self.win.copy_board(b))
        m.addAction(ic("template"), "Убрать из шаблонов" if b.d.get("template") else "Сделать шаблоном",
                    lambda: (b.set_board(template=not b.d.get("template")), self.win.board_changed()))
        ex = m.addMenu(ic("export"), "Экспорт")
        ex.addAction("JSON (Альфа)", lambda: self.win.export(b, "json"))
        ex.addAction("CSV (таблица)", lambda: self.win.export(b, "csv"))
        ex.addAction("Markdown", lambda: self.win.export(b, "md"))
        m.addSeparator()
        m.addAction(ic("close"), "Закрыть доску", lambda: self.win.close_board(b))
        m.exec(pos)

    def toggle_hide_done(self):
        prefs = self.b.d["prefs"]
        prefs["hide_done"] = not prefs.get("hide_done")
        self.b.dirty = True
        self.apply_filter(dict(self.filter, done=False) if prefs["hide_done"] else
                          {k: v for k, v in self.filter.items() if k != "done"})

    def about_board(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("О доске")
        lay = QVBoxLayout(dlg)
        lay.addWidget(label(self.b.name, "Title"))
        lay.addWidget(label(f"Создана {fmt_dt(self.b.d.get('created'))}", "Hint"))
        ed = QPlainTextEdit(self.b.d.get("desc", ""))
        ed.setPlaceholderText("Опишите, для чего эта доска…")
        lay.addWidget(ed)
        ok = QPushButton("Сохранить")
        ok.setObjectName("Accent")
        ok.clicked.connect(lambda: (self.b.set_board(desc=ed.toPlainText()), self.win.board_changed(), dlg.accept()))
        lay.addWidget(ok)
        dlg.resize(480, 360)
        dlg.exec()

    def change_bg(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Фон доски")
        lay = QVBoxLayout(dlg)
        lay.addWidget(label("Фон доски", "H2"))
        grid = QGridLayout()
        for i, key in enumerate(list(theme.BACKGROUNDS) + list(theme.LABEL_COLORS)):
            b = QToolButton()
            b.setIconSize(QSize(72, 46))
            color = key if key in theme.BACKGROUNDS else theme.label_hex(key)
            b.setIcon(color_swatch(key, 72, 46, self.b.d.get("bg") == color))
            b.clicked.connect(lambda _=False, c=color: (self.b.set_board(bg=c), self.win.board_changed(),
                                                        dlg.accept()))
            grid.addWidget(b, i // 5, i % 5)
        lay.addLayout(grid)
        img = QPushButton("Своя картинка…")

        def pick():
            path, _ = QFileDialog.getOpenFileName(dlg, "Картинка для фона", "", "Картинки (*.png *.jpg *.jpeg *.webp)")
            if path:
                self.b.set_board(bg=path)
                self.win.board_changed()
                dlg.accept()

        img.clicked.connect(pick)
        lay.addWidget(img)
        dlg.exec()

    def manage_labels(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Метки")
        lay = QVBoxLayout(dlg)
        lay.addWidget(label("Метки доски", "H2"))
        box = QVBoxLayout()
        lay.addLayout(box)

        def fill():
            while box.count():
                it = box.takeAt(0)
                if it.widget():
                    it.widget().deleteLater()
            for lb in self.b.d["labels"]:
                n = sum(1 for c in self.b.cards() if lb["id"] in c["labels"])
                btn = QPushButton(f"{lb['name'] or theme.LABEL_COLORS.get(lb['color'], ('', ''))[1]}  ·  {n}")
                btn.setIcon(QIcon(color_swatch(lb["color"], 36, 18)))
                btn.setIconSize(QSize(36, 18))
                btn.setStyleSheet("text-align: left;")
                btn.clicked.connect(lambda _=False, l_=lb: (LabelEditor(self.b, l_, dlg).exec(), fill(),
                                                            self.win.board_changed()))
                box.addWidget(btn)

        fill()
        add = QPushButton("Создать метку")
        add.setObjectName("Accent")
        add.clicked.connect(lambda: (LabelEditor(self.b, None, dlg).exec(), fill(), self.win.board_changed()))
        lay.addWidget(add)
        dlg.resize(360, 420)
        dlg.exec()

    def manage_members(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Участники")
        lay = QVBoxLayout(dlg)
        lay.addWidget(label("Участники доски", "H2"))
        lay.addWidget(label("Альфа локальная: участники — это просто подписи (вы, друзья, команда), чтобы "
                            "распределять карточки и фильтровать.", "Hint", wrap=True))
        box = QVBoxLayout()
        lay.addLayout(box)

        def fill():
            while box.count():
                it = box.takeAt(0)
                if it.widget():
                    it.widget().deleteLater()
                elif it.layout():
                    while it.layout().count():
                        w = it.layout().takeAt(0).widget()
                        if w:
                            w.deleteLater()
            for m in self.b.d["members"]:
                row = QWidget()
                hl = QHBoxLayout(row)
                hl.setContentsMargins(0, 0, 0, 0)
                a = QLabel()
                a.setPixmap(avatar_pixmap(m, 26))
                hl.addWidget(a)
                hl.addWidget(label(m["name"]), 1)
                ren = QPushButton("Переименовать")
                ren.clicked.connect(lambda _=False, m_=m: rename(m_))
                hl.addWidget(ren)
                if m["id"] != "me":
                    rm = QPushButton("Удалить")
                    rm.clicked.connect(lambda _=False, m_=m: remove(m_))
                    hl.addWidget(rm)
                box.addWidget(row)

        def rename(m):
            name, ok = QInputDialog.getText(dlg, "Участник", "Имя:", text=m["name"])
            if ok and name.strip():
                from .model import initials

                self.b.touch()
                m.update(name=name.strip(), initials=initials(name.strip()))
                fill()
                self.win.board_changed()

        def remove(m):
            self.b.touch()
            self.b.d["members"] = [x for x in self.b.d["members"] if x["id"] != m["id"]]
            for c in self.b.d["cards"]:
                if m["id"] in c["members"]:
                    c["members"].remove(m["id"])
            fill()
            self.win.board_changed()

        fill()
        add = QPushButton("Добавить участника")
        add.setObjectName("Accent")

        def add_member():
            name, ok = QInputDialog.getText(dlg, "Участник", "Имя:")
            if ok and name.strip():
                colors = ["#5B8CC4", "#7BA05B", "#9B7BC4", "#E08A4A", "#5DAFC4", "#D97BA6", "#D6584B"]
                self.b.add_member(name.strip(), colors[len(self.b.d["members"]) % len(colors)])
                fill()
                self.win.board_changed()

        add.clicked.connect(add_member)
        lay.addWidget(add)
        dlg.resize(420, 380)
        dlg.exec()

    def manage_fields(self):
        from .card_dialog import FieldsPopup

        cards = self.b.cards()
        if not cards:
            QMessageBox.information(self, "Поля", "Сначала создайте хотя бы одну карточку.")
            return
        FieldsPopup(self.b, cards[0]["id"], self, self.win.board_changed).show_at(self.mapToGlobal(QPoint(
            self.width() - 340, 60)))

    def archive(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Архив")
        dlg.resize(520, 520)
        lay = QVBoxLayout(dlg)
        tabs = QTabWidget()
        lay.addWidget(tabs)

        def build():
            while tabs.count():
                tabs.removeTab(0)
            for kind in ("cards", "lists"):
                page = QScrollArea()
                page.setWidgetResizable(True)
                body = QWidget()
                v = QVBoxLayout(body)
                items = self.b.cards(closed=True) if kind == "cards" else self.b.lists(closed=True)
                if not items:
                    v.addWidget(label("В архиве пусто.", "Hint"))
                for it in items:
                    row = QHBoxLayout()
                    name = it.get("title") or it.get("name")
                    extra = ""
                    if kind == "cards":
                        lst = self.b.list(it["list"])
                        extra = f"  ·  {lst['name']}" if lst else ""
                    row.addWidget(label(name + extra, wrap=True), 1)
                    back = QPushButton("Вернуть")
                    if kind == "cards":
                        back.clicked.connect(lambda _=False, i=it["id"]: (self.b.update_card(i, closed=False),
                                                                          self.win.board_changed(), build()))
                        rm = QPushButton("Удалить")
                        rm.clicked.connect(lambda _=False, i=it["id"]: (self.b.delete_card(i), self.win.board_changed(),
                                                                        build()))
                        row.addWidget(back)
                        row.addWidget(rm)
                    else:
                        back.clicked.connect(lambda _=False, i=it["id"]: (self.b.set_list(i, closed=False),
                                                                          self.win.board_changed(), build()))
                        row.addWidget(back)
                    v.addLayout(row)
                v.addStretch(1)
                page.setWidget(body)
                tabs.addTab(page, "Карточки" if kind == "cards" else "Списки")

        build()
        dlg.exec()

    def activity(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Активность")
        dlg.resize(560, 600)
        lay = QVBoxLayout(dlg)
        lay.addWidget(label("Активность", "H2"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        v = QVBoxLayout(body)
        for a in self.b.d["activity"][:300]:
            v.addWidget(label(f"<b>{a.get('who', 'Я')}</b> {a['text']}  <span style='color:"
                              f"{theme.CURRENT['muted']}'>{fmt_dt(a['ts'])}</span>", wrap=True))
        v.addStretch(1)
        scroll.setWidget(body)
        lay.addWidget(scroll)
        dlg.exec()


def QCursorPos():
    from PySide6.QtGui import QCursor

    return QCursor.pos()


class NotificationsPage(QScrollArea):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)

    def items(self):
        hours = int(self.win.settings.get("soon_hours", 24))
        now = datetime.now()
        out = []
        for b in self.win.store.all():
            for c in b.cards():
                d = parse_dt(c.get("due"))
                if not d or c.get("due_done"):
                    continue
                if d < now or d - now <= timedelta(hours=hours):
                    out.append((d, b, c))
        return sorted(out, key=lambda x: x[0])

    def rebuild(self):
        body = QWidget()
        body.setObjectName("Page")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(36, 28, 36, 28)
        lay.setSpacing(10)
        lay.addWidget(label("Уведомления", "Title"))
        lay.addWidget(label(f"Карточки, у которых срок прошёл или наступит в ближайшие "
                            f"{self.win.settings.get('soon_hours', 24)} ч (по всем доскам).", "Muted", wrap=True))
        items = self.items()
        if not items:
            lay.addWidget(label("Всё спокойно — горящих сроков нет.", "Hint"))
        for d, b, c in items:
            row = QFrame()
            row.setObjectName("NoteRow")
            hl = QHBoxLayout(row)
            st = due_state(c)
            badge = label("Просрочено" if st == "overdue" else "Скоро", None)
            badge.setStyleSheet(f"background: {theme.CURRENT['overdue' if st == 'overdue' else 'due_soon']};"
                                f" color: {'#FFFFFF' if st == 'overdue' else '#141413'}; border-radius: 6px;"
                                f" padding: 2px 8px; font-size: 11px;")
            hl.addWidget(badge)
            lst = b.list(c["list"])
            hl.addWidget(label(f"<b>{c['title']}</b><br><span style='color:{theme.CURRENT['muted']}'>{b.name} · "
                               f"{lst['name'] if lst else ''} · срок {fmt_dt(c['due'])}</span>"), 1)
            done = QPushButton("Выполнено")
            done.clicked.connect(lambda _=False, b_=b, c_=c: (b_.update_card(c_["id"], due_done=True),
                                                              self.win.save(b_), self.rebuild()))
            hl.addWidget(done)
            op = QPushButton("Открыть")
            op.clicked.connect(lambda _=False, b_=b, c_=c: (self.win.open_board(b_.id), self.win.open_card(c_["id"])))
            hl.addWidget(op)
            lay.addWidget(row)
        lay.addSpacing(10)
        lay.addWidget(label("АВТОМАТИЗАЦИЯ НЕДАВНО", "Section"))
        log = []
        for b in self.win.store.all():
            for e in b.d.get("autolog", [])[:20]:
                log.append((e["ts"], b.name, e))
        for ts, bname, e in sorted(log, key=lambda x: x[0], reverse=True)[:25]:
            lay.addWidget(label(f"<span style='color:{theme.CURRENT['muted']}'>{fmt_dt(ts)} · {bname}</span>  "
                                f"{e['text']}" + (f" — <b>{e['card']}</b>" if e.get("card") else ""), wrap=True))
        lay.addStretch(1)
        self.setWidget(body)


class SettingsPage(QScrollArea):
    def __init__(self, win):
        super().__init__()
        self.win = win
        s = win.settings
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setObjectName("Page")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(36, 28, 36, 28)
        lay.setSpacing(10)
        lay.addWidget(label("Настройки", "Title"))

        def row(title, w):
            r = QHBoxLayout()
            t = label(title)
            t.setFixedWidth(240)
            r.addWidget(t)
            r.addWidget(w, 1)
            lay.addLayout(r)

        theme_box = QComboBox()
        for k, t in (("system", "Как в системе"), ("light", "Светлая"), ("dark", "Тёмная")):
            theme_box.addItem(t, k)
        theme_box.setCurrentIndex(max(0, theme_box.findData(s.get("theme"))))
        theme_box.currentIndexChanged.connect(lambda i: (s.update(theme=theme_box.itemData(i)), s.save(),
                                                         win.apply_theme()))
        row("Тема", theme_box)
        notify = QCheckBox("Показывать уведомления о сроках и напоминаниях")
        notify.setChecked(bool(s.get("notify", True)))
        notify.toggled.connect(lambda v: (s.update(notify=v), s.save()))
        lay.addWidget(notify)
        soon = QSpinBox()
        soon.setRange(1, 168)
        soon.setSuffix(" ч")
        soon.setValue(int(s.get("soon_hours", 24)))
        soon.valueChanged.connect(lambda v: (s.update(soon_hours=v), s.save()))
        row("«Скоро» — если до срока меньше", soon)
        compact = QCheckBox("Компактные карточки (без обложек)")
        compact.setChecked(bool(s.get("compact")))
        compact.toggled.connect(lambda v: (s.update(compact=v), s.save(), win.refresh_board()))
        lay.addWidget(compact)
        lay.addSpacing(10)
        lay.addWidget(label("ДАННЫЕ", "Section"))
        lay.addWidget(label(f"Доски хранятся в «{win.store.folder}» — по одному JSON-файлу на доску.", "Hint",
                            wrap=True))
        r = QHBoxLayout()
        op = QPushButton("Открыть папку")
        op.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(win.store.folder))))
        r.addWidget(op)
        bk = QPushButton("Резервная копия всех досок…")
        bk.clicked.connect(win.backup)
        r.addWidget(bk)
        imp = QPushButton("Импорт…")
        imp.clicked.connect(win.import_trello)
        r.addWidget(imp)
        r.addStretch(1)
        lay.addLayout(r)
        lay.addSpacing(10)
        lay.addWidget(label("ГОРЯЧИЕ КЛАВИШИ НА ДОСКЕ", "Section"))
        for k, t in (("N", "новая карточка (в списке под курсором)"), ("F", "фильтр"), ("⌘F или /", "поиск"),
                     ("Q", "только мои карточки"), ("Enter", "открыть карточку под курсором"),
                     ("Пробел", "назначить себя на карточку под курсором"), ("L / D", "метки / даты карточки"),
                     ("1–9", "переключить метку по номеру"), ("C", "архивировать карточку под курсором"),
                     ("⌘Z / ⇧⌘Z", "отменить / повторить"), ("Esc", "сбросить фильтр")):
            lay.addWidget(label(f"<b>{k}</b> — {t}"))
        lay.addStretch(1)
        lay.addWidget(label(f"{APP_NAME} {__version__}", "Hint"))
        self.setWidget(body)


class MainWindow(QMainWindow):
    def __init__(self, app, store=None, settings=None):
        super().__init__()
        self.app = app
        self.settings = settings or Settings()
        self.store = store or Store()
        self.automation = Automation()
        for b in self.store.all() + self.store.all(closed=True):
            self.automation.attach(b)
        self.current = None
        self.card_dialog = None
        self.setWindowTitle(APP_NAME)
        self.setObjectName("Main")
        self.resize(1320, 820)
        self.setMinimumSize(960, 600)
        self.apply_theme(rebuild=False)
        root = QWidget()
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        self.side = QFrame()
        self.side.setObjectName("Side")
        self.side.setFixedWidth(220)
        self.side_lay = QVBoxLayout(self.side)
        self.side_lay.setContentsMargins(12, 18, 12, 14)
        self.side_lay.setSpacing(3)
        h.addWidget(self.side)
        self.stack = QStackedWidget()
        h.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.home = HomePage(self)
        self.home.open_board.connect(self.open_board)
        self.notes = NotificationsPage(self)
        self.settings_page = SettingsPage(self)
        for w in (self.home, self.notes, self.settings_page):
            self.stack.addWidget(w)
        self.board_page = None
        self.build_side()
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(lambda: self.store.save())
        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start(30000)
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(QIcon(icons.pixmap("logo", size=64)), self)
            self.tray.setToolTip(APP_NAME)
            self.tray.activated.connect(lambda *_: (self.show(), self.raise_()))
            self.tray.show()
        for keys, fn in (("Ctrl+Z", self.undo), ("Ctrl+Shift+Z", self.redo), ("Ctrl+N", lambda: self.create_board()),
                         ("Ctrl+1", self.go_home)):
            s = QShortcut(QKeySequence(keys), self)
            s.activated.connect(fn)
        last = self.settings.get("last_board")
        if last and last in self.store.boards and not self.store.boards[last].d.get("closed"):
            self.open_board(last)
        else:
            self.go_home()
        QTimer.singleShot(1500, self.tick)

    # -- theme
    def apply_theme(self, rebuild=True):
        mode = self.settings.get("theme", "system")
        if mode == "system":
            try:
                dark = self.app.styleHints().colorScheme() == Qt.ColorScheme.Dark
            except Exception:
                dark = self.app.palette().window().color().lightness() < 128
        else:
            dark = mode == "dark"
        colors = theme.DARK if dark else theme.LIGHT
        theme.use(colors)
        self.app.setStyleSheet(theme.stylesheet(colors))
        if rebuild and hasattr(self, "home"):
            self.build_side()
            self.home.rebuild()
            self.refresh_board(full=True)

    # -- sidebar
    def build_side(self):
        clear_layout(self.side_lay)
        brand = QHBoxLayout()
        brand.addWidget(label(LOGO, "Gamma"))
        brand.addWidget(label(APP_NAME, "Logo"))
        brand.addStretch(1)
        self.side_lay.addLayout(brand)
        self.side_lay.addSpacing(12)
        self.nav = {}
        n_notes = len(self.notes.items()) if hasattr(self, "notes") else 0
        for key, text, icon, fn in (("home", "Доски", "board", self.go_home),
                                    ("notes", "Уведомления" + (f"  ·  {n_notes}" if n_notes else ""), "bell",
                                     self.go_notes),
                                    ("settings", "Настройки", "settings", self.go_settings)):
            b = QPushButton(text)
            b.setIcon(ic(icon))
            b.setIconSize(QSize(16, 16))
            b.setCheckable(True)
            b.clicked.connect(fn)
            self.side_lay.addWidget(b)
            self.nav[key] = b
        self.side_lay.addSpacing(12)
        starred = [b for b in self.store.all() if b.d.get("starred")]
        others = [b for b in self.store.all() if not b.d.get("starred")]
        for title, boards in (("ОТМЕЧЕННЫЕ", starred), ("ДОСКИ", others)):
            if not boards:
                continue
            self.side_lay.addWidget(label(title, "Section"))
            for b in boards[:12]:
                btn = QPushButton(b.name)
                btn.setIcon(QIcon(color_swatch(b.d.get("bg") if b.d.get("bg") in theme.BACKGROUNDS else "terracotta",
                                               22, 16)))
                btn.setIconSize(QSize(22, 16))
                btn.setCheckable(True)
                btn.setChecked(self.current is not None and self.current.id == b.id and self.stack.currentWidget() is
                               self.board_page)
                btn.clicked.connect(lambda _=False, i=b.id: self.open_board(i))
                self.side_lay.addWidget(btn)
            self.side_lay.addSpacing(8)
        new = QPushButton("+  Создать доску")
        new.clicked.connect(lambda: self.create_board())
        self.side_lay.addWidget(new)
        self.side_lay.addStretch(1)

    def _check_nav(self, key):
        for k, b in self.nav.items():
            b.setChecked(k == key)

    def go_home(self):
        self.home.rebuild()
        self.stack.setCurrentWidget(self.home)
        self.build_side()
        self._check_nav("home")

    def go_notes(self):
        self.notes.rebuild()
        self.stack.setCurrentWidget(self.notes)
        self._check_nav("notes")

    def go_settings(self):
        self.stack.setCurrentWidget(self.settings_page)
        self._check_nav("settings")

    # -- boards
    def open_board(self, board_id):
        b = self.store.boards.get(board_id)
        if not b:
            return
        import time

        b.d["opened"] = time.time()
        b.dirty = True
        self.current = b
        self.automation.attach(b)
        if self.board_page is not None:
            self.stack.removeWidget(self.board_page)
            self.board_page.deleteLater()
        self.board_page = BoardPage(self, b)
        self.stack.addWidget(self.board_page)
        self.stack.setCurrentWidget(self.board_page)
        self.settings["last_board"] = b.id
        self.settings.save()
        self.setWindowTitle(f"{b.name} — {APP_NAME}")
        self.build_side()
        self._check_nav("")
        self.save_timer.start(500)

    def create_board(self, template=None):
        dlg = CreateBoardDialog(self, template)
        if not dlg.exec():
            return None
        data = from_template(dlg.tpl.currentData(), dlg.name.text().strip() or dlg.tpl.currentData())
        data["bg"] = dlg.bg
        b = self.store.add(data)
        self.automation.attach(b)
        self.open_board(b.id)
        return b

    def copy_board(self, b):
        name, ok = QInputDialog.getText(self, "Копировать доску", "Название:", text=b.name + " (копия)")
        if not ok:
            return
        keep = QMessageBox.question(self, "Копировать доску", "Скопировать и карточки?") == QMessageBox.Yes
        nb = self.store.copy_board(b, name.strip() or None, keep)
        self.automation.attach(nb)
        self.open_board(nb.id)

    def close_board(self, b):
        b.set_board(closed=True, starred=False)
        self.save(b)
        if self.current is b:
            self.current = None
        self.go_home()

    def delete_board(self, b):
        if QMessageBox.question(self, "Удалить доску", f"Удалить «{b.name}» навсегда?") == QMessageBox.Yes:
            self.store.delete(b.id)
            self.go_home()

    def board_tile_menu(self, b, pos):
        m = QMenu(self)
        m.addAction("Открыть", lambda: self.open_board(b.id))
        m.addAction("Убрать из отмеченных" if b.d.get("starred") else "Отметить",
                    lambda: (b.set_board(starred=not b.d.get("starred")), self.save(b), self.go_home()))
        m.addAction("Копировать…", lambda: self.copy_board(b))
        m.addAction("Закрыть доску", lambda: self.close_board(b))
        m.exec(pos)

    def save(self, b=None):
        self.store.save(b)

    def board_changed(self):
        """Any edit on the current board: save soon, refresh views, the open card and the side bar."""
        self.save_timer.start(300)
        self.refresh_board()
        if self.card_dialog is not None and self.card_dialog.isVisible():
            self.card_dialog.reload()

    def refresh_board(self, full=False):
        if self.board_page is None or self.current is None:
            return
        if full:
            self.open_board(self.current.id)
            return
        self.board_page.refresh_bar()
        self.board_page.refresh_views()
        self.setWindowTitle(f"{self.current.name} — {APP_NAME}")

    def open_card(self, cid):
        if self.current is None or not self.current.card(cid):
            return
        if self.card_dialog is not None:
            try:
                self.card_dialog.close()
            except RuntimeError:
                pass
        self.card_dialog = __import__("alpha.card_dialog", fromlist=["CardDialog"]).CardDialog(self, self.current, cid)
        self.card_dialog.changed.connect(self._card_changed)
        self.card_dialog.show()

    def _card_changed(self):
        self.save_timer.start(300)
        self.refresh_board()

    def open_automation(self, start="rule"):
        if self.current is None:
            return
        dlg = AutomationDialog(self, self.current, self.automation, start)
        dlg.changed.connect(self.board_changed)
        dlg.exec()
        self.board_changed()

    def press_board_button(self, rule):
        n = self.automation.press_board_button(self.current, rule)
        self.board_changed()
        self.statusBar().showMessage(f"«{rule.get('name')}»: готово" + (f", карточек: {n}" if n else ""), 4000)

    def open_url(self, url):
        QDesktopServices.openUrl(QUrl(url) if "://" in url else QUrl.fromLocalFile(url))

    def undo(self):
        if self.current and self.current.undo():
            self.board_changed()

    def redo(self):
        if self.current and self.current.redo():
            self.board_changed()

    # -- time: automation + reminders
    def tick(self):
        changed = False
        now = datetime.now()
        for b in self.store.all():
            if self.automation.tick(b, now):
                changed = True
            for c in b.cards():
                d = parse_dt(c.get("due"))
                if not d or c.get("due_done"):
                    continue
                rem = int(c.get("reminder") or 0)
                if rem and d - timedelta(minutes=rem) <= now < d and c.get("reminded") != c["due"]:
                    c["reminded"] = c["due"]
                    b.dirty = True
                    self.notify(f"Напоминание: {c['title']}", f"{b.name} · срок {fmt_dt(c['due'])}")
                if d <= now and c.get("overdue_told") != c["due"]:
                    c["overdue_told"] = c["due"]
                    b.dirty = True
                    self.notify(f"Срок прошёл: {c['title']}", f"{b.name} · {fmt_dt(c['due'])}")
        if changed and self.current is not None:
            self.refresh_board()
        self.store.save()
        if hasattr(self, "nav"):
            n = len(self.notes.items())
            self.nav["notes"].setText("Уведомления" + (f"  ·  {n}" if n else ""))

    def notify(self, title, text):
        if not self.settings.get("notify", True):
            return
        if self.tray is not None:
            self.tray.showMessage(title, text, QIcon(icons.pixmap("logo", size=64)), 8000)
        self.statusBar().showMessage(f"{title} — {text}", 8000)

    # -- import / export
    def import_trello(self):
        path, _ = QFileDialog.getOpenFileName(self, "Импорт доски", "", "Доска Trello или Альфы (*.json)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text("utf-8"))
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Импорт", f"Не удалось прочитать файл: {e}")
            return
        b = self.import_data(data)
        if b:
            self.open_board(b.id)

    def import_data(self, data):
        from .model import new_id

        if "idOrganization" in data or ("cards" in data and any("idList" in c for c in data.get("cards", []))):
            d = import_trello(data)
        elif "lists" in data and "cards" in data:
            d = data
            d["id"] = new_id() if d.get("id") in self.store.boards else d.get("id") or new_id()
        else:
            QMessageBox.warning(self, "Импорт", "Это не похоже на экспорт доски Trello или Альфы.")
            return None
        b = self.store.add(d)
        self.automation.attach(b)
        return b

    def export(self, b, kind):
        ext = {"json": "json", "csv": "csv", "md": "md"}[kind]
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт", str(Path.home() / f"{b.name}.{ext}"))
        if not path:
            return
        text = {"json": export_json, "csv": export_csv, "md": export_markdown}[kind](b)
        Path(path).write_text(text, "utf-8-sig" if kind == "csv" else "utf-8")
        self.statusBar().showMessage(f"Сохранено: {path}", 5000)

    def backup(self):
        import zipfile

        path, _ = QFileDialog.getSaveFileName(self, "Резервная копия", str(Path.home() / "Альфа — доски.zip"))
        if not path:
            return
        self.store.save()
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in self.store.folder.glob("*.json"):
                z.write(f, f.name)
        self.statusBar().showMessage(f"Копия сохранена: {path}", 5000)

    def closeEvent(self, e):
        self.store.save()
        self.settings.save()
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("Lotus")
    icon_file = resource_path("assets", "icon.png")
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))
    store = Store()
    if not store.boards:
        store.add(from_template("Канбан", "Добро пожаловать"))
    win = MainWindow(app, store)
    try:
        app.styleHints().colorSchemeChanged.connect(lambda *_: win.apply_theme())
    except Exception:
        pass
    win.show()
    return app.exec()


