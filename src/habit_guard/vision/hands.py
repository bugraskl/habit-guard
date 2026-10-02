"""Hand finding and 21-point hand landmarks, run with OpenCV's DNN module.

The two models are MediaPipe's palm detector and hand landmark network, in the
ONNX form published by the OpenCV Zoo (Apache-2.0). The MediaPipe *runtime* is
not used; only the weights are, and the glue around them lives here: the SSD
anchors, the box decoding, and the rotated crop that turns a palm into the
upright hand picture the landmark network expects.

Finding a palm is the expensive step, following one is cheap. After a hand has
been found, the next frame's crop is derived from its previous landmarks and
the palm detector only runs again when no hand is being followed (or now and
then to look for a second one).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from ..types import HAND_LANDMARKS, HandInfo
from .loader import load_net

PALM_INPUT = 192
HAND_INPUT = 224
#: The crop around a palm is this many times the palm box (MediaPipe's constant).
PALM_ROI_SCALE = 2.6
#: A crop is never smaller than this many pixels, so a collapsed hand cannot divide by zero.
MIN_ROI_PX = 8.0
#: The crop around an already followed hand is this many times its landmark box.
TRACK_ROI_SCALE = 2.0

PALM_MODEL = "palm_detection_mediapipe_2023feb.onnx"
HAND_MODEL = "handpose_estimation_mediapipe_2023feb.onnx"

# Palm detector key points: 0 wrist, 1-4 finger bases (index to pinky), 5-6 thumb.
_WRIST, _MIDDLE_BASE = 0, 2
# Hand landmark indices used for the rotation while following a hand.
_LM_WRIST, _LM_MIDDLE_BASE = 0, 9


# --------------------------------------------------------------------------------- geometry
def make_anchors() -> np.ndarray:
    """The palm detector's 2016 SSD anchor centres, normalised to the 192 px input.

    Two feature maps: 24x24 cells with 2 anchors each, then 12x12 cells with 6
    each (three layers share a stride). Anchors are listed row by row.
    """
    centres: list[tuple[float, float]] = []
    for grid, per_cell in ((24, 2), (12, 6)):
        for y in range(grid):
            for x in range(grid):
                centres.extend([((x + 0.5) / grid, (y + 0.5) / grid)] * per_cell)
    return np.array(centres, dtype=np.float32)


@dataclass(frozen=True, slots=True)
class Palm:
    """A palm found by the detector, in image pixels."""

    box: tuple[float, float, float, float]  # x1, y1, x2, y2
    keypoints: np.ndarray  # shape (7, 2)
    score: float


@dataclass(frozen=True, slots=True)
class Roi:
    """A square, rotated crop: centre, side length and the angle that turns the hand upright."""

    center: tuple[float, float]
    size: float
    angle: float  # radians

    def matrix(self, out_size: int) -> tuple[np.ndarray, np.ndarray]:
        """The affine map image -> crop as a 2x3 matrix, and its 2x2 rotation."""
        k = out_size / self.size
        c, s = math.cos(self.angle), math.sin(self.angle)
        rot = np.array([[c, -s], [s, c]], dtype=np.float64)
        linear = k * rot
        offset = np.array([out_size / 2.0] * 2) - linear @ np.array(self.center)
        return np.hstack([linear, offset[:, None]]).astype(np.float32), rot

    def to_image(self, points: np.ndarray, out_size: int) -> np.ndarray:
        """Crop pixel coordinates back to image pixels."""
        _, rot = self.matrix(out_size)
        k = out_size / self.size
        return ((points - out_size / 2.0) / k) @ rot + np.array(self.center)


def _upright_angle(vector: np.ndarray) -> float:
    """The rotation that turns ``vector`` (wrist toward the middle finger) to point up."""
    angle = -math.pi / 2.0 - math.atan2(float(vector[1]), float(vector[0]))
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def _unit(vector: np.ndarray) -> np.ndarray:
    norm = float(np.hypot(vector[0], vector[1]))
    return vector / norm if norm > 1e-6 else np.array([0.0, -1.0])


def roi_from_palm(palm: Palm) -> Roi:
    """MediaPipe's palm-to-hand crop: rotate the palm upright, shift toward the fingers, enlarge."""
    kp = palm.keypoints
    direction = kp[_MIDDLE_BASE] - kp[_WRIST]
    x1, y1, x2, y2 = palm.box
    w, h = x2 - x1, y2 - y1
    center = np.array([(x1 + x2) / 2.0, (y1 + y2) / 2.0]) + _unit(direction) * 0.5 * h
    return Roi(
        (float(center[0]), float(center[1])),
        max(w * PALM_ROI_SCALE, h * PALM_ROI_SCALE, MIN_ROI_PX),
        _upright_angle(direction),
    )


