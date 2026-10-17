"""Main window: start screen + the model workspaces (Нарезка, Риг, Физика, Студия, Эфир, Гайдбук), menus,
import / export."""
import math
import sys
import time
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon, QImage, QKeySequence, QPalette
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QPushButton, QSlider, QSplitter, QStackedWidget, QTabBar, QToolButton,
                               QVBoxLayout, QWidget)

from . import APP_NAME, LOGO, __version__, art, autorig, fileio, icons
from .canvas import Canvas
from .doc import Doc
from .guide import GuidePage
from .home import Home
from .live import LivePage
from .model import ArtMesh, Param, RotationDeformer, STANDARD_PARAMS, WarpDeformer
from .panels import Inspector, ParamPanel, PartsTree, PhysicsPanel, section, tool_button
from .paths import Settings, resource_path
from .poses import add_default_poses
from .studio import StudioPage
from .theme import DARK, LIGHT, stylesheet

WORKSPACES = [("cut", "Нарезка"), ("rig", "Риг"), ("physics", "Физика"), ("studio", "Студия"), ("live", "Эфир"),
              ("guide", "Гайдбук")]


def prepare_model(model):
    for row in STANDARD_PARAMS:
        model.add_param(Param(*row))
    add_default_poses(model)
    return model


# ====================================================================== workspaces
class CutPage(QWidget):
    def __init__(self, win, doc, colors):
        super().__init__()
        self.win, self.c = win, colors
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        split = QSplitter(Qt.Horizontal)
        lay.addWidget(split)
        left = QWidget()
        left.setObjectName("LeftPanel")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        self.tree = PartsTree(doc, colors)
        lv.addWidget(self.tree)
        split.addWidget(left)
        mid = QWidget()
        mv = QVBoxLayout(mid)
        mv.setContentsMargins(0, 0, 0, 0)
        mv.setSpacing(0)
        bar = QWidget()
        bar.setObjectName("ContextBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 4, 8, 4)
        self.canvas = Canvas(doc, colors, win.settings, mode="cut")
        self.tools = {}
        for t, ic, tip in (("pick", "select", "Выбор слоя (V)"), ("lasso", "lasso", "Лассо (L)"),
                           ("polygon", "polygon", "Многоугольник (P)"), ("brush", "brush", "Кисть выделения (B)"),
                           ("wand", "wand", "Волшебная палочка (W)")):
            b = tool_button(ic, tip, colors, lambda _=False, t=t: self.canvas.set_tool(t), checkable=True, size=20)
            self.tools[t] = b
            bl.addWidget(b)
        bl.addSpacing(12)
        self.opt_brush = QSlider(Qt.Horizontal)
        self.opt_brush.setRange(2, 200)
        self.opt_brush.setValue(24)
        self.opt_brush.setFixedWidth(110)
        self.opt_brush.valueChanged.connect(lambda v: setattr(self.canvas, "brush_r", float(v)))
        self.lab_brush = QLabel("Кисть")
        bl.addWidget(self.lab_brush)
        bl.addWidget(self.opt_brush)
        self.lab_tol = QLabel("Допуск")
        self.opt_tol = QSlider(Qt.Horizontal)
        self.opt_tol.setRange(1, 128)
        self.opt_tol.setValue(32)
        self.opt_tol.setFixedWidth(110)
        self.opt_tol.valueChanged.connect(lambda v: setattr(self.canvas, "wand_tol", v))
        self.opt_contig = QCheckBox("Смежные")
        self.opt_contig.setChecked(True)
        self.opt_contig.toggled.connect(lambda on: setattr(self.canvas, "wand_contig", on))
        bl.addWidget(self.lab_tol)
        bl.addWidget(self.opt_tol)
        bl.addWidget(self.opt_contig)
        bl.addStretch(1)
        hint = QLabel("Shift — добавить · Alt — вычесть · Esc — снять")
        hint.setObjectName("Muted")
        bl.addWidget(hint)
        bl.addWidget(tool_button("fit", "Вписать (⌘0)", colors, self.canvas.fit))
        mv.addWidget(bar)
        mv.addWidget(self.canvas, 1)
        split.addWidget(mid)
        right = QWidget()
        right.setObjectName("RightPanel")
        rv = QVBoxLayout(right)
        rv.setContentsMargins(10, 10, 10, 10)
        rv.addWidget(section("Выделение"))
        self.sel_info = QLabel("Выберите слой и выделите область")
        self.sel_info.setObjectName("Muted")
        self.sel_info.setWordWrap(True)
        rv.addWidget(self.sel_info)
        self.b_cut = QPushButton("Вырезать в новый слой")
        self.b_cut.setObjectName("Accent")
        self.b_cut.clicked.connect(lambda: self.cut(False))
        rv.addWidget(self.b_cut)
        self.b_copy = QPushButton("Копировать в новый слой")
        self.b_copy.clicked.connect(lambda: self.cut(True))
        rv.addWidget(self.b_copy)
        self.fill = QCheckBox("Закрашивать дыру")
        self.fill.setChecked(True)
        self.fill.setToolTip("Пиксели под вырезанным заполняются цветом окружения")
        rv.addWidget(self.fill)
        self.role = QComboBox()
        for rid, rt in autorig.ROLES:
            self.role.addItem(rt, rid)
        self.role.setToolTip("Роль нового слоя (для авто-рига)")
        rv.addWidget(QLabel("Роль нового слоя"))
        rv.addWidget(self.role)
        rv.addSpacing(10)
        rv.addWidget(section("Слой"))
        for text, fn in (("Отразить копию", self.flip_copy), ("Объединить с нижним", self.merge_down),
                         ("Импорт картинки как слоя…", win.import_layer), ("Удалить слой", win.delete_selected)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            rv.addWidget(b)
        rv.addSpacing(10)
        self.inspector = Inspector(doc, colors)
        rv.addWidget(self.inspector, 1)
        split.addWidget(right)
        split.setSizes([230, 880, 310])
        split.setStretchFactor(1, 1)
        self.canvas.toolChanged.connect(self.on_tool)
        self.canvas.selectionMaskChanged.connect(self.on_mask)
        self.canvas.status.connect(win.show_status)
        self.canvas.set_tool("lasso")
        self.on_mask()

    def set_doc(self, doc):
        self.tree.set_doc(doc)
        self.canvas.set_doc(doc)
        self.inspector.set_doc(doc)

    def on_tool(self, t):
        for k, b in self.tools.items():
            b.setChecked(k == t)
        for w in (self.lab_brush, self.opt_brush):
            w.setVisible(t == "brush")
        for w in (self.lab_tol, self.opt_tol, self.opt_contig):
            w.setVisible(t == "wand")

    def on_mask(self):
        m = self.canvas.sel_mask
        on = m is not None
        self.b_cut.setEnabled(on)
        self.b_copy.setEnabled(on)
        if on:
            self.sel_info.setText(f"Выделено {int(m.sum()):,} пикс.".replace(",", " "))
        else:
            self.sel_info.setText("Выберите слой и выделите область лассо, многоугольником, кистью или палочкой")

    def cut(self, copy):
        cv = self.canvas
        doc = self.win.doc
        layer = doc.model.nodes.get(cv.sel_layer) if cv.sel_layer else None
        if layer is None or cv.sel_mask is None:
            return
        n = sum(1 for x in doc.model.meshes() if x.name.startswith(layer.name)) + 1
        role = self.role.currentData() or ""
        name = autorig.ROLE_TITLES.get(role) if role else f"{layer.name} — часть {n}"
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            new = art.cut_to_layer(doc.model, layer, cv.sel_mask, name, fill_hole=self.fill.isChecked(), copy=copy,
                                   role=role)
        finally:
            QApplication.restoreOverrideCursor()
        cv.clear_selection_mask()
        if new is not None:
            doc.renderer.reset()
            doc.commit()
            doc.select([new.id])
            self.win.show_status(f"Новый слой «{new.name}»")

    def flip_copy(self):
        doc = self.win.doc
        ms = doc.selected_meshes()
        if not ms:
            return
        cx = doc.model.width / 2
        for face in doc.model.meshes():
            if face.role == "face" and len(face.rest):
                cx = (face.rest[:, 0].min() + face.rest[:, 0].max()) / 2
        new = [art.flip_copy(doc.model, m, cx) for m in ms]
        for src, x in zip(ms, new):
            x.role = src.role
            if src.role.endswith(("_l", "_r")):
                x.role = src.role[:-1] + ("r" if src.role.endswith("l") else "l")
        doc.commit()
        doc.select([x.id for x in new])

    def merge_down(self):
        doc = self.win.doc
        ms = doc.selected_meshes()
        if len(ms) != 1:
            self.win.show_status("Выберите один слой — он сольётся со слоем под ним")
            return
        up = ms[0]
        below = [x for x in doc.model.meshes() if x.order < up.order]
        if not below:
            return
        lower = max(below, key=lambda x: x.order)
        art.merge_down(doc.model, up, lower)
        doc.renderer.reset()
        doc.commit()
        doc.select([lower.id])


class RigPage(QWidget):
    def __init__(self, win, doc, colors):
        super().__init__()
        self.win, self.c = win, colors
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        split = QSplitter(Qt.Horizontal)
        lay.addWidget(split)
        left = QWidget()
        left.setObjectName("LeftPanel")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        self.tree = PartsTree(doc, colors)
        lv.addWidget(self.tree)
        split.addWidget(left)
        mid = QWidget()
        mv = QVBoxLayout(mid)
        mv.setContentsMargins(0, 0, 0, 0)
        mv.setSpacing(0)
        bar = QWidget()
        bar.setObjectName("ContextBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 4, 8, 4)
        self.canvas = Canvas(doc, colors, win.settings, mode="rig")
        self.tools = {}
        for t, ic, tip in (("edit", "move", "Деформация (E): точки и части меняют форму в текущем ключе"),
                           ("mesh", "mesh", "Правка сетки (M): точки скользят по текстуре")):
            b = tool_button(ic, tip, colors, lambda _=False, t=t: self.canvas.set_tool(t), checkable=True, size=20)
            self.tools[t] = b
            bl.addWidget(b)
        bl.addSpacing(10)
        bl.addWidget(tool_button("warp", "Обернуть выбранное деформером-сеткой", colors, self.add_warp, size=20))
        bl.addWidget(tool_button("rotate", "Обернуть выбранное деформером вращения", colors, self.add_rot, size=20))
        bl.addSpacing(10)
        bl.addWidget(QLabel("Сетка"))
        self.density = QSlider(Qt.Horizontal)
        self.density.setRange(12, 120)
        self.density.setValue(48)
        self.density.setInvertedAppearance(True)
        self.density.setFixedWidth(90)
        self.density.setToolTip("Плотность авто-сетки (меньше шаг — больше точек)")
        bl.addWidget(self.density)
        bl.addWidget(tool_button("automesh", "Перестроить сетку выбранных слоёв", colors, self.remesh, size=20))
        bl.addWidget(tool_button("physics", "Риг пряди: деформер, параметры X1…Xn / Y / S и маятник-цепочка "
                                            "(как физика волос в Cubism)", colors, self.strand_rig, size=20))
        bl.addSpacing(10)
        ar = QPushButton("  Авто-риг")
        ar.setIcon(icons.icon("auto", colors["accent_text"], colors["accent_text"]))
        ar.setObjectName("Accent")
        ar.clicked.connect(win.run_autorig)
        bl.addWidget(ar)
        bl.addStretch(1)
        self.b_wire = tool_button("wire", "Показывать сетку", colors, self.toggle_wire, checkable=True)
        self.b_wire.setChecked(self.canvas.show_wire)
        bl.addWidget(self.b_wire)
        self.b_def = tool_button("warp", "Показывать деформеры", colors, self.toggle_def, checkable=True)
        self.b_def.setChecked(self.canvas.show_deformers)
        bl.addWidget(self.b_def)
        self.b_solo = tool_button("eye", "Показывать только выбранное", colors, self.toggle_solo, checkable=True)
        bl.addWidget(self.b_solo)
        bl.addWidget(tool_button("fit", "Вписать (⌘0)", colors, self.canvas.fit))
        mv.addWidget(bar)
        mv.addWidget(self.canvas, 1)
        self.keybar = QLabel()
        self.keybar.setObjectName("Muted")
        self.keybar.setContentsMargins(10, 4, 10, 4)
        mv.addWidget(self.keybar)
        split.addWidget(mid)
        right = QSplitter(Qt.Vertical)
        right.setObjectName("RightPanel")
        self.inspector = Inspector(doc, colors)
        right.addWidget(self.inspector)
        self.params = ParamPanel(doc, colors)
        right.addWidget(self.params)
        right.setSizes([360, 460])
        split.addWidget(right)
        split.setSizes([230, 860, 340])
        split.setStretchFactor(1, 1)
        self.canvas.toolChanged.connect(self.on_tool)
        self.canvas.status.connect(win.show_status)
        self.canvas.set_tool("edit")
        self.connect_doc(doc)

    def connect_doc(self, doc):
        doc.activeParamChanged.connect(self.update_keybar)
        doc.valuesChanged.connect(self.update_keybar)
        doc.selectionChanged.connect(self.update_keybar)
        self.update_keybar()

    def set_doc(self, doc):
        self.tree.set_doc(doc)
        self.canvas.set_doc(doc)
        self.inspector.set_doc(doc)
        self.params.set_doc(doc)
        self.connect_doc(doc)

    def update_keybar(self):
        doc = self.win.doc if self.win.doc else None
        if doc is None:
            return
        p = doc.model.param(doc.active_param) if doc.active_param else None
        if p is None:
            self.keybar.setText("Нет активного параметра")
            return
        v = doc.model.values.get(p.id, p.default)
        nodes = doc.nodes()
        where = "правка меняет основную форму (без ключей)"
        if nodes:
            kind, b, i = doc.edit_target(nodes[0])
            if kind == "key":
                where = f"правка попадёт в ключ ◆ {b.keys[i]:g}"
            elif kind == "between":
                where = "между ключами — правка создаст новый ключ"
            elif abs(v - p.default) > 1e-6:
                where = f"правка создаст ключи ◆ {p.default:g} и {v:g}"
        self.keybar.setText(f"Активный параметр: {p.name} = {v:g}   ·   {where}")

    def on_tool(self, t):
        for k, b in self.tools.items():
            b.setChecked(k == t)

    def toggle_wire(self, on):
        self.canvas.show_wire = on
        self.win.settings["show_wire"] = on
        self.canvas.update()

    def toggle_def(self, on):
        self.canvas.show_deformers = on
        self.win.settings["show_deformers"] = on
        self.canvas.update()

    def toggle_solo(self, on):
        self.canvas.solo = on
        self.canvas.update()

    def _wrap(self, node):
        doc = self.win.doc
        sel = doc.nodes()
        parents = {n.parent for n in sel}
        node.parent = parents.pop() if len(parents) == 1 else None
        doc.model.add(node)
        for n in sel:
            n.parent = node.id
        doc.commit()
        doc.select([node.id])

    def _sel_box(self):
        doc = self.win.doc
        fr = doc.frame()
        pts = []
        for n in doc.nodes():
            if isinstance(n, ArtMesh) and len(n.rest):
                pts.append(n.rest)
            elif isinstance(n, WarpDeformer):
                pts.append(n.rest_grid())
        if not pts:
            return None
        import numpy as np
        a = np.concatenate(pts)
        _ = fr
        return a.min(0), a.max(0)

    def add_warp(self):
        box = self._sel_box()
        if box is None:
            self.win.show_status("Выберите слои, которые нужно обернуть деформером")
            return
        (x0, y0), (x1, y1) = box
        pad = 0.06 * max(x1 - x0, y1 - y0)
        name = "Сетка: " + (self.win.doc.nodes()[0].name if self.win.doc.nodes() else "")
        self._wrap(WarpDeformer(name=name, rect=(x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad),
                                rows=4, cols=4))

    def add_rot(self):
        box = self._sel_box()
        if box is None:
            self.win.show_status("Выберите слои, которые нужно вращать")
            return
        (x0, y0), (x1, y1) = box
        name = "Вращение: " + (self.win.doc.nodes()[0].name if self.win.doc.nodes() else "")
        self._wrap(RotationDeformer(name=name, origin=((x0 + x1) / 2, y1 - (y1 - y0) * 0.1),
                                    length=max(60.0, (y1 - y0) * 0.6)))
        self.win.show_status("Перетащите круг — центр вращения, точку на ручке — угол (в ключе параметра)")

    def strand_rig(self):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QSpinBox
        doc = self.win.doc
        meshes = doc.selected_meshes()
        for d in doc.selected_deformers():
            meshes += [x for x in doc.model.meshes() if x.parent == d.id]
        if not meshes:
            self.win.show_status("Выберите слои пряди (чёлка, локон, хвостик, ушки, ленточка…)")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Риг пряди")
        f = QFormLayout(dlg)
        name = QLineEdit(meshes[0].name.split(":")[0].strip() or "Прядь")
        f.addRow("Название", name)
        segs = QSpinBox()
        segs.setRange(1, 6)
        segs.setValue(3)
        f.addRow("Звеньев (X1…Xn)", segs)
        direc = QComboBox()
        for k, t in autorig.DIRECTIONS.items():
            direc.addItem(f"Растёт {t}", k)
        f.addRow("Направление", direc)
        amp = QSpinBox()
        amp.setRange(4, 60)
        amp.setValue(22)
        amp.setSuffix("°")
        f.addRow("Изгиб звена", amp)
        phys = QCheckBox("Добавить маятник-цепочку в физику")
        phys.setChecked(True)
        f.addRow("", phys)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        f.addRow(bb)
        if dlg.exec() != QDialog.Accepted:
            return
        w, ids, g = autorig.rig_strand(doc.model, meshes, name.text().strip() or "Прядь", direc.currentData(),
                                       segs.value(), float(amp.value()), phys.isChecked())
        doc.commit()
        doc.select([w.id])
        doc.active_param = ids[0]
        doc.activeParamChanged.emit()
        self.win.show_status(f"Риг пряди «{name.text()}»: параметры {', '.join(ids)}"
                             + (" и физика" if g else ""))

    def remesh(self):
        doc = self.win.doc
        ms = doc.selected_meshes() or doc.model.meshes()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for m in ms:
                art.remesh(doc.model, m, spacing=self.density.value())
        finally:
            QApplication.restoreOverrideCursor()
        doc.commit()


class PhysicsPage(QWidget):
    def __init__(self, win, doc, colors):
        super().__init__()
        self.win = win
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        mid = QWidget()
        mv = QVBoxLayout(mid)
        mv.setContentsMargins(0, 0, 0, 0)
        mv.setSpacing(0)
        bar = QWidget()
        bar.setObjectName("ContextBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 4, 8, 4)
        self.b_test = QPushButton("  Проверка")
        self.b_test.setIcon(icons.icon("play", colors["text"], colors["accent"]))
        self.b_test.setCheckable(True)
        self.b_test.toggled.connect(self.toggle)
        bl.addWidget(self.b_test)
        self.motion = QComboBox()
        for k, t in (("sway", "Качать головой"), ("tilt", "Наклоны"), ("mouse", "За мышью")):
            self.motion.addItem(t, k)
        bl.addWidget(self.motion)
        bl.addStretch(1)
        mv.addWidget(bar)
        self.canvas = Canvas(doc, colors, win.settings, mode="view")
        mv.addWidget(self.canvas, 1)
        lay.addWidget(mid, 1)
        side = QWidget()
        side.setObjectName("RightPanel")
        side.setFixedWidth(400)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 0, 0, 0)
        self.panel = PhysicsPanel(doc, colors)
        sv.addWidget(self.panel)
        lay.addWidget(side)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.step)
        self.saved = None
        self.t0 = 0.0

    def set_doc(self, doc):
        self.b_test.setChecked(False)
        self.canvas.set_doc(doc)
        self.panel.set_doc(doc)

    def toggle(self, on):
        doc = self.win.doc
        if on:
            self.saved = dict(doc.model.values)
            doc.physics.reset()
            self.t0 = time.monotonic()
            self.last = self.t0
            self.timer.start(16)
        else:
            self.timer.stop()
            if self.saved is not None:
                doc.model.values = self.saved
                self.saved = None
                doc.touch()

    def step(self):
        doc = self.win.doc
        now = time.monotonic()
        t = now - self.t0
        dt = now - self.last
        self.last = now
        vals = dict(self.saved)
        kind = self.motion.currentData()
        if kind == "sway":
            vals["ParamAngleX"] = 30 * math.sin(t * 2.2)
            vals["ParamBodyAngleX"] = 8 * math.sin(t * 2.2 - 0.6)
        elif kind == "tilt":
            vals["ParamAngleZ"] = 30 * math.sin(t * 1.6)
            vals["ParamBodyAngleZ"] = 8 * math.sin(t * 1.6 - 0.5)
        else:
            pos = self.canvas.mapFromGlobal(self.cursor().pos())
            nx = max(-1, min(1, (pos.x() - self.canvas.width() / 2) / max(1, self.canvas.width() / 2)))
            vals["ParamAngleX"] = 30 * nx
            vals["ParamBodyAngleX"] = 10 * nx
        doc.physics.step(dt, vals)
        doc.model.values = {k: (doc.model.param(k).clamp(v) if doc.model.param(k) else v) for k, v in vals.items()}
        doc.touch()


# ====================================================================== main window
class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.settings = Settings()
        self.colors = DARK if self._is_dark() else LIGHT
        app.setStyleSheet(stylesheet(self.colors))
        self.doc = None
        self.setWindowTitle(APP_NAME)
        self.resize(1440, 900)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.home = Home(self)
        self.stack.addWidget(self.home)
        self.work = None
        self.pages = {}
        self.build_menus()
        self.statusBar().showMessage("Готово")
        self.dirty_extra = False

    # ------------------------------------------------------------------ workspace
    def build_work(self, doc):
        c = self.colors
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        top = QWidget()
        top.setObjectName("TopBar")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(10, 4, 10, 4)
        home = QToolButton()
        home.setIcon(icons.icon("logo", c["text"], c["accent"]))
        home.setIconSize(QSize(22, 22))
        home.setToolTip("На главную")
        home.clicked.connect(self.go_home)
        tl.addWidget(home)
        self.file_label = QLabel()
        self.file_label.setObjectName("FileName")
        tl.addWidget(self.file_label)
        tl.addSpacing(16)
        self.tabs = QTabBar()
        self.tabs.setObjectName("DocTabs")
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)
        for key, title in WORKSPACES:
            self.tabs.addTab(title)
        self.tabs.currentChanged.connect(self.switch)
        tl.addWidget(self.tabs)
        tl.addStretch(1)
        for name, tip, fn in (("undo", "Отменить (⌘Z)", lambda: self.doc and self.doc.undo()),
                              ("redo", "Вернуть (⇧⌘Z)", lambda: self.doc and self.doc.redo()),
                              ("save", "Сохранить (⌘S)", self.save),
                              ("export", "Экспорт для VTube Studio (.moc3, эксперимент)", self.export_moc3)):
            tl.addWidget(tool_button(name, tip, c, fn, size=18))
        v.addWidget(top)
        self.pstack = QStackedWidget()
        v.addWidget(self.pstack, 1)
        self.pages = {"cut": CutPage(self, doc, c), "rig": RigPage(self, doc, c), "physics": PhysicsPage(self, doc, c),
                      "studio": StudioPage(self, c), "live": LivePage(self, c), "guide": GuidePage(c)}
        for key, _ in WORKSPACES:
            self.pstack.addWidget(self.pages[key])
        self.pages["studio"].status.connect(self.show_status)
        self.pages["live"].status.connect(self.show_status)
        self.work = w
        self.stack.addWidget(w)

    def set_doc(self, doc, workspace="rig"):
        self.doc = doc
        if self.work is None:
            self.build_work(doc)
        for key in ("cut", "rig", "physics", "studio", "live"):
            self.pages[key].set_doc(doc)
        doc.titleChanged.connect(self.update_title)
        self.dirty_extra = False
        self.stack.setCurrentWidget(self.work)
        idx = [k for k, _ in WORKSPACES].index(workspace)
        if self.tabs.currentIndex() == idx:
            self.switch(idx)
        else:
            self.tabs.setCurrentIndex(idx)
        self.update_title()
        for key in ("cut", "rig", "physics"):
            QTimer.singleShot(0, self.pages[key].canvas.fit)

    def switch(self, i):
        key = WORKSPACES[i][0]
        if key != "live" and "live" in self.pages:
            self.pages["live"].stop()
        if key != "physics" and "physics" in self.pages:
            self.pages["physics"].b_test.setChecked(False)
        if key == "studio" and self.doc is not None:
            self.pages["studio"].poses.rebuild()
            self.pages["studio"].view.update()
        if key == "live" and self.doc is not None:
            self.pages["live"].set_doc(self.doc)
        self.pstack.setCurrentWidget(self.pages[key])
        page = self.pages[key]
        if hasattr(page, "canvas") and isinstance(page.canvas, Canvas):
            page.canvas.setFocus()

    def workspace(self):
        return WORKSPACES[self.tabs.currentIndex()][0] if self.work is not None else None

    def go_home(self):
        if self.doc is not None and not self.maybe_save():
            return
        if "live" in self.pages:
            self.pages["live"].shutdown()
        self.doc = None
        self.home.rebuild()
        self.stack.setCurrentWidget(self.home)
        self.setWindowTitle(APP_NAME)

    def open_guide(self):
        if self.work is None or self.doc is None:
            from .model import Model
            doc = Doc(prepare_model(Model("Без названия", 1200, 1600)))
            self.set_doc(doc, "guide")
        else:
            self.tabs.setCurrentIndex([k for k, _ in WORKSPACES].index("guide"))

    def show_status(self, text):
        self.statusBar().showMessage(text, 6000)

    def mark_dirty(self):
        self.dirty_extra = True
        self.update_title()

    def is_dirty(self):
        return self.doc is not None and (self.doc.dirty() or self.dirty_extra)

    def update_title(self):
        if self.doc is None:
            return
        t = self.doc.title() + (" •" if self.is_dirty() else "")
        self.file_label.setText(t)
        self.setWindowTitle(f"{t} — {APP_NAME}")

    # ------------------------------------------------------------------ menus
    def build_menus(self):
        mb = self.menuBar()
        f = mb.addMenu("Файл")
        self._act(f, "Новая модель из PSD…", self.new_from_psd, QKeySequence.New)
        self._act(f, "Новая модель из картинки…", self.new_from_image)
        self._act(f, "Открыть…", self.open_dialog, QKeySequence.Open)
        self.recent_menu = f.addMenu("Недавние")
        self.recent_menu.aboutToShow.connect(self.fill_recent)
        f.addSeparator()
        self._act(f, "Сохранить", self.save, QKeySequence.Save)
        self._act(f, "Сохранить как…", self.save_as, QKeySequence.SaveAs)
        f.addSeparator()
        imp = f.addMenu("Импорт")
        self._act(imp, "Картинка как новый слой…", self.import_layer)
        self._act(imp, "Слои из PSD в эту модель…", self.import_psd_layers)
        self._act(imp, "Модель Inochi2D (.inp)…", self.import_inp)
        ex = f.addMenu("Экспорт")
        self._act(ex, "Cubism .moc3 для VTube Studio (эксперимент)…", self.export_moc3)
        self._act(ex, "Inochi2D (.inp)…", self.export_inp)
        self._act(ex, "PSD со слоями…", self.export_psd)
        self._act(ex, "PNGTuber (4 картинки)…", self.export_pngtuber)
        self._act(ex, "Картинка PNG…", self.export_png)
        f.addSeparator()
        self._act(f, "На главную", self.go_home, "Ctrl+Shift+H")
        self._act(f, "Выход", self.close, QKeySequence.Quit)
        e = mb.addMenu("Правка")
        self._act(e, "Отменить", lambda: self.doc and self.doc.undo(), QKeySequence.Undo)
        self._act(e, "Вернуть", lambda: self.doc and self.doc.redo(), QKeySequence.Redo)
        e.addSeparator()
        self._act(e, "Удалить выбранное", self.delete_selected, QKeySequence.Delete)
        self._act(e, "Выбрать все слои", self.select_all, QKeySequence.SelectAll)
        m = mb.addMenu("Модель")
        self._act(m, "Авто-риг…", self.run_autorig, "Ctrl+Shift+R")
        self._act(m, "Определить роли по названиям слоёв", self.guess_roles)
        self._act(m, "Убрать весь риг", self.strip_rig)
        self._act(m, "Сбросить параметры", lambda: self.doc and self.doc.set_values(
            {p.id: p.default for p in self.doc.model.params}))
        v = mb.addMenu("Вид")
        self._act(v, "Вписать в окно", self.fit, "Ctrl+0")
        th = v.addMenu("Тема")
        grp = QActionGroup(self)
        self.theme_actions = {}
        for key, title in (("system", "Как в системе"), ("light", "Светлая"), ("dark", "Тёмная")):
            a = th.addAction(title)
            a.setCheckable(True)
            a.setChecked(self.settings.get("theme", "system") == key)
            a.triggered.connect(lambda _=False, k=key: self.set_theme(k))
            grp.addAction(a)
            self.theme_actions[key] = a
        for key, title in WORKSPACES:
            self._act(v, title, lambda _=False, k=key: self.goto(k), f"Ctrl+{[w for w, _ in WORKSPACES].index(key) + 1}")
        h = mb.addMenu("Справка")
        self._act(h, "Гайдбук", self.open_guide, "F1")
        self._act(h, "О программе", self.about)
        # tool shortcuts (single keys) live on the canvases
        for key, tool in (("L", "lasso"), ("P", "polygon"), ("B", "brush"), ("W", "wand"), ("V", "pick"),
                          ("E", "edit"), ("M", "mesh")):
            a = QAction(self)
            a.setShortcut(key)
            a.setShortcutContext(Qt.WindowShortcut)
            a.triggered.connect(lambda _=False, t=tool: self.tool_key(t))
            self.addAction(a)

    def _act(self, menu, text, fn, shortcut=None):
        a = menu.addAction(text)
        a.triggered.connect(fn)
        if shortcut is not None:
            a.setShortcut(QKeySequence(shortcut))
        return a

    def tool_key(self, tool):
        ws = self.workspace()
        if ws == "cut" and tool in ("lasso", "polygon", "brush", "wand", "pick"):
            self.pages["cut"].canvas.set_tool(tool)
        elif ws == "rig" and tool in ("edit", "mesh"):
            self.pages["rig"].canvas.set_tool(tool)

    def goto(self, key):
        if self.work is not None and self.doc is not None:
            self.tabs.setCurrentIndex([k for k, _ in WORKSPACES].index(key))

    def fit(self):
        ws = self.workspace()
        if ws in ("cut", "rig", "physics"):
            self.pages[ws].canvas.fit()

    def fill_recent(self):
        self.recent_menu.clear()
        for p in self.settings.get("recent", [])[:12]:
            if Path(p).exists():
                self.recent_menu.addAction(Path(p).name, lambda p=p: self.open_path(p))
        if self.recent_menu.isEmpty():
            a = self.recent_menu.addAction("Пусто")
            a.setEnabled(False)

    # ------------------------------------------------------------------ files
    def _dir(self):
        return self.settings.get("last_dir", "") or str(Path.home())

    def _remember(self, path):
        self.settings["last_dir"] = str(Path(path).parent)
        self.settings.save()

    def new_from_psd(self):
        if not self.maybe_save():
            return
        path, _ = QFileDialog.getOpenFileName(self, "PSD со слоями", self._dir(), "Photoshop (*.psd)")
        if path:
            self.open_psd(path)

    def open_psd(self, path, ask_autorig=True):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            model = prepare_model(art.new_model_from_psd(path))
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, APP_NAME, f"Не удалось открыть PSD:\n{e}")
            return None
        QApplication.restoreOverrideCursor()
        self._remember(path)
        doc = Doc(model)
        self.set_doc(doc, "rig")
        n = len(model.meshes())
        known = sum(1 for m in model.meshes() if m.role)
        if ask_autorig:
            r = QMessageBox.question(self, APP_NAME, f"Импортировано слоёв: {n}, роли распознаны у {known}.\n\n"
                                                     "Сделать авто-риг сейчас? (Роли можно поправить в инспекторе и "
                                                     "запустить авто-риг позже — меню «Модель».)")
            if r == QMessageBox.Yes:
                self.run_autorig(confirm=False)
        return doc

    def new_from_image(self):
        if not self.maybe_save():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Картинка", self._dir(),
                                              "Изображения (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return
        img = QImage(path)
        if img.isNull():
            QMessageBox.warning(self, APP_NAME, "Не удалось открыть картинку")
            return
        if max(img.width(), img.height()) > 6000:
            img = img.scaled(6000, 6000, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._remember(path)
        model = prepare_model(art.new_model_from_image(img, Path(path).stem))
        doc = Doc(model)
        self.set_doc(doc, "cut")
        doc.select([model.meshes()[0].id])
        self.show_status("Выделите часть (глаз, бровь, рот…) и нажмите «Вырезать в новый слой»")

    def open_dialog(self):
        if not self.maybe_save():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Открыть", self._dir(),
                                              "Модели (*.mu *.psd *.inp *.png *.jpg *.jpeg);;Мю (*.mu)")
        if path:
            self.open_path(path)

    def open_path(self, path):
        path = str(path)
        low = path.lower()
        if low.endswith(".psd"):
            return self.open_psd(path)
        if low.endswith(".inp"):
            return self.import_inp(path)
        if low.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
            img = QImage(path)
            if img.isNull():
                return None
            doc = Doc(prepare_model(art.new_model_from_image(img, Path(path).stem)))
            self.set_doc(doc, "cut")
            return doc
        try:
            model = prepare_model(fileio.load(path))
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Не удалось открыть файл:\n{e}")
            return None
        self._remember(path)
        self.settings.add_recent(path)
        doc = Doc(model, path)
        self.set_doc(doc, "rig")
        return doc

    def save(self):
        if self.doc is None:
            return False
        if self.doc.path is None or self.doc.path.suffix.lower() != ".mu":
            return self.save_as()
        return self._save_to(self.doc.path)

    def save_as(self):
        if self.doc is None:
            return False
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить", str(Path(self._dir()) / f"{self.doc.title()}.mu"),
                                              "Мю (*.mu)")
        if not path:
            return False
        if not path.lower().endswith(".mu"):
            path += ".mu"
        return self._save_to(Path(path))

    def _save_to(self, path):
        try:
            fileio.save(self.doc.model, path)
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Не удалось сохранить:\n{e}")
            return False
        self.doc.path = Path(path)
        self.doc.model.name = Path(path).stem
        self.doc.mark_saved()
        self.dirty_extra = False
        self.settings.add_recent(str(path))
        self._remember(path)
        self.update_title()
        self.show_status(f"Сохранено: {path}")
        return True

    def maybe_save(self):
        if not self.is_dirty():
            return True
        r = QMessageBox.question(self, APP_NAME, f"Сохранить изменения в «{self.doc.title()}»?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Save:
            return self.save()
        return r == QMessageBox.Discard

    def import_layer(self):
        if self.doc is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Картинка как слой", self._dir(),
                                              "Изображения (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return
        img = QImage(path)
        if img.isNull():
            return
        m = self.doc.model
        x = (m.width - img.width()) / 2
        y = (m.height - img.height()) / 2
        mesh = art.add_layer(m, Path(path).stem, img, x, y)
        mesh.role = autorig.guess_role(mesh.name)[0] if autorig.guess_role(mesh.name)[0] not in (
            "eye", "iris", "eye_white", "eye_hl", "lash", "lower_lash", "brow", "arm", "forearm", "hand", "leg",
            "shin") else ""
        self.doc.commit()
        self.doc.select([mesh.id])

    def import_psd_layers(self):
        if self.doc is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Слои из PSD", self._dir(), "Photoshop (*.psd)")
        if not path:
            return
        from .psd import read_psd
        W, H, layers = read_psd(path)
        m = self.doc.model
        sx, sy = m.width / max(1, W), m.height / max(1, H)
        k = min(sx, sy)
        new = []
        for lay in layers:
            if lay.image.isNull():
                continue
            img = lay.image
            if abs(k - 1) > 1e-3:
                img = img.scaled(max(1, int(img.width() * k)), max(1, int(img.height() * k)), Qt.IgnoreAspectRatio,
                                 Qt.SmoothTransformation)
            mesh = art.add_layer(m, lay.name, img, lay.x * k, lay.y * k)
            mesh.visible = lay.visible
            new.append(mesh)
        autorig.guess_roles(m)
        self.doc.commit()
        self.doc.select([x.id for x in new])

    def import_inp(self, path=None):
        if not isinstance(path, str):
            if not self.maybe_save():
                return None
            path, _ = QFileDialog.getOpenFileName(self, "Модель Inochi2D", self._dir(), "Inochi2D (*.inp)")
            if not path:
                return None
        from .inochi import import_inp
        try:
            model = prepare_model(import_inp(path))
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Не удалось импортировать .inp:\n{e}")
            return None
        doc = Doc(model)
        self.set_doc(doc, "rig")
        return doc

    # ------------------------------------------------------------------ export
    def _need_doc(self):
        if self.doc is None:
            QMessageBox.information(self, APP_NAME, "Сначала откройте или создайте модель")
            return False
        return True

    def export_moc3(self):
        if not self._need_doc():
            return
        folder = QFileDialog.getExistingDirectory(self, "Папка для модели VTube Studio", self._dir())
        if not folder:
            return
        from .moc3 import _safe_id, export_moc3
        name = _safe_id(self.doc.title(), "Model", set())
        out = Path(folder) / name
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            path = export_moc3(self.doc.model, out, name)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, APP_NAME, f"Экспорт не удался:\n{e}")
            return
        QApplication.restoreOverrideCursor()
        QMessageBox.information(self, APP_NAME, f"Готово: {path}\n\nВ VTube Studio: настройки → «Импорт модели» и "
                                                f"выберите эту папку. Экспорт .moc3 экспериментальный — если модель "
                                                f"не откроется, используйте Inochi2D или PSD.")

    def export_inp(self):
        if not self._need_doc():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Inochi2D", str(Path(self._dir()) / f"{self.doc.title()}.inp"),
                                              "Inochi2D (*.inp)")
        if path:
            from .inochi import export_inp
            export_inp(self.doc.model, path)
            self.show_status(f"Сохранено: {path}")

    def export_psd(self):
        if not self._need_doc():
            return
        path, _ = QFileDialog.getSaveFileName(self, "PSD", str(Path(self._dir()) / f"{self.doc.title()}.psd"),
                                              "Photoshop (*.psd)")
        if path:
            from .psd import export_model_psd
            export_model_psd(self.doc.model, path)
            self.show_status(f"Сохранено: {path}")

    def export_pngtuber(self):
        if not self._need_doc():
            return
        folder = QFileDialog.getExistingDirectory(self, "Папка для PNGTuber", self._dir())
        if folder:
            files = export_pngtuber(self.doc.model, Path(folder) / f"{self.doc.title()} PNGTuber")
            self.show_status(f"Сохранено картинок: {len(files)}")

    def export_png(self):
        if not self._need_doc():
            return
        path, _ = QFileDialog.getSaveFileName(self, "PNG", str(Path(self._dir()) / f"{self.doc.title()}.png"),
                                              "PNG (*.png)")
        if path:
            self.doc.renderer.render_image(self.doc.frame(), 1.0).save(path)
            self.show_status(f"Сохранено: {path}")

    # ------------------------------------------------------------------ model commands
    def delete_selected(self):
        if self.doc is None or not self.doc.selection:
            return
        for nid in list(self.doc.selection):
            self.doc.model.remove(nid)
        self.doc.select([])
        self.doc.commit()

    def select_all(self):
        if self.doc is not None:
            self.doc.select([m.id for m in self.doc.model.meshes()])

    def run_autorig(self, confirm=True):
        if self.doc is None:
            return
        m = self.doc.model
        if confirm and (m.deformers() or any(x.bindings for x in m.meshes())):
            r = QMessageBox.question(self, APP_NAME, "Авто-риг заменит текущие деформеры, ключи и физику. "
                                                     "Продолжить? (Отменить можно через ⌘Z.)")
            if r != QMessageBox.Yes:
                return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            notes = autorig.autorig(m)
        finally:
            QApplication.restoreOverrideCursor()
        self.doc.active_param = "ParamAngleX"
        self.doc.commit()
        self.doc.activeParamChanged.emit()
        self.show_status("Авто-риг: " + "; ".join(notes))

    def guess_roles(self):
        if self.doc is not None:
            autorig.guess_roles(self.doc.model, overwrite=True)
            self.doc.commit()

    def strip_rig(self):
        if self.doc is not None:
            autorig.strip_rig(self.doc.model)
            self.doc.commit()

    def about(self):
        QMessageBox.about(self, APP_NAME, f"<h3>{LOGO} {APP_NAME} {__version__}</h3>"
                                          "<p>Оживление 2D-иллюстраций для витуберов: нарезка, сетки, риг, физика, "
                                          "студия, эфир.</p><p>Файлы .mu хранятся у вас. macOS 11+ (Intel).</p>")

    # ------------------------------------------------------------------ theme
    def _is_dark(self):
        mode = self.settings.get("theme", "system")
        if mode == "system":
            try:
                return self.app.styleHints().colorScheme() == Qt.ColorScheme.Dark
            except Exception:
                return self.app.palette().color(QPalette.Window).lightness() < 128
        return mode == "dark"

    def set_theme(self, mode):
        self.settings["theme"] = mode
        self.settings.save()
        QMessageBox.information(self, APP_NAME, "Тема применится полностью после перезапуска Мю.")
        self.colors.clear()
        self.colors.update(DARK if self._is_dark() else LIGHT)
        self.app.setStyleSheet(stylesheet(self.colors))
        for page in self.pages.values():
            page.update()

    def closeEvent(self, e):
        if not self.maybe_save():
            e.ignore()
            return
        if "live" in self.pages:
            self.pages["live"].shutdown()
        self.settings.save()
        e.accept()


