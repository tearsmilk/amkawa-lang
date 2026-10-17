"""Entry point (PyInstaller / `python run.py`). `--selftest` runs headless checks for CI."""
import sys


def selftest():
    import tempfile
    from pathlib import Path

    from epsilon.codedetect import detect_language, looks_like_code
    from epsilon.mdrender import Renderer
    from epsilon.theme import LIGHT
    from epsilon.vault import Vault

    with tempfile.TemporaryDirectory() as tmp:
        v = Vault(Path(tmp) / "vault")
        welcome = v.ensure_welcome()
        assert welcome and welcome.exists()
        a = v.create_note("Идеи", text="# Идеи\nсм. [[Добро пожаловать]] #проект\n```\nimport os\nprint(os.name)\n```\n")
        assert v.backlinks(welcome) == [a], v.backlinks(welcome)
        assert "проект" in v.tags()
        assert v.search("print")[0][0] == a
        renamed = v.rename(welcome, "Старт")
        assert "[[Старт]]" in v.read(a)
        v.add_link("example.com", tags=["web"])
        assert v.links()[0].url == "https://example.com"
        html = Renderer(LIGHT, v.resolve).render(v.read(a) + "\n- [ ] задача\n> [!tip] ок\n> текст\n")
        assert "PYTHON" in html and "task:" in html and "tag:проект" in html and "note:Старт" in html
        assert v.graph()[1], "graph has no edges"
        assert renamed.exists()
        # trash: delete → restore → delete → empty into the system trash
        trashed = v.delete(a)
        assert not a.exists() and v.trash_items()[0][1] == "Идеи.md"
        back = v.restore(trashed)
        assert back == a and a.exists() and not v.trash_items()
        v.delete(a)
        moved_to = []
        moved, errors = v.empty_trash(mover=lambda p: (moved_to.append(p.name), p.unlink()))
        assert moved == 1 and not errors and not v.trash_items(), (moved, errors)
        # tasks / calendar
        import datetime as dt

        from epsilon.tasks import TaskIndex

        idx = TaskIndex(v)
        day = dt.date(2026, 10, 20)
        idx.add("Позвонить", day, dt.time(14, 30), 3)
        v.create_note("План", text="- [ ] сдать отчёт 📅 2026-10-21 🔼\n- [x] готово 📅 2026-10-20\n```\n- [ ] не задача\n```\n- [ ] без даты\n")
        on = idx.on(day)
        assert [t.text for t in on] == ["Позвонить", "готово"], [t.text for t in on]
        assert on[0].time == dt.time(14, 30) and on[0].priority == 3
        assert [t.text for t in idx.on(day + dt.timedelta(days=1))] == ["сдать отчёт"]
        assert "без даты" in [t.text for t in idx.undated()] and "не задача" not in [t.text for t in idx.all()]
        idx.toggle(on[0])
        assert idx.on(day)[0].done
        idx.reschedule(idx.on(day + dt.timedelta(days=1))[0], day)
        assert len(idx.on(day)) == 3
        idx.delete(next(t for t in idx.on(day) if t.text == "готово"))
        assert len(idx.on(day)) == 2
        # attachments: import, kinds, picture / GIF inline, video / file as a card
        from epsilon import attachments as att

        src = Path(tmp) / "clip.mp4"
        src.write_bytes(b"\0" * 2048)
        gif = Path(tmp) / "fun.gif"
        gif.write_bytes(b"GIF89a")
        clip, anim = v.import_file(src), v.import_file(gif)
        again = v.import_file(src)
        assert clip.parent.name == "attachments" and again.name == "clip 2.mp4", again
        assert [att.kind_of(p) for p in (clip, anim, "a.PDF", "b.mp3", "c.heic", "d.xyz")] == \
            ["video", "gif", "pdf", "audio", "image", "file"]
        assert att.describe(clip) == "Видео · MP4 · 2.0 КБ", att.describe(clip)
        note = v.create_note("Медиа", text="![clip](attachments/clip.mp4)\n\n![fun](attachments/fun.gif)\n"
                                           "текст ![[fun.gif]] и [[clip.mp4]]\n")
        r = Renderer(LIGHT, v.resolve, base_dir=note.parent)
        html = r.render(v.read(note))
        clip, anim = clip.resolve(), anim.resolve()  # macOS temp dir: /var → /private/var
        assert "▶&nbsp;Смотреть" in html and "Видео · MP4" in html and anim.as_uri() in html, html
        assert "attach:" in html and "reveal:" in html and r.attachments[:2] == [clip, anim]
        if sys.platform == "darwin":  # the real macOS Trash (NSFileManager via ctypes)
            from epsilon.systrash import move_to_trash

            probe = Path(tmp) / "epsilon-trash-probe.txt"
            probe.write_text("probe")
            move_to_trash(probe)
            assert not probe.exists(), "macOS Trash move failed"
            print("macOS trash ok")
    assert looks_like_code("def f(x):\n    return x * 2\n") and detect_language("SELECT * FROM t WHERE a=1;") == "sql"
    assert not looks_like_code("Сегодня хорошая погода, пойду гулять.\nА вечером почитаю книгу.")
    import PySide6.QtWidgets  # noqa: F401
    from PySide6.QtPrintSupport import QPrinter  # noqa: F401  (PDF export)
    # video / audio playback in the attachment viewer: the backend plugin must be bundled
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtMultimedia import QMediaFormat

    app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841
    formats = QMediaFormat().supportedFileFormats(QMediaFormat.Decode)
    print("media formats:", len(formats))
    assert formats or sys.platform != "darwin", "no QtMultimedia backend"
    print("selftest ok")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    from epsilon.ui import main

    sys.exit(main())
