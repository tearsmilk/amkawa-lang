"""Build "Kappa.app" + .dmg for macOS 11+ / Intel x86_64 WITHOUT a Mac.

The bundle is assembled from prebuilt pieces, nothing is compiled:
- python-build-standalone CPython 3.11 for x86_64-apple-darwin (requires macOS 10.9+);
- macOS x86_64 wheels of the dependencies (pip --platform);
- the official signed BlackHole 2ch installer as the virtual microphone.
The Python binary itself is the bundle's main executable, so macOS attributes microphone
access to "Kappa". `sitecustomize.py` starts the app when that binary is launched.

Host needs: python3 + pip, Pillow, macholib, xorriso, and the `dmg` tool from libdmg-hfsplus.
Usage: python3 packaging/build_dmg_portable.py --dmg-tool /path/to/dmg [--out dist]
"""
import argparse
import hashlib
import os
import plistlib
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kappa import APP_NAME, __version__  # noqa: E402

PYTHON_URL = ("https://github.com/astral-sh/python-build-standalone/releases/download/20241016/"
              "cpython-3.11.10+20241016-x86_64-apple-darwin-install_only.tar.gz")
BLACKHOLE_URL = "https://existential.audio/downloads/BlackHole2ch-0.7.1.pkg"
BLACKHOLE_SHA256 = "57b540f27a3e29c37e310e01bee0fdfab76733087e47f997ef9dccf851400dcf"
WHEELS = [
    "numpy==1.26.4", "scipy==1.13.1", "sounddevice==0.5.1", "cffi==1.17.1", "pycparser==2.22",
    "PySide6-Essentials==6.7.3", "shiboken6==6.7.3", "torch==2.2.2", "filelock==3.16.1",
    "typing-extensions==4.12.2", "sympy==1.13.3", "mpmath==1.3.0", "networkx==3.4.2", "jinja2==3.1.4",
    "MarkupSafe==3.0.2", "fsspec==2024.10.0", "certifi==2024.8.30",
]
QT_FRAMEWORKS = {"QtCore", "QtGui", "QtWidgets", "QtSvg", "QtDBus"}
QT_MODULES = {"QtCore", "QtGui", "QtWidgets"}
MIN_MACOS = (11, 0)

SITECUSTOMIZE = '''\
# Starts Kappa when the bundle's main executable (this Python) is launched from Finder.
import os as _os
import sys as _sys

if _sys.executable.endswith("/Contents/MacOS/Kappa") and _sys.argv in ([], [""]) and \\
        not _os.environ.get("KAPPA_PLAIN_PYTHON"):
    _sys.argv = [_sys.executable] + _sys.argv[1:]
    _sys.dont_write_bytecode = True
    if _os.environ.get("KAPPA_SELFTEST"):
        import run as _run
        _code = _run.selftest()
    else:
        from kappa.ui import main as _main
        _code = _main()
    _sys.stdout.flush()
    _os._exit(_code or 0)
'''


def fetch(url, dest, sha256=None):
    if not dest.exists():
        print("download", url)
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
        with urllib.request.urlopen(req) as resp, open(dest, "wb") as fh:
            shutil.copyfileobj(resp, fh)
    if sha256:
        digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        if digest != sha256:
            raise SystemExit(f"checksum mismatch for {dest}: {digest}")
    return dest


def rm(path):
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def prune_python(lib):
    for name in ["tcl8", "tcl8.6", "tk8.6", "itcl4.2.2", "thread2.8.7", "pkgconfig"]:
        rm(lib / name)
    std = lib / "python3.11"
    for name in ["test", "idlelib", "tkinter", "turtledemo", "ensurepip", "lib2to3", "unittest/test",
                 "site-packages/pip", "config-3.11-darwin"]:
        rm(std / name)
    for so in (std / "lib-dynload").glob("_tkinter*"):
        rm(so)


