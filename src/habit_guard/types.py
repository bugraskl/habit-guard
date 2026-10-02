"""Plain data types shared by the vision, engine and UI layers.

Nothing here imports Qt or OpenCV, so the decision logic that consumes these
types can be tested with hand-made numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np


class Habit(StrEnum):
    """The behaviours Habit Guard can watch for. The value is the settings key."""

    NAIL_BITING = "nail_biting"
    MUSTACHE = "mustache"
    HAIR_PULLING = "hair_pulling"
    FACE_TOUCH = "face_touch"


#: MediaPipe hand landmark indices.
WRIST = 0
THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP = 4, 8, 12, 16, 20
FINGERTIPS: tuple[int, ...] = (THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP)
#: Wrist plus the four finger bases: their mean is the middle of the palm.
PALM_BASE: tuple[int, ...] = (0, 5, 9, 13, 17)
HAND_LANDMARKS = 21


@dataclass(frozen=True, slots=True)
class FaceInfo:
    """A detected face, in frame pixels.

    ``landmarks`` are YuNet's five points: the two eyes, the nose tip and the
    two mouth corners. The eyes and the mouth corners are stored left-to-right
    as they appear in the image, whichever side of the face they belong to.
    """

    box: tuple[float, float, float, float]  # x, y, width, height
    left_eye: tuple[float, float]
    right_eye: tuple[float, float]
    nose: tuple[float, float]
    mouth_left: tuple[float, float]
    mouth_right: tuple[float, float]
    score: float = 1.0

    @property
    def center(self) -> tuple[float, float]:
        x, y, w, h = self.box
        return (x + w / 2.0, y + h / 2.0)


@dataclass(frozen=True, slots=True)
class HandInfo:
    """A tracked hand: 21 landmarks in frame pixels, and the model's confidence."""

    landmarks: np.ndarray  # shape (21, 2)
    score: float = 1.0

    def fingertips(self) -> np.ndarray:
        return self.landmarks[list(FINGERTIPS)]

    def palm_center(self) -> np.ndarray:
        return self.landmarks[list(PALM_BASE)].mean(axis=0)


@dataclass(frozen=True, slots=True)
class Observation:
    """What the camera pipeline saw at one moment.

    ``frame`` is only attached while the preview window is open; the analysis
    itself never keeps a picture.
    """

    ts: float
    face: FaceInfo | None
    hands: tuple[HandInfo, ...] = ()
    #: The face was not found in this frame and the last known one is reused.
    face_held: bool = False
    #: Any hand is close enough to the face to need fast analysis.
    hand_near: bool = False
    #: Camera frame size, for drawing overlays.
    frame_size: tuple[int, int] = (0, 0)
    frame: np.ndarray | None = None
