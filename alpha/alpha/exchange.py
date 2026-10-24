"""Import from a Trello board export (Board menu → Print, export and share → Export as JSON), export to JSON / CSV /
Markdown, and the built-in board templates."""
import csv
import io
import json

from .automation import new_rule
from .model import empty_board, fmt_dt, initials, new_card, new_id, now_iso, parse_dt

TRELLO_BG = {"blue": "ocean", "orange": "terracotta", "green": "forest", "red": "rose", "purple": "plum",
             "pink": "rose", "lime": "forest", "sky": "sky", "grey": "graphite"}
MEMBER_COLORS = ["#D97757", "#5B8CC4", "#7BA05B", "#9B7BC4", "#E08A4A", "#5DAFC4", "#D97BA6"]


def _iso(s):
    d = parse_dt(s) if s else None
    return d.strftime("%Y-%m-%dT%H:%M") if d else ""


def import_trello(data):
    """Trello export dict → our board dict."""
    b = empty_board(data.get("name") or "Доска из Trello", TRELLO_BG.get((data.get("prefs") or {}).get(
        "background", ""), "ocean"))
    b["desc"] = data.get("desc") or ""
    b["labels"] = []
    label_map = {}
    for lb in data.get("labels", []):
        color = lb.get("color") or "black"
        color = color.replace("_dark", "").replace("_light", "")
        if color not in ("green", "yellow", "orange", "red", "purple", "blue", "sky", "lime", "pink", "black"):
            color = "black"
        nid = new_id()
        label_map[lb["id"]] = nid
        b["labels"].append({"id": nid, "name": lb.get("name") or "", "color": color})
    member_map = {}
    for i, m in enumerate(data.get("members", [])):
        nid = new_id()
        member_map[m["id"]] = nid
        name = m.get("fullName") or m.get("username") or "Участник"
        b["members"].append({"id": nid, "name": name, "initials": m.get("initials") or initials(name),
                             "color": MEMBER_COLORS[(i + 1) % len(MEMBER_COLORS)]})
    field_map = {}
    for f in data.get("customFields", []):
        nid = new_id()
        field_map[f["id"]] = (nid, {o["id"]: (o.get("value") or {}).get("text", "") for o in f.get("options", [])})
        ftype = {"text": "text", "number": "number", "date": "date", "checkbox": "checkbox", "list": "list"}.get(
            f.get("type"), "text")
        b["fields"].append({"id": nid, "name": f.get("name", "Поле"), "type": ftype,
                            "options": list(field_map[f["id"]][1].values()), "on_front": True})
    list_map = {}
    for lst in sorted(data.get("lists", []), key=lambda x: x.get("pos", 0)):
        nid = new_id()
        list_map[lst["id"]] = nid
        b["lists"].append({"id": nid, "name": lst.get("name", ""), "pos": float(lst.get("pos", 0) or 0),
                           "closed": bool(lst.get("closed")), "wip": 0, "color": ""})
    checklists = {}
    for cl in data.get("checklists", []):
        checklists.setdefault(cl.get("idCard"), []).append({
            "id": new_id(), "name": cl.get("name") or "Чек-лист",
            "items": [{"id": new_id(), "text": it.get("name", ""), "done": it.get("state") == "complete",
                       "due": _iso(it.get("due")), "member": member_map.get(it.get("idMember"), "")}
                      for it in sorted(cl.get("checkItems", []), key=lambda x: x.get("pos", 0))]})
    comments = {}
    for a in data.get("actions", []):
        if a.get("type") == "commentCard":
            cid = ((a.get("data") or {}).get("card") or {}).get("id")
            who = (a.get("memberCreator") or {}).get("fullName") or "Trello"
            comments.setdefault(cid, []).append({"id": new_id(), "text": (a.get("data") or {}).get("text", ""),
                                                 "ts": _iso(a.get("date")), "who": who})
    card_count = 0
    for c in data.get("cards", []):
        if c.get("idList") not in list_map:
            continue
        nc = new_card(list_map[c["idList"]], c.get("name", ""), float(c.get("pos", 0) or 0))
        nc.update(
            desc=c.get("desc") or "", labels=[label_map[x] for x in c.get("idLabels", []) if x in label_map],
            members=[member_map[x] for x in c.get("idMembers", []) if x in member_map],
            due=_iso(c.get("due")), start=_iso(c.get("start")), due_done=bool(c.get("dueComplete")),
            closed=bool(c.get("closed")), checklists=checklists.get(c["id"], []),
            comments=comments.get(c["id"], []),
            attachments=[{"id": new_id(), "name": a.get("name") or a.get("url", ""), "url": a.get("url", ""),
                          "added": _iso(a.get("date"))} for a in c.get("attachments", [])],
        )
        cover = c.get("cover") or {}
        if cover.get("color"):
            nc["cover"] = {"color": cover["color"], "size": cover.get("size") or "normal"}
        for item in c.get("customFieldItems", []):
            fid, options = field_map.get(item.get("idCustomField"), (None, {}))
            if not fid:
                continue
            v = item.get("value") or {}
            nc["fields"][fid] = options.get(item.get("idValue")) if item.get("idValue") else \
                v.get("text") or v.get("number") or _iso(v.get("date")) or (v.get("checked") == "true")
        b["cards"].append(nc)
        card_count += 1
    b["activity"] = [{"ts": now_iso(), "who": "Я", "text": f"импортировал(а) доску из Trello: {len(b['lists'])} "
                      f"списков, {card_count} карточек", "card": None}]
    return b


