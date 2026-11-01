"""Entry point (PyInstaller / `python run.py`). `--selftest` runs headless checks for CI."""
import sys


def selftest():
    import os
    import tempfile
    from pathlib import Path

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # CI has no display
    from PySide6.QtCore import QPoint, QRect, Qt
    from PySide6.QtGui import QColor, QImageReader, QRegion
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])  # noqa: F841
    from zeta import ase, palettes
    from zeta.gif import save_gif
    from zeta.model import Document, Sprite, Tag
    from zeta.paths import Settings
    from zeta.tools import BucketTool, EllipseTool, LineTool, PencilTool, WandTool, ellipse_points, line_points

    class Win:  # the bits of MainWindow the tools use
        def __init__(self):
            self.settings = Settings()
            self.settings.update(brush_size=1, pixel_perfect=True, contiguous=True, tolerance=0, shape_fill=False)
            self.symmetry = [False, False]
            self.primary, self.secondary = QColor("#D97757"), QColor("#141413")
            self.last_point = None

        def colors_for(self, b):
            return self.secondary if b == Qt.RightButton else self.primary

        def status_message(self, *_):
            pass

        canvas_changed = document_changed = selection_changed = status_message

    win = Win()
    win.canvas = type("C", (), {"update": lambda self: None})()
    sp = Sprite(16, 16)
    doc = Document(sp)
    pen = PencilTool(win)
    pen.press(doc, QPoint(1, 1), Qt.LeftButton, Qt.NoModifier)
    for x in range(2, 8):
        pen.move(doc, QPoint(x, x // 2 + 1), Qt.LeftButton, Qt.NoModifier)
    pen.release(doc, QPoint(7, 4), Qt.LeftButton, Qt.NoModifier)
    img = doc.current_image()
    assert QColor.fromRgba(img.pixel(1, 1)) == win.primary and img.pixel(0, 0) == 0
    assert line_points((0, 0), (3, 1)) == [(0, 0), (1, 0), (2, 1), (3, 1)]
    assert len(ellipse_points((0, 0), (9, 9), True)) > 60
    LineTool(win).press(doc, QPoint(0, 15), Qt.RightButton, Qt.NoModifier)
    EllipseTool(win)
    # bucket fills the enclosed area only
    doc.push("x")
    blank_doc = Document(Sprite(8, 8))
    BucketTool(win).press(blank_doc, QPoint(3, 3), Qt.LeftButton, Qt.NoModifier)
    assert QColor.fromRgba(blank_doc.current_image().pixel(7, 7)) == win.primary
    WandTool(win).press(blank_doc, QPoint(0, 0), Qt.LeftButton, Qt.NoModifier)
    assert blank_doc.selection.boundingRect() == QRect(0, 0, 8, 8)
    # undo / redo
    before = doc.current_image()
    assert doc.undo() and doc.undo() and doc.redo()
    assert doc.redo() and doc.current_image() is not None and before is not None
    # frames / layers / tags
    sp.insert_frame(1, copy_from=0)
    sp.add_layer()
    sp.tags.append(Tag("walk", 0, 1, 2))
    assert sp.frames == 2 and len(sp.layers) == 2
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ase.save(sp, tmp / "t.aseprite")
        back = ase.load(tmp / "t.aseprite")
        assert back.frames == 2 and back.tags[0].name == "walk" and back.tags[0].direction == 2
        assert back.flat_frame(1) == sp.flat_frame(1)
        save_gif(tmp / "a.gif", [sp.flat_frame(f) for f in range(sp.frames)], sp.durations)
        r = QImageReader(str(tmp / "a.gif"))
        assert r.imageCount() == 2, r.imageCount()
        g = r.read()
        assert QColor.fromRgba(g.pixel(1, 1)).name() == win.primary.name(), QColor.fromRgba(g.pixel(1, 1)).name()
        assert g.pixelColor(0, 0).alpha() == 0
        palettes.save(tmp / "p.gpl", palettes.preset("PICO-8"))
        assert palettes.load(tmp / "p.gpl") == palettes.preset("PICO-8")
    sp.resize_canvas(20, 18, 2, 1)
    sp.rotate(90)
    assert (sp.width, sp.height) == (18, 20)
    doc.selection = QRegion(0, 0, 4, 4)
    assert doc.has_selection()
    from zeta.ui import MainWindow  # noqa: F401  (imports every UI module)
    print("selftest ok")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    from zeta.ui import main

    sys.exit(main())