def roi_from_landmarks(landmarks: np.ndarray) -> Roi:
    """The crop for the next frame, from where the hand's 21 points were in this one."""
    direction = landmarks[_LM_MIDDLE_BASE] - landmarks[_LM_WRIST]
    lo, hi = landmarks.min(axis=0), landmarks.max(axis=0)
    w, h = float(hi[0] - lo[0]), float(hi[1] - lo[1])
    center = (lo + hi) / 2.0 + _unit(direction) * 0.1 * h
    return Roi(
        (float(center[0]), float(center[1])),
        max(w * TRACK_ROI_SCALE, h * TRACK_ROI_SCALE, MIN_ROI_PX),
        _upright_angle(direction),
    )


# ---------------------------------------------------------------------------- palm detector
class PalmDetector:
    """Finds palms in a picture. Slow part of hand tracking: ~6 ms on a desktop CPU."""

    def __init__(self, model_path: Path, score_threshold: float = 0.5, nms_threshold: float = 0.3):
        self._net = load_net(model_path)
        self._outputs = self._net.getUnconnectedOutLayersNames()
        self._anchors = make_anchors()
        self.score_threshold = score_threshold
        self.nms_threshold = nms_threshold

    def detect(self, image: np.ndarray) -> list[Palm]:
        """Palms in ``image`` (BGR), best first, with coordinates in that image's pixels."""
        h, w = image.shape[:2]
        scale = PALM_INPUT / max(h, w)
        new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        pad_left, pad_top = (PALM_INPUT - new_w) // 2, (PALM_INPUT - new_h) // 2
        canvas = cv2.copyMakeBorder(
            resized,
            pad_top,
            PALM_INPUT - new_h - pad_top,
            pad_left,
            PALM_INPUT - new_w - pad_left,
            cv2.BORDER_CONSTANT,
            value=(0, 0, 0),
        )
        blob = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        self._net.setInput(blob[np.newaxis])
        raw = self._net.forward(self._outputs)
        # The two outputs: boxes and key points (last dimension 18), scores (last dimension 1).
        boxes_raw, scores_raw = (raw[0], raw[1]) if raw[0].shape[-1] == 18 else (raw[1], raw[0])
        return self._decode(boxes_raw[0], scores_raw[0, :, 0], scale, (pad_left, pad_top))

    def _decode(
        self, raw: np.ndarray, logits: np.ndarray, scale: float, pad: tuple[int, int]
    ) -> list[Palm]:
        scores = 1.0 / (1.0 + np.exp(-np.clip(logits.astype(np.float64), -50.0, 50.0)))
        keep = np.flatnonzero(scores >= self.score_threshold)
        if keep.size == 0:
            return []
        anchors = self._anchors[keep]
        centre = raw[keep, 0:2] / PALM_INPUT + anchors
        size = raw[keep, 2:4] / PALM_INPUT
        top_left = (centre - size / 2.0) * PALM_INPUT
        bottom_right = (centre + size / 2.0) * PALM_INPUT
        rects = np.concatenate([top_left, bottom_right - top_left], axis=1)  # x, y, w, h
        picked = cv2.dnn.NMSBoxes(
            rects.tolist(), scores[keep].tolist(), self.score_threshold, self.nms_threshold
        )
        palms: list[Palm] = []
        offset = np.array(pad, dtype=np.float64)
        for i in np.asarray(picked).reshape(-1):
            kp = (raw[keep[i], 4:].reshape(7, 2) / PALM_INPUT + anchors[i]) * PALM_INPUT
            kp = (kp - offset) / scale
            tl = (top_left[i] - offset) / scale
            br = (bottom_right[i] - offset) / scale
            palms.append(
                Palm(
                    (float(tl[0]), float(tl[1]), float(br[0]), float(br[1])),
                    kp,
                    float(scores[keep[i]]),
                )
            )
        palms.sort(key=lambda p: p.score, reverse=True)
        return palms


