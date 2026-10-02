# PyInstaller spec for Habit Guard. Run from the repository root:
#
#   uv run --group build pyinstaller packaging/pyinstaller/habit-guard.spec --noconfirm --clean
#
# Output (in dist/):
#   Windows  HabitGuard/         HabitGuard.exe (tray app, no console) and habit-guard-cli.exe
#   macOS    Habit Guard.app     the tray app, with habit-guard-cli next to it in Contents/MacOS
#   Linux    habit-guard/        one executable, habit-guard, that is both
#
# What goes in: the three ONNX models (vision/models), and nothing of Qt that the app does not
# use. In particular Qt's network module and its plugins stay out: the privacy promise is "no
# networking code", and a smaller bundle is a bonus. The bundle is checked by `habit-guard
# selftest` in CI (models, vision, tones and the Qt windows all work from the frozen copy).
import re
import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parents[1]  # noqa: F821 - SPECPATH is set by PyInstaller
SRC = ROOT / "src"
ENTRY = str(ROOT / "packaging" / "pyinstaller" / "entry.py")

VERSION = re.search(
    r'^__version__ = "(.+)"$', (SRC / "habit_guard" / "__init__.py").read_text(encoding="utf-8"), re.M
).group(1)
NUMERIC = re.match(r"\d+(\.\d+){0,2}", VERSION).group(0)

WINDOWS = sys.platform == "win32"
MACOS = sys.platform == "darwin"

ICON = None
if WINDOWS:
    ICON = str(ROOT / "packaging" / "windows" / "habit-guard.ico")
elif MACOS:
    ICON = str(ROOT / "packaging" / "macos" / "habit-guard.icns")

# Parts of Qt and the standard library that the app never imports.
EXCLUDES = [
    "PySide6.QtNetwork",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtMultimedia",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.Qt3DCore",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "tkinter",
    "unittest",
    "pydoc",
    "doctest",
    "pytest",
    "PIL",
]

a = Analysis(  # noqa: F821
    [ENTRY],
    pathex=[str(SRC)],
    binaries=[],
    datas=[(str(SRC / "habit_guard" / "vision" / "models"), "habit_guard/vision/models")],
    hiddenimports=["habit_guard.app", "habit_guard.diagnostics"],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)

# Files that nothing in the app uses, and that PyInstaller's Qt and OpenCV hooks collect anyway:
# the software OpenGL renderer (the app draws with Qt's raster engine), Qt's network and SVG
# libraries, Qt's translations (the app has its own texts) and, on Windows, OpenCV's FFmpeg
# (camera capture uses DirectShow and Media Foundation; only video-file replay needs FFmpeg, which
# works when running from source).
_DROP = (
    "opengl32sw",
    "qt6network",
    "qt6svg",
    "qt6pdf",
    "qt6quick",
    "qt6qml",
    "qt6opengl",
    "qt6virtualkeyboard",
    "opencv_videoio_ffmpeg",
    "/iconengines/",
    "pyside6/translations/",
)


def _keep(entry):
    name = "/" + entry[0].replace("\\", "/").lower()
    return not any(part in name for part in _DROP)


a.binaries = [entry for entry in a.binaries if _keep(entry)]
a.datas = [entry for entry in a.datas if _keep(entry)]
pyz = PYZ(a.pure)  # noqa: F821


def program(name: str, console: bool):
    return EXE(  # noqa: F821
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=name,
        console=console,
        icon=ICON,
        upx=False,
        disable_windowed_traceback=False,
    )


if WINDOWS:
    gui = program("HabitGuard", console=False)
    cli = program("habit-guard-cli", console=True)
    bundle = COLLECT(gui, cli, a.binaries, a.datas, upx=False, name="HabitGuard")  # noqa: F821
elif MACOS:
    gui = program("Habit Guard", console=False)
    cli = program("habit-guard-cli", console=True)
    coll = COLLECT(gui, cli, a.binaries, a.datas, upx=False, name="Habit Guard")  # noqa: F821
    app = BUNDLE(  # noqa: F821
        coll,
        name="Habit Guard.app",
        icon=ICON,
        bundle_identifier="io.github.bugraskl.habit-guard",
        version=VERSION,
        info_plist={
            "CFBundleName": "Habit Guard",
            "CFBundleDisplayName": "Habit Guard",
            "CFBundleShortVersionString": NUMERIC,
            "CFBundleVersion": NUMERIC,
            "LSMinimumSystemVersion": "14.0",
            "LSUIElement": True,  # a tray app: no Dock icon
            "NSHighResolutionCapable": True,
            "NSCameraUsageDescription": (
                "Habit Guard watches the camera for a hand going to your face. "
                "Pictures are analysed in memory and never saved."
            ),
            "NSHumanReadableCopyright": "Copyright (c) 2026 Buğra Şıkel. MIT License.",
        },
    )
else:
    main = program("habit-guard", console=True)
    bundle = COLLECT(main, a.binaries, a.datas, upx=False, name="habit-guard")  # noqa: F821
