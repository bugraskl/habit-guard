"""The command line: ``habit-guard`` starts the tray app, the subcommands help around it."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Sequence
from datetime import date

from . import __version__, autostart, control, paths


def _camera_source(value: str | None) -> int | str | None:
    """``--camera 1`` is a camera number, ``--camera clip.mp4`` a video file."""
    if value is None:
        return None
    return int(value) if value.isdigit() else value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="habit-guard",
        description="Catches nail biting, mustache pulling, hair pulling and face touching "
        "through your webcam and nudges you to stop.",
    )
    parser.add_argument("--version", action="version", version=f"habit-guard {__version__}")
    parser.add_argument("--config-dir", help="keep settings and statistics in this folder")
    parser.add_argument("--debug", action="store_true", help="log more detail")
    parser.add_argument("--camera", help="camera number, or a video file to play instead")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="start the tray app (the default)")
    run.add_argument("--camera", default=argparse.SUPPRESS, help="camera number or video file")

    doctor = sub.add_parser("doctor", help="print a diagnostics report for bug reports")
    doctor.add_argument("--probe-cameras", action="store_true", help="also list working cameras")

    bench = sub.add_parser("bench", help="measure CPU use and analysis time")
    bench.add_argument("--seconds", type=float, default=20.0, help="how long to run (default 20)")
    bench.add_argument("--camera", default=argparse.SUPPRESS, help="camera number or video file")

    sub.add_parser("stats", help="print the statistics")

    ctl = sub.add_parser("ctl", help="control a running Habit Guard")
    ctl.add_argument(
        "action",
        choices=(*control.COMMANDS, "status"),
        help="status prints the state; the others ask the running app to do it",
    )
    ctl.add_argument("--timeout", type=float, default=10.0, help="how long quit waits (seconds)")

    sub.add_parser("selftest", help="check that the models, the camera code and the windows work")

    reset = sub.add_parser("reset", help="forget settings and statistics")
    reset.add_argument("--yes", action="store_true", help="do not ask first")

    auto = sub.add_parser("autostart", help="start Habit Guard at login")
    auto.add_argument("action", choices=("enable", "disable", "status"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.config_dir:
        os.environ[paths.HOME_ENV] = args.config_dir
    command = args.command or "run"

    if command == "doctor":
        from . import diagnostics

        print(diagnostics.report(probe=args.probe_cameras))
        return 0
    if command == "bench":
        from . import diagnostics

        print(diagnostics.bench(args.seconds, _camera_source(args.camera)))
        return 0
    if command == "stats":
        return _print_stats()
    if command == "ctl":
        return _ctl(args.action, args.timeout)
    if command == "selftest":
        return _selftest()
    if command == "reset":
        return _reset(args.yes)
    if command == "autostart":
        return _autostart(args.action)
    return _run(args)


def gui_main() -> int:
    """Entry point of the console-less launcher (``habit-guard-gui``)."""
    return main([])


# ------------------------------------------------------------------------------ commands
def _run(args: argparse.Namespace) -> int:
    from . import logging_setup
    from .app import run
    from .config import Settings

    logging_setup.setup(args.debug)
    settings = Settings.load(paths.settings_path())
    return run(settings, _camera_source(args.camera))


def _ctl(action: str, timeout: float) -> int:
    status = control.read_status()
    if action == "status":
        if status is None:
            print("Habit Guard is not running.")
            return control.EXIT_NOT_RUNNING
        print(
            f"running  pid {status.get('pid')}  version {status.get('version')}  "
            f"state {status.get('state')}  alarms today {status.get('today')}"
        )
        return 0
    if status is None:
        print("Habit Guard is not running.", file=sys.stderr)
        return control.EXIT_NOT_RUNNING
    control.send(action)
    if action == "quit":
        if control.wait_until_stopped(timeout):
            print("Habit Guard has quit.")
            return 0
        print("Habit Guard did not quit in time.", file=sys.stderr)
        return 1
    print(f"Sent: {action}")
    return 0


def _selftest() -> int:
    """Exercise what a broken installation would lack: models, vision, tones, Qt windows.

    Runs in a scratch settings folder with Qt's offscreen platform, so it opens no window and
    touches none of your files. A frozen build runs it in CI.
    """
    import tempfile

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ[paths.HOME_ENV] = tempfile.mkdtemp(prefix="habit-guard-selftest-")
    failures: list[str] = []

    def check(name: str, run: Callable[[], str]) -> None:
        try:
            detail = run()
        except Exception as exc:
            failures.append(name)
            print(f"  FAILED   {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"  ok       {name}{(': ' + detail) if detail else ''}")

    def models() -> str:
        from .vision import manifest

        states = manifest.verify(paths.models_dir())
        bad = {n: s for n, s in states.items() if s != "ok"}
        if bad:
            raise RuntimeError(f"model files not ok: {bad}")
        return f"{len(states)} files verified"

    def vision() -> str:
        import numpy as np

        from .config import CADENCES
        from .vision.pipeline import build_analyzer

        step = build_analyzer().step(np.zeros((480, 640, 3), np.uint8), 0.0, CADENCES["balanced"])
        if step.observation is None:
            raise RuntimeError("the first picture was not analysed")
        return "face and hand models ran on a blank picture"

    def tones() -> str:
        from .alerts.sound import wav_bytes

        sizes = [len(wav_bytes(level)) for level in (1, 2, 3)]
        if min(sizes) < 1000:
            raise RuntimeError(f"tones are too short: {sizes}")
        return "alarm tones made"

    def windows() -> str:
        from PySide6.QtWidgets import QApplication

        from .config import Settings
        from .ui.preview import PreviewWindow
        from .ui.settings_dialog import SettingsDialog
        from .ui.stats_dialog import StatsDialog
        from .ui.tray import Tray

        existing = QApplication.instance()
        app = existing if isinstance(existing, QApplication) else QApplication([])
        _ = Tray()
        for widget in (SettingsDialog(Settings()), PreviewWindow(), StatsDialog()):
            widget.show()
            app.processEvents()
            if widget.grab().isNull():
                raise RuntimeError(f"{type(widget).__name__} did not draw")
            widget.close()
        return "tray, settings, preview and statistics windows drew"

    print(f"habit-guard {__version__} selftest")
    check("models", models)
    check("vision", vision)
    check("sound", tones)
    check("windows", windows)
    if failures:
        print(f"selftest failed: {', '.join(failures)}", file=sys.stderr)
        return 1
    print("selftest passed")
    return 0


def _print_stats() -> int:
    from .i18n import habit_name, set_language
    from .stats import Stats

    set_language("auto")
    stats = Stats.load(paths.stats_path())
    today = date.today()
    print(f"today        {stats.count(today)}")
    print(f"all time     {stats.total()}")
    print(f"clean for    {stats.clean_s / 60:.0f} min (best {stats.best_clean_s / 60:.0f} min)")
    for d, n in stats.last_days(today, 7):
        print(f"  {d.isoformat()}  {'#' * n} {n}")
    from .config import Settings
    from .i18n import set_custom_names
    from .types import Habit

    set_custom_names(Settings.load(paths.settings_path()).custom_names())
    for habit in Habit:
        if habit.is_custom and stats.total(habit) == 0:
            continue  # a zone the user drew, with nothing counted yet
        print(f"{habit_name(habit):<36}{stats.total(habit)}")
    return 0


def _reset(yes: bool) -> int:
    folder = paths.config_dir()
    targets = [p for p in (paths.settings_path(), paths.stats_path()) if p.exists()]
    if not targets:
        print("Nothing to reset.")
        return 0
    if not yes:
        answer = input(f"Delete {', '.join(p.name for p in targets)} in {folder}? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Left everything as it was.")
            return 1
    for target in targets:
        target.unlink()
    print("Settings and statistics were reset.")
    return 0


def _autostart(action: str) -> int:
    if action == "enable":
        print(f"Autostart on: {autostart.enable()}")
    elif action == "disable":
        print("Autostart off." if autostart.disable() else "Autostart was not on.")
    else:
        print("Autostart is on." if autostart.is_enabled() else "Autostart is off.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
