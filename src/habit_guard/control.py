"""Controlling a running Habit Guard from the command line (``habit-guard ctl``).

The two sides talk through small files in the settings folder, not through a socket, so the app
needs no networking code at all (the privacy scan would refuse it). ``ctl`` drops a command file
into ``control/``; the running app notices it (a file watcher, with a slow timer as a safety net),
carries it out and deletes it. The app writes ``status.json`` when its state changes and every few
seconds as a heartbeat, which is what ``ctl status`` reads and what tells a running app from a
stale file left by a crash.

This module is plain file handling and imports neither Qt nor OpenCV. Commands come from the
same user's own folder, so any program that can write there can already change the settings; the
list below is the whole vocabulary.
"""

from __future__ import annotations

import contextlib
import itertools
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from . import paths
from .stats import write_json_atomic

#: What ``ctl`` can ask a running app to do.
COMMANDS = (
    "quit",
    "pause",
    "resume",
    "toggle",
    "test",
    "settings",
    "wizard",
    "preview",
    "stats",
)
#: ``habit-guard ctl status`` exit code when no instance is running (the installer relies on it).
EXIT_NOT_RUNNING = 3
#: A status file older than this many seconds does not come from a running app.
STALE_AFTER_S = 15.0
#: How often a running app refreshes its status file.
HEARTBEAT_S = 5.0

#: Makes file names unique and ordered within one process, whatever the clock's resolution
#: (Windows' clock ticks about every 15 ms, so two quick commands can share a timestamp).
_counter = itertools.count()


def control_dir() -> Path:
    return paths.config_dir() / "control"


def status_path() -> Path:
    return paths.config_dir() / "status.json"


# ---------------------------------------------------------------------------- the ctl side
def send(command: str) -> Path:
    """Ask a running app to do ``command``; returns the file written.

    Raises:
        ValueError: ``command`` is not one of :data:`COMMANDS`.
    """
    if command not in COMMANDS:
        raise ValueError(f"unknown command {command!r}; known: {', '.join(COMMANDS)}")
    folder = control_dir()
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{time.time_ns():020d}-{next(_counter):06d}-{os.getpid()}-{secrets.token_hex(3)}.cmd"
    path = folder / name
    tmp = folder / (name + ".part")
    tmp.write_text(command + "\n", encoding="utf-8")
    os.replace(tmp, path)  # the app never sees a half-written command
    return path


def read_status() -> dict[str, Any] | None:
    """The app's last status, or ``None`` when no app is running (no file, or a stale one)."""
    try:
        data = json.loads(status_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    updated = data.get("updated")
    if not isinstance(updated, (int, float)) or time.time() - updated > STALE_AFTER_S:
        return None
    return data


def wait_until_stopped(timeout: float = 10.0, interval: float = 0.25) -> bool:
    """Wait for a running app to stop; ``True`` once it has (or none was running)."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if read_status() is None:
            return True
        time.sleep(interval)
    return read_status() is None


# ----------------------------------------------------------------------------- the app side
def pending() -> list[tuple[Path, str]]:
    """Waiting commands, oldest first, as ``(file, command)``. Unknown ones are dropped."""
    folder = control_dir()
    try:
        files = sorted(p for p in folder.iterdir() if p.suffix == ".cmd")
    except OSError:
        return []
    found: list[tuple[Path, str]] = []
    for path in files:
        try:
            command = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        except ValueError:  # not UTF-8: no command, and it must not block the others
            command = ""
        if command in COMMANDS:
            found.append((path, command))
        else:
            with contextlib.suppress(OSError):
                path.unlink()
    return found


def consume(path: Path) -> None:
    with contextlib.suppress(OSError):
        path.unlink()


def discard_pending() -> None:
    """Delete the commands that are waiting.

    A starting app drops what an earlier one left behind (a second ``quit`` from a double
    click, or a command sent just after a crash), and a quitting app drops what is queued
    behind its ``quit``, so none of it reaches the next run.
    """
    try:
        files = [p for p in control_dir().iterdir() if p.suffix in (".cmd", ".part")]
    except OSError:
        return
    for path in files:
        consume(path)


def write_status(state: dict[str, Any]) -> None:
    """Publish the app's state; ``updated`` is added here."""
    write_json_atomic(status_path(), {**state, "pid": os.getpid(), "updated": time.time()})


def clear_status() -> None:
    """Remove the status file (the app is quitting)."""
    with contextlib.suppress(OSError):
        status_path().unlink()
