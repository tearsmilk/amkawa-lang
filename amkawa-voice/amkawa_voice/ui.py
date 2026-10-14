"""Main window."""
import sys
import traceback

from PySide6.QtCore import QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPalette, QShortcut
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSlider, QTabWidget, QVBoxLayout, QWidget,
)

from . import APP_NAME, __version__, catalog, tts, virtual_mic
from .engine import AudioEngine, default_devices, is_virtual_mic, list_devices, SD_ERROR
from .paths import resource_path
from .settings import Settings
from .theme import DARK, LIGHT, stylesheet

NONE_DEVICE = "— не использовать —"


# ------------------------------------------------------------------ helpers
class Task(QThread):
    """Run a function in a background thread; report progress / result / error."""

    progress = Signal(int, int)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, parent=None, **kwargs):
        super().__init__(parent)
        self.fn, self.args, self.kwargs = fn, args, kwargs

    def run(self):
        try:
            result = self.fn(*self.args, progress=lambda d, t: self.progress.emit(int(d), int(t)),
                             **self.kwargs)
        except Exception as exc:
            traceback.print_exc()
            self.failed.emit(str(exc) or exc.__class__.__name__)
        else:
            self.done.emit(result)


def card(title=None, subtitle=None):
    frame = QFrame()
    frame.setObjectName("Card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(22, 18, 22, 20)
    lay.setSpacing(12)
    if title:
        t = QLabel(title)
        t.setObjectName("CardTitle")
        lay.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("Muted")
        s.setWordWrap(True)
        lay.addWidget(s)
    return frame, lay


def muted(text):
    label = QLabel(text)
    label.setObjectName("Muted")
    label.setWordWrap(True)
    return label


class Meter(QWidget):
    """Flat level bar (no animation beyond the level itself)."""

    def __init__(self, colors):
        super().__init__()
        self.level = 0.0
        self.colors = colors
        self.setFixedHeight(8)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_level(self, rms):
        import math

        db = 20 * math.log10(max(rms, 1e-6))
        level = min(1.0, max(0.0, (db + 60) / 60))
        if abs(level - self.level) > 0.01:
            self.level = level
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self.colors["meter_bg"]))
        p.drawRoundedRect(self.rect(), 4, 4)
        if self.level > 0:
            r = self.rect()
            r.setWidth(int(r.width() * self.level))
            p.setBrush(QColor(self.colors["accent"]))
            p.drawRoundedRect(r, 4, 4)


class ParamSlider(QWidget):
    changed = Signal(str, float)

    def __init__(self, key, label, lo, hi, step, fmt, tip=""):
        super().__init__()
        self.key, self.lo, self.step, self.fmt = key, lo, step, fmt
        lay = QGridLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setHorizontalSpacing(12)
        name = QLabel(label)
        name.setToolTip(tip)
        self.value_label = QLabel()
        self.value_label.setObjectName("Muted")
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, int(round((hi - lo) / step)))
        self.slider.valueChanged.connect(self._moved)
        lay.addWidget(name, 0, 0)
        lay.addWidget(self.value_label, 0, 1)
        lay.addWidget(self.slider, 1, 0, 1, 2)

    def value(self):
        return self.lo + self.slider.value() * self.step

    def set_value(self, v):
        self.slider.blockSignals(True)
        self.slider.setValue(int(round((v - self.lo) / self.step)))
        self.slider.blockSignals(False)
        self.value_label.setText(self.fmt(self.value()))

    def _moved(self, _):
        self.value_label.setText(self.fmt(self.value()))
        self.changed.emit(self.key, self.value())


