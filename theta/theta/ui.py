"""Тета: loading page, home (map / mode / source pickers, daily challenge, recent games), the game page (viewer +
guess map in the corner + result overlays), records, settings. Same shell as the other apps: side bar / icon rail."""
import datetime as dt
import os
import sys
import time

from PySide6.QtCore import QEvent, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QImage, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QCompleter, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea,
                               QSpinBox, QStackedWidget, QToolButton, QVBoxLayout, QWidget)

from . import APP_NAME, LOGO, __version__, game as gamemod, geo, icons, maps, net, theme
from .game import MODES, TIME_LIMITS, Config, Game, Records
from .map import SlippyMap, TileCache, tiles_size
from .pano import EquirectView, FlatView
from .paths import Settings, resource_path
from .sources import ImageCache, all_sources, default_source
from .sources import streetview as sv

IS_MAC = sys.platform == "darwin"
MAP_SIZES = [(240, 170), (340, 240), (480, 340), (680, 480)]


def label(text, name=None, wrap=False):
    w = QLabel(text)
    if name:
        w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


def ic(name, color=None):
    c = theme.CURRENT
    return icons.icon(name, color or c.get("text", "#141413"), c.get("accent", "#D97757"))


def clear_layout(lay):
    while lay.count():
        item = lay.takeAt(0)
        w = item.widget()
        if w is not None:
            w.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def fmt_points(n):
    return f"{int(n):,}".replace(",", " ")


def fmt_date(ts):
    return dt.datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")


def greeting():
    h = dt.datetime.now().hour
    return "Доброе утро" if 5 <= h < 12 else "Добрый день" if h < 18 else "Добрый вечер" if h < 23 else "Доброй ночи"


# ---------------------------------------------------------------- splash

