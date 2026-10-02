"""Entry point for the frozen (PyInstaller) builds of Habit Guard.

Every executable in a bundle is built from this one script, so it chooses what to run from the
name it was started as:

* ``HabitGuard.exe`` (Windows) and ``Habit Guard`` (inside the macOS app) are the windowed tray
  app and call :func:`habit_guard.cli.gui_main`;
* anything else, that is ``habit-guard-cli`` (Windows, macOS) and ``habit-guard`` (Linux, where
  one executable serves both roles), calls :func:`habit_guard.cli.main` with the command line.

The names are set in ``habit-guard.spec``; keep ``_GUI_EXECUTABLES`` in sync with it.
"""

from __future__ import annotations

import os
import sys

#: Case-folded stems of the windowed executables.
_GUI_EXECUTABLES = frozenset({"habitguard", "habit guard"})


def _is_gui_executable(path: str) -> bool:
    """Whether ``path`` names one of the windowed executables.

    Both separators are accepted on every system: ``os.path`` is ``posixpath`` on macOS and Linux
    and would treat a Windows path as a single file name.
    """
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    stem = os.path.splitext(name)[0]
    return stem.casefold() in _GUI_EXECUTABLES


def _run() -> int | None:
    from habit_guard import cli

    if _is_gui_executable(sys.executable):
        return cli.gui_main()
    return cli.main()


if __name__ == "__main__":
    sys.exit(_run())
