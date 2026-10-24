"""Butler-like automation: rules (trigger → conditions → actions), card buttons, board buttons, scheduled commands
and due-date commands. Rules live in board["rules"]; buttons in board["buttons"].

Rule = {"id", "kind": "rule" | "schedule" | "due" | "card_button" | "board_button", "name", "enabled",
        "trigger": {...}, "conditions": [{...}], "actions": [{...}], "runs": int, "last": iso, "created": iso}

Everything an action does goes through `Board` operations, so it is logged ("Автоматизация …"), undoable together
with the user's change that triggered it, and can trigger further rules (limited depth, no loops)."""
import calendar
import copy
from datetime import datetime, timedelta

from .model import fmt_dt, new_id, now_iso, parse_dt

# ---- vocabulary (also drives the editor UI): key → (title, params)
# param kinds: list, label, member, text, int, time, weekday, monthday, field, color, where, sortkey, items, unit, when
TRIGGERS = {
    "card_created": ("карточка добавлена в список", [("list", "list?")]),
    "card_moved": ("карточка перемещена в список", [("list", "list?"), ("from", "list?")]),
    "label_added": ("на карточку добавлена метка", [("label", "label")]),
    "label_removed": ("с карточки снята метка", [("label", "label")]),
    "member_added": ("на карточку добавлен участник", [("member", "member")]),
    "card_done": ("срок карточки отмечен выполненным", []),
    "card_undone": ("отметка выполнения снята", []),
    "checklist_done": ("все пункты чек-листа выполнены", []),
    "item_checked": ("выполнен пункт чек-листа", []),
    "comment_added": ("добавлен комментарий", [("contains", "text?")]),
    "attachment_added": ("к карточке прикреплён файл", []),
    "due_set": ("у карточки установлен срок", []),
    "card_archived": ("карточка архивирована", []),
}
SCHEDULES = {
    "daily": ("каждый день", [("time", "time")]),
    "weekdays": ("каждый будний день", [("time", "time")]),
    "weekly": ("каждую неделю", [("day", "weekday"), ("time", "time")]),
    "monthly": ("каждый месяц", [("day", "monthday"), ("time", "time")]),
}
DUE_WHEN = {"before": "до срока", "after": "после срока", "on": "в момент срока"}
CONDITIONS = {
    "in_list": ("в списке", [("list", "list")]),
    "not_in_list": ("не в списке", [("list", "list")]),
    "has_label": ("с меткой", [("label", "label")]),
    "no_label": ("без метки", [("label", "label")]),
    "has_member": ("с участником", [("member", "member")]),
    "title_contains": ("название содержит", [("text", "text")]),
    "has_due": ("со сроком", []),
    "no_due": ("без срока", []),
    "overdue": ("просрочена", []),
    "is_done": ("выполнена", []),
    "not_done": ("не выполнена", []),
    "checklist_complete": ("все чек-листы выполнены", []),
}
ACTIONS = {
    "move": ("переместить в список", [("list", "list"), ("where", "where")]),
    "copy": ("скопировать в список", [("list", "list")]),
    "add_label": ("добавить метку", [("label", "label")]),
    "remove_label": ("снять метку", [("label", "label")]),
    "clear_labels": ("снять все метки", []),
    "add_member": ("добавить участника", [("member", "member")]),
    "remove_member": ("убрать участника", [("member", "member")]),
    "set_due": ("установить срок через N дней", [("days", "int"), ("time", "time")]),
    "clear_due": ("убрать срок", []),
    "mark_done": ("отметить выполненной", []),
    "mark_undone": ("снять отметку выполнения", []),
    "add_checklist": ("добавить чек-лист", [("name", "text"), ("items", "items")]),
    "check_all": ("отметить все пункты чек-листов", []),
    "comment": ("написать комментарий", [("text", "text")]),
    "rename": ("переименовать", [("title", "text")]),
    "set_cover": ("сделать обложку цветом", [("color", "color")]),
    "set_field": ("заполнить поле", [("field", "field"), ("value", "text")]),
    "vote": ("добавить голос", []),
    "archive": ("архивировать", []),
}
BOARD_ACTIONS = {
    "create_card": ("создать карточку", [("list", "list"), ("title", "text")]),
    "sort_list": ("отсортировать список", [("list", "list"), ("key", "sortkey")]),
    "move_all": ("переместить все карточки", [("from", "list"), ("list", "list")]),
    "archive_list": ("архивировать все карточки списка", [("list", "list")]),
}
SORT_KEYS = {"title": "по названию", "due": "по сроку", "created": "по дате создания", "votes": "по голосам"}
WEEKDAYS = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]
MAX_DEPTH = 5


