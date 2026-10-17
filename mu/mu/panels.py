"""Side panels: parts tree, parameters (sliders + keys), inspector, physics groups and poses."""
import base64

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QFrame,
                               QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
                               QPushButton, QScrollArea, QSlider, QSpinBox, QToolButton, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from . import icons
from .autorig import ROLES, ROLE_TITLES
from .model import PARAM_GROUPS, ArtMesh, Param, PhysGroup, RotationDeformer, WarpDeformer, new_id
from .poses import apply_pose
from .render import BLEND_TITLES

KIND_ICON = {"mesh": "image", "warp": "warp", "rot": "rotate"}


def section(text):
    lab = QLabel(text.upper())
    lab.setObjectName("Section")
    return lab


def tool_button(name, tip, colors, slot=None, checkable=False, size=18):
    b = QToolButton()
    b.setIcon(icons.icon(name, colors["text"], colors["accent"]))
    b.setIconSize(QSize(size, size))
    b.setToolTip(tip)
    b.setCheckable(checkable)
    if slot is not None:
        b.clicked.connect(slot)
    return b


# ====================================================================== parts tree
class PartsTree(QWidget):
    def __init__(self, doc, colors, parent=None):
        super().__init__(parent)
        self.doc, self.c = doc, colors
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 4)
        lay.setSpacing(4)
        head = QHBoxLayout()
        head.addWidget(section("Части"))
        head.addStretch(1)
        self.b_up = tool_button("up", "Выше в порядке отрисовки", colors, lambda: self.shift_order(1))
        self.b_down = tool_button("down", "Ниже в порядке отрисовки", colors, lambda: self.shift_order(-1))
        head.addWidget(self.b_up)
        head.addWidget(self.b_down)
        lay.addLayout(head)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setIndentation(14)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.menu)
        self.tree.itemSelectionChanged.connect(self.on_select)
        self.tree.itemChanged.connect(self.on_changed)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.tree.dropEvent = self._drop
        lay.addWidget(self.tree, 1)
        self._building = False
        doc.modelChanged.connect(self.rebuild)
        doc.selectionChanged.connect(self.sync_selection)
        self.rebuild()

    def set_doc(self, doc):
        self.doc = doc
        doc.modelChanged.connect(self.rebuild)
        doc.selectionChanged.connect(self.sync_selection)
        self.rebuild()

    def rebuild(self):
        self._building = True
        open_state = {}
        for it in self._all_items():
            open_state[it.data(0, Qt.UserRole)] = it.isExpanded()
        self.tree.clear()
        m = self.doc.model
        items = {}

        def add(node, parent_item):
            it = QTreeWidgetItem([node.name or "—"])
            it.setData(0, Qt.UserRole, node.id)
            it.setIcon(0, icons.icon(KIND_ICON[node.kind], self.c["muted"], self.c["accent"]))
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable | Qt.ItemIsDragEnabled |
                        Qt.ItemIsDropEnabled)
            it.setCheckState(0, Qt.Checked if node.visible else Qt.Unchecked)
            tip = {"mesh": "Слой (арт-меш)", "warp": "Деформер-сетка", "rot": "Деформер вращения"}[node.kind]
            if isinstance(node, ArtMesh) and node.role:
                tip += " · роль: " + ROLE_TITLES.get(node.role, node.role)
            if node.bindings:
                tip += " · ключи: " + ", ".join(b.param for b in node.bindings if b.keys)
            it.setToolTip(0, tip)
            if node.bindings and any(b.keys for b in node.bindings):
                it.setForeground(0, QColor(self.c["text"]))
            if parent_item is None:
                self.tree.addTopLevelItem(it)
            else:
                parent_item.addChild(it)
            items[node.id] = it
            kids = m.children(node.id)
            # deformers first, then meshes front-to-back
            kids.sort(key=lambda n: (isinstance(n, ArtMesh), -(n.order if isinstance(n, ArtMesh) else 0)))
            for k in kids:
                add(k, it)
            it.setExpanded(open_state.get(node.id, not isinstance(node, ArtMesh) and m.depth(node) < 2))

        roots = [n for n in m.nodes.values() if not n.parent or n.parent not in m.nodes]
        roots.sort(key=lambda n: (isinstance(n, ArtMesh), -(n.order if isinstance(n, ArtMesh) else 0)))
        for n in roots:
            add(n, None)
        self._items = items
        self._building = False
        self.sync_selection()

    def _all_items(self):
        out = []

        def walk(it):
            out.append(it)
            for i in range(it.childCount()):
                walk(it.child(i))
        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))
        return out

    def sync_selection(self):
        self._building = True
        sel = set(self.doc.selection)
        for it in self._all_items():
            it.setSelected(it.data(0, Qt.UserRole) in sel)
        if self.doc.selection and self.doc.selection[0] in getattr(self, "_items", {}):
            self.tree.scrollToItem(self._items[self.doc.selection[0]])
        self._building = False

    def on_select(self):
        if self._building:
            return
        self.doc.select([it.data(0, Qt.UserRole) for it in self.tree.selectedItems()])

    def on_changed(self, it, col):
        if self._building:
            return
        node = self.doc.model.nodes.get(it.data(0, Qt.UserRole))
        if node is None:
            return
        vis = it.checkState(0) == Qt.Checked
        name = it.text(0)
        if vis != node.visible or name != node.name:
            node.visible = vis
            node.name = name
            self.doc.commit()

    def _drop(self, e):
        target = self.tree.itemAt(e.position().toPoint())
        moving = [it.data(0, Qt.UserRole) for it in self.tree.selectedItems()]
        m = self.doc.model
        new_parent = None
        if target is not None:
            tn = m.nodes.get(target.data(0, Qt.UserRole))
            if isinstance(tn, ArtMesh):
                new_parent = tn.parent
            else:
                new_parent = tn.id if tn else None
        self.reparent(moving, new_parent)
        e.ignore()

    def reparent(self, ids, new_parent):
        m = self.doc.model
        if new_parent and new_parent in ids:
            return
        # forbid cycles
        if new_parent:
            anc = {a.id for a in m.ancestors(m.nodes[new_parent])} | {new_parent}
            if any(i in anc for i in ids):
                return
        for i in ids:
            if i in m.nodes:
                m.nodes[i].parent = new_parent
        m.invalidate()
        self.doc.commit()

    def shift_order(self, d):
        meshes = sorted(self.doc.model.meshes(), key=lambda x: x.order)
        sel = [x for x in meshes if x.id in self.doc.selection]
        if not sel:
            return
        idx = [meshes.index(x) for x in sel]
        for i in (sorted(idx, reverse=True) if d > 0 else sorted(idx)):
            j = i + d
            if 0 <= j < len(meshes) and meshes[j] not in sel:
                meshes[i], meshes[j] = meshes[j], meshes[i]
        for k, x in enumerate(meshes):
            x.order = k * 10
        self.doc.commit()

    def menu(self, pos):
        m = self.doc.model
        menu = QMenu(self)
        par = QMenu("Переместить в…", menu)
        par.addAction("Корень", lambda: self.reparent(list(self.doc.selection), None))
        for d in m.deformers():
            par.addAction(("▦ " if isinstance(d, WarpDeformer) else "↻ ") + d.name,
                          lambda d=d: self.reparent(list(self.doc.selection), d.id))
        menu.addMenu(par)
        menu.addSeparator()
        menu.addAction("Переименовать", lambda: self.tree.editItem(self.tree.currentItem(), 0)
                       if self.tree.currentItem() else None)
        menu.addAction("Удалить", self.window().delete_selected if hasattr(self.window(), "delete_selected") else None)
        menu.exec(self.tree.mapToGlobal(pos))


