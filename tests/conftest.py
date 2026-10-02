"""Shared test helpers: a synthetic face and hand built from plain numbers."""

from __future__ import annotations

import os

# Qt runs without a display in tests; this must be set before Qt is first imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import math

import numpy as np
import pytest

from habit_guard.types import FaceInfo, HandInfo

# A 640x480 frame with a frontal face: eyes 100 px apart, centred on x = 320.
EYE_DISTANCE = 100.0
EYE_Y = 200.0


def make_face(roll_deg: float = 0.0, center: tuple[float, float] = (320.0, EYE_Y)) -> FaceInfo:
    """A frontal face; ``roll_deg`` tilts it in the image plane about the eye midpoint."""
    cx, cy = center
    # Positions in face units (x right, y down), as YuNet would see a typical face.
    pts = {
        "left_eye": (-0.5, 0.0),
        "right_eye": (0.5, 0.0),
        "nose": (0.0, 0.75),
        "mouth_left": (-0.4, 1.3),
        "mouth_right": (0.4, 1.3),
    }
    c, s = math.cos(math.radians(roll_deg)), math.sin(math.radians(roll_deg))

    def place(u: float, v: float) -> tuple[float, float]:
        return (cx + (u * c - v * s) * EYE_DISTANCE, cy + (u * s + v * c) * EYE_DISTANCE)

    placed = {name: place(*uv) for name, uv in pts.items()}
    corners = [place(-1.0, -0.6), place(1.0, 2.3)]
    box = (
        corners[0][0],
        corners[0][1],
        corners[1][0] - corners[0][0],
        corners[1][1] - corners[0][1],
    )
    return FaceInfo(box=box, score=0.95, **placed)


def make_hand(
    tip_at: tuple[float, float] | None = None,
    *,
    face_center: tuple[float, float] = (320.0, EYE_Y),
    face_u_v: tuple[float, float] | None = None,
    roll_deg: float = 0.0,
) -> HandInfo:
    """A hand whose fingertips all sit at one spot, given in face units (``face_u_v``) or pixels.

    The other landmarks sit well away from the face so that only the tips matter.
    """
    if face_u_v is not None:
        cx, cy = face_center
        c, s = math.cos(math.radians(roll_deg)), math.sin(math.radians(roll_deg))
        u, v = face_u_v
        tip_at = (cx + (u * c - v * s) * EYE_DISTANCE, cy + (u * s + v * c) * EYE_DISTANCE)
    assert tip_at is not None
    lm = np.full((21, 2), 5000.0)  # everything far away ...
    for i in (4, 8, 12, 16, 20):
        lm[i] = tip_at  # ... except the fingertips
    return HandInfo(landmarks=lm, score=0.9)


@pytest.fixture
def face() -> FaceInfo:
    return make_face()


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """No test may touch the real settings: every test gets its own empty config folder."""
    monkeypatch.setenv("HABIT_GUARD_HOME", str(tmp_path / "config"))


@pytest.fixture(autouse=True)
def _english_by_default(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Tests must not depend on the language of the machine they run on."""
    from habit_guard import i18n

    monkeypatch.setattr(i18n, "detect_language", lambda: "en")
    i18n.set_language("en")
