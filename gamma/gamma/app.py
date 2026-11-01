"""The controller: actions (screenshots, recordings, replay), menu-bar icon, global hotkeys, toasts."""
import threading
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCursor, QGuiApplication, QImage, QKeySequence, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import ffmpeg, hotkeys, icons, macos
from .overlay import Countdown, RecordBar, RecordFrame, RegionSelector, Toast, fmt_time
from .paths import HOTKEY_TITLES, cache_dir

AUDIO_TITLES = {"none": "без звука", "mic": "микрофон", "system": "звук системы", "both": "микрофон + система"}
LOOPBACK_HINTS = ("blackhole", "loopback", "soundflower", "background music", "ishowu", "zoomaudiodevice")


def stamp():
    return datetime.now().strftime("%Y-%m-%d в %H.%M.%S")


def unique(path: Path) -> Path:
    if not path.exists():
        return path
    for n in range(2, 1000):
        cand = path.with_name(f"{path.stem} ({n}){path.suffix}")
        if not cand.exists():
            return cand
    return path


def screen_index(screen):
    screens = QGuiApplication.screens()
    return screens.index(screen) if screen in screens else 0


def cursor_screen():
    return QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()


def grab(screen):
    """Frozen picture of one screen in device pixels (devicePixelRatio set)."""
    pix = screen.grabWindow(0)
    g = screen.geometry()
    if pix.isNull() or pix.width() == 0:
        pix = QPixmap(round(g.width() * screen.devicePixelRatio()), round(g.height() * screen.devicePixelRatio()))
        pix.fill(Qt.black)
    pix.setDevicePixelRatio(pix.width() / max(1, g.width()))
    return pix


def grab_all():
    """All screens stitched in the virtual desktop layout at the highest pixel ratio."""
    screens = QGuiApplication.screens()
    if len(screens) == 1:
        return grab(screens[0])
    virt = QRect()
    for s in screens:
        virt = virt.united(s.geometry())
    k = max(s.devicePixelRatio() for s in screens)
    img = QImage(round(virt.width() * k), round(virt.height() * k), QImage.Format_ARGB32)
    img.fill(Qt.black)
    p = QPainter(img)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    for s in screens:
        g = s.geometry().translated(-virt.topLeft())
        pix = grab(s)
        pix.setDevicePixelRatio(1)
        p.drawPixmap(QRect(round(g.x() * k), round(g.y() * k), round(g.width() * k), round(g.height() * k)), pix)
    p.end()
    out = QPixmap.fromImage(img)
    out.setDevicePixelRatio(k)
    return out


def crop(pix, rect):
    k = pix.devicePixelRatio() or 1.0
    r = QRect(round(rect.x() * k), round(rect.y() * k), round(rect.width() * k), round(rect.height() * k))
    out = pix.copy(r)
    out.setDevicePixelRatio(1.0)
    return out


