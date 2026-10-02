from __future__ import annotations

import numpy as np
import pytest

from conftest import make_face, make_hand
from habit_guard.types import FaceInfo, Habit, HandInfo
from habit_guard.zones import (
    FaceFrame,
    ZoneSpec,
    build_zones,
    evaluate,
    hand_is_near_face,
)

ALL = {h: ZoneSpec() for h in Habit}
FIRST_THREE = {**{h: ZoneSpec() for h in Habit}, Habit.FACE_TOUCH: ZoneSpec(enabled=False)}


def counts_for(face: FaceInfo, hand: HandInfo, specs: dict[Habit, ZoneSpec]) -> dict[Habit, int]:
    frame = FaceFrame.from_face(face)
    assert frame is not None
    return evaluate(frame, build_zones(frame, specs), [hand])


def hit_habits(counts: dict[Habit, int]) -> set[Habit]:
    return {h for h, n in counts.items() if n > 0}


def test_face_frame_units_and_axes(face: FaceInfo) -> None:
    frame = FaceFrame.from_face(face)
    assert frame is not None
    assert frame.unit == pytest.approx(100.0)
    assert frame.axis == pytest.approx((1.0, 0.0))
    assert frame.down == pytest.approx((0.0, 1.0))
    assert frame.mouth == pytest.approx((0.0, 1.3))
    assert frame.mouth_width == pytest.approx(0.8)
    assert frame.nose == pytest.approx((0.0, 0.75))


def test_degenerate_face_is_rejected() -> None:
    tiny = make_face()
    tiny = FaceInfo(
        box=tiny.box,
        left_eye=(100.0, 100.0),
        right_eye=(102.0, 100.0),
        nose=tiny.nose,
        mouth_left=tiny.mouth_left,
        mouth_right=tiny.mouth_right,
    )
    assert FaceFrame.from_face(tiny) is None


def test_to_image_inverts_to_uv(face: FaceInfo) -> None:
    frame = FaceFrame.from_face(face)
    assert frame is not None
    x, y = frame.to_image(0.3, 1.1)
    uv = frame.to_uv(np.array([[x, y]]))[0]
    assert uv == pytest.approx((0.3, 1.1))


@pytest.mark.parametrize(
    ("spot", "expected"),
    [
        ((0.0, 1.3), Habit.NAIL_BITING),  # on the lips
        ((0.3, 1.35), Habit.NAIL_BITING),
        ((0.0, 0.9), Habit.MUSTACHE),  # between nose and mouth
        ((-0.5, -0.3), Habit.HAIR_PULLING),  # eyebrow
        ((0.0, -1.0), Habit.HAIR_PULLING),  # forehead
    ],
)
def test_each_spot_raises_exactly_one_habit(spot: tuple[float, float], expected: Habit) -> None:
    face = make_face()
    counts = counts_for(face, make_hand(face_u_v=spot), ALL)
    assert hit_habits(counts) == {expected}


def test_hand_far_from_face_hits_nothing(face: FaceInfo) -> None:
    assert hit_habits(counts_for(face, make_hand(tip_at=(600.0, 450.0)), ALL)) == set()


def test_face_touch_takes_what_the_others_do_not_own(face: FaceInfo) -> None:
    cheek = make_hand(face_u_v=(0.9, 0.6))
    assert hit_habits(counts_for(face, cheek, ALL)) == {Habit.FACE_TOUCH}
    assert hit_habits(counts_for(face, cheek, FIRST_THREE)) == set()


def test_mouth_goes_to_mustache_when_nail_biting_is_off(face: FaceInfo) -> None:
    specs = {
        **ALL,
        Habit.NAIL_BITING: ZoneSpec(enabled=False),
        Habit.FACE_TOUCH: ZoneSpec(enabled=False),
    }
    counts = counts_for(face, make_hand(face_u_v=(0.0, 1.3)), specs)
    assert hit_habits(counts) == {Habit.MUSTACHE}


def test_wide_area_adds_chin_and_scalp(face: FaceInfo) -> None:
    chin = make_hand(face_u_v=(0.0, 2.05))
    scalp = make_hand(face_u_v=(0.0, -2.0))
    narrow = {**FIRST_THREE}
    wide = {
        **FIRST_THREE,
        Habit.MUSTACHE: ZoneSpec(wide=True),
        Habit.HAIR_PULLING: ZoneSpec(wide=True),
    }
    assert hit_habits(counts_for(face, chin, narrow)) == set()
    assert hit_habits(counts_for(face, chin, wide)) == {Habit.MUSTACHE}
    assert hit_habits(counts_for(face, scalp, narrow)) == set()
    assert hit_habits(counts_for(face, scalp, wide)) == {Habit.HAIR_PULLING}