def export_json(board):
    return json.dumps(board.d, ensure_ascii=False, indent=1)


def export_csv(board):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Карточка", "Список", "Метки", "Участники", "Начало", "Срок", "Выполнено", "Чек-лист", "Описание",
                "В архиве"])
    for c in board.cards() + board.cards(closed=True):
        lst = board.list(c["list"])
        done, total = board.checklist_progress(c)
        w.writerow([c["title"], lst["name"] if lst else "",
                    ", ".join((board.label(x)["name"] or board.label(x)["color"]) for x in c["labels"] if board.label(x)),
                    ", ".join(board.member(x)["name"] for x in c["members"] if board.member(x)),
                    c.get("start", ""), c.get("due", ""), "да" if c.get("due_done") else "",
                    f"{done}/{total}" if total else "", c.get("desc", ""), "да" if c.get("closed") else ""])
    return buf.getvalue()


def export_markdown(board):
    out = [f"# {board.name}", ""]
    if board.d.get("desc"):
        out += [board.d["desc"], ""]
    for lst in board.lists():
        out.append(f"## {lst['name']}")
        for c in board.cards(lst["id"]):
            mark = "x" if c.get("due_done") else " "
            extra = []
            if c.get("due"):
                extra.append("срок " + fmt_dt(c["due"]))
            labels = [board.label(x)["name"] for x in c["labels"] if board.label(x) and board.label(x)["name"]]
            if labels:
                extra.append(", ".join(labels))
            out.append(f"- [{mark}] {c['title']}" + (f" — {'; '.join(extra)}" if extra else ""))
            for cl in c["checklists"]:
                for it in cl["items"]:
                    out.append(f"  - [{'x' if it['done'] else ' '}] {it['text']}")
        out.append("")
    return "\n".join(out)


# ---- templates