def new_rule(kind="rule", **kw):
    r = {"id": new_id(), "kind": kind, "name": "", "enabled": True, "trigger": {}, "conditions": [], "actions": [],
         "runs": 0, "last": "", "created": now_iso(), "fired": {}, "icon": "auto"}
    r.update(kw)
    return r


# ---- describing rules in Russian

def _name(board, kind, value):
    if not value:
        return "любой" if kind in ("list?",) else "—"
    if kind.startswith("list"):
        lst = board.list(value)
        return f"«{lst['name']}»" if lst else "(список удалён)"
    if kind == "label":
        lb = board.label(value)
        from .theme import LABEL_COLORS

        return f"«{lb['name'] or LABEL_COLORS.get(lb['color'], ('', lb['color']))[1].lower()}»" if lb else "(метка удалена)"
    if kind == "member":
        m = board.member(value)
        return m["name"] if m else "(участник удалён)"
    if kind == "field":
        f = board.field(value)
        return f"«{f['name']}»" if f else "(поле удалено)"
    if kind == "weekday":
        return WEEKDAYS[int(value) % 7]
    if kind == "color":
        from .theme import LABEL_COLORS

        return "без обложки" if value == "none" else LABEL_COLORS.get(value, ("", value))[1].lower()
    if kind == "sortkey":
        return SORT_KEYS.get(value, value)
    if kind == "where":
        return "наверх" if value == "top" else "вниз"
    if kind == "items":
        return ", ".join(value) if isinstance(value, list) else str(value)
    if kind.startswith("text"):
        return f"«{value}»"
    return str(value)


def _phrase(board, vocab, item):
    title, params = vocab.get(item.get("type"), ("?", []))
    parts = [title]
    for key, kind in params:
        v = item.get(key)
        if key == "from" and not v:
            continue
        if kind.endswith("?") and not v:
            if key == "list":
                parts[0] = title.replace(" в список", "").replace(" список", "")
            continue
        if key == "from":
            parts.append(f"из {_name(board, kind, v)}")
        elif kind == "time":
            parts.append(f"в {v or '09:00'}")
        elif kind == "monthday":
            parts.append(f"{v}-го числа")
        elif kind == "int" and key == "days":
            parts[0] = title.replace("через N дней", f"через {v} дн.")
        else:
            parts.append(_name(board, kind, v))
    return " ".join(parts)


def describe(board, rule):
    kind = rule.get("kind", "rule")
    tr = rule.get("trigger", {})
    if kind == "rule":
        head = "Когда " + _phrase(board, TRIGGERS, tr)
    elif kind == "schedule":
        t = tr.get("type", "daily")
        if t == "weekly":
            head = f"Каждую неделю в {WEEKDAYS[int(tr.get('day', 0)) % 7]} в {tr.get('time', '09:00')}"
        elif t == "monthly":
            head = f"Каждый месяц {tr.get('day', 1)}-го числа в {tr.get('time', '09:00')}"
        else:
            head = f"{SCHEDULES.get(t, ('?',))[0].capitalize()} в {tr.get('time', '09:00')}"
    elif kind == "due":
        when = tr.get("when", "before")
        unit = {"hours": "ч", "days": "дн."}.get(tr.get("unit", "days"), "дн.")
        head = ("В момент срока карточки" if when == "on" else
                f"За {tr.get('amount', 1)} {unit} до срока карточки" if when == "before" else
                f"Через {tr.get('amount', 1)} {unit} после срока карточки")
    elif kind == "card_button":
        head = f"Кнопка карточки «{rule.get('name') or 'Без названия'}»"
    else:
        head = f"Кнопка доски «{rule.get('name') or 'Без названия'}»"
    conds = [_phrase(board, CONDITIONS, c) for c in rule.get("conditions", [])]
    if conds:
        scope = " для карточек " if kind in ("schedule", "board_button") else ", если карточка "
        head += scope + " и ".join(conds)
    acts = []
    for a in rule.get("actions", []):
        vocab = BOARD_ACTIONS if a.get("type") in BOARD_ACTIONS else ACTIONS
        acts.append(_phrase(board, vocab, a))
    return head + (": " + ", ".join(acts) if acts else ": (нет действий)")


# ---- engine