def export_pngtuber(model, folder):
    """Idle / talking / blinking / talking+blinking pictures for PNGTuber apps (bust crop, transparent)."""
    from .render import Renderer
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    base = {p.id: p.default for p in model.params}
    states = [("1_молчит", {}), ("2_говорит", {"ParamMouthOpenY": 1.0}),
              ("3_моргает", {"ParamEyeLOpen": 0.0, "ParamEyeROpen": 0.0}),
              ("4_говорит_моргает", {"ParamMouthOpenY": 1.0, "ParamEyeLOpen": 0.0, "ParamEyeROpen": 0.0})]
    r = Renderer(model)
    files = []
    k = min(1.0, 1600 / max(model.width, model.height))
    for name, extra in states:
        vals = dict(base)
        vals.update({pid: v for pid, v in extra.items() if model.param(pid) is not None})
        img = r.render_image(model.evaluate(vals), k)
        out = folder / f"{name}.png"
        img.save(str(out))
        files.append(out)
    return files


class App(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.win = None
        self.pending = []

    def event(self, e):
        if e.type() == e.Type.FileOpen:  # Finder: open with / double-click a .mu file
            path = e.file()
            if self.win is not None:
                self.win.open_path(path)
            else:
                self.pending.append(path)
            return True
        return super().event(e)


def release_caches():
    """Drop module-level Qt objects before QApplication goes away (destroying them at interpreter shutdown
    crashes on macOS)."""
    icons.pixmap.cache_clear()


def main():
    app = App(sys.argv)
    app.aboutToQuit.connect(release_caches)
    app.setApplicationName("Mu")
    app.setApplicationDisplayName(APP_NAME)
    icon = resource_path("assets", "icon.png")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    win = MainWindow(app)
    app.win = win
    win.show()
    for arg in sys.argv[1:] + app.pending:
        if not arg.startswith("-") and Path(arg).exists():
            win.open_path(arg)
    code = app.exec()
    win.deleteLater()
    app.processEvents()
    release_caches()
    return code