# ------------------------------------------------------------------ add model dialog
class AddModelDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Добавить RVC-модель")
        self.setMinimumWidth(520)
        self.result_model = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 22)
        lay.setSpacing(12)
        title = QLabel("Добавить голос")
        title.setObjectName("CardTitle")
        lay.addWidget(title)
        lay.addWidget(muted(
            "Подходит любая RVC v1/v2 модель (.pth или .zip с .pth внутри). Бесплатные женские/аниме "
            "модели ищите на Hugging Face по запросу «RVC v2 female» или «RVC anime». "
            "Проверяйте лицензию модели и не выдавайте себя за реальных людей."))

        self.tabs = QTabWidget()
        file_tab = QWidget()
        fl = QHBoxLayout(file_tab)
        fl.setContentsMargins(0, 8, 0, 0)
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("/путь/к/model.pth или model.zip")
        browse = QPushButton("Выбрать…")
        browse.clicked.connect(self._browse)
        fl.addWidget(self.file_edit, 1)
        fl.addWidget(browse)
        url_tab = QWidget()
        ul = QVBoxLayout(url_tab)
        ul.setContentsMargins(0, 8, 0, 0)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://huggingface.co/<автор>/<модель>  или прямая ссылка на .pth/.zip")
        ul.addWidget(self.url_edit)
        self.tabs.addTab(file_tab, "Файл")
        self.tabs.addTab(url_tab, "Ссылка")
        lay.addWidget(self.tabs)

        row = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Название (необязательно)")
        self.pitch = QDoubleSpinBox()
        self.pitch.setRange(-24, 24)
        self.pitch.setValue(12)
        self.pitch.setSuffix(" полутонов")
        self.pitch.setToolTip("Сдвиг высоты для вашего голоса. Мужской → женский: +12, женский: 0")
        row.addWidget(self.name_edit, 1)
        row.addWidget(self.pitch)
        lay.addLayout(row)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(False)
        lay.addWidget(self.progress)
        self.status = muted("")
        lay.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton("Добавить")
        self.ok.setObjectName("Primary")
        self.ok.clicked.connect(self._start)
        buttons.addWidget(cancel)
        buttons.addWidget(self.ok)
        lay.addLayout(buttons)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "RVC модель", "", "RVC модель (*.pth *.zip)")
        if path:
            self.file_edit.setText(path)

    def _start(self):
        source = self.file_edit.text() if self.tabs.currentIndex() == 0 else self.url_edit.text()
        source = source.strip()
        if not source:
            self.status.setText("Укажите файл или ссылку.")
            return
        self.ok.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status.setText("Загружаю и проверяю модель…")
        self.task = Task(catalog.import_model, source, name=self.name_edit.text(), pitch=self.pitch.value(),
                         parent=self)
        self.task.progress.connect(self._progress)
        self.task.done.connect(self._done)
        self.task.failed.connect(self._failed)
        self.task.start()

    def _progress(self, done, total):
        if total:
            self.progress.setRange(0, 1000)
            self.progress.setValue(int(done * 1000 / total))
            self.status.setText(f"Скачано {done / 1e6:.1f} из {total / 1e6:.1f} МБ")

    def _done(self, model):
        self.result_model = model
        self.accept()

    def _failed(self, msg):
        self.ok.setEnabled(True)
        self.progress.setVisible(False)
        self.status.setText("Не получилось: " + msg)