def check(board, card, conditions, now=None):
    now = now or datetime.now()
    for c in conditions or []:
        t = c.get("type")
        if t == "in_list" and card["list"] != c.get("list"):
            return False
        if t == "not_in_list" and card["list"] == c.get("list"):
            return False
        if t == "has_label" and c.get("label") not in card["labels"]:
            return False
        if t == "no_label" and c.get("label") in card["labels"]:
            return False
        if t == "has_member" and c.get("member") not in card["members"]:
            return False
        if t == "title_contains" and (c.get("text") or "").lower() not in card["title"].lower():
            return False
        if t == "has_due" and not card.get("due"):
            return False
        if t == "no_due" and card.get("due"):
            return False
        if t == "overdue":
            d = parse_dt(card.get("due"))
            if not d or card.get("due_done") or d >= now:
                return False
        if t == "is_done" and not card.get("due_done"):
            return False
        if t == "not_done" and card.get("due_done"):
            return False
        if t == "checklist_complete":
            done, total = board.checklist_progress(card)
            if not total or done < total:
                return False
    return True


def _fill(text, board, card):
    lst = board.list(card["list"]) if card else None
    return (text or "").replace("{title}", card["title"] if card else "").replace(
        "{list}", lst["name"] if lst else "").replace("{date}", fmt_dt(now_iso(), False)).replace(
        "{board}", board.name)


def run_card_actions(board, card, actions, now=None):
    now = now or datetime.now()
    cid = card["id"]
    for a in actions:
        card = board.card(cid)
        if card is None:
            return
        t = a.get("type")
        if t == "move" and board.list(a.get("list")):
            index = 0 if a.get("where") == "top" else None
            if card["list"] != a["list"] or index == 0:
                board.move_card(cid, a["list"], index)
        elif t == "copy" and board.list(a.get("list")):
            board.copy_card(cid, a["list"], len(board.cards(a["list"])))
        elif t == "add_label" and board.label(a.get("label")) and a["label"] not in card["labels"]:
            board.update_card(cid, labels=card["labels"] + [a["label"]])
        elif t == "remove_label" and a.get("label") in card["labels"]:
            board.update_card(cid, labels=[x for x in card["labels"] if x != a["label"]])
        elif t == "clear_labels" and card["labels"]:
            board.update_card(cid, labels=[])
        elif t == "add_member" and board.member(a.get("member")) and a["member"] not in card["members"]:
            board.update_card(cid, members=card["members"] + [a["member"]])
        elif t == "remove_member" and a.get("member") in card["members"]:
            board.update_card(cid, members=[x for x in card["members"] if x != a["member"]])
        elif t == "set_due":
            hh, mm = (a.get("time") or "18:00").split(":")[:2]
            d = (now + timedelta(days=int(a.get("days", 1) or 0))).replace(hour=int(hh), minute=int(mm), second=0,
                                                                         microsecond=0)
            board.update_card(cid, due=d.strftime("%Y-%m-%dT%H:%M"), due_done=False)
        elif t == "clear_due" and card.get("due"):
            board.update_card(cid, due="", due_done=False)
        elif t == "mark_done" and card.get("due_done") is not True:
            board.update_card(cid, due_done=True)
        elif t == "mark_undone" and card.get("due_done"):
            board.update_card(cid, due_done=False)
        elif t == "add_checklist":
            items = a.get("items") or []
            if isinstance(items, str):
                items = [x.strip() for x in items.split(",") if x.strip()]
            board.add_checklist(cid, a.get("name") or "Чек-лист", items)
        elif t == "check_all":
            for cl in card["checklists"]:
                for it in cl["items"]:
                    if not it["done"]:
                        board.set_item(cid, cl["id"], it["id"], done=True)
        elif t == "comment":
            board.add_comment(cid, _fill(a.get("text"), board, card))
        elif t == "rename" and a.get("title"):
            board.update_card(cid, title=_fill(a["title"], board, card))
        elif t == "set_cover":
            board.update_card(cid, cover={"color": a.get("color") or "red", "size": "normal"} if a.get("color") != "none"
                              else None)
        elif t == "set_field" and board.field(a.get("field")):
            fields = dict(card.get("fields") or {})
            fields[a["field"]] = a.get("value", "")
            board.update_card(cid, fields=fields, text=f"заполнил(а) поле «{board.field(a['field'])['name']}»")
        elif t == "vote":
            board.update_card(cid, votes=int(card.get("votes", 0)) + 1, text="")
        elif t == "archive" and not card.get("closed"):
            board.update_card(cid, closed=True)


