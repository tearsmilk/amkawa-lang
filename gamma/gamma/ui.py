"""Main window: Главная (actions, sound, replay, recent captures), Настройки, Горячие клавиши."""
import sys
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
                               QFrame, QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
                               QMenu, QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from . import APP_NAME, LOGO, __version__, ffmpeg, hotkeys, icons, macos, theme
from .app import Gamma
from .overlay import fmt_time
from .paths import DEFAULT_HOTKEYS, HOTKEY_TITLES, Settings, resource_path

IS_MAC = sys.platform == "darwin"
IMAGE_EXT = {".png", ".jpg", ".jpeg"}
VIDEO_EXT = {".mp4", ".mov", ".mkv"}
AUDIO_MODES = (("none", "Без звука", "mic_off"), ("mic", "Микрофон", "mic"), ("system", "Звук системы", "speaker"),
               ("both", "Микрофон + система", "speaker"))


_THEMED = []        # (widget, icon name, pixmap size) re-tinted when the theme changes
_INK = ["#141413"]


def _tint(w, name, size):
    if isinstance(w, QLabel):
        w.setPixmap(icons.pixmap(name, _INK[0], size=size or 64))
    else:
        w.setIcon(icons.icon(name, _INK[0]))


def set_icon(w, name, size=None):
    _THEMED.append((w, name, size))
    _tint(w, name, size)


def retint(ink):
    _INK[0] = ink
    for item in list(_THEMED):
        try:
            _tint(*item)
        except RuntimeError:  # widget is gone
            _THEMED.remove(item)


def label(text, name=None, wrap=False):
    w = QLabel(text)
    if name:
        w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


def kbd(hk):
    w = QLabel(hk["text"] if hk else "—")
    w.setObjectName("Kbd")
    return w


class ActionCard(QPushButton):
    def __init__(self, icon, title, text, hk):
        super().__init__()
        self.setObjectName("Card")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(132)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(6)
        top = QHBoxLayout()
        ic = QLabel()
        set_icon(ic, icon, 64)
        ic.setFixedSize(32, 32)
        ic.setScaledContents(True)
        top.addWidget(ic)
        top.addStretch(1)
        self.key = kbd(hk)
        top.addWidget(self.key, 0, Qt.AlignTop)
        lay.addLayout(top)
        t = label(title, "CardTitle")
        lay.addWidget(t)
        d = label(text, "Hint", wrap=True)
        lay.addWidget(d)
        lay.addStretch(1)
        for w in (ic, t, d, self.key):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_hotkey(self, hk):
        self.key.setText(hk["text"] if hk else "—")


class HotkeyEdit(QPushButton):
    """Click, press a combination. Esc cancels, ⌫ clears."""

    def __init__(self, manager, value, on_change):
        super().__init__()
        self.setObjectName("Hotkey")
        self.manager = manager
        self.value = value
        self.on_change = on_change
        self.listening = False
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self.listen)
        self._show()

    def _show(self):
        self.setText("Нажмите сочетание…" if self.listening else (self.value["text"] if self.value else "Не задано"))
        self.setChecked(self.listening)

    def listen(self):
        self.listening = True
        self.manager.suspend()
        self.grabKeyboard()
        self._show()

    def _done(self):
        self.listening = False
        self.manager.resume()
        self.releaseKeyboard()
        self._show()

    def set_value(self, hk):
        self.value = hk
        self._show()

    def keyPressEvent(self, e):
        if not self.listening:
            return super().keyPressEvent(e)
        if e.key() == Qt.Key_Escape and not e.modifiers():
            self._done()
            return
        if e.key() in (Qt.Key_Backspace, Qt.Key_Delete) and not e.modifiers():
            self.value = None
            self._done()
            self.on_change(None)
            return
        hk = hotkeys.from_event(e)
        if hk:
            self.value = hk
            self._done()
            self.on_change(hk)

    def focusOutEvent(self, e):
        if self.listening:
            self._done()
        super().focusOutEvent(e)


