"""Global hotkeys. macOS: Carbon RegisterEventHotKey through ctypes — works while another app is in front and
needs no Accessibility permission. Elsewhere: application-wide QShortcuts (only while Гамма is focused).

A hotkey is stored as {"vk": macOS virtual key code, "key": Qt key, "mods": Qt modifier bits, "text": label};
vk is the physical key, so ⇧⌘2 works with the Russian layout too."""
import ctypes
import sys
from ctypes import POINTER, Structure, c_int32, c_uint32, c_ulong, c_void_p

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut

IS_MAC = sys.platform == "darwin"

# Qt (macOS mapping) → Carbon modifier bits
_QT_CMD, _QT_SHIFT, _QT_ALT, _QT_CTRL = 0x04000000, 0x02000000, 0x08000000, 0x10000000
_CARBON = ((_QT_CMD, 256), (_QT_SHIFT, 512), (_QT_ALT, 2048), (_QT_CTRL, 4096))
_MOD_MASK = _QT_CMD | _QT_SHIFT | _QT_ALT | _QT_CTRL


def _fourcc(s):
    return int.from_bytes(s.encode("ascii"), "big")


class _HotKeyID(Structure):
    _fields_ = [("signature", c_uint32), ("id", c_uint32)]


class _EventTypeSpec(Structure):
    _fields_ = [("eventClass", c_uint32), ("eventKind", c_uint32)]


_HANDLER = ctypes.CFUNCTYPE(c_int32, c_void_p, c_void_p, c_void_p)
_SIG = _fourcc("Gamm")


def label(mods, key_text):
    """macOS-style label: ⌃⌥⇧⌘ + key."""
    out = ""
    if mods & _QT_CTRL:
        out += "⌃"
    if mods & _QT_ALT:
        out += "⌥"
    if mods & _QT_SHIFT:
        out += "⇧"
    if mods & _QT_CMD:
        out += "⌘"
    return out + key_text


def key_text(key):
    names = {Qt.Key_Space: "Пробел", Qt.Key_Return: "↩", Qt.Key_Enter: "↩", Qt.Key_Tab: "⇥",
             Qt.Key_Backspace: "⌫", Qt.Key_Delete: "⌦", Qt.Key_Left: "←", Qt.Key_Right: "→", Qt.Key_Up: "↑",
             Qt.Key_Down: "↓", Qt.Key_Home: "↖", Qt.Key_End: "↘", Qt.Key_PageUp: "⇞", Qt.Key_PageDown: "⇟"}
    if key in names:
        return names[key]
    return QKeySequence(key).toString(QKeySequence.PortableText).upper() or "?"


def from_event(event):
    """QKeyEvent → hotkey dict, or None when it is only a modifier / plain key without modifiers."""
    key = event.key()
    if key in (Qt.Key_Shift, Qt.Key_Control, Qt.Key_Meta, Qt.Key_Alt, Qt.Key_AltGr, Qt.Key_CapsLock, 0,
               Qt.Key_unknown):
        return None
    mods = int(event.modifiers().value if hasattr(event.modifiers(), "value") else event.modifiers()) & _MOD_MASK
    is_f = Qt.Key_F1 <= key <= Qt.Key_F20
    if not mods and not is_f:
        return None
    vk = event.nativeVirtualKey() if IS_MAC else 0
    # Cyrillic layout: map to the Latin key on the same physical position for Qt's own shortcuts / the label
    if IS_MAC and vk in _VK_LATIN:
        key = _VK_LATIN[vk]
    return {"vk": int(vk), "key": int(key), "mods": mods, "text": label(mods, key_text(key))}


# macOS ANSI virtual key codes → Qt keys (used to show Latin labels whatever the input source)
_VK_LATIN = {
    0x00: Qt.Key_A, 0x0B: Qt.Key_B, 0x08: Qt.Key_C, 0x02: Qt.Key_D, 0x0E: Qt.Key_E, 0x03: Qt.Key_F, 0x05: Qt.Key_G,
    0x04: Qt.Key_H, 0x22: Qt.Key_I, 0x26: Qt.Key_J, 0x28: Qt.Key_K, 0x25: Qt.Key_L, 0x2E: Qt.Key_M, 0x2D: Qt.Key_N,
    0x1F: Qt.Key_O, 0x23: Qt.Key_P, 0x0C: Qt.Key_Q, 0x0F: Qt.Key_R, 0x01: Qt.Key_S, 0x11: Qt.Key_T, 0x20: Qt.Key_U,
    0x09: Qt.Key_V, 0x0D: Qt.Key_W, 0x07: Qt.Key_X, 0x10: Qt.Key_Y, 0x06: Qt.Key_Z,
    0x1D: Qt.Key_0, 0x12: Qt.Key_1, 0x13: Qt.Key_2, 0x14: Qt.Key_3, 0x15: Qt.Key_4, 0x17: Qt.Key_5, 0x16: Qt.Key_6,
    0x1A: Qt.Key_7, 0x1C: Qt.Key_8, 0x19: Qt.Key_9, 0x1B: Qt.Key_Minus, 0x18: Qt.Key_Equal,
    0x21: Qt.Key_BracketLeft, 0x1E: Qt.Key_BracketRight, 0x29: Qt.Key_Semicolon, 0x27: Qt.Key_Apostrophe,
    0x2B: Qt.Key_Comma, 0x2F: Qt.Key_Period, 0x2C: Qt.Key_Slash, 0x2A: Qt.Key_Backslash, 0x32: Qt.Key_QuoteLeft,
}