# ====================================================================== parameter slider with key marks
class KeySlider(QSlider):
    def __init__(self, colors):
        super().__init__(Qt.Horizontal)
        self.c = colors
        self.setRange(0, 1000)
        self.keys = []  # positions 0…1

    def paintEvent(self, e):
        super().paintEvent(e)
        if not self.keys:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self.c["accent"]))
        w = self.width() - 12
        for t in self.keys:
            x = 6 + t * w
            p.save()
            p.translate(x, self.height() - 3)
            p.rotate(45)
            p.drawRect(-2.5, -2.5, 5, 5)
            p.restore()
        p.end()


class ParamRow(QWidget):
    def __init__(self, panel, param):
        super().__init__()
        self.panel, self.param = panel, param
        c = panel.c
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.setSpacing(0)
        top = QHBoxLayout()
        top.setSpacing(4)
        self.name = QLabel(param.name)
        self.name.setToolTip(param.id)
        top.addWidget(self.name, 1)
        self.val = QLabel()
        self.val.setObjectName("Muted")
        top.addWidget(self.val)
        self.key = QToolButton()
        self.key.setIconSize(QSize(13, 13))
        self.key.setToolTip("Ключ для выбранных объектов в этой точке параметра\nПКМ — удалить ключ")
        self.key.clicked.connect(lambda: panel.toggle_key(param.id))
        self.key.setContextMenuPolicy(Qt.CustomContextMenu)
        self.key.customContextMenuRequested.connect(lambda _: panel.remove_key(param.id))
        top.addWidget(self.key)
        lay.addLayout(top)
        self.slider = KeySlider(c)
        self.slider.valueChanged.connect(self.on_slider)
        self.slider.sliderPressed.connect(lambda: panel.set_active(param.id))
        lay.addWidget(self.slider)
        self._lock = False

    def to_pos(self, v):
        p = self.param
        return 0.0 if p.max == p.min else (v - p.min) / (p.max - p.min)

    def on_slider(self, i):
        if self._lock:
            return
        p = self.param
        v = p.min + (p.max - p.min) * i / 1000.0
        # snap to keys / default within 1.5 %
        for k in self.panel.snap_points(p.id) + [p.default]:
            if abs(self.to_pos(k) - i / 1000.0) < 0.015:
                v = k
        self.panel.set_value(p.id, v)

    def refresh(self, value, keys, has_key_here, active):
        self._lock = True
        self.slider.setValue(int(round(self.to_pos(value) * 1000)))
        self._lock = False
        self.slider.keys = [self.to_pos(k) for k in keys]
        self.slider.update()
        self.val.setText(f"{value:.2f}".rstrip("0").rstrip(".") if abs(value) < 100 else f"{value:.0f}")
        c = self.panel.c
        self.key.setIcon(icons.icon("key" if has_key_here else "key_off", c["muted"], c["accent"]))
        self.name.setStyleSheet(f"color: {c['accent']}; font-weight: 600;" if active else "")


