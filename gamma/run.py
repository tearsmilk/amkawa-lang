"""Entry point (PyInstaller / `python run.py`). `--selftest` runs headless checks for CI."""
import sys


def selftest():
    import json
    import os
    import tempfile
    import time
    from pathlib import Path

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # CI has no display
    from PySide6.QtCore import QEvent, QPointF, QRect, Qt
    from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPixmap
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from gamma import ffmpeg, paths
    from gamma.overlay import Countdown, RecordBar, RecordFrame, RegionSelector, Toast

    report = {}
    exe = ffmpeg.ffmpeg_exe()
    assert exe, "ffmpeg is not bundled"
    code, err = ffmpeg.run(["-version"])
    assert code == 0
    report["ffmpeg"] = exe.split("/")[-1]
    assert ffmpeg.has_encoder("libx264")
    if ffmpeg.IS_MAC:
        report["videotoolbox"] = ffmpeg.has_encoder("h264_videotoolbox")   # may be False on a VM without a GPU
        devs = ffmpeg.list_devices(refresh=True)
        report["avfoundation"] = {k: len(v) for k, v in devs.items()}
        code, err = ffmpeg.run(["-hide_banner", "-devices"])
        assert "avfoundation" in err or code == 0

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp).resolve()
        s = paths.Settings(tmp / "settings.json")
        s["video_dir"] = str(tmp / "Видео")
        s["shot_dir"] = str(tmp / "Снимки")
        s["countdown"] = 0
        s["preview"] = True
        s["shutter"] = False
        s.save()
        assert paths.Settings(tmp / "settings.json")["video_dir"] == str(tmp / "Видео")
        assert s.hotkey("replay_save")["text"] == "⇧⌘0"

        # recording: a 640×360 test picture standing in for a 1280×720 Retina screen, region crop + sound
        src = ["-re", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30",
               "-re", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000"]
        spec = ffmpeg.CaptureSpec(screen_size=(640, 360), dpr=2.0, region=(100, 50, 200, 100), fps=30,
                                  encoder="x264", source=src, source_audio=["1:a"])
        assert spec.pixel_size() == (400, 200)
        rec = ffmpeg.Recorder(spec, tmp / "Видео" / "rec.mp4")
        rec.start()
        time.sleep(2.5)
        assert rec.poll()
        out = rec.stop()
        assert out and out.exists() and not rec.tmp.exists(), rec.error
        code, info = ffmpeg.run(["-i", str(out)])
        assert "400x200" in info and "Audio: aac" in info, info
        dur = ffmpeg.probe_duration(out)
        assert 1.5 < dur < 4.0, dur
        report["record_s"] = round(dur, 2)
        assert ffmpeg.thumbnail(out, tmp / "thumb.jpg")
        if ffmpeg.IS_MAC and report.get("videotoolbox"):
            spec_hw = ffmpeg.CaptureSpec(screen_size=(640, 360), fps=30, encoder="hw", source=src[:5])
            r2 = ffmpeg.Recorder(spec_hw, tmp / "hw.mov")
            r2.start()
            time.sleep(1.5)
            assert r2.stop(), r2.error

        # replay: keep 3 s, save 3 s before + 2 s after
        ring = ffmpeg.ReplayBuffer(ffmpeg.CaptureSpec(screen_size=(640, 360), fps=30, encoder="x264", source=src,
                                                      source_audio=["1:a"]),
                                   5, segment=1.0, folder=tmp / "ring", threaded=False)
        ring.start()
        t0 = time.monotonic()
        while time.monotonic() - t0 < 5.5:
            ring.poll()
            time.sleep(0.1)
        assert ring.running() and ring.buffered() > 3
        result = {}
        ring.save(3, 2, tmp / "Видео" / "replay.mp4", lambda p, e: result.update(path=p, error=e))
        t0 = time.monotonic()
        while "path" not in result and time.monotonic() - t0 < 15:
            ring.poll()
            time.sleep(0.1)
        ring.stop()
        assert result.get("path"), result
        rdur = ffmpeg.probe_duration(result["path"])
        assert 4.0 < rdur < 6.5, rdur
        report["replay_s"] = round(rdur, 2)
        ring.cleanup()

        # the UI with these settings
        from gamma import ui
        from gamma.app import Gamma, crop

        paths_settings = ui.Settings
        ui.Settings = lambda: s  # noqa: E731
        try:
            gamma = Gamma(app, s)
            win = ui.MainWindow(app, gamma)
        finally:
            ui.Settings = paths_settings
        win.show()
        app.processEvents()
        for i in range(3):
            win.go(i)
            app.processEvents()
        win.go(0)
        assert win.home.recent.count() >= 2  # rec.mp4 + replay.mp4
        for _ in range(10):
            win.home._next_thumb()
        win.home.set_audio("mic")
        assert s["audio"] == "mic"
        win.home.set_audio("none")
        # hotkey editor: ⇧⌘7 (Qt: Ctrl = ⌘ on macOS)
        ed = win.hotkeys_page.edits["shot_region"]
        ed.listen()
        ev = QKeyEvent(QEvent.KeyPress, Qt.Key_7, Qt.ControlModifier | Qt.ShiftModifier, 0x1A, 0x1A, 0, "7")
        ed.keyPressEvent(ev)
        assert s.hotkey("shot_region")["key"] == Qt.Key_7 and not ed.listening
        win.hotkeys_page.reset()
        assert s.hotkey("shot_region")["text"] == "⇧⌘2"
        report["hotkeys"] = gamma.hotkeys.available()

        # screenshots: region selector on a fake frozen screen, crop, save + clipboard + toast
        screen = app.primaryScreen()
        g = screen.geometry()
        pix = QPixmap(g.width() * 2, g.height() * 2)
        pix.fill(QColor("#336699"))
        pix.setDevicePixelRatio(2.0)
        sel = RegionSelector(screen, pix, "shot", instant=True, hide_from_capture=True)
        got = []
        sel.accepted.connect(lambda r, o: got.append(r))
        sel.show()
        app.processEvents()

        def mouse(kind, x, y):
            btn = Qt.LeftButton
            e = QMouseEvent(kind, QPointF(x, y), QPointF(x, y), btn,
                            Qt.NoButton if kind == QEvent.MouseButtonRelease else btn, Qt.NoModifier)
            {QEvent.MouseButtonPress: sel.mousePressEvent, QEvent.MouseMove: sel.mouseMoveEvent,
             QEvent.MouseButtonRelease: sel.mouseReleaseEvent}[kind](e)

        mouse(QEvent.MouseButtonPress, 20, 30)
        mouse(QEvent.MouseMove, 120, 90)
        sel.grab()  # paint with selection + loupe
        mouse(QEvent.MouseButtonRelease, 120, 90)
        assert got and got[0].width() >= 99 and got[0].height() >= 59, got
        part = crop(pix, got[0])
        assert part.width() >= 198
        shot = gamma.save_shot(part)
        assert shot and shot.exists() and QPixmap(str(shot)).width() == part.width()
        assert not app.clipboard().image().isNull()
        s["shot_format"] = "jpg"
        assert gamma.save_shot(part).suffix == ".jpg"
        # record selector with a toolbar, keyboard accept = whole screen
        sel2 = RegionSelector(screen, pix, "record", audio="mic")
        got2 = []
        sel2.accepted.connect(lambda r, o: got2.append((r, o)))
        sel2.show()
        sel2._set_audio("both")
        sel2.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
        assert got2 and got2[0][0].size() == sel2.rect().size() and got2[0][1]["audio"] == "both"
        # recording chrome
        frame = RecordFrame(QRect(100, 100, 300, 200))
        frame.show()
        bar = RecordBar("Запись области", "микрофон")
        bar.set_time(75.4)
        bar.place(QRect(100, 100, 300, 200), g)
        bar.show()
        assert bar.time.text() == "01:15"
        cd = Countdown(1, g.center())
        done = []
        cd.finished.connect(lambda: done.append(1))
        cd.start()
        t0 = time.monotonic()
        while not done and time.monotonic() - t0 < 3:
            app.processEvents()
            time.sleep(0.02)
        assert done
        t = Toast("Снимок сохранён", "test", pix)
        t.popup()
        app.processEvents()
        # whole flow: recording from the controller with a test source, stopped from the bar
        s["countdown"] = 0
        spec3 = ffmpeg.CaptureSpec(screen_size=(640, 360), fps=30, encoder="x264", source=src[:5])
        gamma.start_recording(screen, QRect(10, 10, 200, 100), spec=spec3)
        t0 = time.monotonic()
        while time.monotonic() - t0 < 2.0:
            app.processEvents()
            time.sleep(0.02)
        assert gamma.recorder is not None and gamma.rec_bar is not None, [(x.title.text(), x.text.text()) for x in gamma.toasts]
        gamma.stop_recording(sync=True)
        app.processEvents()
        vids = list((tmp / "Видео").glob("Запись *.mp4"))
        assert vids, list((tmp / "Видео").iterdir())
        for w in (frame, bar, t):
            w.close()
        win.home.refresh()
        report["files"] = win.home.recent.count()
        gamma.shutdown()
        win.hide()
        app.processEvents()
    print("gamma selftest ok", json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        code = selftest()
        sys.stdout.flush()
        sys.stderr.flush()
        import os

        os._exit(code)  # every check ran; skip interpreter teardown of Qt objects
    from gamma.ui import main

    sys.exit(main())
