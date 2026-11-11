"""Small macOS bridges through ctypes (no PyObjC): window level / exclusion from screen capture, Finder, sounds,
privacy panes. Every function is a no-op elsewhere."""
import ctypes
import subprocess
import sys
from ctypes import c_long, c_ulong, c_void_p

IS_MAC = sys.platform == "darwin"
_objc = None


def _lib():
    global _objc
    if _objc is None and IS_MAC:
        try:
            _objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
            _objc.sel_registerName.restype = c_void_p
            _objc.sel_registerName.argtypes = [ctypes.c_char_p]
        except OSError:
            _objc = False
    return _objc or None


def _send(obj, sel, *args, restype=c_void_p, argtypes=()):
    lib = _lib()
    if not lib or not obj:
        return None
    fn = ctypes.CFUNCTYPE(restype, c_void_p, c_void_p, *argtypes)(("objc_msgSend", lib))
    return fn(obj, lib.sel_registerName(sel.encode()), *args)


def _nswindow(widget):
    from PySide6.QtGui import QGuiApplication

    if QGuiApplication.platformName() != "cocoa":  # e.g. the offscreen platform of the self-test: no NSView
        return None
    try:
        view = c_void_p(int(widget.winId()))
    except Exception:
        return None
    return _send(view, "window")


SCREEN_SAVER_LEVEL = 1000
STATUS_LEVEL = 25


def float_above_all(widget, level=SCREEN_SAVER_LEVEL):
    """Above the menu bar and full-screen apps, on every Space."""
    win = _nswindow(widget)
    if not win:
        return
    _send(win, "setLevel:", c_long(level), argtypes=(c_long,))
    # canJoinAllSpaces | stationary | fullScreenAuxiliary | ignoresCycle
    _send(win, "setCollectionBehavior:", c_ulong(1 | 16 | 256 | 64), argtypes=(c_ulong,))
    _send(win, "setHidesOnDeactivate:", ctypes.c_bool(False), argtypes=(ctypes.c_bool,))


def exclude_from_capture(widget, exclude=True):
    """NSWindowSharingNone: the window is not visible in screenshots / screen recordings."""
    win = _nswindow(widget)
    if win:
        _send(win, "setSharingType:", c_ulong(0 if exclude else 1), argtypes=(c_ulong,))


def reveal(path):
    if IS_MAC:
        subprocess.Popen(["open", "-R", str(path)])
    else:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        from pathlib import Path

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))


def open_file(path):
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


_SHUTTER = "/System/Library/Components/CoreAudio.component/Contents/SharedSupport/SystemSounds/system/Screen Capture.aif"


def play(sound="Tink"):
    """System sound by name; "Grab" = the macOS screenshot shutter."""
    if not IS_MAC:
        return
    import os

    path = _SHUTTER if sound == "Grab" and os.path.exists(_SHUTTER) else \
        f"/System/Library/Sounds/{'Tink' if sound == 'Grab' else sound}.aiff"
    try:
        subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


PRIVACY = {
    "screen": "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
    "mic": "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
}


def open_privacy(kind):
    if IS_MAC:
        subprocess.Popen(["open", PRIVACY[kind]])


def screen_access():
    """True / False when macOS can tell (CGPreflightScreenCaptureAccess, 10.15+), None otherwise."""
    if not IS_MAC:
        return None
    try:
        cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        cg.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
        return bool(cg.CGPreflightScreenCaptureAccess())
    except Exception:
        return None


def request_screen_access():
    if not IS_MAC:
        return
    try:
        cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        cg.CGRequestScreenCaptureAccess.restype = ctypes.c_bool
        cg.CGRequestScreenCaptureAccess()
    except Exception:
        pass
