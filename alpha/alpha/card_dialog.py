"""The back of a card: title, list, members, labels, dates, custom fields, description (Markdown), attachments,
checklists, comments and activity; sidebar with «Добавить на карточку», automation buttons and actions.
Popups: labels, members, dates, move, copy, cover, checklist, fields."""
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, QDateTime, QSize, Qt, QTime, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QApplication, QCalendarWidget, QCheckBox, QComboBox, QDateTimeEdit, QDialog,
                               QFileDialog, QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSpinBox, QToolButton,
                               QVBoxLayout, QWidget)

from . import icons, theme
from .board_view import Composer
from .model import FIELD_TYPES, due_state, fmt_dt, parse_dt
from .widgets import IMAGE_EXT, Popup, avatar_pixmap, color_swatch, label_text_color


def _lbl(text, name=None, wrap=False):
    w = QLabel(text)
    if name:
        w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


def _icon(name):
    return icons.icon(name, theme.CURRENT["text"])


def _section(title, icon):
    row = QHBoxLayout()
    ic = QLabel()
    ic.setPixmap(icons.pixmap(icon, theme.CURRENT["text"], size=36))
    ic.setFixedSize(18, 18)
    ic.setScaledContents(True)
    row.addWidget(ic)
    row.addWidget(_lbl(title, "H3"))
    row.addStretch(1)
    return row


def _side_button(text, icon, fn=None):
    b = QPushButton(text)
    b.setObjectName("SideBtn")
    b.setIcon(_icon(icon))
    b.setIconSize(QSize(14, 14))
    b.setCursor(Qt.PointingHandCursor)
    if fn is not None:
        b.clicked.connect(fn)
    return b


class LabelsPopup(Popup):
    def __init__(self, board, card_id, parent=None, on_change=None):
        super().__init__("Метки", parent, 300)
        self.b, self.cid, self.on_change = board, card_id, on_change
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск меток…")
        self.search.textChanged.connect(self.fill)
        self.body.addWidget(self.search)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(4)
        self.body.addLayout(self.rows)
        create = QPushButton("Создать новую метку")
        create.clicked.connect(lambda: self.edit_label(None))
        self.body.addWidget(create)
        self.fill()

    def fill(self):
        while self.rows.count():
            it = self.rows.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        card = self.b.card(self.cid)
        q = self.search.text().strip().lower()
        for lb in self.b.d["labels"]:
            name = lb["name"] or theme.LABEL_COLORS.get(lb["color"], ("", ""))[1]
            if q and q not in name.lower():
                continue
            row = QWidget()
            hl = QHBoxLayout(row)
            hl.setContentsMargins(0, 0, 0, 0)
            cb = QCheckBox()
            cb.setChecked(lb["id"] in card["labels"])
            cb.toggled.connect(lambda _=False, i=lb["id"]: self._toggle(i))
            hl.addWidget(cb)
            pill = QPushButton(lb["name"])
            pill.setObjectName("LabelPill")
            fg = label_text_color(lb["color"]).name()
            pill.setStyleSheet(f"QPushButton#LabelPill {{ background: {theme.label_hex(lb['color'])}; color: {fg};"
                               f" border: none; border-radius: 4px; padding: 6px 10px; text-align: left;"
                               f" font-weight: 600; }}")
            pill.clicked.connect(lambda _=False, i=lb["id"]: self._toggle(i))
            hl.addWidget(pill, 1)
            ed = QToolButton()
            ed.setIcon(_icon("desc"))
            ed.setToolTip("Изменить метку")
            ed.clicked.connect(lambda _=False, l_=lb: self.edit_label(l_))
            hl.addWidget(ed)
            self.rows.addWidget(row)

    def _toggle(self, label_id):
        self.b.toggle_label(self.cid, label_id)
        if self.on_change:
            self.on_change()
        QTimer.singleShot(0, self.fill)

    def edit_label(self, lb):
        dlg = LabelEditor(self.b, lb, self)
        if dlg.exec():
            if self.on_change:
                self.on_change()
            self.fill()