# ------------------------------------------------------------------------ hand landmarks
class HandLandmarker:
    """The 21-point hand network: a crop in, landmarks and a "this is a hand" score out."""

    def __init__(self, model_path: Path):
        self._net = load_net(model_path)
        self._outputs = self._net.getUnconnectedOutLayersNames()

    def infer(self, image: np.ndarray, roi: Roi) -> tuple[np.ndarray, float]:
        """Landmarks (21, 2) in image pixels and the hand-presence score for ``roi``."""
        matrix, _ = roi.matrix(HAND_INPUT)
        crop = cv2.warpAffine(
            image,
            matrix,
            (HAND_INPUT, HAND_INPUT),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )
        blob = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        self._net.setInput(blob[np.newaxis])
        out = self._net.forward(self._outputs)
        landmarks = out[0].reshape(HAND_LANDMARKS, 3)[:, :2].astype(np.float64)
        score = float(np.ravel(out[1])[0])
        return roi.to_image(landmarks, HAND_INPUT), score


# ------------------------------------------------------------------------------- tracking
class HandTracker:
    """Follows up to ``max_hands`` hands from frame to frame.

    A *new* hand must score ``start_score`` to be believed: skin-coloured
    shoulders, knees and beards produce palm candidates whose hand score hovers
    around 0.5, while a real hand scores 0.9 and more. A hand that is already
    followed is kept down to ``keep_score``, so a partly hidden hand (fingers
    curled at the mouth) does not flicker in and out.
    """

    def __init__(
        self,
        palm: PalmDetector,
        landmarker: HandLandmarker,
        *,
        max_hands: int = 2,
        start_score: float = 0.7,
        keep_score: float = 0.5,
        rescan_s: float = 1.0,
    ):
        self._palm = palm
        self._landmarker = landmarker
        self.max_hands = max_hands
        self.start_score = start_score
        self.keep_score = keep_score
        self.rescan_s = rescan_s
        self._tracked: list[np.ndarray] = []
        self._last_scan = float("-inf")

    def reset(self) -> None:
        self._tracked.clear()
        self._last_scan = float("-inf")

    def update(
        self,
        image: np.ndarray,
        now: float,
        search: tuple[int, int, int, int] | None = None,
    ) -> list[HandInfo]:
        """Hands in ``image`` (BGR).

        ``search`` is an ``x0, y0, x1, y1`` window to look for new palms in
        (the area around the face); hands already followed are tracked wherever
        they went.
        """
        candidates = [(roi_from_landmarks(lm), self.keep_score) for lm in self._tracked]
        scan = len(candidates) < self.max_hands and (
            not candidates or now - self._last_scan >= self.rescan_s
        )
        if scan:
            self._last_scan = now
            for palm in self._find_palms(image, search):
                if len(candidates) >= self.max_hands:
                    break
                roi = roi_from_palm(palm)
                if not self._duplicates(roi, [c[0] for c in candidates]):
                    candidates.append((roi, self.start_score))
        hands: list[HandInfo] = []
        tracked: list[np.ndarray] = []
        for roi, needed in candidates:
            landmarks, score = self._landmarker.infer(image, roi)
            if score >= needed and np.isfinite(landmarks).all():
                hands.append(HandInfo(landmarks=landmarks, score=score))
                tracked.append(landmarks)
        self._tracked = tracked
        return hands

    def _find_palms(
        self, image: np.ndarray, search: tuple[int, int, int, int] | None
    ) -> list[Palm]:
        if search is None:
            return self._palm.detect(image)
        h, w = image.shape[:2]
        x0, y0 = max(0, search[0]), max(0, search[1])
        x1, y1 = min(w, search[2]), min(h, search[3])
        if x1 - x0 < 16 or y1 - y0 < 16:
            return []
        palms = self._palm.detect(image[y0:y1, x0:x1])
        shift = np.array([x0, y0], dtype=np.float64)
        return [
            Palm(
                (p.box[0] + x0, p.box[1] + y0, p.box[2] + x0, p.box[3] + y0),
                p.keypoints + shift,
                p.score,
            )
            for p in palms
        ]

    @staticmethod
    def _duplicates(roi: Roi, others: list[Roi]) -> bool:
        """True when ``roi`` covers (nearly) the same hand as one already in ``others``."""
        return any(
            math.hypot(roi.center[0] - o.center[0], roi.center[1] - o.center[1])
            < 0.5 * min(roi.size, o.size)
            for o in others
        )
