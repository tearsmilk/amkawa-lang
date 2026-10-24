"""Code editor widget: line numbers, current line, indent guides, bracket matching, smart indent,
auto-closing pairs, comment toggling, line moves, word completion, find highlighting."""
import codecs
import re
from pathlib import Path

from PySide6.QtCore import QRect, QSize, QStringListModel, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QKeySequence, QPainter, QTextCursor, QTextDocument, QTextFormat
from PySide6.QtWidgets import QCompleter, QPlainTextEdit, QTextEdit, QWidget

from . import languages
from .highlighter import SyntaxHighlighter
from .theme import MONO_FAMILIES

PAIRS = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'", "`": "`"}
CLOSERS = {v: k for k, v in PAIRS.items() if k not in "\"'`"}
WORD_RE = re.compile(r"[A-Za-z_À-￿][\wÀ-￿]{2,}")


# ---------------------------------------------------------------------- file io
def read_file(path):
    """→ (text, encoding, eol). Raises ValueError for binary files."""
    data = Path(path).read_bytes()
    if b"\0" in data[:8000]:
        raise ValueError("Двоичный файл")
    encoding = "utf-8"
    if data.startswith(codecs.BOM_UTF8):
        encoding, data = "utf-8-sig", data[3:]
    for enc in (encoding, "cp1251", "latin-1"):
        try:
            text = data.decode(enc)
            encoding = enc
            break
        except UnicodeDecodeError:
            continue
    eol = "\r\n" if "\r\n" in text[:20000] else "\n"
    return text.replace("\r\n", "\n").replace("\r", "\n"), encoding, eol


def write_file(path, text, encoding="utf-8", eol="\n"):
    path = Path(path)
    tmp = path.with_name(f".{path.name}.nu-tmp")
    data = text.replace("\n", eol).encode(encoding, errors="replace")
    tmp.write_bytes(data)
    try:
        mode = path.stat().st_mode
        tmp.chmod(mode)
    except OSError:
        pass
    tmp.replace(path)


def mono_font(family="", size=13):
    families = set(QFontDatabase.families())
    fam = family if family and family in families else next((f for f in MONO_FAMILIES if f in families), "monospace")
    font = QFont(fam)
    font.setStyleHint(QFont.Monospace)
    font.setFixedPitch(True)
    font.setPixelSize(size)
    return font


# ---------------------------------------------------------------------- gutter
class Gutter(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_gutter(event)

    def mousePressEvent(self, e):
        # click on a line number selects the line
        cursor = self.editor.cursorForPosition(e.position().toPoint())
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.NextBlock, QTextCursor.KeepAnchor)
        self.editor.setTextCursor(cursor)


