"""Entry point (PyInstaller / `python run.py`). `--selftest` runs headless checks for CI."""
import sys


def selftest():
    import json
    import os
    import struct
    import tempfile
    from pathlib import Path

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # CI has no display
    import numpy as np
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from mu import art, autorig, fileio, generator, inochi, moc3, psd
    from mu.doc import Doc
    from mu.poses import apply_pose, preset_values
    from mu.render import Renderer

    report = {}
    # a test character drawn in layers (only used here, never shown in the app)
    model = generator.build()
    autorig.guess_roles(model, overwrite=True)
    roles = {m.role for m in model.meshes()}
    assert {"face", "eye_white_l", "iris_r", "lash_l", "brow_r", "mouth", "mouth_in", "bangs", "back_hair",
            "arm_l", "forearm_r", "hand_l"} <= roles, roles
    autorig.strip_rig(model)
    assert not model.deformers()
    notes = autorig.autorig(model)
    assert model.deformers() and model.physics and len(notes) >= 3, notes
    rest = model.evaluate({p.id: p.default for p in model.params})
    eye = next(m for m in model.meshes() if m.role == "eye_white_l")
    closed = model.evaluate(dict({p.id: p.default for p in model.params}, ParamEyeLOpen=0.0))
    assert closed.meshes[eye.id][1] < 0.05 and rest.meshes[eye.id][1] > 0.9
    turned = model.evaluate(dict({p.id: p.default for p in model.params}, ParamAngleX=30.0))
    face = next(m for m in model.meshes() if m.role == "face")
    assert np.abs(turned.meshes[face.id][0] - rest.meshes[face.id][0]).max() > 5
    apply_pose(model, preset_values("Привет!"))
    hand = next(m for m in model.meshes() if m.role == "hand_r")
    wave = model.evaluate()
    assert wave.meshes[hand.id][0][:, 1].mean() < rest.meshes[hand.id][0][:, 1].mean() - 200  # the hand is raised
    report["autorig"] = len(model.deformers())

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp).resolve()
        # .mu round trip
        fileio.save(model, tmp / "a.mu")
        back = fileio.load(tmp / "a.mu")
        assert len(back.meshes()) == len(model.meshes()) and len(back.deformers()) == len(model.deformers())
        f1 = back.evaluate(dict(model.values))
        f0 = model.evaluate()
        assert max(np.abs(f1.meshes[k][0] - f0.meshes[k][0]).max() for k in f0.meshes) < 0.01
        assert fileio.read_thumb(tmp / "a.mu") is not None
        # PSD out → new model from PSD → roles + autorig
        model.reset_values()
        psd.export_model_psd(model, tmp / "a.psd")
        W, H, layers = psd.read_psd(tmp / "a.psd")
        assert (W, H) == (model.width, model.height) and len(layers) == len(model.meshes())
        pm = art.new_model_from_psd(tmp / "a.psd")
        assert sum(1 for m in pm.meshes() if m.role) >= len(pm.meshes()) - 3
        autorig.autorig(pm)
        assert pm.deformers()
        report["psd_layers"] = len(layers)
        # one picture → cut parts out of it
        flat = Renderer(model).render_image(model.evaluate(), 0.5)
        im = art.new_model_from_image(flat, "flat")
        src = im.meshes()[0]
        img = im.textures[src.texture]
        path = __import__("PySide6.QtGui", fromlist=["QPainterPath"]).QPainterPath()
        ex, ey = eye.rest.mean(0) * 0.5
        path.addEllipse(QPointF(ex, ey), 40, 30)
        mask = art.canvas_path_to_mask(src, img, path)
        assert mask.sum() > 1000
        new = art.cut_to_layer(im, src, mask, "Глаз", fill_hole=True, role="eye_l")
        assert new is not None and len(im.meshes()) == 2 and new.order > src.order
        hole = art.to_rgba(im.textures[src.texture])
        assert hole[int(ey), int(ex), 3] > 200  # the hole was filled
        wand = art.magic_wand(img, (5, 5), 10)
        assert wand[0, 0] and not wand[int(ey), int(ex)]
        f = im.evaluate()
        r = Renderer(im).render_image(f, 1.0)
        a = r.pixelColor(int(ex), int(ey))
        b = flat.pixelColor(int(ex), int(ey))
        assert abs(a.red() - b.red()) < 40 and a.alpha() > 200, (a.getRgb(), b.getRgb())
        # Cubism export (experimental): structure checks
        model.reset_values()
        m3 = moc3.export_moc3(model, tmp / "cubism", "Test")
        data = (tmp / "cubism" / "Test.moc3").read_bytes()
        assert data[:4] == b"MOC3" and data[4] == 1
        sot = struct.unpack("<160I", data[64:704])
        assert sot[0] == 1984 and all(b >= a for a, b in zip(sot, sot[1:]) if b)
        counts = struct.unpack("<23i", data[1984:1984 + 92])
        assert counts[4] == len([m for m in model.meshes() if len(m.tris)]) and counts[5] == len(model.params)
        meta = json.loads(m3.read_text("utf-8"))
        assert all((tmp / "cubism" / t).exists() for t in meta["FileReferences"]["Textures"])
        assert json.loads((tmp / "cubism" / "Test.physics3.json").read_text("utf-8"))["Meta"]["PhysicsSettingCount"]
        report["moc3_bytes"] = len(data)
        # Inochi2D round trip
        inochi.export_inp(model, tmp / "a.inp")
        im2 = inochi.import_inp(tmp / "a.inp")
        assert len(im2.meshes()) == len(model.meshes())
        # PNGTuber
        from mu.ui import export_pngtuber
        files = export_pngtuber(model, tmp / "png")
        assert len(files) == 4 and all(p.stat().st_size > 1000 for p in files)

        # the whole UI
        from mu.ui import MainWindow, prepare_model
        win = MainWindow(app)
        win.resize(1400, 900)
        win.show()
        doc = Doc(prepare_model(back), tmp / "a.mu")
        win.set_doc(doc, "rig")
        app.processEvents()
        for i in range(6):
            win.tabs.setCurrentIndex(i)
            app.processEvents()
        # rig canvas: select a part and drag it into a key of the active parameter
        win.tabs.setCurrentIndex(1)
        rig = win.pages["rig"]
        cv = rig.canvas
        cv.resize(900, 700)
        cv.fit()
        doc.select([face.id])
        doc.active_param = "ParamAngleZ"
        doc.set_value("ParamAngleZ", 15.0)
        before = doc.frame().meshes[face.id][0].copy()
        cv.vsel = {face.id: {0, 1, 2}}
        doc.move_points(doc.model.nodes[face.id], [0, 1, 2], np.array([6.0, 0.0]))
        doc.commit()
        after = doc.model.evaluate().meshes[face.id][0]
        assert abs(after[0, 0] - before[0, 0] - 6.0) < 0.5
        assert doc.model.nodes[face.id].binding("ParamAngleZ") is not None
        doc.undo()
        assert doc.model.nodes[face.id].binding("ParamAngleZ") is None
        rig.params.toggle_key("ParamAngleZ")
        assert doc.model.nodes[face.id].binding("ParamAngleZ") is not None
        rig.add_warp()
        assert doc.selected_deformers()
        cv.repaint()
        # cut workspace on a picture model
        doc2 = Doc(prepare_model(art.new_model_from_image(flat, "Картинка")))
        win.set_doc(doc2, "cut")
        app.processEvents()
        cut = win.pages["cut"]
        doc2.select([doc2.model.meshes()[0].id])
        cut.canvas.apply_mask(mask)
        cut.cut(False)
        assert len(doc2.model.meshes()) == 2
        doc2.undo()
        assert len(doc2.model.meshes()) == 1
        cut.canvas.repaint()
        # studio + live on the rigged model
        win.set_doc(doc, "studio")
        st = win.pages["studio"]
        app.processEvents()
        assert st.view.instances
        st.apply_pose({"name": "Ура", "kind": "Поза", "values": preset_values("Ура!")})
        st.poses.blend.setChecked(False)
        st.apply_pose({"name": "Ура", "kind": "Поза", "values": preset_values("Ура!")})
        bg = QImage(800, 600, QImage.Format_RGB32)
        bg.fill(QColor("#88AACC"))
        bg.save(str(tmp / "bg.png"))
        st.set_bg_file(str(tmp / "bg.png"))
        shot = st.view.render_image(0.5)
        assert shot.width() == 400 and shot.pixelColor(2, 2).blue() > 150
        from mu.studio import pose_thumbnail
        assert not pose_thumbnail(doc.model, st.view.selected.values).isNull()
        win.tabs.setCurrentIndex(4)
        live = win.pages["live"]
        doc.model.meta["idle"] = [{"param": "ParamAngleZ", "center": 0, "amp": 20, "period": 4.0, "phase": 1.5}]
        live.driver.follow = False
        live.driver.idle = False
        live.driver.t0 = __import__("time").monotonic()
        live.driver.step()
        live.driver.step()
        assert abs(live.driver.values["ParamAngleZ"]) > 10  # the model's own idle loop plays
        # animation clips and blink bursts
        live.driver.play_clip({"name": "t", "duration": 5.0, "tracks": {"ParamMouthOpenY": [[0, 1], [5, 1]]}})
        live.driver.step()
        assert live.driver.values["ParamMouthOpenY"] > 0.99
        doc.model.meta["blink"] = {"double": 1.0, "offset": 0.1}
        live.driver.blinks = []
        live.driver.plan_blinks(__import__("time").monotonic())
        assert len(live.driver.blinks) == 4
        assert abs(live.driver.track_value([[0, 0], [1, 10]], 0.5) - 5.0) < 1e-6
        assert live.driver.values
        live.canvas.repaint()
        doc.mark_saved()
        win.dirty_extra = False
        report["ui"] = "ok"
        win.close()
        win.deleteLater()
        app.processEvents()
    print("mu selftest ok", json.dumps(report, ensure_ascii=False))
    from mu.ui import release_caches
    release_caches()
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        code = selftest()
        sys.stdout.flush()
        sys.stderr.flush()
        import os
        os._exit(code)  # every check ran; skip interpreter teardown of Qt objects
    from mu.ui import main

    sys.exit(main())
