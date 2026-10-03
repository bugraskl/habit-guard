"""A hand lying on the mouth with its fingertips hidden (a finger in the mouth) still counts.

The first test is built from a real preview picture a user sent: a fist under the mouth, a finger
in the mouth, and the hand model putting the fingertips on the palm, below the chin, where no zone
is. Its numbers are the face's and the hand's points read off that picture, in pixels.
"""

from __future__ import annotations

import numpy as np
import pytest

from habit_guard.types import FINGERTIPS, FaceInfo, Habit, HandInfo
from habit_guard.zones import (
    COVER_MIN_POINTS,
    Ellipse,
    FaceFrame,
    ZoneSpec,
    build_zones,
    evaluate,
)

# The face of the picture: eyes 100 px apart, the mouth a little higher than in an average face.
FACE = FaceInfo(
    box=(65.0, 75.0, 225.0, 320.0),
    left_eye=(140.0, 206.0),
    right_eye=(240.0, 206.0),
    nose=(192.0, 268.0),
    mouth_left=(152.0, 315.0),
    mouth_right=(235.0, 316.0),
    score=0.95,
)
FRAME = FaceFrame.from_face(FACE)

# The hand of the picture, point by point (wrist, then thumb, index, middle, ring, pinky).
FIST = np.array(
    [
        (313, 490),
        (350, 462), (368, 425), (381, 392), (388, 366),  # thumb
        (313, 322), (303, 345), (298, 367), (296, 385),  # index: knuckle, joints, tip
        (290, 322), (277, 342), (268, 364), (265, 388),  # middle
        (268, 322), (255, 340), (247, 362), (241, 386),  # ring
        (248, 325), (232, 346), (220, 372), (213, 396),  # pinky
    ],
    dtype=np.float64,
)  # fmt: skip

NAIL = {Habit.NAIL_BITING: ZoneSpec()}
EVERYTHING = {h: ZoneSpec() for h in (Habit.NAIL_BITING, Habit.MUSTACHE, Habit.HAIR_PULLING)}


def hand(shift: tuple[float, float] = (0.0, 0.0), points: np.ndarray = FIST) -> HandInfo:
    return HandInfo(landmarks=points + np.array(shift), score=0.9)


def counts(specs: dict[Habit, ZoneSpec], h: HandInfo) -> dict[Habit, int]:
    assert FRAME is not None
    zones = build_zones(FRAME, specs)
    return {habit: n for habit, n in evaluate(FRAME, zones, [h]).items() if n}


def test_the_fingertips_of_the_picture_are_in_no_zone() -> None:
    """The reason nothing was detected: every tip is below the mouth zone."""
    assert FRAME is not None
    zones = build_zones(FRAME, EVERYTHING)
    tips = FRAME.to_uv(hand().landmarks[list(FINGERTIPS)])
    for zone in zones:
        assert not any(zone.contains(float(u), float(v)) for u, v in tips)


def test_a_fist_on_the_mouth_with_hidden_fingertips_counts_as_nail_biting() -> None:
    result = counts(NAIL, hand())
    assert set(result) == {Habit.NAIL_BITING}
    assert result[Habit.NAIL_BITING] >= COVER_MIN_POINTS


def test_it_also_counts_with_the_other_habits_switched_on() -> None:
    assert set(counts(EVERYTHING, hand())) == {Habit.NAIL_BITING}


@pytest.mark.parametrize(
    "shift", [(0.0, 110.0), (0.0, 180.0), (200.0, 0.0), (-260.0, 0.0), (0.0, -150.0)]
)
def test_the_same_hand_resting_elsewhere_does_not_count(shift: tuple[float, float]) -> None:
    # Under the chin, beside the face, over the eyes: not at the mouth.
    assert counts(NAIL, hand(shift)) == {}


def test_the_zone_is_left_gradually_not_in_a_jump_at_the_first_pixel() -> None:
    hits = [bool(counts(NAIL, hand((0.0, dy)))) for dy in range(-40, 141, 20)]
    first_miss = hits.index(False)
    assert all(hits[:first_miss])
    assert not any(hits[first_miss:])  # once it is out, it stays out
    assert 1 < first_miss < len(hits) - 1


def test_a_fingertip_in_a_zone_decides_and_the_fallback_stays_out_of_it() -> None:
    assert FRAME is not None
    tip_in_the_moustache = hand().landmarks.copy()
    u, v = 0.0, 0.72  # just under the nose, above the lips
    tip_in_the_moustache[8] = FRAME.to_image(u, v)
    result = counts(EVERYTHING, HandInfo(landmarks=tip_in_the_moustache, score=0.9))
    assert set(result) == {Habit.MUSTACHE}  # one movement, one habit


def test_nail_biting_switched_off_means_no_fallback() -> None:
    assert counts({Habit.NAIL_BITING: ZoneSpec(enabled=False)}, hand()) == {}
    assert counts({Habit.MUSTACHE: ZoneSpec()}, hand()) == {}


