"""«Студия»: put a photo in the background and pose the character (one or several copies, or other models)
anywhere on it — move, scale, mirror, layer order, ready-made poses and emotions, parameter sliders per copy —
then export the picture. Scenes are stored inside the .mu file."""
from pathlib import Path

import numpy as np
from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QTransform
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QInputDialog, QListWidget, QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget)

from . import fileio
from .model import new_id
from .panels import ParamPanel, PosesPanel, apply_pose_values, pose_thumb_bytes, section, tool_button
from .render import Renderer

DEFAULT_SIZE = (1920, 1080)


class Instance:
    def __init__(self, model, src="self", x=960.0, y=1000.0, scale=0.4, flip=False, values=None, name=""):
        self.model = model
        self.src = src
        self.x, self.y, self.scale, self.flip = x, y, scale, flip
        self.values = dict(values) if values else {p.id: p.default for p in model.params}
        self.name = name or model.name
        self._frame = None
        self._renderer = None

    def frame(self):
        if self._frame is None:
            self._frame = self.model.evaluate(self.values)
        return self._frame

    def renderer(self):
        if self._renderer is None or self._renderer.model is not self.model:
            self._renderer = Renderer(self.model)
        return self._renderer

    def touch(self):
        self._frame = None

    def transform(self):
        """Model canvas → scene: (x, y) is the bottom centre of the model canvas."""
        m = self.model
        t = QTransform()
        t.translate(self.x, self.y)
        t.scale(-self.scale if self.flip else self.scale, self.scale)
        t.translate(-m.width / 2, -m.height)
        return t

    def bounds(self):
        fr = self.frame()
        pts = [v for v, op, _ in fr.meshes.values() if op > 0.02 and len(v)]
        if not pts:
            return QRectF()
        a = np.concatenate(pts)
        lo, hi = a.min(0), a.max(0)
        return self.transform().mapRect(QRectF(lo[0], lo[1], hi[0] - lo[0], hi[1] - lo[1]))

    def to_dict(self):
        return {"src": self.src, "x": self.x, "y": self.y, "scale": self.scale, "flip": self.flip,
                "values": self.values, "name": self.name}


