"""Left-side panels: pages, layers tree (rename, hide, lock, drag to reorder / regroup), components (assets),
slide thumbnails, website blocks."""
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMenu, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from . import icons
from . import templates as tpl
from .model import owning_instance, world_bounds
from .render import render_image

ID = Qt.UserRole


def flow_order(node):
    """Layers list order: auto layout children read top-to-bottom / left-to-right, others topmost first."""
    return list(node.children) if node.auto else list(reversed(node.children))


def header(title, editor, plus=None, tip="", menu=None):
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(12, 8, 8, 2)
    lbl = QLabel(title.upper())
    lbl.setObjectName("Section")
    h.addWidget(lbl)
    h.addStretch(1)
    if plus is not None or menu is not None:
        b = QToolButton()
        b.setIcon(icons.icon("plus", editor.theme["text"], editor.theme["accent"]))
        b.setIconSize(QSize(14, 14))
        b.setToolTip(tip)
        if menu is not None:
            b.setMenu(menu)
            b.setPopupMode(QToolButton.InstantPopup)
            b.setStyleSheet("QToolButton::menu-indicator { image: none; }")
        else:
            b.clicked.connect(plus)
        h.addWidget(b)
    return w


def node_thumb(renderer, node, size):
    try:
        b = world_bounds(node)
        scale = min(size.width() / max(1.0, b.width()), size.height() / max(1.0, b.height()))
        img = render_image(renderer, [node], scale)
        pix = QPixmap(size)
        pix.fill(Qt.transparent)
        from PySide6.QtGui import QPainter
        p = QPainter(pix)
        p.drawImage((size.width() - img.width()) // 2, (size.height() - img.height()) // 2, img)
        p.end()
        return pix
    except Exception:
        pix = QPixmap(size)
        pix.fill(QColor("#E3DFD3"))
        return pix


# ====================================================================== pages
class PagesPanel(QWidget):
    def __init__(self, editor, title="Страницы"):
        super().__init__()
        self.ed = editor
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(header(title, editor, editor.add_page, "Новая страница"))
        self.list = QListWidget()
        self.list.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.list.itemClicked.connect(self._clicked)
        self.list.itemChanged.connect(self._renamed)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.model().rowsMoved.connect(self._moved)
        lay.addWidget(self.list)
        self._sync = False

    def refresh(self):
        self._sync = True
        self.list.clear()
        for p in self.ed.doc.pages:
            it = QListWidgetItem(p.name)
            it.setData(ID, p.id)
            it.setFlags(it.flags() | Qt.ItemIsEditable)
            self.list.addItem(it)
            if p is self.ed.page:
                it.setSelected(True)
                self.list.setCurrentItem(it)
        rows = max(1, min(6, len(self.ed.doc.pages)))
        self.list.setFixedHeight(rows * 28 + 6)
        self._sync = False

    def _page(self, it):
        pid = it.data(ID)
        return next((p for p in self.ed.doc.pages if p.id == pid), None)

    def _clicked(self, it):
        p = self._page(it)
        if p is not None and p is not self.ed.page:
            self.ed.set_page(p)

    def _renamed(self, it):
        if self._sync:
            return
        p = self._page(it)
        if p is not None and it.text().strip() and it.text() != p.name:
            self.ed.rename_page(p, it.text().strip())

    def _moved(self, *a):
        order = [self.list.item(i).data(ID) for i in range(self.list.count())]
        pages = {p.id: p for p in self.ed.doc.pages}
        self.ed.doc.pages = [pages[i] for i in order if i in pages]
        QTimer.singleShot(0, lambda: self.ed.commit("Порядок страниц"))

    def _menu(self, pos):
        it = self.list.itemAt(pos)
        if it is None:
            return
        p = self._page(it)
        m = QMenu(self)
        m.addAction("Переименовать", lambda: self.list.editItem(it))
        m.addAction("Дублировать", lambda: self.ed.duplicate_page(p))
        a = m.addAction("Удалить", lambda: self.ed.delete_page(p))
        a.setEnabled(len(self.ed.doc.pages) > 1)
        m.exec(self.list.mapToGlobal(pos))


# ====================================================================== layers
class LayerTree(QTreeWidget):
    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.setHeaderHidden(True)
        self.setColumnCount(2)
        self.setIndentation(14)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.setIconSize(QSize(14, 14))
        self.setUniformRowHeights(True)

    def dropEvent(self, e):
        super().dropEvent(e)
        QTimer.singleShot(0, self.panel.sync_from_tree)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.setColumnWidth(0, max(80, self.viewport().width() - 44))
        self.setColumnWidth(1, 40)


class LayersPanel(QWidget):
    def __init__(self, editor, title="Слои"):
        super().__init__()
        self.ed = editor
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(header(title, editor))
        self.tree = LayerTree(self)
        self.tree.itemSelectionChanged.connect(self._selected)
        self.tree.itemChanged.connect(self._renamed)
        self.tree.itemClicked.connect(self._clicked)
        self.tree.itemExpanded.connect(lambda it: self.expanded.add(it.data(0, ID)))
        self.tree.itemCollapsed.connect(lambda it: self.expanded.discard(it.data(0, ID)))
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        lay.addWidget(self.tree, 1)
        self.expanded = set()
        self.items = {}
        self._sync = False

    def refresh(self):
        self._sync = True
        th = self.ed.theme
        self.tree.clear()
        self.items = {}
        root = self.ed.layers_root()
        muted = QColor(th["faint"])

        def add(parent_item, node):
            it = QTreeWidgetItem([node.name or "—", ""])
            it.setData(0, ID, node.id)
            kind = "component" if node.type == "component" else icons.NODE_ICONS.get(node.type, "rect")
            if node.type == "frame" and node.auto:
                kind = "row" if node.layout == "row" else "column"
            it.setIcon(0, icons.icon(kind, th["muted"] if node.type != "component" else th["accent"], th["accent"],
                                     28))
            flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable
            inst = owning_instance(node)
            if inst is None:
                flags |= Qt.ItemIsDragEnabled
                if node.type in ("frame", "component", "group", "section"):
                    flags |= Qt.ItemIsDropEnabled
            it.setFlags(flags)
            if not node.visible or node.locked:
                it.setForeground(0, muted)
            badge = ("🔒" if node.locked else "") + ("" if node.visible else "◌")
            it.setText(1, badge)
            it.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
            if node.type in ("component", "instance"):
                f = it.font(0)
                f.setItalic(node.type == "instance")
                it.setFont(0, f)
            if parent_item is None:
                self.tree.addTopLevelItem(it)
            else:
                parent_item.addChild(it)
            self.items[node.id] = it
            for c in flow_order(node):
                add(it, c)
            if node.id in self.expanded:
                it.setExpanded(True)
        if root is not None:
            for c in flow_order(root):
                add(None, c)
        self.tree.invisibleRootItem().setFlags(Qt.ItemIsEnabled | Qt.ItemIsDropEnabled)
        self._sync = False
        self.show_selection()

    def show_selection(self):
        self._sync = True
        self.tree.clearSelection()
        last = None
        for n in self.ed.selection:
            it = self.items.get(n.id)
            if it is not None:
                p = it.parent()
                while p is not None:
                    p.setExpanded(True)
                    self.expanded.add(p.data(0, ID))
                    p = p.parent()
                it.setSelected(True)
                last = it
        if last is not None:
            self.tree.scrollToItem(last)
        self._sync = False

    def _selected(self):
        if self._sync:
            return
        nodes = [self.ed.doc.find(it.data(0, ID)) for it in self.tree.selectedItems()]
        self.ed.select([n for n in nodes if n is not None], source=self)

    def _renamed(self, it, col):
        if self._sync or col != 0:
            return
        n = self.ed.doc.find(it.data(0, ID))
        if n is not None and it.text(0).strip() and it.text(0) != n.name:
            self.ed.set_attr([n], "name", it.text(0).strip())

    def _clicked(self, it, col):
        if col != 1:
            return
        n = self.ed.doc.find(it.data(0, ID))
        if n is not None:
            self.ed.set_attr([n], "visible", not n.visible)

    def _menu(self, pos):
        it = self.tree.itemAt(pos)
        if it is None:
            return
        n = self.ed.doc.find(it.data(0, ID))
        if n is None:
            return
        if n not in self.ed.selection:
            self.ed.select([n])
        self.ed.context_menu(self.tree.viewport().mapToGlobal(pos), None)

    def sync_from_tree(self):
        doc = self.ed.doc
        root = self.ed.layers_root()

        def order(container, parent_item):
            count = parent_item.childCount() if parent_item is not None else self.tree.topLevelItemCount()
            items = [(parent_item.child(i) if parent_item is not None else self.tree.topLevelItem(i))
                     for i in range(count)]
            nodes = [doc.find(it.data(0, ID)) for it in items]
            nodes = [n for n in nodes if n is not None]
            for n in nodes:
                if n.parent is not container:
                    self.ed.reparent_keep_world(n, container)
            listed = {n.id for n in nodes}
            rest = [c for c in container.children if c.id not in listed]
            container.children = rest + (list(nodes) if container.auto else list(reversed(nodes)))
            for c in container.children:
                c.parent = container
            for it, n in zip(items, nodes):
                if it.childCount() or n.container:
                    order(n, it)
        order(root, None)
        doc.invalidate()
        self.ed.commit("Порядок слоёв")


# ====================================================================== components
class AssetsPanel(QWidget):
    def __init__(self, editor):
        super().__init__()
        self.ed = editor
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(header("Компоненты", editor))
        self.search = QLineEdit()
        self.search.setObjectName("Field")
        self.search.setPlaceholderText("Поиск компонентов")
        self.search.textChanged.connect(self.refresh)
        box = QHBoxLayout()
        box.setContentsMargins(10, 0, 10, 0)
        box.addWidget(self.search)
        lay.addLayout(box)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(96, 72))
        self.list.setGridSize(QSize(108, 100))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setWordWrap(True)
        self.list.itemDoubleClicked.connect(self._insert)
        lay.addWidget(self.list, 1)
        self.hint = QLabel("Выделите объекты и нажмите ⌥⌘K, чтобы создать компонент. Двойной щелчок — вставить экземпляр.")
        self.hint.setWordWrap(True)
        self.hint.setObjectName("Muted")
        self.hint.setContentsMargins(12, 6, 12, 12)
        lay.addWidget(self.hint)

    def refresh(self):
        self.list.clear()
        q = self.search.text().strip().lower()
        for c in self.ed.doc.components():
            if q and q not in c.name.lower():
                continue
            it = QListWidgetItem(QIcon(node_thumb(self.ed.renderer, c, QSize(96, 72))), c.name)
            it.setData(ID, c.id)
            it.setToolTip(f"{c.name} — страница «{c.page().name}»")
            self.list.addItem(it)

    def _insert(self, it):
        c = self.ed.doc.find(it.data(ID))
        if c is not None:
            self.ed.create_instance(c, at_view_center=True)


