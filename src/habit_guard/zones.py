"""Where on the face each habit happens, and whether a hand is there.

Every zone is a handful of ellipses in *face coordinates*: the origin is the
midpoint between the eyes, one unit is the distance between the eyes, ``u``
runs along the eye line and ``v`` points toward the chin. Measuring in that
frame makes the zones follow the head's distance from the camera and its tilt
(roll) for free, and the mouth and nose landmarks keep them on the right spot
when the head turns or nods.

A hand "is in" a zone when one of its tracked points (the fingertips, plus the
middle of the palm for plain face touching) falls inside one of the zone's
ellipses and outside every excluded one. Zones of different habits are kept
from overlapping, so one movement raises one habit's alarm, not two. Where the user has drawn a
custom zone it wins over the built-in ones, and an earlier custom zone wins over a later one.

This module is pure geometry on numbers; it imports neither Qt nor OpenCV.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from .types import CUSTOM_HABITS, FaceInfo, Habit, HandInfo

#: Faces whose eyes are closer than this (in frame pixels) are too small to trust.
MIN_EYE_DISTANCE_PX = 6.0


@dataclass(frozen=True, slots=True)
class Ellipse:
    """An axis-aligned ellipse in face coordinates."""

    cu: float
    cv: float
    rx: float
    ry: float

    def contains(self, u: float, v: float) -> bool:
        return ((u - self.cu) / self.rx) ** 2 + ((v - self.cv) / self.ry) ** 2 <= 1.0

    def scaled(self, factor: float) -> Ellipse:
        return Ellipse(self.cu, self.cv, self.rx * factor, self.ry * factor)


@dataclass(frozen=True, slots=True)
class Zone:
    """The area of one habit: inside any ``include`` ellipse, outside every ``exclude`` one."""

    habit: Habit
    include: tuple[Ellipse, ...]
    exclude: tuple[Ellipse, ...] = ()

    def contains(self, u: float, v: float) -> bool:
        if any(e.contains(u, v) for e in self.exclude):
            return False
        return any(e.contains(u, v) for e in self.include)


@dataclass(frozen=True, slots=True)
class ZoneSpec:
    """What the user chose for one habit."""

    enabled: bool = True
    #: Multiplies the zone's size; below 1 is stricter, above 1 more generous.
    scale: float = 1.0
    #: Also cover the wider area: the chin and beard line, or the scalp.
    wide: bool = False
    #: The shape of a custom zone, in face coordinates (empty for the built-in habits).
    shape: tuple[Ellipse, ...] = ()


@dataclass(frozen=True, slots=True)
class FaceFrame:
    """The face coordinate system of one detected face."""

    origin: tuple[float, float]
    axis: tuple[float, float]  # unit vector along the eye line
    down: tuple[float, float]  # unit vector toward the chin
    unit: float  # pixels per face unit (the eye distance)
    nose: tuple[float, float]  # nose tip, in face coordinates
    mouth: tuple[float, float]  # mouth centre, in face coordinates
    mouth_width: float  # in face units

    @classmethod
    def from_face(cls, face: FaceInfo) -> FaceFrame | None:
        """The coordinate system of ``face``, or ``None`` for a degenerate detection."""
        lx, ly = face.left_eye
        rx, ry = face.right_eye
        dx, dy = rx - lx, ry - ly
        unit = math.hypot(dx, dy)
        if unit < MIN_EYE_DISTANCE_PX:
            return None
        axis = (dx / unit, dy / unit)
        down = (-axis[1], axis[0])
        origin = ((lx + rx) / 2.0, (ly + ry) / 2.0)
        frame = cls(origin, axis, down, unit, (0.0, 0.0), (0.0, 0.0), 0.0)
        nose = frame.to_uv(np.array([face.nose], dtype=np.float64))[0]
        corners = frame.to_uv(np.array([face.mouth_left, face.mouth_right], dtype=np.float64))
        mouth = corners.mean(axis=0)
        mouth_width = float(np.hypot(*(corners[1] - corners[0])))
        return cls(
            origin,
            axis,
            down,
            unit,
            (float(nose[0]), float(nose[1])),
            (float(mouth[0]), float(mouth[1])),
            mouth_width,
        )

    def to_uv(self, points: np.ndarray) -> np.ndarray:
        """Frame pixels, shape (n, 2), to face coordinates."""
        rel = np.asarray(points, dtype=np.float64) - np.array(self.origin)
        u = rel @ np.array(self.axis)
        v = rel @ np.array(self.down)
        return np.stack([u, v], axis=1) / self.unit

    def to_image(self, u: float, v: float) -> tuple[float, float]:
        """A face coordinate back to frame pixels."""
        x = self.origin[0] + (u * self.axis[0] + v * self.down[0]) * self.unit
        y = self.origin[1] + (u * self.axis[1] + v * self.down[1]) * self.unit
        return (x, y)

    def ellipse_polygon(self, ellipse: Ellipse, points: int = 36) -> np.ndarray:
        """The ellipse's outline in frame pixels, shape (points, 2), for drawing."""
        out = np.empty((points, 2), dtype=np.float64)
        for i in range(points):
            t = 2.0 * math.pi * i / points
            out[i] = self.to_image(
                ellipse.cu + ellipse.rx * math.cos(t), ellipse.cv + ellipse.ry * math.sin(t)
            )
        return out


# ------------------------------------------------------------------------------ zone shapes
def _mouth(frame: FaceFrame) -> Ellipse:
    """The lips and a little around them: where fingers go when nails are bitten."""
    mu, mv = frame.mouth
    return Ellipse(mu, mv + 0.06, max(frame.mouth_width, 0.5) / 2.0 + 0.2, 0.30)


