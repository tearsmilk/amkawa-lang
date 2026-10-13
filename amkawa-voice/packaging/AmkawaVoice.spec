# PyInstaller spec — builds "Amkawa Voice.app" (Intel x86_64, macOS 11+).
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
VERSION = os.environ.get("APP_VERSION", "1.0.0")

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    datas=[
        (os.path.join(ROOT, "assets", "icon.png"), "assets"),
        (os.path.join(ROOT, "amkawa_voice", "voices", "rvc_pack", "LICENSE-RVC"), "licenses"),
    ],
    hiddenimports=["amkawa_voice.voices.rvc_pack.models"],
    excludes=[
        "tkinter", "matplotlib", "IPython", "pandas", "torchvision", "torchaudio", "tensorboard",
        "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore",
        "PySide6.QtMultimedia", "PySide6.QtNetwork", "PySide6.QtPdf",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="AmkawaVoice",
    console=False,
    target_arch="x86_64",
    codesign_identity=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="AmkawaVoice", strip=False, upx=False)
app = BUNDLE(
    coll,
    name="Amkawa Voice.app",
    icon=os.path.join(ROOT, "build", "AmkawaVoice.icns"),
    bundle_identifier="ink.amkawa.voice",
    version=VERSION,
    info_plist={
        "CFBundleDisplayName": "Amkawa Voice",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "NSMicrophoneUsageDescription":
            "Amkawa Voice слушает микрофон, чтобы превращать ваш голос в аниме-голос.",
        "LSApplicationCategoryType": "public.app-category.music",
    },
)
