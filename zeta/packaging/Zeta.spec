# PyInstaller spec — builds "Zeta.app" (Дзета; Intel x86_64, macOS 11+).
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
VERSION = os.environ.get("APP_VERSION", "1.0.0")

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "assets", name), "assets") for name in ("icon.png", "zeta-sprite.png")],
    excludes=[
        "tkinter", "matplotlib", "numpy", "IPython", "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick",
        "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtPdf", "PySide6.QtNetwork",
    ],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Zeta", console=False,
          target_arch="x86_64", codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, name="Zeta", strip=False, upx=False)
app = BUNDLE(
    coll,
    name="Zeta.app",
    icon=os.path.join(ROOT, "build", "Zeta.icns"),
    bundle_identifier="ink.zeta.pixel",
    version=VERSION,
    info_plist={
        "CFBundleName": "Дзета",
        "CFBundleDisplayName": "Дзета",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "LSApplicationCategoryType": "public.app-category.graphics-design",
        "CFBundleDocumentTypes": [
            {"CFBundleTypeName": "Aseprite sprite", "CFBundleTypeRole": "Editor",
             "CFBundleTypeExtensions": ["aseprite", "ase"], "LSHandlerRank": "Default"},
            {"CFBundleTypeName": "Image", "CFBundleTypeRole": "Editor", "LSHandlerRank": "Alternate",
             "LSItemContentTypes": ["public.png", "com.compuserve.gif", "public.jpeg", "com.microsoft.bmp"]},
        ],
    },
)
