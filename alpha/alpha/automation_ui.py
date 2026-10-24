"""Automation window: rules, scheduled and due-date commands, card / board buttons, ideas, run log; rule editor."""
from PySide6.QtCore import Qt, QTime, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSpinBox, QTimeEdit, QToolButton, QVBoxLayout, QWidget)

from . import automation as A
from . import icons, theme
from .model import fmt_dt

KINDS = [("rule", "Правила", "bolt", "Срабатывают на события: карточку переместили, отметили, добавили метку…"),
         ("schedule", "По расписанию", "calendar", "Выполняются каждый день, неделю или месяц."),
         ("due", "По срокам", "clock", "Срабатывают за / после / в момент срока карточки."),
         ("card_button", "Кнопки карточек", "button", "Появляются на обратной стороне каждой карточки."),
         ("board_button", "Кнопки доски", "board", "Кнопки в верхней панели доски.")]
ICON_CHOICES = ["bolt", "check", "play", "archive", "move", "label", "member", "clock", "star", "bell", "copy",
                "checklist", "comment", "vote"]


def _lbl(text, name=None, wrap=False):
    w = QLabel(text)
    if name:
        w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


class ParamEditor(QWidget):
    """One row: a type combo (trigger / condition / action) + its parameter widgets."""

    removed = Signal(object)

    def __init__(self, board, vocab, item, removable=True, extra_vocab=None):
        super().__init__()
        self.board = board
        self.vocab = dict(vocab)
        if extra_vocab:
            self.vocab.update(extra_vocab)
        self.item = dict(item)
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(6)
        self.kind = QComboBox()
        for key, (title, _) in self.vocab.items():
            self.kind.addItem(title, key)
        self.kind.setCurrentIndex(max(0, self.kind.findData(self.item.get("type"))))
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self.lay.addWidget(self.kind)
        self.params = QHBoxLayout()
        self.params.setSpacing(6)
        self.lay.addLayout(self.params, 1)
        if removable:
            rm = QToolButton()
            rm.setIcon(icons.icon("close", theme.CURRENT["text"]))
            rm.clicked.connect(lambda: self.removed.emit(self))
            self.lay.addWidget(rm)
        self.widgets = {}
        self._build()

    def _kind_changed(self):
        self.item = {"type": self.kind.currentData()}
        self._build()

    def _build(self):
        while self.params.count():
            it = self.params.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.widgets = {}
        key = self.kind.currentData()
        self.item["type"] = key
        for name, kind in self.vocab.get(key, ("", []))[1]:
            w = self._widget(name, kind)
            self.widgets[name] = (kind, w)
            if name == "from":
                self.params.addWidget(_lbl("из"))
            self.params.addWidget(w, 1)

    def _widget(self, name, kind):
        b = self.board
        v = self.item.get(name)
        base = kind.rstrip("?")
        if base == "list":
            w = QComboBox()
            if kind.endswith("?"):
                w.addItem("любой список", "")
            for lst in b.lists():
                w.addItem(lst["name"], lst["id"])
            w.setCurrentIndex(max(0, w.findData(v or "")))
        elif base == "label":
            w = QComboBox()
            for lb in b.d["labels"]:
                w.addItem(lb["name"] or theme.LABEL_COLORS.get(lb["color"], ("", lb["color"]))[1], lb["id"])
            w.setCurrentIndex(max(0, w.findData(v)))
        elif base == "member":
            w = QComboBox()
            for m in b.d["members"]:
                w.addItem(m["name"], m["id"])
            w.setCurrentIndex(max(0, w.findData(v)))
        elif base == "field":
            w = QComboBox()
            for f in b.d["fields"]:
                w.addItem(f["name"], f["id"])
            w.setCurrentIndex(max(0, w.findData(v)))
        elif base == "color":
            w = QComboBox()
            w.addItem("без обложки", "none")
            for key, (_, title) in theme.LABEL_COLORS.items():
                w.addItem(title, key)
            w.setCurrentIndex(max(0, w.findData(v or "red")))
        elif base == "where":
            w = QComboBox()
            w.addItem("вниз", "bottom")
            w.addItem("наверх", "top")
            w.setCurrentIndex(max(0, w.findData(v or "bottom")))
        elif base == "sortkey":
            w = QComboBox()
            for key, title in A.SORT_KEYS.items():
                w.addItem(title, key)
            w.setCurrentIndex(max(0, w.findData(v or "title")))
        elif base == "weekday":
            w = QComboBox()
            for i, d in enumerate(A.WEEKDAYS):
                w.addItem(d, i)
            w.setCurrentIndex(int(v or 0))
        elif base in ("int", "monthday"):
            w = QSpinBox()
            w.setRange(1 if base == "monthday" else 0, 31 if base == "monthday" else 365)
            w.setValue(int(v if v not in (None, "") else (1 if base == "monthday" else 1)))
            if name == "days":
                w.setSuffix(" дн.")
        elif base == "time":
            w = QTimeEdit(QTime.fromString(v or ("18:00" if name == "time" and self.item.get("type") == "set_due"
                                                 else "09:00"), "HH:mm"))
            w.setDisplayFormat("HH:mm")
        elif base == "items":
            w = QLineEdit(", ".join(v) if isinstance(v, list) else (v or ""))
            w.setPlaceholderText("пункты через запятую")
        else:
            w = QLineEdit(v or "")
            w.setPlaceholderText({"text": "текст ({title}, {list}, {date})", "title": "{title} — новое имя",
                                  "contains": "любой текст", "name": "название"}.get(name, ""))
        return w

    def value(self):
        out = {"type": self.kind.currentData()}
        for name, (kind, w) in self.widgets.items():
            if isinstance(w, QComboBox):
                out[name] = w.currentData()
            elif isinstance(w, QSpinBox):
                out[name] = w.value()
            elif isinstance(w, QTimeEdit):
                out[name] = w.time().toString("HH:mm")
            elif kind == "items":
                out[name] = [x.strip() for x in w.text().split(",") if x.strip()]
            else:
                out[name] = w.text().strip()
        return out


