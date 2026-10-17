"""Calendar + task planner tab: month grid, the selected day's plan, overdue / upcoming / undated lists."""
import datetime as dt
import subprocess
import sys

from PySide6.QtCore import QDate, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QCalendarWidget, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMenu, QMessageBox, QPushButton, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from .tasks import DAILY_NAME, TaskIndex

MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь",
          "Ноябрь", "Декабрь"]
MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
              "ноября", "декабря"]
WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
WEEKDAYS_FULL = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
PRIO_MARK = {3: "⏫ ", 2: "🔼 ", 1: "🔽 ", 0: ""}


def scaled(font, delta, bold=False):
    """Copy of `font` bigger/smaller by `delta` (works for point- and pixel-sized fonts)."""
    f = QFont(font)
    if f.pointSize() > 0:
        f.setPointSize(max(8, f.pointSize() + delta))
    else:
        f.setPixelSize(max(9, f.pixelSize() + delta))
    if bold:
        f.setWeight(QFont.DemiBold)
    return f


def day_title(d):
    return f"{WEEKDAYS_FULL[d.weekday()]}, {d.day} {MONTHS_GEN[d.month - 1]}"


def _label(text, name=None):
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(True)
    return lab


def notify(title, message):
    """System notification (macOS Notification Center); silently ignored elsewhere."""
    if sys.platform == "darwin":
        esc = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')  # noqa: E731
        subprocess.Popen(["osascript", "-e", f'display notification "{esc(message)}" with title "{esc(title)}" '
                                              f'sound name "Glass"'])


class MonthView(QWidget):
    """Month grid painted in one go (no per-cell widgets, no animation)."""

    day_clicked = Signal(object)
    day_double_clicked = Signal(object)

    def __init__(self, colors):
        super().__init__()
        self.c = colors
        self.year, self.month = dt.date.today().year, dt.date.today().month
        self.selected = dt.date.today()
        self.counts = {}  # date -> (open, done)
        self.setMinimumSize(420, 360)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.hover = None

    def set_month(self, year, month):
        self.year, self.month = year, month
        self.update()

    def days(self):
        """42 dates (6 weeks, Monday first) covering the month."""
        first = dt.date(self.year, self.month, 1)
        start = first - dt.timedelta(days=first.weekday())
        return [start + dt.timedelta(days=i) for i in range(42)]

    def _geometry(self):
        head = 28
        w = self.width() / 7
        h = (self.height() - head) / 6
        return head, w, h

    def _date_at(self, pos):
        head, w, h = self._geometry()
        if pos.y() < head:
            return None
        col = int(pos.x() // w)
        row = int((pos.y() - head) // h)
        if 0 <= col < 7 and 0 <= row < 6:
            return self.days()[row * 7 + col]
        return None

    def mousePressEvent(self, e):
        d = self._date_at(e.position())
        if d:
            self.selected = d
            self.update()
            self.day_clicked.emit(d)

    def mouseDoubleClickEvent(self, e):
        d = self._date_at(e.position())
        if d:
            self.day_double_clicked.emit(d)

    def mouseMoveEvent(self, e):
        d = self._date_at(e.position())
        if d != self.hover:
            self.hover = d
            self.update()

    def leaveEvent(self, _e):
        self.hover = None
        self.update()

    def paintEvent(self, _e):
        c = self.c
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        head, w, h = self._geometry()
        small = scaled(self.font(), -2, bold=True)
        p.setFont(small)
        p.setPen(QColor(c["muted"]))
        for i, name in enumerate(WEEKDAYS):
            p.drawText(QRectF(i * w, 0, w, head), Qt.AlignCenter, name.upper())
        today = dt.date.today()
        num_font = scaled(self.font(), 1)
        for i, d in enumerate(self.days()):
            col, row = i % 7, i // 7
            cell = QRectF(col * w + 3, head + row * h + 3, w - 6, h - 6)
            in_month = d.month == self.month
            if d == self.selected:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(c["selected"]))
                p.drawRoundedRect(cell, 10, 10)
            elif d == self.hover:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(c["hover"]))
                p.drawRoundedRect(cell, 10, 10)
            # day number (today = accent circle)
            num_rect = QRectF(cell.left() + 6, cell.top() + 5, 28, 28)
            p.setFont(num_font)
            if d == today:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(c["accent"]))
                p.drawEllipse(num_rect)
                p.setPen(QColor(c["accent_text"]))
            else:
                p.setPen(QColor(c["text"] if in_month else c["muted"]))
                if not in_month:
                    p.setOpacity(0.55)
            p.drawText(num_rect, Qt.AlignCenter, str(d.day))
            p.setOpacity(1.0)
            # task markers
            open_n, done_n = self.counts.get(d, (0, 0))
            if open_n or done_n:
                p.setFont(small)
                overdue = d < today and open_n
                color = QColor(c["warn"] if overdue else c["accent"])
                y = cell.bottom() - 14
                dots = min(open_n, 4)
                for k in range(dots):
                    p.setPen(Qt.NoPen)
                    p.setBrush(color)
                    p.drawEllipse(QRectF(cell.left() + 9 + k * 9, y, 6, 6))
                label = f"{open_n}" if open_n else "✓"
                if done_n and open_n:
                    label = f"{open_n} · ✓{done_n}"
                p.setPen(QColor(c["muted"] if not open_n else (c["warn"] if overdue else c["text"])))
                p.drawText(QRectF(cell.left() + 6, cell.bottom() - 34, cell.width() - 12, 16),
                           Qt.AlignRight | Qt.AlignVCenter, label)
        p.end()


