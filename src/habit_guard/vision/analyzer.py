"""One analysis step: from a camera picture to an :class:`Observation`.

The step also decides how soon the next picture is needed, which is where the
low CPU use comes from. There are three speeds:

* nobody in view: a slow look for a face;
* a face in view and the hands away: a picture every half second or so, and
  only analysed when something near the face moved (or every couple of seconds
  anyway), because a hand cannot reach the face without moving;
* a hand near the face: fast analysis, so the alarm is on time.

Everything the step needs from the outside is passed in, which keeps it
testable with fake detectors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from ..config import Cadence
from ..types import FaceInfo, HandInfo, Observation
from ..zones import hand_is_near_face
from .face import FaceMemory
from .motion import MotionGate, thumbnail

#: Fast analysis goes on this long after the hand was last near the face.
ACTIVE_HOLD_S = 1.5
#: Where hands are looked for: the face box widened by this many box sizes on each side.
SEARCH_MARGIN = 1.2


class FaceFinder(Protocol):
    def detect(self, image: np.ndarray) -> FaceInfo | None: ...


class HandFollower(Protocol):
    def update(
        self, image: np.ndarray, now: float, search: tuple[int, int, int, int] | None = None
    ) -> list[HandInfo]: ...

    def reset(self) -> None: ...


@dataclass(frozen=True, slots=True)
class Step:
    #: ``None`` when the motion gate skipped the analysis.
    observation: Observation | None
    #: Seconds until the next picture is wanted.
    interval: float


def expand_box(
    box: tuple[float, float, float, float], margin: float, size: tuple[int, int]
) -> tuple[int, int, int, int]:
    """``box`` widened by ``margin`` box sizes on every side, clipped to a ``(w, h)`` picture."""
    x, y, w, h = box
    x0, y0 = int(x - margin * w), int(y - margin * h)
    x1, y1 = int(x + (1 + margin) * w), int(y + (1 + margin) * h)
    return (max(0, x0), max(0, y0), min(size[0], x1), min(size[1], y1))


class Analyzer:
    def __init__(
        self,
        faces: FaceFinder,
        hands: HandFollower,
        *,
        memory: FaceMemory | None = None,
        gate: MotionGate | None = None,
    ):
        self._faces = faces
        self._hands = hands
        self._memory = memory or FaceMemory()
        self._gate = gate or MotionGate()
        self._active_until = float("-inf")
        self._last_full = float("-inf")

    def reset(self) -> None:
        """Forget everything (tracking resumed, camera changed)."""
        self._memory.reset()
        self._gate.reset()
        self._hands.reset()
        self._active_until = float("-inf")
        self._last_full = float("-inf")

    def step(
        self, frame: np.ndarray, now: float, cadence: Cadence, *, keep_frame: bool = False
    ) -> Step:
        h, w = frame.shape[:2]
        known = self._memory.last
        window = expand_box(known.box, 1.0, (w, h)) if known is not None else None
        thumb = thumbnail(frame, window)

        active = now < self._active_until
        due = now - self._last_full >= cadence.forced_s
        # A preview wants every picture; otherwise a still scene needs no analysis.
        if known is not None and not (active or due or keep_frame) and not self._gate.moved(thumb):
            return Step(None, cadence.idle_s)

        detected = self._faces.detect(frame)
        search_face = detected or known
        hands: list[HandInfo] = []
        if search_face is not None:
            hands = self._hands.update(
                frame, now, expand_box(search_face.box, SEARCH_MARGIN, (w, h))
            )
        else:
            self._hands.reset()
        face, held = self._memory.update(now, detected, bool(hands))

        near = face is not None and hand_is_near_face(face, hands)
        if near:
            self._active_until = now + ACTIVE_HOLD_S
        self._gate.accept(thumb)
        self._last_full = now

        if face is None:
            interval = cadence.no_face_s
        elif near or now < self._active_until:
            interval = cadence.active_s
        else:
            interval = cadence.idle_s
        if keep_frame:
            interval = min(interval, cadence.active_s)
        observation = Observation(
            ts=now,
            face=face,
            hands=tuple(hands),
            face_held=held,
            hand_near=near,
            frame_size=(w, h),
            frame=frame if keep_frame else None,
        )
        return Step(observation, interval)
