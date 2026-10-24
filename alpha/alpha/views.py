"""Other board views (Trello's Table, Calendar and Dashboard)."""
import calendar
from datetime import date, datetime, timedelta

from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from . import theme
from .board_view import CARD_MIME
from .model import due_state, fmt_dt, parse_dt
from .widgets import draw_avatar, font

MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь",
          "Декабрь"]
DAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


class TableView(QTableWidget):
    open_card_requested = Signal(str)

    COLS = ["Карточка", "Список", "Метки", "Участники", "Срок", "Чек-лист", "Голоса"]

    def __init__(self, board):
        super().__init__()
        self.board = board
        self.filter = {}
        self.setObjectName("CardTable")
        self.setColumnCount(len(self.COLS))
        self.setHorizontalHeaderLabels(self.COLS)
        self.verticalHeader().hide()
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSortingEnabled(True)
        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, len(self.COLS)):
            self.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.cellDoubleClicked.connect(lambda r, _c: self.open_card_requested.emit(self.item(r, 0).data(Qt.UserRole)))
        self.rebuild()

    def rebuild(self):
        b = self.board
        self.setSortingEnabled(False)
        cards = [c for c in b.cards() if b.matches(c, self.filter)]
        self.setRowCount(len(cards))
        order = {lst["id"]: i for i, lst in enumerate(b.lists())}
        for r, c in enumerate(sorted(cards, key=lambda c: (order.get(c["list"], 99), c["pos"]))):
            lst = b.list(c["list"])
            done, total = b.checklist_progress(c)
            vals = [c["title"], lst["name"] if lst else "",
                    ", ".join((b.label(x)["name"] or theme.LABEL_COLORS.get(b.label(x)["color"], ("", "?"))[1])
                              for x in c["labels"] if b.label(x)),
                    ", ".join(b.member(x)["name"] for x in c["members"] if b.member(x)),
                    fmt_dt(c.get("due")) + (" ✓" if c.get("due_done") else ""),
                    f"{done}/{total}" if total else "", str(c.get("votes") or "")]
            for col, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if col == 0:
                    it.setData(Qt.UserRole, c["id"])
                if col == 4 and c.get("due"):
                    it.setData(Qt.UserRole + 1, c["due"])
                    st = due_state(c)
                    if st in ("overdue", "soon", "done"):
                        it.setForeground(QColor(theme.CURRENT[{"overdue": "overdue", "soon": "warn",
                                                               "done": "done"}[st]]))
                self.setItem(r, col, it)
        self.setSortingEnabled(True)