# ------------------------------------------------------------------ main window
class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.settings = Settings()
        self.engine = AudioEngine()
        self.models = []
        self.current = None
        self.loading_task = None
        self.colors = LIGHT
        self.setWindowTitle(APP_NAME)
        self.resize(1040, 720)
        self.setMinimumSize(880, 600)

        root = QWidget()
        root.setObjectName("Main")
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self._build_sidebar())
        h.addWidget(self._build_main(), 1)

        self.apply_theme()
        self.refresh_devices()
        self.reload_models(select=self.settings.get("model_id"))
        self.refresh_driver_status()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(50)

    # ---------------------------------------------------------- layout
    def _build_sidebar(self):
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(270)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(16, 20, 16, 16)
        lay.setSpacing(10)

        logo_row = QHBoxLayout()
        spark = QLabel("✻")
        spark.setObjectName("Spark")
        logo = QLabel(APP_NAME)
        logo.setObjectName("Logo")
        logo_row.addWidget(spark)
        logo_row.addWidget(logo)
        logo_row.addStretch(1)
        lay.addLayout(logo_row)
        lay.addSpacing(14)

        sec = QLabel("ГОЛОСА")
        sec.setObjectName("Section")
        lay.addWidget(sec)
        self.model_list = QListWidget()
        self.model_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.model_list.currentRowChanged.connect(self._on_model_row)
        lay.addWidget(self.model_list, 1)

        add = QPushButton("＋  Добавить RVC-модель")
        add.setObjectName("Ghost")
        add.clicked.connect(self._add_model)
        lay.addWidget(add)

        bottom = QHBoxLayout()
        self.theme_btn = QPushButton()
        self.theme_btn.setObjectName("Link")
        self.theme_btn.clicked.connect(self._cycle_theme)
        version = QLabel(f"v{__version__}")
        version.setObjectName("Muted")
        bottom.addWidget(self.theme_btn)
        bottom.addStretch(1)
        bottom.addWidget(version)
        lay.addLayout(bottom)
        return side

    def _build_main(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner.setObjectName("MainInner")
        scroll.setWidget(inner)
        outer = QHBoxLayout(inner)
        outer.setContentsMargins(0, 0, 0, 0)
        column = QWidget()
        column.setMaximumWidth(760)
        outer.addStretch(1)
        outer.addWidget(column, 100)
        outer.addStretch(1)
        lay = QVBoxLayout(column)
        lay.setContentsMargins(36, 30, 36, 36)
        lay.setSpacing(18)

        # header
        self.title = QLabel()
        self.title.setObjectName("Title")
        self.subtitle = muted("")
        lay.addWidget(self.title)
        lay.addWidget(self.subtitle)

        run_row = QHBoxLayout()
        self.run_btn = QPushButton("Включить голос")
        self.run_btn.setObjectName("Primary")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.clicked.connect(self._toggle_run)
        self.status = QLabel("Выключено")
        self.status.setObjectName("Status")
        self.status.setWordWrap(True)
        run_row.addWidget(self.run_btn)
        run_row.addSpacing(14)
        run_row.addWidget(self.status, 1)
        lay.addLayout(run_row)

        # voice parameters
        vcard, vl = card("Голос", None)
        self.params_box = QVBoxLayout()
        self.params_box.setSpacing(14)
        vl.addLayout(self.params_box)
        reset_row = QHBoxLayout()
        self.bypass = QCheckBox("Без эффекта (мой обычный голос)")
        self.bypass.toggled.connect(lambda v: setattr(self.engine, "bypass", v))
        reset = QPushButton("Сбросить")
        reset.setObjectName("Link")
        reset.clicked.connect(self._reset_params)
        reset_row.addWidget(self.bypass)
        reset_row.addStretch(1)
        reset_row.addWidget(reset)
        vl.addLayout(reset_row)
        lay.addWidget(vcard)
        lay.addWidget(self._build_tts_card())

        # audio routing
        acard, al = card("Звук")
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        self.in_combo = QComboBox()
        self.out_combo = QComboBox()
        self.mon_combo = QComboBox()
        for combo in (self.in_combo, self.out_combo, self.mon_combo):
            combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            combo.currentTextChanged.connect(self._devices_changed)
        grid.addWidget(QLabel("Микрофон"), 0, 0)
        grid.addWidget(self.in_combo, 0, 1)
        grid.addWidget(QLabel("Вывод в Discord"), 1, 0)
        grid.addWidget(self.out_combo, 1, 1)
        grid.addWidget(QLabel("Наушники"), 2, 0)
        grid.addWidget(self.mon_combo, 2, 1)
        grid.setColumnStretch(1, 1)
        al.addLayout(grid)

        refresh = QPushButton("Обновить список устройств")
        refresh.setObjectName("Link")
        refresh.clicked.connect(self.refresh_devices)
        al.addWidget(refresh, 0, Qt.AlignLeft)

        mon_row = QHBoxLayout()
        self.monitor = QCheckBox("Слушать себя")
        self.monitor.setChecked(bool(self.settings["monitor_enabled"]))
        self.monitor.toggled.connect(self._monitor_toggled)
        self.mon_volume = QSlider(Qt.Horizontal)
        self.mon_volume.setRange(0, 100)
        self.mon_volume.setValue(int(self.settings["monitor_volume"] * 100))
        self.mon_volume.valueChanged.connect(self._monitor_volume)
        mon_row.addWidget(self.monitor)
        mon_row.addSpacing(10)
        mon_row.addWidget(muted("громкость"))
        mon_row.addWidget(self.mon_volume, 1)
        al.addLayout(mon_row)

        self.in_gain = ParamSlider("input_gain", "Усиление микрофона", 0.0, 4.0, 0.05, lambda v: f"{v:.2f}×")
        self.in_gain.set_value(self.settings["input_gain"])
        self.in_gain.changed.connect(self._audio_param)
        self.out_gain = ParamSlider("output_gain", "Громкость голоса", 0.0, 3.0, 0.05, lambda v: f"{v:.2f}×")
        self.out_gain.set_value(self.settings["output_gain"])
        self.out_gain.changed.connect(self._audio_param)
        self.gate = ParamSlider("gate_db", "Шумодав (порог)", -80, -20, 1, lambda v: f"{v:.0f} dB",
                                "Тише порога — тишина. Убирает шум комнаты.")
        self.gate.set_value(self.settings["gate_db"])
        self.gate.changed.connect(self._audio_param)
        for w in (self.in_gain, self.out_gain, self.gate):
            al.addWidget(w)

        meters = QGridLayout()
        meters.setHorizontalSpacing(12)
        self.in_meter = Meter(self.colors)
        self.out_meter = Meter(self.colors)
        meters.addWidget(muted("Вход"), 0, 0)
        meters.addWidget(self.in_meter, 0, 1)
        meters.addWidget(muted("Выход"), 1, 0)
        meters.addWidget(self.out_meter, 1, 1)
        meters.setColumnStretch(1, 1)
        al.addLayout(meters)
        lay.addWidget(acard)

        # discord / virtual mic
        dcard, dl = card("Discord")
        self.driver_status = QLabel()
        self.driver_status.setWordWrap(True)
        dl.addWidget(self.driver_status)
        drow = QHBoxLayout()
        self.driver_btn = QPushButton()
        self.driver_btn.clicked.connect(self._driver_action)
        drow.addWidget(self.driver_btn)
        drow.addStretch(1)
        dl.addLayout(drow)
        dl.addWidget(muted(
            "1. Установите виртуальный микрофон кнопкой выше (нужен пароль администратора).\n"
            f"2. Здесь в «Вывод в Discord» выберите «{virtual_mic.device_name()}».\n"
            "3. В Discord: Настройки → Голос и видео → Устройство ввода → "
            f"«{virtual_mic.device_name()}».\n"
            "4. В Discord выключите «Шумоподавление» (Krisp) и «Эхоподавление» — они портят голос.\n"
            "5. Нажмите «Включить голос». Слушать себя можно через «Наушники» + «Слушать себя»."))
        lay.addWidget(dcard)
        lay.addStretch(1)
        return scroll

    def _build_tts_card(self):
        tcard, tl = card("Текст в голос", "Напишите текст — выбранный голос произнесёт его в Discord и в наушники.")
        self.tts_text = QPlainTextEdit()
        self.tts_text.setPlaceholderText("Например: Ня! Всем привет~  (⌘↩ — сказать)")
        self.tts_text.setFixedHeight(84)
        tl.addWidget(self.tts_text)

        row = QHBoxLayout()
        self.tts_voice = QComboBox()
        self.tts_voice.setToolTip("Голос синтезатора macOS, который потом переозвучивает выбранная модель")
        self.tts_voices = tts.list_voices()
        for v in self.tts_voices:
            self.tts_voice.addItem(v.label, v.name)
        if not self.tts_voices:
            self.tts_voice.addItem("Синтезатор речи не найден", None)
        wanted = self.settings.get("tts_voice")
        idx = self.tts_voice.findData(wanted) if wanted else -1
        self.tts_voice.setCurrentIndex(max(idx, 0))
        self.tts_voice.currentIndexChanged.connect(self._tts_settings_changed)
        self.say_btn = QPushButton("Сказать")
        self.say_btn.setObjectName("Accent")
        self.say_btn.clicked.connect(self._speak)
        stop = QPushButton("Стоп")
        stop.clicked.connect(self.engine.player.stop)
        row.addWidget(self.tts_voice, 1)
        row.addWidget(self.say_btn)
        row.addWidget(stop)
        tl.addLayout(row)

        self.tts_rate = ParamSlider("tts_rate", "Скорость речи", 0.5, 1.8, 0.05, lambda v: f"{v:.2f}×")
        self.tts_rate.set_value(self.settings["tts_rate"])
        self.tts_pitch = ParamSlider("tts_pitch", "Высота для озвучки", -12, 12, 1, lambda v: f"{v:+.0f} полутонов",
                                     "Голос синтезатора уже женский, поэтому сдвиг нужен меньше, чем для микрофона")
        self.tts_pitch.set_value(self.settings["tts_pitch"])
        for w in (self.tts_rate, self.tts_pitch):
            w.changed.connect(lambda k, v: self._tts_settings_changed())
            tl.addWidget(w)
        self.tts_duck = QCheckBox("Глушить микрофон, пока звучит текст")
        self.tts_duck.setChecked(bool(self.settings["tts_duck"]))
        self.tts_duck.toggled.connect(self._tts_settings_changed)
        tl.addWidget(self.tts_duck)
        self.engine.duck_mic = bool(self.settings["tts_duck"])
        QShortcut(QKeySequence("Ctrl+Return"), self.tts_text, activated=self._speak)
        self.tts_task = None
        return tcard

    def _tts_settings_changed(self, *_):
        self.settings["tts_voice"] = self.tts_voice.currentData()
        self.settings["tts_rate"] = self.tts_rate.value()
        self.settings["tts_pitch"] = self.tts_pitch.value()
        self.settings["tts_duck"] = self.tts_duck.isChecked()
        self.engine.duck_mic = self.settings["tts_duck"]
        self.settings.save()

    def _speak(self):
        text = self.tts_text.toPlainText().strip()
        if not text:
            self._set_status("Введите текст для озвучки.", "warn")
            return
        if self.tts_task is not None:
            return
        if not self.engine.output_device and not self.engine.monitor_device:
            self._set_status("Выберите «Вывод в Discord» и/или «Наушники».", "warn")
            return
        voice = None if self.bypass.isChecked() else self.engine.voice
        system_voice = self.tts_voice.currentData()
        rate, pitch = self.tts_rate.value(), self.tts_pitch.value()

        def work(progress=None):
            audio = tts.synthesize(text, system_voice, rate)
            return tts.revoice(audio, voice, pitch=pitch)

        def done(audio):
            self.tts_task = None
            self.say_btn.setEnabled(True)
            try:
                self.engine.say(audio)
            except Exception as exc:
                self._set_status(f"Не удалось воспроизвести: {exc}", "warn")
                return
            self._set_status(f"Говорю ({len(audio) / 48000:.1f} с)", "ok")

        def failed(msg):
            self.tts_task = None
            self.say_btn.setEnabled(True)
            self._set_status("Озвучка не удалась: " + msg, "warn")

        self.say_btn.setEnabled(False)
        self._set_status("Готовлю речь…")
        task = Task(work, parent=self)
        task.done.connect(done)
        task.failed.connect(failed)
        task.finished.connect(task.deleteLater)
        self.tts_task = task
        task.start()

    # ---------------------------------------------------------- theme
    def _is_dark(self):
        mode = self.settings.get("theme", "system")
        if mode == "dark":
            return True
        if mode == "light":
            return False
        try:
            return self.app.styleHints().colorScheme() == Qt.ColorScheme.Dark
        except Exception:
            return self.app.palette().color(QPalette.Window).lightness() < 128

    def apply_theme(self):
        self.colors = DARK if self._is_dark() else LIGHT
        self.app.setStyleSheet(stylesheet(self.colors))
        for meter in (getattr(self, "in_meter", None), getattr(self, "out_meter", None)):
            if meter:
                meter.colors = self.colors
                meter.update()
        names = {"system": "Тема: системная", "light": "Тема: светлая", "dark": "Тема: тёмная"}
        self.theme_btn.setText(names.get(self.settings.get("theme", "system")))

    def _cycle_theme(self):
        order = ["system", "light", "dark"]
        cur = self.settings.get("theme", "system")
        self.settings["theme"] = order[(order.index(cur) + 1) % 3 if cur in order else 0]
        self.settings.save()
        self.apply_theme()

    # ---------------------------------------------------------- devices
    def refresh_devices(self):
        inputs, outputs = list_devices()
        d_in, d_out = default_devices()
        virt = [o for o in outputs if is_virtual_mic(o)]
        speakers = [o for o in outputs if not is_virtual_mic(o)]

        def fill(combo, items, wanted, fallback, allow_none):
            combo.blockSignals(True)
            combo.clear()
            if allow_none:
                combo.addItem(NONE_DEVICE)
            combo.addItems(items)
            pick = wanted if wanted in items else fallback
            if pick in items:
                combo.setCurrentText(pick)
            combo.blockSignals(False)

        fill(self.in_combo, [i for i in inputs if not is_virtual_mic(i)] or inputs,
             self.settings["input_device"], d_in, False)
        fill(self.out_combo, virt + speakers, self.settings["output_device"], virt[0] if virt else None, True)
        fill(self.mon_combo, speakers + virt, self.settings["monitor_device"],
             d_out if d_out in speakers else (speakers[0] if speakers else None), True)
        self._devices_changed()
        if SD_ERROR:
            self._set_status("Аудио недоступно: " + SD_ERROR, "warn")

    def _combo_value(self, combo):
        text = combo.currentText()
        return None if not text or text == NONE_DEVICE else text

    def _devices_changed(self, *_):
        self.settings["input_device"] = self._combo_value(self.in_combo)
        self.settings["output_device"] = self._combo_value(self.out_combo)
        self.settings["monitor_device"] = self._combo_value(self.mon_combo)
        self.settings.save()
        self.engine.input_device = self.settings["input_device"]
        self.engine.output_device = self.settings["output_device"]
        self.engine.monitor_device = self.settings["monitor_device"]
        if self.engine.running:
            self._restart_engine()

    def _monitor_toggled(self, on):
        self.settings["monitor_enabled"] = bool(on)
        self.settings.save()
        self.engine.monitor_enabled = bool(on)
        if on and not self.settings["monitor_device"]:
            self._set_status("Выберите «Наушники», чтобы слышать себя.", "warn")

    def _monitor_volume(self, value):
        self.settings["monitor_volume"] = value / 100
        self.engine.monitor_volume = value / 100
        self.settings.save()

    def _audio_param(self, key, value):
        self.settings[key] = value
        setattr(self.engine, key, value)
        self.settings.save()

    # ---------------------------------------------------------- models
    def reload_models(self, select=None):
        self.models = catalog.all_models()
        self.model_list.blockSignals(True)
        self.model_list.clear()
        row_to_select = 0
        for i, model in enumerate(self.models):
            item = QListWidgetItem()
            widget = QWidget()
            wl = QVBoxLayout(widget)
            wl.setContentsMargins(12, 8, 12, 8)
            wl.setSpacing(1)
            name = QLabel(model.name)
            name.setObjectName("ModelName")
            info = QLabel(model.info or "Встроенный · без загрузки")
            info.setObjectName("ModelInfo")
            wl.addWidget(name)
            wl.addWidget(info)
            widget.setAttribute(Qt.WA_TransparentForMouseEvents)
            item.setSizeHint(QSize(200, 52))
            self.model_list.addItem(item)
            self.model_list.setItemWidget(item, widget)
            if model.id == select:
                row_to_select = i
        self.model_list.blockSignals(False)
        self.model_list.setCurrentRow(row_to_select)
        self._on_model_row(row_to_select)

    def _params_for(self, model):
        params = dict(model.params)
        if model.kind == "rvc":
            params.setdefault("block", self.settings.get("rvc_block", 0.5))
        params.update(self.settings["overrides"].get(model.id, {}))
        return params

    def _on_model_row(self, row):
        if row < 0 or row >= len(self.models):
            return
        model = self.models[row]
        self.current = model
        self.settings["model_id"] = model.id
        self.settings.save()
        self.title.setText(model.name)
        self.subtitle.setText(model.description)
        self._build_params(model)
        self._load_voice(model)

    def _build_params(self, model):
        while self.params_box.count():
            w = self.params_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        params = self._params_for(model)
        specs = [("pitch", "Высота тона", -12, 24, 1, lambda v: f"{v:+.0f} полутонов",
                  "Мужской голос → женский: примерно +10…+14")]
        if model.kind == "builtin":
            specs += [
                ("formant", "Тембр (форманты)", 0.8, 1.6, 0.01, lambda v: f"{v:.2f}×",
                 "Больше — «меньше» и милее звучит голос"),
                ("brightness", "Яркость", -6, 8, 0.5, lambda v: f"{v:+.1f} dB", ""),
                ("breath", "Придыхание", 0.0, 0.6, 0.01, lambda v: f"{v * 100:.0f}%", ""),
            ]
        else:
            specs += [("block", "Размер блока", 0.25, 1.0, 0.05, lambda v: f"{v:.2f} с",
                       "Меньше — меньше задержка, но нужен быстрый процессор. "
                       "Если звук прерывается — увеличьте.")]
            menu_note = muted(
                "RVC — нейросеть: звучит естественнее, но на Intel-процессоре задержка ~0.6–1 с. "
                "Для живого общения без задержки берите встроенные голоса.")
            self.params_box.addWidget(menu_note)
            menu_del = QPushButton("Удалить эту модель")
            menu_del.setObjectName("Link")
            menu_del.clicked.connect(self._delete_model)
            self.params_box.addWidget(menu_del, 0, Qt.AlignLeft)
        for key, label, lo, hi, step, fmt, tip in specs:
            slider = ParamSlider(key, label, lo, hi, step, fmt, tip)
            slider.set_value(params.get(key, lo))
            slider.changed.connect(self._param_changed)
            self.params_box.insertWidget(self.params_box.count(), slider)

    def _param_changed(self, key, value):
        model = self.current
        if model is None:
            return
        self.settings["overrides"].setdefault(model.id, {})[key] = value
        self.settings.save()
        if key == "block":
            self.settings["rvc_block"] = value
            self._load_voice(model)
        else:
            voice = self.engine.voice
            if getattr(voice, "model_id", None) == model.id:
                voice.set_params(**{key: value})

    def _reset_params(self):
        if self.current:
            self.settings["overrides"].pop(self.current.id, None)
            self.settings.save()
            self._build_params(self.current)
            self._load_voice(self.current)

    def _load_voice(self, model):
        params = self._params_for(model)
        if model.kind == "builtin":
            from .voices.dsp import SpectralVoice

            voice = SpectralVoice(**{k: params[k] for k in ("pitch", "formant", "brightness", "breath")})
            voice.model_id = model.id
            self._install_voice(voice)
            return
        if not catalog.contentvec_ready():
            answer = QMessageBox.question(
                self, "Нужен файл ContentVec",
                "Для RVC-моделей один раз нужно скачать ContentVec (~380 МБ, Hugging Face). Скачать сейчас?")
            if answer != QMessageBox.Yes:
                self._set_status("RVC-модель не загружена: нет ContentVec.", "warn")
                return
            self._run_task(catalog.ensure_contentvec, "Скачиваю ContentVec…", lambda _: self._load_voice(model))
            return

        def build(progress=None):
            from .voices.rvc import RVCVoice

            return RVCVoice(model.path, str(catalog.contentvec_path()), pitch=params.get("pitch", 0),
                            block_time=params.get("block", 0.5))

        def ready(voice):
            if self.current is not model:
                voice.close()
                return
            voice.model_id = model.id
            self._install_voice(voice)

        self._run_task(build, f"Загружаю модель «{model.name}»…", ready)

    def _install_voice(self, voice):
        self.engine.set_voice(voice)
        self._set_status("Голос включён" if self.engine.running else "Готово. Нажмите «Включить голос».",
                         "ok" if self.engine.running else None)

    def _run_task(self, fn, message, on_done):
        self._set_status(message)
        task = Task(fn, parent=self)
        task.progress.connect(lambda d, t: self._set_status(
            f"{message} {d / 1e6:.0f} / {t / 1e6:.0f} МБ" if t else message))
        task.done.connect(on_done)
        task.failed.connect(lambda msg: self._set_status("Ошибка: " + msg, "warn"))
        task.finished.connect(task.deleteLater)
        self.loading_task = task
        task.start()

    def _add_model(self):
        dialog = AddModelDialog(self)
        if dialog.exec() == QDialog.Accepted and dialog.result_model:
            self.reload_models(select=dialog.result_model.id)

    def _delete_model(self):
        model = self.current
        if not model or model.kind != "rvc":
            return
        if QMessageBox.question(self, "Удалить модель", f"Удалить «{model.name}»?") == QMessageBox.Yes:
            self.engine.set_voice(None)
            catalog.remove_model(model)
            self.reload_models(select="kawaii")

    # ---------------------------------------------------------- run
    def _toggle_run(self):
        if self.engine.running:
            self.engine.stop()
            self._set_status("Выключено")
        else:
            self._restart_engine()
        self._update_run_button()

    def _restart_engine(self):
        e = self.engine
        e.input_gain = self.settings["input_gain"]
        e.output_gain = self.settings["output_gain"]
        e.gate_db = self.settings["gate_db"]
        e.monitor_enabled = self.settings["monitor_enabled"]
        e.monitor_volume = self.settings["monitor_volume"]
        if not e.output_device and not e.monitor_device:
            self._set_status("Выберите «Вывод в Discord» и/или «Наушники».", "warn")
            return
        try:
            e.start()
        except Exception as exc:
            self._set_status(f"Не удалось запустить звук: {exc}", "warn")
        else:
            hint = "" if is_virtual_mic(e.output_device or "") else \
                " (вывод не в виртуальный микрофон — Discord его не услышит)"
            self._set_status("Голос включён" + hint, "ok" if not hint else "warn")
        self._update_run_button()

    def _update_run_button(self):
        on = self.engine.running
        self.run_btn.setText("Выключить" if on else "Включить голос")
        self.run_btn.setProperty("active", on)
        self.run_btn.style().unpolish(self.run_btn)
        self.run_btn.style().polish(self.run_btn)

    def _set_status(self, text, kind=None):
        self.status.setText(text)
        self.status.setObjectName({"ok": "StatusOk", "warn": "StatusWarn"}.get(kind, "Status"))
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _tick(self):
        self.in_meter.set_level(self.engine.in_level if self.engine.running else 0.0)
        self.out_meter.set_level(self.engine.out_level if self.engine.running else 0.0)
        if self.engine.error:
            self._set_status(self.engine.error, "warn")
            self.engine.error = ""
        if self.engine.running and self.engine.load > 1.05:
            self._set_status(f"Процессор не успевает ({self.engine.load:.1f}×). Увеличьте размер блока "
                             "или выберите встроенный голос.", "warn")

    # ---------------------------------------------------------- driver
    def refresh_driver_status(self):
        installed = virtual_mic.is_installed()
        others = [o for o in list_devices()[1] if is_virtual_mic(o)]
        if installed or any(virtual_mic.device_name() in o for o in others):
            self.driver_status.setText(f"✓ Виртуальный микрофон «{virtual_mic.device_name()}» установлен.")
            self.driver_status.setObjectName("StatusOk")
            self.driver_btn.setText("Удалить виртуальный микрофон")
        else:
            extra = f" Найдено похожее устройство: {others[0]}." if others else ""
            self.driver_status.setText("Виртуальный микрофон не установлен." + extra)
            self.driver_status.setObjectName("StatusWarn")
            self.driver_btn.setText("Установить виртуальный микрофон")
        self.driver_btn.setEnabled(virtual_mic.can_install() or installed)
        if not virtual_mic.can_install() and not installed:
            self.driver_btn.setToolTip("Доступно только в сборке для macOS")
        self.driver_status.style().unpolish(self.driver_status)
        self.driver_status.style().polish(self.driver_status)

    def _driver_action(self):
        was_running = self.engine.running
        self.engine.stop()
        self._update_run_button()
        try:
            if virtual_mic.is_installed():
                virtual_mic.uninstall()
            else:
                virtual_mic.install()
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
        # CoreAudio needs a moment to bring the device up
        QTimer.singleShot(2500, lambda: self._after_driver(was_running))

    def _after_driver(self, was_running):
        try:
            import sounddevice as sd

            sd._terminate()
            sd._initialize()
        except Exception:
            pass
        self.refresh_driver_status()
        self.refresh_devices()
        if was_running:
            self._restart_engine()

    def closeEvent(self, event):
        self.engine.stop()
        self.settings.save()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    icon = resource_path("assets", "icon.png")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    window = MainWindow(app)
    window.show()
    try:
        app.styleHints().colorSchemeChanged.connect(lambda *_: window.apply_theme())
    except Exception:
        pass
    return app.exec()
