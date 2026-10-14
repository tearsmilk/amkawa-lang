"""Entry point (PyInstaller / `python run.py`). `--selftest` runs headless checks for CI."""
import sys


def selftest():
    import tempfile
    from pathlib import Path

    from milkys_hub.codedetect import detect_language, looks_like_code
    from milkys_hub.mdrender import Renderer
    from milkys_hub.theme import LIGHT
    from milkys_hub.vault import Vault

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
    assert looks_like_code("def f(x):\n    return x * 2\n") and detect_language("SELECT * FROM t WHERE a=1;") == "sql"
    assert not looks_like_code("Сегодня хорошая погода, пойду гулять.\nА вечером почитаю книгу.")
    import PySide6.QtWidgets  # noqa: F401
    from PySide6.QtPrintSupport import QPrinter  # noqa: F401  (PDF export)
    print("selftest ok")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    from milkys_hub.ui import main

    sys.exit(main())
