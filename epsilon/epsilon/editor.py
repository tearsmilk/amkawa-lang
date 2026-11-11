"""Markdown editor: syntax highlighting (incl. code inside fences), smart paste of code,
drag & drop of files/images into the vault, and a Notion-style "/" block menu."""
import re
from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QSyntaxHighlighter, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QMenu, QPlainTextEdit

from . import attachments as att
from .codedetect import detect_language, looks_like_code

MONO = QFont("Menlo")
MONO.setStyleHint(QFont.Monospace)

BLOCKS = [
    ("Заголовок 1", "# ", ""), ("Заголовок 2", "## ", ""), ("Заголовок 3", "### ", ""),
    ("Задача", "- [ ] ", ""), ("Список", "- ", ""), ("Нумерованный список", "1. ", ""),
    ("Цитата", "> ", ""), ("Выноска", "> [!note] ", "\n> "), ("Блок кода", "```", "\n\n```"),
    ("Таблица", "| Колонка 1 | Колонка 2 |\n|---|---|\n| ", " |  |"), ("Разделитель", "---\n", ""),
    ("Ссылка на заметку", "[[", "]]"), ("Вложение: файл, фото, видео, GIF…", "@attach", ""),
    ("Сегодняшняя дата", "@date", ""),
]
# shown inline (photo, GIF) or as a player card (video, audio) in the reader
EMBED_KINDS = {"image", "gif", "video", "audio"}


class MarkdownHighlighter(QSyntaxHighlighter):
    def __init__(self, document, colors):
        super().__init__(document)
        self.set_colors(colors)

    def set_colors(self, c):
        self.c = c

        def fmt(color=None, bold=False, italic=False, mono=False, bg=None, size=None):
            f = QTextCharFormat()
            if color:
                f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.DemiBold)
            if italic:
                f.setFontItalic(True)
            if mono:
                f.setFontFamilies(["Menlo", "Monaco", "Courier New"])
            if bg:
                f.setBackground(QColor(bg))
            if size:
                f.setProperty(QTextCharFormat.FontSizeAdjustment, size)
            return f

        self.f_h = [fmt(c["text"], bold=True, size=s) for s in (3, 2, 1, 0, 0, 0)]
        self.f_mark = fmt(c["muted"])
        self.f_bold = fmt(bold=True)
        self.f_italic = fmt(italic=True)
        self.f_code = fmt(c["code_inline"], mono=True, bg=c["code_bg"])
        self.f_block = fmt(c["text"], mono=True, bg=c["code_bg"])
        self.f_fence = fmt(c["muted"], mono=True, bg=c["code_bg"])
        self.f_link = fmt(c["accent"])
        self.f_tag = fmt(c["accent"], bg=c["tag_bg"])
        self.f_quote = fmt(c["muted"], italic=True)
        self.f_task_done = fmt(c["muted"])
        self._lexers = {}
        self._token_formats = {}
        try:
            from pygments.styles import get_style_by_name

            self._style = get_style_by_name(c.get("code_style", "default"))
        except Exception:
            self._style = None
        self.rehighlight()

    def _lexer(self, lang):
        if lang not in self._lexers:
            try:
                from pygments.lexers import get_lexer_by_name

                self._lexers[lang] = get_lexer_by_name(lang, stripnl=False, ensurenl=False)
            except Exception:
                self._lexers[lang] = None
        return self._lexers[lang]

    def _token_format(self, ttype):
        if ttype in self._token_formats:
            return self._token_formats[ttype]
        f = QTextCharFormat(self.f_block)
        if self._style is not None:
            try:
                st = self._style.style_for_token(ttype)
                if st.get("color"):
                    f.setForeground(QColor("#" + st["color"]))
                if st.get("bold"):
                    f.setFontWeight(QFont.DemiBold)
                if st.get("italic"):
                    f.setFontItalic(True)
            except Exception:
                pass
        self._token_formats[ttype] = f
        return f

    def highlightBlock(self, text):
        prev = self.previousBlockState()
        # state: -1/0 normal; >=1 inside code fence, value = index into self._langs + 1
        if not hasattr(self, "_langs"):
            self._langs = [""]
        stripped = text.strip()
        if prev >= 1:
            if stripped.startswith("```") or stripped.startswith("~~~"):
                self.setFormat(0, len(text), self.f_fence)
                self.setCurrentBlockState(0)
                return
            self.setFormat(0, len(text), self.f_block)
            lang = self._langs[prev - 1]
            lexer = self._lexer(lang) if lang else None
            if lexer is not None:
                pos = 0
                for ttype, value in lexer.get_tokens(text):
                    n = len(value.rstrip("\n")) if value.endswith("\n") else len(value)
                    if n:
                        self.setFormat(pos, n, self._token_format(ttype))
                    pos += len(value)
            self.setCurrentBlockState(prev)
            return
        m = re.match(r"^\s*(```|~~~)\s*([\w+#.-]*)", text)
        if m:
            lang = m.group(2).lower()
            if lang not in self._langs:
                self._langs.append(lang)
            self.setFormat(0, len(text), self.f_fence)
            self.setCurrentBlockState(self._langs.index(lang) + 1)
            return
        self.setCurrentBlockState(0)
        h = re.match(r"^(#{1,6})\s", text)
        if h:
            self.setFormat(0, len(text), self.f_h[len(h.group(1)) - 1])
            self.setFormat(0, len(h.group(1)), self.f_mark)
            return
        if text.startswith(">"):
            self.setFormat(0, len(text), self.f_quote)
        t = re.match(r"^\s*[-*+]\s\[[xX]\]\s", text)
        if t:
            self.setFormat(0, len(text), self.f_task_done)
        for rx, f in ((r"\*\*[^*]+\*\*|__[^_]+__", self.f_bold), (r"(?<![*\w])\*[^*\n]+\*(?!\*)|(?<![_\w])_[^_\n]+_(?!_)", self.f_italic),
                      (r"\[\[[^\]]+\]\]", self.f_link), (r"!?\[[^\]]*\]\([^)]+\)", self.f_link),
                      (r"https?://\S+", self.f_link),
                      (r"(?<![\w#/&])#[A-Za-zА-Яа-яЁё0-9_][\wА-Яа-яЁё/-]*", self.f_tag), (r"`[^`]+`", self.f_code)):
            for mm in re.finditer(rx, text):
                self.setFormat(mm.start(), mm.end() - mm.start(), f)