class CalendarGrid(QWidget):
    """Month grid with cards on their due days; drop a card on a day to set its due date."""

    open_card_requested = Signal(str)
    changed = Signal()

    def __init__(self, board):
        super().__init__()
        self.board = board
        self.filter = {}
        self.month = date.today().replace(day=1)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.hits = []      # (QRect, card id)
        self.drop_day = None
        self.setMinimumSize(700, 500)

    def days(self):
        first = self.month
        start = first - timedelta(days=first.weekday())
        return [start + timedelta(days=i) for i in range(42)]

    def cell_rect(self, i):
        top = 30
        w = self.width() / 7
        h = (self.height() - top) / 6
        return QRectF((i % 7) * w, top + (i // 7) * h, w, h)

    def paintEvent(self, _):
        c = theme.CURRENT
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(c["bg"]))
        w = self.width() / 7
        p.setFont(font(11, bold=True))
        p.setPen(QColor(c["muted"]))
        for i, d in enumerate(DAYS):
            p.drawText(QRectF(i * w, 0, w, 28), Qt.AlignCenter, d)
        cards = [x for x in self.board.cards() if x.get("due") and self.board.matches(x, self.filter)]
        by_day = {}
        for card in sorted(cards, key=lambda x: x["due"]):
            by_day.setdefault(parse_dt(card["due"]).date(), []).append(card)
        today = date.today()
        self.hits = []
        fm = QFontMetrics(font(11))
        for i, d in enumerate(self.days()):
            r = self.cell_rect(i)
            other = d.month != self.month.month
            p.setPen(QPen(QColor(c["border"]), 1))
            p.setBrush(QColor(c["panel"] if other else c["card"]))
            if self.drop_day == d:
                p.setBrush(QColor(c["selected"]))
            p.drawRect(r)
            num = QRectF(r.x() + 6, r.y() + 4, 26, 20)
            if d == today:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(c["accent"]))
                p.drawEllipse(QRectF(r.x() + 4, r.y() + 3, 22, 22))
                p.setPen(QColor("#FFFFFF"))
                num = QRectF(r.x() + 4, r.y() + 3, 22, 22)
            else:
                p.setPen(QColor(c["faint"] if other else c["text"]))
            p.setFont(font(12, bold=d == today))
            p.drawText(num, Qt.AlignCenter, str(d.day))
            y = r.y() + 28
            items = by_day.get(d, [])
            for k, card in enumerate(items):
                if y + 20 > r.bottom() - 2:
                    p.setPen(QColor(c["muted"]))
                    p.setFont(font(11))
                    p.drawText(QRectF(r.x() + 6, y, r.width() - 10, 16), Qt.AlignLeft, f"ещё {len(items) - k}…")
                    break
                cr = QRectF(r.x() + 4, y, r.width() - 8, 18)
                st = due_state(card)
                bg = {"overdue": c["overdue"], "done": c["done"], "soon": c["due_soon"]}.get(st)
                lb = next((self.board.label(x) for x in card["labels"] if self.board.label(x)), None)
                path = QPainterPath()
                path.addRoundedRect(cr, 4, 4)
                p.fillPath(path, QColor(bg or (theme.label_hex(lb["color"]) if lb else c["selected"])))
                p.setPen(QColor("#FFFFFF" if (bg and st != "soon") or (lb and not bg and QColor(theme.label_hex(
                    lb["color"])).lightness() < 175) else c["text"]))
                p.setFont(font(11))
                p.drawText(cr.adjusted(5, 0, -3, 0), Qt.AlignVCenter | Qt.AlignLeft,
                           fm.elidedText(card["title"], Qt.ElideRight, int(cr.width()) - 8))
                self.hits.append((cr.toRect(), card["id"]))
                y += 21
        p.end()

    def day_at(self, pos):
        for i, d in enumerate(self.days()):
            if self.cell_rect(i).contains(pos):
                return d
        return None

    def mouseDoubleClickEvent(self, e):
        self.mousePressEvent(e)

    def mousePressEvent(self, e):
        pos = e.position().toPoint()
        for r, cid in self.hits:
            if r.contains(pos):
                if e.button() == Qt.LeftButton:
                    self._drag_from = (pos, cid)
                return
        self._drag_from = None

    def mouseMoveEvent(self, e):
        df = getattr(self, "_drag_from", None)
        if df and e.buttons() & Qt.LeftButton and (e.position().toPoint() - df[0]).manhattanLength() > 6:
            from PySide6.QtCore import QMimeData
            from PySide6.QtGui import QDrag

            self._drag_from = None
            drag = QDrag(self)
            md = QMimeData()
            md.setData(CARD_MIME, df[1].encode())
            drag.setMimeData(md)
            drag.exec(Qt.MoveAction)

    def mouseReleaseEvent(self, e):
        df = getattr(self, "_drag_from", None)
        if df:
            self._drag_from = None
            self.open_card_requested.emit(df[1])

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(CARD_MIME):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        self.drop_day = self.day_at(e.position())
        self.update()
        e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.drop_day = None
        self.update()

    def dropEvent(self, e):
        d = self.day_at(e.position())
        self.drop_day = None
        if d:
            cid = bytes(e.mimeData().data(CARD_MIME)).decode()
            card = self.board.card(cid)
            old = parse_dt(card.get("due")) if card else None
            t = (old.hour, old.minute) if old else (18, 0)
            self.board.update_card(cid, due=datetime(d.year, d.month, d.day, *t).strftime("%Y-%m-%dT%H:%M"))
            self.changed.emit()
        e.acceptProposedAction()
        self.update()


class CalendarView(QWidget):
    def __init__(self, board):
        super().__init__()
        self.board = board
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        head = QHBoxLayout()
        prev = QPushButton("‹")
        nxt = QPushButton("›")
        today = QPushButton("Сегодня")
        self.title = QLabel()
        self.title.setObjectName("H2")
        head.addWidget(self.title)
        head.addStretch(1)
        for b in (prev, today, nxt):
            head.addWidget(b)
        lay.addLayout(head)
        self.grid = CalendarGrid(board)
        lay.addWidget(self.grid, 1)
        hint = QLabel("Перетащите карточку на другой день, чтобы перенести срок. Карточки без срока здесь не видны.")
        hint.setObjectName("Hint")
        lay.addWidget(hint)
        prev.clicked.connect(lambda: self.shift(-1))
        nxt.clicked.connect(lambda: self.shift(1))
        today.clicked.connect(self.today)
        self.open_card_requested = self.grid.open_card_requested
        self.changed = self.grid.changed
        self.rebuild()

    def shift(self, k):
        m = self.grid.month
        y, mo = m.year + (m.month - 1 + k) // 12, (m.month - 1 + k) % 12 + 1
        self.grid.month = date(y, mo, 1)
        self.rebuild()

    def today(self):
        self.grid.month = date.today().replace(day=1)
        self.rebuild()

    def set_filter(self, flt):
        self.grid.filter = flt
        self.rebuild()

    def rebuild(self):
        m = self.grid.month
        self.title.setText(f"{MONTHS[m.month - 1]} {m.year}")
        self.grid.update()


