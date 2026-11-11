# PyInstaller spec — builds "Delta.app" (Дельта; Intel x86_64, macOS 11+).
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
VERSION = os.environ.get("APP_VERSION", "1.0.0")

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "assets", "icon.png"), "assets")],
    hiddenimports=["numpy", "xml.etree.ElementTree"],
    excludes=[
        "tkinter", "matplotlib", "IPython", "scipy", "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick",
        "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtPdf", "PySide6.QtNetwork",
    ],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Delta", console=False,
          target_arch="x86_64", codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, name="Delta", strip=False, upx=False)
app = BUNDLE(
    coll,
    name="Delta.app",
    icon=os.path.join(ROOT, "build", "Delta.icns"),
    bundle_identifier="ink.delta.paint",
    version=VERSION,
    info_plist={
        "CFBundleName": "Дельта",
        "CFBundleDisplayName": "Дельта",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "LSApplicationCategoryType": "public.app-category.graphics-design",
        "CFBundleDocumentTypes": [
            {"CFBundleTypeName": "Delta drawing", "CFBundleTypeRole": "Editor", "CFBundleTypeExtensions": ["delta"],
             "LSHandlerRank": "Owner"},
            {"CFBundleTypeName": "OpenRaster", "CFBundleTypeRole": "Editor", "CFBundleTypeExtensions": ["ora"],
             "LSHandlerRank": "Alternate"},
            {"CFBundleTypeName": "Image", "CFBundleTypeRole": "Editor", "LSHandlerRank": "Alternate",
             "LSItemContentTypes": ["public.png", "public.jpeg", "org.webmproject.webp", "com.compuserve.gif",
                                    "public.tiff", "com.microsoft.bmp"]},
        ],
    },
)
