# PyInstaller spec — builds "Lambda.app" (Лямбда; Intel x86_64, macOS 11+).
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
VERSION = os.environ.get("APP_VERSION", "1.0.0")

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "assets", "icon.png"), "assets")],
    hiddenimports=["xml.etree.ElementTree"],
    excludes=[
        "tkinter", "matplotlib", "IPython", "scipy", "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick",
        "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtPdf", "PySide6.QtNetwork", "numpy",
    ],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Lambda", console=False,
          target_arch="x86_64", codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, name="Lambda", strip=False, upx=False)
app = BUNDLE(
    coll,
    name="Lambda.app",
    icon=os.path.join(ROOT, "build", "Lambda.icns"),
    bundle_identifier="ink.lambda.design",
    version=VERSION,
    info_plist={
        "CFBundleName": "Лямбда",
        "CFBundleDisplayName": "Лямбда",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "LSApplicationCategoryType": "public.app-category.graphics-design",
        "CFBundleDocumentTypes": [
            {"CFBundleTypeName": "Lambda document", "CFBundleTypeRole": "Editor", "CFBundleTypeExtensions": ["lambda"],
             "LSHandlerRank": "Owner"},
            {"CFBundleTypeName": "Image", "CFBundleTypeRole": "Viewer", "LSHandlerRank": "Alternate",
             "LSItemContentTypes": ["public.png", "public.jpeg", "public.svg-image", "com.compuserve.gif"]},
        ],
    },
)