def test_zone_scale_makes_the_zone_stricter_or_more_generous(face: FaceInfo) -> None:
    edge = make_hand(face_u_v=(0.0, 1.70))  # just outside the default mouth zone
    default = {Habit.NAIL_BITING: ZoneSpec()}
    generous = {Habit.NAIL_BITING: ZoneSpec(scale=1.5)}
    strict = {Habit.NAIL_BITING: ZoneSpec(scale=0.5)}
    assert hit_habits(counts_for(face, edge, default)) == set()
    assert hit_habits(counts_for(face, edge, generous)) == {Habit.NAIL_BITING}
    on_lips = make_hand(face_u_v=(0.0, 1.55))
    assert hit_habits(counts_for(face, on_lips, default)) == {Habit.NAIL_BITING}
    assert hit_habits(counts_for(face, on_lips, strict)) == set()


@pytest.mark.parametrize("roll", [-35.0, 20.0, 90.0, 180.0])
def test_zones_follow_head_tilt_and_position(roll: float) -> None:
    centre = (250.0, 260.0)
    face = make_face(roll_deg=roll, center=centre)
    mouth = make_hand(face_u_v=(0.0, 1.3), face_center=centre, roll_deg=roll)
    brow = make_hand(face_u_v=(0.5, -0.3), face_center=centre, roll_deg=roll)
    assert hit_habits(counts_for(face, mouth, ALL)) == {Habit.NAIL_BITING}
    assert hit_habits(counts_for(face, brow, ALL)) == {Habit.HAIR_PULLING}


def test_zones_scale_with_distance_from_the_camera() -> None:
    near = make_face()
    far_lm = {
        "left_eye": (300.0, 200.0),
        "right_eye": (340.0, 200.0),
        "nose": (320.0, 230.0),
        "mouth_left": (304.0, 252.0),
        "mouth_right": (336.0, 252.0),
    }
    far = FaceInfo(box=(290.0, 175.0, 60.0, 100.0), **far_lm)
    hand_at_far_mouth = make_hand(tip_at=(320.0, 252.0))
    assert hit_habits(counts_for(far, hand_at_far_mouth, ALL)) == {Habit.NAIL_BITING}
    # The same pixel is nowhere near the mouth of the large face.
    assert Habit.NAIL_BITING not in hit_habits(counts_for(near, hand_at_far_mouth, ALL))


def test_palm_counts_for_face_touch_only() -> None:
    face = make_face()
    lm = np.full((21, 2), 5000.0)
    for i in (0, 5, 9, 13, 17):  # the palm base points
        lm[i] = (400.0, 280.0)  # u = 0.8, v = 0.8: cheek
    hand = HandInfo(landmarks=lm)
    assert hit_habits(counts_for(face, hand, ALL)) == {Habit.FACE_TOUCH}
    only_others = {**ALL, Habit.FACE_TOUCH: ZoneSpec(enabled=False)}
    assert hit_habits(counts_for(face, hand, only_others)) == set()


def test_counts_sum_over_hands_and_tips(face: FaceInfo) -> None:
    frame = FaceFrame.from_face(face)
    assert frame is not None
    zones = build_zones(frame, {Habit.NAIL_BITING: ZoneSpec()})
    one = make_hand(face_u_v=(0.0, 1.3))
    counts = evaluate(frame, zones, [one, one])
    assert counts[Habit.NAIL_BITING] == 10  # five tips on each of two hands


def test_hand_is_near_face(face: FaceInfo) -> None:
    assert hand_is_near_face(face, [make_hand(face_u_v=(0.0, 1.3))])
    assert hand_is_near_face(face, [make_hand(tip_at=(520.0, 300.0))])  # beside the face
    assert not hand_is_near_face(face, [])
    # A small, distant face: a hand resting low in the picture is not "near".
    far = FaceInfo(
        box=(300.0, 150.0, 60.0, 80.0),
        left_eye=(315.0, 175.0),
        right_eye=(345.0, 175.0),
        nose=(330.0, 195.0),
        mouth_left=(318.0, 210.0),
        mouth_right=(342.0, 210.0),
    )
    assert not hand_is_near_face(far, [make_hand(tip_at=(600.0, 470.0))])
    assert hand_is_near_face(far, [make_hand(tip_at=(330.0, 260.0))])
