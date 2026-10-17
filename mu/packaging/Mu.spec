# PyInstaller spec — builds "Mu.app" (Мю; Intel x86_64, macOS 11+).
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
VERSION = os.environ.get("APP_VERSION", "1.0.0")

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "assets", "icon.png"), "assets")],
    hiddenimports=["sounddevice", "_sounddevice"],
    excludes=[
        "tkinter", "matplotlib", "IPython", "scipy", "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick",
        "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtPdf", "PySide6.QtNetwork",
    ],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Mu", console=False,
          target_arch="x86_64", codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, name="Mu", strip=False, upx=False)
app = BUNDLE(
    coll,
    name="Mu.app",
    icon=os.path.join(ROOT, "build", "Mu.icns"),
    bundle_identifier="ink.mu.vtuber",
    version=VERSION,
    info_plist={
        "CFBundleName": "Мю",
        "CFBundleDisplayName": "Мю",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "NSMicrophoneUsageDescription": "Мю слушает микрофон, чтобы модель открывала рот, когда вы говорите (липсинк).",
        "LSApplicationCategoryType": "public.app-category.graphics-design",
        "CFBundleDocumentTypes": [
            {"CFBundleTypeName": "Mu model", "CFBundleTypeRole": "Editor", "CFBundleTypeExtensions": ["mu"],
             "LSHandlerRank": "Owner"},
            {"CFBundleTypeName": "Photoshop document", "CFBundleTypeRole": "Viewer", "LSHandlerRank": "Alternate",
             "CFBundleTypeExtensions": ["psd"]},
            {"CFBundleTypeName": "Inochi2D puppet", "CFBundleTypeRole": "Viewer", "LSHandlerRank": "Alternate",
             "CFBundleTypeExtensions": ["inp"]},
        ],
    },
)
