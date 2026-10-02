#!/usr/bin/env python3
"""Check a PyInstaller bundle before it is packaged.

``scripts/check_privacy.py`` looks at the source; this looks at what actually ships. It fails when
the bundle

* contains a networking or telemetry component the app never uses (Qt's network and web modules,
  MediaPipe's runtime, an HTTP client package),
* lacks a model file, or the notice and licence texts that must travel with them, or
* is much bigger than it should be (something heavy slipped in).

Usage::

    python scripts/check_bundle.py dist/HabitGuard
    python scripts/check_bundle.py "dist/Habit Guard.app"
    python scripts/check_bundle.py dist/habit-guard
"""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from pathlib import Path

#: Bytes: a bundle bigger than this is bloated (a normal one is 150 to 250 MB).
MAX_BUNDLE_BYTES = 400 * 1024 * 1024

#: File or folder names (case-folded) that must not be in the bundle.
FORBIDDEN = (
    re.compile(r"qt6?network"),
    re.compile(r"qt6?websockets"),
    re.compile(r"qt6?webengine"),
    re.compile(r"qt6?multimedia"),
    re.compile(r"^mediapipe($|[-_.])"),
    re.compile(r"^(requests|urllib3|httpx|aiohttp|websockets|websocket|grpc|boto3|botocore)$"),
    re.compile(r"^(requests|urllib3|httpx|aiohttp)-[\d.]+\.dist-info$"),
)

MODEL_FILES = (
    "face_detection_yunet_2023mar.onnx",
    "palm_detection_mediapipe_2023feb.onnx",
    "handpose_estimation_mediapipe_2023feb.onnx",
)
LICENCE_FILES = ("NOTICE.md", "licenses/LICENSE-APACHE-2.0.txt", "licenses/LICENSE-YUNET.txt")


def models_folder(bundle: Path) -> Path | None:
    """The ``habit_guard/vision/models`` folder inside ``bundle`` (wherever the layout puts it)."""
    for found in bundle.rglob("models"):
        if found.parts[-3:] == ("habit_guard", "vision", "models"):
            return found
    return None


def problems(bundle: Path) -> list[str]:
    """What is wrong with ``bundle``; empty when it is fine."""
    if not bundle.exists():
        return [f"{bundle} does not exist"]
    found: list[str] = []
    total = 0
    for path in bundle.rglob("*"):
        if path.is_symlink():
            continue
        name = path.name.casefold()
        if any(pattern.search(name) for pattern in FORBIDDEN):
            found.append(f"forbidden component: {path.relative_to(bundle)}")
        if path.is_file():
            total += path.stat().st_size
    folder = models_folder(bundle)
    if folder is None:
        found.append("the model folder habit_guard/vision/models is missing")
    else:
        for name in (*MODEL_FILES, *LICENCE_FILES):
            if not (folder / name).is_file():
                found.append(f"missing next to the models: {name}")
    if total > MAX_BUNDLE_BYTES:
        found.append(
            f"bundle is {total / 1024 / 1024:.0f} MiB, over the limit of "
            f"{MAX_BUNDLE_BYTES / 1024 / 1024:.0f} MiB"
        )
    return found


def size_mib(bundle: Path) -> float:
    return (
        sum(p.stat().st_size for p in bundle.rglob("*") if p.is_file() and not p.is_symlink())
        / 1048576
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    bundle = Path(args[0])
    found = problems(bundle)
    if found:
        print("Bundle check FAILED:", file=sys.stderr)
        for line in found:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(
        f"Bundle check passed: {bundle} ({size_mib(bundle):.0f} MiB), models and licences "
        "present, no networking or telemetry components."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
