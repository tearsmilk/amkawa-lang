"""Shared painting helpers and small widgets: avatars, label pills, badges, the card face layout, popups."""
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from . import icons, theme
from .model import due_state, fmt_dt

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def defer(fn, ms=0):
    """QTimer.singleShot that tolerates the widget being gone when it fires (a rebuilt board, a closed dialog).
    An exception raised inside a timer slot is left set by PySide 6.7 and the next Qt call dies with SystemError."""
    def run():
        try:
            fn()
        except (RuntimeError, AttributeError):
            pass
    QTimer.singleShot(ms, run)


def font(px, bold=False, serif=False, italic=False):
    f = QFont(theme.SERIF.split(",")[0].strip('" ')) if serif else QFont()
    f.setPixelSize(px)
    f.setBold(bold)
    f.setItalic(italic)
    return f


def paint_background(p, rect, bg, dim=0):
    """Board background: gradient key, #hex colour, painted scene or picture (see backgrounds.py)."""
    from . import backgrounds

    backgrounds.paint(p, rect, bg, dim)


def bg_is_light(bg):
    from . import backgrounds

    return backgrounds.is_light(bg)


@lru_cache(maxsize=256)
def _image(path, width):
    pix = QPixmap(path)
    if pix.isNull() or not width:
        return pix
    return pix.scaledToWidth(width * 2, Qt.SmoothTransformation)


def draw_avatar(p, rect, member):
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(member.get("color") or "#D97757") if member else QColor("#A8A59C"))
    p.drawEllipse(QRectF(rect))
    p.setPen(QColor("#FFFFFF"))
    p.setFont(font(max(8, int(rect.height() * 0.42)), bold=True))
    p.drawText(QRectF(rect), Qt.AlignCenter, (member or {}).get("initials", "?")[:2])
    p.restore()


def avatar_pixmap(member, size=28):
    pix = QPixmap(size * 2, size * 2)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    draw_avatar(p, QRect(0, 0, size * 2, size * 2), member)
    p.end()
    pix.setDevicePixelRatio(2)
    return pix


def label_text_color(color):
    return QColor("#FFFFFF") if QColor(theme.label_hex(color)).lightness() < 175 else QColor("#141413")


DUE_COLORS = {"done": ("done", "#FFFFFF"), "overdue": ("overdue", "#FFFFFF"), "soon": ("due_soon", "#141413")}


