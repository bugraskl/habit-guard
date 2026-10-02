"""``habit-guard doctor`` and ``habit-guard bench``.

The doctor report is meant to be pasted into a bug report: it lists versions,
paths and the state of the model files, and contains no pictures. Paths inside
your home folder are shown with ``~`` so your user name does not travel with it.
"""

from __future__ import annotations

import os
import platform
import threading
import time
from pathlib import Path

from . import __version__, autostart, paths
from .config import Settings
from .logging_setup import log_path
from .vision import manifest
from .vision.camera import probe_cameras
from .vision.pipeline import Pipeline, Status


def short_path(path: str | Path) -> str:
    """``path`` with the home folder replaced by ``~``."""
    text = str(path)
    home = str(Path.home())
    return "~" + text[len(home) :] if text.startswith(home) else text


def report(*, probe: bool = False) -> str:
    import cv2
    import numpy

    lines = [
        f"habit-guard      {__version__}",
        f"python           {platform.python_version()} ({platform.python_implementation()})",
        f"platform         {platform.platform()}",
        f"opencv           {cv2.__version__}",
        f"numpy            {numpy.__version__}",
    ]
    try:
        import PySide6

        lines.append(f"pyside6          {PySide6.__version__}")
    except ImportError:
        lines.append("pyside6          NOT INSTALLED")
    lines += [
        f"config folder    {short_path(paths.config_dir())}",
        f"log file         {short_path(log_path())}",
        f"autostart        {'on' if autostart.is_enabled() else 'off'}",
    ]
    settings = Settings.load(paths.settings_path())
    enabled = [h for h, c in settings.habits.items() if c.enabled]
    lines += [
        f"habits on        {', '.join(enabled) or 'none'}",
        f"profile          {settings.profile}",
        f"camera index     {settings.camera_index}",
        "models:",
    ]
    for name, state in manifest.verify(paths.models_dir()).items():
        lines.append(f"  {state:<9}{name}")
    if probe:
        lines.append("cameras (this switches each camera on briefly):")
        found = probe_cameras()
        lines += [f"  {i}: {size}" for i, size in found] or ["  none opened"]
    else:
        lines.append("cameras          (run `habit-guard doctor --probe-cameras` to list them)")
    return "\n".join(lines)


def bench(seconds: float, source: int | str | None) -> str:
    """Run the camera pipeline for ``seconds`` and report the CPU use and the analysis time."""
    settings = Settings.load(paths.settings_path())
    observed = 0
    failure: list[str] = []
    ready = threading.Event()

    def on_observation(obs: object) -> None:
        nonlocal observed
        observed += 1

    def on_status(status: Status, detail: str) -> None:
        if status in (Status.NO_CAMERA, Status.ERROR):
            failure.append(f"{status.value}: {detail}")
            ready.set()

    pipeline = Pipeline(settings, on_observation, on_status, source=source)
    cpu_start, wall_start = time.process_time(), time.perf_counter()
    pipeline.start()
    ready.wait(seconds)
    pipeline.stop()
    cpu = time.process_time() - cpu_start
    wall = time.perf_counter() - wall_start
    if failure:
        return f"bench could not run: {failure[0]}"
    cores = os.cpu_count() or 1
    analysed = max(pipeline.analyses, 1)
    return "\n".join(
        [
            f"ran for          {wall:.1f} s with profile '{settings.profile}'",
            f"CPU              {100 * cpu / wall:.1f} % of one core, "
            f"{100 * cpu / wall / cores:.2f} % of this machine ({cores} threads)",
            f"analyses         {pipeline.analyses} "
            f"({pipeline.skipped} pictures skipped as unchanged)",
            f"per analysis     {1000 * pipeline.analysis_s / analysed:.1f} ms on average",
            f"observations     {observed}",
            "Nobody in view and no hand near the face is the idle case; move your hand to",
            "your mouth during the run to see the cost of fast analysis.",
        ]
    )
