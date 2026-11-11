"""Syntax highlighting with Pygments for the whole document (so multi-line strings / comments are right).

The document is re-lexed in the background of typing (debounced); only lines whose colours changed are
re-highlighted.
"""
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from pygments.token import Comment, Error, Generic, Keyword, Literal, Name, Number, Operator, Punctuation, String

from .theme import SYNTAX

MAX_CHARS = 3_000_000  # bigger files are shown without colours


def token_kind(ttype):
    """Pygments token type → colour key of theme.SYNTAX (or None)."""
    checks = (
        (Comment, "comment"), (String.Escape, "string_escape"), (String.Regex, "regex"), (String.Interpol, "string_escape"),
        (String, "string"), (Number, "number"), (Keyword.Type, "keyword_type"), (Keyword.Constant, "constant"),
        (Keyword.Namespace, "keyword"), (Keyword, "keyword"), (Name.Function, "function"), (Name.Class, "class_"),
        (Name.Exception, "class_"), (Name.Builtin.Pseudo, "constant"), (Name.Builtin, "builtin"),
        (Name.Decorator, "decorator"), (Name.Tag, "tag"), (Name.Attribute, "attribute"), (Name.Constant, "constant"),
        (Name.Variable, "variable"), (Name.Namespace, "namespace"), (Name.Label, "decorator"), (Name.Entity, "constant"),
        (Name.Property, "attribute"), (Operator.Word, "keyword"), (Operator, "operator"), (Punctuation, "punctuation"),
        (Generic.Heading, "heading"), (Generic.Subheading, "heading"), (Generic.Emph, "emph"),
        (Generic.Strong, "strong"), (Generic.Inserted, "inserted"), (Generic.Deleted, "deleted"),
        (Literal, "string"),
    )
    for base, kind in checks:
        if ttype in base:
            return kind
    if ttype in Error:
        return None
    return None


class SyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, document, colors):
        super().__init__(document)
        self.lexer = None
        self.spans = []  # per line: [(start, length, kind)]
        self._kinds = {}
        self.formats = {}
        self.timer = QTimer(self, singleShot=True, interval=120, timeout=self.relex)
        document.contentsChange.connect(self._changed)
        self.set_colors(colors)

    # ------------------------------------------------------------------ setup
    def set_colors(self, colors):
        palette = SYNTAX[colors.get("name", "light")]
        self.formats = {}
        for kind, (color, bold, italic) in palette.items():
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.DemiBold)
            if italic:
                f.setFontItalic(True)
            self.formats[kind] = f
        self.rehighlight()

    def set_lexer(self, alias):
        try:
            from pygments.lexers import get_lexer_by_name

            self.lexer = None if alias == "text" else get_lexer_by_name(alias, stripnl=False, ensurenl=False,
                                                                       stripall=False, tabsize=0)
        except Exception:
            self.lexer = None
        self.relex(force=True)

    # ------------------------------------------------------------------ lexing
    def _changed(self, position, removed, added):
        # keep spans aligned with lines until the next re-lex: shift them by the number of added / removed lines
        delta = self.document().blockCount() - len(self.spans)
        if delta and self.spans:
            line = self.document().findBlock(position).blockNumber()
            if delta > 0:
                self.spans[line + 1:line + 1] = [[] for _ in range(delta)]
            else:
                del self.spans[line + 1:line + 1 - delta]
        n = self.document().characterCount()
        self.timer.setInterval(120 if n < 200_000 else 400)
        self.timer.start()

    def lex(self, text):
        """Spans per line for `text` (also used by the self-test)."""
        lines = [[]]
        if self.lexer is None or len(text) > MAX_CHARS:
            return [[] for _ in range(text.count("\n") + 1)]
        col = 0
        for _pos, ttype, value in self.lexer.get_tokens_unprocessed(text):
            kind = self._kinds.get(ttype, False)
            if kind is False:
                kind = self._kinds[ttype] = token_kind(ttype)
            parts = value.split("\n")
            for i, part in enumerate(parts):
                if i:
                    lines.append([])
                    col = 0
                if part and kind:
                    line = lines[-1]
                    if line and line[-1][2] == kind and line[-1][0] + line[-1][1] == col:
                        line[-1] = (line[-1][0], line[-1][1] + len(part), kind)
                    else:
                        line.append((col, len(part), kind))
                col += len(part)
        return lines

    def relex(self, force=False):
        doc = self.document()
        new = self.lex(doc.toPlainText())
        old = self.spans
        self.spans = new
        if force or len(old) != len(new):
            self.rehighlight()
            return
        changed = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
        if len(changed) > 400:
            self.rehighlight()
            return
        for i in changed:
            block = doc.findBlockByNumber(i)
            if block.isValid():
                self.rehighlightBlock(block)

    def highlightBlock(self, text):
        n = self.currentBlock().blockNumber()
        if n >= len(self.spans):
            return
        size = len(text)
        for start, length, kind in self.spans[n]:
            if start >= size:
                break
            f = self.formats.get(kind)
            if f is not None:
                self.setFormat(start, min(length, size - start), f)
