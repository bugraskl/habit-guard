"""Motion gate: skip the analysis while the picture around the face has not changed.

Someone typing or reading sits almost still for long stretches, and a hand
cannot arrive at the face without moving. The gate compares a tiny greyscale
thumbnail of the area around the face with the one from the last *analysed*
frame, which costs a fraction of a millisecond and removes most of the
inference work.

It also tells whether a frame is *blind* (lens covered, shutter closed, dark
room): then "no face" means "cannot tell", not "nobody there".
"""

from __future__ import annotations

import cv2
import numpy as np

THUMB_SIZE = (32, 24)
#: Mean absolute grey-level change (0-255) that counts as movement. Camera noise is ~1.
DEFAULT_THRESHOLD = 3.0
#: A thumbnail darker than this mean grey level ...
BLIND_MAX_MEAN = 24.0
#: ... and flatter than this standard deviation shows nothing recognisable.
BLIND_MAX_STD = 5.0


def thumbnail(frame: np.ndarray, window: tuple[int, int, int, int] | None = None) -> np.ndarray:
    """A small greyscale ``float32`` copy of ``frame`` (or of the ``x0, y0, x1, y1`` window)."""
    if window is not None:
        h, w = frame.shape[:2]
        x0, y0 = max(0, window[0]), max(0, window[1])
        x1, y1 = min(w, window[2]), min(h, window[3])
        if x1 - x0 >= 8 and y1 - y0 >= 8:
            frame = frame[y0:y1, x0:x1]
    gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, THUMB_SIZE, interpolation=cv2.INTER_AREA).astype(np.float32)


def is_blind(thumb: np.ndarray) -> bool:
    """True when the thumbnail is too dark and uniform to show anyone."""
    mean, std = cv2.meanStdDev(thumb)
    return float(mean[0, 0]) < BLIND_MAX_MEAN and float(std[0, 0]) < BLIND_MAX_STD


class MotionGate:
    """Says whether a frame differs enough from the last analysed one."""

    def __init__(self, threshold: float = DEFAULT_THRESHOLD):
        self.threshold = threshold
        self._last: np.ndarray | None = None

    def reset(self) -> None:
        self._last = None

    def moved(self, thumb: np.ndarray) -> bool:
        """True for the first frame, and whenever ``thumb`` differs from the reference."""
        if self._last is None or self._last.shape != thumb.shape:
            return True
        return float(cv2.norm(thumb, self._last, cv2.NORM_L1)) / thumb.size > self.threshold

    def accept(self, thumb: np.ndarray) -> None:
        """Make ``thumb`` the reference: call it when the frame was actually analysed."""
        self._last = thumb