class HomePage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        g = win.gamma
        self.setObjectName("Page")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 28, 36, 24)
        lay.setSpacing(14)
        lay.addWidget(label("Что запишем?", "Title"))
        lay.addWidget(label("Снимки и видео экрана — целиком или выделенной области. Всё сохраняется в папки из "
                            "настроек, горячие клавиши работают из любой программы.", "Muted", wrap=True))
        grid = QGridLayout()
        grid.setSpacing(12)
        hk = g.settings.hotkeys()
        specs = [("shot_region", "shot_region", "Снимок области", "Выделите мышкой — сохранится и скопируется"),
                 ("shot_screen", "shot_screen", "Снимок экрана", "Весь экран под курсором одним нажатием"),
                 ("rec_region", "rec_region", "Запись области", "Выделите место на экране — запишется только оно"),
                 ("rec_screen", "rec_screen", "Запись экрана", "Весь экран; повторное нажатие — стоп")]
        self.cards = {}
        for i, (key, ic, title, text) in enumerate(specs):
            c = ActionCard(ic, title, text, hk.get(key))
            c.clicked.connect(lambda _=False, k=key: g.run_action(k, from_ui=True))
            grid.addWidget(c, 0, i)
            self.cards[key] = c
        lay.addLayout(grid)

        # sound
        row = QHBoxLayout()
        row.setSpacing(0)
        row.addWidget(label("Звук при записи", "Section"))
        row.addSpacing(12)
        self.audio_group = QButtonGroup(self)
        self.audio_buttons = {}
        for i, (key, title, ic) in enumerate(AUDIO_MODES):
            b = QPushButton(title)
            b.setObjectName("Seg")
            b.setCheckable(True)
            set_icon(b, ic)
            b.setIconSize(QSize(14, 14))
            r = "7px" if i in (0, len(AUDIO_MODES) - 1) else "0"
            b.setStyleSheet(f"QPushButton#Seg {{ border-top-left-radius: {'7px' if i == 0 else '0'};"
                            f" border-bottom-left-radius: {'7px' if i == 0 else '0'};"
                            f" border-top-right-radius: {r if i else '0'}; border-bottom-right-radius: {r if i else '0'}; }}")
            b.clicked.connect(lambda _=False, k=key: self.set_audio(k))
            self.audio_group.addButton(b)
            self.audio_buttons[key] = b
            row.addWidget(b)
        row.addSpacing(12)
        self.audio_hint = label("", "Hint")
        row.addWidget(self.audio_hint, 1)
        lay.addLayout(row)
        self.sync_audio()

        # replay
        self.replay_box = QFrame()
        self.replay_box.setObjectName("Box")
        rb = QHBoxLayout(self.replay_box)
        rb.setContentsMargins(16, 14, 16, 14)
        rb.setSpacing(14)
        ic = QLabel()
        set_icon(ic, "replay", 64)
        ic.setFixedSize(34, 34)
        ic.setScaledContents(True)
        rb.addWidget(ic, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(4)
        head = QHBoxLayout()
        head.addWidget(label("Откат", "H2"))
        self.replay_badge = label("", "Badge")
        head.addWidget(self.replay_badge)
        head.addStretch(1)
        col.addLayout(head)
        self.replay_text = label("", "Muted", wrap=True)
        col.addWidget(self.replay_text)
        self.replay_status = label("", "Hint")
        col.addWidget(self.replay_status)
        rb.addLayout(col, 1)
        btns = QVBoxLayout()
        self.replay_toggle = QPushButton()
        self.replay_toggle.clicked.connect(g.toggle_replay)
        btns.addWidget(self.replay_toggle)
        self.replay_save = QPushButton("Сохранить откат")
        self.replay_save.setObjectName("Accent")
        self.replay_save.clicked.connect(g.save_replay)
        btns.addWidget(self.replay_save)
        btns.addStretch(1)
        rb.addLayout(btns)
        lay.addWidget(self.replay_box)

        # recent
        rh = QHBoxLayout()
        rh.addWidget(label("Недавние", "H2"))
        rh.addStretch(1)
        for title, kind in (("Папка снимков", "shot"), ("Папка видео", "video")):
            b = QPushButton(title)
            b.setObjectName("Link")
            set_icon(b, "folder")
            b.clicked.connect(lambda _=False, k=kind: macos.open_file(g.settings.folder(k)))
            rh.addWidget(b)
        lay.addLayout(rh)
        self.recent = QListWidget()
        self.recent.setViewMode(QListWidget.IconMode)
        self.recent.setIconSize(QSize(176, 110))
        self.recent.setGridSize(QSize(196, 150))
        self.recent.setResizeMode(QListWidget.Adjust)
        self.recent.setMovement(QListWidget.Static)
        self.recent.setWordWrap(True)
        self.recent.setUniformItemSizes(True)
        self.recent.itemDoubleClicked.connect(lambda it: macos.open_file(it.data(Qt.UserRole)))
        self.recent.setContextMenuPolicy(Qt.CustomContextMenu)
        self.recent.customContextMenuRequested.connect(self._recent_menu)
        lay.addWidget(self.recent, 1)
        self.empty = label("Здесь появятся ваши снимки и записи.", "Hint")
        self.empty.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.empty)
        self._thumbs = {}
        self._queue = []
        self._thumb_timer = QTimer(self)
        self._thumb_timer.timeout.connect(self._next_thumb)

    # -- sound
    def set_audio(self, key):
        s = self.win.gamma.settings
        s["audio"] = key
        s.save()
        self.sync_audio()

    def sync_audio(self):
        g = self.win.gamma
        mode = g.settings.get("audio", "none")
        for k, b in self.audio_buttons.items():
            b.setChecked(k == mode)
        names, warn = g.audio_devices(mode) if mode != "none" else ([], "")
        if warn:
            self.audio_hint.setText("Нужен BlackHole — см. Настройки → Звук")
            self.audio_hint.setObjectName("Warn")
        else:
            nice = [("микрофон по умолчанию" if n == "default" else n) for n in names]
            self.audio_hint.setText(" + ".join(nice) if nice else "видео без звуковой дорожки")
            self.audio_hint.setObjectName("Hint")
        self.audio_hint.style().unpolish(self.audio_hint)
        self.audio_hint.style().polish(self.audio_hint)

    # -- replay
    def sync_replay(self):
        g = self.win.gamma
        s = g.settings
        on = g.replay_running()
        b, a = float(s.get("replay_before", 5)), float(s.get("replay_after", 1))
        hk = s.hotkey("replay_save")
        self.replay_text.setText(
            f"Гамма постоянно помнит последние {fmt_time(b * 60)} экрана. Нажмите "
            f"{hk['text'] if hk else '«Сохранить откат»'} — и получите видео: {fmt_time(b * 60)} до нажатия "
            f"+ {fmt_time(a * 60)} после (итого {fmt_time((a + b) * 60)}).")
        self.replay_toggle.setText("Выключить" if on else "Включить откат")
        self.replay_save.setEnabled(on)
        self.replay_badge.setText("● идёт" if on else "")
        self.replay_badge.setVisible(on)
        self.replay_box.setObjectName("ReplayOn" if on else "Box")
        self.replay_box.style().unpolish(self.replay_box)
        self.replay_box.style().polish(self.replay_box)
        if on:
            mb = g.replay.buffered()
            self.replay_status.setText(f"В буфере {fmt_time(min(mb, b * 60))} из {fmt_time(b * 60)} · "
                                       f"временные файлы удаляются при выключении")
        else:
            self.replay_status.setText("Выключен — включите, чтобы начать запоминать.")

    # -- recent files
    def refresh(self):
        s = self.win.gamma.settings
        files = []
        for kind in ("shot", "video"):
            folder = s.folder(kind)
            try:
                for p in folder.iterdir():
                    if p.suffix.lower() in IMAGE_EXT | VIDEO_EXT and not p.name.startswith("."):
                        files.append(p)
            except OSError:
                pass
        files = sorted(set(files), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:40]
        self.recent.clear()
        self._queue = []
        for p in files:
            it = QListWidgetItem(p.stem)
            it.setData(Qt.UserRole, str(p))
            it.setToolTip(str(p))
            it.setIcon(self._placeholder(p))
            self.recent.addItem(it)
            self._queue.append(it)
        self.empty.setVisible(not files)
        self.recent.setVisible(bool(files))
        self._thumb_timer.start(30)

    def _placeholder(self, p):
        pix = QPixmap(352, 220)
        pix.fill(QColor("#E9E6DC"))
        q = QPainter(pix)
        q.drawPixmap(146, 80, icons.pixmap("video" if p.suffix.lower() in VIDEO_EXT else "image", size=60))
        q.end()
        return QIcon(pix)

    def _next_thumb(self):
        if not self._queue:
            self._thumb_timer.stop()
            return
        it = self._queue.pop(0)
        try:
            p = Path(it.data(Qt.UserRole))
        except RuntimeError:
            return
        key = (str(p), p.stat().st_mtime if p.exists() else 0)
        pix = self._thumbs.get(key)
        if pix is None:
            if p.suffix.lower() in VIDEO_EXT:
                src = self.win.gamma.video_thumb(p)
            else:
                src = QPixmap(str(p))
            pix = self._frame(src, p.suffix.lower() in VIDEO_EXT)
            self._thumbs[key] = pix
        it.setIcon(QIcon(pix))

    @staticmethod
    def _frame(src, video):
        out = QPixmap(352, 220)
        out.fill(QColor("#E9E6DC"))
        if not src.isNull():
            sc = src.scaled(out.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            q = QPainter(out)
            q.drawPixmap((out.width() - sc.width()) // 2, (out.height() - sc.height()) // 2, sc)
            if video:
                q.setRenderHint(QPainter.Antialiasing)
                q.setPen(Qt.NoPen)
                q.setBrush(QColor(20, 20, 19, 150))
                q.drawEllipse(out.rect().center(), 30, 30)
                q.drawPixmap(out.rect().center().x() - 16, out.rect().center().y() - 16,
                             icons.pixmap("play", "#FFFFFF", "#FFFFFF", 32))
            q.end()
        return out

    def _recent_menu(self, pos):
        it = self.recent.itemAt(pos)
        if not it:
            return
        p = Path(it.data(Qt.UserRole))
        m = QMenu(self)
        m.addAction("Открыть", lambda: macos.open_file(p))
        m.addAction("Показать в Finder" if IS_MAC else "Показать в папке", lambda: macos.reveal(p))
        if p.suffix.lower() in IMAGE_EXT:
            m.addAction("Скопировать картинку", lambda: QApplication.clipboard().setImage(QPixmap(str(p)).toImage()))
        m.addAction("Скопировать путь", lambda: QApplication.clipboard().setText(str(p)))
        m.addSeparator()

        def trash():
            from PySide6.QtCore import QFile

            if not QFile.moveToTrash(str(p)):
                p.unlink(missing_ok=True)
            self.refresh()

        m.addAction("В корзину", trash)
        m.exec(self.recent.mapToGlobal(pos))


class SettingsPage(QScrollArea):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.s = win.gamma.settings
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("Page")
        self.setWidget(body)
        self.lay = QVBoxLayout(body)
        self.lay.setContentsMargins(36, 28, 36, 28)
        self.lay.setSpacing(10)
        self.lay.addWidget(label("Настройки", "Title"))

        self.section("Сохранение")
        self.dir_row("Видео", "video")
        self.dir_row("Снимки", "shot")
        self.combo("Формат видео", "video_format", [("mp4", "MP4 (H.264)"), ("mov", "MOV (QuickTime)"),
                                                   ("mkv", "MKV (не теряется при сбое)")])
        self.combo("Формат снимков", "shot_format", [("png", "PNG — без потерь"), ("jpg", "JPEG — меньше размер")])

        self.section("Видео")
        self.combo("Кадров в секунду", "fps", [(15, "15"), (24, "24"), (30, "30"), (60, "60")])
        self.combo("Качество", "quality", [(0, "Низкое — маленькие файлы"), (1, "Среднее"), (2, "Высокое"),
                                           (3, "Максимальное")])
        self.combo("Кодировщик", "encoder", [("hw", "Аппаратный (VideoToolbox) — меньше нагрузка"),
                                             ("x264", "Программный (x264) — совместимее")])
        self.combo("Размер", "max_height", [(0, "Как на экране (Retina — в полном разрешении)"),
                                           (2160, "Не больше 2160p"), (1440, "Не больше 1440p"),
                                           (1080, "Не больше 1080p"), (720, "Не больше 720p")])
        self.combo("Обратный отсчёт", "countdown", [(0, "Без отсчёта"), (3, "3 секунды"), (5, "5 секунд"),
                                                    (10, "10 секунд")])
        self.check("Показывать курсор", "cursor")
        self.check("Подсвечивать щелчки мыши", "clicks")
        self.check("Убирать окно Гаммы во время записи", "minimize")
        self.check("Не показывать окна Гаммы на снимках и записях (рамка, панель, уведомления)", "hide_windows")

        self.section("Звук")
        devs = ffmpeg.audio_devices() if IS_MAC else []
        self.combo("Микрофон", "mic_device", [("", "По умолчанию (как в системе)")] + [(d, d) for d in devs],
                   editable=not IS_MAC)
        sys_devs = [("", "Найти автоматически (BlackHole, Loopback…)")] + [(d, d) for d in devs]
        self.combo("Звук системы", "system_device", sys_devs, editable=not IS_MAC)
        self.note("macOS не отдаёт звук программ напрямую. Чтобы записывать звук системы, поставьте бесплатный "
                  "BlackHole 2ch (existential.audio/blackhole), в «Настройке Audio-MIDI» создайте «Устройство с "
                  "несколькими выходами» (динамики + BlackHole) и выберите его для вывода звука. Гамма сама найдёт "
                  "BlackHole. Режим звука выбирается на главной или при выделении области.")
        rr = QHBoxLayout()
        refresh = QPushButton("Обновить список устройств")
        refresh.clicked.connect(self.refresh_devices)
        rr.addWidget(refresh)
        rr.addStretch(1)
        self.lay.addLayout(rr)

        self.section("Снимки")
        self.check("Копировать снимок в буфер обмена", "clipboard")
        self.check("Показывать превью после снимка", "preview")
        self.check("Звук затвора", "shutter")
        self.check("Снимок области — сразу после выделения (иначе — кнопка «Снимок»)", "instant_shot")
        self.combo("Задержка", "shot_delay", [(0, "Без задержки"), (3, "3 секунды"), (5, "5 секунд"),
                                              (10, "10 секунд")])
        self.combo("«Снимок экрана»", "screen_mode", [("cursor", "Экран под курсором"),
                                                       ("all", "Все экраны одной картинкой")])

        self.section("Откат")
        self.spin("Помнить до нажатия, мин", "replay_before", 0.5, 30, 0.5)
        self.spin("Дописать после нажатия, мин", "replay_after", 0, 10, 0.5)
        screens = QApplication.screens()
        self.combo("Экран", "replay_screen", [(i, f"{i + 1}: {sc.name()} — {sc.geometry().width()}×"
                                                  f"{sc.geometry().height()}") for i, sc in enumerate(screens)])
        self.check("Включать откат при запуске Гаммы", "replay_on_start")
        self.disk = label("", "Hint", wrap=True)
        self.lay.addWidget(self.disk)
        self.note("Откат пишет экран и звук (по выбранному режиму) в кольцевой буфер во временной папке и хранит "
                  "только последние минуты. Изменения применяются при следующем включении.")
        self._disk()

        self.section("Разрешения macOS")
        self.perm = label("", "Hint", wrap=True)
        self.lay.addWidget(self.perm)
        pr = QHBoxLayout()
        b1 = QPushButton("Запись экрана…")
        set_icon(b1, "shield")
        b1.clicked.connect(lambda: (macos.request_screen_access(), macos.open_privacy("screen")))
        b2 = QPushButton("Микрофон…")
        set_icon(b2, "mic")
        b2.clicked.connect(lambda: macos.open_privacy("mic"))
        pr.addWidget(b1)
        pr.addWidget(b2)
        pr.addStretch(1)
        self.lay.addLayout(pr)
        self.sync_perm()

        self.section("Оформление")
        self.combo("Тема", "theme", [("system", "Как в системе"), ("light", "Светлая"), ("dark", "Тёмная")],
                   after=lambda: win.apply_theme())
        self.lay.addStretch(1)
        self.lay.addWidget(label(f"{APP_NAME} {__version__} · ffmpeg: {ffmpeg.ffmpeg_exe() or 'не найден'}", "Hint",
                                 wrap=True))

    # -- builders
    def section(self, title):
        self.lay.addSpacing(10)
        self.lay.addWidget(label(title.upper(), "Section"))

    def note(self, text):
        self.lay.addWidget(label(text, "Hint", wrap=True))

    def _row(self, title, widget):
        row = QHBoxLayout()
        t = label(title)
        t.setFixedWidth(210)
        row.addWidget(t)
        row.addWidget(widget, 1)
        self.lay.addLayout(row)

    def combo(self, title, key, options, after=None, editable=False):
        cb = QComboBox()
        cb.setEditable(editable)
        for val, text in options:
            cb.addItem(text, val)
        cur = self.s.get(key)
        idx = next((i for i, (v, _) in enumerate(options) if v == cur), -1)
        if idx < 0 and cur not in (None, ""):
            cb.addItem(str(cur), cur)
            idx = cb.count() - 1
        cb.setCurrentIndex(max(0, idx))

        def changed(i):
            self.s[key] = cb.itemData(i)
            self.s.save()
            self.win.settings_changed()
            if after:
                after()

        cb.currentIndexChanged.connect(changed)
        self._row(title, cb)
        setattr(self, "cb_" + key, cb)
        return cb

    def check(self, title, key):
        c = QCheckBox(title)
        c.setChecked(bool(self.s.get(key)))

        def changed(on):
            self.s[key] = bool(on)
            self.s.save()
            self.win.settings_changed()

        c.toggled.connect(changed)
        self.lay.addWidget(c)
        setattr(self, "ch_" + key, c)
        return c

    def spin(self, title, key, lo, hi, step):
        sp = QDoubleSpinBox()
        sp.setRange(lo, hi)
        sp.setSingleStep(step)
        sp.setDecimals(1)
        sp.setValue(float(self.s.get(key)))

        def changed(v):
            self.s[key] = float(v)
            self.s.save()
            self._disk()
            self.win.settings_changed()

        sp.valueChanged.connect(changed)
        self._row(title, sp)
        setattr(self, "sp_" + key, sp)
        return sp

    def dir_row(self, title, kind):
        row = QHBoxLayout()
        t = label(title)
        t.setFixedWidth(210)
        row.addWidget(t)
        path = label(str(self.s.folder(kind)), "Muted")
        path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path.setMinimumWidth(40)
        path.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        path.setToolTip(str(self.s.folder(kind)))
        row.addWidget(path, 1)
        pick = QPushButton("Выбрать…")

        def choose():
            d = QFileDialog.getExistingDirectory(self, f"Куда сохранять: {title.lower()}", str(self.s.folder(kind)))
            if d:
                self.s[kind + "_dir"] = d
                self.s.save()
                path.setText(str(self.s.folder(kind)))
                path.setToolTip(str(self.s.folder(kind)))
                self.win.settings_changed()

        pick.clicked.connect(choose)
        row.addWidget(pick)
        show = QPushButton()
        set_icon(show, "folder")
        show.setToolTip("Открыть папку")
        show.clicked.connect(lambda: macos.open_file(self.s.folder(kind)))
        row.addWidget(show)
        self.lay.addLayout(row)
        setattr(self, "dir_" + kind, path)

    def _disk(self):
        mins = float(self.s.get("replay_before", 5)) + float(self.s.get("replay_after", 1))
        mb = mins * 60 * 6.5 / 8  # ~6.5 Мбит/с for 1080p30 at "Высокое"
        self.disk.setText(f"Сохранённый откат длится {fmt_time(mins * 60)}; буфер на диске ≈ {int(mb)}–{int(mb * 3)} "
                          f"МБ (зависит от разрешения экрана и качества).")

    def refresh_devices(self):
        if not IS_MAC:
            return
        devs = [d for _, d in ffmpeg.list_devices(refresh=True)["audio"]]
        for key, first in (("mic_device", "По умолчанию (как в системе)"),
                           ("system_device", "Найти автоматически (BlackHole, Loopback…)")):
            cb = getattr(self, "cb_" + key)
            cb.blockSignals(True)
            cb.clear()
            cb.addItem(first, "")
            for d in devs:
                cb.addItem(d, d)
            cur = self.s.get(key) or ""
            i = cb.findData(cur)
            cb.setCurrentIndex(max(0, i))
            cb.blockSignals(False)
        self.win.settings_changed()

    def sync_perm(self):
        ok = macos.screen_access()
        if ok is None:
            self.perm.setText("Гамме нужны разрешения «Запись экрана» (для снимков и видео) и «Микрофон» (для звука). "
                              "macOS спросит при первом использовании; после выдачи доступа перезапустите Гамму.")
        elif ok:
            self.perm.setText("Запись экрана: разрешена ✓. Микрофон macOS спросит при первой записи со звуком.")
        else:
            self.perm.setText("Запись экрана: нет доступа — снимки покажут только обои. Нажмите «Запись экрана…», "
                              "включите Гамму в списке и перезапустите её.")


class HotkeysPage(QScrollArea):
    def __init__(self, win):
        super().__init__()
        self.win = win
        g = win.gamma
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("Page")
        self.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(36, 28, 36, 28)
        lay.setSpacing(10)
        lay.addWidget(label("Горячие клавиши", "Title"))
        where = ("Работают из любой программы, даже когда Гамма свёрнута." if g.hotkeys.available() == "global"
                 else "На этой системе клавиши работают, только когда окно Гаммы активно.")
        lay.addWidget(label(f"{where} Нажмите на поле и затем сочетание; ⌫ — очистить, Esc — отмена. "
                            "Системные ⇧⌘3 / ⇧⌘4 / ⇧⌘5 заняты macOS.", "Muted", wrap=True))
        lay.addSpacing(8)
        self.edits = {}
        self.warns = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        icon_for = {"shot_region": "shot_region", "shot_screen": "shot_screen", "rec_region": "rec_region",
                    "rec_screen": "rec_screen", "replay_save": "replay", "replay_toggle": "replay",
                    "show": "logo"}
        for r, (action, title) in enumerate(HOTKEY_TITLES.items()):
            ic = QLabel()
            set_icon(ic, icon_for[action], 40)
            ic.setFixedSize(20, 20)
            ic.setScaledContents(True)
            grid.addWidget(ic, r, 0)
            grid.addWidget(label(title), r, 1)
            ed = HotkeyEdit(g.hotkeys, g.settings.hotkey(action), lambda hk, a=action: self.changed(a, hk))
            grid.addWidget(ed, r, 2)
            clear = QPushButton()
            set_icon(clear, "close")
            clear.setToolTip("Очистить")
            clear.clicked.connect(lambda _=False, a=action: self.changed(a, None))
            grid.addWidget(clear, r, 3)
            w = label("", "Warn")
            grid.addWidget(w, r, 4)
            self.edits[action] = ed
            self.warns[action] = w
        grid.setColumnStretch(4, 1)
        lay.addLayout(grid)
        lay.addSpacing(10)
        reset = QPushButton("Вернуть по умолчанию")
        reset.clicked.connect(self.reset)
        rr = QHBoxLayout()
        rr.addWidget(reset)
        rr.addStretch(1)
        lay.addLayout(rr)
        lay.addSpacing(16)
        lay.addWidget(label("ВО ВРЕМЯ ЗАПИСИ", "Section"))
        lay.addWidget(label("Повторное нажатие клавиши записи останавливает её. Ещё остановить можно кнопкой «Стоп» "
                            "на панели записи или из значка γ в строке меню.", "Muted", wrap=True))
        lay.addStretch(1)
        self.sync_warnings()

    def changed(self, action, hk):
        s = self.win.gamma.settings
        if hk:
            for other, ed in self.edits.items():   # one combination — one action
                if other != action and hotkeys.same(ed.value, hk):
                    s.setdefault("hotkeys", {})[other] = None
                    ed.set_value(None)
        s.setdefault("hotkeys", {})[action] = hk
        s.save()
        self.edits[action].set_value(hk)
        self.win.gamma.apply_hotkeys()
        self.sync_warnings()
        self.win.settings_changed()

    def reset(self):
        s = self.win.gamma.settings
        s["hotkeys"] = {}
        s.save()
        for a, ed in self.edits.items():
            ed.set_value(DEFAULT_HOTKEYS.get(a))
        self.win.gamma.apply_hotkeys()
        self.sync_warnings()
        self.win.settings_changed()

    def sync_warnings(self):
        failed = set(self.win.gamma.hotkeys.failed)
        for a, w in self.warns.items():
            w.setText("занято другой программой" if a in failed else "")


class MainWindow(QMainWindow):
    def __init__(self, app, gamma):
        super().__init__()
        self.app = app
        self.gamma = gamma
        gamma.window = self
        self.setWindowTitle(APP_NAME)
        self.setObjectName("Main")
        self.resize(1040, 720)
        self.setMinimumSize(860, 600)
        self.apply_theme()
        root = QWidget()
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        side = QFrame()
        side.setObjectName("Side")
        side.setFixedWidth(200)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(12, 18, 12, 14)
        sl.setSpacing(4)
        brand = QHBoxLayout()
        g = label(LOGO, "Gamma")
        brand.addWidget(g)
        brand.addWidget(label(APP_NAME, "Logo"))
        brand.addStretch(1)
        sl.addLayout(brand)
        sl.addSpacing(14)
        self.stack = QStackedWidget()
        self.home = HomePage(self)
        self.settings_page = SettingsPage(self)
        self.hotkeys_page = HotkeysPage(self)
        self.nav = {}
        for i, (key, title, ic, page) in enumerate((("home", "Главная", "home", self.home),
                                                     ("settings", "Настройки", "settings", self.settings_page),
                                                     ("keys", "Горячие клавиши", "keyboard", self.hotkeys_page))):
            b = QPushButton(title)
            set_icon(b, ic)
            b.setIconSize(QSize(16, 16))
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, n=i: self.go(n))
            sl.addWidget(b)
            self.nav[key] = b
            self.stack.addWidget(page)
        sl.addStretch(1)
        self.status = label("", "Hint", wrap=True)
        sl.addWidget(self.status)
        h.addWidget(side)
        h.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.go(0)
        gamma.recording_changed.connect(lambda *_: self.sync())
        gamma.replay_changed.connect(lambda *_: self.sync())
        gamma.files_changed.connect(self.home.refresh)
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(lambda *_: self._refresh_later.start(400))
        self._refresh_later = QTimer(self)
        self._refresh_later.setSingleShot(True)
        self._refresh_later.timeout.connect(self.home.refresh)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.sync)
        self.timer.start(1000)
        self.settings_changed()
        self.home.refresh()

    def go(self, n):
        self.stack.setCurrentIndex(n)
        for i, b in enumerate(self.nav.values()):
            b.setChecked(i == n)
        if n == 1:
            self.settings_page.sync_perm()

    def sync_audio(self):
        self.home.sync_audio()

    def settings_changed(self):
        hk = self.gamma.settings.hotkeys()
        for key, card in self.home.cards.items():
            card.set_hotkey(hk.get(key))
        self.home.sync_audio()
        self.home.sync_replay()
        dirs = [str(self.gamma.settings.folder(k)) for k in ("shot", "video")]
        old = self.watcher.directories()
        if old:
            self.watcher.removePaths(old)
        self.watcher.addPaths(list(set(dirs)))
        if self.gamma.settings.get("hide_windows", True):
            macos.exclude_from_capture(self, False)
        self.gamma._update_tray()

    def sync(self):
        g = self.gamma
        self.home.sync_replay()
        parts = []
        if g.recorder:
            parts.append(f"● Запись {fmt_time(g.recorder.elapsed())}")
        if g.replay_running():
            parts.append(f"Откат: {fmt_time(g.replay.buffered())} в буфере")
        self.status.setText("\n".join(parts) or "Готова к записи")

    def apply_theme(self):
        mode = self.gamma.settings.get("theme", "system")
        if mode == "system":
            dark = False
            try:
                dark = self.app.styleHints().colorScheme() == Qt.ColorScheme.Dark
            except Exception:
                dark = self.app.palette().window().color().lightness() < 128
        else:
            dark = mode == "dark"
        self.colors = theme.DARK if dark else theme.LIGHT
        self.app.setStyleSheet(theme.stylesheet(self.colors))
        retint(self.colors["text"])

    def closeEvent(self, e):
        if self.gamma.tray is not None and not self.gamma.quitting:
            e.ignore()
            self.hide()
        else:
            self.gamma.shutdown()
            e.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("Lotus")
    app.setQuitOnLastWindowClosed(False)
    icon_file = resource_path("assets", "icon.png")
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))
    settings = Settings()
    gamma = Gamma(app, settings)
    app.installEventFilter(gamma)  # ⌘Q / Dock → Quit: let the window close instead of hiding to the menu bar
    win = MainWindow(app, gamma)
    try:
        app.styleHints().colorSchemeChanged.connect(lambda *_: win.apply_theme())
    except Exception:
        pass
    win.show()
    if settings.get("replay_on_start"):
        QTimer.singleShot(1500, gamma.start_replay)
    if IS_MAC and macos.screen_access() is False:
        QTimer.singleShot(800, lambda: gamma.toast(
            "Нужен доступ к записи экрана", "Разрешите Гамме «Запись экрана» и перезапустите её.",
            actions=[("Открыть настройки", lambda: (macos.request_screen_access(), macos.open_privacy("screen")))],
            timeout=12))
    app.aboutToQuit.connect(gamma.shutdown)

    def reopen(state):
        """Dock icon click (macOS) brings the window back when nothing else of Гамма is on screen."""
        if state != Qt.ApplicationActive or win.isVisible() or gamma.busy or gamma.recorder is not None:
            return
        if gamma.toasts or getattr(gamma, "_restore_main", False):
            return
        if any(w.isVisible() for w in app.topLevelWidgets() if w is not win):
            return
        win.show()

    app.applicationStateChanged.connect(reopen)
    return app.exec()