class RuleEditor(QDialog):
    def __init__(self, board, rule, parent=None):
        super().__init__(parent)
        self.board = board
        self.rule = rule
        kind = rule.get("kind", "rule")
        self.kind = kind
        self.setWindowTitle({"rule": "Правило", "schedule": "Команда по расписанию", "due": "Команда по сроку",
                             "card_button": "Кнопка карточки", "board_button": "Кнопка доски"}.get(kind, "Правило"))
        self.resize(760, 560)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.addWidget(_lbl(self.windowTitle(), "Title"))
        if kind in ("card_button", "board_button"):
            row = QHBoxLayout()
            row.addWidget(_lbl("Название кнопки"))
            self.name = QLineEdit(rule.get("name", ""))
            row.addWidget(self.name, 1)
            self.icon = QComboBox()
            for ic in ICON_CHOICES:
                self.icon.addItem(icons.icon(ic, theme.CURRENT["text"]), "", ic)
            self.icon.setCurrentIndex(max(0, self.icon.findData(rule.get("icon") or "bolt")))
            row.addWidget(self.icon)
            lay.addLayout(row)
        # trigger
        tr = rule.get("trigger", {})
        if kind == "rule":
            lay.addWidget(_lbl("КОГДА", "Section"))
            self.trigger = ParamEditor(board, A.TRIGGERS, tr or {"type": "card_moved"}, removable=False)
            lay.addWidget(self.trigger)
        elif kind == "schedule":
            lay.addWidget(_lbl("КОГДА", "Section"))
            self.trigger = ParamEditor(board, A.SCHEDULES, tr or {"type": "daily"}, removable=False)
            lay.addWidget(self.trigger)
        elif kind == "due":
            lay.addWidget(_lbl("КОГДА", "Section"))
            row = QHBoxLayout()
            self.amount = QDoubleSpinBox()
            self.amount.setRange(0, 365)
            self.amount.setDecimals(0)
            self.amount.setValue(float(tr.get("amount", 1)))
            self.unit = QComboBox()
            self.unit.addItem("дней", "days")
            self.unit.addItem("часов", "hours")
            self.unit.setCurrentIndex(max(0, self.unit.findData(tr.get("unit", "days"))))
            self.when = QComboBox()
            for k, t in A.DUE_WHEN.items():
                self.when.addItem(t, k)
            self.when.setCurrentIndex(max(0, self.when.findData(tr.get("when", "before"))))
            row.addWidget(self.amount)
            row.addWidget(self.unit)
            row.addWidget(self.when, 1)
            lay.addLayout(row)
        # conditions
        lay.addWidget(_lbl("ЕСЛИ КАРТОЧКА (необязательно)" if kind not in ("schedule", "board_button") else
                           "ДЛЯ КАРТОЧЕК (необязательно; без условий действия над карточками не выполняются)",
                           "Section"))
        self.cond_box = QVBoxLayout()
        lay.addLayout(self.cond_box)
        add_c = QPushButton("+ условие")
        add_c.clicked.connect(lambda: self._add(self.cond_box, A.CONDITIONS, {"type": "in_list"}))
        lay.addWidget(add_c, 0, Qt.AlignLeft)
        for c in rule.get("conditions", []):
            self._add(self.cond_box, A.CONDITIONS, c)
        # actions
        lay.addWidget(_lbl("СДЕЛАТЬ", "Section"))
        self.act_box = QVBoxLayout()
        scroll_host = QWidget()
        scroll_host.setLayout(self.act_box)
        lay.addWidget(scroll_host)
        self.board_level = kind in ("schedule", "board_button")
        add_a = QPushButton("+ действие")
        add_a.clicked.connect(lambda: self._add(self.act_box, A.ACTIONS, {"type": "move"}, True))
        lay.addWidget(add_a, 0, Qt.AlignLeft)
        for a in rule.get("actions", []) or [{"type": "move"}]:
            self._add(self.act_box, A.ACTIONS, a, True)
        lay.addStretch(1)
        self.preview = _lbl("", "Muted", wrap=True)
        lay.addWidget(self.preview)
        row = QHBoxLayout()
        ok = QPushButton("Сохранить")
        ok.setObjectName("Accent")
        ok.clicked.connect(self.save)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        prev = QPushButton("Проверить текст")
        prev.clicked.connect(self.update_preview)
        row.addWidget(prev)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)
        self.update_preview()

    def _add(self, box, vocab, item, actions=False):
        ed = ParamEditor(self.board, vocab, item, extra_vocab=A.BOARD_ACTIONS if actions and self.board_level else None)
        ed.removed.connect(lambda w: (box.removeWidget(w), w.deleteLater()))
        box.addWidget(ed)

    def _items(self, box):
        out = []
        for i in range(box.count()):
            w = box.itemAt(i).widget()
            if isinstance(w, ParamEditor) and not w.isHidden():
                out.append(w.value())
        return out

    def result_rule(self):
        r = dict(self.rule)
        if self.kind in ("rule", "schedule"):
            r["trigger"] = self.trigger.value()
        elif self.kind == "due":
            r["trigger"] = {"when": self.when.currentData(), "amount": int(self.amount.value()),
                            "unit": self.unit.currentData()}
        if self.kind in ("card_button", "board_button"):
            r["name"] = self.name.text().strip() or "Кнопка"
            r["icon"] = self.icon.currentData()
        r["conditions"] = self._items(self.cond_box)
        r["actions"] = self._items(self.act_box)
        return r

    def update_preview(self):
        self.preview.setText(A.describe(self.board, self.result_rule()))

    def save(self):
        self.rule.clear()
        self.rule.update(self.result_rule())
        self.accept()