def test_a_smaller_mouth_zone_narrows_the_fallback_too() -> None:
    assert counts({Habit.NAIL_BITING: ZoneSpec(scale=0.5)}, hand()) == {}
    assert counts({Habit.NAIL_BITING: ZoneSpec(scale=1.5)}, hand())


def test_a_few_stray_joints_are_not_enough() -> None:
    points = np.full((21, 2), 5000.0)
    assert FRAME is not None
    lips = FRAME.to_image(0.0, 1.16)
    for i in (6, 10):  # two joints on the lips, the rest far away
        points[i] = lips
    assert counts(NAIL, HandInfo(landmarks=points, score=0.9)) == {}
    points[14] = lips  # three
    assert Habit.NAIL_BITING in counts(NAIL, HandInfo(landmarks=points, score=0.9))


def test_fingertips_alone_never_use_the_fallback() -> None:
    """Five tips just outside the zone are visible and honest: they stay outside."""
    points = np.full((21, 2), 5000.0)
    assert FRAME is not None
    edge = FRAME.to_image(0.0, 1.70)  # just below the mouth zone
    for i in FINGERTIPS:
        points[i] = edge
    assert counts(NAIL, HandInfo(landmarks=points, score=0.9)) == {}


def test_a_zone_the_user_drew_over_the_mouth_takes_the_area_from_the_fallback() -> None:
    shape = (Ellipse(0.0, 1.15, 1.2, 0.8),)
    specs = {**NAIL, Habit.CUSTOM_1: ZoneSpec(shape=shape)}
    assert Habit.NAIL_BITING not in counts(specs, hand())


# ------------------------------------------------------------------ the limits found in review
def test_the_joints_of_two_hands_do_not_add_up_to_a_hand_on_the_mouth() -> None:
    assert FRAME is not None
    lips = FRAME.to_image(0.0, 1.16)
    one = np.full((21, 2), 5000.0)
    other = np.full((21, 2), 5000.0)
    one[6] = one[10] = lips  # two joints on the lips
    other[14] = lips  # one more, on the other hand
    zones = build_zones(FRAME, NAIL)
    assert evaluate(FRAME, zones, [HandInfo(one, 0.9), HandInfo(other, 0.9)]) == {
        Habit.NAIL_BITING: 0
    }
    one[14] = lips  # three on the same hand
    assert evaluate(FRAME, zones, [HandInfo(one, 0.9)])[Habit.NAIL_BITING] >= COVER_MIN_POINTS


def test_a_fist_on_the_mouth_is_nail_biting_and_not_also_face_touching() -> None:
    both = {Habit.NAIL_BITING: ZoneSpec(), Habit.FACE_TOUCH: ZoneSpec()}
    result = counts(both, hand())
    assert set(result) == {Habit.NAIL_BITING}  # one movement, one habit, one alarm
    assert counts({Habit.FACE_TOUCH: ZoneSpec()}, hand()) != {}  # on its own it is face touching


def test_a_visible_fingertip_in_a_zone_still_wins_over_face_touching_elsewhere() -> None:
    assert FRAME is not None
    points = np.full((21, 2), 5000.0)
    points[8] = FRAME.to_image(0.0, 1.16)  # the index tip on the lips
    result = counts(
        {Habit.NAIL_BITING: ZoneSpec(), Habit.FACE_TOUCH: ZoneSpec()}, HandInfo(points, 0.9)
    )
    assert result == {Habit.NAIL_BITING: 1}


def test_switching_the_fallback_off_leaves_only_the_fingertips() -> None:
    off = {Habit.NAIL_BITING: ZoneSpec(hidden_tips=False)}
    assert counts(off, hand()) == {}
    assert Habit.NAIL_BITING in counts({Habit.NAIL_BITING: ZoneSpec(hidden_tips=True)}, hand())
    visible_tip = np.full((21, 2), 5000.0)
    assert FRAME is not None
    visible_tip[8] = FRAME.to_image(0.0, 1.16)
    assert Habit.NAIL_BITING in counts(off, HandInfo(visible_tip, 0.9))  # tips never need it


def test_a_larger_mouth_zone_does_not_widen_the_fallback_with_it() -> None:
    assert FRAME is not None
    far = np.full((21, 2), 5000.0)
    # Three joints 0.7 eye distances below the mouth zone's centre: inside 1.5 x (1.0 x), but
    # outside 1.5 x 2.0 would have been, had the scale been multiplied in.
    spot = FRAME.to_image(0.0, 1.16 + 0.62)
    for i in (6, 10, 14):
        far[i] = spot
    zones = build_zones(FRAME, {Habit.NAIL_BITING: ZoneSpec(scale=2.0)})
    below = zones[0].cover[0]
    assert below.ry == pytest.approx(0.3 * 1.0 * 1.5)  # the cap: scale 2.0 counts as 1.0 here
    result = evaluate(FRAME, zones, [HandInfo(far, 0.9)])
    assert result == {Habit.NAIL_BITING: 0}