def prune_site(site):
    pyside = site / "PySide6"
    for item in list(pyside.iterdir()):
        if item.suffix == ".app" or item.name in {"include", "typesystems", "glue", "scripts", "examples"}:
            rm(item)
        elif item.is_file() and item.suffix == ".so" and item.name.split(".")[0] not in QT_MODULES:
            rm(item)
        elif item.is_file() and "pyside6qml" in item.name:
            rm(item)
        elif item.is_file() and item.suffix in ("", ".pyi") and item.name != "py.typed":
            rm(item)  # lupdate, qmlls, designer, ... and type stubs
    qt = pyside / "Qt"
    for name in ["qml", "libexec", "metatypes", "translations"]:
        rm(qt / name)
    for fw in (qt / "lib").iterdir():
        if fw.name.replace(".framework", "") not in QT_FRAMEWORKS:
            rm(fw)
    for plugin_dir in (qt / "plugins").iterdir():
        if plugin_dir.name not in {"platforms", "styles", "imageformats", "iconengines"}:
            rm(plugin_dir)
    for name in ["platforms/libqminimal.dylib", "platforms/libqoffscreen.dylib", "imageformats/libqpdf.dylib"]:
        rm(qt / "plugins" / name)
    for name in ["include", "bin", "testing/_internal/opinfo"]:
        rm(site / "torch" / name)
    for pkg in ["numpy", "scipy"]:
        for tests in (site / pkg).rglob("tests"):
            if tests.is_dir():
                rm(tests)
    rm(site / "bin")
    for cache in list(site.rglob("__pycache__")):
        rm(cache)


def check_binaries(contents):
    """Every Mach-O must contain x86_64, need macOS <= 11.0, and every Qt framework it links must exist."""
    from macholib.MachO import MachO

    problems, count = [], 0
    for path in contents.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        with open(path, "rb") as fh:
            if fh.read(4) not in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
                continue
        count += 1
        try:
            macho = MachO(str(path))
        except Exception as exc:
            problems.append(f"{path}: unreadable ({exc})")
            continue
        headers = [h for h in macho.headers if h.header.cputype == 0x01000007]
        if not headers:
            problems.append(f"{path}: no x86_64 slice")
            continue
        header = headers[0]
        for lc, cmd, _ in header.commands:
            if lc.cmd == 0x32:  # LC_BUILD_VERSION
                raw = cmd.minos
            elif lc.cmd == 0x24:  # LC_VERSION_MIN_MACOSX
                raw = cmd.version
            else:
                continue
            version = (raw >> 16, (raw >> 8) & 0xFF)
            if version > MIN_MACOS:
                problems.append(f"{path}: needs macOS {version[0]}.{version[1]}")
        for _, _, name in header.walkRelocatables():
            if ".framework" in name and "/Qt" in name and not name.startswith("/System"):
                fw = next(p for p in name.split("/") if p.endswith(".framework"))
                if fw.replace(".framework", "") not in QT_FRAMEWORKS:
                    problems.append(f"{path}: links removed {fw}")
    print(f"checked {count} Mach-O files")
    if problems:
        raise SystemExit("\n".join(problems[:50]))


