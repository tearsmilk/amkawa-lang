"""Markdown → HTML for the reader view (QTextBrowser-friendly HTML: tables + inline styles).

Extras on top of Markdown: [[wiki links]], ![[embeds]], #tags, clickable - [ ] tasks,
> [!note] callouts, and code blocks highlighted by Pygments with an auto-detected language.
"""
import html
import re
from pathlib import Path
from urllib.parse import quote, unquote

import markdown
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name

from . import attachments as att
from .codedetect import detect_language, pretty_name
from .vault import TAG_RE, WIKILINK_RE

FENCE_OPEN = re.compile(r"^(\s*)(```|~~~)\s*([\w+#.-]*)[^\n]*$")
TASK_RE = re.compile(r"^(\s*(?:[-*+]|\d+\.)\s+)\[( |x|X)\]\s?")
TASK_SLOT_MARK = "MILKYTASK"
LIST_INDENT_RE = re.compile(r"^( +)(?:[-*+]|\d+\.)\s")
CALLOUT_RE = re.compile(r"^>\s*\[!(\w+)\][+-]?\s*(.*)$")
IMAGE_EXT = att.IMAGE_EXT | att.GIF_EXT
# a line that is only a link / embed of a file → shown as a picture or an attachment card
EMBED_MD = re.compile(r'^\s*(!?)\[([^\]]*)\]\(\s*<?([^()<>]+?)>?(?:\s+"[^"]*")?\s*\)\s*$')
EMBED_WIKI = re.compile(r"^\s*!\[\[([^\]|#]+)(?:\|([^\]]*))?\]\]\s*$")
IMG_SRC = re.compile(r'(<img [^>]*?src=")([^"]+)(")')
SCHEME = re.compile(r"^[a-zA-Z][\w+.-]*:")


def attach_href(path, scheme="attach"):
    return f"{scheme}:{quote(str(path), safe='/')}"


def href_path(text):
    """Path from an attach:/reveal: link (the part after the scheme, percent-encoded)."""
    return Path(unquote(text.split(":", 1)[1]))

CALLOUTS = {
    "note": ("✎", "Заметка", "#4A7BD0"), "info": ("ℹ", "Инфо", "#4A7BD0"), "tip": ("✦", "Совет", "#3E8E63"),
    "success": ("✓", "Готово", "#3E8E63"), "question": ("?", "Вопрос", "#B5862E"), "warning": ("!", "Внимание", "#C27A2C"),
    "danger": ("✕", "Опасно", "#C2453E"), "bug": ("✕", "Баг", "#C2453E"), "example": ("❖", "Пример", "#8A63C9"),
    "quote": ("❝", "Цитата", "#8A8780"), "todo": ("☐", "Сделать", "#4A7BD0"),
}


