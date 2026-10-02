"""The camera thread: grabs pictures, runs the analysis, hands observations to the app.

It owns the camera. Pausing (or privacy) releases it completely, which switches
the webcam's light off; a camera that another program has taken is retried
quietly until it comes back.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

import cv2

from ..config import Settings
from ..paths import models_dir
from ..types import Observation
from .analyzer import Analyzer
from .camera import Camera
from .face import YUNET_MODEL, FaceDetector
from .hands import HAND_MODEL, PALM_MODEL, HandLandmarker, HandTracker, PalmDetector

log = logging.getLogger(__name__)

#: Seconds before a missing or busy camera is tried again.
CAMERA_RETRY_S = 3.0
#: Consecutive failed grabs after which the camera is considered gone.
MAX_GRAB_FAILURES = 5
#: Threads OpenCV may use for one inference; few threads keep the peak CPU low.
INFERENCE_THREADS = 2


class Status(StrEnum):
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    NO_CAMERA = "no_camera"
    ERROR = "error"


class ModelError(RuntimeError):
    """A model file is missing."""


def build_analyzer(directory: Path | None = None) -> Analyzer:
    """Load the three models and wire up an :class:`Analyzer`.

    Raises:
        ModelError: A model file is missing from ``directory``.
    """
    base = directory or models_dir()
    missing = [n for n in (YUNET_MODEL, PALM_MODEL, HAND_MODEL) if not (base / n).is_file()]
    if missing:
        raise ModelError(
            f"Missing model file(s) in {base}: {', '.join(missing)}. "
            "Run: python scripts/fetch_models.py"
        )
    cv2.setNumThreads(INFERENCE_THREADS)
    faces = FaceDetector(base / YUNET_MODEL)
    hands = HandTracker(PalmDetector(base / PALM_MODEL), HandLandmarker(base / HAND_MODEL))
    return Analyzer(faces, hands)


class Pipeline:
    """Runs the camera loop on its own thread."""

    def __init__(
        self,
        settings: Settings,
        on_observation: Callable[[Observation], None],
        on_status: Callable[[Status, str], None] | None = None,
        *,
        source: int | str | None = None,
        analyzer: Analyzer | None = None,
        camera_factory: Callable[[int | str, str], Camera] = Camera,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._settings = settings
        self._on_observation = on_observation
        self._on_status = on_status or (lambda status, detail: None)
        self._source_override = source
        self._analyzer = analyzer
        self._camera_factory = camera_factory
        self._clock = clock
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._paused = False
        self._preview = False
        self._thread: threading.Thread | None = None
        self._camera: Camera | None = None
        self._next_at = 0.0
        self._failures = 0
        self._status: Status | None = None
        # Counters for `habit-guard bench`.
        self.analyses = 0
        self.skipped = 0
        self.analysis_s = 0.0

    # ------------------------------------------------------------------------------- control
    def start(self, paused: bool = False) -> None:
        if self._thread is not None:
            return
        self._paused = paused
        self._thread = threading.Thread(target=self._run, name="habit-guard-camera", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None

    def pause(self) -> None:
        self._paused = True
        self._wake.set()

    def resume(self) -> None:
        self._paused = False
        self._wake.set()

    @property
    def paused(self) -> bool:
        return self._paused

    def set_preview(self, on: bool) -> None:
        """While on, every observation carries its camera picture and analysis runs fast."""
        self._preview = on

    def apply_settings(self, settings: Settings) -> None:
        """Take new settings; a changed camera number is picked up by the loop."""
        self._settings = settings

    # --------------------------------------------------------------------------------- loop
    def _emit_status(self, status: Status, detail: str = "") -> None:
        if status != self._status:
            self._status = status
            self._on_status(status, detail)

    def _wait(self, seconds: float) -> None:
        """Sleep, but wake early on pause, resume or stop."""
        self._wake.wait(seconds)
        self._wake.clear()

    def _run(self) -> None:
        self._emit_status(Status.STARTING)
        try:
            analyzer = self._analyzer or build_analyzer()
        except Exception as exc:
            log.exception("could not start the analysis")
            self._emit_status(Status.ERROR, str(exc))
            return

        while not self._stop.is_set():
            try:
                self._iteration(analyzer)
            except Exception:
                # A driver or OpenCV error must not end the thread silently while the tray
                # still says "watching": let go of the camera and try again in a moment.
                log.exception("camera loop error")
                self._drop_camera()
                analyzer.reset()
                self._emit_status(Status.NO_CAMERA, "error")
                self._wait(CAMERA_RETRY_S)
        self._drop_camera()

    def _drop_camera(self) -> None:
        if self._camera is not None:
            self._camera.release()
            self._camera = None

    def _iteration(self, analyzer: Analyzer) -> None:
        """One turn of the camera loop."""
        if self._paused:
            if self._camera is not None:
                self._drop_camera()
                analyzer.reset()
            self._emit_status(Status.PAUSED)
            self._wait(0.5)
            return

        source = (
            self._source_override
            if self._source_override is not None
            else self._settings.camera_index
        )
        api = self._settings.camera_api
        camera = self._camera
        if camera is None or camera.source != source or camera.api != api:
            self._drop_camera()
            camera = self._camera_factory(source, api)
            if not camera.open():
                camera.release()
                self._emit_status(Status.NO_CAMERA, str(source))
                self._wait(CAMERA_RETRY_S)
                return
            self._camera = camera
            analyzer.reset()
            self._next_at = 0.0
            self._failures = 0
        self._emit_status(Status.RUNNING)

        if not camera.grab():
            self._failures += 1
            if self._failures >= MAX_GRAB_FAILURES:
                self._drop_camera()
                self._emit_status(Status.NO_CAMERA, str(source))
                self._wait(CAMERA_RETRY_S)
            else:
                self._wait(0.05)
            return
        self._failures = 0

        now = self._clock()
        if now < self._next_at:
            return  # this picture is dropped; a later one will be analysed
        frame = camera.retrieve()
        if frame is None:
            return
        started = time.perf_counter()
        try:
            step = analyzer.step(frame, now, self._settings.cadence(), keep_frame=self._preview)
        except Exception:
            log.exception("analysis failed on one picture")
            self._next_at = now + 1.0
            return
        self.analysis_s += time.perf_counter() - started
        self._next_at = now + step.interval
        if step.observation is None:
            self.skipped += 1
            return
        self.analyses += 1
        self._on_observation(step.observation)