def run_board_actions(board, rule, now=None):
    """Board-level actions + card actions for every card matching the conditions."""
    card_actions = [a for a in rule.get("actions", []) if a.get("type") in ACTIONS]
    for a in rule.get("actions", []):
        t = a.get("type")
        if t == "create_card" and board.list(a.get("list")):
            board.add_card(a["list"], _fill(a.get("title") or "Новая карточка", board, None))
        elif t == "sort_list" and board.list(a.get("list")):
            board.sort_list(a["list"], a.get("key") or "title")
        elif t == "move_all" and board.list(a.get("from")) and board.list(a.get("list")):
            board.move_all_cards(a["from"], a["list"])
        elif t == "archive_list" and board.list(a.get("list")):
            board.archive_all_cards(a["list"])
    affected = 0
    if card_actions:
        for card in list(board.cards()):
            if check(board, card, rule.get("conditions"), now):
                run_card_actions(board, card, card_actions, now)
                affected += 1
    return affected


class Automation:
    """Attach to boards; feeds events into rules; `tick()` runs scheduled and due-date commands."""

    def __init__(self):
        self.depth = 0
        self.on_run = None   # callback(board, rule, card or None)

    def attach(self, board):
        if self.on_event not in board.listeners:
            board.listeners.append(self.on_event)

    def _record(self, board, rule, card=None):
        rule["runs"] = int(rule.get("runs", 0)) + 1
        rule["last"] = now_iso()
        log = board.d.setdefault("autolog", [])
        log.insert(0, {"ts": now_iso(), "rule": rule["id"], "text": describe(board, rule),
                       "card": card["title"] if card else ""})
        del log[200:]
        if self.on_run:
            self.on_run(board, rule, card)

    def _as_bot(self, board, fn):
        prev, board.actor = board.actor, "Автоматизация"
        self.depth += 1
        try:
            return fn()
        finally:
            self.depth -= 1
            board.actor = prev

    def on_event(self, board, event, payload):
        if self.depth >= MAX_DEPTH:
            return
        card = board.card(payload.get("card")) if payload.get("card") else None
        if card is None:
            return
        for rule in list(board.d.get("rules", [])):
            if rule.get("kind") != "rule" or not rule.get("enabled", True):
                continue
            tr = rule.get("trigger", {})
            if tr.get("type") != event or not self._trigger_matches(tr, payload):
                continue
            card = board.card(payload["card"])
            if card is None or not check(board, card, rule.get("conditions")):
                continue
            self._as_bot(board, lambda r=rule, c=card: run_card_actions(board, c, r.get("actions", [])))
            self._record(board, rule, card)

    @staticmethod
    def _trigger_matches(tr, payload):
        for key in ("list", "from", "label", "member"):
            if tr.get(key) and tr[key] != payload.get(key):
                return False
        if tr.get("contains") and tr["contains"].lower() not in (payload.get("text") or "").lower():
            return False
        return True

    # -- buttons
    def press_card_button(self, board, button, card_id):
        card = board.card(card_id)
        if not card:
            return
        board._begin()   # one undo step for the whole button
        try:
            self._as_bot(board, lambda: run_card_actions(board, card, button.get("actions", [])))
        finally:
            board._end("", None, {})
        self._record(board, button, card)

    def press_board_button(self, board, button):
        board._begin()
        try:
            n = self._as_bot(board, lambda: run_board_actions(board, button))
        finally:
            board._end("", None, {})
        self._record(board, button)
        return n

    # -- time
    def tick(self, board, now=None):
        """Run scheduled / due-date commands that became due; returns the number of runs."""
        now = now or datetime.now()
        runs = 0
        for rule in board.d.get("rules", []):
            if not rule.get("enabled", True):
                continue
            if rule.get("kind") == "schedule":
                at = last_occurrence(rule.get("trigger", {}), now)
                created = parse_dt(rule.get("created")) or now
                done = parse_dt(rule.get("last_at")) or created
                if at and at > done and at >= created.replace(second=0, microsecond=0):
                    rule["last_at"] = at.strftime("%Y-%m-%dT%H:%M")
                    board._begin()
                    try:
                        self._as_bot(board, lambda r=rule: run_board_actions(board, r, now))
                    finally:
                        board._end("", None, {})
                    self._record(board, rule)
                    runs += 1
            elif rule.get("kind") == "due":
                runs += self._due(board, rule, now)
        return runs

    def _due(self, board, rule, now):
        tr = rule.get("trigger", {})
        amount = float(tr.get("amount", 1) or 0)
        delta = timedelta(hours=amount) if tr.get("unit") == "hours" else timedelta(days=amount)
        when = tr.get("when", "before")
        created = parse_dt(rule.get("created")) or now
        fired = rule.setdefault("fired", {})
        runs = 0
        for card in list(board.cards()):
            due = parse_dt(card.get("due"))
            if not due or card.get("due_done"):
                continue
            at = due - delta if when == "before" else due + delta if when == "after" else due
            if at > now or fired.get(card["id"]) == card["due"]:
                continue
            ref = due if when == "before" else at   # "before" still fires late for a due set after the rule
            if ref < created - timedelta(minutes=1):  # don't fire for moments before the rule existed
                fired[card["id"]] = card["due"]
                continue
            if not check(board, card, rule.get("conditions"), now):
                continue
            fired[card["id"]] = card["due"]
            board._begin()
            try:
                self._as_bot(board, lambda c=card: run_card_actions(board, c, rule.get("actions", []), now))
            finally:
                board._end("", None, {})
            self._record(board, rule, card)
            runs += 1
        return runs