class ParamPanel(QWidget):
    """Parameter sliders. Works on the document (editing, with keys) or on any values dict (studio / live)."""
    valuesEdited = Signal()

    def __init__(self, doc, colors, with_keys=True, parent=None):
        super().__init__(parent)
        self.doc, self.c, self.with_keys = doc, colors, with_keys
        self.values = None   # external values dict (studio instance); None → doc.model.values
        self.model = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 0)
        head = QHBoxLayout()
        head.setContentsMargins(8, 0, 8, 0)
        head.addWidget(section("Параметры"))
        head.addStretch(1)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Поиск")
        self.filter.setMaximumWidth(110)
        self.filter.textChanged.connect(self.rebuild)
        head.addWidget(self.filter)
        b = tool_button("reset", "Сбросить все параметры", colors, self.reset_all)
        head.addWidget(b)
        if with_keys:
            head.addWidget(tool_button("plus", "Новый параметр", colors, self.new_param))
        lay.addLayout(head)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        lay.addWidget(self.scroll, 1)
        self.rows = {}
        if doc is not None:
            self.connect_doc(doc)
        self.rebuild()

    def connect_doc(self, doc):
        self.doc = doc
        doc.modelChanged.connect(self.rebuild)
        doc.valuesChanged.connect(self.refresh)
        doc.selectionChanged.connect(self.refresh)
        doc.activeParamChanged.connect(self.refresh)

    def set_doc(self, doc):
        self.connect_doc(doc)
        self.rebuild()

    def bind_values(self, model, values):
        """Studio mode: sliders edit `values` of `model` (no keys)."""
        self.model, self.values = model, values
        self.rebuild()

    def cur_model(self):
        return self.model or (self.doc.model if self.doc else None)

    def cur_values(self):
        if self.values is not None:
            return self.values
        return self.doc.model.values

    def rebuild(self):
        body = QWidget()
        body.setObjectName("InspectorBody")
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 0, 0, 8)
        v.setSpacing(0)
        self.rows = {}
        m = self.cur_model()
        if m is None:
            self.scroll.setWidget(body)
            return
        flt = self.filter.text().strip().lower()
        groups = {}
        for p in m.params:
            if flt and flt not in p.name.lower() and flt not in p.id.lower():
                continue
            groups.setdefault(p.group if p.group in PARAM_GROUPS else "Прочее", []).append(p)
        for g in PARAM_GROUPS:
            if g not in groups:
                continue
            lab = QLabel(g)
            lab.setObjectName("Muted")
            lab.setStyleSheet("padding: 8px 8px 2px 8px; font-style: italic;")
            v.addWidget(lab)
            for p in groups[g]:
                row = ParamRow(self, p)
                if not self.with_keys or self.values is not None:
                    row.key.hide()
                row.setContextMenuPolicy(Qt.CustomContextMenu)
                row.customContextMenuRequested.connect(lambda pos, p=p, row=row: self.param_menu(p, row, pos))
                self.rows[p.id] = row
                v.addWidget(row)
        v.addStretch(1)
        self.scroll.setWidget(body)
        self.refresh()

    def snap_points(self, pid):
        if self.values is not None or self.doc is None:
            return []
        keys = set()
        for n in self.doc.nodes():
            b = n.binding(pid)
            if b:
                keys.update(b.keys)
        return sorted(keys)

    def refresh(self):
        m = self.cur_model()
        if m is None:
            return
        vals = self.cur_values()
        for pid, row in self.rows.items():
            p = m.param(pid)
            if p is None:
                continue
            v = vals.get(pid, p.default)
            keys = self.snap_points(pid)
            here = False
            if self.values is None and self.doc is not None:
                for n in self.doc.nodes():
                    b = n.binding(pid)
                    if b and b.key_index(v) is not None:
                        here = True
            row.refresh(v, keys, here, self.doc is not None and self.values is None and pid == self.doc.active_param)

    def set_active(self, pid):
        if self.values is None and self.doc is not None and self.doc.active_param != pid:
            self.doc.active_param = pid
            self.doc.activeParamChanged.emit()

    def set_value(self, pid, v):
        if self.values is not None:
            p = self.model.param(pid)
            self.values[pid] = p.clamp(v) if p else v
            self.refresh()
            self.valuesEdited.emit()
        else:
            self.doc.set_value(pid, v)
            self.valuesEdited.emit()

    def reset_all(self):
        m = self.cur_model()
        if m is None:
            return
        if self.values is not None:
            self.values.update({p.id: p.default for p in m.params})
            self.refresh()
            self.valuesEdited.emit()
        else:
            self.doc.set_values({p.id: p.default for p in m.params})

    def toggle_key(self, pid):
        doc = self.doc
        nodes = doc.nodes()
        if not nodes:
            self.window().statusBar().showMessage("Сначала выберите объекты, которым нужен ключ", 4000)
            return
        p = doc.model.param(pid)
        v = doc.model.values.get(pid, p.default)
        self.set_active(pid)
        for n in nodes:
            doc.model.ensure_key(n, pid, v)
        doc.commit()

    def remove_key(self, pid):
        doc = self.doc
        p = doc.model.param(pid)
        v = doc.model.values.get(pid, p.default)
        changed = False
        for n in doc.nodes():
            b = n.binding(pid)
            if b is None:
                continue
            i = b.key_index(v)
            if i is not None:
                b.remove_key(i)
                changed = True
            if not b.keys:
                n.bindings.remove(b)
        if changed:
            doc.commit()

    def param_menu(self, p, row, pos):
        if self.values is not None or not self.with_keys:
            return
        menu = QMenu(self)
        menu.addAction("Сделать активным", lambda: self.set_active(p.id))
        menu.addAction("Добавить ключи на краях и в нуле", lambda: self.add_three_keys(p))
        menu.addAction("Удалить все ключи выбранных объектов", lambda: self.clear_keys(p))
        menu.addSeparator()
        menu.addAction("Изменить диапазон…", lambda: self.edit_range(p))
        menu.addAction("Удалить параметр", lambda: self.delete_param(p))
        menu.exec(row.mapToGlobal(pos))

    def add_three_keys(self, p):
        for n in self.doc.nodes():
            for k in sorted({p.min, p.default, p.max}):
                self.doc.model.ensure_key(n, p.id, k)
        self.set_active(p.id)
        self.doc.commit()

    def clear_keys(self, p):
        for n in self.doc.nodes():
            b = n.binding(p.id)
            if b is not None:
                n.bindings.remove(b)
        self.doc.commit()

    def edit_range(self, p):
        text, ok = QInputDialog.getText(self, "Диапазон", f"{p.name}: минимум, по умолчанию, максимум",
                                        text=f"{p.min:g}, {p.default:g}, {p.max:g}")
        if not ok:
            return
        try:
            lo, de, hi = [float(x) for x in text.replace(";", ",").split(",")]
        except ValueError:
            return
        if lo < hi and lo <= de <= hi:
            p.min, p.default, p.max = lo, de, hi
            self.doc.model.set_value(p.id, self.doc.model.values.get(p.id, de))
            self.doc.commit()

    def delete_param(self, p):
        m = self.doc.model
        for n in m.nodes.values():
            n.bindings = [b for b in n.bindings if b.param != p.id]
        m.params = [q for q in m.params if q.id != p.id]
        m.values.pop(p.id, None)
        if self.doc.active_param == p.id:
            self.doc.active_param = m.params[0].id if m.params else None
        self.doc.commit()

    def new_param(self):
        name, ok = QInputDialog.getText(self, "Новый параметр", "Название (например «Ушки»):")
        if not ok or not name.strip():
            return
        m = self.doc.model
        pid = "Param" + "".join(ch for ch in new_id("") if ch.isalnum())
        m.add_param(Param(pid, name.strip(), -1, 1, 0, "Прочее"))
        self.doc.active_param = pid
        self.doc.commit()


