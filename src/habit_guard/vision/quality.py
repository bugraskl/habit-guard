"""Is the camera set up well? Judges one observation and says what to fix.

Habit Guard needs the face to be lit, big enough and with room around it for the hands. The setup
wizard and the camera preview use this module to tell the user *what* is wrong ("too dark", "too
close") instead of leaving them to wonder why nothing is detected.

It is cheap on purpose (a small greyscale copy of the face area and of the whole picture) and only
runs while one of those windows is open, since only then a picture is kept. A picture is
looked at, never stored.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum

import cv2
import numpy as np

from ..types import Observation

#: Mean grey level (0-255) of the face below which the picture is too dark ...
DARK_BELOW = 55.0
#: ... and above which it is too bright; or when this share of its pixels is blown out.
BRIGHT_ABOVE = 215.0
BLOWN_OUT_SHARE = 0.18
#: The face is "in the shadow" when it is this much darker than the rest of a bright picture.
BACKLIT_RATIO = 0.6
BACKLIT_MIN_BACKGROUND = 110.0
#: The face box's width as a share of the picture's width: too small to read, too big for hands.
FACE_SMALL_BELOW = 0.14
FACE_LARGE_ABOVE = 0.50
#: How much of the face box may lie outside the picture before it counts as cut off.
CUT_OFF_SHARE = 0.08
#: Free space wanted beside and above the face, in face-box widths and heights, so that hands
#: raised to the face stay in the picture.
ROOM_SIDES = 0.30
ROOM_TOP = 0.12


class Issue(StrEnum):
    """What can be wrong. The value is the end of the translation key (``quality.<value>``)."""

    NO_FACE = "no_face"
    TOO_DARK = "too_dark"
    TOO_BRIGHT = "too_bright"
    BACKLIT = "backlit"
    FACE_SMALL = "face_small"
    FACE_LARGE = "face_large"
    FACE_CUT = "face_cut"
    NO_ROOM = "no_room"


#: The order in which advice is given: the most basic problem first.
PRIORITY = tuple(Issue)

#: Which checks the wizard shows, and which issues each one covers.
LIGHT_ISSUES = frozenset({Issue.TOO_DARK, Issue.TOO_BRIGHT, Issue.BACKLIT})
DISTANCE_ISSUES = frozenset({Issue.FACE_SMALL, Issue.FACE_LARGE})
ROOM_ISSUES = frozenset({Issue.FACE_CUT, Issue.NO_ROOM})


@dataclass(frozen=True, slots=True)
class Report:
    """The verdict on one observation."""

    face_found: bool
    issues: frozenset[Issue] = frozenset()
    hands: int = 0
    #: Mean grey level of the face, when a picture was available to measure it.
    brightness: float | None = None

    def first_issue(self) -> Issue | None:
        """The issue to talk about first, or ``None`` when all is well."""
        for issue in PRIORITY:
            if issue in self.issues:
                return issue
        return None


def assess(obs: Observation) -> Report:
    """Judge ``obs``: geometry always, light only when it carries a picture."""
    if obs.face is None:
        return Report(face_found=False, issues=frozenset({Issue.NO_FACE}), hands=len(obs.hands))
    issues: set[Issue] = set()
    width, height = obs.frame_size
    x, y, w, h = obs.face.box
    brightness: float | None = None
    if width > 0 and height > 0 and w > 0 and h > 0:
        issues |= _geometry(x, y, w, h, width, height)
        if obs.frame is not None and not obs.face_held:
            brightness, light = _light(obs.frame, (x, y, w, h))
            issues |= light
    return Report(True, frozenset(issues), len(obs.hands), brightness)


def _geometry(x: float, y: float, w: float, h: float, width: int, height: int) -> set[Issue]:
    issues: set[Issue] = set()
    share = w / width
    if share < FACE_SMALL_BELOW:
        issues.add(Issue.FACE_SMALL)
    if share > FACE_LARGE_ABOVE:
        issues.add(Issue.FACE_LARGE)
    outside_x = max(0.0, -x) + max(0.0, x + w - width)
    outside_y = max(0.0, -y) + max(0.0, y + h - height)
    if outside_x / w > CUT_OFF_SHARE or outside_y / h > CUT_OFF_SHARE:
        issues.add(Issue.FACE_CUT)
    elif x < ROOM_SIDES * w or width - (x + w) < ROOM_SIDES * w or y < ROOM_TOP * h:
        issues.add(Issue.NO_ROOM)
    return issues


def _light(frame: np.ndarray, box: tuple[float, float, float, float]) -> tuple[float, set[Issue]]:
    """Mean grey level of the face and what it says about the light."""
    gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    full_h, full_w = gray.shape[:2]
    x, y, w, h = box
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(full_w, int(x + w)), min(full_h, int(y + h))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return 0.0, set()
    face = cv2.resize(gray[y0:y1, x0:x1], (24, 24), interpolation=cv2.INTER_AREA)
    mean = float(face.mean())
    issues: set[Issue] = set()
    if mean < DARK_BELOW:
        issues.add(Issue.TOO_DARK)
    if mean > BRIGHT_ABOVE or float((face >= 250).mean()) > BLOWN_OUT_SHARE:
        issues.add(Issue.TOO_BRIGHT)
    face_area = (x1 - x0) * (y1 - y0)
    rest_area = full_w * full_h - face_area
    if rest_area > 0 and Issue.TOO_DARK not in issues:
        whole = float(cv2.resize(gray, (32, 24), interpolation=cv2.INTER_AREA).mean())
        background = (whole * full_w * full_h - mean * face_area) / rest_area
        if background >= BACKLIT_MIN_BACKGROUND and mean < BACKLIT_RATIO * background:
            issues.add(Issue.BACKLIT)
    return mean, issues


@dataclass
class QualityTracker:
    """Smooths the verdict over the last few observations, so advice does not flicker.

    An issue is reported once it showed in more than half of the last ``window`` observations
    that had a face; "no face" only when most of them had none. Hands are "in view" when any
    recent observation had one.
    """

    window: int = 8
    _recent: deque[Report] = field(default_factory=deque, init=False, repr=False)

    def reset(self) -> None:
        self._recent.clear()

    def update(self, obs: Observation) -> Report:
        """Add ``obs`` and return the smoothed verdict."""
        self._recent.append(assess(obs))
        while len(self._recent) > self.window:
            self._recent.popleft()
        return self.current()

    def current(self) -> Report:
        recent = list(self._recent)
        if not recent:
            return Report(face_found=False, issues=frozenset({Issue.NO_FACE}))
        with_face = [r for r in recent if r.face_found]
        hands = max((r.hands for r in recent), default=0)
        if len(with_face) * 2 <= len(recent):
            return Report(face_found=False, issues=frozenset({Issue.NO_FACE}), hands=hands)
        counts: dict[Issue, int] = {}
        for report in with_face:
            for issue in report.issues:
                counts[issue] = counts.get(issue, 0) + 1
        issues = frozenset(i for i, n in counts.items() if n * 2 > len(with_face))
        brightness = [r.brightness for r in with_face if r.brightness is not None]
        mean = sum(brightness) / len(brightness) if brightness else None
        return Report(True, issues, hands, mean)
