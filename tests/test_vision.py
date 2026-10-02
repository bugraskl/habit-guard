from __future__ import annotations

import math
import threading
import time
from typing import ClassVar

import cv2
import numpy as np
import pytest

from conftest import make_face, make_hand
from habit_guard.config import CADENCES, Settings
from habit_guard.paths import models_dir
from habit_guard.types import FaceInfo, HandInfo, Observation
from habit_guard.vision.analyzer import Analyzer, expand_box
from habit_guard.vision.camera import Camera
from habit_guard.vision.face import YUNET_MODEL, FaceDetector, FaceMemory
from habit_guard.vision.hands import (
    HAND_INPUT,
    HAND_MODEL,
    PALM_MODEL,
    HandLandmarker,
    HandTracker,
    Palm,
    PalmDetector,
    Roi,
    make_anchors,
    roi_from_landmarks,
    roi_from_palm,
)
from habit_guard.vision.motion import MotionGate, is_blind, thumbnail
from habit_guard.vision.pipeline import Pipeline, Status

CADENCE = CADENCES["balanced"]
needs_models = pytest.mark.skipif(
    not all((models_dir() / n).is_file() for n in (YUNET_MODEL, PALM_MODEL, HAND_MODEL)),
    reason="model files not fetched",
)


# ------------------------------------------------------------------------------ hand maths
def test_anchor_table_matches_the_models_output_size() -> None:
    anchors = make_anchors()
    assert anchors.shape == (2016, 2)
    assert anchors[0] == pytest.approx((0.5 / 24, 0.5 / 24))
    assert anchors[-1] == pytest.approx((11.5 / 12, 11.5 / 12))
    assert (anchors > 0).all()
    assert (anchors < 1).all()


@pytest.mark.parametrize("angle", [0.0, 0.7, -2.0, math.pi])
def test_roi_maps_points_to_the_crop_and_back(angle: float) -> None:
    roi = Roi(center=(300.0, 200.0), size=180.0, angle=angle)
    matrix, _ = roi.matrix(HAND_INPUT)
    pts = np.array([[300.0, 200.0], [250.0, 150.0], [400.0, 260.0]])
    crop = cv2.transform(pts[None].astype(np.float32), matrix)[0]
    assert crop[0] == pytest.approx((HAND_INPUT / 2, HAND_INPUT / 2), abs=1e-3)
    assert roi.to_image(crop.astype(np.float64), HAND_INPUT) == pytest.approx(pts, abs=1e-2)


@pytest.mark.parametrize(
    ("direction", "expected_angle"),
    [((0.0, -1.0), 0.0), ((1.0, 0.0), -math.pi / 2), ((-1.0, 0.0), math.pi / 2)],
)
def test_palm_roi_turns_the_hand_upright(
    direction: tuple[float, float], expected_angle: float
) -> None:
    wrist = np.array([300.0, 300.0])
    kp = np.zeros((7, 2))
    kp[0] = wrist
    kp[2] = wrist + 100.0 * np.array(direction)
    palm = Palm(box=(260.0, 200.0, 340.0, 280.0), keypoints=kp, score=0.9)
    roi = roi_from_palm(palm)
    assert roi.angle == pytest.approx(expected_angle, abs=1e-6)
    # Shifted from the palm box centre toward the fingers, and enlarged 2.6x.
    assert roi.size == pytest.approx(80.0 * 2.6)
    shift = np.array(roi.center) - np.array([300.0, 240.0])
    assert np.dot(shift, direction) > 0


