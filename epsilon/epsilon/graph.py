"""Static graph of notes and their [[links]] (force layout computed once, no animation)."""
import math
import random

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView


def layout(n, edges, iterations=150, seed=7):
    rnd = random.Random(seed)
    pos = [[rnd.uniform(-1, 1) * 300, rnd.uniform(-1, 1) * 300] for _ in range(n)]
    if n < 2:
        return pos
    k = 90.0
    temp = 60.0
    for _ in range(iterations):
        disp = [[0.0, 0.0] for _ in range(n)]
        for i in range(n):
            xi, yi = pos[i]
            for j in range(i + 1, n):
                dx, dy = xi - pos[j][0], yi - pos[j][1]
                d2 = dx * dx + dy * dy + 0.01
                f = k * k / d2
                disp[i][0] += dx * f
                disp[i][1] += dy * f
                disp[j][0] -= dx * f
                disp[j][1] -= dy * f
        for a, b in edges:
            dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
            d = math.sqrt(dx * dx + dy * dy) + 0.01
            f = d / k
            disp[a][0] -= dx * f
            disp[a][1] -= dy * f
            disp[b][0] += dx * f
            disp[b][1] += dy * f
        for i in range(n):  # gravity keeps islands close
            disp[i][0] -= pos[i][0] * 0.02
            disp[i][1] -= pos[i][1] * 0.02
            dx, dy = disp[i]
            d = math.sqrt(dx * dx + dy * dy) + 0.01
            pos[i][0] += dx / d * min(d, temp)
            pos[i][1] += dy / d * min(d, temp)
        temp = max(2.0, temp * 0.96)
    return pos


class GraphView(QGraphicsView):
    open_note = Signal(str)

    def __init__(self, colors):
        super().__init__()
        self.c = colors
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setScene(QGraphicsScene(self))
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def set_graph(self, notes, edges, current=None):
        scene = self.scene()
        scene.clear()
        self.setBackgroundBrush(QColor(self.c["bg"]))
        index = {str(p): i for i, p in enumerate(notes)}
        pairs = [(index[str(a)], index[str(b)]) for a, b in edges if str(a) in index and str(b) in index]
        pos = layout(len(notes), pairs)
        degree = [0] * len(notes)
        for a, b in pairs:
            degree[a] += 1
            degree[b] += 1
        pen = QPen(QColor(self.c["border"]), 1.2)
        for a, b in pairs:
            scene.addLine(pos[a][0], pos[a][1], pos[b][0], pos[b][1], pen)
        font = QFont()
        font.setPointSize(10)
        for i, p in enumerate(notes):
            r = 5 + min(10, degree[i] * 1.5)
            is_current = current is not None and str(p) == str(current)
            dot = QGraphicsEllipseItem(-r, -r, 2 * r, 2 * r)
            dot.setPos(QPointF(*pos[i]))
            dot.setBrush(QBrush(QColor(self.c["accent"] if is_current or degree[i] else self.c["muted"])))
            dot.setPen(QPen(Qt.NoPen))
            dot.setData(0, str(p))
            dot.setCursor(Qt.PointingHandCursor)
            dot.setToolTip(p.stem)
            scene.addItem(dot)
            label = QGraphicsSimpleTextItem(p.stem)
            label.setFont(font)
            label.setBrush(QBrush(QColor(self.c["text"] if is_current else self.c["muted"])))
            label.setPos(pos[i][0] - label.boundingRect().width() / 2, pos[i][1] + r + 2)
            label.setData(0, str(p))
            scene.addItem(label)
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-60, -60, 60, 60))
        self.resetTransform()
        rect = scene.sceneRect()
        if rect.width() and rect.height():
            fit = min(self.viewport().width() / rect.width(), self.viewport().height() / rect.height())
            k = max(0.3, min(1.6, fit))
            self.scale(k, k)

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        if item is not None and item.data(0):
            self.open_note.emit(item.data(0))
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