class Renderer:
    def __init__(self, colors, resolve=None, code_style="default", base_dir=None, thumbs=None):
        self.c = colors
        self.resolve = resolve or (lambda name: None)
        self.code_style = code_style
        self.base_dir = Path(base_dir) if base_dir else None
        self.thumbs = thumbs  # attachments.Thumbnails or None
        self.code_blocks = []  # raw code, for "copy" links
        self.attachments = []  # embedded files in order, for the media viewer
    # ------------------------------------------------------------------ public
    def render(self, text: str) -> str:
        self.code_blocks = []
        self.attachments = []
        self._slots = {}
        body = self._render_md(text, top=True)
        return f"<html><body>{body}</body></html>"

    def stylesheet(self, font_px=15):
        c = self.c
        return f"""
body {{ color: {c['text']}; font-size: {font_px}px; }}
h1 {{ font-family: Georgia, 'Times New Roman', serif; font-size: {font_px + 15}px; font-weight: normal; margin-top: 6px; margin-bottom: 10px; }}
h2 {{ font-family: Georgia, 'Times New Roman', serif; font-size: {font_px + 8}px; font-weight: normal; margin-top: 18px; margin-bottom: 6px; }}
h3 {{ font-size: {font_px + 3}px; font-weight: 600; margin-top: 14px; margin-bottom: 4px; }}
h4, h5, h6 {{ font-size: {font_px}px; font-weight: 600; }}
p {{ margin-top: 4px; margin-bottom: 8px; line-height: 150%; }}
li {{ margin-bottom: 3px; }}
a {{ color: {c['accent']}; text-decoration: none; }}
code {{ font-family: Menlo, Monaco, monospace; background-color: {c['code_bg']}; color: {c['code_inline']}; font-size: {font_px - 2}px; }}
blockquote {{ color: {c['muted']}; margin-left: 12px; padding-left: 12px; border-left: 3px solid {c['border']}; }}
th {{ background-color: {c['code_bg']}; font-weight: 600; padding: 6px 10px; }}
td {{ padding: 6px 10px; }}
hr {{ border: none; height: 1px; background-color: {c['border']}; }}
"""

    # ------------------------------------------------------------------ internals
    def _slot(self, html_text):
        key = f"MILKYSLOT{len(self._slots)}X"
        self._slots[key] = html_text
        return key

    def _render_md(self, text, top=False):
        lines = text.split("\n")
        out = []
        i = 0
        while i < len(lines):
            line = lines[i]
            fence = FENCE_OPEN.match(line)
            if fence:
                indent, mark, lang = fence.groups()
                j = i + 1
                while j < len(lines) and not lines[j].strip().startswith(mark):
                    j += 1
                code = "\n".join(l[len(indent):] if l.startswith(indent) else l for l in lines[i + 1:j])
                out.append("")
                out.append(self._slot(self._code_html(code, lang)))
                out.append("")
                i = j + 1
                continue
            callout = CALLOUT_RE.match(line)
            if callout:
                kind, title = callout.group(1).lower(), callout.group(2).strip()
                j = i + 1
                body = []
                while j < len(lines) and lines[j].startswith(">"):
                    body.append(re.sub(r"^>\s?", "", lines[j]))
                    j += 1
                out.append("")
                out.append(self._slot(self._callout_html(kind, title, "\n".join(body))))
                out.append("")
                i = j
                continue
            media = self._embed_line(line)
            if media is not None:
                out += ["", self._slot(media), ""]
                i += 1
                continue
            if top:
                task = TASK_RE.match(line)
                if task:
                    done = task.group(2).lower() == "x"
                    box = TASK_SLOT_MARK.join([self._slot(
                        f'<a href="task:{i}" style="text-decoration:none; color:{self.c["accent"] if done else self.c["muted"]};">'
                        f'{"☑" if done else "☐"}</a>&nbsp;'), ""])
                    rest = line[task.end():]
                    if done and rest:
                        rest = (self._slot(f"<span style='color:{self.c['muted']}'>") + rest
                                + self._slot("</span>"))
                    line = task.group(1) + box + rest
            # Obsidian nests lists with 2 spaces, Python-Markdown needs 4
            lst = LIST_INDENT_RE.match(line)
            if lst and len(lst.group(1)) % 4:
                line = " " * (len(lst.group(1)) * 2) + line.lstrip(" ")
            out.append(line)
            i += 1
        text = "\n".join(out)
        text = self._inline_extras(text)
        rendered = markdown.markdown(text, extensions=["tables", "sane_lists", "nl2br"], output_format="html")
        # placeholders that ended up alone in a paragraph: drop the <p> wrapper
        # task lists: no bullets, the checkbox is the marker
        task_key = re.escape(TASK_SLOT_MARK)
        rendered = re.sub(r"<ul>(\s*<li>(?:<p>)?MILKYSLOT\d+X" + task_key + ")", r'<ul style="list-style-type:none; margin-left:-18px;">\1', rendered)
        for key, value in list(self._slots.items()):
            rendered = rendered.replace(f"<p>{key}</p>", value).replace(key, value)
        rendered = IMG_SRC.sub(self._absolute_src, rendered)
        return rendered.replace(TASK_SLOT_MARK, "")

    # ------------------------------------------------------------------ attachments
    def _local(self, target):
        """A local file for a Markdown link target (relative to the note), or None."""
        target = target.strip()
        if target.startswith("file://"):
            target = target[7:]
        elif SCHEME.match(target):
            return None
        path = Path(unquote(target))
        if not path.is_absolute():
            if self.base_dir is None:
                return None
            path = self.base_dir / path
        try:
            return path.resolve() if path.is_file() else None
        except OSError:
            return None

    def _absolute_src(self, m):
        local = self._local(html.unescape(m.group(2)))
        return m.group(1) + (local.as_uri() if local else m.group(2)) + m.group(3)

    def _embed_line(self, line):
        m = EMBED_MD.match(line)
        if m:
            path = self._local(m.group(3))
            embed, title = bool(m.group(1)), m.group(2)
        else:
            m = EMBED_WIKI.match(line)
            if not m:
                return None
            path = self.resolve(m.group(1).strip())
            embed, title = True, m.group(2)
        if path is None or Path(path).suffix.lower() == ".md":
            return None
        return self._media_html(Path(path), title, embed)

    def _media_html(self, path, title="", embed=True):
        kind = att.kind_of(path)
        self.attachments.append(path)
        href = attach_href(path)
        if embed and kind in ("image", "gif"):
            # line-height 100%: the reader's 150% would add half the picture's height as a gap
            return (f'<p style="line-height:100%; margin-top:6px; margin-bottom:10px;"><a href="{href}">'
                    f'<img src="{path.as_uri()}" alt="{html.escape(title or path.stem)}"></a></p>')
        c = self.c
        thumb = path if kind in ("image", "gif") else (self.thumbs.get(path) if self.thumbs else None)
        if thumb is not None:
            width = 168 if kind == "video" else 96
            preview = (f'<td width="{width}" valign="middle" style="padding:10px 0px 10px 10px;">'
                       f'<a href="{href}"><img src="{Path(thumb).as_uri()}" width="{width}"></a></td>')
        else:
            preview = (f'<td width="64" align="center" valign="middle" style="padding:12px 4px; '
                       f'background-color:{c["tag_bg"]};"><a href="{href}" style="text-decoration:none; '
                       f'font-size:28px;">{att.icon_of(path)}</a></td>')
        action = {"video": "▶&nbsp;Смотреть", "audio": "▶&nbsp;Слушать"}.get(kind, "Открыть")
        name = title if title and not embed and title != path.name else path.name
        return (
            f'<table width="100%" cellspacing="0" cellpadding="0" style="margin-top:6px; margin-bottom:10px; '
            f'background-color:{c["card"]}; border: 1px solid {c["border"]};"><tr>{preview}'
            f'<td valign="middle" style="padding:10px 14px;">'
            f'<a href="{href}" style="color:{c["text"]}; font-weight:600;">{html.escape(name)}</a><br>'
            f'<span style="color:{c["muted"]}; font-size:12px;">{html.escape(att.describe(path))}</span><br>'
            f'<span style="font-size:12px;"><a href="{href}">{action}</a>&nbsp;&nbsp;&nbsp;'
            f'<a href="{attach_href(path, "reveal")}" style="color:{c["muted"]};">Показать в Finder</a></span>'
            f'</td></tr></table>')

    def _inline_extras(self, text):
        # protect inline code from tag / link processing
        codes = []

        def keep(m):
            codes.append(m.group(0))
            return f"MILKYCODE{len(codes) - 1}X"

        text = re.sub(r"`[^`\n]+`", keep, text)
        accent = self.c["accent"]
        text = TAG_RE.sub(lambda m: self._slot(
            f'<a href="tag:{html.escape(m.group(1))}" style="color:{accent}; background-color:{self.c["tag_bg"]};">'
            f'&nbsp;#{html.escape(m.group(1))}&nbsp;</a>'), text)
        text = WIKILINK_RE.sub(self._wikilink, text)
        for n, code in enumerate(codes):
            text = text.replace(f"MILKYCODE{n}X", code)
        return text

    def _wikilink(self, m):
        embed, target, alias = m.group(1), m.group(2).strip(), m.group(4)
        path = self.resolve(target)
        if embed and path is not None and Path(path).suffix.lower() in IMAGE_EXT:
            self.attachments.append(Path(path))
            return self._slot(f'<a href="{attach_href(path)}"><img src="{Path(path).as_uri()}" alt="{html.escape(target)}"></a>')
        if path is not None and Path(path).suffix.lower() != ".md":
            label = html.escape(alias or Path(path).name)
            return self._slot(f'<a href="{attach_href(path)}">{att.icon_of(path)}&nbsp;{label}</a>')
        label = html.escape(alias or target)
        if path is None:
            return self._slot(f'<a href="note:{html.escape(target)}" style="color:{self.c["muted"]};">{label}</a>')
        return self._slot(f'<a href="note:{html.escape(target)}">{label}</a>')

    def _code_html(self, code, lang):
        lang = (lang or "").lower()
        if not lang:
            lang = detect_language(code)
        try:
            lexer = get_lexer_by_name(lang)
        except Exception:
            lexer = TextLexer()
        formatter = HtmlFormatter(noclasses=True, nowrap=True, style=self.code_style, nobackground=True)
        body = highlight(code, lexer, formatter).rstrip("\n")
        n = len(self.code_blocks)
        self.code_blocks.append(code)
        c = self.c
        return (
            f'<table width="100%" cellspacing="0" cellpadding="0" style="margin-top:6px; margin-bottom:10px; '
            f'background-color:{c["code_bg"]}; border: 1px solid {c["border"]};">'
            f'<tr><td style="padding:7px 12px 0px 12px; color:{c["muted"]}; font-size:11px;">'
            f'{html.escape(pretty_name(lang).upper())}</td>'
            f'<td align="right" style="padding:7px 12px 0px 12px; font-size:11px;">'
            f'<a href="copy:{n}">Копировать</a></td></tr>'
            f'<tr><td colspan="2" style="padding:6px 12px 10px 12px;">'
            f'<pre style="font-family: Menlo, Monaco, monospace; font-size:12px; margin:0px;">{body}</pre>'
            f'</td></tr></table>')

    def _callout_html(self, kind, title, body):
        icon, default_title, color = CALLOUTS.get(kind, ("✎", kind.capitalize(), "#4A7BD0"))
        inner = Renderer(self.c, self.resolve, self.code_style, self.base_dir, self.thumbs)
        inner._slots = self._slots  # share placeholder space
        inner.code_blocks = self.code_blocks
        inner.attachments = self.attachments
        body_html = inner._render_md(body) if body.strip() else ""
        return (
            f'<table width="100%" cellspacing="0" cellpadding="0" style="margin-top:6px; margin-bottom:10px; '
            f'background-color:{self.c["callout_bg"]}; border-left: 3px solid {color};">'
            f'<tr><td style="padding:8px 14px 2px 14px; color:{color}; font-weight:600;">'
            f'{icon}&nbsp;&nbsp;{html.escape(title or default_title)}</td></tr>'
            f'<tr><td style="padding:0px 14px 6px 14px;">{body_html}</td></tr></table>')