# ====================================================================== slides
class SlidesPanel(QWidget):
    THUMB = QSize(176, 99)

    def __init__(self, editor):
        super().__init__()
        self.ed = editor
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        menu = QMenu(self)
        for key, title in tpl.LAYOUTS:
            menu.addAction(title, lambda k=key: editor.add_slide(k))
        lay.addWidget(header("Слайды", editor, tip="Новый слайд", menu=menu))
        self.list = QListWidget()
        self.list.setIconSize(self.THUMB)
        self.list.setSpacing(6)
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.model().rowsMoved.connect(self._moved)
        self.list.itemClicked.connect(self._clicked)
        self.list.currentRowChanged.connect(self._row)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        lay.addWidget(self.list, 1)
        self._sync = False

    def refresh(self):
        self._sync = True
        self.list.clear()
        cur = self.ed.current_slide()
        for i, s in enumerate(self.ed.slides()):
            pix = node_thumb(self.ed.renderer, s, self.THUMB)
            ic = QIcon(pix)
            ic.addPixmap(pix, QIcon.Selected)
            it = QListWidgetItem(ic, f"{i + 1}" + ("" if s.visible else "  (скрыт)"))
            it.setData(ID, s.id)
            self.list.addItem(it)
            if s is cur:
                self.list.setCurrentItem(it)
        self._sync = False

    def _clicked(self, it):
        self._row(self.list.row(it))

    def _row(self, row):
        if self._sync or row < 0:
            return
        slides = self.ed.slides()
        if row < len(slides) and slides[row] is not self.ed.current_slide():
            self.ed.set_slide(slides[row])

    def _moved(self, *a):
        order = [self.list.item(i).data(ID) for i in range(self.list.count())]
        page = self.ed.page
        by_id = {c.id: c for c in page.children}
        page.children = [by_id[i] for i in order if i in by_id] + [c for c in page.children if c.id not in order]
        QTimer.singleShot(0, lambda: self.ed.commit("Порядок слайдов"))

    def _menu(self, pos):
        it = self.list.itemAt(pos)
        m = QMenu(self)
        sub = m.addMenu("Новый слайд")
        for key, title in tpl.LAYOUTS:
            sub.addAction(title, lambda k=key: self.ed.add_slide(k))
        if it is not None:
            s = self.ed.doc.find(it.data(ID))
            m.addAction("Дублировать", lambda: self.ed.duplicate_slide(s))
            m.addAction("Показать" if not s.visible else "Скрыть при показе",
                        lambda: self.ed.set_attr([s], "visible", not s.visible))
            a = m.addAction("Удалить", lambda: self.ed.delete_slide(s))
            a.setEnabled(len(self.ed.slides()) > 1)
        m.exec(self.list.mapToGlobal(pos))