# ====================================================================== inspector
class Inspector(QWidget):
    def __init__(self, doc, colors, parent=None):
        super().__init__(parent)
        self.doc, self.c = doc, colors
        self.setObjectName("Inspector")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        lay.addWidget(self.scroll)
        doc.selectionChanged.connect(self.rebuild)
        doc.modelChanged.connect(self.rebuild)
        self._lock = False
        self.rebuild()

    def set_doc(self, doc):
        self.doc = doc
        doc.selectionChanged.connect(self.rebuild)
        doc.modelChanged.connect(self.rebuild)
        self.rebuild()

    def rebuild(self):
        if self._lock:
            return
        body = QWidget()
        body.setObjectName("InspectorBody")
        v = QVBoxLayout(body)
        v.setContentsMargins(10, 8, 10, 10)
        nodes = self.doc.nodes()
        if not nodes:
            v.addWidget(section("Инспектор"))
            hint = QLabel("Выберите часть на холсте или в списке.\n\nСовет: Shift — добавить к выбору, "
                          "перетаскивание пустого места — выбрать точки сетки.")
            hint.setWordWrap(True)
            hint.setObjectName("Muted")
            v.addWidget(hint)
            v.addStretch(1)
            self.scroll.setWidget(body)
            return
        n = nodes[0]
        title = {"mesh": "Слой", "warp": "Деформер-сетка", "rot": "Деформер вращения"}[n.kind]
        v.addWidget(section(title + (f" · выбрано {len(nodes)}" if len(nodes) > 1 else "")))
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setSpacing(6)
        name = QLineEdit(n.name)
        name.editingFinished.connect(lambda: self.set_attr(n, "name", name.text()))
        form.addRow("Имя", name)
        if isinstance(n, ArtMesh):
            role = QComboBox()
            for rid, rt in ROLES:
                role.addItem(rt, rid)
            role.setCurrentIndex(max(0, role.findData(n.role)))
            role.currentIndexChanged.connect(lambda _: self.set_all("role", role.currentData()))
            role.setToolTip("Роль подсказывает авто-ригу, что это за часть")
            form.addRow("Роль", role)
            op = QSpinBox()
            op.setRange(0, 100)
            op.setSuffix(" %")
            op.setValue(int(round(n.opacity * 100)))
            op.editingFinished.connect(lambda: self.set_all("opacity", op.value() / 100))
            form.addRow("Непрозрачность", op)
            bl = QComboBox()
            for k, t in BLEND_TITLES:
                bl.addItem(t, k)
            bl.setCurrentIndex(max(0, bl.findData(n.blend)))
            bl.currentIndexChanged.connect(lambda _: self.set_all("blend", bl.currentData()))
            form.addRow("Наложение", bl)
            mk = QComboBox()
            mk.addItem("— нет —", "")
            for x in sorted(self.doc.model.meshes(), key=lambda q: -q.order):
                if x.id != n.id:
                    mk.addItem(x.name, x.id)
            mk.setCurrentIndex(max(0, mk.findData(n.masks[0] if n.masks else "")))
            mk.currentIndexChanged.connect(lambda _: self.set_all("masks", [mk.currentData()] if mk.currentData()
                                                                   else []))
            mk.setToolTip("Клиппинг-маска: слой виден только внутри выбранного (как радужка внутри белка)")
            form.addRow("Маска", mk)
            inv = QCheckBox("Инвертировать маску")
            inv.setChecked(n.invert_mask)
            inv.toggled.connect(lambda on: self.set_all("invert_mask", on))
            form.addRow("", inv)
            info = QLabel(f"{len(n.rest)} точек · {len(n.tris)} треугольников")
            info.setObjectName("Muted")
            form.addRow("Сетка", info)
        elif isinstance(n, WarpDeformer):
            rows = QSpinBox()
            rows.setRange(1, 12)
            rows.setValue(n.rows)
            cols = QSpinBox()
            cols.setRange(1, 12)
            cols.setValue(n.cols)
            hb = QHBoxLayout()
            hb.addWidget(cols)
            hb.addWidget(QLabel("×"))
            hb.addWidget(rows)
            form.addRow("Деления", hb)
            apply_ = QPushButton("Применить (сбросит ключи сетки)")
            apply_.clicked.connect(lambda: self.set_grid(n, rows.value(), cols.value()))
            form.addRow("", apply_)
        elif isinstance(n, RotationDeformer):
            ln = QSpinBox()
            ln.setRange(10, 4000)
            ln.setValue(int(n.length))
            ln.editingFinished.connect(lambda: self.set_attr(n, "length", float(ln.value())))
            form.addRow("Длина ручки", ln)
            ox = QDoubleSpinBox()
            oy = QDoubleSpinBox()
            for s, val in ((ox, n.origin[0]), (oy, n.origin[1])):
                s.setRange(-20000, 20000)
                s.setDecimals(1)
                s.setValue(val)
            ox.editingFinished.connect(lambda: self.set_attr(n, "origin", (ox.value(), n.origin[1])))
            oy.editingFinished.connect(lambda: self.set_attr(n, "origin", (n.origin[0], oy.value())))
            hb = QHBoxLayout()
            hb.addWidget(ox)
            hb.addWidget(oy)
            form.addRow("Центр", hb)
        par = QComboBox()
        par.addItem("— корень —", "")
        anc_block = {n.id} | {d.id for d in self.doc.model.deformers() if n in self.doc.model.ancestors(d) or False}
        for d in self.doc.model.deformers():
            if d.id in anc_block or n.id in {a.id for a in self.doc.model.ancestors(d)}:
                continue
            par.addItem(d.name, d.id)
        par.setCurrentIndex(max(0, par.findData(n.parent or "")))
        par.currentIndexChanged.connect(lambda _: self.set_parent(par.currentData() or None))
        form.addRow("Родитель", par)
        v.addLayout(form)
        # bindings summary
        v.addSpacing(8)
        v.addWidget(section("Ключи"))
        if not any(b.keys for b in n.bindings):
            lab = QLabel("Нет ключей. Выберите параметр справа и нажмите ◆, затем сдвиньте ползунок и "
                         "деформируйте часть.")
            lab.setWordWrap(True)
            lab.setObjectName("Muted")
            v.addWidget(lab)
        for b in n.bindings:
            p = self.doc.model.param(b.param)
            if p is None or not b.keys:
                continue
            row = QHBoxLayout()
            lab = QLabel(f"{p.name}: " + ", ".join(f"{k:g}" for k in b.keys))
            lab.setWordWrap(True)
            row.addWidget(lab, 1)
            go = QToolButton()
            go.setText("→")
            go.setToolTip("Сделать параметр активным")
            go.clicked.connect(lambda _=False, pid=p.id: self._activate(pid))
            row.addWidget(go)
            v.addLayout(row)
        v.addStretch(1)
        for cb in body.findChildren(QComboBox):
            cb.setMinimumContentsLength(6)
            cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.scroll.setWidget(body)

    def _activate(self, pid):
        self.doc.active_param = pid
        self.doc.activeParamChanged.emit()

    def set_attr(self, n, attr, value):
        if getattr(n, attr) == value:
            return
        setattr(n, attr, value)
        self._commit()

    def set_all(self, attr, value):
        for n in self.doc.nodes():
            if isinstance(n, ArtMesh):
                if attr == "masks" and value and value[0] == n.id:
                    continue
                setattr(n, attr, value)
        self._commit()

    def set_parent(self, pid):
        m = self.doc.model
        for n in self.doc.nodes():
            if pid == n.id or (pid and n.id in {a.id for a in m.ancestors(m.nodes[pid])}):
                continue
            n.parent = pid
        m.invalidate()
        self._commit()

    def set_grid(self, w, rows, cols):
        w.rows, w.cols = rows, cols
        for b in w.bindings:
            for f in b.forms:
                f["offsets"] = None
        self._commit()

    def _commit(self):
        self._lock = True
        try:
            self.doc.commit()
        finally:
            self._lock = False
        QTimer.singleShot(0, self.rebuild)


