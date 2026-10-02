"""The model files Habit Guard needs, with the checksums they must have.

``scripts/fetch_models.py`` downloads them from the sources listed in
``vision/models/NOTICE.md`` and checks them against this table; ``habit-guard
doctor`` checks them too. Nothing here touches the network.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

#: file name -> SHA-256
MODEL_SHA256: dict[str, str] = {
    "face_detection_yunet_2023mar.onnx": (
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
    ),
    "palm_detection_mediapipe_2023feb.onnx": (
        "78ff51c38496b7fc8b8ebdb6cc8c1abb02fa6c38427c6848254cdaba57fcce7c"
    ),
    "handpose_estimation_mediapipe_2023feb.onnx": (
        "db0898ae717b76b075d9bf563af315b29562e11f8df5027a1ef07b02bef6d81c"
    ),
}

_CHUNK = 1 << 18


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(directory: Path) -> dict[str, str]:
    """``{file name: "ok" | "missing" | "mismatch"}`` for every model in ``directory``."""
    result: dict[str, str] = {}
    for name, expected in MODEL_SHA256.items():
        path = directory / name
        if not path.is_file():
            result[name] = "missing"
        else:
            result[name] = "ok" if sha256_file(path) == expected else "mismatch"
    return result