class LabelEditor(QDialog):
    def __init__(self, board, lb, parent=None):
        super().__init__(parent)
        self.b, self.lb = board, lb
        self.setWindowTitle("Метка" if lb else "Новая метка")
        lay = QVBoxLayout(self)
        lay.addWidget(_lbl("Название"))
        self.name = QLineEdit(lb["name"] if lb else "")
        lay.addWidget(self.name)
        lay.addWidget(_lbl("Цвет"))
        grid = QGridLayout()
        self.color = lb["color"] if lb else "green"
        self.btns = {}
        for i, key in enumerate(theme.LABEL_COLORS):
            b = QToolButton()
            b.setIconSize(QSize(46, 28))
            b.clicked.connect(lambda _=False, k=key: self.pick(k))
            grid.addWidget(b, i // 5, i % 5)
            self.btns[key] = b
        lay.addLayout(grid)
        self.pick(self.color)
        row = QHBoxLayout()
        ok = QPushButton("Сохранить" if lb else "Создать")
        ok.setObjectName("Accent")
        ok.clicked.connect(self.save)
        row.addWidget(ok)
        if lb:
            rm = QPushButton("Удалить")
            rm.clicked.connect(self.remove)
            row.addWidget(rm)
        row.addStretch(1)
        lay.addLayout(row)

    def pick(self, key):
        self.color = key
        for k, b in self.btns.items():
            b.setIcon(color_swatch(k, 46, 28, k == key))

    def save(self):
        if self.lb:
            self.b.touch()
            self.lb.update(name=self.name.text().strip(), color=self.color)
        else:
            self.b.add_label(self.name.text().strip(), self.color)
        self.accept()

    def remove(self):
        self.b.remove_label(self.lb["id"])
        self.accept()


class MembersPopup(Popup):
    def __init__(self, board, card_id, parent=None, on_change=None):
        super().__init__("Участники", parent, 280)
        self.b, self.cid, self.on_change = board, card_id, on_change
        self.rows = QVBoxLayout()
        self.body.addLayout(self.rows)
        add = QPushButton("Добавить участника доски…")
        add.clicked.connect(self.add)
        self.body.addWidget(add)
        self.fill()

    def fill(self):
        while self.rows.count():
            it = self.rows.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        card = self.b.card(self.cid)
        for m in self.b.d["members"]:
            b = QPushButton(m["name"])
            b.setObjectName("MemberRow")
            b.setIcon(avatar_pixmap(m, 22))
            b.setIconSize(QSize(22, 22))
            b.setCheckable(True)
            b.setChecked(m["id"] in card["members"])
            b.clicked.connect(lambda _=False, i=m["id"]: self._toggle(i))
            self.rows.addWidget(b)

    def _toggle(self, mid):
        self.b.toggle_member(self.cid, mid)
        if self.on_change:
            self.on_change()
        QTimer.singleShot(0, self.fill)

    def add(self):
        name, ok = QInputDialog.getText(self, "Участник", "Имя участника:")
        if ok and name.strip():
            colors = ["#5B8CC4", "#7BA05B", "#9B7BC4", "#E08A4A", "#5DAFC4", "#D97BA6", "#D6584B"]
            self.b.add_member(name.strip(), colors[len(self.b.d["members"]) % len(colors)])
            self.fill()


class DatesPopup(Popup):
    def __init__(self, board, card_id, parent=None, on_change=None):
        super().__init__("Даты", parent, 320)
        self.b, self.cid, self.on_change = board, card_id, on_change
        card = board.card(card_id)
        self.cal = QCalendarWidget()
        self.cal.setGridVisible(False)
        self.cal.setFirstDayOfWeek(Qt.Monday)
        self.cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.cal.clicked.connect(self._picked)
        self.body.addWidget(self.cal)
        due = parse_dt(card.get("due")) or (datetime.now() + timedelta(days=1)).replace(hour=18, minute=0)
        start = parse_dt(card.get("start")) or datetime.now()
        self.use_start = QCheckBox("Начало")
        self.use_start.setChecked(bool(card.get("start")))
        self.start = QDateTimeEdit(QDateTime(QDate(start.year, start.month, start.day), QTime(0, 0)))
        self.start.setDisplayFormat("dd.MM.yyyy")
        self.start.setCalendarPopup(True)
        self.use_due = QCheckBox("Срок")
        self.use_due.setChecked(bool(card.get("due")) or not card.get("start"))
        self.due = QDateTimeEdit(QDateTime(QDate(due.year, due.month, due.day), QTime(due.hour, due.minute)))
        self.due.setDisplayFormat("dd.MM.yyyy  HH:mm")
        self.due.setCalendarPopup(True)
        grid = QGridLayout()
        grid.addWidget(self.use_start, 0, 0)
        grid.addWidget(self.start, 0, 1)
        grid.addWidget(self.use_due, 1, 0)
        grid.addWidget(self.due, 1, 1)
        self.body.addLayout(grid)
        self.reminder = QComboBox()
        for minutes, text in ((0, "Без напоминания"), (5, "За 5 минут"), (60, "За час"), (1440, "За день"),
                              (2880, "За 2 дня")):
            self.reminder.addItem(text, minutes)
        self.reminder.setCurrentIndex(max(0, self.reminder.findData(int(card.get("reminder") or 0))))
        self.body.addWidget(self.reminder)
        save = QPushButton("Сохранить")
        save.setObjectName("Accent")
        save.clicked.connect(self.save)
        self.body.addWidget(save)
        rm = QPushButton("Удалить даты")
        rm.clicked.connect(self.remove)
        self.body.addWidget(rm)
        self.cal.setSelectedDate(QDate(due.year, due.month, due.day))

    def _picked(self, d):
        t = self.due.time()
        self.due.setDateTime(QDateTime(d, t))
        self.use_due.setChecked(True)

    def save(self):
        due = self.due.dateTime().toString("yyyy-MM-ddTHH:mm") if self.use_due.isChecked() else ""
        start = self.start.dateTime().toString("yyyy-MM-ddT00:00") if self.use_start.isChecked() else ""
        self.b.update_card(self.cid, due=due, start=start, reminder=int(self.reminder.currentData() or 0))
        if self.on_change:
            self.on_change()
        self.close()

    def remove(self):
        self.b.update_card(self.cid, due="", start="", due_done=False)
        if self.on_change:
            self.on_change()
        self.close()


class MovePopup(Popup):
    def __init__(self, store, board, card_id, parent=None, on_change=None, copy=False):
        super().__init__("Копировать карточку" if copy else "Переместить карточку", parent, 300)
        self.store, self.b, self.cid, self.on_change, self.copy = store, board, card_id, on_change, copy
        card = board.card(card_id)
        if copy:
            self.body.addWidget(_lbl("Название"))
            self.title = QPlainTextEdit(card["title"])
            self.title.setFixedHeight(56)
            self.body.addWidget(self.title)
            self.keep = {}
            for key, text in (("checklists", "Чек-листы"), ("labels", "Метки"), ("members", "Участники"),
                              ("attachments", "Вложения"), ("desc", "Описание"), ("due", "Срок")):
                cb = QCheckBox(text)
                cb.setChecked(True)
                self.body.addWidget(cb)
                self.keep[key] = cb
        self.body.addWidget(_lbl("Доска"))
        self.board_box = QComboBox()
        for b in store.all():
            self.board_box.addItem(b.name, b.id)
        self.board_box.setCurrentIndex(max(0, self.board_box.findData(board.id)))
        self.board_box.currentIndexChanged.connect(self._lists)
        self.body.addWidget(self.board_box)
        row = QHBoxLayout()
        self.list_box = QComboBox()
        self.pos = QSpinBox()
        self.pos.setMinimum(1)
        row.addWidget(self.list_box, 1)
        row.addWidget(self.pos)
        self.body.addWidget(_lbl("Список и позиция"))
        self.body.addLayout(row)
        self.list_box.currentIndexChanged.connect(self._positions)
        go = QPushButton("Создать карточку" if copy else "Переместить")
        go.setObjectName("Accent")
        go.clicked.connect(self.go)
        self.body.addWidget(go)
        self._lists()
        i = self.list_box.findData(card["list"])
        if i >= 0 and self.board_box.currentData() == board.id:
            self.list_box.setCurrentIndex(i)
            idx = [c["id"] for c in board.cards(card["list"])].index(card_id) if not card.get("closed") else 0
            self.pos.setValue(idx + 1 + (1 if copy else 0))

    def target(self):
        return self.store.boards.get(self.board_box.currentData(), self.b)

    def _lists(self):
        tb = self.target()
        self.list_box.clear()
        for lst in tb.lists():
            self.list_box.addItem(lst["name"], lst["id"])
        self._positions()

    def _positions(self):
        tb = self.target()
        lid = self.list_box.currentData()
        n = len(tb.cards(lid)) if lid else 0
        self.pos.setMaximum(n + 1)
        self.pos.setValue(n + 1)

    def go(self):
        tb = self.target()
        lid = self.list_box.currentData()
        if not lid:
            return
        idx = self.pos.value() - 1
        if tb is self.b:
            if self.copy:
                keep = tuple(k for k, cb in self.keep.items() if cb.isChecked()) + ("fields",)
                self.b.copy_card(self.cid, lid, idx, self.title.toPlainText().strip() or None, keep)
            else:
                self.b.move_card(self.cid, lid, idx)
        else:
            import copy as _copy

            from .model import new_id, now_iso

            src = self.b.card(self.cid)
            c = _copy.deepcopy(src)
            c.update(id=new_id(), list=lid, labels=[], members=[m for m in src["members"] if tb.member(m)],
                     created=now_iso())
            if self.copy:
                c["title"] = self.title.toPlainText().strip() or src["title"]
            tb._begin()
            c["pos"] = tb._pos_at(tb.cards(lid), idx)
            tb.d["cards"].append(c)
            tb._end(f"{'скопировал(а)' if self.copy else 'перенёс(ла)'} «{c['title']}» с доски «{self.b.name}»",
                    "card_created", {"card": c["id"], "list": lid})
            if not self.copy:
                self.b.delete_card(self.cid)
            tb.dirty = True
        if self.on_change:
            self.on_change()
        self.close()


class CoverPopup(Popup):
    def __init__(self, board, card_id, parent=None, on_change=None):
        super().__init__("Обложка", parent, 300)
        self.b, self.cid, self.on_change = board, card_id, on_change
        card = board.card(card_id)
        self.body.addWidget(_lbl("Цвета", "Section"))
        grid = QGridLayout()
        for i, key in enumerate(theme.LABEL_COLORS):
            btn = QToolButton()
            btn.setIconSize(QSize(46, 30))
            btn.setIcon(color_swatch(key, 46, 30, (card.get("cover") or {}).get("color") == key))
            btn.clicked.connect(lambda _=False, k=key: self.set({"color": k, "size": "normal"}))
            grid.addWidget(btn, i // 5, i % 5)
        self.body.addLayout(grid)
        imgs = [a for a in card.get("attachments", []) if Path(a["url"]).suffix.lower() in IMAGE_EXT
                and Path(a["url"]).exists()]
        if imgs:
            self.body.addWidget(_lbl("Вложения", "Section"))
            row = QHBoxLayout()
            for a in imgs[:4]:
                btn = QToolButton()
                btn.setIconSize(QSize(60, 40))
                btn.setIcon(QPixmap(a["url"]).scaled(120, 80, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
                btn.clicked.connect(lambda _=False, i=a["id"]: self.set({"attachment": i, "size": "normal"}))
                row.addWidget(btn)
            row.addStretch(1)
            self.body.addLayout(row)
        up = QPushButton("Загрузить картинку…")
        up.clicked.connect(self.upload)
        self.body.addWidget(up)
        rm = QPushButton("Убрать обложку")
        rm.clicked.connect(lambda: self.set(None))
        self.body.addWidget(rm)

    def set(self, cover):
        self.b.update_card(self.cid, cover=cover, text=f"изменил(а) обложку «{self.b.card(self.cid)['title']}»")
        if self.on_change:
            self.on_change()
        self.close()

    def upload(self):
        path, _ = QFileDialog.getOpenFileName(self, "Картинка для обложки", "", "Картинки (*.png *.jpg *.jpeg *.gif "
                                                                               "*.webp *.bmp)")
        if path:
            att = self.b.add_attachment(self.cid, path)
            self.set({"attachment": att["id"], "size": "normal"})


class FieldsPopup(Popup):
    def __init__(self, board, card_id, parent=None, on_change=None):
        super().__init__("Пользовательские поля", parent, 320)
        self.b, self.cid, self.on_change = board, card_id, on_change
        for f in board.d["fields"]:
            row = QHBoxLayout()
            row.addWidget(_lbl(f"{f['name']} · {FIELD_TYPES.get(f['type'], f['type'])}"), 1)
            front = QCheckBox("на карточке")
            front.setChecked(f.get("on_front", True))
            front.toggled.connect(lambda v, f_=f: (self.b.touch(), f_.update(on_front=v), self._changed()))
            row.addWidget(front)
            rm = QToolButton()
            rm.setIcon(_icon("trash"))
            rm.clicked.connect(lambda _=False, f_=f: self._remove(f_))
            row.addWidget(rm)
            self.body.addLayout(row)
        self.body.addWidget(_lbl("Новое поле", "Section"))
        self.name = QLineEdit()
        self.name.setPlaceholderText("Название, например «Приоритет»")
        self.body.addWidget(self.name)
        self.kind = QComboBox()
        for k, v in FIELD_TYPES.items():
            self.kind.addItem(v, k)
        self.body.addWidget(self.kind)
        self.options = QLineEdit()
        self.options.setPlaceholderText("Варианты для списка через запятую")
        self.body.addWidget(self.options)
        add = QPushButton("Добавить поле")
        add.setObjectName("Accent")
        add.clicked.connect(self.add)
        self.body.addWidget(add)

    def _changed(self):
        if self.on_change:
            self.on_change()

    def _remove(self, f):
        self.b.touch()
        self.b.d["fields"] = [x for x in self.b.d["fields"] if x["id"] != f["id"]]
        self._changed()
        self.close()

    def add(self):
        if not self.name.text().strip():
            return
        opts = [x.strip() for x in self.options.text().split(",") if x.strip()]
        self.b.add_field(self.name.text().strip(), self.kind.currentData(), opts)
        self._changed()
        self.close()


class CardDialog(QDialog):
    changed = Signal()

    def __init__(self, window, board, card_id):
        super().__init__(window)
        self.win = window
        self.b = board
        self.cid = card_id
        self.setObjectName("CardDialog")
        self.setWindowTitle("Карточка")
        self.resize(820, 760)
        self.desc_editing = False
        self.show_details = False
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.lay.addWidget(self.scroll)
        self.reload()

    @property
    def card(self):
        return self.b.card(self.cid)

    def emit_changed(self):
        self.changed.emit()
        QTimer.singleShot(0, self.reload)

    def reload(self):
        card = self.card
        if card is None:
            self.close()
            return
        v = self.scroll.verticalScrollBar().value()
        body = QWidget()
        body.setObjectName("CardBody")
        outer = QVBoxLayout(body)
        outer.setContentsMargins(0, 0, 0, 20)
        outer.setSpacing(0)
        cover = card.get("cover") or {}
        if cover.get("color") or cover.get("attachment"):
            band = QLabel()
            band.setFixedHeight(110)
            if cover.get("color"):
                band.setStyleSheet(f"background: {theme.label_hex(cover['color'])};")
            else:
                att = next((a for a in card["attachments"] if a["id"] == cover["attachment"]), None)
                if att and Path(att["url"]).exists():
                    pix = QPixmap(att["url"])
                    band.setPixmap(pix.scaled(QSize(820, 110) * 2, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    band.setAlignment(Qt.AlignCenter)
                    band.setStyleSheet(f"background: {theme.CURRENT['panel']};")
            outer.addWidget(band)
        inner = QHBoxLayout()
        inner.setContentsMargins(24, 18, 18, 0)
        inner.setSpacing(18)
        outer.addLayout(inner)
        main = QVBoxLayout()
        main.setSpacing(12)
        inner.addLayout(main, 1)
        side = QVBoxLayout()
        side.setSpacing(5)
        side_w = QWidget()
        side_w.setFixedWidth(184)
        side_w.setLayout(side)
        inner.addWidget(side_w, 0, Qt.AlignTop)

        # title + list
        title = QPlainTextEdit(card["title"])
        title.setObjectName("CardTitleEdit")
        title.setFixedHeight(46)
        title.installEventFilter(self)
        self.title_edit = title
        main.addWidget(title)
        lst = self.b.list(card["list"])
        where = QPushButton(f"в списке «{lst['name'] if lst else '?'}»" + ("  ·  в архиве" if card.get("closed") else ""))
        where.setObjectName("Link")
        where.clicked.connect(lambda: MovePopup(self.win.store, self.b, self.cid, self, self.emit_changed).show_at(where))
        main.addWidget(where, 0, Qt.AlignLeft)

        # chips: members, labels, dates
        chips = QHBoxLayout()
        chips.setSpacing(18)
        if card["members"]:
            col = QVBoxLayout()
            col.addWidget(_lbl("УЧАСТНИКИ", "Section"))
            row = QHBoxLayout()
            row.setSpacing(4)
            for mid in card["members"]:
                m = self.b.member(mid)
                if m:
                    a = QLabel()
                    a.setPixmap(avatar_pixmap(m, 30))
                    a.setToolTip(m["name"])
                    row.addWidget(a)
            plus = QToolButton()
            plus.setIcon(_icon("plus"))
            plus.clicked.connect(lambda: MembersPopup(self.b, self.cid, self, self.emit_changed).show_at(plus))
            row.addWidget(plus)
            col.addLayout(row)
            chips.addLayout(col)
        if card["labels"]:
            col = QVBoxLayout()
            col.addWidget(_lbl("МЕТКИ", "Section"))
            row = QHBoxLayout()
            row.setSpacing(4)
            for lid in card["labels"]:
                lb = self.b.label(lid)
                if not lb:
                    continue
                pill = QPushButton(lb["name"] or " ")
                pill.setMinimumWidth(44)
                fg = label_text_color(lb["color"]).name()
                pill.setStyleSheet(f"background: {theme.label_hex(lb['color'])}; color: {fg}; border: none;"
                                   f" border-radius: 4px; padding: 6px 10px; font-weight: 600;")
                pill.clicked.connect(lambda: LabelsPopup(self.b, self.cid, self, self.emit_changed).show_at(
                    self.mapToGlobal(self.rect().center())))
                row.addWidget(pill)
            plus = QToolButton()
            plus.setIcon(_icon("plus"))
            plus.clicked.connect(lambda: LabelsPopup(self.b, self.cid, self, self.emit_changed).show_at(plus))
            row.addWidget(plus)
            col.addLayout(row)
            chips.addLayout(col)
        if card.get("due") or card.get("start"):
            col = QVBoxLayout()
            col.addWidget(_lbl("СРОК" if card.get("due") else "НАЧАЛО", "Section"))
            row = QHBoxLayout()
            if card.get("due"):
                done = QCheckBox()
                done.setChecked(bool(card.get("due_done")))
                done.toggled.connect(lambda v: (self.b.update_card(self.cid, due_done=v), self.emit_changed()))
                row.addWidget(done)
            text = (fmt_dt(card["start"], False) + " – " if card.get("start") else "") + (fmt_dt(card["due"]) if
                                                                                         card.get("due") else "")
            st = due_state(card)
            badge = {"done": "  Выполнено", "overdue": "  Просрочено", "soon": "  Скоро"}.get(st, "")
            dd = QPushButton(text + badge)
            dd.setObjectName("DueChip_" + (st or "later"))
            dd.clicked.connect(lambda: DatesPopup(self.b, self.cid, self, self.emit_changed).show_at(dd))
            row.addWidget(dd)
            col.addLayout(row)
            chips.addLayout(col)
        if card.get("votes"):
            col = QVBoxLayout()
            col.addWidget(_lbl("ГОЛОСА", "Section"))
            col.addWidget(_lbl(f"👍 {card['votes']}"))
            chips.addLayout(col)
        chips.addStretch(1)
        main.addLayout(chips)

        # custom fields
        if self.b.d["fields"]:
            main.addLayout(_section("Пользовательские поля", "field"))
            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            for i, f in enumerate(self.b.d["fields"]):
                grid.addWidget(_lbl(f["name"], "Muted"), (i // 2) * 2, i % 2)
                grid.addWidget(self._field_editor(f), (i // 2) * 2 + 1, i % 2)
            main.addLayout(grid)

        # description
        head = _section("Описание", "desc")
        if card.get("desc") and not self.desc_editing:
            e = QPushButton("Изменить")
            e.clicked.connect(self._edit_desc)
            head.addWidget(e)
        main.addLayout(head)
        if self.desc_editing or not card.get("desc"):
            if self.desc_editing:
                ed = QPlainTextEdit(card.get("desc", ""))
                ed.setObjectName("DescEdit")
                ed.setMinimumHeight(150)
                ed.setPlaceholderText("Markdown: **жирный**, *курсив*, списки, [ссылки](https://…)")
                self.desc_box = ed
                main.addWidget(ed)
                row = QHBoxLayout()
                ok = QPushButton("Сохранить")
                ok.setObjectName("Accent")
                ok.clicked.connect(self._save_desc)
                row.addWidget(ok)
                cancel = QPushButton("Отмена")
                cancel.clicked.connect(self._cancel_desc)
                row.addWidget(cancel)
                row.addStretch(1)
                main.addLayout(row)
                QTimer.singleShot(0, ed.setFocus)
            else:
                ph = QPushButton("Добавить более подробное описание…")
                ph.setObjectName("DescPlaceholder")
                ph.clicked.connect(self._edit_desc)
                main.addWidget(ph)
        else:
            md = QLabel()
            md.setObjectName("DescView")
            md.setTextFormat(Qt.MarkdownText)
            md.setWordWrap(True)
            md.setOpenExternalLinks(True)
            md.setText(card["desc"])
            md.setTextInteractionFlags(Qt.TextBrowserInteraction)
            md.mouseDoubleClickEvent = lambda e: self._edit_desc()
            main.addWidget(md)

        # attachments
        if card["attachments"]:
            head = _section("Вложения", "attach")
            add = QPushButton("Добавить")
            add.clicked.connect(self.attach)
            head.addWidget(add)
            main.addLayout(head)
            for a in card["attachments"]:
                main.addWidget(self._attachment_row(a))

        # checklists
        for cl in card["checklists"]:
            main.addWidget(self._checklist(cl))

        # comments + activity
        head = _section("Действия", "comment")
        det = QPushButton("Скрыть подробности" if self.show_details else "Показать подробности")
        det.clicked.connect(self._toggle_details)
        head.addWidget(det)
        main.addLayout(head)
        cbox = QHBoxLayout()
        me = self.b.member("me") or {"initials": "Я", "color": "#D97757"}
        av = QLabel()
        av.setPixmap(avatar_pixmap(me, 28))
        cbox.addWidget(av, 0, Qt.AlignTop)
        self.comment_composer = Composer("Напишите комментарий…", "Сохранить")
        self.comment_composer.submitted.connect(self._comment)
        self.comment_composer.closed.connect(lambda: self.comment_composer.edit.setPlainText(""))
        cbox.addWidget(self.comment_composer, 1)
        main.addLayout(cbox)
        entries = [("comment", cm) for cm in card["comments"]]
        if self.show_details:
            entries += [("act", a) for a in self.b.d["activity"] if a.get("card") == self.cid]
            entries.sort(key=lambda e: e[1].get("ts", ""), reverse=True)
        for kind, e in entries[:60]:
            main.addWidget(self._activity_row(kind, e))
        main.addStretch(1)

        # sidebar
        side.addWidget(_lbl("ДОБАВИТЬ НА КАРТОЧКУ", "Section"))
        for text, icon, fn in (("Участники", "member", lambda: MembersPopup(self.b, self.cid, self, self.emit_changed)),
                               ("Метки", "label", lambda: LabelsPopup(self.b, self.cid, self, self.emit_changed)),
                               ("Чек-лист", "checklist", self._checklist_popup),
                               ("Даты", "clock", lambda: DatesPopup(self.b, self.cid, self, self.emit_changed)),
                               ("Вложение", "attach", None),
                               ("Обложка", "cover", lambda: CoverPopup(self.b, self.cid, self, self.emit_changed)),
                               ("Поля", "field", lambda: FieldsPopup(self.b, self.cid, self, self.emit_changed))):
            b = _side_button(text, icon)
            if fn is None:
                b.clicked.connect(self.attach)
            else:
                b.clicked.connect(lambda _=False, f=fn, b_=b: self._popup(f, b_))
            side.addWidget(b)
        buttons = [r for r in self.b.d.get("rules", []) if r.get("kind") == "card_button" and r.get("enabled", True)]
        side.addSpacing(8)
        side.addWidget(_lbl("КНОПКИ", "Section"))
        for r in buttons:
            side.addWidget(_side_button(r.get("name") or "Кнопка", r.get("icon") or "button",
                                        lambda _=False, r_=r: self._press(r_)))
        side.addWidget(_side_button("Добавить кнопку", "plus", lambda: self.win.open_automation("card_button")))
        side.addSpacing(8)
        side.addWidget(_lbl("ДЕЙСТВИЯ", "Section"))
        mv = _side_button("Переместить", "move")
        mv.clicked.connect(lambda: MovePopup(self.win.store, self.b, self.cid, self, self.emit_changed).show_at(mv))
        side.addWidget(mv)
        cp = _side_button("Копировать", "copy")
        cp.clicked.connect(lambda: MovePopup(self.win.store, self.b, self.cid, self, self.emit_changed,
                                             copy=True).show_at(cp))
        side.addWidget(cp)
        side.addWidget(_side_button("Голосовать", "vote", self._vote))
        side.addWidget(_side_button("Это шаблон ✓" if card.get("template") else "Сделать шаблоном", "template",
                                    lambda: (self.b.update_card(self.cid, template=not card.get("template"),
                                                                text=""), self.emit_changed())))
        side.addWidget(_side_button("Как Markdown", "export", self._copy_md))
        if card.get("closed"):
            side.addWidget(_side_button("Вернуть из архива", "undo",
                                        lambda: (self.b.update_card(self.cid, closed=False), self.emit_changed())))
            d = _side_button("Удалить", "trash", self._delete)
            d.setObjectName("DangerBtn")
            side.addWidget(d)
        else:
            side.addWidget(_side_button("Архивировать", "archive",
                                        lambda: (self.b.update_card(self.cid, closed=True), self.emit_changed())))
        side.addStretch(1)
        self.scroll.setWidget(body)
        QTimer.singleShot(0, lambda: self._restore_scroll(v))

    def _restore_scroll(self, v):
        try:
            self.scroll.verticalScrollBar().setValue(v)
        except (RuntimeError, AttributeError):   # the dialog was closed / rebuilt before the timer fired
            pass

    def _popup(self, factory, anchor):
        p = factory()
        if p is not None:
            p.show_at(anchor)

    # -- pieces
    def _field_editor(self, f):
        card = self.card
        val = (card.get("fields") or {}).get(f["id"])

        def setv(v):
            fields = dict(self.card.get("fields") or {})
            fields[f["id"]] = v
            self.b.update_card(self.cid, fields=fields, text=f"изменил(а) поле «{f['name']}»")
            self.changed.emit()

        if f["type"] == "checkbox":
            w = QCheckBox()
            w.setChecked(bool(val))
            w.toggled.connect(setv)
        elif f["type"] == "list":
            w = QComboBox()
            w.addItem("—", "")
            for o in f.get("options", []):
                w.addItem(o, o)
            w.setCurrentIndex(max(0, w.findData(val or "")))
            w.currentIndexChanged.connect(lambda i: setv(w.itemData(i)))
        elif f["type"] == "date":
            w = QDateTimeEdit()
            w.setCalendarPopup(True)
            w.setDisplayFormat("dd.MM.yyyy")
            d = parse_dt(val) if val else None
            w.setDate(QDate(d.year, d.month, d.day) if d else QDate.currentDate())
            w.dateChanged.connect(lambda d_: setv(d_.toString("yyyy-MM-ddT00:00")))
        else:
            w = QLineEdit("" if val in (None, False) else str(val))
            w.setPlaceholderText("Добавить…")
            w.editingFinished.connect(lambda: setv(w.text().strip()))
        return w

    def _attachment_row(self, a):
        row = QFrame()
        row.setObjectName("AttRow")
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 2, 0, 2)
        thumb = QLabel()
        thumb.setFixedSize(84, 56)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setObjectName("AttThumb")
        is_img = Path(a["url"]).suffix.lower() in IMAGE_EXT and Path(a["url"]).exists()
        if is_img:
            thumb.setPixmap(QPixmap(a["url"]).scaled(QSize(168, 112), Qt.KeepAspectRatioByExpanding,
                                                     Qt.SmoothTransformation).copy(0, 0, 168, 112))
            thumb.setScaledContents(True)
        else:
            ext = ("ссылка" if "://" in a["url"] else Path(a["url"]).suffix[1:].upper() or "файл")
            thumb.setText(ext)
        hl.addWidget(thumb)
        col = QVBoxLayout()
        name = QPushButton(a["name"])
        name.setObjectName("Link")
        name.clicked.connect(lambda: self.win.open_url(a["url"]))
        col.addWidget(name, 0, Qt.AlignLeft)
        col.addWidget(_lbl(f"Добавлено {fmt_dt(a.get('added'))}", "Hint"))
        acts = QHBoxLayout()
        if is_img:
            cv = QPushButton("Сделать обложкой")
            cv.setObjectName("Link")
            cv.clicked.connect(lambda: (self.b.update_card(self.cid, cover={"attachment": a["id"], "size": "normal"},
                                                           text=""), self.emit_changed()))
            acts.addWidget(cv)
        rm = QPushButton("Удалить")
        rm.setObjectName("Link")
        rm.clicked.connect(lambda: self._remove_attachment(a))
        acts.addWidget(rm)
        acts.addStretch(1)
        col.addLayout(acts)
        hl.addLayout(col, 1)
        return row

    def _remove_attachment(self, a):
        card = self.card
        cover = card.get("cover") or {}
        self.b.update_card(self.cid, attachments=[x for x in card["attachments"] if x["id"] != a["id"]],
                           cover=None if cover.get("attachment") == a["id"] else card.get("cover"),
                           text=f"удалил(а) вложение «{a['name']}»")
        self.emit_changed()

    def _checklist(self, cl):
        box = QFrame()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 4, 0, 4)
        v.setSpacing(4)
        head = _section(cl["name"], "checklist")
        hide = cl.get("hide_done", False)
        hb = QPushButton("Показать отмеченные" if hide else "Скрыть отмеченные")
        hb.clicked.connect(lambda: (self.b.touch(), cl.update(hide_done=not hide), self.emit_changed()))
        head.addWidget(hb)
        rm = QPushButton("Удалить")
        rm.clicked.connect(lambda: (self.b.remove_checklist(self.cid, cl["id"]), self.emit_changed()))
        head.addWidget(rm)
        v.addLayout(head)
        done = sum(1 for it in cl["items"] if it["done"])
        total = len(cl["items"])
        pr = QHBoxLayout()
        pct = int(100 * done / total) if total else 0
        pr.addWidget(_lbl(f"{pct}%", "Hint"))
        bar = QProgressBar()
        bar.setObjectName("Progress" + ("Done" if total and done == total else ""))
        bar.setRange(0, 100)
        bar.setValue(pct)
        bar.setTextVisible(False)
        bar.setFixedHeight(8)
        pr.addWidget(bar, 1)
        v.addLayout(pr)
        for it in cl["items"]:
            if hide and it["done"]:
                continue
            row = QHBoxLayout()
            cb = QCheckBox(it["text"])
            cb.setObjectName("ItemDone" if it["done"] else "Item")
            cb.setChecked(it["done"])
            cb.toggled.connect(lambda val, i=it["id"]: (self.b.set_item(self.cid, cl["id"], i, done=val),
                                                        self.emit_changed()))
            row.addWidget(cb, 1)
            if it.get("due"):
                row.addWidget(_lbl(fmt_dt(it["due"]), "Hint"))
            ed = QToolButton()
            ed.setIcon(_icon("desc"))
            ed.setToolTip("Изменить")
            ed.clicked.connect(lambda _=False, it_=it: self._edit_item(cl, it_))
            row.addWidget(ed)
            x = QToolButton()
            x.setIcon(_icon("close"))
            x.setToolTip("Удалить пункт")
            x.clicked.connect(lambda _=False, i=it["id"]: (self.b.remove_item(self.cid, cl["id"], i),
                                                           self.emit_changed()))
            row.addWidget(x)
            v.addLayout(row)
        comp = Composer("Добавить элемент…", "Добавить")
        comp.submitted.connect(lambda t: (self.b.add_item(self.cid, cl["id"], t), self.changed.emit(),
                                          self._reload_keep_item(cl["id"])))
        comp.closed.connect(lambda: comp.edit.setPlainText(""))
        v.addWidget(comp)
        return box

    def _reload_keep_item(self, clid):
        self.reload()

    def _edit_item(self, cl, it):
        text, ok = QInputDialog.getText(self, "Пункт чек-листа", "Текст:", text=it["text"])
        if ok and text.strip():
            self.b.set_item(self.cid, cl["id"], it["id"], text=text.strip())
            self.emit_changed()

    def _activity_row(self, kind, e):
        row = QFrame()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 4, 0, 4)
        who = e.get("who", "Я")
        m = next((x for x in self.b.d["members"] if x["name"] == who), None) or \
            {"initials": "⚡" if who == "Автоматизация" else who[:2], "color": "#9B7BC4" if who == "Автоматизация"
             else "#D97757"}
        av = QLabel()
        av.setPixmap(avatar_pixmap(m, 28))
        hl.addWidget(av, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        if kind == "comment":
            col.addWidget(_lbl(f"<b>{who}</b>  <span style='color:{theme.CURRENT['muted']}'>{fmt_dt(e['ts'])}</span>"))
            body = QLabel(e["text"])
            body.setObjectName("CommentBody")
            body.setWordWrap(True)
            body.setTextFormat(Qt.MarkdownText)
            col.addWidget(body)
            rm = QPushButton("Удалить")
            rm.setObjectName("Link")
            rm.clicked.connect(lambda: self._delete_comment(e))
            col.addWidget(rm, 0, Qt.AlignLeft)
        else:
            col.addWidget(_lbl(f"<b>{who}</b> {e['text']}", wrap=True))
            col.addWidget(_lbl(fmt_dt(e["ts"]), "Hint"))
        hl.addLayout(col, 1)
        return row

    # -- actions
    def eventFilter(self, obj, e):
        if obj is getattr(self, "title_edit", None):
            if e.type() == e.Type.KeyPress and e.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._save_title()
                return True
            if e.type() == e.Type.FocusOut:
                self._save_title()
        return False

    def _save_title(self):
        t = self.title_edit.toPlainText().strip().replace("\n", " ")
        if t and self.card and t != self.card["title"]:
            self.b.update_card(self.cid, title=t)
            self.changed.emit()

    def _edit_desc(self):
        self.desc_editing = True
        self.reload()

    def _save_desc(self):
        self.b.update_card(self.cid, desc=self.desc_box.toPlainText())
        self.desc_editing = False
        self.emit_changed()

    def _cancel_desc(self):
        self.desc_editing = False
        self.reload()

    def _toggle_details(self):
        self.show_details = not self.show_details
        self.reload()

    def _comment(self, text):
        self.b.add_comment(self.cid, text)
        self.emit_changed()

    def _delete_comment(self, cm):
        self.b.touch()
        self.card["comments"] = [x for x in self.card["comments"] if x["id"] != cm["id"]]
        self.emit_changed()

    def _checklist_popup(self):
        p = Popup("Добавить чек-лист", self, 280)
        p.body.addWidget(_lbl("Название"))
        name = QLineEdit("Чек-лист")
        p.body.addWidget(name)
        p.body.addWidget(_lbl("Скопировать пункты из"))
        src = QComboBox()
        src.addItem("(нет)", None)
        for c in self.b.cards():
            for cl in c["checklists"]:
                src.addItem(f"{c['title']} — {cl['name']}", (c["id"], cl["id"]))
        p.body.addWidget(src)
        ok = QPushButton("Добавить")
        ok.setObjectName("Accent")

        def add():
            items = []
            if src.currentData():
                cl = self.b.checklist(*src.currentData())
                items = [it["text"] for it in cl["items"]] if cl else []
            self.b.add_checklist(self.cid, name.text().strip() or "Чек-лист", items)
            p.close()
            self.emit_changed()

        ok.clicked.connect(add)
        p.body.addWidget(ok)
        return p

    def attach(self):
        p = Popup("Прикрепить", self, 300)
        f = QPushButton("Файл с компьютера…")

        def pick():
            paths, _ = QFileDialog.getOpenFileNames(self, "Прикрепить файлы")
            for path in paths:
                self.b.add_attachment(self.cid, path)
            p.close()
            if paths:
                self.emit_changed()

        f.clicked.connect(pick)
        p.body.addWidget(f)
        p.body.addWidget(_lbl("Ссылка"))
        url = QLineEdit()
        url.setPlaceholderText("https://…")
        p.body.addWidget(url)
        title = QLineEdit()
        title.setPlaceholderText("Текст ссылки (необязательно)")
        p.body.addWidget(title)
        ok = QPushButton("Прикрепить")
        ok.setObjectName("Accent")

        def add_url():
            u = url.text().strip()
            if u:
                if "://" not in u:
                    u = "https://" + u
                self.b.add_attachment(self.cid, u, title.text().strip() or None)
                p.close()
                self.emit_changed()

        ok.clicked.connect(add_url)
        p.body.addWidget(ok)
        p.show_at(self.mapToGlobal(self.rect().center()))

    def _vote(self):
        self.b.update_card(self.cid, votes=int(self.card.get("votes", 0)) + 1, text="")
        self.emit_changed()

    def _press(self, rule):
        self.win.automation.press_card_button(self.b, rule, self.cid)
        self.emit_changed()

    def _copy_md(self):
        c = self.card
        lines = [f"## {c['title']}", ""]
        if c.get("desc"):
            lines += [c["desc"], ""]
        for cl in c["checklists"]:
            lines.append(f"**{cl['name']}**")
            lines += [f"- [{'x' if it['done'] else ' '}] {it['text']}" for it in cl["items"]]
        QApplication.clipboard().setText("\n".join(lines))

    def _delete(self):
        self.b.delete_card(self.cid)
        self.changed.emit()
        self.close()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(e)

    def closeEvent(self, e):
        if hasattr(self, "title_edit"):
            try:
                self._save_title()
            except RuntimeError:
                pass
        super().closeEvent(e)
