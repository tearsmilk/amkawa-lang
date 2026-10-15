# PyInstaller spec — builds "Epsilon.app" (Intel x86_64, macOS 11+).
import os

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
VERSION = os.environ.get("APP_VERSION", "1.0.0")

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    datas=[
        (os.path.join(ROOT, "assets", "icon.png"), "assets"),
        (os.path.join(ROOT, "assets", "close.svg"), "assets"),
    ],
    # Pygments loads lexers/styles by name at runtime
    hiddenimports=collect_submodules("pygments.lexers") + collect_submodules("pygments.styles")
    + collect_submodules("markdown.extensions")
    + ["PySide6.QtPrintSupport", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets"],  # PDF, video / audio
    excludes=[
        "tkinter", "matplotlib", "numpy", "IPython", "PySide6.QtWebEngineCore", "PySide6.QtQml",
        "PySide6.QtQuick", "PySide6.Qt3DCore", "PySide6.QtPdf",
    ],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Epsilon", console=False,
          target_arch="x86_64", codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, name="Epsilon", strip=False, upx=False)
app = BUNDLE(
    coll,
    name="Epsilon.app",
    icon=os.path.join(ROOT, "build", "Epsilon.icns"),
    bundle_identifier="ink.epsilon.notes",
    version=VERSION,
    info_plist={
        "CFBundleDisplayName": "Epsilon",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "LSApplicationCategoryType": "public.app-category.productivity",
        "CFBundleDocumentTypes": [{
            "CFBundleTypeName": "Markdown",
            "CFBundleTypeRole": "Editor",
            "LSItemContentTypes": ["net.daringfireball.markdown"],
            "CFBundleTypeExtensions": ["md", "markdown"],
        }],
    },
)
