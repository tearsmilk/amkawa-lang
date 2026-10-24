"""Boards, lists and cards as plain JSON-able dicts, wrapped by `Board` with Trello-like operations.

* Order is a float `pos` (like Trello): moving between two cards takes the middle value, no renumbering.
* Every mutating operation goes through `Board.change(...)`: an undo snapshot, an activity entry, an event for
  automation (`Board.listeners`), and a debounced save by the owner (`Store`).
* Dates are ISO strings "YYYY-MM-DDTHH:MM" in local time (no time zone games for a local app)."""
import copy
import json
import os
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from .paths import data_dir

FIELD_TYPES = {"text": "Текст", "number": "Число", "date": "Дата", "checkbox": "Флажок", "list": "Список"}


def new_id():
    return uuid.uuid4().hex[:12]


def now_iso():
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s[:16])
    except ValueError:
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
        except ValueError:
            return None


def fmt_dt(s, with_time=True):
    d = parse_dt(s)
    if not d:
        return ""
    months = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
    out = f"{d.day} {months[d.month - 1]}"
    if d.year != datetime.now().year:
        out += f" {d.year}"
    if with_time and (d.hour or d.minute):
        out += f", {d.hour}:{d.minute:02d}"
    return out


def due_state(card, now=None):
    """'done' | 'overdue' | 'soon' (≤ 24 h) | 'later' | None."""
    d = parse_dt(card.get("due"))
    if not d:
        return None
    if card.get("due_done"):
        return "done"
    now = now or datetime.now()
    if d < now:
        return "overdue"
    if d - now <= timedelta(hours=24):
        return "soon"
    return "later"