# ---------------------------------------------------------------------- editor
class CodeEditor(QPlainTextEdit):
    cursor_moved = Signal(int, int)       # line, column (1-based)
    modified_changed = Signal(bool)

    def __init__(self, colors, settings, path=None, share=None):
        """`share`: another editor whose document (and highlighter) this one shows — split view."""
        super().__init__()
        self.setObjectName("CodeEditor")
        self.c = colors
        self.settings = settings
        self.path = Path(path) if path else None
        self.encoding, self.eol = "utf-8", "\n"
        self.lang = languages.detect(path) if path else languages.PLAIN
        self.tab_size = int(settings.get("tab_size", 4))
        self.insert_spaces = bool(settings.get("insert_spaces", True))
        self.find_selections = []
        self.word_selections = []
        self.disk_mtime = None
        if share is not None:
            self.setDocument(share.document())
            self.path, self.lang, self.encoding, self.eol = share.path, share.lang, share.encoding, share.eol
            self.tab_size, self.insert_spaces, self.disk_mtime = share.tab_size, share.insert_spaces, share.disk_mtime
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth if settings.get("word_wrap") else QPlainTextEdit.NoWrap)
        self.setCenterOnScroll(False)
        self.gutter = Gutter(self)
        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)
        self.cursorPositionChanged.connect(self._cursor_changed)
        self.document().modificationChanged.connect(self.modified_changed)
        if share is None:
            self.highlighter = SyntaxHighlighter(self.document(), colors)
            self.highlighter.set_lexer(self.lang.lexer)
        else:
            self.highlighter = share.highlighter
        self.word_timer = QTimer(self, singleShot=True, interval=250, timeout=self._highlight_word)
        self.completer = QCompleter(self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setModel(QStringListModel(self))
        self.completer.activated.connect(self._insert_completion)
        self.apply_font()
        self._update_gutter_width()
        self._cursor_changed()

    # ------------------------------------------------------------------ appearance
    def apply_font(self, family=None, size=None):
        font = mono_font(family if family is not None else self.settings.get("font_family", ""),
                         size or int(self.settings.get("font_size", 13)))
        self.setFont(font)
        self.gutter.setFont(font)
        self.char_w = QFontMetricsF(font).horizontalAdvance(" ")
        self.setTabStopDistance(self.char_w * self.tab_size)
        self._update_gutter_width()

    def set_colors(self, colors):
        self.c = colors
        if self.highlighter is not None:
            self.highlighter.set_colors(colors)
        self._cursor_changed()
        self.viewport().update()
        self.gutter.update()

    def set_language(self, lang):
        self.lang = lang
        if self.highlighter is not None:
            self.highlighter.set_lexer(lang.lexer)

    def set_wrap(self, on):
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth if on else QPlainTextEdit.NoWrap)

    # ------------------------------------------------------------------ file
    def load(self, path):
        text, self.encoding, self.eol = read_file(path)
        self.path = Path(path)
        lang = languages.detect(path)
        if lang is languages.PLAIN or lang.id == "text":
            lang = languages.from_shebang(text.split("\n", 1)[0]) or lang
        self.lang = lang
        self.setPlainText(text)
        self.highlighter.set_lexer(lang.lexer)
        self._detect_indent(text)
        self.document().setModified(False)
        self.disk_mtime = self.path.stat().st_mtime

    def save(self, path=None):
        if path:
            self.path = Path(path)
            lang = languages.detect(path)
            if lang.id != self.lang.id:
                self.set_language(lang)
        text = self.toPlainText()
        if self.settings.get("trim_trailing"):
            text = "\n".join(l.rstrip() for l in text.split("\n"))
        if self.settings.get("final_newline") and text and not text.endswith("\n"):
            text += "\n"
        write_file(self.path, text, self.encoding, self.eol)
        self.document().setModified(False)
        self.disk_mtime = self.path.stat().st_mtime

    def reload(self):
        bar = self.verticalScrollBar().value()
        cur = self.textCursor().position()
        text, self.encoding, self.eol = read_file(self.path)
        c = self.textCursor()
        c.beginEditBlock()
        c.select(QTextCursor.Document)
        c.insertText(text)
        c.endEditBlock()
        c.setPosition(min(cur, len(text)))
        self.setTextCursor(c)
        self.verticalScrollBar().setValue(bar)
        self.document().setModified(False)
        self.disk_mtime = self.path.stat().st_mtime

    def _detect_indent(self, text):
        tabs = spaces = 0
        widths = {}
        for line in text.split("\n")[:2000]:
            if line.startswith("\t"):
                tabs += 1
            elif line.startswith("  "):
                spaces += 1
                n = len(line) - len(line.lstrip(" "))
                widths[n] = widths.get(n, 0) + 1
        if tabs > spaces:
            self.insert_spaces = False
        elif spaces:
            self.insert_spaces = True
            for w in (2, 4, 8):
                if widths.get(w) and not any(k % w for k in widths if widths[k] > 2):
                    self.tab_size = w
                    break
        self.setTabStopDistance(self.char_w * self.tab_size)

    @property
    def indent_unit(self):
        return " " * self.tab_size if self.insert_spaces else "\t"

    # ------------------------------------------------------------------ gutter
    def gutter_width(self):
        digits = max(3, len(str(max(1, self.blockCount()))))
        return int(18 + self.char_w * digits + 14)

    def _update_gutter_width(self, *_):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _update_gutter(self, rect, dy):
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def paint_gutter(self, event):
        p = QPainter(self.gutter)
        p.fillRect(event.rect(), QColor(self.c["gutter"]))
        block = self.firstVisibleBlock()
        n = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        current = self.textCursor().blockNumber()
        w = self.gutter.width() - 14
        h = self.fontMetrics().height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                p.setPen(QColor(self.c["line_no_active"] if n == current else self.c["line_no"]))
                p.drawText(0, top, w, h, Qt.AlignRight | Qt.AlignVCenter, str(n + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            n += 1

    # ------------------------------------------------------------------ painting: indent guides
    def paintEvent(self, e):
        if self.settings.get("indent_guides", True) and self.lineWrapMode() == QPlainTextEdit.NoWrap:
            self._paint_guides(e)
        super().paintEvent(e)

    def _paint_guides(self, e):
        p = QPainter(self.viewport())
        offset = self.contentOffset()
        x0 = offset.x() + self.document().documentMargin()
        step = self.char_w * self.tab_size
        block = self.firstVisibleBlock()
        cur = self.textCursor().block()
        cur_level = self._indent_level(cur.text()) if cur.text().strip() else 0
        prev_level = 0
        while block.isValid():
            geo = self.blockBoundingGeometry(block).translated(offset)
            if geo.top() > e.rect().bottom():
                break
            text = block.text()
            level = self._indent_level(text) if text.strip() else prev_level
            for i in range(1, level):
                active = cur_level and i == cur_level - 1 and abs(block.blockNumber() - cur.blockNumber()) < 400
                p.setPen(QColor(self.c["guide_active"] if active else self.c["guide"]))
                x = int(x0 + i * step)
                p.drawLine(x, int(geo.top()), x, int(geo.bottom()))
            prev_level = level if text.strip() else prev_level
            block = block.next()
        p.end()

    def _indent_level(self, text):
        width = 0
        for ch in text:
            if ch == " ":
                width += 1
            elif ch == "\t":
                width += self.tab_size - width % self.tab_size
            else:
                break
        return int(width // self.tab_size) + 1 if width else 0

    # ------------------------------------------------------------------ selections (current line, brackets, finds)
    def _cursor_changed(self):
        sels = []
        line = QTextEdit.ExtraSelection()
        line.format.setBackground(QColor(self.c["current_line"]))
        line.format.setProperty(QTextFormat.FullWidthSelection, True)
        line.cursor = self.textCursor()
        line.cursor.clearSelection()
        sels.append(line)
        sels += self.word_selections + self.find_selections + self._bracket_selections()
        self.setExtraSelections(sels)
        c = self.textCursor()
        self.cursor_moved.emit(c.blockNumber() + 1, c.positionInBlock() + 1)
        self.word_timer.start()
        self.gutter.update()

    def _bracket_selections(self):
        doc = self.document()
        pos = self.textCursor().position()
        for at in (pos - 1, pos):
            ch = doc.characterAt(at)
            if ch in "([{" or ch in ")]}":
                other = self._match_bracket(at, ch)
                if other is None:
                    continue
                out = []
                for p in (at, other):
                    s = QTextEdit.ExtraSelection()
                    s.format.setBackground(QColor(self.c["bracket"]))
                    s.cursor = QTextCursor(doc)
                    s.cursor.setPosition(p)
                    s.cursor.setPosition(p + 1, QTextCursor.KeepAnchor)
                    out.append(s)
                return out
        return []

    def _match_bracket(self, at, ch, limit=200_000):
        doc = self.document()
        if ch in "([{":
            open_, close, step = ch, PAIRS[ch], 1
        else:
            open_, close, step = CLOSERS[ch], ch, -1
        depth = 0
        i = at
        end = doc.characterCount()
        for _ in range(limit):
            c = doc.characterAt(i)
            if c == (open_ if step == 1 else close):
                depth += 1
            elif c == (close if step == 1 else open_):
                depth -= 1
                if depth == 0:
                    return i
            i += step
            if i < 0 or i >= end:
                return None
        return None

    def _highlight_word(self):
        self.word_selections = []
        c = self.textCursor()
        if not c.hasSelection():
            c.select(QTextCursor.WordUnderCursor)
        word = c.selectedText()
        if word and len(word) < 80 and re.fullmatch(r"\w+", word) and self.document().characterCount() < 500_000:
            doc = self.document()
            found = doc.find(word, 0, QTextDocument.FindCaseSensitively | QTextDocument.FindWholeWords)
            count = 0
            while not found.isNull() and count < 500:
                s = QTextEdit.ExtraSelection()
                s.format.setBackground(QColor(self.c["selected"]))
                s.cursor = found
                self.word_selections.append(s)
                found = doc.find(word, found, QTextDocument.FindCaseSensitively | QTextDocument.FindWholeWords)
                count += 1
            if count < 2:
                self.word_selections = []
        sels = [s for s in self.extraSelections()[:1]] + self.word_selections + self.find_selections + self._bracket_selections()
        self.setExtraSelections(sels)

    def set_find_matches(self, cursors, current=None):
        self.find_selections = []
        for cur in cursors:
            s = QTextEdit.ExtraSelection()
            is_cur = current is not None and cur.selectionStart() == current.selectionStart()
            s.format.setBackground(QColor(self.c["find_current"] if is_cur else self.c["find"]))
            s.cursor = cur
            self.find_selections.append(s)
        self._cursor_changed()

    # ------------------------------------------------------------------ editing helpers
    def _selected_blocks(self):
        c = self.textCursor()
        doc = self.document()
        first = doc.findBlock(c.selectionStart())
        last = doc.findBlock(c.selectionEnd())
        if c.hasSelection() and last.position() == c.selectionEnd() and last != first:
            last = last.previous()
        return first, last

    def _blocks(self, first, last):
        b = first
        while b.isValid():
            yield b
            if b == last:
                break
            b = b.next()

    def indent(self):
        first, last = self._selected_blocks()
        c = QTextCursor(self.document())
        c.beginEditBlock()
        for b in self._blocks(first, last):
            if b.text().strip() or first == last:
                c.setPosition(b.position())
                c.insertText(self.indent_unit)
        c.endEditBlock()

    def outdent(self):
        first, last = self._selected_blocks()
        c = QTextCursor(self.document())
        c.beginEditBlock()
        for b in self._blocks(first, last):
            text = b.text()
            n = 0
            if text.startswith("\t"):
                n = 1
            else:
                while n < self.tab_size and n < len(text) and text[n] == " ":
                    n += 1
            if n:
                c.setPosition(b.position())
                c.setPosition(b.position() + n, QTextCursor.KeepAnchor)
                c.removeSelectedText()
        c.endEditBlock()

    def toggle_comment(self):
        lang = self.lang
        first, last = self._selected_blocks()
        blocks = list(self._blocks(first, last))
        c = QTextCursor(self.document())
        if not lang.comment and lang.block:
            return self._toggle_block_comment(blocks, *lang.block)
        mark = lang.comment or "#"
        lines = [b for b in blocks if b.text().strip()]
        if not lines:
            return
        commented = all(b.text().lstrip().startswith(mark) for b in lines)
        col = min(len(b.text()) - len(b.text().lstrip()) for b in lines)
        c.beginEditBlock()
        for b in lines:
            text = b.text()
            if commented:
                i = text.index(mark)
                n = len(mark) + (1 if text[i + len(mark):i + len(mark) + 1] == " " else 0)
                c.setPosition(b.position() + i)
                c.setPosition(b.position() + i + n, QTextCursor.KeepAnchor)
                c.removeSelectedText()
            else:
                c.setPosition(b.position() + col)
                c.insertText(mark + " ")
        c.endEditBlock()

    def _toggle_block_comment(self, blocks, open_, close):
        first, last = blocks[0], blocks[-1]
        start, end = first.position(), last.position() + len(last.text())
        c = QTextCursor(self.document())
        c.setPosition(start)
        c.setPosition(end, QTextCursor.KeepAnchor)
        text = c.selectedText().replace(" ", "\n")
        stripped = text.strip()
        c.beginEditBlock()
        if stripped.startswith(open_) and stripped.endswith(close):
            inner = stripped[len(open_):len(stripped) - len(close)].strip(" ")
            lead = text[:len(text) - len(text.lstrip())]
            c.insertText(lead + inner)
        else:
            lead = text[:len(text) - len(text.lstrip())]
            c.insertText(f"{lead}{open_} {text.strip()} {close}")
        c.endEditBlock()

    def duplicate_lines(self, down=True):
        first, last = self._selected_blocks()
        c = QTextCursor(self.document())
        start, end = first.position(), last.position() + len(last.text())
        c.setPosition(start)
        c.setPosition(end, QTextCursor.KeepAnchor)
        text = c.selectedText().replace(" ", "\n")
        c.beginEditBlock()
        c.setPosition(end)
        c.insertText("\n" + text)
        c.endEditBlock()
        if down:
            cur = self.textCursor()
            shift = len(text) + 1
            a, p = cur.anchor() + shift, cur.position() + shift
            cur.setPosition(a)
            cur.setPosition(p, QTextCursor.KeepAnchor)
            self.setTextCursor(cur)

    def move_lines(self, direction):
        first, last = self._selected_blocks()
        doc = self.document()
        if direction < 0 and not first.previous().isValid():
            return
        if direction > 0 and not last.next().isValid():
            return
        cur = self.textCursor()
        anchor_off = cur.anchor() - first.position()
        pos_off = cur.position() - first.position()
        c = QTextCursor(doc)
        start, end = first.position(), last.position() + len(last.text())
        c.setPosition(start)
        c.setPosition(end, QTextCursor.KeepAnchor)
        text = c.selectedText().replace(" ", "\n")
        c.beginEditBlock()
        if direction < 0:
            prev = first.previous()
            new_start = prev.position()
            prev_text = prev.text()
            c.setPosition(new_start)
            c.setPosition(end, QTextCursor.KeepAnchor)
            c.insertText(text + "\n" + prev_text)
        else:
            nxt = last.next()
            c.setPosition(start)
            c.setPosition(nxt.position() + len(nxt.text()), QTextCursor.KeepAnchor)
            c.insertText(nxt.text() + "\n" + text)
            new_start = start + len(nxt.text()) + 1
        c.endEditBlock()
        cur.setPosition(new_start + anchor_off)
        cur.setPosition(new_start + pos_off, QTextCursor.KeepAnchor)
        self.setTextCursor(cur)

    def delete_lines(self):
        first, last = self._selected_blocks()
        c = QTextCursor(self.document())
        c.beginEditBlock()
        c.setPosition(first.position())
        if last.next().isValid():
            c.setPosition(last.next().position(), QTextCursor.KeepAnchor)
        else:
            c.setPosition(last.position() + len(last.text()), QTextCursor.KeepAnchor)
            if first.previous().isValid():
                start = first.previous().position() + len(first.previous().text())
                end = c.position()
                c.setPosition(start)
                c.setPosition(end, QTextCursor.KeepAnchor)
        c.removeSelectedText()
        c.endEditBlock()

    def select_line(self):
        c = self.textCursor()
        first, last = self._selected_blocks()
        c.setPosition(first.position())
        if last.next().isValid():
            c.setPosition(last.next().position(), QTextCursor.KeepAnchor)
        else:
            c.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        self.setTextCursor(c)

    def insert_line(self, below=True):
        c = self.textCursor()
        indent = re.match(r"\s*", c.block().text()).group(0)
        if below:
            c.movePosition(QTextCursor.EndOfBlock)
            c.insertText("\n" + indent)
        else:
            c.movePosition(QTextCursor.StartOfBlock)
            c.insertText(indent + "\n")
            c.movePosition(QTextCursor.PreviousBlock)
            c.movePosition(QTextCursor.EndOfBlock)
        self.setTextCursor(c)

    def goto_line(self, line, col=1):
        block = self.document().findBlockByNumber(max(0, line - 1))
        if not block.isValid():
            block = self.document().lastBlock()
        c = QTextCursor(block)
        c.movePosition(QTextCursor.Right, n=min(max(0, col - 1), len(block.text())))
        self.setTextCursor(c)
        self.centerCursor()
        self.setFocus()

    def select_range(self, start, end):
        c = self.textCursor()
        c.setPosition(start)
        c.setPosition(end, QTextCursor.KeepAnchor)
        self.setTextCursor(c)
        self.centerCursor()

    def transform(self, fn):
        c = self.textCursor()
        if not c.hasSelection():
            c.select(QTextCursor.WordUnderCursor)
        a, p = c.anchor(), c.position()
        c.insertText(fn(c.selectedText()))
        c.setPosition(a)
        c.setPosition(p, QTextCursor.KeepAnchor)
        self.setTextCursor(c)

    # ------------------------------------------------------------------ completion
    def _completion_prefix(self):
        c = self.textCursor()
        text = c.block().text()[:c.positionInBlock()]
        m = re.search(r"[\wÀ-￿]+$", text)
        return m.group(0) if m else ""

    def show_completions(self, explicit=False):
        prefix = self._completion_prefix()
        if len(prefix) < (1 if explicit else 3):
            self.completer.popup().hide()
            return
        text = self.toPlainText()
        if len(text) > 2_000_000:
            return
        words = {w for w in WORD_RE.findall(text) if w != prefix}
        self.completer.model().setStringList(sorted(words, key=str.lower))
        self.completer.setCompletionPrefix(prefix)
        if self.completer.completionCount() == 0:
            self.completer.popup().hide()
            return
        popup = self.completer.popup()
        popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
        rect = self.cursorRect()
        rect.translate(self.viewportMargins().left(), 4)
        rect.setWidth(popup.sizeHintForColumn(0) + popup.verticalScrollBar().sizeHint().width() + 24)
        self.completer.complete(rect)

    def _insert_completion(self, word):
        prefix = self._completion_prefix()
        c = self.textCursor()
        c.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, len(prefix))
        c.insertText(word)
        self.setTextCursor(c)

    # ------------------------------------------------------------------ keys
    def keyPressEvent(self, e):
        popup = self.completer.popup()
        key, mods, text = e.key(), e.modifiers(), e.text()
        if popup.isVisible() and key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab, Qt.Key_Escape, Qt.Key_Backtab):
            if key == Qt.Key_Tab:
                idx = popup.currentIndex()
                if idx.isValid():
                    self._insert_completion(idx.data())
                popup.hide()
                return
            e.ignore()
            return
        cursor = self.textCursor()
        plain = not (mods & (Qt.ControlModifier | Qt.MetaModifier | Qt.AltModifier))

        if key == Qt.Key_Tab and plain:
            if cursor.hasSelection() and self._selected_blocks()[0] != self._selected_blocks()[1]:
                self.indent()
            elif self.insert_spaces:
                col = cursor.positionInBlock()
                cursor.insertText(" " * (self.tab_size - col % self.tab_size))
            else:
                cursor.insertText("\t")
            return
        if key == Qt.Key_Backtab:
            self.outdent()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter) and not (mods & (Qt.ControlModifier | Qt.MetaModifier)):
            self._newline()
            return
        if key == Qt.Key_Backspace and plain and not cursor.hasSelection():
            if self._smart_backspace(cursor):
                return
        if key == Qt.Key_Home and not (mods & (Qt.ControlModifier | Qt.MetaModifier)):
            self._smart_home(bool(mods & Qt.ShiftModifier))
            return
        if text and self.settings.get("auto_close", True) and (plain or mods == Qt.ShiftModifier):
            if self._auto_pair(text, cursor):
                return
        super().keyPressEvent(e)
        if text == "}" or text == "]" or text == ")":
            self._dedent_closer(text)
        if self.settings.get("autocomplete", True):
            if text and (text.isalnum() or text == "_"):
                self.show_completions()
            elif popup.isVisible() and key not in (Qt.Key_Up, Qt.Key_Down):
                self.show_completions(explicit=True) if self._completion_prefix() else popup.hide()

    def _newline(self):
        c = self.textCursor()
        block_text = c.block().text()
        before = block_text[:c.positionInBlock()]
        after = block_text[c.positionInBlock():]
        indent = re.match(r"[ \t]*", block_text).group(0)
        if c.hasSelection():
            c.removeSelectedText()
        opener = before.rstrip()[-1:] if before.strip() else ""
        extra = bool(opener) and opener in (self.lang.indent_after or "{[(")
        if self.lang.id == "python" and opener != ":":
            extra = bool(opener) and opener in "{[("
        c.beginEditBlock()
        if extra and after.strip()[:1] == PAIRS.get(opener, "\0"):
            c.insertText("\n" + indent + self.indent_unit + "\n" + indent)
            c.movePosition(QTextCursor.Up)
            c.movePosition(QTextCursor.EndOfBlock)
        else:
            # drop trailing spaces of the split line
            c.insertText("\n" + indent + (self.indent_unit if extra else ""))
            if after.startswith(" ") and not after.strip():
                c.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                c.removeSelectedText()
        c.endEditBlock()
        self.setTextCursor(c)
        self.ensureCursorVisible()

    def _smart_backspace(self, c):
        pos = c.positionInBlock()
        text = c.block().text()
        before, after = text[:pos], text[pos:]
        if before and after and PAIRS.get(before[-1]) == after[0]:
            c.beginEditBlock()
            c.deletePreviousChar()
            c.deleteChar()
            c.endEditBlock()
            return True
        if before and not before.strip(" ") and self.insert_spaces and len(before) >= 1 and "\t" not in before:
            n = (len(before) - 1) % self.tab_size + 1
            c.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, n)
            c.removeSelectedText()
            return True
        return False

    def _smart_home(self, select):
        c = self.textCursor()
        text = c.block().text()
        first = len(text) - len(text.lstrip())
        target = 0 if c.positionInBlock() == first else first
        mode = QTextCursor.KeepAnchor if select else QTextCursor.MoveAnchor
        c.setPosition(c.block().position() + target, mode)
        self.setTextCursor(c)

    def _auto_pair(self, ch, c):
        nxt = self.document().characterAt(c.position())
        prev = self.document().characterAt(c.position() - 1) if c.position() else ""
        if c.hasSelection() and ch in PAIRS:
            sel = c.selectedText()
            c.insertText(ch + sel + PAIRS[ch])
            return True
        if ch in CLOSERS or ch in "\"'`":
            if nxt == ch and not c.hasSelection():
                c.movePosition(QTextCursor.Right)
                self.setTextCursor(c)
                return True
        if ch in PAIRS:
            if ch in "\"'`":
                if prev and (prev.isalnum() or prev == "_" or prev == ch):
                    return False
                if self.lang.id in ("text", "markdown") and ch != '"':
                    return False
            if nxt and not (nxt.isspace() or nxt in ")]};:,." or nxt == " "):
                return False
            c.insertText(ch + PAIRS[ch])
            c.movePosition(QTextCursor.Left)
            self.setTextCursor(c)
            return True
        return False

    def _dedent_closer(self, ch):
        c = self.textCursor()
        text = c.block().text()
        if text.strip() != ch:
            return
        # align with the line holding the matching bracket
        other = self._match_bracket(c.position() - 1, ch)
        if other is None:
            return
        target = re.match(r"[ \t]*", self.document().findBlock(other).text()).group(0)
        cur = re.match(r"[ \t]*", text).group(0)
        if cur != target:
            c.beginEditBlock()
            c.movePosition(QTextCursor.StartOfBlock)
            c.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(cur))
            c.insertText(target)
            c.endEditBlock()
            c.movePosition(QTextCursor.EndOfBlock)
            self.setTextCursor(c)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            size = int(self.settings.get("font_size", 13)) + (1 if e.angleDelta().y() > 0 else -1)
            self.window().set_font_size(size) if hasattr(self.window(), "set_font_size") else None
            return
        super().wheelEvent(e)

    def focusInEvent(self, e):
        super().focusInEvent(e)
        w = self.window()
        if hasattr(w, "editor_focused"):
            w.editor_focused(self)

    # ------------------------------------------------------------------ find
    def find_all(self, pattern, case=False, regex=False, word=False, limit=20000):
        """All matches as QTextCursors."""
        doc = self.document()
        flags = QTextDocument.FindFlag(0)
        if case:
            flags |= QTextDocument.FindCaseSensitively
        if word:
            flags |= QTextDocument.FindWholeWords
        out = []
        if not pattern:
            return out
        if regex:
            from PySide6.QtCore import QRegularExpression

            rx = QRegularExpression(pattern)
            if not case:
                rx.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
            if not rx.isValid():
                return out
            needle = rx
        else:
            needle = pattern
        cur = doc.find(needle, 0, flags)
        while not cur.isNull() and len(out) < limit:
            if cur.selectionStart() == cur.selectionEnd():  # empty regex match
                nxt = QTextCursor(doc)
                nxt.setPosition(cur.position() + 1)
                if nxt.position() >= doc.characterCount() - 1:
                    break
                cur = doc.find(needle, nxt, flags)
                continue
            out.append(cur)
            cur = doc.find(needle, cur, flags)
        return out


def clean_shortcut(seq):
    return QKeySequence(seq).toString(QKeySequence.NativeText)