def make_icns(png, dest):
    from PIL import Image

    Image.open(png).save(dest, format="ICNS", sizes=[(16, 16), (32, 32), (64, 64), (128, 128),
                                                      (256, 256), (512, 512), (1024, 1024)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dmg-tool", required=True, help="libdmg-hfsplus `dmg` binary")
    ap.add_argument("--out", default=str(ROOT / "dist"))
    ap.add_argument("--cache", default=str(ROOT / "build" / "cache"))
    args = ap.parse_args()

    cache, out = Path(args.cache), Path(args.out)
    cache.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    work = ROOT / "build" / "portable"
    rm(work)
    app = work / "stage" / f"{APP_NAME}.app"
    contents = app / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    (contents / "Resources" / "drivers").mkdir(parents=True)

    # 1. Python runtime: Contents/MacOS/Kappa + Contents/lib (binary links @executable_path/../lib)
    py_tgz = fetch(PYTHON_URL, cache / "python.tar.gz")
    with tarfile.open(py_tgz) as tar:
        tar.extractall(work / "py", filter="tar")
    shutil.copytree(work / "py" / "python" / "lib", contents / "lib", symlinks=True)
    shutil.copy2(work / "py" / "python" / "bin" / "python3.11", contents / "MacOS" / "Kappa")
    os.chmod(contents / "MacOS" / "Kappa", 0o755)
    prune_python(contents / "lib")

    # 2. dependencies (macOS x86_64 wheels) + the app itself
    site = contents / "lib" / "python3.11" / "site-packages"
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--no-deps", "--ignore-requires-python",
                    "--target", str(site), "--platform", "macosx_11_0_x86_64", "--only-binary=:all:",
                    "--python-version", "3.11", "--implementation", "cp", "--abi", "cp311",
                    "--cache-dir", str(cache / "pip"), *WHEELS], check=True)
    prune_site(site)
    shutil.copytree(ROOT / "kappa", site / "kappa",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(ROOT / "run.py", site / "run.py")
    shutil.copytree(ROOT / "assets", site / "assets")
    (site / "sitecustomize.py").write_text(SITECUSTOMIZE)

    # 3. resources: icon, virtual mic installer, licenses
    make_icns(ROOT / "assets" / "icon.png", contents / "Resources" / "Kappa.icns")
    fetch(BLACKHOLE_URL, cache / "BlackHole2ch.pkg", BLACKHOLE_SHA256)
    shutil.copy2(cache / "BlackHole2ch.pkg", contents / "Resources" / "drivers" / "BlackHole2ch.pkg")
    (contents / "Resources" / "licenses").mkdir()
    shutil.copy2(ROOT / "kappa" / "voices" / "rvc_pack" / "LICENSE-RVC",
                 contents / "Resources" / "licenses" / "LICENSE-RVC.txt")
    (contents / "Resources" / "licenses" / "BlackHole.txt").write_text(
        "BlackHole 2ch by Existential Audio Inc., GPL-3.0, https://github.com/ExistentialAudio/BlackHole\n"
        "Shipped unmodified as the official signed installer package.\n")
    with open(contents / "Info.plist", "wb") as fh:
        plistlib.dump({
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleExecutable": "Kappa",
            "CFBundleIdentifier": "ink.kappa.voice",
            "CFBundleIconFile": "Kappa.icns",
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "CFBundleInfoDictionaryVersion": "6.0",
            "LSMinimumSystemVersion": "11.0",
            "LSArchitecturePriority": ["x86_64"],
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "NSPrincipalClass": "NSApplication",
            "NSMicrophoneUsageDescription":
                "Каппа слушает микрофон, чтобы превращать ваш голос в аниме-голос.",
            "LSApplicationCategoryType": "public.app-category.music",
            "LSEnvironment": {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"},
        }, fh)
    (contents / "PkgInfo").write_text("APPL????")

    check_binaries(contents)

    # 4. dmg: Rock Ridge ISO wrapped as a compressed UDIF image (macOS mounts it like any .dmg)
    stage = work / "stage"
    os.symlink("/Applications", stage / "Applications")
    shutil.copy2(ROOT / "packaging" / "README-dmg.txt", stage / "README.txt")
    raw = work / "uncompressed.dmg"
    subprocess.run(["xorrisofs", "-D", "-l", "-V", "Kappa", "-no-pad", "-r", "-dir-mode", "0755",
                    "-o", str(raw), str(stage)], check=True, stderr=subprocess.DEVNULL)
    dmg = out / f"Kappa-{__version__}-macOS-x64.dmg"
    rm(dmg)
    subprocess.run([args.dmg_tool, str(raw), str(dmg)], check=True, stdout=subprocess.DEVNULL)
    print(f"{dmg}  {dmg.stat().st_size / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
