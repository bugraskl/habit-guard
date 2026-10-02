#!/usr/bin/env python3
"""Write the platform icons (Windows .ico, macOS .icns, Linux .png) from ``assets/icon.png``.

``assets/icon.png`` is rendered from ``assets/icon.svg`` by ``scripts/make_screenshots.py``. The
outputs are committed, and the build workflows run this script again so a fresh checkout always
packages icons that match the source picture.

Usage::

    python scripts/make_icons.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "assets" / "icon.png"
ICO = REPO_ROOT / "packaging" / "windows" / "habit-guard.ico"
ICNS = REPO_ROOT / "packaging" / "macos" / "habit-guard.icns"
PNG = REPO_ROOT / "packaging" / "linux" / "habit-guard.png"
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> int:
    from PIL import Image

    if not SOURCE.is_file():
        print(f"make_icons: {SOURCE} is missing; run scripts/make_screenshots.py", file=sys.stderr)
        return 1
    with Image.open(SOURCE) as source:
        image = source.convert("RGBA")
    for target in (ICO, ICNS, PNG):
        target.parent.mkdir(parents=True, exist_ok=True)
    image.save(ICO, sizes=ICO_SIZES)
    image.resize((1024, 1024), Image.Resampling.LANCZOS).save(ICNS)
    image.resize((512, 512), Image.Resampling.LANCZOS).save(PNG, optimize=True)
    for target in (ICO, ICNS, PNG):
        print(f"wrote {target.relative_to(REPO_ROOT)} ({target.stat().st_size / 1024:.0f} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
