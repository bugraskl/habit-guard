#!/usr/bin/env python3
"""Download and verify the model files that ship with Habit Guard.

The models are committed to the repository, so most people never need to run
this. It exists to recreate them in a damaged checkout, to verify them in CI,
and to record exactly where each file comes from (see also
``src/habit_guard/vision/models/NOTICE.md``).

Usage::

    python scripts/fetch_models.py            # download missing or corrupt models
    python scripts/fetch_models.py --check    # verify only; never touches the network
    python scripts/fetch_models.py --force    # download again even if valid

Every download is checked against the pinned SHA-256 in
``habit_guard.vision.manifest`` before it replaces anything, so a failed or
tampered download can never overwrite a good model. The sources are pinned to
one commit of the OpenCV Zoo.

This is developer tooling that lives outside ``src/``: the application itself
never touches the network.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from habit_guard.vision.manifest import MODEL_SHA256, sha256_file  # noqa: E402

DEFAULT_DEST = REPO_ROOT / "src" / "habit_guard" / "vision" / "models"
USER_AGENT = "habit-guard-fetch-models/1.0 (+https://github.com/bugraskl/habit-guard)"
#: The OpenCV Zoo commit the models are taken from.
ZOO_COMMIT = "47534e27c9851bb1128ccc0102f1145e27f23f98"
ZOO_RAW = f"https://github.com/opencv/opencv_zoo/raw/{ZOO_COMMIT}/models"
#: Refuse absurdly large responses (the real files are a few MiB).
MAX_BYTES = 64 * 1024 * 1024
_CHUNK = 1024 * 256


@dataclass(frozen=True)
class Source:
    filename: str
    url: str
    license: str
    description: str


SOURCES: tuple[Source, ...] = (
    Source(
        "face_detection_yunet_2023mar.onnx",
        f"{ZOO_RAW}/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "MIT",
        "YuNet face detector: face box, eyes, nose tip and mouth corners",
    ),
    Source(
        "palm_detection_mediapipe_2023feb.onnx",
        f"{ZOO_RAW}/palm_detection_mediapipe/palm_detection_mediapipe_2023feb.onnx",
        "Apache-2.0",
        "MediaPipe palm detector, converted to ONNX by the OpenCV Zoo",
    ),
    Source(
        "handpose_estimation_mediapipe_2023feb.onnx",
        f"{ZOO_RAW}/handpose_estimation_mediapipe/handpose_estimation_mediapipe_2023feb.onnx",
        "Apache-2.0",
        "MediaPipe 21-point hand landmark network, converted to ONNX by the OpenCV Zoo",
    ),
)


class DownloadError(RuntimeError):
    """A model could not be downloaded or failed verification."""


def verify(source: Source, dest: Path) -> str:
    """``"ok"``, ``"missing"`` or ``"mismatch"`` for one model in ``dest``."""
    path = dest / source.filename
    if not path.is_file():
        return "missing"
    return "ok" if sha256_file(path) == MODEL_SHA256[source.filename] else "mismatch"


def _download_once(source: Source, target: Path, timeout: float) -> None:
    request = urllib.request.Request(source.url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    received = 0
    with urllib.request.urlopen(request, timeout=timeout) as response, target.open("wb") as out:
        while chunk := response.read(_CHUNK):
            received += len(chunk)
            if received > MAX_BYTES:
                raise DownloadError(f"{source.filename}: response larger than {MAX_BYTES} bytes")
            digest.update(chunk)
            out.write(chunk)
    expected = MODEL_SHA256[source.filename]
    if digest.hexdigest() != expected:
        raise DownloadError(
            f"{source.filename}: checksum mismatch (got {digest.hexdigest()}, "
            f"expected {expected}); the upstream file may have changed"
        )


def download(source: Source, dest: Path, *, timeout: float = 60.0, attempts: int = 3) -> Path:
    """Download ``source`` into ``dest`` atomically; the file appears only once it is verified."""
    dest.mkdir(parents=True, exist_ok=True)
    final = dest / source.filename
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        fd, tmp_name = tempfile.mkstemp(prefix=f".{source.filename}.", suffix=".part", dir=dest)
        os.close(fd)
        tmp = Path(tmp_name)
        try:
            _download_once(source, tmp, timeout)
            os.replace(tmp, final)
            return final
        except DownloadError:
            raise  # a checksum mismatch will not fix itself on retry
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500:
                raise DownloadError(f"{source.filename}: {source.url} returned {exc}") from exc
            last_error = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        finally:
            tmp.unlink(missing_ok=True)
        if attempt < attempts:
            delay = 2.0 * attempt
            print(f"  retry    {source.filename}: {last_error} (again in {delay:.0f} s)")
            time.sleep(delay)
    raise DownloadError(f"{source.filename}: download failed: {last_error}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download and verify Habit Guard's models.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify only; exit 1 on any problem")
    mode.add_argument("--force", action="store_true", help="download even if the files are valid")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="model folder")
    parser.add_argument("--timeout", type=float, default=60.0, help="network timeout in seconds")
    args = parser.parse_args(argv)

    failures = 0
    for source in SOURCES:
        status = "stale" if args.force else verify(source, args.dest)
        if status == "ok":
            size = (args.dest / source.filename).stat().st_size
            print(f"  ok       {source.filename} ({size / 1024 / 1024:.1f} MiB, sha256 verified)")
            continue
        if args.check:
            print(f"  {status:<8} {source.filename}  (run scripts/fetch_models.py to fix)")
            failures += 1
            continue
        print(f"  fetch    {source.filename} [{source.license}] from {source.url}")
        try:
            download(source, args.dest, timeout=args.timeout)
        except DownloadError as exc:
            print(f"  FAILED   {exc}", file=sys.stderr)
            failures += 1
            continue
        print(f"  ok       {source.filename} (verified)")
    if failures:
        print(f"{failures} model(s) missing or invalid in {args.dest}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
