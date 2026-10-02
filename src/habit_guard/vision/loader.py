"""Loading model files in a way that survives any install path.

OpenCV opens a model given by *path* with the operating system's ANSI file API.
On Windows that cannot name a folder with letters outside the ANSI code page,
for example a user name such as "Şükrü" on a Western system: the model then
"cannot be read" although it is right there. Reading the file in Python and
handing OpenCV the *bytes* avoids the path altogether.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def _bytes(path: Path) -> np.ndarray:
    return np.frombuffer(path.read_bytes(), dtype=np.uint8)


def load_net(path: Path) -> cv2.dnn.Net:
    """An ONNX network from ``path``."""
    return cv2.dnn.readNetFromONNX(_bytes(path))


def load_face_detector(
    path: Path, size: tuple[int, int], score_threshold: float, nms_threshold: float, top_k: int
) -> cv2.FaceDetectorYN:
    """A YuNet face detector from ``path`` for pictures of ``size``."""
    return cv2.FaceDetectorYN.create(
        "onnx", _bytes(path), np.empty(0, np.uint8), size, score_threshold, nms_threshold, top_k
    )