class AutomationDialog(QDialog):
    changed = Signal()

    def __init__(self, window, board, automation, start="rule"):
        super().__init__(window)
        self.win = window
        self.b = board
        self.auto = automation
        self.setWindowTitle("Автоматизация")
        self.resize(1000, 640)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        side = QFrame()
        side.setObjectName("Side")
        side.setFixedWidth(220)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(12, 18, 12, 12)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap("bolt", size=48))
        ic.setFixedSize(24, 24)
        ic.setScaledContents(True)
        head.addWidget(ic)
        head.addWidget(_lbl("Автоматизация", "Logo"))
        head.addStretch(1)
        sl.addLayout(head)
        sl.addSpacing(10)
        self.nav = QListWidget()
        self.nav.setObjectName("Nav")
        for key, title, icon, _ in KINDS + [("ideas", "Идеи", "star", ""), ("log", "Журнал", "list", "")]:
            it = QListWidgetItem(icons.icon(icon, theme.CURRENT["text"]), title)
            it.setData(Qt.UserRole, key)
            self.nav.addItem(it)
        self.nav.currentRowChanged.connect(self.show_kind)
        sl.addWidget(self.nav, 1)
        h.addWidget(side)
        self.page = QScrollArea()
        self.page.setWidgetResizable(True)
        self.page.setFrameShape(QFrame.NoFrame)
        h.addWidget(self.page, 1)
        keys = [k for k, *_ in KINDS] + ["ideas", "log"]
        self.nav.setCurrentRow(keys.index(start) if start in keys else 0)

    def current(self):
        it = self.nav.currentItem()
        return it.data(Qt.UserRole) if it else "rule"

    def show_kind(self, *_):
        key = self.current()
        body = QWidget()
        body.setObjectName("Page")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(28, 22, 28, 22)
        lay.setSpacing(10)
        if key == "log":
            lay.addWidget(_lbl("Журнал", "Title"))
            log = self.b.d.get("autolog", [])
            if not log:
                lay.addWidget(_lbl("Автоматизация ещё ничего не делала на этой доске.", "Muted"))
            for e in log[:120]:
                lay.addWidget(_lbl(f"<span style='color:{theme.CURRENT['muted']}'>{fmt_dt(e['ts'])}</span>  "
                                   f"{e['text']}" + (f" — <b>{e['card']}</b>" if e.get("card") else ""), wrap=True))
        elif key == "ideas":
            lay.addWidget(_lbl("Идеи для этой доски", "Title"))
            lay.addWidget(_lbl("Готовые правила по вашим спискам — добавьте в один щелчок и поправьте под себя.",
                               "Muted", wrap=True))
            for r in A.suggestions(self.b):
                lay.addWidget(self._row(r, idea=True))
        else:
            title, desc = next((t, d) for k, t, _, d in KINDS if k == key)
            head = QHBoxLayout()
            head.addWidget(_lbl(title, "Title"))
            head.addStretch(1)
            add = QPushButton("Создать")
            add.setObjectName("Accent")
            add.clicked.connect(lambda: self.edit(A.new_rule(kind=key), new=True))
            head.addWidget(add)
            lay.addLayout(head)
            lay.addWidget(_lbl(desc, "Muted", wrap=True))
            rules = [r for r in self.b.d.get("rules", []) if r.get("kind", "rule") == key]
            if not rules:
                lay.addWidget(_lbl("Пока пусто. Нажмите «Создать» или загляните в «Идеи».", "Hint"))
            for r in rules:
                lay.addWidget(self._row(r))
        lay.addStretch(1)
        self.page.setWidget(body)

    def _row(self, r, idea=False):
        box = QFrame()
        box.setObjectName("RuleRow")
        hl = QHBoxLayout(box)
        hl.setContentsMargins(14, 10, 10, 10)
        ic = QLabel()
        ic.setPixmap(icons.pixmap(r.get("icon") if r.get("kind") in ("card_button", "board_button") else
                                  {"rule": "bolt", "schedule": "calendar", "due": "clock"}.get(r.get("kind"), "bolt"),
                                  size=40))
        ic.setFixedSize(20, 20)
        ic.setScaledContents(True)
        hl.addWidget(ic, 0, Qt.AlignTop)
        col = QVBoxLayout()
        text = _lbl(A.describe(self.b, r), wrap=True)
        col.addWidget(text)
        if not idea:
            stat = f"Срабатывало: {r.get('runs', 0)}" + (f" · последний раз {fmt_dt(r['last'])}" if r.get("last") else "")
            col.addWidget(_lbl(stat, "Hint"))
        hl.addLayout(col, 1)
        if idea:
            add = QPushButton("Добавить")
            add.clicked.connect(lambda: self._add_idea(r))
            hl.addWidget(add)
            return box
        if r.get("kind") in ("card_button", "board_button") or r.get("kind") == "schedule":
            run = QPushButton("Запустить" if r.get("kind") != "card_button" else "")
            if r.get("kind") == "card_button":
                run.hide()
            run.clicked.connect(lambda: self._run(r))
            hl.addWidget(run)
        on = QCheckBox("вкл")
        on.setChecked(r.get("enabled", True))
        on.toggled.connect(lambda v: (self.b.touch(), r.update(enabled=v), self.changed.emit()))
        hl.addWidget(on)
        ed = QToolButton()
        ed.setIcon(icons.icon("desc", theme.CURRENT["text"]))
        ed.setToolTip("Изменить")
        ed.clicked.connect(lambda: self.edit(r))
        hl.addWidget(ed)
        cp = QToolButton()
        cp.setIcon(icons.icon("copy", theme.CURRENT["text"]))
        cp.setToolTip("Копировать")
        cp.clicked.connect(lambda: (self.b.touch(), self.b.d["rules"].append(A.clone_rule(r)), self.changed.emit(),
                                    self.show_kind()))
        hl.addWidget(cp)
        rm = QToolButton()
        rm.setIcon(icons.icon("trash", theme.CURRENT["text"]))
        rm.setToolTip("Удалить")
        rm.clicked.connect(lambda: self._remove(r))
        hl.addWidget(rm)
        return box

    def _add_idea(self, r):
        self.b.touch("добавил(а) правило автоматизации")
        self.b.d["rules"].append(A.clone_rule(r))
        self.changed.emit()
        keys = [k for k, *_ in KINDS]
        self.nav.setCurrentRow(keys.index(r["kind"]))

    def _run(self, r):
        if r.get("kind") == "board_button":
            self.auto.press_board_button(self.b, r)
        else:
            self.b._begin()
            try:
                self.auto._as_bot(self.b, lambda: A.run_board_actions(self.b, r))
            finally:
                self.b._end("", None, {})
            self.auto._record(self.b, r)
        self.changed.emit()
        self.show_kind()

    def _remove(self, r):
        self.b.touch()
        self.b.d["rules"] = [x for x in self.b.d["rules"] if x["id"] != r["id"]]
        self.changed.emit()
        self.show_kind()

    def edit(self, r, new=False):
        work = dict(r)
        dlg = RuleEditor(self.b, work, self)
        if dlg.exec():
            self.b.touch("изменил(а) автоматизацию" if not new else "добавил(а) правило автоматизации")
            if new:
                self.b.d["rules"].append(work)
            else:
                r.clear()
                r.update(work)
            self.changed.emit()
            self.show_kind()


