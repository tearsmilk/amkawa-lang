"""Entry point (PyInstaller / `python run.py`). `--selftest` runs headless checks for CI."""
import os
import sys


def selftest():
    import os
    import tempfile
    import time

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # CI has no display
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")
    tmp = tempfile.mkdtemp()
    os.environ["THETA_DATA"] = tmp
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    report = {}
    from tests.test_theta import run as core_test

    report["core"] = core_test(tmp)["calls"]
    from theta import theme
    from theta.game import Records
    from theta.paths import Settings
    from theta.ui import MainWindow

    assert theme.compose(theme.DARK, {})["accent"] == "#D97757" and "#Overlay" in theme.extra(theme.LIGHT | {"serif": theme.SERIF})
    settings = Settings()
    settings.update(nickname="Hoka", mapillary_token="tok", source="mapillary")
    win = MainWindow(app, settings, Records())
    win.resize(1240, 800)
    win.show()
    win.start(fast=True)
    t0 = time.monotonic()
    while win.root.currentIndex() == 0 and time.monotonic() - t0 < 5:
        app.processEvents()
        time.sleep(0.005)
    assert win.root.currentIndex() == 1, "loading page did not finish"
    for key in ("home", "records", "settings", "home"):
        win.go(key)
        app.processEvents()
        win.grab()
    assert win.nav["home"].isChecked() and "Hoka" in win.home.title.text()
    assert win.home.hero.source_box.currentData() == "mapillary" and win.home.hero.play.isEnabled()
    win.home.hero.mode_box.setCurrentIndex(win.home.hero.mode_box.findData("daily"))
    assert settings["mode"] == "daily" and not win.home.hero.map_box.isEnabled()
    win.home.hero.mode_box.setCurrentIndex(0)
    # the game page: the controller is tested in tests.test_theta; here the overlays lay out and switch
    win.go("game")
    gp = win.game_page
    gp.resize(1000, 700)
    gp.set_map_size(2)
    gp.expand(True)
    gp._relayout()
    assert gp.map_panel.width() >= 400 and settings["map_size"] == 2
    gp.toggle_pin()
    assert settings["map_pinned"] and gp.pinned
    gp.toggle_pin()
    win.grab()
    # settings page toggles
    win.go("settings")
    win.settings_page.theme_box.setCurrentIndex(win.settings_page.theme_box.findData("dark"))
    assert settings["theme"] == "dark" and theme.CURRENT["name"] == "dark"
    win.settings_page.theme_box.setCurrentIndex(0)
    win.toggle_sidebar()
    assert win.rail.isVisible() or not win.isVisible()
    win.toggle_sidebar()
    report["ui"] = 4
    print("theta selftest ok", __import__("json").dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        code = selftest()
        # the result is already printed; skip Qt/WebEngine teardown, which can crash offscreen
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)
    from theta.ui import main

    sys.exit(main())
