"""Tasks for the calendar / planner, read from and written back to plain Markdown.

A task is any `- [ ] text` line in any note. Optional markers (Obsidian Tasks compatible):
  📅 2026-10-20   due date        ⏰ 14:30   time        ⏫ / 🔼 / 🔽   high / medium / low priority
A task in a daily note (Дневник/2026-10-20.md) without 📅 belongs to that day.
"""
import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

from .vault import FENCE_RE

TASK_LINE = re.compile(r"^(\s*(?:[-*+]|\d+\.)\s+)\[( |x|X)\]\s+(.*\S)\s*$")
DATE_RE = re.compile(r"(?:📅|@)\s*(\d{4}-\d{2}-\d{2})")
TIME_RE = re.compile(r"⏰\s*(\d{1,2}):(\d{2})")
PRIORITY = {"⏫": 3, "🔼": 2, "🔽": 1}
DAILY_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})$")
DAILY_FOLDER = "Дневник"


@dataclass
class Task:
    path: Path
    line: int          # 0-based line number in the file
    raw: str           # the full source line
    text: str          # text without markers
    done: bool
    date: dt.date | None
    time: dt.time | None
    priority: int      # 0 none, 1 low, 2 medium, 3 high
    explicit_date: bool

    @property
    def key(self):
        return f"{self.path}:{self.line}:{self.text}"

    @property
    def when(self):
        if not self.date:
            return None
        return dt.datetime.combine(self.date, self.time or dt.time(0, 0))


def _clean(text):
    text = DATE_RE.sub("", text)
    text = TIME_RE.sub("", text)
    for mark in PRIORITY:
        text = text.replace(mark, "")
    return re.sub(r"\s{2,}", " ", text).strip()


def _fenced_lines(text):
    """Line numbers that are inside ``` code blocks (tasks there are not tasks)."""
    skip = set()
    for m in FENCE_RE.finditer(text):
        a = text.count("\n", 0, m.start())
        b = text.count("\n", 0, m.end())
        skip.update(range(a, b + 1))
    return skip


def parse_note(path, text):
    path = Path(path)
    daily = DAILY_NAME.match(path.stem)
    daily_date = dt.date.fromisoformat(daily.group(1)) if daily else None
    skip = _fenced_lines(text)
    tasks = []
    for n, line in enumerate(text.split("\n")):
        if n in skip:
            continue
        m = TASK_LINE.match(line)
        if not m:
            continue
        body = m.group(3)
        text_only = _clean(body)
        if not text_only:
            continue
        dm = DATE_RE.search(body)
        tm = TIME_RE.search(body)
        try:
            date = dt.date.fromisoformat(dm.group(1)) if dm else daily_date
        except ValueError:
            date = daily_date
        time = None
        if tm and int(tm.group(1)) < 24 and int(tm.group(2)) < 60:
            time = dt.time(int(tm.group(1)), int(tm.group(2)))
        prio = max((v for k, v in PRIORITY.items() if k in body), default=0)
        tasks.append(Task(path, n, line, text_only, m.group(2).lower() == "x", date, time, prio, bool(dm)))
    return tasks


class TaskIndex:
    def __init__(self, vault):
        self.vault = vault
        self._cache = {}

    def all(self):
        out = []
        for p in self.vault.notes():
            mtime = p.stat().st_mtime
            cached = self._cache.get(p)
            if not cached or cached[0] != mtime:
                cached = (mtime, parse_note(p, self.vault.read(p)))
                self._cache[p] = cached
            out.extend(cached[1])
        return out

    # ------------------------------------------------------------ queries
    def on(self, day):
        return sorted((t for t in self.all() if t.date == day), key=_order)

    def by_day(self, first, last):
        days = {}
        for t in self.all():
            if t.date and first <= t.date <= last:
                days.setdefault(t.date, []).append(t)
        return days

    def overdue(self, today=None):
        today = today or dt.date.today()
        return sorted((t for t in self.all() if t.date and t.date < today and not t.done), key=_order)

    def upcoming(self, days=7, today=None):
        today = today or dt.date.today()
        end = today + dt.timedelta(days=days)
        return sorted((t for t in self.all() if t.date and today < t.date <= end and not t.done), key=_order)

    def undated(self):
        return sorted((t for t in self.all() if not t.date and not t.done), key=lambda t: (-t.priority, t.text.lower()))

    # ------------------------------------------------------------ edits (always re-read the file first)
    def _edit_line(self, task, fn):
        text = self.vault.read(task.path)
        lines = text.split("\n")
        idx = task.line
        if idx >= len(lines) or lines[idx] != task.raw:
            # the note changed since indexing: find the same task text
            idx = next((i for i, l in enumerate(lines) if l == task.raw), None)
            if idx is None:
                raise RuntimeError("Задача изменилась — обновите календарь")
        new = fn(lines[idx])
        if new is None:
            del lines[idx]
        else:
            lines[idx] = new
        self.vault.write(task.path, "\n".join(lines))
        self._cache.pop(task.path, None)

    def toggle(self, task):
        def flip(line):
            m = TASK_LINE.match(line)
            return f"{m.group(1)}[{' ' if m.group(2).lower() == 'x' else 'x'}] {m.group(3)}"
        self._edit_line(task, flip)

    def reschedule(self, task, day):
        def move(line):
            m = TASK_LINE.match(line)
            body = DATE_RE.sub("", m.group(3)).rstrip()
            if day is not None:
                body = f"{body} 📅 {day.isoformat()}"
            return f"{m.group(1)}[{m.group(2)}] {re.sub(r'  +', ' ', body)}"
        self._edit_line(task, move)

    def delete(self, task):
        self._edit_line(task, lambda _line: None)

    def add(self, text, day=None, time=None, priority=0):
        """Add a task to the daily note of `day` (or to «Входящие» when undated)."""
        text = text.strip()
        if not text:
            raise ValueError("Введите задачу")
        marks = ""
        if time:
            marks += f" ⏰ {time.strftime('%H:%M')}"
        marks += {3: " ⏫", 2: " 🔼", 1: " 🔽"}.get(priority, "")
        if day is not None:
            path = self.vault.daily_note(day)
        else:
            path = self.vault.root / "Входящие.md"
            if not path.exists():
                self.vault.write(path, "# Входящие\n\nЗадачи без даты.\n\n")
        lines = self.vault.read(path).split("\n")
        # drop the empty "- [ ] " placeholder of a fresh daily note
        lines = [l for l in lines if l.strip() not in ("- [ ]", "- [ ] ")]
        entry = f"- [ ] {text}{marks}"
        head = next((i for i, l in enumerate(lines) if l.strip().lower() == "## задачи"), None)
        if head is None:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(entry)
        else:
            j = head + 1
            while j < len(lines) and TASK_LINE.match(lines[j]):
                j += 1
            lines.insert(j, entry)
        self.vault.write(path, "\n".join(lines))
        self._cache.pop(path, None)
        return path


def _order(t):
    return (t.done, t.date or dt.date.max, t.time or dt.time(23, 59, 59), -t.priority, t.text.lower())