class DashboardView(QWidget):
    """Four charts: cards per list, per label, per member, by due status (Trello's Dashboard view)."""

    def __init__(self, board):
        super().__init__()
        self.board = board
        self.filter = {}
        self.setMinimumSize(700, 500)

    def rebuild(self):
        self.update()

    def paintEvent(self, _):
        c = theme.CURRENT
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(c["bg"]))
        b = self.board
        cards = [x for x in b.cards() if b.matches(x, self.filter)]
        lists = [(lst["name"], sum(1 for x in cards if x["list"] == lst["id"]), c["accent"]) for lst in b.lists()]
        labels = [(lb["name"] or theme.LABEL_COLORS.get(lb["color"], ("", lb["color"]))[1],
                   sum(1 for x in cards if lb["id"] in x["labels"]), theme.label_hex(lb["color"]))
                  for lb in b.d["labels"]]
        members = [(m["name"], sum(1 for x in cards if m["id"] in x["members"]), m.get("color") or c["accent"], m)
                   for m in b.d["members"]]
        names = {"done": ("Выполнено", c["done"]), "soon": ("Скоро", c["due_soon"]),
                 "overdue": ("Просрочено", c["overdue"]), "later": ("Позже", "#5B8CC4"), None: ("Без срока", c["faint"])}
        dues = []
        for key in ("done", "soon", "overdue", "later", None):
            n = sum(1 for x in cards if due_state(x) == key)
            dues.append((names[key][0], n, names[key][1]))
        W, H = self.width(), self.height()
        pad = 16
        cw, ch = (W - pad * 3) / 2, (H - pad * 3) / 2
        self._chart(p, QRectF(pad, pad, cw, ch), "Карточек в списках", lists)
        self._chart(p, QRectF(pad * 2 + cw, pad, cw, ch), "Карточек по меткам", labels)
        self._chart(p, QRectF(pad, pad * 2 + ch, cw, ch), "Карточек на участника", [m[:3] for m in members],
                    avatars=[m[3] for m in members])
        self._chart(p, QRectF(pad * 2 + cw, pad * 2 + ch, cw, ch), "Сроки", dues)
        p.end()

    def _chart(self, p, r, title, rows, avatars=None):
        c = theme.CURRENT
        path = QPainterPath()
        path.addRoundedRect(r, 14, 14)
        p.fillPath(path, QColor(c["card"]))
        p.setPen(QPen(QColor(c["border"]), 1))
        p.drawPath(path)
        p.setPen(QColor(c["text"]))
        p.setFont(font(16, serif=True))
        p.drawText(QRectF(r.x() + 16, r.y() + 10, r.width() - 32, 26), Qt.AlignLeft | Qt.AlignVCenter, title)
        rows = rows[:12]
        if not rows:
            return
        area = QRectF(r.x() + 16, r.y() + 46, r.width() - 32, r.height() - 86)
        peak = max(1, max(n for _, n, _ in rows))
        bw = min(56, area.width() / len(rows) * 0.62)
        step = area.width() / len(rows)
        fm = QFontMetrics(font(11))
        for i, (name, n, color) in enumerate(rows):
            x = area.x() + step * i + (step - bw) / 2
            h = (area.height() - 18) * n / peak
            bar = QRectF(x, area.bottom() - h, bw, h)
            bp = QPainterPath()
            bp.addRoundedRect(bar, 5, 5)
            p.fillPath(bp, QColor(color))
            p.setPen(QColor(c["text"]))
            p.setFont(font(12, bold=True))
            p.drawText(QRectF(x - 10, bar.top() - 18, bw + 20, 16), Qt.AlignCenter, str(n))
            p.setFont(font(11))
            p.setPen(QColor(c["muted"]))
            lab = QRectF(area.x() + step * i, area.bottom() + 6, step, 30)
            if avatars:
                draw_avatar(p, QRect(int(lab.center().x() - 11), int(lab.y()), 22, 22), avatars[i])
            else:
                p.drawText(lab, Qt.AlignHCenter | Qt.AlignTop, fm.elidedText(name, Qt.ElideRight, int(step) - 4))


def month_days(year, month):
    return calendar.monthrange(year, month)[1]
