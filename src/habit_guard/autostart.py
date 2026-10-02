"""Start Habit Guard when you log in, on Windows, macOS and Linux.

Windows uses the per-user ``Run`` registry key, macOS a LaunchAgent and Linux
an XDG autostart entry. All of them live in your own profile and need no
administrator rights; ``disable`` removes exactly what ``enable`` added.
"""

from __future__ import annotations

import os
import shlex
import shutil
import sys
from pathlib import Path
from xml.sax.saxutils import escape

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "HabitGuard"
PLIST_NAME = "io.github.bugraskl.habit-guard.plist"
DESKTOP_NAME = "habit-guard.desktop"
#: Case-folded stems of the windowed programs of a frozen build; keep in sync with
#: ``_GUI_EXECUTABLES`` in packaging/pyinstaller/entry.py.
_GUI_STEMS = frozenset({"habitguard", "habit guard"})


def launch_command() -> list[str]:
    """The command that starts the tray app without a console window."""
    if getattr(sys, "frozen", False):
        return [_frozen_gui_executable()]
    gui = shutil.which("habit-guard-gui")
    if gui:
        return [gui]
    python = Path(sys.executable)
    if sys.platform == "win32":
        pythonw = python.with_name("pythonw.exe")
        if pythonw.is_file():
            python = pythonw
    return [str(python), "-m", "habit_guard"]


def _frozen_gui_executable() -> str:
    """The windowed program of an installed copy, whichever of its programs is running.

    ``habit-guard autostart enable`` runs a console program (``habit-guard.exe`` and
    ``habit-guard-cli.exe`` on Windows), but at login the windowed one must start. An
    AppImage runs from a temporary mount, so its own path is used instead.
    """
    appimage = os.environ.get("APPIMAGE")
    if appimage:
        return appimage
    exe = Path(sys.executable)
    if exe.stem.casefold() in _GUI_STEMS:
        return str(exe)
    for name in ("HabitGuard.exe", "Habit Guard"):
        sibling = exe.with_name(name)
        if sibling.is_file():
            return str(sibling)
    return str(exe)  # Linux: one program serves both roles


def _windows_command(command: list[str]) -> str:
    return " ".join(f'"{part}"' for part in command)


def plist_text(command: list[str]) -> str:
    args = "\n".join(f"    <string>{escape(part)}</string>" for part in command)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n<dict>\n'
        f"  <key>Label</key>\n  <string>{PLIST_NAME[:-6]}</string>\n"
        f"  <key>ProgramArguments</key>\n  <array>\n{args}\n  </array>\n"
        "  <key>RunAtLoad</key>\n  <true/>\n</dict>\n</plist>\n"
    )


def desktop_text(command: list[str]) -> str:
    return (
        "[Desktop Entry]\nType=Application\nName=Habit Guard\n"
        "Comment=Stops nail biting and similar habits through your webcam\n"
        f"Exec={shlex.join(command)}\nTerminal=false\nX-GNOME-Autostart-enabled=true\n"
    )


def _file_target() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "LaunchAgents" / PLIST_NAME
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "autostart" / DESKTOP_NAME


def is_enabled() -> bool:
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.QueryValueEx(key, RUN_VALUE)
            return True
        except OSError:
            return False
    return _file_target().is_file()


def enable() -> str:
    """Turn autostart on; returns the command that will be run."""
    command = launch_command()
    if sys.platform == "win32":
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, _windows_command(command))
        return _windows_command(command)
    target = _file_target()
    target.parent.mkdir(parents=True, exist_ok=True)
    text = plist_text(command) if sys.platform == "darwin" else desktop_text(command)
    target.write_text(text, encoding="utf-8")
    return shlex.join(command)


def disable() -> bool:
    """Turn autostart off; ``False`` if it was not on."""
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, RUN_VALUE)
            return True
        except OSError:
            return False
    target = _file_target()
    if target.is_file():
        target.unlink()
        return True
    return False