# ====================================================================== physics
class PhysicsPanel(QWidget):
    def __init__(self, doc, colors, parent=None):
        super().__init__(parent)
        self.doc, self.c = doc, colors
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        head = QHBoxLayout()
        head.addWidget(section("Группы физики"))
        head.addStretch(1)
        head.addWidget(tool_button("plus", "Новая группа", colors, self.add_group))
        head.addWidget(tool_button("trash", "Удалить группу", colors, self.del_group))
        lay.addLayout(head)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self.show_group)
        self.list.setMaximumHeight(120)
        lay.addWidget(self.list)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setObjectName("InspectorBody")
        outer = QVBoxLayout(body)
        outer.setContentsMargins(0, 0, 4, 0)
        self.form_host = QVBoxLayout()
        outer.addLayout(self.form_host)
        outer.addStretch(1)
        scroll.setWidget(body)
        lay.addWidget(scroll, 1)
        doc.modelChanged.connect(self.rebuild)
        self._lock = False
        self.rebuild()

    def set_doc(self, doc):
        self.doc = doc
        doc.modelChanged.connect(self.rebuild)
        self.rebuild()

    def rebuild(self):
        if self._lock:
            return
        row = max(0, self.list.currentRow())
        self.list.blockSignals(True)
        self.list.clear()
        for g in self.doc.model.physics:
            it = QListWidgetItem(("● " if g.enabled else "○ ") + g.name)
            self.list.addItem(it)
        if self.doc.model.physics:
            self.list.setCurrentRow(min(row, len(self.doc.model.physics) - 1))
        self.list.blockSignals(False)
        if self.doc.model.physics:
            self.show_group(self.list.currentRow())
        else:
            self.show_group(-1)

    def clear_form(self):
        while self.form_host.count():
            it = self.form_host.takeAt(0)
            w = it.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def show_group(self, i):
        self.clear_form()
        m = self.doc.model
        if not (0 <= i < len(m.physics)):
            lab = QLabel("Физика раскачивает волосы, юбку и украшения, когда голова и тело двигаются. "
                         "Авто-риг создаёт группы сам.")
            lab.setWordWrap(True)
            lab.setObjectName("Muted")
            self.form_host.addWidget(lab)
            return
        g = m.physics[i]
        box = QWidget()
        f = QFormLayout(box)
        f.setContentsMargins(0, 8, 0, 0)
        name = QLineEdit(g.name)
        name.editingFinished.connect(lambda: self.set(g, "name", name.text()))
        f.addRow("Имя", name)
        en = QCheckBox("Включена")
        en.setChecked(g.enabled)
        en.toggled.connect(lambda on: self.set(g, "enabled", on))
        f.addRow("", en)
        segs = QSpinBox()
        segs.setRange(1, 8)
        segs.setValue(g.segments)
        segs.setToolTip("Звенья маятника: у каждого свой выход — по волосам идёт волна с запаздыванием")
        segs.valueChanged.connect(lambda v: self.set_segments(g, v))
        f.addRow("Звеньев", segs)
        for attr, title, lo, hi, step in (("stiffness", "Жёсткость", 5, 200, 5), ("damping", "Затухание", 0.5, 30, 0.5),
                                          ("gravity", "Гравитация", 0, 2, 0.1), ("scale", "Размах", 0.1, 3, 0.1)):
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setSingleStep(step)
            s.setValue(getattr(g, attr))
            s.valueChanged.connect(lambda val, a=attr: self.set(g, a, val, quiet=True))
            s.editingFinished.connect(self.commit)
            f.addRow(title, s)
        self.form_host.addWidget(box)
        self.form_host.addWidget(section("Входы"))
        for k, inp in enumerate(g.inputs):
            row = QHBoxLayout()
            pc = QComboBox()
            for p in m.params:
                pc.addItem(p.name, p.id)
            pc.setCurrentIndex(max(0, pc.findData(inp.get("param"))))
            pc.currentIndexChanged.connect(lambda _, inp=inp, pc=pc: self.set_input(inp, "param", pc.currentData()))
            w = QDoubleSpinBox()
            w.setRange(-2, 2)
            w.setSingleStep(0.1)
            w.setValue(inp.get("weight", 1.0))
            w.valueChanged.connect(lambda val, inp=inp: self.set_input(inp, "weight", val))
            kd = QComboBox()
            kd.addItem("сдвиг", "x")
            kd.addItem("наклон", "angle")
            kd.setCurrentIndex(1 if inp.get("kind") == "angle" else 0)
            kd.currentIndexChanged.connect(lambda _, inp=inp, kd=kd: self.set_input(inp, "kind", kd.currentData()))
            rm = QToolButton()
            rm.setText("×")
            rm.clicked.connect(lambda _=False, k=k: self.del_input(g, k))
            row.addWidget(pc, 1)
            row.addWidget(w)
            row.addWidget(kd)
            row.addWidget(rm)
            holder = QWidget()
            holder.setLayout(row)
            self.form_host.addWidget(holder)
        add = QPushButton("+ вход")
        add.clicked.connect(lambda: self.add_input(g))
        self.form_host.addWidget(add)
        self.form_host.addWidget(section("Выходы (звено → параметр)"))
        for k, o in enumerate(g.out_list()):
            row = QHBoxLayout()
            pc = QComboBox()
            for p in m.params:
                pc.addItem(p.name, p.id)
            pc.setCurrentIndex(max(0, pc.findData(o.get("param"))))
            pc.currentIndexChanged.connect(lambda _, k=k, pc=pc: self.set_output(g, k, "param", pc.currentData()))
            vx = QSpinBox()
            vx.setRange(1, max(1, g.segments))
            vx.setValue(max(1, min(g.segments, int(o.get("vertex", g.segments)))))
            vx.setToolTip("Номер звена")
            vx.valueChanged.connect(lambda v, k=k: self.set_output(g, k, "vertex", v))
            kd = QComboBox()
            kd.addItem("угол", "angle")
            kd.addItem("сдвиг", "x")
            kd.setCurrentIndex(1 if o.get("kind") == "x" else 0)
            kd.currentIndexChanged.connect(lambda _, k=k, kd=kd: self.set_output(g, k, "kind", kd.currentData()))
            sc = QDoubleSpinBox()
            sc.setRange(-3, 3)
            sc.setSingleStep(0.1)
            sc.setValue(float(o.get("scale", 1.0)))
            sc.valueChanged.connect(lambda v, k=k: self.set_output(g, k, "scale", v))
            rm = QToolButton()
            rm.setText("×")
            rm.clicked.connect(lambda _=False, k=k: self.del_output(g, k))
            row.addWidget(pc, 1)
            row.addWidget(vx)
            row.addWidget(kd)
            row.addWidget(sc)
            row.addWidget(rm)
            holder = QWidget()
            holder.setLayout(row)
            self.form_host.addWidget(holder)
        addo = QPushButton("+ выход")
        addo.clicked.connect(lambda: self.add_output(g))
        self.form_host.addWidget(addo)
        self.chain = ChainView(self.doc, g, self.c)
        self.form_host.insertWidget(0, self.chain)
        for cb in self.findChildren(QComboBox):
            cb.setMinimumContentsLength(5)
            cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)

    def set(self, g, attr, value, quiet=False):
        setattr(g, attr, value)
        if not quiet:
            self.commit()

    def set_input(self, inp, key, value):
        inp[key] = value

    def _materialize(self, g):
        if not g.outputs:
            g.outputs = [dict(o) for o in g.out_list()]

    def set_segments(self, g, n):
        g.segments = n
        self._materialize(g)
        for o in g.outputs:
            o["vertex"] = min(int(o.get("vertex", n)), n)
        self.doc.physics.reset()
        self.commit()
        self.show_group(self.list.currentRow())

    def set_output(self, g, k, key, value):
        self._materialize(g)
        if 0 <= k < len(g.outputs):
            g.outputs[k][key] = value
            if key == "param" and k == 0:
                g.output = value

    def add_output(self, g):
        self._materialize(g)
        pid = g.outputs[-1]["param"] if g.outputs else (self.doc.model.params[0].id if self.doc.model.params else "")
        g.outputs.append({"param": pid, "vertex": g.segments, "kind": "angle", "scale": 1.0})
        self.commit()
        self.show_group(self.list.currentRow())

    def del_output(self, g, k):
        self._materialize(g)
        if 0 <= k < len(g.outputs):
            g.outputs.pop(k)
            if g.outputs:
                g.output = g.outputs[0]["param"]
        self.commit()
        self.show_group(self.list.currentRow())

    def add_input(self, g):
        g.inputs.append({"param": "ParamAngleX", "weight": 0.5, "kind": "x"})
        self.commit()

    def del_input(self, g, k):
        g.inputs.pop(k)
        self.commit()

    def commit(self):
        self._lock = True
        try:
            self.doc.commit()
        finally:
            self._lock = False
        row = self.list.currentRow()
        self.list.blockSignals(True)
        for i, g in enumerate(self.doc.model.physics):
            if i < self.list.count():
                self.list.item(i).setText(("● " if g.enabled else "○ ") + g.name)
        self.list.blockSignals(False)
        if self.sender() is not None and isinstance(self.sender(), (QPushButton, QToolButton)):
            self.show_group(row)

    def add_group(self):
        m = self.doc.model
        out = next((p.id for p in m.params if p.group == "Волосы"), m.params[0].id if m.params else "")
        m.physics.append(PhysGroup(name="Новая группа", inputs=[{"param": "ParamAngleX", "weight": 0.6, "kind": "x"},
                                                                {"param": "ParamAngleZ", "weight": 0.5,
                                                                 "kind": "angle"}], output=out))
        self.doc.commit()
        self.list.setCurrentRow(len(m.physics) - 1)

    def del_group(self):
        i = self.list.currentRow()
        if 0 <= i < len(self.doc.model.physics):
            self.doc.model.physics.pop(i)
            self.doc.commit()