def test_crop_really_makes_the_hand_upright() -> None:
    """A bar pointing right, with a bright fingertip end, must point up in the crop."""
    image = np.zeros((400, 400, 3), np.uint8)
    cv2.rectangle(image, (200, 190), (300, 210), (150, 150, 150), -1)  # the palm
    cv2.rectangle(image, (300, 190), (320, 210), (255, 255, 255), -1)  # the fingertip end
    kp = np.zeros((7, 2))
    kp[0] = (200, 200)  # wrist
    kp[2] = (300, 200)  # middle finger base: the hand points right
    palm = Palm(box=(180.0, 160.0, 260.0, 240.0), keypoints=kp, score=0.9)
    roi = roi_from_palm(palm)
    matrix, _ = roi.matrix(HAND_INPUT)
    crop = cv2.warpAffine(image, matrix, (HAND_INPUT, HAND_INPUT))[:, :, 0]
    ys, xs = np.nonzero(crop > 100)
    assert ys.size > 100
    assert ys.std() > 3 * xs.std()  # long axis is vertical now
    assert abs(xs.mean() - HAND_INPUT / 2) < 8  # centred horizontally
    top, bottom = crop[: HAND_INPUT // 2].mean(), crop[HAND_INPUT // 2 :].mean()
    assert top > bottom  # the bright fingertip end is at the top


def test_roi_from_landmarks_encloses_the_hand() -> None:
    lm = np.zeros((21, 2))
    lm[:, 0] = np.linspace(100, 160, 21)
    lm[:, 1] = np.linspace(300, 200, 21)  # points up and a bit right
    lm[9] = (140, 230)
    roi = roi_from_landmarks(lm)
    assert roi.size >= 2.0 * 100.0 - 1e-6
    assert 100 < roi.center[0] < 170
    assert 190 < roi.center[1] < 300


# --------------------------------------------------------------------- models on real files
@needs_models
def test_palm_detector_and_landmarker_run_and_find_nothing_in_an_empty_picture() -> None:
    palm = PalmDetector(models_dir() / PALM_MODEL)
    assert palm.detect(np.zeros((480, 640, 3), np.uint8)) == []
    assert palm.detect(np.full((120, 90, 3), 127, np.uint8)) == []
    lm = HandLandmarker(models_dir() / HAND_MODEL)
    points, score = lm.infer(np.zeros((480, 640, 3), np.uint8), Roi((320.0, 240.0), 200.0, 0.0))
    assert points.shape == (21, 2)
    assert 0.0 <= score <= 1.0
    assert score < 0.5  # no hand in a black picture


@needs_models
def test_face_detector_finds_nothing_in_an_empty_picture() -> None:
    faces = FaceDetector(models_dir() / YUNET_MODEL)
    assert faces.detect(np.zeros((480, 640, 3), np.uint8)) is None
    assert faces.detect(np.random.default_rng(1).integers(0, 255, (480, 640, 3), np.uint8)) is None


@needs_models
def test_tracker_returns_no_hands_for_noise_and_survives_odd_windows() -> None:
    tracker = HandTracker(
        PalmDetector(models_dir() / PALM_MODEL), HandLandmarker(models_dir() / HAND_MODEL)
    )
    noise = np.random.default_rng(2).integers(0, 255, (480, 640, 3), np.uint8)
    assert tracker.update(noise, 0.0) == []
    assert tracker.update(noise, 1.0, (100, 100, 400, 400)) == []
    assert tracker.update(noise, 2.0, (0, 0, 5, 5)) == []  # a window too small to search
    assert tracker.update(noise, 3.0, (-50, -50, 900, 900)) == []  # a window beyond the picture


# --------------------------------------------------------------------------- motion gate
def test_motion_gate_notices_change_and_ignores_noise() -> None:
    rng = np.random.default_rng(0)
    base = rng.integers(60, 180, (480, 640, 3), np.uint8)
    gate = MotionGate()
    first = thumbnail(base)
    assert gate.moved(first)  # nothing to compare with yet
    gate.accept(first)
    noisy = np.clip(base.astype(np.int16) + rng.integers(-2, 3, base.shape), 0, 255).astype(
        np.uint8
    )
    assert not gate.moved(thumbnail(noisy))
    moved = base.copy()
    moved[100:400, 200:500] = 250
    assert gate.moved(thumbnail(moved))


def test_blind_frames_are_recognised() -> None:
    assert is_blind(thumbnail(np.zeros((480, 640, 3), np.uint8)))
    assert not is_blind(
        thumbnail(np.random.default_rng(3).integers(0, 255, (480, 640, 3), np.uint8))
    )


def test_thumbnail_window_is_clipped_to_the_picture() -> None:
    frame = np.full((100, 100, 3), 200, np.uint8)
    assert thumbnail(frame, (-50, -50, 500, 500)).shape == (24, 32)
    assert thumbnail(frame, (10, 10, 12, 12)).shape == (24, 32)  # too small: the whole picture


# --------------------------------------------------------------------------- face memory
def test_face_memory_holds_the_face_only_while_a_hand_is_visible() -> None:
    memory = FaceMemory(hold_s=2.0)
    face = make_face()
    assert memory.update(0.0, face, False) == (face, False)
    assert memory.update(1.0, None, True) == (face, True)  # hand over the face: keep it
    assert memory.update(1.5, None, False) == (None, False)  # no hand: the person left
    assert memory.update(1.6, None, True) == (face, True)  # not forgotten yet
    assert memory.update(3.5, None, True) == (None, False)  # held too long
    assert memory.last is None


def test_face_memory_holds_a_covered_face_for_as_long_as_the_hand_stays_near() -> None:
    memory = FaceMemory(hold_s=2.0, hold_near_s=60.0)
    face = make_face()
    memory.update(0.0, face, False)
    # A hand covers the mouth for half a minute: the face detector sees nothing, the zones stay.
    assert memory.update(30.0, None, True, True) == (face, True)
    assert memory.update(59.0, None, True, True) == (face, True)
    # Beyond the long hold, or once the hand is not near, the short hold applies.
    assert memory.update(61.0, None, True, True) == (None, False)
    memory.update(100.0, face, False)
    assert memory.update(105.0, None, True, False) == (None, False)


# ------------------------------------------------------------------------------ analyzer
class FakeFaces:
    def __init__(self) -> None:
        self.face: FaceInfo | None = make_face()
        self.calls = 0

    def detect(self, image: np.ndarray) -> FaceInfo | None:
        self.calls += 1
        return self.face


class FakeHands:
    def __init__(self) -> None:
        self.hands: list[HandInfo] = []
        self.calls = 0
        self.resets = 0
        self.last_search: tuple[int, int, int, int] | None = None

    def update(self, image, now, search=None):  # type: ignore[no-untyped-def]
        self.calls += 1
        self.last_search = search
        return list(self.hands)

    def reset(self) -> None:
        self.resets += 1


def still_frame() -> np.ndarray:
    return np.random.default_rng(5).integers(50, 200, (480, 640, 3), np.uint8)


def test_analyzer_runs_slowly_when_nobody_is_there() -> None:
    faces, hands = FakeFaces(), FakeHands()
    faces.face = None
    analyzer = Analyzer(faces, hands)
    step = analyzer.step(still_frame(), 0.0, CADENCE)
    assert step.observation is not None
    assert step.observation.face is None
    assert step.interval == CADENCE.no_face_s
    assert hands.calls == 0  # no face, no zones, no hand search


def test_analyzer_skips_still_pictures_but_not_forever() -> None:
    faces, hands = FakeFaces(), FakeHands()
    analyzer = Analyzer(faces, hands)
    frame = still_frame()
    assert analyzer.step(frame, 0.0, CADENCE).observation is not None
    skipped = analyzer.step(frame, 0.5, CADENCE)
    assert skipped.observation is None
    assert skipped.interval == CADENCE.idle_s
    assert faces.calls == 1
    forced = analyzer.step(frame, CADENCE.forced_s + 0.1, CADENCE)
    assert forced.observation is not None
    assert faces.calls == 2


def test_analyzer_analyses_when_the_picture_changes() -> None:
    faces, hands = FakeFaces(), FakeHands()
    analyzer = Analyzer(faces, hands)
    frame = still_frame()
    analyzer.step(frame, 0.0, CADENCE)
    changed = frame.copy()
    changed[:, :] = 255 - changed
    assert analyzer.step(changed, 0.3, CADENCE).observation is not None


def test_analyzer_speeds_up_while_a_hand_is_near_and_slows_down_after() -> None:
    faces, hands = FakeFaces(), FakeHands()
    analyzer = Analyzer(faces, hands)
    frame = still_frame()
    hands.hands = [make_hand(face_u_v=(0.0, 1.3))]
    step = analyzer.step(frame, 0.0, CADENCE)
    assert step.observation is not None
    assert step.observation.hand_near
    assert step.interval == CADENCE.active_s
    hands.hands = []
    # The hand is gone, but fast analysis goes on for a moment (no motion gating).
    assert analyzer.step(frame, 0.3, CADENCE).observation is not None
    late = analyzer.step(frame, 3.0, CADENCE)
    assert late.observation is not None
    assert late.interval == CADENCE.idle_s


def test_analyzer_keeps_the_face_while_a_hand_covers_it() -> None:
    faces, hands = FakeFaces(), FakeHands()
    analyzer = Analyzer(faces, hands)
    frame = still_frame()
    first = analyzer.step(frame, 0.0, CADENCE).observation
    assert first is not None
    faces.face = None  # the hand covers the face, the detector loses it
    hands.hands = [make_hand(face_u_v=(0.0, 1.3))]
    step = analyzer.step(255 - frame, 0.2, CADENCE)  # the hand's arrival moved the picture
    assert step.observation is not None
    assert step.observation.face == first.face
    assert step.observation.face_held
    # ... and the search window for the hand is still built from the remembered face.
    assert hands.last_search is not None


def test_analyzer_keeps_zones_while_a_hand_stays_over_the_face_for_a_long_time() -> None:
    faces, hands = FakeFaces(), FakeHands()
    analyzer = Analyzer(faces, hands)
    frame = still_frame()
    first = analyzer.step(frame, 0.0, CADENCE).observation
    assert first is not None
    faces.face = None  # the detector never sees the face again while the hand covers it
    hands.hands = [make_hand(face_u_v=(0.0, 1.3))]
    for i, t in enumerate((0.2, 3.0, 10.0, 30.0)):
        step = analyzer.step(255 - frame if i % 2 == 0 else frame, t, CADENCE)
        assert step.observation is not None
        assert step.observation.face == first.face
        assert step.observation.face_held
    hands.hands = []  # the hand comes down and the face is still not found: the person left
    gone = analyzer.step(255 - frame, 40.0, CADENCE)
    assert gone.observation is not None
    assert gone.observation.face is None


def test_preview_bypasses_the_gate_and_attaches_the_picture() -> None:
    analyzer = Analyzer(FakeFaces(), FakeHands())
    frame = still_frame()
    analyzer.step(frame, 0.0, CADENCE)
    step = analyzer.step(frame, 0.1, CADENCE, keep_frame=True)
    assert step.observation is not None
    assert step.observation.frame is frame
    assert step.interval <= CADENCE.active_s


def test_expand_box_clips_to_the_picture() -> None:
    assert expand_box((100.0, 100.0, 50.0, 60.0), 1.0, (640, 480)) == (50, 40, 200, 220)
    assert expand_box((10.0, 10.0, 600.0, 400.0), 1.0, (640, 480)) == (0, 0, 640, 480)


# ------------------------------------------------------------------------------ pipeline
class FakeCamera:
    """A camera that delivers still pictures, with a switch to make it busy."""

    available = True
    opened_sources: ClassVar[list[object]] = []

    def __init__(self, source: int | str, api: str = "auto"):
        self.source = source
        self.api = api
        self._open = False

    def open(self) -> bool:
        if not FakeCamera.available:
            return False
        FakeCamera.opened_sources.append(self.source)
        self._open = True
        return True

    def grab(self) -> bool:
        time.sleep(0.005)
        return self._open

    def retrieve(self) -> np.ndarray:
        return still_frame()

    def release(self) -> None:
        self._open = False


def wait_for(predicate, timeout: float = 5.0) -> bool:  # type: ignore[no-untyped-def]
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_pipeline_streams_observations_pauses_and_resumes() -> None:
    FakeCamera.available = True
    FakeCamera.opened_sources = []
    observations: list[Observation] = []
    statuses: list[Status] = []
    lock = threading.Lock()

    def on_obs(obs: Observation) -> None:
        with lock:
            observations.append(obs)

    pipeline = Pipeline(
        Settings(),
        on_obs,
        lambda status, detail: statuses.append(status),
        analyzer=Analyzer(FakeFaces(), FakeHands()),
        camera_factory=FakeCamera,  # type: ignore[arg-type]
    )
    pipeline.start()
    try:
        assert wait_for(lambda: len(observations) >= 1)
        assert Status.RUNNING in statuses
        pipeline.pause()
        assert wait_for(lambda: Status.PAUSED in statuses)
        before = len(observations)
        time.sleep(0.3)
        assert len(observations) == before  # nothing is analysed while paused
        pipeline.resume()
        assert wait_for(lambda: len(observations) > before)
        assert len(FakeCamera.opened_sources) >= 2  # released on pause, opened again on resume
    finally:
        pipeline.stop()


def test_pipeline_retries_a_busy_camera() -> None:
    FakeCamera.available = False
    statuses: list[Status] = []
    pipeline = Pipeline(
        Settings(),
        lambda obs: None,
        lambda status, detail: statuses.append(status),
        analyzer=Analyzer(FakeFaces(), FakeHands()),
        camera_factory=FakeCamera,  # type: ignore[arg-type]
    )
    pipeline.start()
    try:
        assert wait_for(lambda: Status.NO_CAMERA in statuses)
    finally:
        pipeline.stop()
        FakeCamera.available = True


def test_pipeline_reports_missing_models(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("habit_guard.vision.pipeline.models_dir", lambda: tmp_path)
    statuses: list[tuple[Status, str]] = []
    pipeline = Pipeline(Settings(), lambda obs: None, lambda s, d: statuses.append((s, d)))
    pipeline.start()
    assert wait_for(lambda: any(s is Status.ERROR for s, _ in statuses))
    assert "fetch_models" in next(d for s, d in statuses if s is Status.ERROR)
    pipeline.stop()


def test_camera_returns_false_for_a_missing_file() -> None:
    cam = Camera("definitely-not-a-video.mp4")
    assert cam.open() is False
    assert cam.grab() is False
    assert cam.retrieve() is None
    cam.release()


# ----------------------------------------------------------------------- tracker thresholds
class StubPalms:
    def __init__(self) -> None:
        self.calls = 0

    def detect(self, image: np.ndarray) -> list[Palm]:
        self.calls += 1
        kp = np.zeros((7, 2))
        kp[0] = (300, 300)
        kp[2] = (300, 200)
        return [Palm(box=(260.0, 200.0, 340.0, 280.0), keypoints=kp, score=0.9)]


class StubLandmarker:
    """Returns a scripted presence score for each call."""

    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.calls = 0

    def infer(self, image: np.ndarray, roi: Roi) -> tuple[np.ndarray, float]:
        score = self.scores[min(self.calls, len(self.scores) - 1)]
        self.calls += 1
        points = np.tile(np.array(roi.center), (21, 1)) + np.arange(21)[:, None]
        return points, score


def test_a_new_hand_needs_a_high_score_but_a_followed_one_is_kept_lower() -> None:
    frame = np.zeros((480, 640, 3), np.uint8)
    # Presence 0.55 is not enough to believe in a new hand ...
    tracker = HandTracker(StubPalms(), StubLandmarker([0.55]))  # type: ignore[arg-type]
    assert tracker.update(frame, 0.0) == []
    # ... but a hand that scored 0.9 is followed through frames at 0.55.
    tracker = HandTracker(StubPalms(), StubLandmarker([0.9, 0.55, 0.55, 0.3]))  # type: ignore[arg-type]
    assert len(tracker.update(frame, 0.0)) == 1
    assert len(tracker.update(frame, 0.1)) == 1
    assert len(tracker.update(frame, 0.2)) == 1
    assert tracker.update(frame, 0.3) == []  # presence 0.3: the hand is gone


def test_tracker_does_not_run_the_palm_detector_while_following_a_hand() -> None:
    frame = np.zeros((480, 640, 3), np.uint8)
    palms = StubPalms()
    tracker = HandTracker(palms, StubLandmarker([0.95]), max_hands=1)  # type: ignore[arg-type]
    for i in range(5):
        assert len(tracker.update(frame, i * 0.1)) == 1
    assert palms.calls == 1  # found once, then followed from its own landmarks
    tracker.reset()
    tracker.update(frame, 1.0)
    assert palms.calls == 2
