"""Entry point (PyInstaller / `python run.py`). `--selftest` runs headless checks for CI."""
import sys


def selftest():
    import json
    import os
    import tempfile
    from pathlib import Path

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # CI has no display
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from lyambda import fileio, svgio, templates
    from lyambda.model import (Document, Node, arrange, make_instance, path_to_points, build_path, solid,
                               world_bounds)
    from lyambda.render import Renderer, render_image
    from lyambda.site import export_site

    # every template builds, lays out and renders
    for kind, items in templates.TEMPLATES.items():
        for key, _, f in items:
            doc = f()
            img = fileio.make_thumbnail(doc, size=200)
            assert not img.isNull() and img.width() > 0, (kind, key)
    # auto layout: hug, fill, gap, padding
    f = Node("frame", layout="row", gap=10, pad=[8, 8, 8, 8], w=300, h=60, hug_h=True)
    a, b = Node("rect", w=40, h=20), Node("rect", grow=True, h=30)
    f.add(a)
    f.add(b)
    arrange(f)
    assert (a.x, a.y) == (8, 8) and abs(b.x - 58) < 1e-6 and abs(b.w - 234) < 1e-6 and f.h == 46, (b.x, b.w, f.h)
    # components: instances follow the master, overrides survive
    doc = Document("design")
    page = doc.pages[0]
    comp = Node("component", w=120, h=40, layout="row", hug_w=True, hug_h=True, pad=[10, 20, 10, 20])
    label = Node("text", text="Кнопка", id="lbl")
    comp.add(label)
    page.add(comp)
    inst = make_instance(comp)
    page.add(inst)
    inst.overrides = {"lbl": {"text": "Готово"}}
    comp.fills = [solid("#D97757")]
    label.size = 20
    doc.relayout()
    t = inst.children[0]
    assert t.text == "Готово" and t.size == 20 and inst.w > 60
    # booleans / path conversion
    sq = Node("rect", w=100, h=100)
    from lyambda.model import world_shape
    res = world_shape(sq).subtracted(world_shape(Node("ellipse", x=50, y=50, w=100, h=100)))
    pts = path_to_points(res)
    assert pts and abs(build_path(pts).boundingRect().width() - 100) < 1
    # svg round trip
    svg = svgio.export_svg(doc, [comp, inst])
    g = svgio.import_svg(svg.encode("utf-8"), "test")
    assert g.children and "<svg" in svg
    arc = svgio.parse_path_d("M10 10 A 20 20 0 0 1 50 10 Z")
    assert abs(arc.boundingRect().width() - 40) < 1
    # board: connectors attach to their nodes
    bd = templates.board_flowchart()
    conns = [n for n in bd.pages[0].children if n.type == "connector"]
    assert conns and all(c._path is not None and c._path.length() > 10 for c in conns)
    # file round trip with an image
    from PySide6.QtGui import QColor, QImage
    img = QImage(8, 8, QImage.Format_ARGB32)
    img.fill(QColor("#D97757"))
    ref = doc.add_image(fileio.image_bytes(img))
    page.add(Node("rect", x=300, w=80, h=80, fills=[{"type": "image", "ref": ref, "mode": "fill", "opacity": 1}]))
    doc.relayout()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp).resolve()
        fileio.save(doc, tmp / "a.lambda")
        back = fileio.load(tmp / "a.lambda")
        assert back.snapshot() == doc.snapshot() and ref in back.images
        kind, thumb = fileio.read_meta(tmp / "a.lambda")
        assert kind == "design" and thumb is not None and not thumb.isNull()
        r = render_image(Renderer(back), back.pages[0].children, 1.0)
        assert r.pixelColor(r.width() - 40, 40).red() > 200
        for fmt in ("PNG", "JPG", "SVG", "PDF"):
            out = fileio.export_nodes(doc, [comp], tmp / f"c.{fmt.lower()}", fmt, 2)
            assert out.stat().st_size > 100, fmt
        # slides → PDF
        sd = templates.slides_pitch()
        fileio.export_pdf(sd, sd.pages[0].children, tmp / "deck.pdf")
        assert (tmp / "deck.pdf").read_bytes()[:4] == b"%PDF"
        # site → html / css with responsive rules
        site = templates.site_landing()
        index = export_site(site, tmp / "site")
        html = index.read_text("utf-8")
        css = (tmp / "site" / "style.css").read_text("utf-8")
        assert "<h1" in html and "display: flex" in css and "@media (max-width: 767px)" in css
        assert (tmp / "site" / "o-nas.html").exists() and 'href="o-nas.html"' in html
        site.site["breakpoint"] = 375
        site.relayout()
        root = site.site_root(site.pages[0])
        assert root.w == 375 and all(world_bounds(c).width() <= 375.5 for c in root.children)
    # the whole UI comes up for every kind of file
    from lyambda.ui import MainWindow
    win = MainWindow(app)
    win.resize(1280, 800)
    win.show()
    for kind in ("design", "board", "slides", "site"):
        ed = win.new_document(kind, templates.TEMPLATES[kind][1][0])
        app.processEvents()
        ed.select(list(ed.scope_children())[:2])
        ed.inspector.rebuild()
        ed.canvas.repaint()
        ed.copy()
        ed.paste()
        ed.undo()
        ed.redo()
        assert ed.hist_i >= 1
    for ed in win.editors:
        ed.saved_i = ed.hist_i  # nothing to ask about on close
    print("lambda selftest ok", json.dumps({"templates": sum(len(v) for v in templates.TEMPLATES.values())}))
    win.close()
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    from lyambda.ui import main

    sys.exit(main())