def initials(name):
    parts = [p for p in name.replace("_", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def empty_board(name="Новая доска", bg="terracotta"):
    return {
        "id": new_id(), "name": name, "desc": "", "bg": bg, "starred": False, "closed": False,
        "created": now_iso(), "opened": time.time(), "template": False,
        "lists": [], "cards": [],
        "labels": [{"id": new_id(), "name": "", "color": c} for c in ("green", "yellow", "orange", "red", "purple",
                                                                       "blue")],
        "members": [{"id": "me", "name": "Я", "initials": "Я", "color": "#D97757"}],
        "fields": [], "rules": [], "buttons": [], "activity": [],
        "prefs": {"covers": True, "show_done": True},
    }


def new_card(list_id, title, pos):
    return {
        "id": new_id(), "list": list_id, "pos": pos, "title": title, "desc": "", "labels": [], "members": [],
        "start": "", "due": "", "due_done": False, "reminder": 0, "checklists": [], "attachments": [],
        "cover": None, "comments": [], "fields": {}, "closed": False, "created": now_iso(), "template": False,
        "votes": 0,
    }


class Board:
    """A board dict plus operations. `listeners` get (board, event, payload) after each change."""

    UNDO_LIMIT = 100

    def __init__(self, data):
        self.d = data
        for k, v in empty_board().items():
            self.d.setdefault(k, copy.deepcopy(v) if k not in ("id", "created") else v)
        self.undo_stack = []
        self.redo_stack = []
        self.listeners = []
        self.dirty = False
        self._depth = 0          # nested changes (automation acting inside a change)
        self.actor = "Я"         # who is acting: "Я" or "Автоматизация"

    # -- basic accessors
    @property
    def id(self):
        return self.d["id"]

    @property
    def name(self):
        return self.d["name"]

    def lists(self, closed=False):
        return sorted((x for x in self.d["lists"] if bool(x.get("closed")) == closed), key=lambda x: x["pos"])

    def list(self, lid):
        return next((x for x in self.d["lists"] if x["id"] == lid), None)

    def list_by_name(self, name):
        name = (name or "").strip().lower()
        return next((x for x in self.lists() if x["name"].strip().lower() == name), None)

    def cards(self, list_id=None, closed=False):
        cs = [c for c in self.d["cards"] if bool(c.get("closed")) == closed and (list_id is None or c["list"] == list_id)]
        return sorted(cs, key=lambda c: c["pos"])

    def card(self, cid):
        return next((c for c in self.d["cards"] if c["id"] == cid), None)

    def label(self, lid):
        return next((x for x in self.d["labels"] if x["id"] == lid), None)

    def label_by(self, text):
        """Label by name, or by colour key when the name is empty."""
        t = (text or "").strip().lower()
        return next((x for x in self.d["labels"] if (x["name"].strip().lower() == t and t) or
                     (not x["name"] and x["color"] == t)), None)

    def member(self, mid):
        return next((m for m in self.d["members"] if m["id"] == mid), None)

    def field(self, fid):
        return next((f for f in self.d["fields"] if f["id"] == fid), None)

    # -- change machinery
    def snapshot(self):
        return json.dumps(self.d, ensure_ascii=False)

    def _begin(self):
        if self._depth == 0:
            self.undo_stack.append(self.snapshot())
            del self.undo_stack[:-self.UNDO_LIMIT]
            self.redo_stack.clear()
        self._depth += 1

    def _end(self, text, event, payload, more=()):
        """Finish a change: log, mark dirty, notify listeners (automation runs inside the same undo step)."""
        if text:
            self.log(text, payload.get("card"))
        self.dirty = True
        try:
            events = ([(event, payload)] if event else []) + list(more)
            for ev, pl in events:
                for fn in list(self.listeners):
                    fn(self, ev, pl)
        finally:
            self._depth -= 1

    def log(self, text, card_id=None):
        self.d["activity"].insert(0, {"ts": now_iso(), "who": self.actor, "text": text, "card": card_id})
        del self.d["activity"][500:]

    def undo(self):
        if not self.undo_stack:
            return False
        self.redo_stack.append(self.snapshot())
        self.d.clear()
        self.d.update(json.loads(self.undo_stack.pop()))
        self.dirty = True
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        self.undo_stack.append(self.snapshot())
        self.d.clear()
        self.d.update(json.loads(self.redo_stack.pop()))
        self.dirty = True
        return True

    def touch(self, text="", event=None, **payload):
        """Generic mutation wrapper for simple edits done by the caller: board.touch() before, then edit."""
        self._begin()
        self._end(text, event, payload)

    # -- positions
    @staticmethod
    def _pos_between(before, after):
        if before is None and after is None:
            return 65536.0
        if before is None:
            return after / 2.0
        if after is None:
            return before + 65536.0
        return (before + after) / 2.0

    def _pos_at(self, items, index, exclude=None):
        items = [x for x in items if x["id"] != exclude]
        index = max(0, min(index, len(items)))
        before = items[index - 1]["pos"] if index > 0 else None
        after = items[index]["pos"] if index < len(items) else None
        pos = self._pos_between(before, after)
        if before is not None and after is not None and abs(after - before) < 1e-6:
            for i, x in enumerate(items):   # renumber when the gap gets too small
                x["pos"] = (i + 1) * 65536.0
            return self._pos_at(items, index)
        return pos

    # -- lists
    def add_list(self, name, index=None):
        self._begin()
        lists = self.lists()
        lst = {"id": new_id(), "name": name, "pos": self._pos_at(lists, len(lists) if index is None else index),
               "closed": False, "wip": 0, "color": ""}
        self.d["lists"].append(lst)
        self._end(f"добавил(а) список «{name}»", "list_created", {"list": lst["id"]})
        return lst

    def rename_list(self, lid, name):
        lst = self.list(lid)
        if not lst or lst["name"] == name:
            return
        self._begin()
        old, lst["name"] = lst["name"], name
        self._end(f"переименовал(а) список «{old}» в «{name}»", None, {"list": lid})

    def move_list(self, lid, index, board=None):
        lst = self.list(lid)
        if not lst:
            return
        self._begin()
        lst["pos"] = self._pos_at(self.lists(), index, exclude=lid)
        self._end("", None, {"list": lid})

    def set_list(self, lid, **kw):
        lst = self.list(lid)
        if not lst:
            return
        self._begin()
        lst.update(kw)
        text = ""
        if "closed" in kw:
            text = f"{'архивировал(а)' if kw['closed'] else 'вернул(а) из архива'} список «{lst['name']}»"
        self._end(text, None, {"list": lid})

    def copy_list(self, lid, name=None):
        src = self.list(lid)
        if not src:
            return None
        self._begin()
        lists = self.lists()
        idx = next(i for i, x in enumerate(lists) if x["id"] == lid) + 1
        lst = dict(src, id=new_id(), name=name or src["name"], pos=self._pos_at(lists, idx))
        self.d["lists"].append(lst)
        for c in self.cards(lid):
            nc = copy.deepcopy(c)
            nc.update(id=new_id(), list=lst["id"], comments=[], created=now_iso())
            self.d["cards"].append(nc)
        self._end(f"скопировал(а) список «{src['name']}»", "list_created", {"list": lst["id"]})
        return lst

    def move_all_cards(self, src, dst):
        cards = self.cards(src)
        if not cards or src == dst:
            return
        self._begin()
        target = self.cards(dst)
        top = target[-1]["pos"] if target else 0.0
        for i, c in enumerate(cards):
            c["list"] = dst
            c["pos"] = top + (i + 1) * 65536.0
        self._end(f"переместил(а) все карточки из «{self.list(src)['name']}» в «{self.list(dst)['name']}»", None,
                  {"list": dst}, [("card_moved", {"card": c["id"], "list": dst, "from": src}) for c in cards])

    def archive_all_cards(self, lid):
        cards = self.cards(lid)
        if not cards:
            return
        self._begin()
        for c in cards:
            c["closed"] = True
        self._end(f"архивировал(а) все карточки списка «{self.list(lid)['name']}»", None, {"list": lid})

    def sort_list(self, lid, key="title", reverse=False):
        cards = self.cards(lid)
        if not cards:
            return
        self._begin()
        keys = {
            "title": lambda c: c["title"].lower(),
            "due": lambda c: (not c.get("due"), c.get("due") or ""),
            "created": lambda c: c.get("created") or "",
            "votes": lambda c: -int(c.get("votes", 0)),
        }
        for i, c in enumerate(sorted(cards, key=keys.get(key, keys["title"]), reverse=reverse)):
            c["pos"] = (i + 1) * 65536.0
        self._end("", None, {"list": lid})

    # -- cards
    def add_card(self, lid, title, index=None, **fields):
        self._begin()
        cards = self.cards(lid)
        c = new_card(lid, title, self._pos_at(cards, len(cards) if index is None else index))
        c.update(fields)
        self.d["cards"].append(c)
        self._end(f"добавил(а) карточку «{title}» в «{self.list(lid)['name']}»", "card_created",
                  {"card": c["id"], "list": lid})
        return c

    def move_card(self, cid, lid, index=None, board=None):
        """Move within / between lists (index None = bottom)."""
        c = self.card(cid)
        if not c:
            return
        src = c["list"]
        target = self.cards(lid)
        idx = len([x for x in target if x["id"] != cid]) if index is None else index
        self._begin()
        c["list"] = lid
        c["pos"] = self._pos_at(target, idx, exclude=cid)
        text = ""
        if src != lid:
            text = f"переместил(а) «{c['title']}» из «{self.list(src)['name']}» в «{self.list(lid)['name']}»"
        self._end(text, "card_moved" if src != lid else None, {"card": cid, "list": lid, "from": src})

    def update_card(self, cid, text=None, **kw):
        """Generic field update with the right automation events."""
        c = self.card(cid)
        if not c:
            return
        self._begin()
        events = []
        before = copy.deepcopy(c)
        c.update(kw)
        if "labels" in kw:
            for lb in set(kw["labels"]) - set(before["labels"]):
                events.append(("label_added", {"label": lb}))
            for lb in set(before["labels"]) - set(kw["labels"]):
                events.append(("label_removed", {"label": lb}))
        if "members" in kw:
            for m in set(kw["members"]) - set(before["members"]):
                events.append(("member_added", {"member": m}))
        if "due_done" in kw and kw["due_done"] != before.get("due_done"):
            events.append(("card_done" if kw["due_done"] else "card_undone", {}))
        if "due" in kw and kw["due"] != before.get("due"):
            events.append(("due_set", {}))
        if "closed" in kw and kw["closed"] != before.get("closed"):
            events.append(("card_archived" if kw["closed"] else "card_restored", {}))
        if text is None:
            text = self._describe(before, c)
        self._end(text, None, {"card": cid}, [(ev, dict({"card": cid, "list": c["list"]}, **extra))
                                               for ev, extra in events])

    def _describe(self, before, c):
        t = c["title"]
        if before["title"] != c["title"]:
            return f"переименовал(а) «{before['title']}» в «{t}»"
        if before.get("closed") != c.get("closed"):
            return f"{'архивировал(а)' if c['closed'] else 'вернул(а) из архива'} «{t}»"
        if before.get("due_done") != c.get("due_done"):
            return f"отметил(а) «{t}» как {'выполненную' if c['due_done'] else 'невыполненную'}"
        if before.get("due") != c.get("due"):
            return f"{'установил(а) срок ' + fmt_dt(c['due']) if c['due'] else 'убрал(а) срок'} для «{t}»"
        if before["labels"] != c["labels"]:
            return f"изменил(а) метки «{t}»"
        if before["members"] != c["members"]:
            return f"изменил(а) участников «{t}»"
        if before["desc"] != c["desc"]:
            return f"изменил(а) описание «{t}»"
        return ""

    def toggle_label(self, cid, label_id):
        c = self.card(cid)
        labels = list(c["labels"])
        labels.remove(label_id) if label_id in labels else labels.append(label_id)
        self.update_card(cid, labels=labels)

    def toggle_member(self, cid, member_id):
        c = self.card(cid)
        ms = list(c["members"])
        ms.remove(member_id) if member_id in ms else ms.append(member_id)
        self.update_card(cid, members=ms)

    def copy_card(self, cid, lid=None, index=None, title=None, keep=("labels", "members", "checklists",
                                                                     "attachments", "desc", "due", "fields")):
        src = self.card(cid)
        if not src:
            return None
        lid = lid or src["list"]
        cards = self.cards(lid)
        if index is None:
            index = next((i + 1 for i, x in enumerate(cards) if x["id"] == cid), len(cards))
        self._begin()
        c = new_card(lid, title or src["title"], self._pos_at(cards, index))
        for k in keep:
            c[k] = copy.deepcopy(src.get(k))
        for cl in c["checklists"]:
            cl["id"] = new_id()
            for it in cl["items"]:
                it["id"] = new_id()
        c["cover"] = copy.deepcopy(src.get("cover"))
        self.d["cards"].append(c)
        self._end(f"скопировал(а) «{src['title']}»", "card_created", {"card": c["id"], "list": lid})
        return c

    def delete_card(self, cid):
        c = self.card(cid)
        if not c:
            return
        self._begin()
        self.d["cards"].remove(c)
        self._end(f"удалил(а) карточку «{c['title']}»", None, {})

    # -- checklists
    def add_checklist(self, cid, name="Чек-лист", items=()):
        c = self.card(cid)
        self._begin()
        cl = {"id": new_id(), "name": name, "items": [{"id": new_id(), "text": t, "done": False, "due": "",
                                                      "member": ""} for t in items]}
        c["checklists"].append(cl)
        self._end(f"добавил(а) чек-лист «{name}» в «{c['title']}»", None, {"card": cid})
        return cl

    def checklist(self, cid, clid):
        c = self.card(cid)
        return next((x for x in c["checklists"] if x["id"] == clid), None) if c else None

    def add_item(self, cid, clid, text):
        cl = self.checklist(cid, clid)
        self._begin()
        it = {"id": new_id(), "text": text, "done": False, "due": "", "member": ""}
        cl["items"].append(it)
        self._end("", None, {"card": cid})
        return it

    def set_item(self, cid, clid, iid, **kw):
        cl = self.checklist(cid, clid)
        it = next((x for x in cl["items"] if x["id"] == iid), None)
        if not it:
            return
        self._begin()
        was_done = all(x["done"] for x in cl["items"])
        it.update(kw)
        text = ""
        if "done" in kw:
            text = f"{'выполнил(а)' if kw['done'] else 'снял(а) отметку'} «{it['text']}» в «{self.card(cid)['title']}»"
        complete = bool(cl["items"]) and all(x["done"] for x in cl["items"])
        pl = {"card": cid, "list": self.card(cid)["list"]}
        self._end(text, "item_checked" if kw.get("done") else None, pl,
                  [("checklist_done", dict(pl, checklist=clid))] if complete and not was_done else [])

    def remove_item(self, cid, clid, iid):
        cl = self.checklist(cid, clid)
        self._begin()
        cl["items"] = [x for x in cl["items"] if x["id"] != iid]
        self._end("", None, {"card": cid})

    def remove_checklist(self, cid, clid):
        c = self.card(cid)
        self._begin()
        c["checklists"] = [x for x in c["checklists"] if x["id"] != clid]
        self._end("", None, {"card": cid})

    def checklist_progress(self, card):
        items = [it for cl in card.get("checklists", []) for it in cl["items"]]
        return sum(1 for it in items if it["done"]), len(items)

    # -- comments, attachments
    def add_comment(self, cid, text):
        c = self.card(cid)
        self._begin()
        cm = {"id": new_id(), "text": text, "ts": now_iso(), "who": self.actor}
        c["comments"].insert(0, cm)
        self._end(f"прокомментировал(а) «{c['title']}»", "comment_added", {"card": cid, "list": c["list"],
                                                                          "text": text})
        return cm

    def add_attachment(self, cid, path_or_url, name=None):
        c = self.card(cid)
        self._begin()
        is_url = "://" in path_or_url
        att = {"id": new_id(), "name": name or (path_or_url if is_url else Path(path_or_url).name),
               "url": path_or_url, "added": now_iso()}
        c["attachments"].append(att)
        if not c.get("cover") and not is_url and Path(path_or_url).suffix.lower() in (".png", ".jpg", ".jpeg",
                                                                                     ".gif", ".webp", ".bmp"):
            if self.d["prefs"].get("covers", True):
                c["cover"] = {"attachment": att["id"], "size": "normal"}
        self._end(f"прикрепил(а) «{att['name']}» к «{c['title']}»", "attachment_added", {"card": cid,
                                                                                        "list": c["list"]})
        return att

    # -- board level
    def set_board(self, **kw):
        self._begin()
        self.d.update(kw)
        self._end("", None, {})

    def add_label(self, name, color):
        self._begin()
        lb = {"id": new_id(), "name": name, "color": color}
        self.d["labels"].append(lb)
        self._end("", None, {})
        return lb

    def remove_label(self, lid):
        self._begin()
        self.d["labels"] = [x for x in self.d["labels"] if x["id"] != lid]
        for c in self.d["cards"]:
            if lid in c["labels"]:
                c["labels"].remove(lid)
        self._end("", None, {})

    def add_member(self, name, color="#5B8CC4"):
        self._begin()
        m = {"id": new_id(), "name": name, "initials": initials(name), "color": color}
        self.d["members"].append(m)
        self._end(f"добавил(а) участника {name}", None, {})
        return m

    def add_field(self, name, ftype="text", options=()):
        self._begin()
        f = {"id": new_id(), "name": name, "type": ftype, "options": list(options), "on_front": True}
        self.d["fields"].append(f)
        self._end("", None, {})
        return f

    # -- search / filter
    def matches(self, card, flt):
        """flt: {"text", "labels": set, "members": set, "due": "" | overdue | today | week | none | done,
        "done": None | True | False}."""
        if not flt:
            return True
        t = (flt.get("text") or "").strip().lower()
        if t:
            hay = " ".join([card["title"], card.get("desc", "")] +
                           [self.label(x)["name"] for x in card["labels"] if self.label(x)] +
                           [it["text"] for cl in card["checklists"] for it in cl["items"]]).lower()
            if not all(w in hay for w in t.split()):
                return False
        if flt.get("labels") and not set(flt["labels"]) & set(card["labels"]):
            return False
        if flt.get("members") and not set(flt["members"]) & set(card["members"]):
            return False
        due = flt.get("due") or ""
        if due:
            d = parse_dt(card.get("due"))
            now = datetime.now()
            if due == "none" and d:
                return False
            if due != "none" and not d:
                return False
            if due == "overdue" and (card.get("due_done") or d >= now):
                return False
            if due == "today" and d.date() != now.date():
                return False
            if due == "week" and not (now - timedelta(days=1) <= d <= now + timedelta(days=7)):
                return False
        if flt.get("done") is not None and bool(card.get("due_done")) != flt["done"]:
            return False
        return True

    def stats(self):
        cards = self.cards()
        out = {"total": len(cards), "lists": {}, "labels": {}, "members": {}, "due": {}}
        for lst in self.lists():
            out["lists"][lst["name"]] = len(self.cards(lst["id"]))
        for lb in self.d["labels"]:
            out["labels"][lb["name"] or lb["color"]] = sum(1 for c in cards if lb["id"] in c["labels"])
        for m in self.d["members"]:
            out["members"][m["name"]] = sum(1 for c in cards if m["id"] in c["members"])
        names = {"done": "Выполнено", "overdue": "Просрочено", "soon": "Скоро", "later": "Позже", None: "Без срока"}
        for c in cards:
            k = names[due_state(c)]
            out["due"][k] = out["due"].get(k, 0) + 1
        return out


class Store:
    """All boards in <data>/boards/<id>.json (written atomically)."""

    def __init__(self, folder=None):
        self.folder = Path(folder) if folder else data_dir() / "boards"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.boards = {}
        for f in sorted(self.folder.glob("*.json")):
            try:
                d = json.loads(f.read_text("utf-8"))
                self.boards[d["id"]] = Board(d)
            except Exception:
                continue

    def all(self, closed=False, templates=None):
        bs = [b for b in self.boards.values() if bool(b.d.get("closed")) == closed]
        if templates is not None:
            bs = [b for b in bs if bool(b.d.get("template")) == templates]
        return sorted(bs, key=lambda b: (-float(b.d.get("opened", 0)), b.name))

    def add(self, data):
        b = Board(data)
        self.boards[b.id] = b
        b.dirty = True
        self.save(b)
        return b

    def save(self, board=None):
        for b in [board] if board else list(self.boards.values()):
            if not b.dirty:
                continue
            path = self.folder / f"{b.id}.json"
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(b.d, ensure_ascii=False, indent=1), "utf-8")
            os.replace(tmp, path)
            b.dirty = False

    def delete(self, board_id):
        b = self.boards.pop(board_id, None)
        if b:
            (self.folder / f"{board_id}.json").unlink(missing_ok=True)

    def copy_board(self, board, name=None, keep_cards=True):
        d = json.loads(board.snapshot())
        d["id"] = new_id()
        d["name"] = name or board.name + " (копия)"
        d["starred"] = False
        d["template"] = False
        d["activity"] = []
        d["created"] = now_iso()
        if not keep_cards:
            d["cards"] = []
        list_map = {}
        for lst in d["lists"]:
            list_map[lst["id"]] = new_id()
            lst["id"] = list_map[lst["id"]]
        for c in d["cards"]:
            c["id"] = new_id()
            c["list"] = list_map.get(c["list"], c["list"])
            c["comments"] = []
        for r in d.get("rules", []) + d.get("buttons", []):
            r["id"] = new_id()
            _remap(r, list_map)
        return self.add(d)


def _remap(obj, mapping):
    """Replace list ids inside rule/button params after copying a board."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and v in mapping:
                obj[k] = mapping[v]
            else:
                _remap(v, mapping)
    elif isinstance(obj, list):
        for v in obj:
            _remap(v, mapping)