class StudioView(QWidget):
    selectionChanged = Signal()
    changed = Signal()

    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.c = colors
        self.instances = []
        self.selected = None
        self.bg = None            # QImage
        self.size_ = DEFAULT_SIZE
        self.drag = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(320, 240)

    def scene_rect(self):
        w, h = self.size_
        k = min((self.width() - 40) / w, (self.height() - 40) / h)
        k = max(0.05, k)
        return QRectF((self.width() - w * k) / 2, (self.height() - h * k) / 2, w * k, h * k), k

    def view_T(self):
        r, k = self.scene_rect()
        t = QTransform()
        t.translate(r.x(), r.y())
        t.scale(k, k)
        return t

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(self.c["canvas"]))
        r, k = self.scene_rect()
        p.fillRect(r, QColor(self.c["checker_a"]))
        V = self.view_T()
        self.paint_scene(p, V, r.toRect())
        p.setPen(QPen(QColor(self.c["border"]), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(r)
        if self.selected is not None and self.selected in self.instances:
            b = V.mapRect(self.selected.bounds())
            p.setPen(QPen(QColor(self.c["accent"]), 1.5, Qt.DashLine))
            p.drawRect(b.adjusted(-4, -4, 4, 4))
        if not self.instances:
            p.setPen(QColor(self.c["muted"]))
            p.drawText(self.rect(), Qt.AlignCenter, "Добавьте модель на сцену кнопкой слева")
        p.end()

    def paint_scene(self, p, V, clip):
        if self.bg is not None:
            p.save()
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)
            p.setTransform(V)
            w, h = self.size_
            p.drawImage(QRectF(0, 0, w, h), self.bg)
            p.restore()
        for inst in self.instances:
            inst.renderer().render(p, inst.frame(), inst.transform() * V, clip)

    def render_image(self, scale=1.0):
        w, h = self.size_
        img = QImage(int(w * scale), int(h * scale), QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.paint_scene(p, QTransform.fromScale(scale, scale), img.rect())
        p.end()
        return img

    def to_scene(self, pos):
        inv, _ = self.view_T().inverted()
        return inv.map(QPointF(pos))

    def hit(self, pos):
        sp = self.to_scene(pos)
        for inst in reversed(self.instances):
            if inst.bounds().contains(sp):
                return inst
        return None

    def select(self, inst):
        if inst is not self.selected:
            self.selected = inst
            self.selectionChanged.emit()
        self.update()

    def mousePressEvent(self, e):
        self.setFocus()
        inst = self.hit(e.position())
        self.select(inst)
        if inst is not None and e.button() == Qt.LeftButton:
            self.drag = (inst, self.to_scene(e.position()), QPointF(inst.x, inst.y))

    def mouseMoveEvent(self, e):
        if self.drag is not None:
            inst, start, orig = self.drag
            d = self.to_scene(e.position()) - start
            inst.x, inst.y = orig.x() + d.x(), orig.y() + d.y()
            self.update()

    def mouseReleaseEvent(self, e):
        if self.drag is not None:
            self.drag = None
            self.changed.emit()

    def wheelEvent(self, e):
        inst = self.selected
        if inst is None:
            return
        f = 1.0015 ** e.angleDelta().y()
        inst.scale = max(0.02, min(5.0, inst.scale * f))
        self.update()
        self.changed.emit()

    def keyPressEvent(self, e):
        inst = self.selected
        if inst is None:
            return super().keyPressEvent(e)
        k = e.key()
        if k in (Qt.Key_Delete, Qt.Key_Backspace):
            self.instances.remove(inst)
            self.select(None)
        elif k == Qt.Key_F:
            inst.flip = not inst.flip
        elif k == Qt.Key_BracketRight:
            i = self.instances.index(inst)
            if i < len(self.instances) - 1:
                self.instances[i], self.instances[i + 1] = self.instances[i + 1], self.instances[i]
        elif k == Qt.Key_BracketLeft:
            i = self.instances.index(inst)
            if i > 0:
                self.instances[i], self.instances[i - 1] = self.instances[i - 1], self.instances[i]
        elif k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            step = 20 if e.modifiers() & Qt.ShiftModifier else 4
            inst.x += {Qt.Key_Left: -step, Qt.Key_Right: step}.get(k, 0)
            inst.y += {Qt.Key_Up: -step, Qt.Key_Down: step}.get(k, 0)
        else:
            return super().keyPressEvent(e)
        self.update()
        self.changed.emit()


class StudioPage(QWidget):
    """The «Студия» workspace."""
    status = Signal(str)

    def __init__(self, win, colors):
        super().__init__()
        self.win = win
        self.c = colors
        self.doc = None
        self.scene = None
        self._models = {}  # path → Model (other models added to the scene)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        split = QSplitter(Qt.Horizontal)
        lay.addWidget(split)
        # left: scenes + objects
        left = QWidget()
        left.setObjectName("LeftPanel")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(8, 8, 8, 8)
        h = QHBoxLayout()
        h.addWidget(section("Сцены"))
        h.addStretch(1)
        h.addWidget(tool_button("plus", "Новая сцена", colors, self.new_scene))
        h.addWidget(tool_button("trash", "Удалить сцену", colors, self.delete_scene))
        lv.addLayout(h)
        self.scenes = QListWidget()
        self.scenes.setMaximumHeight(130)
        self.scenes.currentRowChanged.connect(self.open_scene)
        self.scenes.itemDoubleClicked.connect(self.rename_scene)
        lv.addWidget(self.scenes)
        lv.addWidget(section("Фон"))
        bh = QHBoxLayout()
        b = QPushButton("Фото…")
        b.setToolTip("Поставить фотографию или картинку на фон")
        b.clicked.connect(self.choose_bg)
        bh.addWidget(b)
        b2 = QPushButton("Убрать")
        b2.clicked.connect(self.clear_bg)
        bh.addWidget(b2)
        lv.addLayout(bh)
        lv.addWidget(section("На сцене"))
        self.objects = QListWidget()
        self.objects.currentRowChanged.connect(self.pick_object)
        lv.addWidget(self.objects, 1)
        ab = QPushButton("+ Эта модель")
        ab.setObjectName("Accent")
        ab.clicked.connect(lambda: self.add_instance(None))
        lv.addWidget(ab)
        ob = QPushButton("+ Модель из файла .mu…")
        ob.clicked.connect(self.add_other)
        lv.addWidget(ob)
        row = QHBoxLayout()
        for name, tip, fn in (("flip", "Отразить (F)", self.flip), ("front", "Вперёд (])", lambda: self.order(1)),
                              ("back", "Назад ([)", lambda: self.order(-1)), ("trash", "Убрать со сцены", self.remove)):
            row.addWidget(tool_button(name, tip, colors, fn))
        row.addStretch(1)
        lv.addLayout(row)
        ex = QPushButton("Сохранить картинку…")
        ex.clicked.connect(self.export_png)
        lv.addWidget(ex)
        split.addWidget(left)
        # centre
        self.view = StudioView(colors)
        self.view.selectionChanged.connect(self.on_view_select)
        self.view.changed.connect(self.store)
        split.addWidget(self.view)
        # right: poses + params of the selected copy
        right = QSplitter(Qt.Vertical)
        right.setObjectName("RightPanel")
        self.poses = PosesPanel(colors)
        self.poses.thumb_fn = pose_thumbnail
        self.poses.applied.connect(self.apply_pose)
        self.poses.saveRequested.connect(self.save_pose)
        right.addWidget(self.poses)
        self.params = ParamPanel(None, colors, with_keys=False)
        self.params.valuesEdited.connect(self.on_values)
        right.addWidget(self.params)
        right.setSizes([430, 400])
        split.addWidget(right)
        split.setSizes([230, 880, 330])
        split.setStretchFactor(1, 1)

    # ------------------------------------------------------------------ doc / scenes
    def set_doc(self, doc):
        self.doc = doc
        self.poses.set_model(doc.model)
        self.reload_scenes()

    def reload_scenes(self):
        m = self.doc.model
        if not m.scenes:
            m.scenes.append(self.blank_scene("Сцена 1"))
        self.scenes.blockSignals(True)
        self.scenes.clear()
        for sc in m.scenes:
            self.scenes.addItem(sc.get("name", "Сцена"))
        self.scenes.blockSignals(False)
        self.scenes.setCurrentRow(0)
        self.open_scene(0)

    def blank_scene(self, name):
        return {"id": new_id("sc"), "name": name, "size": list(DEFAULT_SIZE), "instances": []}

    def open_scene(self, i):
        m = self.doc.model
        if not (0 <= i < len(m.scenes)):
            return
        self.scene = sc = m.scenes[i]
        self.view.size_ = tuple(sc.get("size", DEFAULT_SIZE))
        self.view.bg = None
        if sc.get("_bg_bytes"):
            img = QImage.fromData(QByteArray(sc["_bg_bytes"]))
            if not img.isNull():
                self.view.bg = img
        self.view.instances = []
        for d in sc.get("instances", []):
            model = self.model_for(d.get("src", "self"))
            if model is None:
                continue
            vals = {p.id: p.default for p in model.params}
            vals.update({k: v for k, v in d.get("values", {}).items() if model.param(k) is not None})
            self.view.instances.append(Instance(model, d.get("src", "self"), d.get("x", 960), d.get("y", 1000),
                                                d.get("scale", 0.4), d.get("flip", False), vals, d.get("name", "")))
        if not self.view.instances and not sc.get("instances"):
            self.add_instance(None, store=False)
        self.view.select(self.view.instances[0] if self.view.instances else None)
        self.refresh_objects()
        self.view.update()

    def model_for(self, src):
        if src == "self":
            return self.doc.model
        if src not in self._models:
            try:
                self._models[src] = fileio.load(src)
            except Exception:
                return None
        return self._models[src]

    def store(self):
        """Write the view state back into the scene dict (saved with the .mu file)."""
        if self.scene is None:
            return
        self.scene["instances"] = [i.to_dict() for i in self.view.instances]
        self.scene["size"] = list(self.view.size_)
        self.refresh_objects()
        self.win.mark_dirty()

    def refresh_objects(self):
        self.objects.blockSignals(True)
        self.objects.clear()
        for k, inst in enumerate(self.view.instances):
            self.objects.addItem(f"{k + 1}. {inst.name}")
        if self.view.selected in self.view.instances:
            self.objects.setCurrentRow(self.view.instances.index(self.view.selected))
        self.objects.blockSignals(False)

    def new_scene(self):
        m = self.doc.model
        m.scenes.append(self.blank_scene(f"Сцена {len(m.scenes) + 1}"))
        self.scenes.addItem(m.scenes[-1]["name"])
        self.scenes.setCurrentRow(len(m.scenes) - 1)
        self.win.mark_dirty()

    def delete_scene(self):
        m = self.doc.model
        i = self.scenes.currentRow()
        if len(m.scenes) <= 1 or not (0 <= i < len(m.scenes)):
            return
        m.scenes.pop(i)
        self.reload_scenes()
        self.win.mark_dirty()

    def rename_scene(self, it):
        i = self.scenes.row(it)
        name, ok = QInputDialog.getText(self, "Сцена", "Название:", text=it.text())
        if ok and name.strip():
            self.doc.model.scenes[i]["name"] = name.strip()
            it.setText(name.strip())
            self.win.mark_dirty()

    # ------------------------------------------------------------------ background
    def choose_bg(self):
        path, _ = QFileDialog.getOpenFileName(self, "Фото для фона", self.win.settings.get("last_dir", ""),
                                              "Изображения (*.png *.jpg *.jpeg *.webp *.bmp)")
        if path:
            self.set_bg_file(path)

    def set_bg_file(self, path):
        data = Path(path).read_bytes()
        img = QImage.fromData(QByteArray(data))
        if img.isNull():
            QMessageBox.warning(self, "Мю", "Не удалось открыть картинку")
            return
        self.scene["_bg_bytes"] = data
        self.view.bg = img
        self.view.size_ = (img.width(), img.height())
        # keep the characters standing on the new photo
        for inst in self.view.instances:
            inst.y = min(inst.y, img.height() * 0.95)
            inst.x = min(inst.x, img.width() * 0.9)
            inst.scale = min(inst.scale, img.height() * 0.85 / max(1, inst.model.height))
        self.store()
        self.view.update()

    def clear_bg(self):
        self.scene.pop("_bg_bytes", None)
        self.view.bg = None
        self.store()
        self.view.update()

    # ------------------------------------------------------------------ objects
    def add_instance(self, model=None, src="self", store=True):
        model = model or self.doc.model
        w, h = self.view.size_
        n = len(self.view.instances)
        scale = h * 0.85 / max(1, model.height)
        inst = Instance(model, src, w * (0.5 + 0.18 * ((n + 1) // 2) * (-1) ** n), h * 0.96, scale)
        self.view.instances.append(inst)
        self.view.select(inst)
        if store:
            self.store()
        self.view.update()

    def add_other(self):
        path, _ = QFileDialog.getOpenFileName(self, "Модель Мю", self.win.settings.get("last_dir", ""),
                                              "Модели Мю (*.mu)")
        if not path:
            return
        model = self.model_for(path)
        if model is None:
            QMessageBox.warning(self, "Мю", "Не удалось открыть модель")
            return
        self.add_instance(model, path)

    def pick_object(self, row):
        if 0 <= row < len(self.view.instances):
            self.view.select(self.view.instances[row])

    def on_view_select(self):
        inst = self.view.selected
        self.refresh_objects()
        if inst is None:
            self.params.bind_values(None, None)
            self.poses.set_model(self.doc.model if self.doc else None)
            return
        self.params.bind_values(inst.model, inst.values)
        self.poses.set_model(inst.model)

    def flip(self):
        if self.view.selected:
            self.view.selected.flip = not self.view.selected.flip
            self.view.update()
            self.store()

    def order(self, d):
        inst = self.view.selected
        if inst is None:
            return
        L = self.view.instances
        i = L.index(inst)
        j = max(0, min(len(L) - 1, i + d))
        L[i], L[j] = L[j], L[i]
        self.view.update()
        self.store()

    def remove(self):
        inst = self.view.selected
        if inst is not None:
            self.view.instances.remove(inst)
            self.view.select(None)
            self.store()

    # ------------------------------------------------------------------ poses
    def apply_pose(self, pose):
        inst = self.view.selected
        if inst is None:
            return
        target = apply_pose_values(inst.model, inst.values, pose, reset=pose.get("kind") != "Эмоция")
        if self.poses.blend.isChecked():
            self._animate(inst, dict(inst.values), target)
        else:
            inst.values.update(target)
            self.on_values()

    def _animate(self, inst, start, target, steps=10):
        from PySide6.QtCore import QTimer
        state = {"k": 0}

        def tick():
            state["k"] += 1
            t = state["k"] / steps
            t = t * t * (3 - 2 * t)
            for pid, v in target.items():
                a = start.get(pid, v)
                inst.values[pid] = a + (v - a) * t
            inst.touch()
            self.view.update()
            if state["k"] >= steps:
                timer.stop()
                self.params.refresh()
                self.store()
        timer = QTimer(self)
        timer.timeout.connect(tick)
        timer.start(16)

    def on_values(self):
        inst = self.view.selected
        if inst is not None:
            inst.touch()
            self.view.update()
            self.store()

    def save_pose(self):
        inst = self.view.selected
        if inst is None:
            return
        name, ok = QInputDialog.getText(self, "Сохранить позу", "Название позы:",
                                        text=f"Моя поза {len(inst.model.poses) + 1}")
        if not ok or not name.strip():
            return
        thumb = pose_thumbnail(inst.model, inst.values)
        inst.model.poses.append({"name": name.strip(), "kind": "Поза", "values": dict(inst.values),
                                 "thumb": pose_thumb_bytes(thumb)})
        self.poses.rebuild()
        if inst.model is self.doc.model:
            self.win.mark_dirty()
        else:
            fileio.save(inst.model, inst.src)
        self.status.emit(f"Поза «{name.strip()}» сохранена")

    def export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить картинку", str(Path(self.win.settings.get(
            "last_dir", "")) / f"{self.scene.get('name', 'Сцена')}.png"), "PNG (*.png);;JPEG (*.jpg)")
        if not path:
            return
        img = self.view.render_image(1.0)
        if path.lower().endswith((".jpg", ".jpeg")):
            flat = QImage(img.size(), QImage.Format_RGB32)
            flat.fill(QColor("#FFFFFF"))
            p = QPainter(flat)
            p.drawImage(0, 0, img)
            p.end()
            img = flat
        img.save(path)
        self.status.emit(f"Сохранено: {path}")


def pose_thumbnail(model, values, size=96, face=False):
    """Preview of a pose: the model's visible bounds at `values` (or just the head for emotions), fitted into
    a square."""
    fr = model.evaluate(values)
    pts = [v for v, op, _ in fr.meshes.values() if op > 0.02 and len(v)]
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    if not pts:
        return img
    a = np.concatenate(pts)
    lo, hi = a.min(0), a.max(0)
    if face:
        heads = [fr.meshes[m.id][0] for m in model.meshes() if m.role == "face" and m.id in fr.meshes]
        if heads:
            hp = np.concatenate(heads)
            c = (hp.min(0) + hp.max(0)) / 2
            r = (hp.max(0) - hp.min(0)).max() * 0.62
            lo, hi = c - r, c + r
        else:
            hi = np.array([hi[0], lo[1] + (hi[1] - lo[1]) * 0.3])
    w, h = max(1.0, hi[0] - lo[0]), max(1.0, hi[1] - lo[1])
    k = (size - 6) / max(w, h)
    t = QTransform()
    t.translate((size - w * k) / 2, (size - h * k) / 2)
    t.scale(k, k)
    t.translate(-lo[0], -lo[1])
    p = QPainter(img)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    Renderer(model).render(p, fr, t, img.rect())
    p.end()
    return img

