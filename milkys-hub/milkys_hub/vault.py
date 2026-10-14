"""A vault is a plain folder: notes are .md files, attachments live in `attachments/`,
saved links in `.milkys/links.json`, deleted notes go to `.trash/`. Everything stays on disk."""
import datetime as dt
import json
import re
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

ATTACHMENTS = "attachments"
HIDDEN = {".milkys", ".trash", ".git", ".obsidian"}

WIKILINK_RE = re.compile(r"(!?)\[\[([^\]|#]+)(#[^\]|]*)?(?:\|([^\]]+))?\]\]")
TAG_RE = re.compile(r"(?<![\w#/&])#([A-Za-zА-Яа-яЁё0-9_][\wА-Яа-яЁё/-]*)")
FENCE_RE = re.compile(r"^(```|~~~).*?^\1[ \t]*$", re.M | re.S)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.M)


def strip_code(text: str) -> str:
    """Remove fenced and inline code so tags/links inside code are ignored."""
    return INLINE_CODE_RE.sub("", FENCE_RE.sub("", text))


def safe_name(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", name).strip().strip(".")
    return name[:120] or "Без названия"


@dataclass
class NoteInfo:
    path: Path
    title: str
    mtime: float
    tags: set = field(default_factory=set)
    links: set = field(default_factory=set)  # lower-cased target names


@dataclass
class Link:
    id: str
    url: str
    title: str
    tags: list
    note: str
    added: str


class Vault:
    def __init__(self, root):
        self.root = Path(root).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / ATTACHMENTS).mkdir(exist_ok=True)
        (self.root / ".milkys").mkdir(exist_ok=True)
        self._index = {}

    # ---------------------------------------------------------------- notes
    def notes(self):
        out = []
        for p in self.root.rglob("*.md"):
            rel = p.relative_to(self.root)
            if any(part in HIDDEN for part in rel.parts[:-1]):
                continue
            out.append(p)
        return sorted(out, key=lambda p: str(p).lower())

    def rel(self, path) -> str:
        return str(Path(path).relative_to(self.root))

    def read(self, path) -> str:
        try:
            return Path(path).read_text("utf-8")
        except FileNotFoundError:
            return ""

    def write(self, path, text: str):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, "utf-8")
        tmp.replace(path)
        self._index.pop(path, None)

    def unique_path(self, folder, name, suffix=".md"):
        folder = Path(folder)
        base = safe_name(name)
        path = folder / f"{base}{suffix}"
        n = 2
        while path.exists():
            path = folder / f"{base} {n}{suffix}"
            n += 1
        return path

    def create_note(self, name="Без названия", folder=None, text=None):
        folder = Path(folder) if folder else self.root
        path = self.unique_path(folder, name)
        self.write(path, text if text is not None else f"# {path.stem}\n\n")
        return path

    def create_folder(self, name, parent=None):
        path = Path(parent or self.root) / safe_name(name)
        n = 2
        while path.exists():
            path = Path(parent or self.root) / f"{safe_name(name)} {n}"
            n += 1
        path.mkdir(parents=True)
        return path

    def rename(self, path, new_name):
        path = Path(path)
        target = path.with_name(safe_name(new_name) + path.suffix)
        if target == path:
            return path
        if target.exists():
            raise FileExistsError(f"«{target.name}» уже существует")
        old_title = path.stem
        path.rename(target)
        self._index.pop(path, None)
        if target.suffix == ".md":
            self._rewrite_links(old_title, target.stem)
        return target

    def _rewrite_links(self, old, new):
        rx = re.compile(r"\[\[" + re.escape(old) + r"(?=[\]|#])", re.I)
        for note in self.notes():
            text = self.read(note)
            if "[[" in text and rx.search(text):
                self.write(note, rx.sub("[[" + new, text))

    def delete(self, path):
        path = Path(path)
        trash = self.root / ".trash"
        trash.mkdir(exist_ok=True)
        dest = trash / f"{time.strftime('%Y%m%d-%H%M%S')} {path.name}"
        shutil.move(str(path), str(dest))
        self._index.pop(path, None)
        return dest

    def daily_note(self, day=None):
        day = day or dt.date.today()
        path = self.root / "Дневник" / f"{day.isoformat()}.md"
        if not path.exists():
            self.write(path, f"# {day.strftime('%d.%m.%Y')}\n\n## Задачи\n- [ ] \n\n## Заметки\n\n")
        return path

    # ---------------------------------------------------------------- index
    def info(self, path) -> NoteInfo:
        path = Path(path)
        mtime = path.stat().st_mtime
        cached = self._index.get(path)
        if cached and cached.mtime == mtime:
            return cached
        text = strip_code(self.read(path))
        tags = {t.lower() for t in TAG_RE.findall(text)}
        links = {m.group(2).strip().lower() for m in WIKILINK_RE.finditer(text) if not m.group(1)}
        info = NoteInfo(path, path.stem, mtime, tags, links)
        self._index[path] = info
        return info

    def all_info(self):
        return [self.info(p) for p in self.notes()]

    def resolve(self, name: str):
        """Find a note (or attachment) by wiki-link name."""
        name = name.strip()
        low = name.lower().removesuffix(".md")
        for p in self.notes():
            if p.stem.lower() == low or self.rel(p).lower().removesuffix(".md") == low:
                return p
        cand = self.root / ATTACHMENTS / name
        if cand.exists():
            return cand
        for p in self.root.rglob(name):
            if not any(part in HIDDEN for part in p.relative_to(self.root).parts):
                return p
        return None

    def backlinks(self, path):
        title = Path(path).stem.lower()
        return [i.path for i in self.all_info() if title in i.links and i.path != Path(path)]

    def tags(self):
        counts = {}
        for i in self.all_info():
            for t in i.tags:
                counts[t] = counts.get(t, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    def notes_with_tag(self, tag):
        tag = tag.lower().lstrip("#")
        return [i.path for i in self.all_info() if tag in i.tags or any(t.startswith(tag + "/") for t in i.tags)]

    def search(self, query, limit=200):
        q = query.strip().lower()
        if not q:
            return []
        if q.startswith("#"):
            return [(p, "") for p in self.notes_with_tag(q)]
        results = []
        for p in self.notes():
            text = self.read(p)
            low = text.lower()
            name_hit = q in p.stem.lower()
            pos = low.find(q)
            if name_hit or pos >= 0:
                snippet = ""
                if pos >= 0:
                    a, b = max(0, pos - 50), min(len(text), pos + len(q) + 70)
                    snippet = ("…" if a else "") + text[a:b].replace("\n", " ") + ("…" if b < len(text) else "")
                results.append((p, snippet, 0 if name_hit else 1))
            if len(results) >= limit:
                break
        results.sort(key=lambda r: (r[2], r[0].stem.lower()))
        return [(p, s) for p, s, _ in results]

    def graph(self):
        infos = self.all_info()
        by_title = {i.title.lower(): i.path for i in infos}
        edges = set()
        for i in infos:
            for target in i.links:
                if target in by_title and by_title[target] != i.path:
                    edges.add(tuple(sorted((str(i.path), str(by_title[target])))))
        return [i.path for i in infos], [(Path(a), Path(b)) for a, b in edges]

    @staticmethod
    def outline(text):
        return [(len(m.group(1)), m.group(2), text.count("\n", 0, m.start())) for m in HEADING_RE.finditer(strip_code(text))]

    # ---------------------------------------------------------------- attachments
    def attachments(self):
        folder = self.root / ATTACHMENTS
        return sorted((p for p in folder.rglob("*") if p.is_file()), key=lambda p: -p.stat().st_mtime)

    def import_file(self, src):
        """Copy a file into the vault's attachments folder; returns the new path."""
        src = Path(src)
        dest = self.unique_path(self.root / ATTACHMENTS, src.stem, src.suffix)
        shutil.copy2(src, dest)
        return dest

    def save_image_bytes(self, data: bytes, ext="png"):
        dest = self.unique_path(self.root / ATTACHMENTS, f"Вставка {time.strftime('%Y-%m-%d %H.%M.%S')}", "." + ext)
        dest.write_bytes(data)
        return dest

    # ---------------------------------------------------------------- links (bookmarks)
    @property
    def _links_file(self):
        return self.root / ".milkys" / "links.json"

    def links(self):
        try:
            return [Link(**d) for d in json.loads(self._links_file.read_text("utf-8"))]
        except Exception:
            return []

    def _save_links(self, links):
        tmp = self._links_file.with_suffix(".tmp")
        tmp.write_text(json.dumps([l.__dict__ for l in links], ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(self._links_file)

    def add_link(self, url, title="", tags=None, note=""):
        url = url.strip()
        if not re.match(r"^[a-z][\w+.-]*:", url):
            url = "https://" + url
        link = Link(uuid.uuid4().hex[:12], url, title.strip() or _title_from_url(url),
                    [t.strip().lstrip("#") for t in (tags or []) if t.strip()], note.strip(),
                    dt.datetime.now().isoformat(timespec="minutes"))
        links = self.links()
        links.insert(0, link)
        self._save_links(links)
        return link

    def update_link(self, link):
        self._save_links([link if l.id == link.id else l for l in self.links()])

    def delete_link(self, link_id):
        self._save_links([l for l in self.links() if l.id != link_id])

    # ---------------------------------------------------------------- first run
    def ensure_welcome(self):
        if any(self.notes()):
            return None
        return self.create_note("Добро пожаловать", text=WELCOME)


def _title_from_url(url):
    m = re.match(r"^[a-z]+://(www\.)?([^/?#]+)(/[^?#]*)?", url)
    if not m:
        return url
    host, path = m.group(2), (m.group(3) or "").strip("/")
    last = path.split("/")[-1] if path else ""
    return f"{host} — {last}" if last else host


WELCOME = """# Добро пожаловать в Milkys Hub ✻

Всё хранится **локально** в папке хранилища — обычные `.md` файлы, их можно открыть любым редактором.

## Что умеет
- [[Заметки]] со ссылками в стиле Obsidian: `[[Название]]` — щёлкните, чтобы перейти или создать
- Теги: #идеи #работа — список тегов слева
- Задачи — щёлкайте по квадратикам в просмотре:
  - [ ] попробовать вставить код
  - [x] открыть Milkys Hub
- Файлы и картинки: перетащите в заметку — они скопируются в папку `attachments`
- Ссылки (закладки) — раздел «Ссылки» слева
- Наберите `/` в начале строки — меню блоков (как в Notion)

> [!tip] Код
> Вставьте код (⌘V) — язык определится сам, и код упакуется в красивый блок.

```python
def hello(name: str) -> str:
    return f"Привет, {name}!"
```

| Клавиши | Действие |
|---|---|
| ⌘N | новая заметка |
| ⌘O | быстрый переход |
| ⇧⌘F | поиск по всему |
| ⌘E | редактор / просмотр |
"""