class ChainView(QWidget):
    """Live drawing of a physics group's pendulum chain (like Cubism's physics window)."""

    def __init__(self, doc, group, colors, parent=None):
        super().__init__(parent)
        self.doc, self.g, self.c = doc, group, colors
        self.setMinimumHeight(170)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(33)

    def paintEvent(self, e):
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(self.c["card"]))
        p.setPen(QPen(QColor(self.c["border"]), 1))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 8, 8)
        n = max(1, int(self.g.segments))
        th = self.doc.physics.chain_points(self.g.id) or [0.0] * n
        L = (self.height() - 30) / n
        x, y = self.width() / 2, 14.0
        p.setPen(QPen(QColor(self.c["muted"]), 1, Qt.DashLine))
        p.drawLine(int(x), 8, int(x), self.height() - 8)
        pts = [(x, y)]
        for a in th[:n]:
            x += L * math.sin(a)
            y += L * math.cos(a)
            pts.append((x, y))
        p.setPen(QPen(QColor(self.c["accent"]), 2.4, Qt.SolidLine, Qt.RoundCap))
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            p.drawLine(int(x0), int(y0), int(x1), int(y1))
        p.setBrush(QColor(self.c["accent"]))
        p.setPen(Qt.NoPen)
        for i, (px, py) in enumerate(pts):
            r = 5 if i == 0 else 4
            p.drawEllipse(QRectF(px - r, py - r, 2 * r, 2 * r))
        p.setPen(QColor(self.c["muted"]))
        p.drawText(8, self.height() - 8, "Маятник — включите «Проверку»")
        p.end()