def last_occurrence(tr, now):
    """Latest scheduled moment ≤ now for a schedule trigger."""
    try:
        hh, mm = [int(x) for x in (tr.get("time") or "09:00").split(":")[:2]]
    except ValueError:
        hh, mm = 9, 0
    t = tr.get("type", "daily")
    for back in range(0, 62):
        day = (now - timedelta(days=back)).replace(hour=hh, minute=mm, second=0, microsecond=0)
        if day > now:
            continue
        if t == "daily":
            return day
        if t == "weekdays" and day.weekday() < 5:
            return day
        if t == "weekly" and day.weekday() == int(tr.get("day", 0)) % 7:
            return day
        if t == "monthly":
            want = min(int(tr.get("day", 1) or 1), calendar.monthrange(day.year, day.month)[1])
            if day.day == want:
                return day
    return None


# ---- ready-made rules for templates and the "Идеи" list

def suggestions(board):
    """A few useful rules for this board's lists (shown as one-click ideas)."""
    lists = board.lists()
    if not lists:
        return []
    first, last = lists[0], lists[-1]
    done_label = next((x for x in board.d["labels"] if x["color"] == "green"), None)
    out = [
        new_rule(trigger={"type": "card_moved", "list": last["id"]},
                 actions=[{"type": "mark_done"}] + ([{"type": "add_label", "label": done_label["id"]}]
                                                    if done_label else [])),
        new_rule(trigger={"type": "card_moved", "list": first["id"]}, actions=[{"type": "mark_undone"}]),
        new_rule(trigger={"type": "checklist_done"}, actions=[{"type": "move", "list": last["id"], "where": "top"}]),
        new_rule(kind="due", trigger={"when": "before", "amount": 1, "unit": "days"},
                 actions=[{"type": "set_cover", "color": "yellow"}, {"type": "move", "list": lists[min(1, len(lists) - 1)]["id"],
                                                                     "where": "top"}],
                 conditions=[{"type": "in_list", "list": first["id"]}]),
        new_rule(kind="due", trigger={"when": "after", "amount": 0, "unit": "hours"},
                 actions=[{"type": "set_cover", "color": "red"}, {"type": "comment", "text": "Срок прошёл ⏰"}]),
        new_rule(kind="schedule", trigger={"type": "weekly", "day": 0, "time": "09:00"},
                 actions=[{"type": "archive"}], conditions=[{"type": "in_list", "list": last["id"]}]),
        new_rule(kind="schedule", trigger={"type": "daily", "time": "09:00"},
                 actions=[{"type": "sort_list", "list": first["id"], "key": "due"}]),
        new_rule(kind="card_button", name="Взять в работу", icon="play",
                 actions=[{"type": "add_member", "member": "me"},
                          {"type": "move", "list": lists[min(1, len(lists) - 1)]["id"], "where": "top"}]),
        new_rule(kind="board_button", name="Убрать готовое", icon="archive",
                 actions=[{"type": "archive_list", "list": last["id"]}]),
    ]
    return out


def clone_rule(rule):
    r = copy.deepcopy(rule)
    r.update(id=new_id(), runs=0, last="", created=now_iso(), fired={})
    return r