class DatePickDialog(QDialog):
    def __init__(self, parent, initial):
        super().__init__(parent)
        self.setWindowTitle("Перенести на дату")
        lay = QVBoxLayout(self)
        self.cal = QCalendarWidget()
        self.cal.setFirstDayOfWeek(Qt.Monday)
        self.cal.setSelectedDate(QDate(initial.year, initial.month, initial.day))
        lay.addWidget(self.cal)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def date(self):
        q = self.cal.selectedDate()
        return dt.date(q.year(), q.month(), q.day())


class CalendarTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.kind = "calendar"
        self.index = win.task_index
        self.day = dt.date.today()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(1)
        outer.addWidget(split)

        # ---------------- left: month + planner lists
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(28, 20, 18, 16)
        ll.setSpacing(10)
        head = QHBoxLayout()
        self.month_label = _label("", "Title")
        head.addWidget(self.month_label, 1)
        for text, fn in (("‹", lambda: self.shift_month(-1)), ("Сегодня", self.go_today), ("›", lambda: self.shift_month(1))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            head.addWidget(b)
        ll.addLayout(head)
        self.month = MonthView(win.colors)
        self.month.day_clicked.connect(self.select_day)
        self.month.day_double_clicked.connect(lambda d: self.win.open_note(self.win.vault.daily_note(d)))
        ll.addWidget(self.month, 3)
        ll.addWidget(_label("ПЛАНИРОВЩИК", "Section"))
        self.planner = QListWidget()
        self.planner.setObjectName("Plain")
        self.planner.itemChanged.connect(self._item_checked)
        self.planner.itemDoubleClicked.connect(self._open_item)
        self.planner.setContextMenuPolicy(Qt.CustomContextMenu)
        self.planner.customContextMenuRequested.connect(lambda pos: self._menu(self.planner, pos))
        ll.addWidget(self.planner, 2)
        split.addWidget(left)

        # ---------------- right: selected day
        right = QWidget()
        right.setObjectName("RightPanel")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(22, 20, 22, 16)
        rl.setSpacing(10)
        self.day_label = _label("", "CardTitle")
        rl.addWidget(self.day_label)
        self.day_info = _label("", "Muted")
        rl.addWidget(self.day_info)
        open_daily = QPushButton("Открыть дневник дня")
        open_daily.setObjectName("Link")
        open_daily.clicked.connect(lambda: self.win.open_note(self.win.vault.daily_note(self.day)))
        rl.addWidget(open_daily, 0, Qt.AlignLeft)
        self.new_text = QLineEdit(placeholderText="Новая задача…  (Enter — добавить)")
        self.new_text.returnPressed.connect(self.add_task)
        rl.addWidget(self.new_text)
        row = QHBoxLayout()
        self.new_time = QLineEdit(placeholderText="⏰ 14:30")
        self.new_time.setFixedWidth(96)
        self.new_time.returnPressed.connect(self.add_task)
        self.new_prio = QComboBox()
        for label, value in (("Без приоритета", 0), ("⏫ Высокий", 3), ("🔼 Средний", 2), ("🔽 Низкий", 1)):
            self.new_prio.addItem(label, value)
        add = QPushButton("Добавить")
        add.setObjectName("Accent")
        add.clicked.connect(self.add_task)
        row.addWidget(self.new_time)
        row.addWidget(self.new_prio, 1)
        row.addWidget(add)
        rl.addLayout(row)
        self.day_list = QListWidget()
        self.day_list.setObjectName("Plain")
        self.day_list.itemChanged.connect(self._item_checked)
        self.day_list.itemDoubleClicked.connect(self._open_item)
        self.day_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.day_list.customContextMenuRequested.connect(lambda pos: self._menu(self.day_list, pos))
        rl.addWidget(self.day_list, 1)
        rl.addWidget(_label("Задачи — это строки «- [ ]» в заметках. Дата: 📅 2026-10-20, время: ⏰ 14:30. "
                            "Двойной щелчок — открыть заметку, правый — перенести или удалить.", "Muted"))
        split.addWidget(right)
        split.setSizes([620, 380])
        self.refresh()

    # ------------------------------------------------------------ navigation
    def shift_month(self, delta):
        y, m = self.month.year, self.month.month + delta
        y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
        self.month.set_month(y, m)
        self.refresh()

    def go_today(self):
        today = dt.date.today()
        self.month.set_month(today.year, today.month)
        self.month.selected = today
        self.select_day(today)

    def select_day(self, day):
        self.day = day
        if (day.year, day.month) != (self.month.year, self.month.month):
            self.month.set_month(day.year, day.month)
        self.month.selected = day
        self.refresh()

    # ------------------------------------------------------------ data
    def refresh(self):
        self.month.c = self.win.colors
        self.month_label.setText(f"{MONTHS[self.month.month - 1]} {self.month.year}")
        days = self.month.days()
        by_day = self.index.by_day(days[0], days[-1])
        self.month.counts = {d: (sum(not t.done for t in ts), sum(t.done for t in ts)) for d, ts in by_day.items()}
        self.month.update()

        self.day_label.setText(day_title(self.day) + (" · сегодня" if self.day == dt.date.today() else ""))
        tasks = self.index.on(self.day)
        open_n = sum(not t.done for t in tasks)
        self.day_info.setText(f"Задач: {len(tasks)}, осталось: {open_n}" if tasks else "На этот день задач нет.")
        self._fill(self.day_list, [(None, tasks)], show_date=False)

        today = dt.date.today()
        groups = [("Просрочено", self.index.overdue(today)),
                  ("Сегодня", [t for t in self.index.on(today) if not t.done]),
                  ("Ближайшие 7 дней", self.index.upcoming(7, today)),
                  ("Без даты", self.index.undated()[:50])]
        self._fill(self.planner, groups, show_date=True)

    def _fill(self, widget, groups, show_date):
        widget.blockSignals(True)
        widget.clear()
        for title, tasks in groups:
            if title is not None:
                if not tasks:
                    continue
                head = QListWidgetItem(f"{title.upper()}   {len(tasks)}")
                head.setFlags(Qt.NoItemFlags)
                head.setFont(scaled(widget.font(), -2, bold=True))
                head.setForeground(QColor(self.win.colors["warn" if title == "Просрочено" else "muted"]))
                widget.addItem(head)
            for t in tasks:
                parts = []
                if show_date and t.date:
                    parts.append(f"{t.date.day} {MONTHS_GEN[t.date.month - 1][:3]}")
                if t.time:
                    parts.append(t.time.strftime("%H:%M"))
                prefix = ("  ".join(parts) + "   ") if parts else ""
                source = "Дневник" if DAILY_NAME.match(t.path.stem) else t.path.stem
                item = QListWidgetItem(f"{prefix}{PRIO_MARK[t.priority]}{t.text}\n    {source}")
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if t.done else Qt.Unchecked)
                if t.done:
                    item.setForeground(QColor(self.win.colors["muted"]))
                item.setData(Qt.UserRole, t)
                widget.addItem(item)
        if widget.count() == 0 and show_date:
            empty = QListWidgetItem("Всё сделано ✓  Добавьте задачи справа или в заметках.")
            empty.setFlags(Qt.NoItemFlags)
            widget.addItem(empty)
        widget.blockSignals(False)

    # ------------------------------------------------------------ actions
    def _apply(self, fn, *args):
        self.win.save_all()
        try:
            fn(*args)
        except Exception as exc:
            QMessageBox.warning(self, "Календарь", str(exc))
        self.win.reload_open_notes()
        self.refresh()

    def _item_checked(self, item):
        task = item.data(Qt.UserRole)
        if task is not None:
            self._apply(self.index.toggle, task)

    def _open_item(self, item):
        task = item.data(Qt.UserRole)
        if task is not None:
            self.win.open_note(task.path, line=task.line)

    def add_task(self):
        text = self.new_text.text().strip()
        if not text:
            return
        time = None
        raw = self.new_time.text().strip()
        if raw:
            try:
                h, m = raw.replace(".", ":").split(":")
                time = dt.time(int(h), int(m))
            except Exception:
                QMessageBox.warning(self, "Календарь", "Время в формате ЧЧ:ММ, например 14:30")
                return
        self._apply(self.index.add, text, self.day, time, self.new_prio.currentData())
        self.new_text.clear()
        self.new_time.clear()
        self.new_text.setFocus()

    def _menu(self, widget, pos):
        item = widget.itemAt(pos)
        task = item.data(Qt.UserRole) if item else None
        if task is None:
            return
        today = dt.date.today()
        menu = QMenu(self)
        menu.addAction("Открыть заметку", lambda: self.win.open_note(task.path, line=task.line))
        menu.addSeparator()
        menu.addAction("На сегодня", lambda: self._apply(self.index.reschedule, task, today))
        menu.addAction("На завтра", lambda: self._apply(self.index.reschedule, task, today + dt.timedelta(days=1)))
        menu.addAction("Через неделю", lambda: self._apply(self.index.reschedule, task, (task.date or today) + dt.timedelta(days=7)))

        def pick():
            dlg = DatePickDialog(self, task.date or self.day)
            if dlg.exec():
                self._apply(self.index.reschedule, task, dlg.date())

        menu.addAction("Выбрать дату…", pick)
        if task.explicit_date:
            menu.addAction("Убрать дату", lambda: self._apply(self.index.reschedule, task, None))
        menu.addSeparator()
        menu.addAction("Удалить задачу", lambda: (
            QMessageBox.question(self, "Удалить", f"Удалить задачу «{task.text}»?") == QMessageBox.Yes
            and self._apply(self.index.delete, task)))
        menu.exec(widget.viewport().mapToGlobal(pos))


__all__ = ["CalendarTab", "notify"]