class MarkdownEditor(QPlainTextEdit):
    """`vault` is used to store pasted / dropped files as attachments."""

    status = Signal(str)
    attach_requested = Signal()

    def __init__(self, vault, note_path, colors):
        super().__init__()
        self.setObjectName("Editor")
        self.vault = vault
        self.note_path = Path(note_path)
        self.setTabStopDistance(28)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.document().setDocumentMargin(28)
        self.highlighter = MarkdownHighlighter(self.document(), colors)

    def set_colors(self, colors):
        self.highlighter.set_colors(colors)

    # ---------------------------------------------------------------- helpers
    def _in_code_fence(self):
        block = self.textCursor().block()
        return block.previous().userState() >= 1 if block.previous().isValid() else False

    def _link_for(self, path: Path):
        target = str(Path(path).relative_to(self.vault.root)).replace(" ", "%20")
        # links are relative to the note's folder so they work in any Markdown app
        try:
            import os

            target = os.path.relpath(path, self.note_path.parent).replace(" ", "%20")
        except ValueError:
            pass
        if att.kind_of(path) in EMBED_KINDS:
            return f"![{Path(path).stem}]({target})"
        return f"[{Path(path).name}]({target})"

    def insert_files(self, paths):
        links = []
        for p in paths:
            try:
                dest = self.vault.import_file(p)
                links.append(self._link_for(dest))
            except Exception as exc:
                self.status.emit(f"Не удалось добавить {Path(p).name}: {exc}")
        if links:
            # every attachment on its own line, so the reader shows it as a picture / card
            cursor = self.textCursor()
            prefix = "\n" if cursor.block().text()[:cursor.positionInBlock()].strip() else ""
            cursor.insertText(prefix + "\n".join(links) + "\n")
            self.setTextCursor(cursor)
            self.status.emit(f"Прикреплено файлов: {len(links)} → attachments")

    # ---------------------------------------------------------------- paste / drop
    def canInsertFromMimeData(self, source):
        return source.hasUrls() or source.hasImage() or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source: QMimeData):
        if source.hasUrls() and all(u.isLocalFile() for u in source.urls()):
            self.insert_files([u.toLocalFile() for u in source.urls() if Path(u.toLocalFile()).is_file()])
            return
        if source.hasImage() and not source.hasText():
            from PySide6.QtCore import QBuffer, QByteArray, QIODevice

            image = source.imageData()
            data = QByteArray()
            buf = QBuffer(data)
            buf.open(QIODevice.WriteOnly)
            image.save(buf, "PNG")
            dest = self.vault.save_image_bytes(bytes(data), "png")
            self.textCursor().insertText(self._link_for(dest) + "\n")
            self.status.emit("Картинка сохранена в attachments")
            return
        text = source.text()
        if re.fullmatch(r"https?://\S+", text.strip() or "-"):
            cursor = self.textCursor()
            if cursor.hasSelection():
                cursor.insertText(f"[{cursor.selectedText()}]({text.strip()})")
            else:
                cursor.insertText(f"<{text.strip()}>")
            return
        if not self._in_code_fence() and looks_like_code(text):
            lang = detect_language(text)
            code = text.strip("\n")
            cursor = self.textCursor()
            prev = cursor.block().previous()
            if cursor.positionInBlock():
                prefix = "\n\n"
            else:
                prefix = "\n" if prev.isValid() and prev.text().strip() else ""
            cursor.insertText(f"{prefix}```{lang}\n{code}\n```\n")
            self.status.emit(f"Код оформлен как {lang}")
            return
        super().insertFromMimeData(source)

    # ---------------------------------------------------------------- keys
    def keyPressEvent(self, event):
        cursor = self.textCursor()
        key, mods = event.key(), event.modifiers()
        if event.text() == "/" and not cursor.block().text()[:cursor.positionInBlock()].strip() \
                and not self._in_code_fence():
            super().keyPressEvent(event)
            QTimer.singleShot(0, self._slash_menu)
            return
        if key in (Qt.Key_Return, Qt.Key_Enter) and not mods & ~Qt.KeypadModifier:
            if self._continue_list():
                return
        if key == Qt.Key_Tab and not self._in_code_fence() and self._indent_list(+1):
            return
        if key == Qt.Key_Backtab and self._indent_list(-1):
            return
        if event.matches(QKeySequence.Bold):
            return self._wrap("**")
        if event.matches(QKeySequence.Italic):
            return self._wrap("*")
        if mods & Qt.ControlModifier and key == Qt.Key_K:
            return self._wrap("[", "](https://)")
        super().keyPressEvent(event)

    def _wrap(self, left, right=None):
        right = left if right is None else right
        c = self.textCursor()
        text = c.selectedText()
        c.insertText(f"{left}{text}{right}")
        if not text:
            c.movePosition(QTextCursor.Left, n=len(right))
            self.setTextCursor(c)

    def _continue_list(self):
        c = self.textCursor()
        line = c.block().text()
        m = re.match(r"^(\s*)([-*+]\s\[[ xX]\]\s|[-*+]\s|(\d+)\.\s|>\s?)", line)
        if not m or self._in_code_fence() or c.positionInBlock() < len(m.group(0)):
            return False
        if line.strip() == m.group(0).strip():  # empty item → end the list
            c.movePosition(QTextCursor.StartOfBlock)
            c.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            c.insertText("")
            return True
        marker = m.group(2)
        if m.group(3):
            marker = f"{int(m.group(3)) + 1}. "
        elif "[" in marker:
            marker = marker[0] + " [ ] "
        c.insertText("\n" + m.group(1) + marker)
        return True

    def _indent_list(self, direction):
        c = self.textCursor()
        line = c.block().text()
        if not re.match(r"^\s*([-*+]|\d+\.)\s", line):
            return False
        c.movePosition(QTextCursor.StartOfBlock)
        if direction > 0:
            c.insertText("  ")
        else:
            n = len(line) - len(line.lstrip(" "))
            for _ in range(min(2, n)):
                c.deleteChar()
        return True

    def _slash_menu(self):
        menu = QMenu(self)
        for title, before, after in BLOCKS:
            act = menu.addAction(title)
            act.setData((before, after))
        rect = self.cursorRect()
        chosen = menu.exec(self.viewport().mapToGlobal(rect.bottomLeft()))
        if not chosen:
            return
        before, after = chosen.data()
        c = self.textCursor()
        c.deletePreviousChar()  # remove the "/"
        if before == "@attach":
            QTimer.singleShot(0, self.attach_requested.emit)
            return
        if before == "@date":
            import datetime as dt

            c.insertText(dt.date.today().strftime("%d.%m.%Y"))
            return
        c.insertText(before + after)
        if after:
            c.movePosition(QTextCursor.Left, n=len(after))
        self.setTextCursor(c)
