# PyInstaller spec — builds "Nu.app" (Ню; Intel x86_64, macOS 11+).
import os

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
VERSION = os.environ.get("APP_VERSION", "1.0.0")
ASSETS = ["icon.png", "close.svg", "close-hover.svg", "chevron-right.svg", "chevron-down.svg"]

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "assets", name), "assets") for name in ASSETS],
    # Pygments loads lexers / styles by name at runtime
    hiddenimports=collect_submodules("pygments.lexers") + collect_submodules("pygments.styles")
    + collect_submodules("pyte") + ["wcwidth"],
    excludes=[
        "tkinter", "matplotlib", "numpy", "IPython", "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick",
        "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtPdf",
    ],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Nu", console=False,
          target_arch="x86_64", codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, name="Nu", strip=False, upx=False)
app = BUNDLE(
    coll,
    name="Nu.app",
    icon=os.path.join(ROOT, "build", "Nu.icns"),
    bundle_identifier="ink.nu.editor",
    version=VERSION,
    info_plist={
        "CFBundleName": "Ню",
        "CFBundleDisplayName": "Ню",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "LSApplicationCategoryType": "public.app-category.developer-tools",
        "CFBundleDocumentTypes": [
            {"CFBundleTypeName": "Folder", "CFBundleTypeRole": "Editor", "LSItemContentTypes": ["public.folder"]},
            {"CFBundleTypeName": "Source code", "CFBundleTypeRole": "Editor", "LSHandlerRank": "Alternate",
             "LSItemContentTypes": ["public.source-code", "public.plain-text", "public.script", "public.json",
                                    "public.xml", "public.yaml", "net.daringfireball.markdown", "public.shell-script",
                                    "public.python-script", "com.netscape.javascript-source", "public.data"]},
        ],
    },
)
