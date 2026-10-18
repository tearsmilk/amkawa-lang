"""Entry point (PyInstaller / `python run.py`). `--selftest` runs headless checks for CI."""
import sys


def selftest():
    import json
    import os
    import tempfile
    from datetime import datetime, timedelta

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # CI has no display
    tmp = tempfile.mkdtemp()
    os.environ["ALPHA_DATA"] = tmp
    from PySide6.QtCore import QMimeData, QPointF, Qt
    from PySide6.QtGui import QDropEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from alpha import automation as A
    from alpha.exchange import export_csv, export_markdown, from_template, import_trello
    from alpha.model import Store
    from alpha.paths import Settings

    report = {}
    store = Store()
    b = store.add(from_template("Канбан", "Тест"))
    auto = A.Automation()
    auto.attach(b)
    lists = b.lists()
    todo, doing, done = lists[1], lists[2], lists[-1]
    # cards, moving, positions
    c1 = b.add_card(todo["id"], "Первая")
    c2 = b.add_card(todo["id"], "Вторая")
    b.move_card(c2["id"], todo["id"], 0)
    assert [c["id"] for c in b.cards(todo["id"])][0] == c2["id"]
    # rule from the template: moved to «Готово» → done + green label
    b.move_card(c1["id"], done["id"])
    assert b.card(c1["id"])["due_done"] and b.card(c1["id"])["labels"]
    assert b.undo() and not b.card(c1["id"])["due_done"] and b.card(c1["id"])["list"] == todo["id"]
    assert b.redo() and b.card(c1["id"])["due_done"]
    # checklist → automation (rule added from the ideas)
    ideas = A.suggestions(b)
    b.d["rules"].append(A.clone_rule(ideas[2]))  # all checklist items done → move to the last list
    cl = b.add_checklist(c2["id"], "Шаги", ["раз", "два"])
    for it in cl["items"]:
        b.set_item(c2["id"], cl["id"], it["id"], done=True)
    assert b.card(c2["id"])["list"] == done["id"]
    # due-date command and schedule
    due_rule = A.new_rule(kind="due", trigger={"when": "before", "amount": 2, "unit": "hours"},
                          actions=[{"type": "set_cover", "color": "red"}])
    sched = A.new_rule(kind="schedule", trigger={"type": "daily", "time": "00:00"},
                       actions=[{"type": "create_card", "list": todo["id"], "title": "Ежедневная {date}"}])
    sched["created"] = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
    b.d["rules"] += [due_rule, sched]
    c3 = b.add_card(todo["id"], "Скоро срок", due=(datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"))
    assert auto.tick(b) >= 2
    assert b.card(c3["id"])["cover"]["color"] == "red"
    assert any(c["title"].startswith("Ежедневная") for c in b.cards(todo["id"]))
    assert auto.tick(b) == 0  # nothing twice
    # buttons
    btn = next(r for r in b.d["rules"] if r["kind"] == "card_button")
    auto.press_card_button(b, btn, c3["id"])
    assert b.card(c3["id"])["list"] == done["id"]
    assert auto.press_board_button(b, next(r for r in b.d["rules"] if r["kind"] == "board_button")) == 0
    assert not b.cards(done["id"])  # archived
    report["rules"] = len(b.d["rules"])
    # filter, stats, export, store round trip
    assert b.matches(b.card(c3["id"]), {"text": "скоро"}) and not b.matches(b.card(c3["id"]), {"text": "нет"})
    assert "Скоро срок" in export_csv(b) and export_markdown(b).startswith("# Тест")
    store.save()
    again = Store()
    assert len(again.boards[b.id].d["cards"]) == len(b.d["cards"])
    # Trello import
    trello = {
        "name": "Из Trello", "idOrganization": "x", "prefs": {"background": "blue"},
        "labels": [{"id": "l1", "name": "Баг", "color": "red"}],
        "lists": [{"id": "L1", "name": "To Do", "pos": 1}, {"id": "L2", "name": "Done", "pos": 2}],
        "members": [{"id": "m1", "fullName": "Аня Петрова", "initials": "АП"}],
        "cards": [{"id": "C1", "name": "Починить", "idList": "L1", "idLabels": ["l1"], "idMembers": ["m1"],
                   "pos": 1, "due": "2026-10-20T15:00:00.000Z", "dueComplete": False, "desc": "текст",
                   "attachments": [{"name": "сайт", "url": "https://example.com"}]}],
        "checklists": [{"id": "K1", "idCard": "C1", "name": "Шаги",
                        "checkItems": [{"name": "a", "state": "complete", "pos": 1}]}],
        "actions": [{"type": "commentCard", "date": "2026-10-01T10:00:00Z", "data": {"text": "привет",
                                                                                   "card": {"id": "C1"}},
                     "memberCreator": {"fullName": "Аня"}}],
    }
    tb = store.add(import_trello(trello))
    tc = tb.cards()[0]
    assert tc["labels"] and tc["members"] and tc["checklists"][0]["items"][0]["done"] and tc["comments"] and tc["due"]
    report["trello"] = "ok"

    # the UI
    from alpha.ui import MainWindow

    settings = Settings(os.path.join(tmp, "settings.json"))
    win = MainWindow(app, store, settings)
    win.resize(1300, 800)
    win.show()
    win.open_board(b.id)
    app.processEvents()
    page = win.board_page
    bv = page.board_view
    cols = bv.lane.columns()
    assert len(cols) == len(b.lists())
    # drag a card onto another list through a real drop event
    src = b.add_card(lists[0]["id"], "Перетащи меня")
    win.board_changed()
    app.processEvents()
    target = bv.column(doing["id"])
    md = QMimeData()
    from alpha.board_view import CARD_MIME

    md.setData(CARD_MIME, src["id"].encode())
    bv.dragging = src["id"]
    ev = QDropEvent(QPointF(40, 60), Qt.MoveAction, md, Qt.LeftButton, Qt.NoModifier)
    target.dropEvent(ev)
    bv.dragging = None
    app.processEvents()
    assert b.card(src["id"])["list"] == doing["id"], b.list(b.card(src["id"])["list"])["name"]
    # list reorder
    b.move_list(lists[0]["id"], len(b.lists()))
    assert b.lists()[-1]["id"] == lists[0]["id"]
    win.board_changed()
    app.processEvents()
    # views
    for key in ("table", "calendar", "dashboard", "board"):
        page.set_view(key)
        app.processEvents()
        page.stack.currentWidget().grab()
    assert page.table.rowCount() == len(b.cards())
    page.apply_filter({"text": "перетащи меня"})
    app.processEvents()
    visible = [w for col in bv.lane.columns() for w in col.stack.cards() if not w.isHidden()]
    assert len(visible) == 1
    page.apply_filter({})
    # card dialog: description, comment, checklist, label
    win.open_card(src["id"])
    dlg = win.card_dialog
    app.processEvents()
    dlg._edit_desc()
    dlg.desc_box.setPlainText("**Жирный** текст")
    dlg._save_desc()
    dlg._comment("Готово наполовину")
    b.add_checklist(src["id"], "Пункты", ["x"])
    dlg.reload()
    b.toggle_label(src["id"], b.d["labels"][0]["id"])
    win.board_changed()
    app.processEvents()
    assert b.card(src["id"])["desc"] and b.card(src["id"])["comments"]
    dlg.grab()
    dlg.close()
    # automation window + rule editor
    from alpha.automation_ui import AutomationDialog, RuleEditor

    ad = AutomationDialog(win, b, win.automation)
    for i in range(ad.nav.count()):
        ad.nav.setCurrentRow(i)
        app.processEvents()
    r = A.new_rule(trigger={"type": "label_added", "label": b.d["labels"][1]["id"]},
                   actions=[{"type": "move", "list": doing["id"], "where": "top"}])
    ed = RuleEditor(b, r)
    ed.update_preview()
    assert "метка" in ed.preview.text()
    ed.save()
    ad.close()
    win.go_home()
    win.go_notes()
    win.go_settings()
    app.processEvents()
    win.store.save()
    report["boards"] = len(store.boards)
    report["cards"] = sum(len(x.d["cards"]) for x in store.boards.values())
    win.close()
    app.processEvents()
    print("alpha selftest ok", json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        code = selftest()
        sys.stdout.flush()
        sys.stderr.flush()
        import os

        os._exit(code)  # every check ran; skip interpreter teardown of Qt objects
    from alpha.ui import main

    sys.exit(main())