TEMPLATES = {
    "Канбан": dict(bg="terracotta", lists=["Идеи", "Нужно сделать", "В работе", "На проверке", "Готово"],
                   labels=[("Срочно", "red"), ("Важно", "orange"), ("Баг", "purple"), ("Улучшение", "blue"),
                           ("Готово", "green")],
                   cards={"Нужно сделать": ["Добро пожаловать в Альфу 👋", "Перетащите эту карточку в «В работе»"],
                          "В работе": ["Откройте карточку — там описание, чек-лист и сроки"],
                          "Готово": ["Карточки в «Готово» отмечаются выполненными автоматически"]}),
    "Учёба": dict(bg="ocean", lists=["Предметы", "Задания", "Делаю", "Сдано"],
                  labels=[("Экзамен", "red"), ("Домашка", "blue"), ("Проект", "purple"), ("Сдано", "green")],
                  cards={"Задания": ["Реферат", "Лабораторная №1"], "Предметы": ["Математика", "Физика"]}),
    "Спринт": dict(bg="plum", lists=["Бэклог", "Спринт", "В работе", "Ревью", "Готово"],
                   labels=[("Фича", "blue"), ("Баг", "red"), ("Техдолг", "black"), ("Дизайн", "pink"),
                           ("Готово", "green")],
                   cards={"Бэклог": ["Пользовательская история", "Исследование"]}),
    "Личные дела": dict(bg="forest", lists=["Входящие", "Сегодня", "На неделе", "Когда-нибудь", "Сделано"],
                        labels=[("Дом", "green"), ("Работа", "blue"), ("Здоровье", "red"), ("Покупки", "yellow")],
                        cards={"Входящие": ["Купить продукты", "Записаться к врачу"]}),
    "Контент-план": dict(bg="rose", lists=["Идеи", "Сценарий", "Съёмка", "Монтаж", "Опубликовано"],
                         labels=[("YouTube", "red"), ("TikTok", "black"), ("Стрим", "purple"), ("Пост", "sky")],
                         cards={"Идеи": ["Новый ролик"]}),
    "Пустая": dict(bg="ivory", lists=["Нужно сделать", "В работе", "Готово"], labels=[], cards={}),
}


def from_template(name, title=None):
    t = TEMPLATES[name]
    b = empty_board(title or name, t["bg"])
    if t["labels"]:
        b["labels"] = [{"id": new_id(), "name": n, "color": c} for n, c in t["labels"]]
    ids = {}
    for i, ln in enumerate(t["lists"]):
        lid = new_id()
        ids[ln] = lid
        b["lists"].append({"id": lid, "name": ln, "pos": (i + 1) * 65536.0, "closed": False, "wip": 0, "color": ""})
    for ln, titles in t["cards"].items():
        for j, title_ in enumerate(titles):
            b["cards"].append(new_card(ids[ln], title_, (j + 1) * 65536.0))
    if name == "Канбан":
        welcome = b["cards"][0]
        welcome["desc"] = ("Альфа — локальная доска в духе Trello.\n\n"
                           "* **Перетаскивайте** карточки между списками и сами списки за заголовок.\n"
                           "* **Щелчок** по карточке открывает её: метки, участники, сроки, чек-листы, вложения, "
                           "обложка, поля, комментарии.\n"
                           "* **Автоматизация** (⚡ вверху) — правила, кнопки, команды по расписанию и по срокам.\n"
                           "* Горячие клавиши: N — новая карточка, F — фильтр, ⌘F — поиск, ⌘Z — отменить.")
        welcome["checklists"] = [{"id": new_id(), "name": "Первые шаги", "items": [
            {"id": new_id(), "text": t_, "done": False, "due": "", "member": ""}
            for t_ in ("Создать свою доску", "Добавить метку", "Настроить правило автоматизации")]}]
    lists = b["lists"]
    last = lists[-1]["id"]
    done_label = next((x["id"] for x in b["labels"] if x["color"] == "green"), None)
    if len(lists) >= 3:
        b["rules"] = [
            new_rule(trigger={"type": "card_moved", "list": last},
                     actions=[{"type": "mark_done"}] + ([{"type": "add_label", "label": done_label}]
                                                        if done_label else [])),
            new_rule(kind="card_button", name="Готово", icon="check",
                     actions=[{"type": "move", "list": last, "where": "top"}]),
            new_rule(kind="board_button", name="Архивировать готовое", icon="archive",
                     actions=[{"type": "archive_list", "list": last}]),
        ]
    return b