class CardFace:
    """Computes the layout of a card face for a width, then paints it (shared by the board, drag pixmaps and
    the calendar)."""

    PAD = 8

    def __init__(self, board, card, width, compact=False, show_fields=True):
        self.b = board
        self.c = card
        self.w = width
        self.compact = compact
        self.items = []   # (kind, rect, data)
        self.h = self._layout(show_fields)

    def _layout(self, show_fields):
        b, c, w, pad = self.b, self.c, self.w, self.PAD
        y = 0
        cover = c.get("cover") or {}
        if cover and not self.compact:
            if cover.get("attachment"):
                att = next((a for a in c.get("attachments", []) if a["id"] == cover["attachment"]), None)
                if att and Path(att["url"]).suffix.lower() in IMAGE_EXT and Path(att["url"]).exists():
                    pix = _image(att["url"], w)
                    if not pix.isNull():
                        h = min(160, int(pix.height() / 2))
                        self.items.append(("cover_img", QRect(0, 0, w, h), pix))
                        y = h
            elif cover.get("color"):
                self.items.append(("cover", QRect(0, 0, w, 30), cover["color"]))
                y = 30
        y += pad
        # labels
        x = pad
        lab_font = QFontMetrics(font(11, bold=True))
        row_h = 16
        any_label = False
        for lid in c.get("labels", []):
            lb = b.label(lid)
            if not lb:
                continue
            any_label = True
            tw = lab_font.horizontalAdvance(lb["name"]) + 16 if lb["name"] else 40
            tw = min(tw, w - 2 * pad)
            if x + tw > w - pad and x > pad:
                x = pad
                y += row_h + 4
            self.items.append(("label", QRect(x, y, tw, row_h), lb))
            x += tw + 4
        if any_label:
            y += row_h + 6
        # title
        fm = QFontMetrics(font(13))
        tr = fm.boundingRect(QRect(pad, y, w - 2 * pad, 2000), Qt.TextWordWrap, c["title"] or " ")
        self.items.append(("title", QRect(pad, y, w - 2 * pad, tr.height()), c["title"]))
        y += tr.height() + 4
        # custom fields on the front
        if show_fields and not self.compact:
            for f in b.d.get("fields", []):
                v = (c.get("fields") or {}).get(f["id"])
                if v in (None, "", False) or not f.get("on_front", True):
                    continue
                text = f"{f['name']}: {'✓' if v is True else v}"
                self.items.append(("field", QRect(pad, y, w - 2 * pad, 16), text))
                y += 17
        # badges
        badges = []
        st = due_state(c)
        if c.get("due") or c.get("start"):
            text = fmt_dt(c["due"]) if c.get("due") else "с " + fmt_dt(c["start"], False)
            badges.append(("due", "clock", text, st))
        if c.get("desc"):
            badges.append(("plain", "desc", "", None))
        if c.get("comments"):
            badges.append(("plain", "comment", str(len(c["comments"])), None))
        if c.get("attachments"):
            badges.append(("plain", "attach", str(len(c["attachments"])), None))
        done, total = b.checklist_progress(c)
        if total:
            badges.append(("check", "checklist", f"{done}/{total}", done == total))
        if c.get("votes"):
            badges.append(("plain", "vote", str(c["votes"]), None))
        members = [b.member(m) for m in c.get("members", []) if b.member(m)]
        bx = pad
        bfm = QFontMetrics(font(11))
        avatar = 22
        right_space = (len(members) * (avatar - 4) + 6) if members else 0
        if badges or members:
            for kind, icon, text, state in badges:
                tw = 16 + (bfm.horizontalAdvance(text) + 4 if text else 0) + (8 if kind != "plain" else 2)
                if bx + tw > w - pad - right_space and bx > pad:
                    bx = pad
                    y += 24
                self.items.append(("badge", QRect(bx, y, tw, 20), (kind, icon, text, state)))
                bx += tw + 4
            ax = w - pad - avatar
            for m in reversed(members[:5]):
                self.items.append(("avatar", QRect(ax, y - 1, avatar, avatar), m))
                ax -= avatar - 4
            y += 24
        return y + pad - 2

    def paint(self, p, origin=QPointF(0, 0), hover=False, ghost=False):
        c = theme.CURRENT
        p.save()
        p.translate(origin)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 0, self.w, self.h)
        path = QPainterPath()
        path.addRoundedRect(r, 9, 9)
        if ghost:
            p.fillPath(path, QColor(0, 0, 0, 28))
            p.restore()
            return
        p.fillPath(path, QColor(c["card"]))
        p.setPen(QPen(QColor(c["accent"] if hover else c["border"]), 1.2 if hover else 1))
        p.drawPath(path)
        p.setClipPath(path)
        for kind, rect, data in self.items:
            if kind == "cover":
                p.fillRect(rect, QColor(theme.label_hex(data)))
            elif kind == "cover_img":
                sc = data.scaled(rect.size() * 2, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                sc.setDevicePixelRatio(2)
                p.drawPixmap(rect.topLeft(), sc, QRect(0, 0, rect.width() * 2, rect.height() * 2))
        p.setClipping(False)
        for kind, rect, data in self.items:
            if kind == "label":
                lp = QPainterPath()
                lp.addRoundedRect(QRectF(rect), 4, 4)
                p.fillPath(lp, QColor(theme.label_hex(data["color"])))
                if data["name"]:
                    p.setPen(label_text_color(data["color"]))
                    p.setFont(font(11, bold=True))
                    p.drawText(QRectF(rect).adjusted(8, 0, -6, 0), Qt.AlignVCenter | Qt.AlignLeft,
                               QFontMetrics(font(11, bold=True)).elidedText(data["name"], Qt.ElideRight,
                                                                            rect.width() - 14))
            elif kind == "title":
                p.setPen(QColor(c["text"]))
                p.setFont(font(13))
                p.drawText(QRectF(rect), Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, data)
            elif kind == "field":
                p.setPen(QColor(c["muted"]))
                p.setFont(font(11))
                p.drawText(QRectF(rect), Qt.AlignLeft | Qt.AlignVCenter,
                           QFontMetrics(font(11)).elidedText(data, Qt.ElideRight, rect.width()))
            elif kind == "badge":
                bkind, icon, text, state = data
                ink = c["muted"]
                if bkind == "due" and state in DUE_COLORS:
                    bgkey, ink = DUE_COLORS[state]
                    bp = QPainterPath()
                    bp.addRoundedRect(QRectF(rect), 4, 4)
                    p.fillPath(bp, QColor(c[bgkey]))
                elif bkind == "check" and state:
                    bp = QPainterPath()
                    bp.addRoundedRect(QRectF(rect), 4, 4)
                    p.fillPath(bp, QColor(c["done"]))
                    ink = "#FFFFFF"
                x0 = rect.x() + (4 if bkind != "plain" else 0)
                p.drawPixmap(QRect(x0, rect.y() + 3, 14, 14), icons.pixmap(icon, ink, ink, 28))
                if text:
                    p.setPen(QColor(ink))
                    p.setFont(font(11))
                    p.drawText(QRect(x0 + 17, rect.y(), rect.width(), rect.height()), Qt.AlignVCenter | Qt.AlignLeft,
                               text)
            elif kind == "avatar":
                p.setPen(QPen(QColor(c["card"]), 2))
                p.setBrush(Qt.NoBrush)
                draw_avatar(p, rect, data)
        if self.c.get("due_done") and self.c.get("due"):
            pass
        p.restore()

    def pixmap(self, dpr=2.0):
        pix = QPixmap(int(self.w * dpr), int(self.h * dpr))
        pix.fill(Qt.transparent)
        pix.setDevicePixelRatio(dpr)
        p = QPainter(pix)
        self.paint(p)
        p.end()
        return pix


class Popup(QDialog):
    """A small floating panel (Trello's popovers): title, close button, body layout."""

    changed = Signal()

    def __init__(self, title, parent=None, width=300):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.frame = QFrame()
        self.frame.setObjectName("Popup")
        outer.addWidget(self.frame)
        self.body = QVBoxLayout(self.frame)
        self.body.setContentsMargins(12, 10, 12, 12)
        self.body.setSpacing(6)
        head = QLabel(title)
        head.setObjectName("PopupTitle")
        head.setAlignment(Qt.AlignCenter)
        self.body.addWidget(head)
        sep = QFrame()
        sep.setObjectName("Sep")
        sep.setFixedHeight(1)
        self.body.addWidget(sep)
        self.setFixedWidth(width)

    def show_at(self, widget_or_point):
        if isinstance(widget_or_point, QWidget):
            pt = widget_or_point.mapToGlobal(widget_or_point.rect().bottomLeft())
        else:
            pt = widget_or_point
        self.adjustSize()
        scr = self.screen().availableGeometry() if self.screen() else None
        if scr is not None:
            pt.setX(min(pt.x(), scr.right() - self.width() - 8))
            pt.setY(min(pt.y(), scr.bottom() - self.height() - 8))
        self.move(pt)
        self.show()


def icon_button(name, tip="", text="", obj=None, size=16):
    b = QPushButton(text)
    b.setIcon(icons.icon(name, theme.CURRENT["text"]))
    b.setIconSize(QSize(size, size))
    if tip:
        b.setToolTip(tip)
    if obj:
        b.setObjectName(obj)
    b.setCursor(Qt.PointingHandCursor)
    return b


def color_swatch(color, w=40, h=24, selected=False):
    pix = QPixmap(w * 2, h * 2)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(2, 2, w * 2 - 4, h * 2 - 4), 8, 8)
    if color in theme.BACKGROUNDS:
        a, b = theme.BACKGROUNDS[color]
        g = QLinearGradient(0, 0, w * 2, h * 2)
        g.setColorAt(0, QColor(a))
        g.setColorAt(1, QColor(b))
        p.fillPath(path, g)
    else:
        p.fillPath(path, QColor(theme.label_hex(color)))
    if selected:
        p.setPen(QPen(QColor("#141413"), 4))
        p.drawPath(path)
    p.end()
    pix.setDevicePixelRatio(2)
    return pix
