"""Entry point (PyInstaller / `python run.py`). `--selftest` runs headless checks for CI."""
import sys


def selftest():
    import os
    import tempfile
    from pathlib import Path

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # CI has no display
    from PySide6.QtCore import QPointF, QRect, QRectF, Qt
    from PySide6.QtGui import QColor, QImageReader, QPainterPath
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])  # noqa: F841
    import numpy as np

    from delta import fileio, imgops
    from delta.brushes import PRESETS, Brush, Stroke
    from delta.model import Document, Layer, blank

    doc = Document(320, 240, "#FFFFFF")
    layer = doc.current
    # a pressure stroke with the G-pen
    pen = Brush.from_dict(PRESETS[1].to_dict())
    s = Stroke(pen, layer, QColor("#141413"))
    for i in range(40):
        s.add(QPointF(20 + i * 5, 100 + (i % 7)), 0.2 + i / 50)
    layer.image = s.finish(QPointF(220, 104), 1.0)
    a = imgops.to_array(layer.image)
    assert a[..., 3].sum() > 0 and a[100, 60, 3] > 0, "stroke not painted"
    # eraser removes it
    er = Brush.from_dict(next(b for b in PRESETS if b.mode == "erase").to_dict())
    s = Stroke(er, layer, QColor("#000000"))
    s.add(QPointF(60, 100), 1.0)
    layer.image = s.finish(QPointF(60, 104), 1.0)
    assert imgops.to_array(layer.image)[102, 60, 3] < 40
    # fill + flood region inside a closed rectangle
    m = np.zeros((50, 50), bool)
    m[10:40, 10:40] = True
    assert imgops.flood_region(m, 20, 20).sum() == 900
    # adjustments / tone
    a = imgops.to_array(blank(40, 30, "#D97757"))
    assert imgops.grayscale(a)[0, 0, 0] == imgops.grayscale(a)[0, 0, 2]
    assert imgops.hue_saturation(a, 180, 0, 0)[0, 0, 0] > a[0, 0, 0]  # orange → blue-ish
    assert imgops.gaussian_blur(a, 3).shape == a.shape
    clip = QPainterPath()
    clip.addRect(QRectF(0, 0, 100, 100))
    toned = imgops.to_array(imgops.tone_fill(blank(120, 120), clip, 8, 50, 45, QColor("#000000")))
    cover = toned[:100, :100, 3].mean() / 255
    assert 0.35 < cover < 0.65 and toned[110, 110, 3] == 0, cover
    # keyframes
    top = doc.add_layer("Анимация")
    top.image = blank(320, 240, "#2E5E9E")
    top.set_key("x", 0, 0)
    top.set_key("x", 10, 100, "linear")
    assert abs(top.value("x", 5) - 50) < 1e-6 and top.value("x", 20) == 100
    top.set_key("opacity", 0, 100)
    top.set_key("opacity", 10, 0)
    assert doc.render(0).pixelColor(160, 120).name() == "#2e5e9e"
    assert doc.render(10).pixelColor(160, 120).alpha() == 255
    # clipping mask
    base = doc.add_layer("База")
    base.image = blank(320, 240)
    from PySide6.QtGui import QPainter

    p = QPainter(base.image)
    p.fillRect(QRect(0, 0, 50, 50), QColor("#FFFFFF"))
    p.end()
    clipl = doc.add_layer("Тень")
    clipl.image = blank(320, 240, "#FF0000")
    clipl.clip = True
    out = doc.render(10)
    assert out.pixelColor(10, 10).name() == "#ff0000" and out.pixelColor(200, 200).name() != "#ff0000"
    # undo / redo
    doc.push("x")
    clipl.name = "changed"
    doc.undo()
    assert doc.layers[-1].name == "Тень"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        fileio.save_delta(doc, tmp / "a.delta")
        back = fileio.load_delta(tmp / "a.delta")
        assert [l.name for l in back.layers] == [l.name for l in doc.layers] and back.layers[-1].clip
        assert back.layers[1].keys["x"][1].value == 100
        assert back.render(5) == doc.render(5)
        fileio.save_ora(doc, tmp / "a.ora")
        ora = fileio.load_ora(tmp / "a.ora")
        assert len(ora.layers) == len(doc.layers)
        fileio.save_psd(doc, tmp / "a.psd")
        data = (tmp / "a.psd").read_bytes()
        assert data[:4] == b"8BPS" and len(data) > 320 * 240 * 4 * len(doc.layers)
        doc.length = 3
        assert fileio.save_gif(doc, tmp / "a.gif")
        r = QImageReader(str(tmp / "a.gif"))
        assert r.imageCount() == 3, r.imageCount()
        fileio.save_flat(doc, tmp / "a.jpg")
        assert (tmp / "a.jpg").stat().st_size > 0
    from delta.ui import MainWindow  # noqa: F401  (imports every UI module)
    del Layer, Qt
    print("selftest ok")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    from delta.ui import main

    sys.exit(main())