# ====================================================================== poses
def pose_thumb_bytes(img):
    from .fileio import png_bytes
    return base64.b64encode(png_bytes(img)).decode("ascii")


def pose_pixmap(pose, size=72):
    data = pose.get("thumb")
    if not data:
        return None
    img = QImage.fromData(QByteArray(base64.b64decode(data)))
    if img.isNull():
        return None
    return QPixmap.fromImage(img.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))


class PosesPanel(QWidget):
    """Ready-made poses / expressions plus the model's saved poses (with preview thumbnails)."""
    applied = Signal(dict)
    saveRequested = Signal()

    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.c = colors
        self.model = None
        self.thumb_fn = None      # (model, values) → QImage, for poses without a stored preview
        self._thumbs = {}
        self._queue = []
        self._timer = QTimer(self)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._next_thumb)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        head = QHBoxLayout()
        head.addWidget(section("Позы и эмоции"))
        head.addStretch(1)
        self.b_save = tool_button("save", "Сохранить текущую позу (с превью)", colors, self.saveRequested.emit)
        self.b_del = tool_button("trash", "Удалить позу", colors, self.delete)
        head.addWidget(self.b_save)
        head.addWidget(self.b_del)
        lay.addLayout(head)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(72, 72))
        self.list.setGridSize(QSize(92, 108))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setWordWrap(True)
        self.list.itemClicked.connect(self.on_click)
        lay.addWidget(self.list, 1)
        self.blend = QCheckBox("Плавный переход")
        self.blend.setChecked(True)
        lay.addWidget(self.blend)

    def set_model(self, model):
        self.model = model
        self.rebuild()

    def rebuild(self):
        self.list.clear()
        if self.model is None:
            return
        from .poses import add_default_poses
        add_default_poses(self.model)
        self._queue = []
        for i, pose in enumerate(self.model.poses):
            it = QListWidgetItem(pose["name"])
            pm = pose_pixmap(pose)
            if pm is None:
                pm = self._thumbs.get(self._key(pose))
            if pm is None:
                pm = icons.pixmap("pose" if pose.get("kind") != "Эмоция" else "auto", self.c["muted"],
                                  self.c["accent"], 72)
                if self.thumb_fn is not None:
                    self._queue.append((i, pose))
            it.setIcon(pm)
            it.setData(Qt.UserRole, i)
            it.setToolTip(pose.get("kind", "Поза"))
            self.list.addItem(it)
        if self._queue:
            self._timer.start()

    def _key(self, pose):
        return (id(self.model), pose.get("name"), tuple(sorted(pose.get("values", {}).items())))

    def _next_thumb(self):
        if not self._queue or self.model is None:
            self._timer.stop()
            return
        i, pose = self._queue.pop(0)
        vals = {p.id: p.default for p in self.model.params}
        vals.update({k: v for k, v in pose.get("values", {}).items() if self.model.param(k) is not None})
        if pose.get("kind") == "Эмоция":
            img = self.thumb_fn(self.model, vals, face=True)
        else:
            img = self.thumb_fn(self.model, vals)
        pm = QPixmap.fromImage(img)
        self._thumbs[self._key(pose)] = pm
        if i < self.list.count():
            self.list.item(i).setIcon(pm)

    def on_click(self, it):
        i = it.data(Qt.UserRole)
        if self.model is not None and 0 <= i < len(self.model.poses):
            self.applied.emit(dict(self.model.poses[i]))

    def delete(self):
        it = self.list.currentItem()
        if it is None or self.model is None:
            return
        i = it.data(Qt.UserRole)
        self.model.poses.pop(i)
        if not self.model.poses:
            self.model.poses.append({"name": "Стоит", "kind": "Поза", "values": {}})
        self.rebuild()


def apply_pose_values(model, values, pose, reset=True):
    """Apply a pose dict to a values dict (studio instances keep their own values)."""
    saved = model.values
    model.values = dict(values)
    try:
        apply_pose(model, pose.get("values", {}), reset=reset)
        return dict(model.values)
    finally:
        model.values = saved

