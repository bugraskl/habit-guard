"""The camera, opened with the right backend for each operating system.

A frame is *grabbed* (cheap: the camera's next picture is taken off the driver)
far more often than it is *retrieved* (decoded to an array). The analysis asks
for a picture a few times a second, and every other grabbed frame is simply
dropped, so the CPU hardly notices the camera's 30 frames per second.
"""

from __future__ import annotations

import sys
import time

import cv2
import numpy as np

#: Asked of the camera: analysis does not need more, and a small picture is cheaper to move.
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FRAME_RATE = 15


def backends(api: str = "auto") -> list[int]:
    """The OpenCV capture backends to try, in order, for the ``camera_api`` setting."""
    if api == "dshow" and sys.platform == "win32":
        return [cv2.CAP_DSHOW]
    if api == "msmf" and sys.platform == "win32":
        return [cv2.CAP_MSMF]
    if api == "any":
        return [cv2.CAP_ANY]
    if sys.platform == "win32":
        return [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
    if sys.platform == "darwin":
        return [cv2.CAP_AVFOUNDATION, cv2.CAP_ANY]
    return [cv2.CAP_V4L2, cv2.CAP_ANY]


class Camera:
    """A webcam (an index) or, for development, a video file (a path) played in real time."""

    def __init__(self, source: int | str, api: str = "auto"):
        self.source = source
        self.api = api
        self._cap: cv2.VideoCapture | None = None
        self._file_period = 0.0
        self._file_next = 0.0

    @property
    def is_file(self) -> bool:
        return isinstance(self.source, str)

    @property
    def opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def open(self) -> bool:
        """Open the source; ``False`` if nothing delivers a picture (missing or busy camera)."""
        self.release()
        candidates = [cv2.CAP_ANY] if self.is_file else backends(self.api)
        for backend in candidates:
            cap = cv2.VideoCapture(self.source, backend)
            if not cap.isOpened():
                cap.release()
                continue
            if not self.is_file:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
                cap.set(cv2.CAP_PROP_FPS, FRAME_RATE)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if not cap.grab():  # a camera that opens but never delivers is as good as absent
                cap.release()
                continue
            self._cap = cap
            fps = cap.get(cv2.CAP_PROP_FPS) if self.is_file else 0.0
            self._file_period = 1.0 / fps if fps and fps > 1 else 1.0 / 30.0
            self._file_next = time.monotonic()
            return True
        return False

    def grab(self) -> bool:
        """Take the next picture off the camera. Blocks until the camera has one."""
        if self._cap is None:
            return False
        if self.is_file:
            self._pace_file()
        ok = bool(self._cap.grab())
        if not ok and self.is_file:  # loop the clip
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok = bool(self._cap.grab())
        return ok

    def retrieve(self) -> np.ndarray | None:
        """Decode the picture taken by the last :meth:`grab`."""
        if self._cap is None:
            return None
        ok, frame = self._cap.retrieve()
        return frame if ok and frame is not None else None

    def release(self) -> None:
        """Let go of the camera, which also switches its light off."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _pace_file(self) -> None:
        now = time.monotonic()
        if self._file_next > now:
            time.sleep(self._file_next - now)
        self._file_next = max(self._file_next, now) + self._file_period


def probe_cameras(limit: int = 4) -> list[tuple[int, str]]:
    """Which camera numbers open, with the picture size they deliver. Switches each camera on."""
    found: list[tuple[int, str]] = []
    for index in range(limit):
        cam = Camera(index)
        if cam.open():
            frame = cam.retrieve()
            size = f"{frame.shape[1]}x{frame.shape[0]}" if frame is not None else "unknown size"
            found.append((index, size))
        cam.release()
    return found