# ====================================================================== site blocks
class BlocksPanel(QWidget):
    def __init__(self, editor):
        super().__init__()
        self.ed = editor
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(header("Блоки", editor))
        hint = QLabel("Щелчок — добавить блок после выделенной секции (или в конец страницы).")
        hint.setWordWrap(True)
        hint.setObjectName("Muted")
        hint.setContentsMargins(12, 0, 12, 6)
        lay.addWidget(hint)
        self.list = QListWidget()
        self.list.setIconSize(QSize(200, 110))
        self.list.setSpacing(6)
        self.list.itemClicked.connect(lambda it: editor.insert_block(it.data(ID)))
        lay.addWidget(self.list, 1)
        self._built = False

    def refresh(self):
        if self._built:
            return
        self._built = True
        from .model import Document, Node, arrange
        tmp = Document("site")
        for key, title, f in tpl.BLOCKS:
            block = f()
            holder = Node("frame", layout="column", w=1440, hug_h=True, role="webpage")
            holder.add(block)
            tmp.pages[0].add(holder)
            arrange(holder, w=1440)
            it = QListWidgetItem(QIcon(node_thumb(self.ed.renderer, holder, QSize(200, 110))), title)
            it.setData(ID, key)
            self.list.addItem(it)
            holder.remove()