def _upper_lip(frame: FaceFrame) -> Ellipse:
    """Between the nose and the mouth: the moustache."""
    nu, nv = frame.nose
    mu, mv = frame.mouth
    half = max((mv - nv) / 2.0, 0.22)
    return Ellipse((nu + mu) / 2.0, (nv + mv) / 2.0 + 0.02, 0.62, half)


def _chin_and_beard(frame: FaceFrame) -> tuple[Ellipse, ...]:
    mu, mv = frame.mouth
    return (
        Ellipse(mu, mv + 0.78, 0.8, 0.42),  # chin
        Ellipse(mu - 1.0, mv - 0.05, 0.42, 0.62),  # cheek and jaw, image left
        Ellipse(mu + 1.0, mv - 0.05, 0.42, 0.62),  # cheek and jaw, image right
    )


def _eyes_and_brows(frame: FaceFrame) -> tuple[Ellipse, ...]:
    # Both eyes sit on the v = 0 line, half an eye distance either side of u = 0.
    return (
        Ellipse(-0.5, -0.3, 0.5, 0.2),  # brow, image left
        Ellipse(0.5, -0.3, 0.5, 0.2),  # brow, image right
        Ellipse(-0.5, 0.0, 0.4, 0.22),  # lashes, image left
        Ellipse(0.5, 0.0, 0.4, 0.22),  # lashes, image right
        Ellipse(0.0, -1.0, 1.1, 0.55),  # forehead and hairline
    )


def _scalp() -> Ellipse:
    return Ellipse(0.0, -1.9, 1.4, 0.7)


def _whole_face() -> Ellipse:
    return Ellipse(0.0, 0.5, 1.4, 1.6)


def build_zones(frame: FaceFrame, specs: Mapping[Habit, ZoneSpec]) -> list[Zone]:
    """The zones of every enabled habit for one face, in face coordinates."""

    def spec(habit: Habit) -> ZoneSpec:
        return specs.get(habit, ZoneSpec(enabled=False))

    zones: list[Zone] = []
    mouth_zone: Zone | None = None

    # Zones the user drew come first: they own their area, and every other zone steps around it.
    drawn: list[Ellipse] = []
    for habit in CUSTOM_HABITS:
        custom = spec(habit)
        if custom.enabled and custom.shape:
            shape = tuple(e.scaled(custom.scale) for e in custom.shape)
            zones.append(Zone(habit, shape, tuple(drawn)))
            drawn.extend(shape)
    owned_by_user = tuple(drawn)

    nail = spec(Habit.NAIL_BITING)
    if nail.enabled:
        mouth_zone = Zone(Habit.NAIL_BITING, (_mouth(frame).scaled(nail.scale),), owned_by_user)
        zones.append(mouth_zone)

    mustache = spec(Habit.MUSTACHE)
    if mustache.enabled:
        include = [_upper_lip(frame)]
        exclude: tuple[Ellipse, ...] = owned_by_user
        if mouth_zone is not None:
            exclude += mouth_zone.include  # a fingertip at the lips is nail biting's
        else:
            include.append(_mouth(frame))  # lip picking belongs here when nothing else owns it
        if mustache.wide:
            include.extend(_chin_and_beard(frame))
        zones.append(
            Zone(Habit.MUSTACHE, tuple(e.scaled(mustache.scale) for e in include), exclude)
        )

    hair = spec(Habit.HAIR_PULLING)
    if hair.enabled:
        include = list(_eyes_and_brows(frame))
        if hair.wide:
            include.append(_scalp())
        zones.append(
            Zone(Habit.HAIR_PULLING, tuple(e.scaled(hair.scale) for e in include), owned_by_user)
        )

    touch = spec(Habit.FACE_TOUCH)
    if touch.enabled:
        # Whatever the other habits already own is not "just touching the face".
        owned = tuple(e for z in zones for e in z.include)
        zones.append(Zone(Habit.FACE_TOUCH, (_whole_face().scaled(touch.scale),), owned))
    return zones


# ------------------------------------------------------------------------------ evaluation
def tracked_points(habit: Habit, hand: HandInfo) -> np.ndarray:
    """The hand points that count for ``habit``, shape (n, 2), in frame pixels."""
    tips = hand.fingertips()
    if habit is Habit.FACE_TOUCH:
        return np.vstack([tips, hand.palm_center()[None, :]])
    return tips


def evaluate(
    frame: FaceFrame, zones: Sequence[Zone], hands: Iterable[HandInfo]
) -> dict[Habit, int]:
    """How many tracked hand points are inside each zone, summed over all hands."""
    counts: dict[Habit, int] = {z.habit: 0 for z in zones}
    for hand in hands:
        for zone in zones:
            uv = frame.to_uv(tracked_points(zone.habit, hand))
            counts[zone.habit] += sum(1 for u, v in uv if zone.contains(float(u), float(v)))
    return counts


def hand_is_near_face(face: FaceInfo, hands: Iterable[HandInfo], margin: float = 0.9) -> bool:
    """True when any hand landmark is within ``margin`` face sizes of the face box.

    This is only the wake-up call for fast analysis: it is deliberately much
    wider than any zone, and does not need the face coordinate system.
    """
    x, y, w, h = face.box
    x0, y0, x1, y1 = x - margin * w, y - margin * h, x + (1 + margin) * w, y + (1 + margin) * h
    for hand in hands:
        pts = hand.landmarks
        inside = (pts[:, 0] >= x0) & (pts[:, 0] <= x1) & (pts[:, 1] >= y0) & (pts[:, 1] <= y1)
        if bool(inside.any()):
            return True
    return False