class SplashPage(QWidget):
    finished = Signal()
    STEPS = ["Читаем страны", "Открываем кеш", "Проверяем источники", "Почти готово"]

    def __init__(self):
        super().__init__()
        self.setObjectName("Splash")
        lay = QVBoxLayout(self)
        lay.addStretch(3)
        logo = label(LOGO, "SplashLogo")
        logo.setAlignment(Qt.AlignCenter)
        lay.addWidget(logo)
        name = label(APP_NAME, "SplashName")
        name.setAlignment(Qt.AlignCenter)
        lay.addWidget(name)
        sub = label("Угадай, где ты", "Muted")
        sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(sub)
        lay.addSpacing(28)
        row = QHBoxLayout()
        row.addStretch(1)
        self.bar = QProgressBar()
        self.bar.setRange(0, len(self.STEPS) * 10)
        self.bar.setTextVisible(False)
        self.bar.setFixedSize(320, 6)
        row.addWidget(self.bar)
        row.addStretch(1)
        lay.addLayout(row)
        self.status = label("", "Hint")
        self.status.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.status)
        lay.addStretch(4)
        ver = label(f"версия {__version__}", "Hint")
        ver.setAlignment(Qt.AlignCenter)
        lay.addWidget(ver)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.value = 0

    def start(self, fast=False):
        self.value = 0
        self.timer.start(4 if fast else 32)

    def _tick(self):
        self.value += 1
        self.bar.setValue(self.value)
        self.status.setText(self.STEPS[min(len(self.STEPS) - 1, self.value // 10)] + "…")
        if self.value >= self.bar.maximum():
            self.timer.stop()
            QTimer.singleShot(120, self.finished.emit)


# ---------------------------------------------------------------- home

class Hero(QFrame):
    """Big card: map, mode, source, options and the Play button."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setObjectName("Hero")
        self.setMinimumHeight(230)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 22)
        col = QVBoxLayout()
        col.setSpacing(10)
        self.title = label("Новая игра", "HeroTitle")
        col.addWidget(self.title)
        self.meta = label("", "HeroMeta")
        col.addWidget(self.meta)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        self.map_box = QComboBox()
        self.map_box.setObjectName("HeroPick")
        for a in maps.all_areas():
            self.map_box.addItem(("   " if a.kind == "country" else "") + a.name, a.key)
        self.map_box.setMaxVisibleItems(18)
        self.mode_box = QComboBox()
        self.mode_box.setObjectName("HeroPick")
        for k, v in MODES.items():
            self.mode_box.addItem(v, k)
        self.source_box = QComboBox()
        self.source_box.setObjectName("HeroPick")
        self.time_box = QComboBox()
        self.time_box.setObjectName("HeroPick")
        for secs, text in TIME_LIMITS:
            self.time_box.addItem(text, secs)
        for r, (text, w) in enumerate((("Карта", self.map_box), ("Режим", self.mode_box), ("Источник", self.source_box),
                                       ("Время на раунд", self.time_box))):
            lbl = label(text, "HeroMeta")
            grid.addWidget(lbl, r, 0)
            grid.addWidget(w, r, 1)
        col.addLayout(grid)
        opts = QHBoxLayout()
        self.no_move = QCheckBox("Без движения")
        self.no_pan = QCheckBox("Без поворота")
        self.no_zoom = QCheckBox("Без зума")
        for cb in (self.no_move, self.no_pan, self.no_zoom):
            cb.setObjectName("HeroCheck")
            opts.addWidget(cb)
        opts.addStretch(1)
        col.addLayout(opts)
        col.addStretch(1)
        lay.addLayout(col, 1)
        right = QVBoxLayout()
        right.addStretch(1)
        self.play = QPushButton("  Играть")
        self.play.setObjectName("PlayBtn")
        self.play.setIcon(icons.icon("play", "#FFFFFF", "#FFFFFF"))
        self.play.setIconSize(QSize(18, 18))
        self.play.setCursor(Qt.PointingHandCursor)
        self.play.clicked.connect(self.win.start_game)
        right.addWidget(self.play)
        self.hint = label("", "HeroMeta")
        self.hint.setWordWrap(True)
        self.hint.setMaximumWidth(260)
        right.addWidget(self.hint)
        right.addStretch(1)
        lay.addLayout(right)
        self.sync_from_settings()
        for w in (self.map_box, self.mode_box, self.source_box, self.time_box):
            w.currentIndexChanged.connect(self.store)
        for cb in (self.no_move, self.no_pan, self.no_zoom):
            cb.toggled.connect(self.store)

    def sync_from_settings(self):
        s = self.win.settings
        self.source_box.blockSignals(True)
        self.source_box.clear()
        for src in all_sources(s):
            self.source_box.addItem(src.title + ("" if src.available() else " — нет ключа"), src.name)
        self.source_box.blockSignals(False)
        cur = s.get("source") or default_source(s)
        for box, key in ((self.map_box, s.get("map")), (self.mode_box, s.get("mode")), (self.source_box, cur),
                         (self.time_box, int(s.get("time_limit") or 0))):
            i = box.findData(key)
            box.blockSignals(True)
            box.setCurrentIndex(max(0, i))
            box.blockSignals(False)
        for cb, key in ((self.no_move, "no_move"), (self.no_pan, "no_pan"), (self.no_zoom, "no_zoom")):
            cb.blockSignals(True)
            cb.setChecked(bool(s.get(key)))
            cb.blockSignals(False)
        self.refresh_text()

    def store(self):
        s = self.win.settings
        s.update(map=self.map_box.currentData(), mode=self.mode_box.currentData(), source=self.source_box.currentData(),
                 time_limit=self.time_box.currentData(), no_move=self.no_move.isChecked(),
                 no_pan=self.no_pan.isChecked(), no_zoom=self.no_zoom.isChecked())
        s.save()
        self.refresh_text()

    def refresh_text(self):
        s = self.win.settings
        area = maps.area(s.get("map") or "world")
        mode = s.get("mode") or "classic"
        daily = mode == "daily"
        for w in (self.map_box, self.time_box, self.no_move, self.no_pan, self.no_zoom):
            w.setEnabled(not daily)
        src = next((x for x in all_sources(s) if x.name == (s.get("source") or "")), None)
        if daily:
            self.meta.setText(f"Задание дня {dt.date.today().strftime('%d.%m')}: 5 раундов по всему миру, у всех одни и те же места")
        elif mode == "streak":
            self.meta.setText(f"{area.name} · угадывайте страну, пока не ошибётесь")
        else:
            self.meta.setText(f"{area.name} · 5 раундов · до {fmt_points(gamemod.MAX_ROUND * 5)} очков")
        if src and not src.available():
            self.hint.setText(src.hint())
            self.play.setEnabled(False)
        else:
            self.hint.setText("")
            self.play.setEnabled(True)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = theme.CURRENT
        from PySide6.QtGui import QLinearGradient, QPainterPath
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(0, 0, -1, -1), 18, 18)
        g = QLinearGradient(0, 0, self.width(), self.height())
        g.setColorAt(0, QColor(c.get("accent", "#D97757")).darker(115))
        g.setColorAt(1, QColor("#3B4A6B"))
        p.fillPath(path, g)
        p.setPen(QColor(255, 255, 255, 40))
        for i in range(-2, 9):
            y = 30 + i * 36
            p.drawLine(0, y, self.width(), y + 60)


class MiniCard(QPushButton):
    def __init__(self, title, sub, icon_name="trophy"):
        super().__init__()
        self.setObjectName("MiniCard")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        i = QLabel()
        i.setPixmap(icons.pixmap(icon_name, theme.CURRENT.get("text", "#141413"), theme.CURRENT.get("accent", "#D97757"), 36))
        lay.addWidget(i)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(label(title, "CardTitle"))
        col.addWidget(label(sub, "Hint"))
        lay.addLayout(col, 1)
        for w in self.findChildren(QLabel):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setMinimumHeight(64)


class HomePage(QScrollArea):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setObjectName("Page")
        self.lay = QVBoxLayout(body)
        self.lay.setContentsMargins(32, 26, 32, 26)
        self.lay.setSpacing(14)
        self.title = label("", "Title")
        self.lay.addWidget(self.title)
        self.hero = Hero(win)
        self.lay.addWidget(self.hero)
        self.lay.addWidget(label("ЗАДАНИЕ ДНЯ", "Section"))
        self.daily = MiniCard("Задание дня", "", "calendar")
        self.daily.clicked.connect(lambda: self.win.start_game(mode="daily"))
        self.lay.addWidget(self.daily)
        self.lay.addWidget(label("НЕДАВНИЕ ИГРЫ", "Section"))
        self.recent_box = QVBoxLayout()
        self.recent_box.setSpacing(8)
        self.lay.addLayout(self.recent_box)
        self.lay.addStretch(1)
        self.setWidget(body)

    def refresh(self):
        s = self.win.settings
        nick = s.get("nickname") or ""
        self.title.setText(f"{greeting()}{', ' + nick if nick else ''}")
        self.hero.sync_from_settings()
        done = self.win.records.daily_result()
        self.daily.findChildren(QLabel)[2].setText(
            f"Сегодня сыграно: {fmt_points(done)} очков" if done is not None else "Ещё не сыграно · 5 раундов, мир")
        clear_layout(self.recent_box)
        games = self.win.records.recent(5)
        if not games:
            self.recent_box.addWidget(label("Пока пусто — сыграйте первую игру.", "Hint"))
        for g in games:
            self.recent_box.addWidget(RecordRow(g))


class RecordRow(QFrame):
    def __init__(self, g):
        super().__init__()
        self.setObjectName("Card")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        col = QVBoxLayout()
        col.setSpacing(2)
        mode = MODES.get(g["mode"], g["mode"])
        col.addWidget(label(f"{g.get('map_name') or g['map']} · {mode}", "CardTitle"))
        sub = f"{g.get('nick', '')} · {fmt_date(g['date'])}"
        if g["mode"] == "streak":
            sub += f" · серия {g.get('streak', 0)}"
        col.addWidget(label(sub, "Hint"))
        lay.addLayout(col, 1)
        pts = label(f"{g.get('streak', 0)} подряд" if g["mode"] == "streak" else f"{fmt_points(g['score'])} / {fmt_points(g.get('max', 0))}", "H3")
        lay.addWidget(pts)


# ---------------------------------------------------------------- game page

class Overlay(QFrame):
    """Rounded translucent panel floating over the viewer."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("Overlay")
        self.setAttribute(Qt.WA_StyledBackground, True)


class GamePage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.game = None
        self.result_shown = False
        self.map_size = int(win.settings.get("map_size") or 1)
        self.pinned = bool(win.settings.get("map_pinned"))
        self.sv_panel = None
        self.sv_key = ""
        self.current_loc = self.start_loc = None
        self.game_summary = None
        self.setObjectName("GamePage")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        root.addWidget(self.stack)
        # viewers
        self.viewer_host = QWidget()
        vl = QVBoxLayout(self.viewer_host)
        vl.setContentsMargins(0, 0, 0, 0)
        self.viewers = QStackedWidget()
        self.pano = EquirectView()
        self.flat = FlatView()
        self.viewers.addWidget(self.pano)
        self.viewers.addWidget(self.flat)
        vl.addWidget(self.viewers)
        self.stack.addWidget(self.viewer_host)
        # end-of-game results page
        self.results = QScrollArea()
        self.results.setWidgetResizable(True)
        self.results.setFrameShape(QFrame.NoFrame)
        self.results_body = QWidget()
        self.results_body.setObjectName("Page")
        self.results_lay = QVBoxLayout(self.results_body)
        self.results_lay.setContentsMargins(40, 30, 40, 30)
        self.results.setWidget(self.results_body)
        self.stack.addWidget(self.results)
        # overlays (children of viewer_host, positioned manually)
        self.top = Overlay(self.viewer_host)
        tl = QHBoxLayout(self.top)
        tl.setContentsMargins(14, 8, 14, 8)
        self.round_lbl = label("Раунд 1 / 5", "OverlayTitle")
        self.score_lbl = label("0 очков", "OverlayText")
        self.timer_lbl = label("", "OverlayText")
        self.map_lbl = label("", "OverlayHint")
        for w in (self.round_lbl, self.score_lbl, self.timer_lbl, self.map_lbl):
            tl.addWidget(w)
            tl.addSpacing(14)
        tl.addStretch(1)
        self.quit_btn = QToolButton()
        self.quit_btn.setIcon(icons.icon("close", "#FFFFFF", "#FFFFFF"))
        self.quit_btn.setToolTip("Выйти на главную (Esc)")
        self.quit_btn.clicked.connect(self.confirm_quit)
        tl.addWidget(self.quit_btn)
        self.ctrl = Overlay(self.viewer_host)
        cl = QHBoxLayout(self.ctrl)
        cl.setContentsMargins(6, 4, 6, 4)
        self.btn_prev = self._tool("left", "Назад по улице", self.move_prev)
        self.btn_home = self._tool("target", "Вернуться в начало", self.go_start)
        self.btn_next = self._tool("right", "Вперёд по улице", self.move_next)
        self.btn_zin = self._tool("zoom_in", "Приблизить", lambda: self._zoom(1))
        self.btn_zout = self._tool("zoom_out", "Отдалить", lambda: self._zoom(-1))
        for b in (self.btn_prev, self.btn_home, self.btn_next, self.btn_zin, self.btn_zout):
            cl.addWidget(b)
        self.attr = label("", "Attribution")
        self.attr.setParent(self.viewer_host)
        self.attr.setAttribute(Qt.WA_StyledBackground, True)
        self.loading = label("Ищем место…", "LoadingBadge")
        self.loading.setParent(self.viewer_host)
        self.loading.setAlignment(Qt.AlignCenter)
        self.loading.setAttribute(Qt.WA_StyledBackground, True)
        # guess map panel
        self.map_panel = Overlay(self.viewer_host)
        self.map_panel.setObjectName("MapPanel")
        ml = QVBoxLayout(self.map_panel)
        ml.setContentsMargins(6, 6, 6, 6)
        ml.setSpacing(6)
        mtop = QHBoxLayout()
        self.pin_btn = self._tool("pinned" if self.pinned else "pin", "Закрепить карту развёрнутой", self.toggle_pin)
        mtop.addWidget(self.pin_btn)
        mtop.addStretch(1)
        self.size_btns = []
        for i in range(4):
            b = QToolButton()
            b.setText(str(i + 1))
            b.setToolTip(f"Размер карты {i + 1} (клавиша {i + 1})")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=i: self.set_map_size(k))
            mtop.addWidget(b)
            self.size_btns.append(b)
        mtop.addWidget(self._tool("zoom_out", "Отдалить", lambda: self.map.zoom_out()))
        mtop.addWidget(self._tool("zoom_in", "Приблизить", lambda: self.map.zoom_in()))
        ml.addLayout(mtop)
        self.map = SlippyMap(win.tiles)
        self.map.guessed.connect(self._guessed)
        self.map.interacted.connect(lambda: self.expand(True))
        ml.addWidget(self.map, 1)
        self.country_box = QComboBox()
        self.country_box.setEditable(True)
        self.country_box.setInsertPolicy(QComboBox.NoInsert)
        for name, iso in geo.countries().names():
            self.country_box.addItem(name, iso)
        self.country_box.setCurrentIndex(-1)
        comp = QCompleter([n for n, _ in geo.countries().names()], self.country_box)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        self.country_box.setCompleter(comp)
        self.country_box.lineEdit().setPlaceholderText("Какая это страна?")
        ml.addWidget(self.country_box)
        self.answer_btn = QPushButton("Ответить")
        self.answer_btn.setObjectName("Accent")
        self.answer_btn.clicked.connect(self.answer)
        self.answer_btn.setEnabled(False)
        ml.addWidget(self.answer_btn)
        self.map_panel.installEventFilter(self)
        # round result overlay
        self.result = Overlay(self.viewer_host)
        self.result.setObjectName("ResultPanel")
        rl = QVBoxLayout(self.result)
        rl.setContentsMargins(20, 14, 20, 14)
        self.res_title = label("", "ResultTitle")
        self.res_text = label("", "OverlayText")
        self.res_text.setWordWrap(True)
        rl.addWidget(self.res_title)
        rl.addWidget(self.res_text)
        rrow = QHBoxLayout()
        rrow.addStretch(1)
        self.next_btn = QPushButton("Следующий раунд")
        self.next_btn.setObjectName("Accent")
        self.next_btn.clicked.connect(self.next_round)
        rrow.addWidget(self.next_btn)
        rl.addLayout(rrow)
        self.result.hide()
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self._tick)
        for keys, fn in (("Space", self.answer_or_next), ("N", self.next_round), ("Esc", self.confirm_quit),
                         ("1", lambda: self.set_map_size(0)), ("2", lambda: self.set_map_size(1)),
                         ("3", lambda: self.set_map_size(2)), ("4", lambda: self.set_map_size(3)),
                         ("R", self.go_start)):
            sc = QShortcut(QKeySequence(keys), self)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)
        self.expanded = self.pinned
        self._relayout()

    def _tool(self, icon, tip, fn):
        b = QToolButton()
        b.setIcon(icons.icon(icon, "#FFFFFF", theme.CURRENT.get("accent", "#D97757")))
        b.setIconSize(QSize(18, 18))
        b.setToolTip(tip)
        b.clicked.connect(fn)
        return b

    # -- layout of the overlays
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._relayout()

    def _relayout(self):
        W, H = self.viewer_host.width(), self.viewer_host.height()
        self.top.adjustSize()
        self.top.setGeometry(12, 12, max(360, self.top.sizeHint().width()), 40)
        self.ctrl.adjustSize()
        cw = self.ctrl.sizeHint().width()
        self.ctrl.setGeometry((W - cw) // 2, H - 56, cw, 40)
        self.attr.adjustSize()
        self.attr.move(12, H - self.attr.height() - 12)
        self.loading.setGeometry((W - 220) // 2, (H - 44) // 2, 220, 44)
        big = self.expanded or self.pinned
        mw, mh = MAP_SIZES[min(3, max(0, self.map_size))] if big else (220, 150)
        mw, mh = min(mw, W - 24), min(mh, H - 70)
        self.map_panel.setGeometry(W - mw - 12, H - mh - 12, mw, mh)
        self.result.adjustSize()
        rw = min(520, W - 24)
        self.result.setGeometry((W - rw) // 2, H - self.result.sizeHint().height() - 70, rw, self.result.sizeHint().height())
        for i, b in enumerate(self.size_btns):
            b.setChecked(i == self.map_size)
        for b in self.size_btns + [self.pin_btn]:
            b.setVisible(big)

    def eventFilter(self, obj, e):
        if obj is self.map_panel:
            if e.type() == QEvent.Enter:
                self.expand(True)
            elif e.type() == QEvent.Leave and not self.pinned and not self.result_shown:
                self.expand(False)
        return super().eventFilter(obj, e)

    def expand(self, on):
        if self.expanded != on:
            self.expanded = on
            self._relayout()

    def toggle_pin(self):
        self.pinned = not self.pinned
        self.win.settings["map_pinned"] = self.pinned
        self.win.settings.save()
        self.pin_btn.setIcon(icons.icon("pinned" if self.pinned else "pin", "#FFFFFF", theme.CURRENT.get("accent", "#D97757")))
        self.expand(True)

    def set_map_size(self, k):
        self.map_size = max(0, min(3, k))
        self.win.settings["map_size"] = self.map_size
        self.win.settings.save()
        self.expand(True)
        self._relayout()

    # -- game flow
    def begin(self, game):
        self.game = game
        self.result_shown = False
        self.stack.setCurrentWidget(self.viewer_host)
        self.map_lbl.setText(game.config.area.name + " · " + MODES.get(game.config.mode, ""))
        streak = game.config.mode == "streak"
        self.map.setVisible(not streak)
        self.country_box.setVisible(streak)
        self.answer_btn.setText("Ответить")
        game.loading.connect(self.show_loading)
        game.round_ready.connect(self.show_round)
        game.round_done.connect(self.show_result)
        game.finished.connect(self.show_final)
        game.failed.connect(self.show_failed)
        self.show_loading("Ищем место…")
        game.start()

    def show_loading(self, text):
        self.loading.setText(text)
        self.loading.show()
        self.loading.raise_()

    def _ensure_sv(self):
        key = (self.win.settings.get("google_key") or "").strip()
        if self.sv_panel is not None and self.sv_key == key:
            return self.sv_panel
        if self.sv_panel is not None:
            self.viewers.removeWidget(self.sv_panel)
            self.sv_panel.deleteLater()
            self.sv_panel = None
        panel = sv.make_panel(key, self.viewers)
        if panel is None:
            return None
        panel.failed.connect(lambda m: self.win.toast(m))
        self.viewers.addWidget(panel)
        self.sv_panel, self.sv_key = panel, key
        return panel

    def show_round(self, index, loc, path):
        g = self.game
        self.result.hide()
        self.result_shown = False
        self.loading.hide()
        self.map.reset()
        self.map.set_view(20.0, 0.0, 1)
        self.map.locked = False
        self.country_box.setCurrentIndex(-1)
        self.country_box.lineEdit().clear()
        self.answer_btn.setEnabled(False)
        self.round_lbl.setText("Серия: %d" % g.streak if g.config.mode == "streak" else f"Раунд {index + 1} / {g.config.rounds}")
        self.score_lbl.setText(f"{fmt_points(g.total())} очков")
        opts = g.config.opts()
        self.current_loc = loc
        if loc.source == "streetview":
            panel = self._ensure_sv()
            if panel is None:
                self.win.toast("Нет QtWebEngine — Street View недоступен, выберите другой источник")
                return
            self.viewers.setCurrentWidget(panel)
            panel.show_pano(loc.id, dict(opts, heading=loc.heading))
        elif loc.pano:
            img = QImage(path) if path else QImage()
            self.pano.set_image(img, loc.heading)
            self.pano.locked = not opts["pan"]
            self.pano.zoomable = opts["zoom"]
            self.viewers.setCurrentWidget(self.pano)
            self.pano.setFocus()
        else:
            self.flat.set_image(QImage(path) if path else QImage())
            self.flat.locked = not opts["pan"]
            self.flat.zoomable = opts["zoom"]
            self.viewers.setCurrentWidget(self.flat)
        moves = opts["move"] and g.source.moves and loc.source != "streetview"
        for b in (self.btn_prev, self.btn_next):
            b.setVisible(moves)
        self.btn_home.setVisible(opts["move"] and g.source.moves)
        self.btn_zin.setVisible(opts["zoom"] and loc.source != "streetview")
        self.btn_zout.setVisible(opts["zoom"] and loc.source != "streetview")
        self.attr.setText(loc.attribution + (f" · {loc.extra.get('title')}" if loc.extra.get("title") else ""))
        self.attr.setVisible(bool(loc.attribution))
        self.start_loc = loc
        self.timer.start() if g.config.time_limit else self.timer.stop()
        self._tick()
        self.expand(self.pinned)
        self._relayout()

    def _tick(self):
        g = self.game
        if not g or self.result_shown:
            self.timer_lbl.setText("")
            return
        left = g.time_left()
        if left is None:
            self.timer_lbl.setText("")
            return
        self.timer_lbl.setText(f"⏱ {int(left) // 60}:{int(left) % 60:02d}")
        if left <= 0:
            self.timer.stop()
            g.timeout()

    def _guessed(self, lat, lon):
        self.answer_btn.setEnabled(True)
        self.answer_btn.setText("Ответить")

    def answer(self):
        g = self.game
        if not g or self.result_shown:
            return
        if g.config.mode == "streak":
            i = self.country_box.currentIndex()
            text = self.country_box.currentText().strip().lower()
            iso = self.country_box.itemData(i) if i >= 0 else next((c for n, c in geo.countries().names() if n.lower() == text), None)
            if not iso:
                self.win.toast("Выберите страну из списка")
                return
            g.guess(iso=iso)
        else:
            if not self.map.guess:
                self.win.toast("Поставьте метку на карте")
                return
            g.guess(*self.map.guess)

    def answer_or_next(self):
        if self.result_shown:
            self.next_round()
        else:
            self.answer()

    def show_result(self, res):
        g = self.game
        self.result_shown = True
        self.timer.stop()
        self.map.locked = True
        self.map.truth = (res["lat"], res["lon"])
        if g.config.mode == "streak":
            truth = res.get("country") or "неизвестно"
            guessed = geo.countries().by_iso.get(res.get("guess_iso") or "", {}).get("name", "—")
            self.res_title.setText("Верно!" if res["correct"] else "Мимо")
            self.res_text.setText(f"Это {truth}. Ваш ответ: {guessed}. Серия: {res['streak']}")
            self.map.show()
            self.map.fit([(res["lat"], res["lon"])])
            self.map.set_view(res["lat"], res["lon"], max(3, self.map.zoom - 2))
        else:
            if res["distance"] is None:
                self.res_title.setText("Время вышло")
                self.res_text.setText(f"Место: {res.get('country') or 'неизвестно'} · 0 очков")
                self.map.fit([(res["lat"], res["lon"])])
            else:
                self.res_title.setText(f"{fmt_points(res['score'])} очков")
                self.res_text.setText(f"{geo.fmt_distance(res['distance'])} от места · {res.get('country') or ''} · {res['time']:.0f} с")
                self.map.fit([(res["lat"], res["lon"]), res["guess"]])
        self.score_lbl.setText(f"{fmt_points(g.total())} очков")
        last = (g.index + 1 >= g.config.rounds) or (g.config.mode == "streak" and not res.get("correct"))
        self.next_btn.setText("Итоги" if last else "Следующий раунд")
        self.answer_btn.setEnabled(False)
        self.expand(True)
        self.result.show()
        self.result.raise_()
        self._relayout()

    def next_round(self):
        if not self.game or not self.result_shown:
            return
        self.result.hide()
        if self.game.over:
            self.show_final(self.game.finish() or self.game_summary)
            return
        self.show_loading("Ищем место…")
        self.game.next_round()

    def show_final(self, summary):
        self.game_summary = summary
        self.timer.stop()
        clear_layout(self.results_lay)
        title = f"Серия: {summary['streak']} подряд" if summary["mode"] == "streak" else f"{fmt_points(summary['score'])} из {fmt_points(summary['max'])}"
        self.results_lay.addWidget(label(title, "Title"))
        self.results_lay.addWidget(label(f"{summary['map_name']} · {MODES.get(summary['mode'], '')} · {summary['nick']}", "Muted"))
        self.results_lay.addSpacing(10)
        for r in summary["rounds"]:
            row = QFrame()
            row.setObjectName("Card")
            hl = QHBoxLayout(row)
            hl.setContentsMargins(14, 10, 14, 10)
            hl.addWidget(label(f"Раунд {r['round']}", "CardTitle"))
            if summary["mode"] == "streak":
                hl.addWidget(label(f"{r.get('country') or '?'} — {'верно' if r.get('correct') else 'мимо'}", "Muted"), 1)
            else:
                d = "время вышло" if r["distance"] is None else geo.fmt_distance(r["distance"])
                hl.addWidget(label(f"{d} · {r.get('country') or ''}", "Muted"), 1)
            hl.addWidget(label(fmt_points(r["score"]), "H3"))
            self.results_lay.addWidget(row)
        self.results_lay.addSpacing(10)
        btns = QHBoxLayout()
        again = QPushButton("Играть ещё")
        again.setObjectName("Accent")
        again.clicked.connect(lambda: self.win.start_game(mode=summary["mode"], map_key=summary["map"]))
        home = QPushButton("На главную")
        home.clicked.connect(lambda: self.win.go("home"))
        btns.addWidget(again)
        btns.addWidget(home)
        btns.addStretch(1)
        self.results_lay.addLayout(btns)
        self.results_lay.addStretch(1)
        self.stack.setCurrentWidget(self.results)
        self.win.home.refresh()

    def show_failed(self, text):
        self.loading.hide()
        QMessageBox.warning(self, "Не получилось", text)
        self.win.go("home")

    # -- movement / zoom
    def go_start(self):
        if not self.game:
            return
        if self.viewers.currentWidget() is self.sv_panel and self.sv_panel is not None:
            self.sv_panel.reset()
        elif self.current_loc is not self.start_loc:
            self._show_image(self.start_loc)
        else:
            self.pano.reset_view()
            self.flat.reset_view()

    def _show_image(self, loc):
        self.show_loading("Переходим…")

        def job():
            return loc, str(self.game.cache.fetch(loc.url))

        def done(r):
            loc_, path = r
            self.loading.hide()
            self.current_loc = loc_
            if loc_.pano:
                self.pano.set_image(QImage(path), loc_.heading)
                self.viewers.setCurrentWidget(self.pano)
            else:
                self.flat.set_image(QImage(path))
                self.viewers.setCurrentWidget(self.flat)

        self.win.runner.run(job, done, lambda e: (self.loading.hide(), self.win.toast(str(e))))

    def _move(self, forward):
        if not self.game or not self.game.source.moves or self.game.config.no_move:
            return
        loc = self.current_loc
        self.show_loading("Ищем следующий снимок…")

        def job():
            prev, nxt = self.game.source.neighbors(loc)
            return nxt if forward else prev

        def done(n):
            self.loading.hide()
            if n is None:
                self.win.toast("Дальше дороги нет")
            else:
                self._show_image(n)

        self.win.runner.run(job, done, lambda e: (self.loading.hide(), self.win.toast(str(e))))

    def move_next(self):
        self._move(True)

    def move_prev(self):
        self._move(False)

    def _zoom(self, d):
        w = self.viewers.currentWidget()
        if w is self.pano:
            self.pano.fov = max(30.0, min(110.0, self.pano.fov - d * 10))
            self.pano.update()
        elif w is self.flat:
            self.flat.zoom = max(1.0, min(4.0, self.flat.zoom * (1.25 if d > 0 else 0.8)))
            self.flat.update()

    def confirm_quit(self):
        if self.game and not self.game.over and self.stack.currentWidget() is self.viewer_host:
            if QMessageBox.question(self, "Выйти", "Прервать игру? Результат не сохранится.") != QMessageBox.Yes:
                return
            self.game.over = True
            self.timer.stop()
        self.win.go("home")


# ---------------------------------------------------------------- records

class RecordsPage(QScrollArea):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setObjectName("Page")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(32, 26, 32, 26)
        lay.setSpacing(12)
        head = QHBoxLayout()
        head.addWidget(label("Рекорды", "Title"))
        head.addStretch(1)
        self.map_box = QComboBox()
        self.map_box.addItem("Все карты", "")
        for a in maps.regions():
            self.map_box.addItem(a.name, a.key)
        self.mode_box = QComboBox()
        self.mode_box.addItem("Все режимы", "")
        for k, v in MODES.items():
            self.mode_box.addItem(v, k)
        for b in (self.map_box, self.mode_box):
            b.currentIndexChanged.connect(lambda _=0: self.refresh())
            head.addWidget(b)
        lay.addLayout(head)
        self.list = QVBoxLayout()
        self.list.setSpacing(8)
        lay.addLayout(self.list)
        lay.addStretch(1)
        self.setWidget(body)

    def refresh(self):
        clear_layout(self.list)
        games = self.win.records.top(self.map_box.currentData() or None, self.mode_box.currentData() or None, 20)
        if not games:
            self.list.addWidget(label("Рекордов пока нет.", "Hint"))
        for i, g in enumerate(games):
            row = RecordRow(g)
            row.layout().insertWidget(0, label(f"{i + 1}.", "H3"))
            self.list.addWidget(row)


# ---------------------------------------------------------------- settings

class SettingsPage(QScrollArea):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setObjectName("Page")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(32, 26, 32, 26)
        lay.setSpacing(12)
        s = win.settings
        lay.addWidget(label("Настройки", "Title"))
        lay.addWidget(label("ИГРОК", "Section"))
        self.nick = QLineEdit(s.get("nickname") or "")
        self.nick.setPlaceholderText("Ник для рекордов")
        self.nick.setMaximumWidth(320)
        self.nick.editingFinished.connect(lambda: self._set("nickname", self.nick.text().strip()))
        lay.addWidget(self.nick)
        lay.addWidget(label("ИСТОЧНИКИ", "Section"))
        box = QFrame()
        box.setObjectName("Box")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(16, 14, 16, 14)
        bl.setSpacing(8)
        bl.addWidget(label("Google Street View — ключ Maps Platform", "H3"))
        self.gkey, row = self._secret("google_key", "AIza…")
        bl.addLayout(row)
        self.sv_official = QCheckBox("Только официальные панорамы Google (без пользовательских)")
        self.sv_official.setChecked(bool(s.get("sv_official_only", True)))
        self.sv_official.toggled.connect(lambda v: self._set("sv_official_only", v))
        bl.addWidget(self.sv_official)
        hint = label("Включите Maps JavaScript API и Street View Static API в console.cloud.google.com. Поиск точек бесплатный, "
                     "показ панорамы ≈ $14 за 1000 раундов — бесплатного кредита $200/мес хватает на ~14 000 раундов.", "Hint", wrap=True)
        bl.addWidget(hint)
        link = QPushButton("Открыть console.cloud.google.com")
        link.setObjectName("Link")
        link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://console.cloud.google.com/apis/credentials")))
        bl.addWidget(link, 0, Qt.AlignLeft)
        bl.addWidget(label("Mapillary — client token", "H3"))
        self.mkey, row = self._secret("mapillary_token", "MLY|…")
        bl.addLayout(row)
        bl.addWidget(label("Бесплатно: mapillary.com → Developers → Register application → Client token. Панорамы улиц, лицензия CC BY-SA.", "Hint", wrap=True))
        link2 = QPushButton("Открыть mapillary.com/dashboard/developers")
        link2.setObjectName("Link")
        link2.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.mapillary.com/dashboard/developers")))
        bl.addWidget(link2, 0, Qt.AlignLeft)
        bl.addWidget(label("Wikimedia Commons работает без ключа (фотографии мест, автор указывается на экране).", "Hint", wrap=True))
        lay.addWidget(box)
        lay.addWidget(label("КЕШ", "Section"))
        crow = QHBoxLayout()
        crow.addWidget(label("Лимит кеша картинок, МБ"))
        self.cache_mb = QSpinBox()
        self.cache_mb.setRange(50, 5000)
        self.cache_mb.setSingleStep(50)
        self.cache_mb.setValue(int(s.get("cache_mb") or 500))
        self.cache_mb.valueChanged.connect(lambda v: self._set("cache_mb", v))
        crow.addWidget(self.cache_mb)
        self.cache_lbl = label("", "Hint")
        crow.addWidget(self.cache_lbl)
        clear = QPushButton("Очистить кеш")
        clear.clicked.connect(self.clear_cache)
        crow.addWidget(clear)
        crow.addStretch(1)
        lay.addLayout(crow)
        lay.addWidget(label("ОФОРМЛЕНИЕ", "Section"))
        trow = QHBoxLayout()
        trow.addWidget(label("Тема"))
        self.theme_box = QComboBox()
        for k, v in (("system", "Как в системе"), ("light", "Светлая"), ("dark", "Тёмная")):
            self.theme_box.addItem(v, k)
        self.theme_box.setCurrentIndex(max(0, self.theme_box.findData(s.get("theme", "system"))))
        self.theme_box.currentIndexChanged.connect(lambda _=0: self._set("theme", self.theme_box.currentData(), True))
        trow.addWidget(self.theme_box)
        trow.addSpacing(16)
        trow.addWidget(label("Акцент"))
        self.swatches = {}
        for key, (hexv, name) in theme.ACCENTS.items():
            b = QToolButton()
            b.setFixedSize(26, 26)
            b.setToolTip(name)
            b.setCheckable(True)
            b.setStyleSheet(f"QToolButton {{ background: {hexv}; border-radius: 13px; border: 2px solid transparent; }}"
                            f"QToolButton:checked {{ border: 2px solid {theme.CURRENT.get('text', '#141413')}; }}")
            b.clicked.connect(lambda _=False, k=key: self._set("accent", k, True))
            trow.addWidget(b)
            self.swatches[key] = b
        trow.addStretch(1)
        lay.addLayout(trow)
        self.serif = QCheckBox("Заголовки с засечками")
        self.serif.setChecked(bool(s.get("serif_headings", True)))
        self.serif.toggled.connect(lambda v: self._set("serif_headings", v, True))
        lay.addWidget(self.serif)
        lay.addStretch(1)
        lay.addWidget(label(f"Тета {__version__} · карта © OpenStreetMap contributors · панорамы © Google / Mapillary / Wikimedia Commons", "Hint", wrap=True))
        self.setWidget(body)
        self._sync_look()

    def _secret(self, key, placeholder):
        edit = QLineEdit(self.win.settings.get(key) or "")
        edit.setEchoMode(QLineEdit.Password)
        edit.setPlaceholderText(placeholder)
        edit.editingFinished.connect(lambda: self._set(key, edit.text().strip()))
        show = QToolButton()
        show.setIcon(ic("eye"))
        show.setCheckable(True)
        show.setToolTip("Показать")
        show.toggled.connect(lambda on: edit.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        row = QHBoxLayout()
        row.addWidget(edit, 1)
        row.addWidget(show)
        return edit, row

    def _set(self, key, value, look=False):
        self.win.settings[key] = value
        self.win.settings.save()
        if look:
            self.win.apply_theme()
        elif key in ("google_key", "mapillary_token"):
            self.win.home.hero.sync_from_settings()

    def _sync_look(self):
        acc = self.win.settings.get("accent") or "terracotta"
        for k, b in self.swatches.items():
            b.setChecked(k == acc)
        mb = ImageCache(self.win.settings).size() + tiles_size()
        self.cache_lbl.setText(f"сейчас {mb / 1048576:.0f} МБ")

    def clear_cache(self):
        ImageCache(self.win.settings).clear()
        self.win.tiles.mem.clear()
        self._sync_look()
        self.win.toast("Кеш очищен")

    def refresh(self):
        self._sync_look()


# ---------------------------------------------------------------- main window

class Toast(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAlignment(Qt.AlignCenter)
        self.hide()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def show_text(self, text):
        self.setText(text)
        self.adjustSize()
        p = self.parent()
        self.move((p.width() - self.width()) // 2, p.height() - self.height() - 24)
        self.show()
        self.raise_()
        self.timer.start(2600)


class MainWindow(QMainWindow):
    NAV = (("home", "Главная", "home"), ("records", "Рекорды", "trophy"), ("settings", "Настройки", "settings"))

    def __init__(self, app, settings=None, records=None):
        super().__init__()
        self.app = app
        self.settings = settings or Settings()
        self.records = records or Records()
        self.runner = net.Runner(6)
        self.tiles = TileCache(self.runner)
        self.setWindowTitle(APP_NAME)
        self.setObjectName("Main")
        self.resize(1240, 800)
        self.setMinimumSize(980, 640)
        self.apply_theme(rebuild=False)
        self.root = QStackedWidget()
        self.setCentralWidget(self.root)
        self.splash = SplashPage()
        self.splash.finished.connect(self.show_main)
        self.root.addWidget(self.splash)
        shell = QWidget()
        self.shell_lay = QHBoxLayout(shell)
        self.shell_lay.setContentsMargins(0, 0, 0, 0)
        self.shell_lay.setSpacing(0)
        self.side = QFrame()
        self.side.setObjectName("Side")
        self.side.setFixedWidth(200)
        self.side_lay = QVBoxLayout(self.side)
        self.side_lay.setContentsMargins(12, 18, 12, 14)
        self.side_lay.setSpacing(3)
        self.rail = QFrame()
        self.rail.setObjectName("Side")
        self.rail.setFixedWidth(56)
        self.rail_lay = QVBoxLayout(self.rail)
        self.rail_lay.setContentsMargins(8, 16, 8, 12)
        self.rail_lay.setSpacing(6)
        self.pages = QStackedWidget()
        self.shell_lay.addWidget(self.side)
        self.shell_lay.addWidget(self.rail)
        self.shell_lay.addWidget(self.pages, 1)
        self.root.addWidget(shell)
        self.home = HomePage(self)
        self.game_page = GamePage(self)
        self.records_page = RecordsPage(self)
        self.settings_page = SettingsPage(self)
        for p in (self.home, self.game_page, self.records_page, self.settings_page):
            self.pages.addWidget(p)
        self.toast_w = Toast(self)
        self.place_side()
        self.build_side()
        for keys, fn in (("Ctrl+1", lambda: self.go("home")), ("Ctrl+2", lambda: self.go("records")),
                         ("Ctrl+,", lambda: self.go("settings")), ("Ctrl+\\", self.toggle_sidebar)):
            sc = QShortcut(QKeySequence(keys), self)
            sc.activated.connect(fn)
        self.current_page = "home"
        self.game = None

    def start(self, fast=False):
        self.root.setCurrentWidget(self.splash)
        self.splash.start(fast)

    def show_main(self):
        self.root.setCurrentIndex(1)
        self.go("home")

    def toast(self, text):
        self.toast_w.show_text(text)

    # -- theme / side bar
    def apply_theme(self, rebuild=True):
        mode = self.settings.get("theme", "system")
        if mode == "system":
            try:
                dark = self.app.styleHints().colorScheme() == Qt.ColorScheme.Dark
            except Exception:
                dark = self.app.palette().window().color().lightness() < 128
        else:
            dark = mode == "dark"
        colors = theme.compose(theme.DARK if dark else theme.LIGHT, self.settings)
        theme.use(colors)
        self.app.setStyleSheet(theme.stylesheet(colors) + theme.extra(colors))
        if rebuild:
            self.place_side()
            self.build_side()
            self.settings_page._sync_look()
            self.home.refresh()

    def place_side(self):
        hidden = bool(self.settings.get("sidebar_hidden"))
        self.side.setVisible(not hidden)
        self.rail.setVisible(hidden)

    def toggle_sidebar(self):
        self.settings["sidebar_hidden"] = not self.settings.get("sidebar_hidden")
        self.settings.save()
        self.place_side()
        self.build_side()
        self.go(self.current_page)

    def build_side(self):
        clear_layout(self.rail_lay)
        logo = label(LOGO, "Gamma")
        logo.setAlignment(Qt.AlignCenter)
        self.rail_lay.addWidget(logo)
        expand = QToolButton()
        expand.setObjectName("CollapseBtn")
        expand.setText("»")
        expand.setToolTip("Показать панель  ⌘\\")
        expand.clicked.connect(self.toggle_sidebar)
        self.rail_lay.addWidget(expand, 0, Qt.AlignHCenter)
        self.rail_nav = {}
        for key, tip, icon in self.NAV:
            b = QToolButton()
            b.setIcon(ic(icon))
            b.setIconSize(QSize(18, 18))
            b.setToolTip(tip)
            b.setCheckable(True)
            b.setFixedSize(38, 34)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            self.rail_lay.addWidget(b, 0, Qt.AlignHCenter)
            self.rail_nav[key] = b
        self.rail_lay.addStretch(1)
        clear_layout(self.side_lay)
        brand = QHBoxLayout()
        brand.addWidget(label(LOGO, "Gamma"))
        brand.addWidget(label(APP_NAME, "Logo"))
        brand.addStretch(1)
        hide = QToolButton()
        hide.setObjectName("CollapseBtn")
        hide.setText("«")
        hide.setToolTip("Скрыть панель  ⌘\\")
        hide.clicked.connect(self.toggle_sidebar)
        brand.addWidget(hide)
        self.side_lay.addLayout(brand)
        self.side_lay.addSpacing(14)
        self.nav = {}
        for key, text, icon in self.NAV:
            b = QPushButton(text)
            b.setIcon(ic(icon))
            b.setIconSize(QSize(16, 16))
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            self.side_lay.addWidget(b)
            self.nav[key] = b
        self.side_lay.addStretch(1)
        daily = self.records.daily_result()
        self.side_lay.addWidget(label("Задание дня: " + (f"{fmt_points(daily)}" if daily is not None else "не сыграно"), "Hint"))
        self.side_lay.addWidget(label(f"версия {__version__}", "Hint"))

    def go(self, key):
        page = {"home": self.home, "records": self.records_page, "settings": self.settings_page, "game": self.game_page}[key]
        self.current_page = key
        if key == "home":
            self.home.refresh()
        elif key == "records":
            self.records_page.refresh()
        elif key == "settings":
            self.settings_page.refresh()
        self.pages.setCurrentWidget(page)
        for d in (self.nav, getattr(self, "rail_nav", {})):
            for k, b in d.items():
                b.setChecked(k == key)

    # -- game
    def start_game(self, mode=None, map_key=None, source=None):
        s = self.settings
        if mode == "daily" and self.records.daily_result() is not None:
            if QMessageBox.question(self, "Задание дня", "Сегодня уже сыграно. Сыграть ещё раз (результат не засчитается)?") != QMessageBox.Yes:
                return
        cfg = Config(s, mode=mode, map_key=map_key, source=source)
        src = next((x for x in all_sources(s) if x.name == cfg.source), None)
        if src is None or not src.available():
            self.toast((src.hint() if src else "Источник недоступен"))
            self.go("settings")
            return
        if cfg.source == "streetview" and not sv.webengine_available():
            self.toast("Нет QtWebEngine: Street View недоступен, выберите Mapillary или Commons")
            return
        self.game = Game(s, self.runner, cfg, self.records, source=src)
        self.go("game")
        self.game_page.begin(self.game)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.toast_w.isVisible():
            self.toast_w.move((self.width() - self.toast_w.width()) // 2, self.height() - self.toast_w.height() - 24)


def main():
    if "QTWEBENGINE_CHROMIUM_FLAGS" not in os.environ and not IS_MAC:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--no-sandbox"
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("Lotus")
    icon_file = resource_path("assets", "icon.png")
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))
    win = MainWindow(app)
    try:
        app.styleHints().colorSchemeChanged.connect(lambda *_: win.apply_theme())
    except Exception:
        pass
    win.show()
    win.start()
    return app.exec()
