# PyInstaller spec — builds "Theta.app" (Тета; Intel x86_64, macOS 11+). QtWebEngine (Street View) is kept:
# PyInstaller's PySide6.QtWebEngineCore hook bundles QtWebEngineProcess.app and its resources into the bundle.
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
VERSION = os.environ.get("APP_VERSION", "1.0.0")

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "assets", "icon.png"), "assets"),
           (os.path.join(ROOT, "assets", "countries.json"), "assets")],
    hiddenimports=["PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineCore", "PySide6.QtWebChannel", "PySide6.QtNetwork"],
    excludes=[
        "tkinter", "matplotlib", "IPython", "scipy", "numpy", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore",
        "PySide6.QtMultimedia", "PySide6.QtPdf", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtXml",
        "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSensors",
        "PySide6.QtSerialPort", "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtTextToSpeech",
    ],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Theta", console=False,
          target_arch="x86_64", codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, name="Theta", strip=False, upx=False)
app = BUNDLE(
    coll,
    name="Theta.app",
    icon=os.path.join(ROOT, "build", "Theta.icns"),
    bundle_identifier="ink.theta.game",
    version=VERSION,
    info_plist={
        "CFBundleName": "Тета",
        "CFBundleDisplayName": "Тета",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "LSApplicationCategoryType": "public.app-category.games",
        "NSAppTransportSecurity": {"NSAllowsArbitraryLoads": True},
    },
)
