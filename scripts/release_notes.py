#!/usr/bin/env python3
"""Work out the version to build and write the release notes from CHANGELOG.md.

Used by the build workflow:

    python scripts/release_notes.py --out release-notes.md

It reads ``__version__``, checks that a tag (``GITHUB_REF_NAME`` for a tag build) is ``v<version>``
and that CHANGELOG.md has a ``## [<version>]`` section, writes the notes (that section, then the
download table and the checksum hint) and prints ``version=``, ``numeric=`` and ``prerelease=`` lines
for ``$GITHUB_OUTPUT``. A build that is not for a tag only warns about a missing section.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "bugraskl/habit-guard"


def read_version(init_file: Path) -> str:
    match = re.search(r'^__version__ = "([^"]+)"$', init_file.read_text(encoding="utf-8"), re.M)
    if match is None:
        raise SystemExit(f"cannot read __version__ from {init_file}")
    return match.group(1)


def changelog_section(text: str, version: str) -> str | None:
    """The body of ``## [version]`` in Keep a Changelog style, or ``None``.

    It ends at the next ``## `` heading or at the link definitions (``[x]: url``) at the bottom.
    """
    match = re.search(
        rf"^## \[{re.escape(version)}\][^\n]*\n(?P<body>.*?)(?=^## |^\[[^\]\n]+\]:|\Z)",
        text,
        re.M | re.S,
    )
    if match is None:
        return None
    return match.group("body").strip()


def numeric_version(version: str) -> str:
    """The leading ``X.Y.Z`` part: Windows file versions and CFBundleVersion must be numeric."""
    match = re.match(r"\d+(\.\d+){0,2}", version)
    if match is None:
        raise SystemExit(f"version {version!r} does not start with a number")
    return match.group(0)


def is_prerelease(version: str) -> bool:
    return re.search(r"[A-Za-z]", version) is not None


def notes(version: str, section: str, *, stable_signature: bool = False) -> str:
    docs = f"https://github.com/{REPO}/blob/main/docs"
    mac_note = (
        "The app is signed with a stable certificate, so macOS keeps the camera permission across updates."
        if stable_signature
        else "The app is signed ad hoc: macOS asks for the camera permission again after each update."
    )
    return f"""{section}

## Download

| System | File |
| --- | --- |
| **Windows** 10/11 x64 | `HabitGuard-{version}-windows-x64-setup.exe` (installer) or `HabitGuard-{version}-windows-x64-portable.zip` |
| **macOS** 14+ Apple silicon | `HabitGuard-{version}-macos-arm64.dmg` |
| **Linux** x86_64 | `HabitGuard-{version}-linux-x86_64.AppImage` or `HabitGuard-{version}-linux-x86_64.tar.gz` |

`SHA256SUMS.txt` lists the checksums; every file also has a build-provenance attestation
(`gh attestation verify <file> --repo {REPO}`).

**Builds are not code-signed yet.** Windows SmartScreen may warn: choose *More info*, then *Run
anyway*. On macOS, right-click the app and choose *Open* the first time. {mac_note} Intel Macs can
[run from source](https://github.com/{REPO}#install). More in the
[platform notes]({docs}/troubleshooting.md).

Habit Guard is alpha software: please report false alarms and misses in the
[issue tracker](https://github.com/{REPO}/issues/new/choose).
"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--out", type=Path, help="where to write the release notes")
    parser.add_argument("--init", type=Path, default=ROOT / "src" / "habit_guard" / "__init__.py")
    parser.add_argument("--changelog", type=Path, default=ROOT / "CHANGELOG.md")
    args = parser.parse_args(argv)

    version = read_version(args.init)
    is_tag = os.environ.get("GITHUB_REF_TYPE") == "tag"
    ref = os.environ.get("GITHUB_REF_NAME", "")
    if is_tag and ref != f"v{version}":
        print(f"::error::tag {ref} does not match __version__ {version!r} (expected v{version})")
        return 1
    section = changelog_section(args.changelog.read_text(encoding="utf-8"), version)
    if section is None:
        level = "error" if is_tag else "warning"
        print(f"::{level}::CHANGELOG.md has no '## [{version}]' section")
        if is_tag:
            return 1
        section = f"Habit Guard {version}."
    stable = os.environ.get("MACOS_STABLE_SIGNATURE") == "true"
    if args.out:
        args.out.write_text(notes(version, section, stable_signature=stable), encoding="utf-8")
    outputs = [
        f"version={version}",
        f"numeric={numeric_version(version)}",
        f"prerelease={'true' if is_prerelease(version) else 'false'}",
    ]
    for line in outputs:
        print(line)
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:  # written here, so that annotations printed above never land in it
        with open(github_output, "a", encoding="utf-8") as handle:
            handle.write("\n".join(outputs) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
