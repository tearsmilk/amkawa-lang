"""Integrated terminal: the user's shell in a pseudo-terminal, screen emulated by pyte (xterm subset),
drawn with QPainter. Scrollback, selection + copy, paste, 256 colours / true colour, alternate screen."""
import copy
import fcntl
import os
import pty
import signal
import struct
import sys
import termios
from collections import deque

import pyte
from PySide6.QtCore import QPoint, QSocketNotifier, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

from .editor import mono_font
from .theme import ANSI

MAC = sys.platform == "darwin"
COLOR_NAMES = ["black", "red", "green", "brown", "blue", "magenta", "cyan", "white"]
BRACKETED_PASTE = 2004 << 5
APP_CURSOR = 1 << 5
ALT_SCREENS = (47, 1047, 1049)


class TermScreen(pyte.Screen):
    """pyte screen + scrollback + alternate screen buffer."""

    def __init__(self, columns, lines, history=5000):
        super().__init__(columns, lines)
        self.scrollback = deque(maxlen=history)
        self.alt = None  # saved main buffer while a full-screen app (vim, less, htop) runs

    def index(self):
        top, bottom = self.margins or pyte.screens.Margins(0, self.lines - 1)
        if self.cursor.y == bottom and top == 0 and self.alt is None:
            line = self.buffer[0]
            self.scrollback.append({x: line[x] for x in line})
        super().index()

    def set_mode(self, *modes, **kwargs):
        if kwargs.get("private") and any(m in ALT_SCREENS for m in modes) and self.alt is None:
            self.alt = (copy.deepcopy(dict(self.buffer)), copy.copy(self.cursor))
            self.buffer.clear()
            self.dirty.update(range(self.lines))
        super().set_mode(*modes, **kwargs)

    def reset_mode(self, *modes, **kwargs):
        if kwargs.get("private") and any(m in ALT_SCREENS for m in modes) and self.alt is not None:
            buf, cursor = self.alt
            self.alt = None
            self.buffer.clear()
            self.buffer.update(buf)
            self.cursor = cursor
            self.dirty.update(range(self.lines))
        super().reset_mode(*modes, **kwargs)


