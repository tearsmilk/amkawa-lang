"""Dialogs: new document, adjustments with live preview, text, export, manga page grid, canvas size."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFontComboBox, QFormLayout,
    QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QSlider, QSpinBox, QToolButton, QVBoxLayout,
)

PRESETS = [
    ("Страница манги A4 · 150 dpi", 1240, 1754, 150, "#FFFFFF"),
    ("Страница манги B4 · 300 dpi (печать)", 3035, 4299, 300, "#FFFFFF"),
    ("Обложка лайт-новеллы · 1600×2400", 1600, 2400, 300, "#FFFFFF"),
    ("Персонаж / арт · 1200×1600", 1200, 1600, 150, None),
    ("Иллюстрация 16:9 · 1920×1080", 1920, 1080, 150, "#FFFFFF"),
    ("Вебтун · 800×1280", 800, 1280, 72, "#FFFFFF"),
    ("Квадрат · 2048×2048", 2048, 2048, 150, "#FFFFFF"),
    ("Анимация 720p · 1280×720", 1280, 720, 72, "#FFFFFF"),
    ("Аватар · 512×512", 512, 512, 72, None),
]


def buttons(dialog, ok="OK"):
    bb = QDialogButtonBox()
    b = bb.addButton(ok, QDialogButtonBox.AcceptRole)
    b.setObjectName("Accent")
    bb.addButton("Отмена", QDialogButtonBox.RejectRole)
    bb.accepted.connect(dialog.accept)
    bb.rejected.connect(dialog.reject)
    return bb


def title(text):
    t = QLabel(text)
    t.setObjectName("Title")
    return t


class NewDocDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.setWindowTitle("Новый документ")
        s = win.settings
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.addWidget(title("Новый документ"))
        form = QFormLayout()
        self.preset = QComboBox()
        self.preset.addItem("Свой размер", None)
        for p in PRESETS:
            self.preset.addItem(p[0], p)
        self.preset.currentIndexChanged.connect(self._preset)
        form.addRow("Шаблон", self.preset)
        self.w = QSpinBox()
        self.w.setRange(16, 12000)
        self.w.setValue(int(s.get("new_width", 1240)))
        self.w.setSuffix(" px")
        self.h = QSpinBox()
        self.h.setRange(16, 12000)
        self.h.setValue(int(s.get("new_height", 1754)))
        self.h.setSuffix(" px")
        self.dpi = QSpinBox()
        self.dpi.setRange(36, 1200)
        self.dpi.setValue(int(s.get("new_dpi", 150)))
        form.addRow("Ширина", self.w)
        form.addRow("Высота", self.h)
        form.addRow("Разрешение, dpi", self.dpi)
        self.bg = QComboBox()
        for key, label in (("#FFFFFF", "Белая бумага"), ("#F6F1E4", "Тёплая бумага"), ("transparent", "Прозрачный"),
                           ("#141413", "Чёрный")):
            self.bg.addItem(label, key)
        self.bg.setCurrentIndex(max(0, self.bg.findData(s.get("new_background", "#FFFFFF"))))
        form.addRow("Фон", self.bg)
        self.fps = QSpinBox()
        self.fps.setRange(1, 120)
        self.fps.setValue(24)
        self.secs = QDoubleSpinBox()
        self.secs.setRange(0.1, 600)
        self.secs.setValue(2.0)
        self.secs.setSuffix(" с")
        form.addRow("Анимация: кадров/с", self.fps)
        form.addRow("Анимация: длительность", self.secs)
        lay.addLayout(form)
        self.note = QLabel()
        self.note.setObjectName("Muted")
        lay.addWidget(self.note)
        for wdg in (self.w, self.h, self.dpi):
            wdg.valueChanged.connect(self._note)
        self._note()
        lay.addWidget(buttons(self, "Создать"))

    def _preset(self, i):
        p = self.preset.itemData(i)
        if p:
            _n, w, h, dpi, bg = p
            self.w.setValue(w)
            self.h.setValue(h)
            self.dpi.setValue(dpi)
            self.bg.setCurrentIndex(max(0, self.bg.findData(bg or "transparent")))

    def _note(self):
        w, h, dpi = self.w.value(), self.h.value(), self.dpi.value()
        mb = w * h * 4 / 1024 / 1024
        self.note.setText(f"{w / dpi * 25.4:.0f} × {h / dpi * 25.4:.0f} мм · ~{mb:.0f} МБ на слой")


class AdjustDialog(QDialog):
    """Generic adjustment: `params` = [(key, label, min, max, default)]; `apply(values) → None` previews."""

    def __init__(self, win, name, params, preview, checks=()):
        super().__init__(win)
        self.setWindowTitle(name)
        self.preview_fn = preview
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.addWidget(title(name))
        form = QFormLayout()
        self.values = {}
        self.sliders = {}
        for key, label, lo, hi, default in params:
            s = QSlider(Qt.Horizontal)
            s.setRange(lo, hi)
            s.setValue(default)
            val = QLabel(str(default))
            val.setFixedWidth(40)
            s.valueChanged.connect(lambda v, k=key, lab=val: (lab.setText(str(v)), self._changed()))
            row = QHBoxLayout()
            row.addWidget(s, 1)
            row.addWidget(val)
            form.addRow(label, row)
            self.sliders[key] = s
        self.checks = {}
        for key, label in checks:
            cb = QCheckBox(label)
            cb.toggled.connect(self._changed)
            form.addRow("", cb)
            self.checks[key] = cb
        lay.addLayout(form)
        self.live = QCheckBox("Предпросмотр")
        self.live.setChecked(True)
        self.live.toggled.connect(self._changed)
        lay.addWidget(self.live)
        lay.addWidget(buttons(self, "Применить"))
        self.timer = QTimer(self, singleShot=True, interval=120, timeout=self._run)
        self.setMinimumWidth(420)
        QTimer.singleShot(0, self._run)

    def result_values(self):
        v = {k: s.value() for k, s in self.sliders.items()}
        v.update({k: c.isChecked() for k, c in self.checks.items()})
        return v

    def _changed(self, *_):
        self.timer.start()

    def _run(self):
        self.preview_fn(self.result_values() if self.live.isChecked() else None)


class TextDialog(QDialog):
    def __init__(self, win, text=""):
        super().__init__(win)
        self.setWindowTitle("Текст")
        s = win.settings
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.addWidget(title("Текст"))
        self.text = QPlainTextEdit(text)
        self.text.setObjectName("Input")
        self.text.setPlaceholderText("Реплика или подпись…")
        self.text.setMinimumHeight(90)
        lay.addWidget(self.text)
        form = QFormLayout()
        self.font = QFontComboBox()
        fam = s.get("text_font") or ""
        if fam in QFontDatabase.families():
            self.font.setCurrentText(fam)
        self.size = QSpinBox()
        self.size.setRange(4, 600)
        self.size.setValue(int(s.get("text_size", 36)))
        self.size.setSuffix(" px")
        self.bold = QCheckBox("Жирный")
        self.vertical = QCheckBox("Вертикально (как в японской манге)")
        self.vertical.setChecked(bool(s.get("text_vertical")))
        self.outline = QCheckBox("Белая обводка")
        form.addRow("Шрифт", self.font)
        form.addRow("Размер", self.size)
        form.addRow("", self.bold)
        form.addRow("", self.vertical)
        form.addRow("", self.outline)
        lay.addLayout(form)
        lay.addWidget(buttons(self, "Добавить"))


class ExportDialog(QDialog):
    KINDS = [("png", "PNG — текущий кадр"), ("jpg", "JPEG — текущий кадр"), ("webp", "WebP — текущий кадр"),
             ("psd", "Photoshop PSD — со слоями"), ("ora", "OpenRaster ORA — со слоями (Krita)"),
             ("gif", "GIF — анимация"), ("mp4", "MP4 — анимация (нужен ffmpeg)"), ("sequence", "PNG-последовательность")]

    def __init__(self, win, doc):
        super().__init__(win)
        self.setWindowTitle("Экспорт")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.addWidget(title("Экспорт"))
        form = QFormLayout()
        self.kind = QComboBox()
        for k, label in self.KINDS:
            self.kind.addItem(label, k)
        form.addRow("Формат", self.kind)
        self.scale = QSpinBox()
        self.scale.setRange(10, 400)
        self.scale.setValue(int(float(win.settings.get("export_scale", 1)) * 100))
        self.scale.setSuffix(" %")
        form.addRow("Масштаб", self.scale)
        lay.addLayout(form)
        self.info = QLabel()
        self.info.setObjectName("Muted")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        self.doc = doc
        self.kind.currentIndexChanged.connect(self._sync)
        self.scale.valueChanged.connect(self._sync)
        self._sync()
        lay.addWidget(buttons(self, "Экспортировать…"))

    def _sync(self):
        k = self.kind.currentData()
        d = self.doc
        sc = self.scale.value() / 100
        size = f"{int(d.width * sc)}×{int(d.height * sc)} px"
        if k in ("gif", "mp4", "sequence"):
            self.info.setText(f"{size} · {d.length} кадров · {d.fps} к/с · {d.length / d.fps:.1f} с")
        elif k in ("psd", "ora"):
            self.info.setText(f"{d.width}×{d.height} px · {len(d.layers)} слоёв (масштаб не применяется)")
        else:
            self.info.setText(size)


class PanelGridDialog(QDialog):
    """Manga page layout: rows × columns of panels with gutters."""

    def __init__(self, win):
        super().__init__(win)
        self.setWindowTitle("Раскадровка страницы")
        s = win.settings
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.addWidget(title("Раскадровка"))
        form = QFormLayout()
        self.rows = QSpinBox()
        self.rows.setRange(1, 12)
        self.rows.setValue(3)
        self.cols = QSpinBox()
        self.cols.setRange(1, 8)
        self.cols.setValue(2)
        self.margin = QSpinBox()
        self.margin.setRange(0, 1000)
        self.margin.setValue(60)
        self.gutter = QSpinBox()
        self.gutter.setRange(0, 400)
        self.gutter.setValue(int(s.get("panel_gutter", 24)))
        self.width_ = QSpinBox()
        self.width_.setRange(1, 60)
        self.width_.setValue(int(s.get("panel_width", 6)))
        form.addRow("Рядов", self.rows)
        form.addRow("Колонок", self.cols)
        form.addRow("Поля страницы, px", self.margin)
        form.addRow("Промежуток, px", self.gutter)
        form.addRow("Толщина рамки, px", self.width_)
        lay.addLayout(form)
        lay.addWidget(buttons(self, "Разметить"))


class CanvasSizeDialog(QDialog):
    def __init__(self, win, doc, scale=False):
        super().__init__(win)
        self.setWindowTitle("Размер изображения" if scale else "Размер холста")
        self.doc = doc
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.addWidget(title("Размер изображения" if scale else "Размер холста"))
        form = QFormLayout()
        self.w = QSpinBox()
        self.w.setRange(1, 20000)
        self.w.setValue(doc.width)
        self.h = QSpinBox()
        self.h.setRange(1, 20000)
        self.h.setValue(doc.height)
        self.keep = QCheckBox("Сохранять пропорции")
        self.keep.setChecked(scale)
        self.w.valueChanged.connect(self._w)
        form.addRow("Ширина", self.w)
        form.addRow("Высота", self.h)
        form.addRow("", self.keep)
        lay.addLayout(form)
        self.anchor = None
        if not scale:
            grid = QGridLayout()
            self.anchor = QButtonGroup(self)
            for i, a in enumerate("↖↑↗←•→↙↓↘"):
                b = QToolButton()
                b.setText(a)
                b.setCheckable(True)
                b.setFixedSize(30, 30)
                self.anchor.addButton(b, i)
                grid.addWidget(b, i // 3, i % 3)
            self.anchor.button(4).setChecked(True)
            row = QHBoxLayout()
            lab = QLabel("Привязка")
            lab.setObjectName("Muted")
            row.addWidget(lab)
            row.addLayout(grid)
            row.addStretch(1)
            lay.addLayout(row)
        lay.addWidget(buttons(self))

    def _w(self, v):
        if self.keep.isChecked():
            self.h.blockSignals(True)
            self.h.setValue(max(1, round(v * self.doc.height / self.doc.width)))
            self.h.blockSignals(False)

    def offset(self):
        i = self.anchor.checkedId() if self.anchor else 4
        dw, dh = self.w.value() - self.doc.width, self.h.value() - self.doc.height
        return (dw * (i % 3)) // 2, (dh * (i // 3)) // 2


