"""Face finding with OpenCV's YuNet detector, and keeping the last face while a hand hides it."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ..types import FaceInfo
from .loader import load_face_detector

#: Faces are searched in a copy of the picture no wider than this; YuNet is quick at this size.
DETECT_WIDTH = 320
YUNET_MODEL = "face_detection_yunet_2023mar.onnx"


class FaceDetector:
    """Finds the main face and its five landmarks (eyes, nose tip, mouth corners)."""

    def __init__(self, model_path: Path, score_threshold: float = 0.6):
        self._score_threshold = score_threshold
        self._size = (0, 0)
        self._detector = load_face_detector(
            model_path, (DETECT_WIDTH, DETECT_WIDTH * 3 // 4), score_threshold, 0.3, 5
        )

    def detect(self, image: np.ndarray) -> FaceInfo | None:
        """The largest confident face in ``image`` (BGR), in that image's pixels."""
        h, w = image.shape[:2]
        scale = min(1.0, DETECT_WIDTH / w)
        size = (max(1, round(w * scale)), max(1, round(h * scale)))
        small = image if scale == 1.0 else cv2.resize(image, size, interpolation=cv2.INTER_AREA)
        if size != self._size:
            self._detector.setInputSize(size)
            self._size = size
        _, faces = self._detector.detect(small)
        if faces is None or len(faces) == 0:
            return None
        best = max(faces, key=lambda f: float(f[2] * f[3]) * float(f[14]))
        return _to_face_info(best / scale if scale != 1.0 else best, float(best[14]))


def _to_face_info(row: np.ndarray, score: float) -> FaceInfo:
    """Turn a YuNet row (box, five points, score) into a :class:`FaceInfo`."""
    x, y, w, h = (float(v) for v in row[:4])
    pts = np.asarray(row[4:14], dtype=np.float64).reshape(5, 2)
    eyes = sorted((tuple(pts[0]), tuple(pts[1])), key=lambda p: p[0])
    mouth = sorted((tuple(pts[3]), tuple(pts[4])), key=lambda p: p[0])
    return FaceInfo(
        box=(x, y, w, h),
        left_eye=(float(eyes[0][0]), float(eyes[0][1])),
        right_eye=(float(eyes[1][0]), float(eyes[1][1])),
        nose=(float(pts[2][0]), float(pts[2][1])),
        mouth_left=(float(mouth[0][0]), float(mouth[0][1])),
        mouth_right=(float(mouth[1][0]), float(mouth[1][1])),
        score=score,
    )


class FaceMemory:
    """Remembers the last face so zones survive a hand covering the face.

    A hand over the mouth is exactly when the detector tends to lose the face,
    and nail biting keeps it there for as long as the habit lasts. The head
    hardly moves in that time, so the last good face stays valid while a hand
    is *near it* (up to ``hold_near_s``), or for a short ``hold_s`` while a hand
    is merely in view. With no hand at all, a lost face means the person left.
    """

    def __init__(self, hold_s: float = 2.0, hold_near_s: float = 60.0):
        self.hold_s = hold_s
        self.hold_near_s = hold_near_s
        self._face: FaceInfo | None = None
        self._seen_at = float("-inf")

    def reset(self) -> None:
        self._face = None
        self._seen_at = float("-inf")

    def update(
        self,
        now: float,
        detected: FaceInfo | None,
        hand_visible: bool,
        hand_near_face: bool = False,
    ) -> tuple[FaceInfo | None, bool]:
        """``(face to use, whether it is a remembered one)``."""
        if detected is not None:
            self._face, self._seen_at = detected, now
            return detected, False
        if self._face is not None:
            age = now - self._seen_at
            if hand_near_face and age <= self.hold_near_s:
                return self._face, True
            if hand_visible and age <= self.hold_s:
                return self._face, True
            if age > self.hold_s:
                self._face = None
        return None, False

    @property
    def last(self) -> FaceInfo | None:
        return self._face
