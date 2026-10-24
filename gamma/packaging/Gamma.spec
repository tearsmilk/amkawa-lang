# PyInstaller spec — builds "Gamma.app" (Гамма; Intel x86_64, macOS 11+) with the static ffmpeg inside.
import os
import shutil

import imageio_ffmpeg

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
VERSION = os.environ.get("APP_VERSION", "1.0.0")
FF_DIR = os.path.join(ROOT, "build", "ffmpeg-bin")
os.makedirs(FF_DIR, exist_ok=True)
FF = os.path.join(FF_DIR, "ffmpeg")
shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(), FF)  # ffmpeg 7.1, avfoundation + VideoToolbox + x264, minos 11.0
os.chmod(FF, 0o755)

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    binaries=[(FF, "ffmpeg")],
    datas=[(os.path.join(ROOT, "assets", "icon.png"), "assets")],
    excludes=[
        "tkinter", "matplotlib", "IPython", "scipy", "numpy", "imageio_ffmpeg", "PySide6.QtWebEngineCore",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtPdf",
        "PySide6.QtNetwork", "PySide6.QtOpenGL", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtXml",
    ],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Gamma", console=False,
          target_arch="x86_64", codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, name="Gamma", strip=False, upx=False)
app = BUNDLE(
    coll,
    name="Gamma.app",
    icon=os.path.join(ROOT, "build", "Gamma.icns"),
    bundle_identifier="ink.gamma.recorder",
    version=VERSION,
    info_plist={
        "CFBundleName": "Гамма",
        "CFBundleDisplayName": "Гамма",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "NSMicrophoneUsageDescription": "Гамма записывает звук с микрофона в видео, когда вы включаете запись со звуком.",
        "LSApplicationCategoryType": "public.app-category.productivity",
    },
)