def same(a, b):
    if not a or not b:
        return False
    if IS_MAC and a.get("vk") is not None and b.get("vk") is not None:
        return a["vk"] == b["vk"] and a["mods"] == b["mods"]
    return a.get("key") == b.get("key") and a.get("mods") == b.get("mods")


class HotkeyManager(QObject):
    activated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._refs = {}       # action → EventHotKeyRef / QShortcut
        self._ids = {}        # carbon id → action
        self._carbon = None
        self._handler = None
        self.failed = []      # actions whose combination is taken by another app
        self.paused = False
        self._mapping = {}
        if IS_MAC:
            self._install()

    # -- Carbon
    def _install(self):
        try:
            c = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/Carbon.framework/Carbon")
            c.GetApplicationEventTarget.restype = c_void_p
            c.InstallEventHandler.argtypes = [c_void_p, _HANDLER, c_ulong, POINTER(_EventTypeSpec), c_void_p,
                                              POINTER(c_void_p)]
            c.InstallEventHandler.restype = c_int32
            c.RegisterEventHotKey.argtypes = [c_uint32, c_uint32, _HotKeyID, c_void_p, c_uint32, POINTER(c_void_p)]
            c.RegisterEventHotKey.restype = c_int32
            c.UnregisterEventHotKey.argtypes = [c_void_p]
            c.UnregisterEventHotKey.restype = c_int32
            c.GetEventParameter.argtypes = [c_void_p, c_uint32, c_uint32, c_void_p, c_ulong, c_void_p, c_void_p]
            c.GetEventParameter.restype = c_int32
            spec = _EventTypeSpec(_fourcc("keyb"), 5)  # kEventClassKeyboard / kEventHotKeyPressed
            self._handler = _HANDLER(self._on_carbon)
            ref = c_void_p()
            if c.InstallEventHandler(c.GetApplicationEventTarget(), self._handler, 1, ctypes.byref(spec), None,
                                     ctypes.byref(ref)) == 0:
                self._carbon = c
        except Exception:
            self._carbon = None

    def _on_carbon(self, _call, event, _data):
        hk = _HotKeyID()
        try:
            self._carbon.GetEventParameter(event, _fourcc("----"), _fourcc("hkid"), None, ctypes.sizeof(hk), None,
                                           ctypes.byref(hk))
        except Exception:
            return 0
        action = self._ids.get(hk.id)
        if action and not self.paused:
            QTimer.singleShot(0, lambda: self.activated.emit(action))
        return 0

    # -- public
    def available(self):
        """'global' when hotkeys work from any app, 'app' when only inside Гамма."""
        return "global" if self._carbon else "app"

    def set(self, mapping):
        """mapping: action → hotkey dict or None. Re-registers everything."""
        self.clear()
        self._mapping = dict(mapping)
        self.failed = []
        for n, (action, hk) in enumerate(mapping.items(), 1):
            if not hk:
                continue
            if self._carbon and hk.get("vk") is not None:
                mods = sum(c for q, c in _CARBON if hk["mods"] & q)
                ref = c_void_p()
                err = self._carbon.RegisterEventHotKey(int(hk["vk"]), mods, _HotKeyID(_SIG, n),
                                                       self._carbon.GetApplicationEventTarget(), 0, ctypes.byref(ref))
                if err == 0:
                    self._refs[action] = ref
                    self._ids[n] = action
                else:
                    self.failed.append(action)
            else:
                from PySide6.QtWidgets import QApplication

                seq = QKeySequence(int(hk["key"]) | int(hk["mods"]))
                parent = QApplication.activeWindow() or self.parent()
                if parent is None:
                    continue
                sc = QShortcut(seq, parent)
                sc.setContext(Qt.ApplicationShortcut)
                sc.activated.connect(lambda a=action: None if self.paused else self.activated.emit(a))
                self._refs[action] = sc

    def suspend(self):
        """Release every combination (while the user types a new one — Carbon would swallow the key press)."""
        self.paused = True
        mapping = self._mapping
        self.clear()
        self._mapping = mapping

    def resume(self):
        self.paused = False
        self.set(self._mapping)

    def clear(self):
        for action, ref in self._refs.items():
            if isinstance(ref, QShortcut):
                ref.setEnabled(False)
                ref.deleteLater()
            elif self._carbon:
                self._carbon.UnregisterEventHotKey(ref)
        self._refs = {}
        self._ids = {}