class Gamma(QObject):
    recording_changed = Signal(bool)
    replay_changed = Signal(bool)
    files_changed = Signal()
    _clip_done = Signal(object, object, str)     # path, error, kind (from worker threads)

    def __init__(self, app, settings):
        super().__init__()
        self.app = app
        self.settings = settings
        self.window = None
        self.recorder = None
        self.rec_ui = []          # frame + bar
        self.rec_info = {}
        self.replay = None
        self.replay_jobs = []     # (job, toast)
        self.busy = False         # a selector / countdown is open
        self.quitting = False
        self.toasts = []
        self._clip_done.connect(self._on_clip_done)
        self.hotkeys = hotkeys.HotkeyManager(self)
        self.hotkeys.activated.connect(self.run_action)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(250)
        self.tray = None
        self._make_tray()
        self.apply_hotkeys()

    # -- infrastructure
    def _make_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(icons.tray_icon(False), self)
        self.tray.setToolTip("Гамма")
        menu = QMenu()
        self.tray_status = QAction("Гамма", menu)
        self.tray_status.setEnabled(False)
        menu.addAction(self.tray_status)
        menu.addSeparator()
        self.tray_actions = {}
        for key in ("shot_region", "shot_screen", "rec_region", "rec_screen"):
            a = QAction(HOTKEY_TITLES[key].split(" (")[0], menu)
            a.triggered.connect(lambda _=False, k=key: self.run_action(k, from_ui=True))
            menu.addAction(a)
            self.tray_actions[key] = a
        self.tray_stop = QAction("■  Остановить запись", menu)
        self.tray_stop.triggered.connect(self.stop_recording)
        self.tray_stop.setVisible(False)
        menu.addAction(self.tray_stop)
        menu.addSeparator()
        self.tray_replay = QAction("Откат: включить", menu)
        self.tray_replay.triggered.connect(self.toggle_replay)
        menu.addAction(self.tray_replay)
        self.tray_replay_save = QAction("Сохранить откат", menu)
        self.tray_replay_save.triggered.connect(self.save_replay)
        menu.addAction(self.tray_replay_save)
        menu.addSeparator()
        show = QAction("Открыть Гамму", menu)
        show.triggered.connect(self.show_window)
        menu.addAction(show)
        quit_ = QAction("Выйти", menu)
        quit_.triggered.connect(self.quit)
        menu.addAction(quit_)
        self.tray.setContextMenu(menu)
        self.tray_menu = menu
        self.tray.show()
        self._update_tray()

    def _update_tray(self):
        if not self.tray:
            return
        rec = self.recorder is not None
        self.tray.setIcon(icons.tray_icon(rec))
        self.tray_stop.setVisible(rec)
        for a in self.tray_actions.values():
            a.setEnabled(not rec)
        on = self.replay_running()
        self.tray_replay.setText("Откат: выключить" if on else "Откат: включить")
        self.tray_replay_save.setEnabled(on)
        if rec:
            self.tray_status.setText(f"●  Запись {fmt_time(self.recorder.elapsed())}")
        elif on:
            self.tray_status.setText(f"Откат: в буфере {fmt_time(self.replay.buffered())}")
        else:
            self.tray_status.setText("Гамма готова")
        hk = self.settings.hotkeys()
        for key, a in self.tray_actions.items():
            if hk.get(key) and self.hotkeys.available() == "global":
                a.setShortcut(QKeySequence(int(hk[key]["key"]) | int(hk[key]["mods"])))
            else:
                a.setShortcut(QKeySequence())

    def apply_hotkeys(self):
        self.hotkeys.set(self.settings.hotkeys())
        self._update_tray()

    def hide_windows(self):
        return bool(self.settings.get("hide_windows", True))

    def toast(self, title, text="", thumb=None, actions=(), timeout=6.0):
        t = Toast(title, text, thumb, actions, timeout, self.hide_windows())
        t.destroyed.connect(lambda *_: self.toasts.remove(t) if t in self.toasts else None)
        self.toasts.append(t)
        t.popup()
        return t

    def error(self, text, title="Не получилось"):
        acts = []
        low = text.lower()
        if "доступ" in low or "разреш" in low:
            acts = [("Открыть настройки", lambda: macos.open_privacy("screen"))]
        return self.toast(title, text, None, acts, 9.0)

    def run_action(self, action, from_ui=False):
        fn = {"shot_region": self.shot_region, "shot_screen": self.shot_screen, "rec_region": self.rec_region,
              "rec_screen": self.rec_screen, "replay_save": self.save_replay, "replay_toggle": self.toggle_replay,
              "show": self.show_window}.get(action)
        if fn:
            if from_ui and action not in ("replay_save", "replay_toggle", "show"):
                self._hide_main_then(fn)
            else:
                fn()

    def _hide_main_then(self, fn):
        """Actions started from Гамма's own window: get it out of the picture first."""
        w = self.window
        if w is not None and w.isVisible() and not w.isMinimized():
            w.hide()
            self._restore_main = True
            QTimer.singleShot(350, fn)
        else:
            fn()

    def _restore_window(self):
        if getattr(self, "_restore_main", False) and self.window is not None and self.recorder is None:
            self._restore_main = False
            self.window.show()

    def show_window(self):
        if self.window is not None:
            self.window.show()
            self.window.setWindowState(self.window.windowState() & ~Qt.WindowMinimized)
            self.window.raise_()
            self.window.activateWindow()

    def eventFilter(self, obj, event):
        if obj is self.app and event.type() == QEvent.Quit:
            self.quitting = True
        return False

    def quit(self):
        self.quitting = True
        self.shutdown()
        self.app.quit()

    def shutdown(self):
        if self.recorder:
            self.stop_recording(sync=True)
        if self.replay:
            self.replay.stop(flush=True)
            self.replay.cleanup()
            self.replay = None
        self.hotkeys.clear()
        if self.tray:
            self.tray.hide()

    # -- screenshots
    def shot_region(self):
        if self.busy:
            return
        self._with_delay(lambda: self._select(cursor_screen(), "shot"))

    def shot_screen(self):
        if self.busy:
            return

        def go():
            if self.settings.get("screen_mode") == "all":
                pix = grab_all()
            else:
                pix = grab(cursor_screen())
            pix.setDevicePixelRatio(1.0)
            self.save_shot(pix)
            self._restore_window()

        self._with_delay(go)

    def _with_delay(self, fn):
        delay = int(self.settings.get("shot_delay", 0) or 0)
        if delay <= 0:
            fn()
            return
        self.busy = True
        screen = cursor_screen()
        cd = Countdown(delay, screen.geometry().center(), self.hide_windows())

        def done():
            self.busy = False
            fn()

        def cancelled():
            self.busy = False
            self._restore_window()

        cd.finished.connect(done)
        cd.cancelled.connect(cancelled)
        self._countdown = cd
        cd.start()

    def _select(self, screen, mode):
        self.busy = True
        pix = grab(screen)
        sel = RegionSelector(screen, pix, mode, bool(self.settings.get("instant_shot", True)),
                             self.settings.get("audio", "none"), self.hide_windows())

        def accepted(rect, opts):
            self.busy = False
            if mode == "shot":
                self.save_shot(crop(pix, rect))
                self._restore_window()
            else:
                if opts.get("audio") != self.settings.get("audio"):
                    self.settings["audio"] = opts["audio"]
                    self.settings.save()
                    if self.window:
                        self.window.sync_audio()
                full = rect.size() == screen.geometry().size()
                self.start_recording(screen, None if full else rect)

        def cancelled():
            self.busy = False
            self._restore_window()

        sel.accepted.connect(accepted)
        sel.cancelled.connect(cancelled)
        sel.show()
        sel.activateWindow()
        self.selector = sel
        return sel

    def save_shot(self, pix):
        """Save a QPixmap (device pixels) by the settings; returns the path."""
        fmt = self.settings.get("shot_format", "png").lower()
        folder = self.settings.folder("shot")
        path = unique(folder / f"Снимок {stamp()}.{'jpg' if fmt == 'jpg' else 'png'}")
        img = pix.toImage()
        ok = img.save(str(path), "JPG" if fmt == "jpg" else "PNG",
                      int(self.settings.get("jpg_quality", 92)) if fmt == "jpg" else -1)
        if not ok:
            self.error(f"Не удалось сохранить снимок в «{folder}»")
            return None
        if self.settings.get("clipboard", True):
            QApplication.clipboard().setImage(img)
        if self.settings.get("shutter", True):
            macos.play("Grab")
        if self.settings.get("preview", True):
            self.toast("Снимок сохранён", f"{path.name}\n{img.width()} × {img.height()}"
                       + (" · скопирован" if self.settings.get("clipboard", True) else ""), QPixmap.fromImage(img),
                       [("Открыть", lambda: macos.open_file(path)), ("Показать", lambda: macos.reveal(path))])
        self.files_changed.emit()
        return path

    # -- recording
    def rec_region(self):
        if self.recorder:
            self.stop_recording()
        elif not self.busy:
            self._select(cursor_screen(), "record")

    def rec_screen(self):
        if self.recorder:
            self.stop_recording()
        elif not self.busy:
            self.start_recording(cursor_screen(), None)

    def audio_devices(self, mode=None):
        """avfoundation device names for an audio mode; (names, warning)."""
        mode = mode or self.settings.get("audio", "none")
        names, warn = [], ""
        if mode in ("mic", "both"):
            names.append(self.settings.get("mic_device") or "default")
        if mode in ("system", "both"):
            dev = self.settings.get("system_device") or ""
            if not dev:
                dev = next((n for n in ffmpeg.audio_devices() if any(h in n.lower() for h in LOOPBACK_HINTS)), "")
            if dev:
                names.append(dev)
            else:
                warn = ("Для звука системы нужно виртуальное устройство (например, BlackHole) — "
                        "пишу без него. Подробнее в Настройках → Звук.")
        return names, warn

    def make_spec(self, screen, rect=None, audio_mode=None):
        g = screen.geometry()
        names, warn = self.audio_devices(audio_mode)
        spec = ffmpeg.CaptureSpec(
            screen=screen_index(screen), screen_size=(g.width(), g.height()), dpr=screen.devicePixelRatio(),
            region=(rect.x(), rect.y(), rect.width(), rect.height()) if rect is not None else None,
            fps=int(self.settings.get("fps", 30)), quality=int(self.settings.get("quality", 2)),
            encoder=self.settings.get("encoder", "hw"), max_height=int(self.settings.get("max_height", 0) or 0),
            cursor=bool(self.settings.get("cursor", True)), clicks=bool(self.settings.get("clicks", False)),
            audio=names)
        return spec, warn

    def start_recording(self, screen, rect=None, spec=None):
        if self.recorder:
            return
        warn = ""
        if spec is None:
            spec, warn = self.make_spec(screen, rect)
        if warn:
            self.toast("Звук системы", warn, timeout=8)
        g = screen.geometry()
        region_global = rect.translated(g.topLeft()) if rect is not None else None
        out = unique(self.settings.folder("video") / f"Запись {stamp()}.{self.settings.get('video_format', 'mp4')}")
        self.busy = True
        center = region_global.center() if region_global is not None else g.center()
        cd = Countdown(int(self.settings.get("countdown", 3) or 0), center, self.hide_windows())

        def go():
            self.busy = False
            rec = ffmpeg.Recorder(spec, out)
            try:
                rec.start()
            except Exception as e:  # noqa: BLE001
                self.error(str(e))
                self._restore_window()
                return
            self.recorder = rec
            self.rec_info = {"screen": screen, "region": region_global, "spec": spec}
            if self.settings.get("minimize", True) and self.window is not None and self.window.isVisible():
                self.window.hide()
                self._restore_main = True
            hide = self.hide_windows()
            if region_global is not None:
                frame = RecordFrame(region_global, hide)
                frame.show()
                self.rec_ui.append(frame)
            n_audio = len(spec.audio)
            audio_text = AUDIO_TITLES.get(self.settings.get("audio", "none"), "") if n_audio else "без звука"
            bar = RecordBar("Запись области" if region_global is not None else "Запись экрана", audio_text, hide)
            bar.stop_clicked.connect(self.stop_recording)
            bar.cancel_clicked.connect(self.cancel_recording)
            bar.place(region_global, g)
            bar.show()
            self.rec_ui.append(bar)
            self.rec_bar = bar
            self._update_tray()
            self.recording_changed.emit(True)

        def cancelled():
            self.busy = False
            self._restore_window()

        cd.finished.connect(go)
        cd.cancelled.connect(cancelled)
        self._countdown = cd
        cd.start()

    def _close_rec_ui(self):
        for w in self.rec_ui:
            w.close()
            w.deleteLater()
        self.rec_ui = []
        self.rec_bar = None

    def cancel_recording(self):
        rec, self.recorder = self.recorder, None
        self._close_rec_ui()
        if rec:
            rec.cancel()
        self._update_tray()
        self.recording_changed.emit(False)
        self._restore_window()

    def stop_recording(self, sync=False):
        rec, self.recorder = self.recorder, None
        self._close_rec_ui()
        self._update_tray()
        self.recording_changed.emit(False)
        if rec is None:
            return
        progress = None if sync else self.toast("Сохраняю запись…", rec.out.name, timeout=0)
        if progress:
            progress.keep(True)

        def work():
            path = rec.stop()
            self._clip_done.emit((path, progress), rec.error, "record")

        if sync:
            work()
        else:
            threading.Thread(target=work, daemon=True).start()
        self._restore_window()

    def _on_clip_done(self, payload, error, kind):
        path, progress = payload if isinstance(payload, tuple) else (payload, None)
        if progress is not None:
            progress.close()
        if not path:
            self.error(error or "Видео не записалось", "Запись не сохранилась" if kind == "record" else
                       "Откат не сохранился")
            return
        path = Path(path)
        thumb = self.video_thumb(path)
        dur = ffmpeg.probe_duration(path)
        title = {"record": "Запись сохранена", "replay": "Откат сохранён"}.get(kind, "Готово")
        self.toast(title, f"{path.name}\n{fmt_time(dur)}", thumb,
                   [("Открыть", lambda: macos.open_file(path)), ("Показать", lambda: macos.reveal(path))], 8.0)
        self.files_changed.emit()

    def video_thumb(self, path):
        path = Path(path)
        try:
            key = f"{abs(hash((str(path), path.stat().st_mtime))) % 10**12}.jpg"
        except OSError:
            return QPixmap()
        out = cache_dir("thumbs") / key
        if not out.exists():
            ffmpeg.thumbnail(path, out, at=0.5)
        return QPixmap(str(out)) if out.exists() else QPixmap()

    # -- replay buffer
    def replay_running(self):
        return self.replay is not None and self.replay.running()

    def replay_keep(self):
        return (float(self.settings.get("replay_before", 5)) + float(self.settings.get("replay_after", 1))) * 60

    def start_replay(self):
        if self.replay_running():
            return True
        screens = QGuiApplication.screens()
        idx = int(self.settings.get("replay_screen", 0) or 0)
        screen = screens[idx] if idx < len(screens) else QGuiApplication.primaryScreen()
        spec, warn = self.make_spec(screen, None)
        if warn:
            self.toast("Звук системы", warn, timeout=8)
        self.replay = ffmpeg.ReplayBuffer(spec, self.replay_keep(), segment=10.0)
        try:
            self.replay.start()
        except Exception as e:  # noqa: BLE001
            self.replay = None
            self.error(str(e))
            return False
        self._update_tray()
        self.replay_changed.emit(True)
        return True

    def stop_replay(self):
        if self.replay:
            self.replay.threaded = False
            self.replay.stop(flush=True)
            self.replay.cleanup()
            self.replay = None
        self._update_tray()
        self.replay_changed.emit(False)

    def toggle_replay(self):
        if self.replay_running():
            self.stop_replay()
        else:
            if self.start_replay():
                b, a = float(self.settings.get("replay_before", 5)), float(self.settings.get("replay_after", 1))
                hk = self.settings.hotkey("replay_save")
                self.toast("Откат включён", f"Храню последние {fmt_time(b * 60)}. "
                           + (f"{hk['text']} — " if hk else "") + f"сохранить их и ещё {fmt_time(a * 60)}.", timeout=5)

    def save_replay(self):
        if not self.replay_running():
            self.toast("Откат выключен", "Включите откат — тогда Гамма будет помнить последние минуты.",
                       actions=[("Включить", self.toggle_replay)])
            return
        before = float(self.settings.get("replay_before", 5)) * 60
        after = float(self.settings.get("replay_after", 1)) * 60
        out = unique(self.settings.folder("video") / f"Откат {stamp()}.{self.settings.get('video_format', 'mp4')}")
        toast = self.toast("Сохраняю откат…", "", timeout=0)
        toast.keep(True)

        def done(path, error):
            self._clip_done.emit((path, toast), error, "replay")

        job = self.replay.save(before, after, out, done)
        self.replay_jobs.append((job, toast))
        macos.play("Pop")
        self._tick()

    def _tick(self):
        if self.recorder:
            if not self.recorder.poll():
                err = self.recorder.error
                self.cancel_recording()
                self.error(err or "Запись остановилась", "Запись прервалась")
            elif getattr(self, "rec_bar", None) is not None:
                self.rec_bar.set_time(self.recorder.elapsed())
        if self.replay:
            ok = self.replay.poll()
            if not ok and not self.replay.running():
                err = self.replay.error
                self.replay = None
                self.replay_changed.emit(False)
                self.error(err or "Буфер отката остановился", "Откат выключился")
            for job, toast in list(self.replay_jobs):
                if self.replay is None or job not in self.replay.pending:
                    self.replay_jobs.remove((job, toast))
                    continue
                left = self.replay.remaining(job)
                total = job["before"] + job["after"]
                toast.set_text("Сохраняю откат…" if left > 0 else "Склеиваю откат…",
                               f"Последние {fmt_time(job['before'])} уже в буфере, дописываю ещё {fmt_time(left)}. "
                               f"Итого ≈ {fmt_time(total)}." if left > 0 else "Почти готово")
        if self.tray and int(time.monotonic() * 4) % 4 == 0:
            self._update_tray()