class TerminalWidget(QWidget):
    title_changed = Signal(str)
    finished = Signal(int)

    def __init__(self, colors, settings, cwd=None, shell=None):
        super().__init__()
        self.setObjectName("Terminal")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_InputMethodEnabled, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setMouseTracking(False)
        self.c = colors
        self.settings = settings
        self.cwd = cwd or os.path.expanduser("~")
        self.shell = shell or settings.get("shell") or None
        self.pid = None
        self.fd = None
        self.notifier = None
        self.scroll = 0          # lines scrolled back
        self.sel = None          # ((row, col), (row, col)) in absolute rows
        self._drag = None
        self.alive = False
        self.apply_font()
        self.term = TermScreen(80, 24)
        self.stream = pyte.ByteStream(self.term)
        self.term.write_process_input = self._reply
        self.repaint_timer = QTimer(self, singleShot=True, interval=12, timeout=self.update)
        self.start()

    # ------------------------------------------------------------------ process
    def start(self):
        from .paths import default_shell

        shell = self.shell or default_shell()
        cols, rows = self._grid_size()
        self.term.resize(rows, cols)
        env = dict(os.environ)
        env.update(TERM="xterm-256color", COLORTERM="truecolor", TERM_PROGRAM="Nu", LANG=env.get("LANG") or "ru_RU.UTF-8",
                   LC_CTYPE=env.get("LC_CTYPE") or "UTF-8")
        env.pop("PYTHONHOME", None)
        env.pop("PYTHONPATH", None)
        pid, fd = pty.fork()
        if pid == 0:  # child
            try:
                os.chdir(self.cwd)
            except OSError:
                pass
            name = os.path.basename(shell)
            try:
                os.execvpe(shell, ["-" + name], env)  # login shell, like Terminal.app
            except OSError:
                os.execvpe("/bin/sh", ["-sh"], env)
            os._exit(127)
        self.pid, self.fd = pid, fd
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        self._set_winsize(rows, cols)
        self.notifier = QSocketNotifier(fd, QSocketNotifier.Read, self)
        self.notifier.activated.connect(self._read)
        self.alive = True

    def _set_winsize(self, rows, cols):
        if self.fd is not None:
            try:
                fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
            except OSError:
                pass

    def _read(self, *_):
        try:
            data = os.read(self.fd, 65536)
        except BlockingIOError:
            return
        except OSError:
            data = b""
        if not data:
            self._ended()
            return
        self.stream.feed(data)
        if self.term.title:
            self.title_changed.emit(self.term.title)
            self.term.title = ""
        self.scroll = 0
        if not self.repaint_timer.isActive():
            self.repaint_timer.start()

    def _ended(self):
        if not self.alive:
            return
        self.alive = False
        if self.notifier:
            self.notifier.setEnabled(False)
        code = 0
        try:
            _pid, status = os.waitpid(self.pid, os.WNOHANG)
            code = os.waitstatus_to_exitcode(status) if _pid else 0
        except (ChildProcessError, OSError, ValueError):
            pass
        try:
            os.close(self.fd)
        except OSError:
            pass
        self.stream.feed("\r\n\x1b[2m[процесс завершён — нажмите Enter, чтобы перезапустить]\x1b[0m".encode())
        self.update()
        self.finished.emit(code)

    def _reply(self, data):
        self.send(data.encode() if isinstance(data, str) else data)

    def send(self, data):
        if isinstance(data, str):
            data = data.encode("utf-8")
        if not self.alive:
            return
        try:
            os.write(self.fd, data)
        except OSError:
            pass

    def run(self, command):
        """Type a command and press Enter (used by «Запустить файл»)."""
        if not self.alive:
            self.restart()
        self.send(command + "\r")

    def restart(self):
        self.close_process()
        self.term.reset()
        self.term.scrollback.clear()
        self.start()
        self.update()

    def close_process(self):
        if self.alive and self.pid:
            try:
                os.killpg(os.getpgid(self.pid), signal.SIGHUP)
            except (OSError, ProcessLookupError):
                try:
                    os.kill(self.pid, signal.SIGHUP)
                except OSError:
                    pass
        if self.notifier:
            self.notifier.setEnabled(False)
        if self.alive:
            try:
                os.close(self.fd)
            except OSError:
                pass
            try:
                os.waitpid(self.pid, os.WNOHANG)
            except OSError:
                pass
        self.alive = False

    def busy(self):
        """True when something other than the shell runs in the foreground."""
        if not self.alive:
            return False
        try:
            return os.tcgetpgrp(self.fd) != self.pid
        except OSError:
            return False

    # ------------------------------------------------------------------ geometry / looks
    def apply_font(self):
        self.font_ = mono_font(self.settings.get("font_family", ""), int(self.settings.get("terminal_font_size", 12)))
        self.bold_font = QFont(self.font_)
        self.bold_font.setBold(True)
        fm = QFontMetricsF(self.font_)
        self.cw = fm.horizontalAdvance("M")
        self.ch = round(fm.height() + 2)
        self.ascent = fm.ascent() + 1
        if hasattr(self, "term"):
            self.resizeEvent(None)
        self.update()

    def set_colors(self, colors):
        self.c = colors
        self.update()

    def _grid_size(self):
        cols = max(10, int((self.width() - 16) // self.cw))
        rows = max(3, int((self.height() - 8) // self.ch))
        return cols, rows

    def resizeEvent(self, e):
        cols, rows = self._grid_size()
        if (cols, rows) != (self.term.columns, self.term.lines):
            self.term.resize(rows, cols)
            self._set_winsize(rows, cols)
        self.update()

    def _color(self, name, fg, bold=False):
        pal = ANSI[self.c.get("name", "light")]
        if name == "default":
            return QColor(self.c["terminal_text"] if fg else self.c["terminal"])
        if name in COLOR_NAMES:
            i = COLOR_NAMES.index(name)
            return QColor(pal[i + 8 if bold and fg else i])
        if name.startswith("bright"):
            base = name[6:]
            base = "brown" if base == "yellow" else base
            if base in COLOR_NAMES:
                return QColor(pal[COLOR_NAMES.index(base) + 8])
        if len(name) == 6:
            try:
                return QColor("#" + name)
            except Exception:
                pass
        return QColor(self.c["terminal_text"] if fg else self.c["terminal"])

    # ------------------------------------------------------------------ painting
    def _rows(self):
        """Visible rows: list of (absolute row, line dict)."""
        sb = self.term.scrollback
        lines = self.term.lines
        start = len(sb) - self.scroll
        out = []
        for i in range(lines):
            r = start + i
            if r < len(sb):
                out.append((r, sb[r]))
            else:
                out.append((r, self.term.buffer[r - len(sb)]))
        return out

    def paintEvent(self, e):
        p = QPainter(self)
        bg = QColor(self.c["terminal"])
        p.fillRect(self.rect(), bg)
        default = self.term.default_char
        x0, y0 = 8, 4
        sel = self._sel_range()
        for i, (absrow, line) in enumerate(self._rows()):
            y = y0 + i * self.ch
            col = 0
            cols = self.term.columns
            while col < cols:
                ch = line.get(col, default) if isinstance(line, dict) else line[col]
                # group equal attributes into one run
                run = [ch.data]
                end = col + 1
                while end < cols:
                    nxt = line.get(end, default) if isinstance(line, dict) else line[end]
                    if (nxt.fg, nxt.bg, nxt.bold, nxt.reverse, nxt.underscore, nxt.italics) != \
                            (ch.fg, ch.bg, ch.bold, ch.reverse, ch.underscore, ch.italics):
                        break
                    run.append(nxt.data)
                    end += 1
                fg = self._color(ch.fg, True, ch.bold)
                back = self._color(ch.bg, False)
                if ch.reverse:
                    fg, back = back, fg
                if back != bg:
                    p.fillRect(int(x0 + col * self.cw), y, int((end - col) * self.cw + 1), self.ch, back)
                text = "".join(run)
                if text.strip():
                    p.setFont(self.bold_font if ch.bold else self.font_)
                    p.setPen(fg)
                    # draw cell by cell positions to keep the grid exact with wide / fallback glyphs
                    for k, glyph in enumerate(run):
                        if glyph and glyph != " ":
                            p.drawText(int(x0 + (col + k) * self.cw), int(y + self.ascent), glyph)
                    if ch.underscore:
                        p.drawLine(int(x0 + col * self.cw), y + self.ch - 2, int(x0 + end * self.cw), y + self.ch - 2)
                col = end
            if sel:
                (r1, c1), (r2, c2) = sel
                if r1 <= absrow <= r2:
                    a = c1 if absrow == r1 else 0
                    b = c2 if absrow == r2 else self.term.columns
                    sc = QColor(self.c["selection"])
                    sc.setAlpha(150)
                    p.fillRect(int(x0 + a * self.cw), y, int((b - a) * self.cw), self.ch, sc)
        # cursor
        if self.scroll == 0 and not self.term.cursor.hidden and self.alive:
            cx = int(x0 + self.term.cursor.x * self.cw)
            cy = y0 + self.term.cursor.y * self.ch
            cur = QColor(self.c["accent"])
            if self.hasFocus():
                cur.setAlpha(170)
                p.fillRect(cx, cy, int(self.cw), self.ch, cur)
            else:
                p.setPen(cur)
                p.drawRect(cx, cy, int(self.cw) - 1, self.ch - 1)
        p.end()

    # ------------------------------------------------------------------ keyboard
    def event(self, e):
        # Tab / Backtab must reach the shell (completion), not move focus
        if e.type() == e.Type.KeyPress and e.key() in (Qt.Key_Tab, Qt.Key_Backtab):
            self.keyPressEvent(e)
            return True
        # Control-key combos belong to the shell (^C, ^R, ^G…), not to the app's menu shortcuts.
        # On macOS that is the physical ⌃ key (Qt: Meta); ⌘ shortcuts keep working.
        if e.type() == e.Type.ShortcutOverride:
            mods = e.modifiers()
            ctrl = Qt.MetaModifier if MAC else Qt.ControlModifier
            if mods & ctrl and not mods & Qt.ShiftModifier and e.key() != Qt.Key_QuoteLeft:
                e.accept()
                return True
        return super().event(e)

    def keyPressEvent(self, e):
        key, mods, text = e.key(), e.modifiers(), e.text()
        ctrl = Qt.MetaModifier if MAC else Qt.ControlModifier
        app_cursor = APP_CURSOR in self.term.mode
        arrows = {Qt.Key_Up: "A", Qt.Key_Down: "B", Qt.Key_Right: "C", Qt.Key_Left: "D"}
        if key in arrows:
            if mods & Qt.AltModifier and key in (Qt.Key_Left, Qt.Key_Right):
                self.send("\x1bb" if key == Qt.Key_Left else "\x1bf")  # word jump, like Terminal.app
            elif MAC and mods & Qt.ControlModifier and key in (Qt.Key_Left, Qt.Key_Right):
                self.send("\x01" if key == Qt.Key_Left else "\x05")      # ⌘← / ⌘→ — line start / end
            else:
                self.send(("\x1bO" if app_cursor else "\x1b[") + arrows[key])
            self._reset_view()
            return
        special = {
            Qt.Key_Return: "\r", Qt.Key_Enter: "\r", Qt.Key_Backspace: "\x7f", Qt.Key_Tab: "\t",
            Qt.Key_Backtab: "\x1b[Z", Qt.Key_Escape: "\x1b", Qt.Key_Home: "\x1b[H", Qt.Key_End: "\x1b[F",
            Qt.Key_PageUp: "\x1b[5~", Qt.Key_PageDown: "\x1b[6~", Qt.Key_Delete: "\x1b[3~", Qt.Key_Insert: "\x1b[2~",
            Qt.Key_F1: "\x1bOP", Qt.Key_F2: "\x1bOQ", Qt.Key_F3: "\x1bOR", Qt.Key_F4: "\x1bOS",
        }
        if mods & Qt.ShiftModifier and key in (Qt.Key_PageUp, Qt.Key_PageDown):
            self.scroll_by((1 if key == Qt.Key_PageUp else -1) * (self.term.lines - 1))
            return
        if key in (Qt.Key_Return, Qt.Key_Enter) and not self.alive:
            self.restart()
            return
        if MAC and mods & Qt.ControlModifier and key == Qt.Key_Backspace:
            self.send("\x15")  # ⌘⌫ — delete line
            return
        if key in special:
            seq = special[key]
            if key == Qt.Key_Backspace and mods & Qt.AltModifier:
                seq = "\x17"
            self.send(seq)
            self._reset_view()
            return
        if mods & ctrl:
            k = key
            if Qt.Key_A <= k <= Qt.Key_Z:
                self.send(chr(k - Qt.Key_A + 1))
                self._reset_view()
                return
            mapping = {Qt.Key_BracketLeft: "\x1b", Qt.Key_Backslash: "\x1c", Qt.Key_BracketRight: "\x1d",
                       Qt.Key_Space: "\x00", Qt.Key_Underscore: "\x1f", Qt.Key_Minus: "\x1f"}
            if k in mapping:
                self.send(mapping[k])
                return
        if text:
            if mods & Qt.AltModifier and not MAC:
                text = "\x1b" + text
            self.send(text)
            self._reset_view()
            return
        super().keyPressEvent(e)

    def inputMethodEvent(self, e):
        if e.commitString():
            self.send(e.commitString())
        e.accept()

    def _reset_view(self):
        self.sel = None
        if self.scroll:
            self.scroll = 0
            self.update()

    # ------------------------------------------------------------------ clipboard (called by the Edit menu)
    def copy(self):
        text = self.selected_text()
        if text:
            QGuiApplication.clipboard().setText(text)
        elif not MAC:
            self.send("\x03")

    def paste(self):
        text = QGuiApplication.clipboard().text()
        if not text:
            return
        text = text.replace("\r\n", "\n").replace("\n", "\r")
        if BRACKETED_PASTE in self.term.mode:
            text = "\x1b[200~" + text + "\x1b[201~"
        self.send(text)
        self._reset_view()

    def selectAll(self):
        if not MAC:
            self.send("\x01")
            return
        total = len(self.term.scrollback) + self.term.lines
        self.sel = ((0, 0), (total - 1, self.term.columns))
        self.update()

    def clear(self):
        self.term.scrollback.clear()
        self.send("\x0c")
        self.update()

    def undo(self):
        if not MAC:
            self.send("\x1a")

    # ------------------------------------------------------------------ mouse: selection and scrolling
    def _cell(self, pos: QPoint):
        col = int(max(0, min(self.term.columns, round((pos.x() - 8) / self.cw))))
        row = int(max(0, min(self.term.lines - 1, (pos.y() - 4) // self.ch)))
        return len(self.term.scrollback) - self.scroll + row, col

    def _sel_range(self):
        if not self.sel or self.sel[0] == self.sel[1]:
            return None
        a, b = sorted(self.sel)
        return a, b

    def mousePressEvent(self, e):
        self.setFocus()
        if e.button() == Qt.LeftButton:
            cell = self._cell(e.position().toPoint())
            self._drag = cell
            self.sel = (cell, cell)
            self.update()
        elif e.button() == Qt.MiddleButton:
            self.paste()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.sel = (self._drag, self._cell(e.position().toPoint()))
            self.update()

    def mouseReleaseEvent(self, e):
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        row, col = self._cell(e.position().toPoint())
        line = self._line_text(row)
        a = b = min(col, len(line))
        while a > 0 and (line[a - 1].isalnum() or line[a - 1] in "_-./~"):
            a -= 1
        while b < len(line) and (line[b].isalnum() or line[b] in "_-./~"):
            b += 1
        self.sel = ((row, a), (row, b))
        self.update()

    def wheelEvent(self, e):
        lines = int(-e.angleDelta().y() / 40) or (-1 if e.angleDelta().y() > 0 else 1)
        self.scroll_by(-lines)

    def scroll_by(self, n):
        self.scroll = max(0, min(len(self.term.scrollback), self.scroll + n))
        self.update()

    def _line_text(self, absrow):
        sb = self.term.scrollback
        line = sb[absrow] if absrow < len(sb) else self.term.buffer[absrow - len(sb)]
        default = self.term.default_char
        return "".join((line.get(x, default) if isinstance(line, dict) else line[x]).data
                       for x in range(self.term.columns))

    def selected_text(self):
        rng = self._sel_range()
        if not rng:
            return ""
        (r1, c1), (r2, c2) = rng
        out = []
        for r in range(r1, r2 + 1):
            text = self._line_text(r)
            a = c1 if r == r1 else 0
            b = c2 if r == r2 else len(text)
            out.append(text[a:b].rstrip())
        return "\n".join(out)

    def text(self):
        """Whole screen + scrollback as text (self-test, «Копировать всё»)."""
        total = len(self.term.scrollback) + self.term.lines
        return "\n".join(self._line_text(r).rstrip() for r in range(total)).rstrip()

    def focusInEvent(self, e):
        super().focusInEvent(e)
        self.update()

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self.update()
