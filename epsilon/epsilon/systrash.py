"""Move files to the system Trash (macOS Finder Trash, so "Put Back" works)."""
import ctypes
import shutil
import subprocess
import sys
import time
from pathlib import Path


def _macos_trash(path: Path) -> bool:
    """NSFileManager.trashItemAtURL via the Objective-C runtime (no PyObjC needed)."""
    try:
        objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
        ctypes.cdll.LoadLibrary("/System/Library/Frameworks/Foundation.framework/Foundation")
    except OSError:
        return False
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    send = objc.objc_msgSend

    def msg(obj, sel, *args, argtypes=(), restype=ctypes.c_void_p):
        send.restype = restype
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, *argtypes]
        return send(obj, objc.sel_registerName(sel), *args)

    ns_string = msg(objc.objc_getClass(b"NSString"), b"stringWithUTF8String:", str(path).encode("utf-8"),
                    argtypes=(ctypes.c_char_p,))
    url = msg(objc.objc_getClass(b"NSURL"), b"fileURLWithPath:", ns_string, argtypes=(ctypes.c_void_p,))
    manager = msg(objc.objc_getClass(b"NSFileManager"), b"defaultManager")
    ok = msg(manager, b"trashItemAtURL:resultingItemURL:error:", url, None, None,
             argtypes=(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p), restype=ctypes.c_bool)
    return bool(ok) and not path.exists()


def _finder_trash(path: Path) -> bool:
    escaped = str(path).replace("\\", "\\\\").replace('"', '\\"')
    result = subprocess.run(["osascript", "-e", f'tell application "Finder" to delete POSIX file "{escaped}"'],
                            capture_output=True, text=True)
    return result.returncode == 0 and not path.exists()


def _xdg_trash(path: Path) -> bool:
    """freedesktop.org Trash (Linux) — used for development and tests."""
    base = Path.home() / ".local" / "share" / "Trash"
    files, info = base / "files", base / "info"
    files.mkdir(parents=True, exist_ok=True)
    info.mkdir(parents=True, exist_ok=True)
    dest = files / path.name
    n = 2
    while dest.exists():
        dest = files / f"{path.stem} {n}{path.suffix}"
        n += 1
    (info / (dest.name + ".trashinfo")).write_text(
        f"[Trash Info]\nPath={path}\nDeletionDate={time.strftime('%Y-%m-%dT%H:%M:%S')}\n", "utf-8")
    shutil.move(str(path), str(dest))
    return True


def move_to_trash(path) -> None:
    path = Path(path)
    if not path.exists():
        return
    if sys.platform == "darwin":
        if _macos_trash(path) or _finder_trash(path):
            return
        raise OSError(f"Не удалось переместить «{path.name}» в Корзину macOS")
    _xdg_trash(path)
