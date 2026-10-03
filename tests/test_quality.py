"""The camera-setup check: what it says about light, distance and room for the hands."""

from __future__ import annotations

import numpy as np
import pytest

from conftest import make_face, make_hand
from habit_guard.types import Observation
from habit_guard.vision.quality import Issue, QualityTracker, Report, assess

SIZE = (640, 480)


def frame_of(level: int) -> np.ndarray:
    return np.full((SIZE[1], SIZE[0], 3), level, dtype=np.uint8)


def observe(
    frame: np.ndarray | None = None,
    *,
    center: tuple[float, float] = (320.0, 200.0),
    size: tuple[int, int] = SIZE,
    with_face: bool = True,
    hands: int = 0,
    held: bool = False,
) -> Observation:
    face = make_face(center=center) if with_face else None
    return Observation(
        ts=0.0,
        face=face,
        hands=tuple(make_hand(face_u_v=(0.0, 1.3)) for _ in range(hands)),
        face_held=held,
        frame_size=size,
        frame=frame,
    )


def test_a_well_lit_face_with_room_around_it_has_no_issues() -> None:
    report = assess(observe(frame_of(130)))
    assert report.face_found
    assert report.issues == frozenset()
    assert report.brightness == pytest.approx(130.0, abs=1.0)
    assert report.first_issue() is None


def test_no_face_is_the_only_thing_said() -> None:
    report = assess(observe(frame_of(130), with_face=False))
    assert not report.face_found
    assert report.issues == {Issue.NO_FACE}
    assert report.brightness is None


def test_a_dark_picture_is_too_dark() -> None:
    assert assess(observe(frame_of(20))).issues == {Issue.TOO_DARK}


def test_a_washed_out_picture_is_too_bright() -> None:
    assert Issue.TOO_BRIGHT in assess(observe(frame_of(240))).issues


def test_a_mostly_burnt_out_face_is_too_bright_even_when_its_average_is_not() -> None:
    frame = frame_of(110)
    frame[140:430, 220:320] = 255  # the left half of the face box
    report = assess(observe(frame))
    assert report.brightness is not None
    assert report.brightness < 215
    assert Issue.TOO_BRIGHT in report.issues


def test_a_face_much_darker_than_a_bright_room_is_backlit() -> None:
    frame = frame_of(205)
    frame[140:430, 220:420] = 90
    assert assess(observe(frame)).issues == {Issue.BACKLIT}


def test_a_dim_room_is_not_called_backlit() -> None:
    frame = frame_of(100)
    frame[140:430, 220:420] = 60
    assert Issue.BACKLIT not in assess(observe(frame)).issues


def test_a_face_far_from_the_camera_is_too_small() -> None:
    assert Issue.FACE_SMALL in assess(observe(frame_of(130), size=(1920, 1080))).issues


def test_a_face_close_to_the_camera_is_too_large() -> None:
    assert Issue.FACE_LARGE in assess(observe(frame_of(130), size=(340, 255))).issues


def test_a_face_at_the_edge_of_the_picture_is_cut_off() -> None:
    assert Issue.FACE_CUT in assess(observe(frame_of(130), center=(620.0, 200.0))).issues


def test_a_face_against_the_side_or_the_top_leaves_no_room_for_the_hands() -> None:
    assert assess(observe(frame_of(130), center=(110.0, 200.0))).issues == {Issue.NO_ROOM}
    assert assess(observe(frame_of(130), center=(320.0, 60.0))).issues == {Issue.NO_ROOM}


def test_room_below_the_face_is_not_needed() -> None:
    # Hands come up from the lap; a face low in the picture is fine as long as it is not cut.
    assert assess(observe(frame_of(130), center=(320.0, 260.0))).issues == frozenset()


def test_without_a_picture_only_the_geometry_is_judged() -> None:
    report = assess(observe(None, center=(110.0, 200.0)))
    assert report.issues == {Issue.NO_ROOM}
    assert report.brightness is None
    assert assess(observe(None)).issues == frozenset()


def test_a_remembered_face_is_not_judged_by_its_light() -> None:
    # A hand covers the face: the picture there is the hand, not the face.
    report = assess(observe(frame_of(10), held=True))
    assert report.issues == frozenset()
    assert report.brightness is None


def test_hands_are_counted() -> None:
    assert assess(observe(frame_of(130), hands=2)).hands == 2


def test_the_first_issue_follows_the_priority_order() -> None:
    report = Report(True, frozenset({Issue.NO_ROOM, Issue.TOO_DARK, Issue.FACE_SMALL}))
    assert report.first_issue() is Issue.TOO_DARK
    assert Report(True, frozenset({Issue.NO_ROOM})).first_issue() is Issue.NO_ROOM


# ------------------------------------------------------------------------------ smoothing
def feed(tracker: QualityTracker, levels: list[int | None]) -> Report:
    report = tracker.current()
    for level in levels:
        report = tracker.update(
            observe(frame_of(level) if level is not None else None, with_face=level is not None)
        )
    return report


def test_a_single_dark_picture_does_not_raise_the_issue() -> None:
    report = feed(QualityTracker(), [130, 130, 20, 130, 130])
    assert report.issues == frozenset()


def test_an_issue_that_lasts_is_reported() -> None:
    report = feed(QualityTracker(), [130, 20, 20, 20, 20])
    assert report.issues == {Issue.TOO_DARK}


def test_a_face_seen_now_and_then_counts_as_not_found() -> None:
    tracker = QualityTracker()
    report = feed(tracker, [None, None, 130, None, None, 130, None, None])
    assert not report.face_found
    assert report.issues == {Issue.NO_FACE}
    report = feed(tracker, [130, 130, 130, 130, 130])
    assert report.face_found


def test_hands_in_any_recent_picture_count_as_seen() -> None:
    tracker = QualityTracker(window=4)
    tracker.update(observe(frame_of(130), hands=0))
    tracker.update(observe(frame_of(130), hands=1))
    tracker.update(observe(frame_of(130), hands=0))
    assert tracker.current().hands == 1


def test_the_window_forgets_old_pictures() -> None:
    tracker = QualityTracker(window=4)
    feed(tracker, [20, 20, 20, 20])
    assert tracker.current().issues == {Issue.TOO_DARK}
    feed(tracker, [130, 130, 130, 130])
    assert tracker.current().issues == frozenset()
    tracker.reset()
    assert tracker.current().issues == {Issue.NO_FACE}
