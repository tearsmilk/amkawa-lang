"""Entry point (PyInstaller / `python run.py`). `--selftest` runs headless checks for CI."""
import sys


def selftest():
    import os
    import subprocess
    import tempfile
    import time
    from pathlib import Path

    from nu import languages
    from nu.palette import fuzzy_score, symbols
    from nu.scm import parse_status
    from nu.search import compile_query, search

    # languages
    assert languages.detect("main.py").id == "python" and languages.detect("App.tsx").id == "tsx"
    assert languages.detect("Dockerfile").id == "dockerfile" and languages.detect("x.unknownext").id == "text"
    assert languages.detect("lib.rs").name == "Rust" and languages.detect("query.sql").comment == "--"
    assert len(languages.all_languages()) > 300, len(languages.all_languages())
    assert "python3" in languages.run_command(languages.detect("a.py"), "/tmp/a b.py", "/tmp")
    assert fuzzy_score("mwin", "nu/main_window.py") is not None and fuzzy_score("zzz", "abc") is None
    assert [s[0] for s in symbols("class A:\n    def run(self):\n        pass\nfunction go() {}")] == ["A", "run", "go"]
    st = parse_status(" M a.py\0?? new.txt\0R  b.py\0old.py\0", "/r")
    assert st == {"/r/a.py": "M", "/r/new.txt": "?", "/r/b.py": "R"}, st

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "src").mkdir()
        (root / "src" / "app.py").write_text("def hello():\n    return 'Привет'\n\nprint(hello())\n", "utf-8")
        (root / "node_modules").mkdir()
        (root / "node_modules" / "x.js").write_text("hello", "utf-8")
        res = search(str(root), compile_query("hello"))
        assert [Path(p).name for p, _ in res] == ["app.py"] and len(res[0][1]) == 2, res

        # Qt: editor, highlighter, terminal
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # CI has no display
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from nu.editor import CodeEditor
        from nu.paths import Settings
        from nu.theme import LIGHT

        settings = Settings()
        ed = CodeEditor(LIGHT, settings, root / "src" / "app.py")
        ed.load(root / "src" / "app.py")
        spans = ed.highlighter.lex(ed.toPlainText())
        assert any(k == "keyword" for _s, _l, k in spans[0]) and any(k == "string" for _s, _l, k in spans[1]), spans[:2]
        ml = ed.highlighter.lex('x = """a\nb"""\ny = 1')
        assert ml[1] and ml[1][0][2] == "string", ml  # multi-line string stays a string on line 2
        ed.toggle_comment()
        assert ed.toPlainText().startswith("# def hello"), ed.toPlainText()[:20]
        ed.toggle_comment()
        assert ed.toPlainText().startswith("def hello")
        ed.move_lines(1)
        assert ed.toPlainText().split("\n")[1] == "def hello():"
        ed.move_lines(-1)
        ed.duplicate_lines()
        assert ed.toPlainText().split("\n")[:2] == ["def hello():", "def hello():"]
        assert len(ed.find_all("hello")) == 3
        ed.save()
        assert (root / "src" / "app.py").read_text("utf-8").startswith("def hello():\ndef hello():")

        from nu.terminal import TerminalWidget

        term = TerminalWidget(LIGHT, settings, cwd=str(root), shell="/bin/sh")
        term.resize(600, 300)
        term.run("echo nu-$((6*7))")
        deadline = time.time() + 10
        while "nu-42" not in term.text() and time.time() < deadline:
            app.processEvents()
            time.sleep(0.02)
        assert "nu-42" in term.text(), term.text()
        term.close_process()

        if subprocess.run(["git", "--version"], capture_output=True).returncode == 0:
            from nu.scm import repo_root, status

            subprocess.run(["git", "init", "-q", str(root)], check=True)
            assert repo_root(str(root)) is not None
            assert any(v == "?" for v in status(repo_root(str(root))).values())
    print("selftest ok")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    from nu.ui import main

    sys.exit(main())
