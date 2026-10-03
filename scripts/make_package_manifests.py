"""Write the package-manager manifests of a release: Scoop, Homebrew, AUR and winget.

Usage:
    python scripts/make_package_manifests.py --version 0.1.0 --sums SHA256SUMS.txt
    python scripts/make_package_manifests.py --version 0.1.0 --sums SHA256SUMS.txt --date 2026-10-02

The version and the SHA-256 of every package come from the release's ``SHA256SUMS.txt`` (so the
manifests describe exactly what was published). Four things are written:

* ``bucket/habit-guard.json``: the Scoop manifest (this repository is a Scoop bucket);
* ``Casks/habit-guard.rb``: the Homebrew cask (this repository is a Homebrew tap);
* ``packaging/aur/habit-guard-bin/PKGBUILD`` and ``.SRCINFO``: for the Arch User Repository;
* ``winget/manifests/b/BugraSikel/HabitGuard/<version>/``: the winget manifests, in the layout of
  the winget-pkgs repository (not committed: they are submitted there, see
  docs/package-managers.md).

The first three are committed to the repository by ``.github/workflows/packages.yml`` after each
release. Nothing here talks to the network.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "packaging" / "templates"

REPO = "bugraskl/habit-guard"
RELEASES = f"https://github.com/{REPO}/releases/download"
HOMEPAGE = "https://bugraskl.github.io/habit-guard/"
DESCRIPTION = "Catches nail biting, mustache and hair pulling and face touching through your webcam"
PACKAGE_ID = "BugraSikel.HabitGuard"

#: The release assets the manifests point at, by the name each one has for a version.
ASSET_NAMES = {
    "WIN_SETUP": "HabitGuard-{v}-windows-x64-setup.exe",
    "WIN_ZIP": "HabitGuard-{v}-windows-x64-portable.zip",
    "MAC_DMG": "HabitGuard-{v}-macos-arm64.dmg",
    "LINUX_TAR": "HabitGuard-{v}-linux-x86_64.tar.gz",
}
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+([.\-+][0-9A-Za-z.\-+]*)?$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
PLACEHOLDER = re.compile(r"@([A-Z0-9_]+)@")

WINGET_FILES = {
    "winget.version.yaml.in": f"{PACKAGE_ID}.yaml",
    "winget.installer.yaml.in": f"{PACKAGE_ID}.installer.yaml",
    "winget.locale.en-US.yaml.in": f"{PACKAGE_ID}.locale.en-US.yaml",
    "winget.locale.tr-TR.yaml.in": f"{PACKAGE_ID}.locale.tr-TR.yaml",
}


def read_sums(text: str) -> dict[str, str]:
    """``{file name: lower-case SHA-256}`` from the text of a ``SHA256SUMS.txt``."""
    sums: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2:
            continue
        digest, name = parts[0].lower(), parts[1].lstrip("*").strip()
        if SHA256.match(digest):
            sums[name] = digest
    return sums


def asset_urls_and_hashes(version: str, sums: dict[str, str]) -> dict[str, str]:
    """The placeholder values for the assets of ``version``; ``SystemExit`` when one is missing."""
    values: dict[str, str] = {}
    for key, pattern in ASSET_NAMES.items():
        name = pattern.format(v=version)
        digest = sums.get(name)
        if digest is None:
            raise SystemExit(f"make_package_manifests: {name} is not in the checksums file")
        values[f"{key}_URL"] = f"{RELEASES}/v{version}/{name}"
        values[f"{key}_SHA256"] = digest
    return values


def render(template: str, values: dict[str, str]) -> str:
    def substitute(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise SystemExit(f"make_package_manifests: unknown placeholder @{key}@")
        return values[key]

    return PLACEHOLDER.sub(substitute, template)


def template_text(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def scoop_manifest(version: str, values: dict[str, str]) -> str:
    """The Scoop manifest: the portable ZIP, a ``habit-guard`` command and a Start menu entry."""
    manifest = {
        "version": version,
        "description": DESCRIPTION,
        "homepage": HOMEPAGE,
        "license": "MIT",
        "notes": [
            "Habit Guard is not code-signed yet: Windows SmartScreen may warn on the first start.",
            "Start it from the Start menu (Habit Guard) or run: HabitGuard.exe",
            "The command 'habit-guard' (doctor, stats, ctl ...) is on your PATH.",
        ],
        "architecture": {
            "64bit": {
                "url": values["WIN_ZIP_URL"],
                "hash": values["WIN_ZIP_SHA256"],
            }
        },
        "extract_dir": "HabitGuard",
        "bin": [["habit-guard-cli.exe", "habit-guard"]],
        "shortcuts": [["HabitGuard.exe", "Habit Guard"]],
        "checkver": {"github": f"https://github.com/{REPO}"},
        "autoupdate": {
            "architecture": {
                "64bit": {
                    "url": f"{RELEASES}/v$version/HabitGuard-$version-windows-x64-portable.zip",
                }
            },
            "hash": {"url": f"{RELEASES}/v$version/SHA256SUMS.txt"},
        },
    }
    return json.dumps(manifest, indent=4, ensure_ascii=False) + "\n"


def winget_files(version: str, values: dict[str, str], date: str | None) -> dict[str, str]:
    """``{file name: text}`` of the four winget manifest files."""
    winget_values = {
        **values,
        "VERSION": version,
        "WIN_SETUP_SHA256": values["WIN_SETUP_SHA256"].upper(),
        "RELEASE_DATE_LINE": f"ReleaseDate: {date}\n" if date else "",
    }
    return {
        target: render(template_text(source), winget_values)
        for source, target in WINGET_FILES.items()
    }


def build(version: str, sums: dict[str, str], date: str | None = None) -> dict[Path, str]:
    """Every file to write, by path relative to the repository root."""
    if not VERSION_PATTERN.match(version):
        raise SystemExit(f"make_package_manifests: {version!r} is not a version number")
    if date is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise SystemExit(f"make_package_manifests: --date must be YYYY-MM-DD, not {date!r}")
    values = asset_urls_and_hashes(version, sums)
    common = {**values, "VERSION": version}
    files: dict[Path, str] = {
        Path("bucket/habit-guard.json"): scoop_manifest(version, values),
        Path("Casks/habit-guard.rb"): render(template_text("cask.rb.in"), common),
        Path("packaging/aur/habit-guard-bin/PKGBUILD"): render(
            template_text("PKGBUILD.in"), common
        ),
        Path("packaging/aur/habit-guard-bin/.SRCINFO"): render(template_text("SRCINFO.in"), common),
    }
    folder = Path("winget/manifests/b/BugraSikel/HabitGuard") / version
    for name, text in winget_files(version, values, date).items():
        files[folder / name] = text
    return files


def write(files: dict[Path, str], root: Path) -> list[Path]:
    written: list[Path] = []
    for relative, text in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
        written.append(target)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--version", required=True, help="the release version, without the v")
    parser.add_argument("--sums", required=True, type=Path, help="the release's SHA256SUMS.txt")
    parser.add_argument("--date", help="the release date, YYYY-MM-DD (for the winget manifest)")
    parser.add_argument("--root", type=Path, default=ROOT, help="where to write (default: repo)")
    args = parser.parse_args(argv)
    sums = read_sums(args.sums.read_text(encoding="utf-8"))
    files = build(args.version.removeprefix("v"), sums, args.date)
    for path in write(files, args.root):
        print(f"wrote {path.relative_to(args.root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
