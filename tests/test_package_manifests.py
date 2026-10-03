"""The package-manager manifests: what the generator writes, and that it matches the installers."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

from habit_guard import __version__

ROOT = Path(__file__).resolve().parents[1]


def load_generator():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "make_package_manifests", ROOT / "scripts" / "make_package_manifests.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_package_manifests"] = module
    spec.loader.exec_module(module)
    return module


gen = load_generator()

VERSION = "1.2.3"
SUMS = {
    gen.ASSET_NAMES[key].format(v=VERSION): f"{n}c" * 32  # 64 hex digits, never all numbers
    for n, key in enumerate(gen.ASSET_NAMES, start=1)
}
ISS = (ROOT / "packaging" / "windows" / "installer.iss").read_bytes().decode("utf-8-sig")
SPEC = (ROOT / "packaging" / "pyinstaller" / "habit-guard.spec").read_text(encoding="utf-8")


def iss_define(name: str) -> str:
    match = re.search(rf'^#define {name} "([^"]*)"', ISS, re.MULTILINE)
    assert match, name
    return match.group(1)


def iss_setup(name: str) -> str:
    match = re.search(rf"^{name}=(.*)$", ISS, re.MULTILINE)
    assert match, name
    return match.group(1).strip()


@pytest.fixture(scope="module")
def files() -> dict[Path, str]:
    return gen.build(VERSION, SUMS, "2026-10-05")


def text_of(files: dict[Path, str], suffix: str) -> str:
    matches = [text for path, text in files.items() if path.as_posix().endswith(suffix)]
    assert len(matches) == 1, suffix
    return matches[0]


# ----------------------------------------------------------------------------- the input
def test_checksum_files_are_read_in_both_common_layouts() -> None:
    digest = "a" * 64
    text = f"{digest}  one.zip\n{digest.upper()} *two.exe\nnot a hash  three\n\n{'b' * 63}  short\n"
    assert gen.read_sums(text) == {"one.zip": digest, "two.exe": digest}


def test_a_missing_asset_stops_the_build() -> None:
    incomplete = {k: v for k, v in SUMS.items() if not k.endswith(".dmg")}
    with pytest.raises(SystemExit, match=r"macos-arm64\.dmg"):
        gen.build(VERSION, incomplete)


@pytest.mark.parametrize("version", ["", "v1.2.3", "1.2", "latest", "1.2.3; rm -rf /"])
def test_a_version_that_is_not_one_is_refused(version: str) -> None:
    with pytest.raises(SystemExit):
        gen.build(version, SUMS)


def test_a_malformed_date_is_refused() -> None:
    with pytest.raises(SystemExit, match="YYYY-MM-DD"):
        gen.build(VERSION, SUMS, "5 October")


def test_an_unknown_placeholder_in_a_template_is_refused() -> None:
    with pytest.raises(SystemExit, match="NOPE"):
        gen.render("x @NOPE@ y", {"VERSION": "1"})


def test_every_placeholder_of_every_template_is_filled(files: dict[Path, str]) -> None:
    for path, text in files.items():
        assert not re.search(r"@[A-Z0-9_]+@", text), path


# ------------------------------------------------------------------------------- Scoop
def test_the_scoop_manifest_points_at_the_portable_zip(files: dict[Path, str]) -> None:
    manifest = json.loads(text_of(files, "bucket/habit-guard.json"))
    asset = f"HabitGuard-{VERSION}-windows-x64-portable.zip"
    url = manifest["architecture"]["64bit"]["url"]
    assert url == f"https://github.com/bugraskl/habit-guard/releases/download/v{VERSION}/{asset}"
    assert manifest["architecture"]["64bit"]["hash"] == SUMS[asset]
    assert manifest["version"] == VERSION
    assert manifest["license"] == "MIT"
    assert manifest["extract_dir"] == "HabitGuard"  # the folder the portable ZIP is made of
    assert manifest["bin"] == [["habit-guard-cli.exe", "habit-guard"]]
    assert manifest["shortcuts"] == [["HabitGuard.exe", "Habit Guard"]]


def test_scoop_can_find_new_versions_and_their_hashes_by_itself(files: dict[Path, str]) -> None:
    manifest = json.loads(text_of(files, "bucket/habit-guard.json"))
    assert manifest["checkver"] == {"github": "https://github.com/bugraskl/habit-guard"}
    auto = manifest["autoupdate"]
    assert auto["architecture"]["64bit"]["url"].endswith(
        "/v$version/HabitGuard-$version-windows-x64-portable.zip"
    )
    assert auto["hash"]["url"].endswith("/v$version/SHA256SUMS.txt")


def test_the_scoop_names_match_what_the_zip_really_contains() -> None:
    build = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    assert '7z a -tzip -mx=9 -bd "HabitGuard-$VERSION-windows-x64-portable.zip" HabitGuard' in build
    assert iss_define("AppExeName") == "HabitGuard.exe"
    assert iss_define("CliExeName") == "habit-guard-cli.exe"
    assert 'program("HabitGuard", console=False)' in SPEC  # the tray app
    assert 'program("habit-guard-cli", console=True)' in SPEC  # what the "habit-guard" shim runs
    assert 'COLLECT(gui, cli, a.binaries, a.datas, upx=False, name="HabitGuard")' in SPEC


# ------------------------------------------------------------------------------- winget
def winget(files: dict[Path, str], suffix: str) -> dict[str, object]:
    loaded = yaml.safe_load(text_of(files, suffix))
    assert isinstance(loaded, dict)
    return loaded


def test_the_winget_files_sit_in_the_layout_of_the_community_repository(
    files: dict[Path, str],
) -> None:
    folder = Path(f"winget/manifests/b/BugraSikel/HabitGuard/{VERSION}")
    names = sorted(p.name for p in files if folder in p.parents)
    assert names == [
        "BugraSikel.HabitGuard.installer.yaml",
        "BugraSikel.HabitGuard.locale.en-US.yaml",
        "BugraSikel.HabitGuard.locale.tr-TR.yaml",
        "BugraSikel.HabitGuard.yaml",
    ]


def test_all_winget_files_agree_on_the_package_and_the_schema_version(
    files: dict[Path, str],
) -> None:
    parts = [
        yaml.safe_load(text)
        for path, text in files.items()
        if path.as_posix().startswith("winget/")
    ]
    assert len(parts) == 4
    assert {p["PackageIdentifier"] for p in parts} == {"BugraSikel.HabitGuard"}
    assert {str(p["PackageVersion"]) for p in parts} == {VERSION}
    assert {p["ManifestVersion"] for p in parts} == {"1.12.0"}
    assert sorted(p["ManifestType"] for p in parts) == [
        "defaultLocale",
        "installer",
        "locale",
        "version",
    ]


def test_the_winget_installer_entry_describes_the_inno_setup(files: dict[Path, str]) -> None:
    installer = yaml.safe_load(text_of(files, "HabitGuard.installer.yaml"))
    entry = installer["Installers"][0]
    asset = f"HabitGuard-{VERSION}-windows-x64-setup.exe"
    assert entry["InstallerUrl"].endswith(f"/v{VERSION}/{asset}")
    assert entry["InstallerSha256"] == SUMS[asset].upper()
    assert entry["Architecture"] == "x64"
    assert installer["InstallerType"] == "inno"
    assert installer["Scope"] == "user"  # the installer is per user, no administrator rights
    assert str(installer["ReleaseDate"]) == "2026-10-05"


def test_winget_recognises_the_installed_program_by_the_innos_own_identity(
    files: dict[Path, str],
) -> None:
    installer = yaml.safe_load(text_of(files, "HabitGuard.installer.yaml"))
    entry = installer["Installers"][0]["AppsAndFeaturesEntries"][0]
    assert entry["ProductCode"] == "{" + iss_define("AppGuid") + "}_is1"
    assert entry["DisplayName"] == iss_define("AppName")
    assert entry["Publisher"] == iss_setup("AppPublisher")
    assert entry["DisplayVersion"] == VERSION
    assert installer["MinimumOSVersion"] == iss_setup("MinVersion") + ".0"


def test_the_release_date_is_only_written_when_it_is_known() -> None:
    without = gen.build(VERSION, SUMS)
    text = text_of(without, "HabitGuard.installer.yaml")
    assert "ReleaseDate" not in text
    yaml.safe_load(text)  # still valid


def test_the_winget_descriptions_fit_the_limits_and_the_turkish_one_is_turkish(
    files: dict[Path, str],
) -> None:
    english = yaml.safe_load(text_of(files, "locale.en-US.yaml"))
    turkish = yaml.safe_load(text_of(files, "locale.tr-TR.yaml"))
    assert english["License"] == "MIT"
    assert english["PackageName"] == iss_define("AppName")
    assert len(english["ShortDescription"]) <= 256
    assert len(turkish["ShortDescription"]) <= 256
    assert len(english["Tags"]) <= 16
    assert all(len(tag) <= 40 and " " not in tag for tag in english["Tags"] + turkish["Tags"])
    assert "webcam ile" in turkish["ShortDescription"]
    assert english["ReleaseNotesUrl"].endswith(f"/releases/tag/v{VERSION}")
    assert english["Moniker"] == "habit-guard"


# ----------------------------------------------------------------------------- Homebrew
def test_the_cask_installs_the_app_from_the_disk_image(files: dict[Path, str]) -> None:
    cask = text_of(files, "Casks/habit-guard.rb")
    asset = f"HabitGuard-{VERSION}-macos-arm64.dmg"
    assert f'version "{VERSION}"' in cask
    assert f'sha256 "{SUMS[asset]}"' in cask
    assert "HabitGuard-#{version}-macos-arm64.dmg" in cask
    assert "releases/download/v#{version}/" in cask
    assert 'app "Habit Guard.app"' in cask
    assert "depends_on arch: :arm64" in cask  # the only build there is is for Apple silicon


def test_the_cask_names_match_the_app_bundle_and_the_minimum_system(files: dict[Path, str]) -> None:
    cask = text_of(files, "Casks/habit-guard.rb")
    assert 'bundle_identifier="io.github.bugraskl.habit-guard"' in SPEC.replace(" ", "")
    assert "io.github.bugraskl.habit-guard.plist" in cask  # the LaunchAgent that autostart writes
    build = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    minimum = re.search(r'MACOS_MINIMUM: "(\d+)\.', build)
    assert minimum
    names = {13: "ventura", 14: "sonoma", 15: "sequoia", 26: "tahoe"}
    assert f"depends_on macos: :{names[int(minimum.group(1))]}\n" in cask


def test_the_cask_tells_about_the_missing_signature(files: dict[Path, str]) -> None:
    assert "not signed with an Apple Developer ID" in text_of(files, "Casks/habit-guard.rb")


# ------------------------------------------------------------------------------------ AUR
def pkgbuild_field(text: str, name: str) -> str:
    match = re.search(rf"^{name}=(.*)$", text, re.MULTILINE)
    assert match, name
    return match.group(1)


def srcinfo_values(text: str, key: str) -> list[str]:
    return re.findall(rf"^\t{key} = (.*)$", text, re.MULTILINE)


def test_the_pkgbuild_downloads_the_tarball_and_installs_what_the_tarball_contains(
    files: dict[Path, str],
) -> None:
    pkgbuild = text_of(files, "PKGBUILD")
    asset = f"HabitGuard-{VERSION}-linux-x86_64.tar.gz"
    assert pkgbuild_field(pkgbuild, "pkgver") == VERSION
    assert f"sha256sums=('{SUMS[asset]}')" in pkgbuild
    assert "HabitGuard-$pkgver-linux-x86_64.tar.gz" in pkgbuild
    script = (ROOT / "packaging" / "linux" / "build_appimage.sh").read_text(encoding="utf-8")
    for name in ("habit-guard.desktop", "habit-guard.png", "LICENSE"):
        assert f'"$WORK/tar/habit-guard/{name}"' in script  # the files the PKGBUILD installs
        assert name in pkgbuild
    assert "options=('!strip' '!debug')" in pkgbuild  # a PyInstaller bundle must not be stripped
    assert "arch=('x86_64')" in pkgbuild


def test_the_srcinfo_says_the_same_as_the_pkgbuild(files: dict[Path, str]) -> None:
    pkgbuild = text_of(files, "PKGBUILD")
    info = text_of(files, ".SRCINFO")
    assert srcinfo_values(info, "pkgver") == [VERSION]
    assert srcinfo_values(info, "pkgrel") == [pkgbuild_field(pkgbuild, "pkgrel")]
    assert srcinfo_values(info, "sha256sums") == re.findall(r"'([0-9a-f]{64})'", pkgbuild)
    depends = re.search(r"^depends=\((.*)\)$", pkgbuild, re.MULTILINE)
    assert depends
    assert srcinfo_values(info, "depends") == re.findall(r"'([^']+)'", depends.group(1))
    assert srcinfo_values(info, "options") == ["!strip", "!debug"]
    assert info.startswith("pkgbase = habit-guard-bin\n")
    assert info.rstrip().endswith("pkgname = habit-guard-bin")
    source = srcinfo_values(info, "source")[0]
    assert source.endswith(f"/v{VERSION}/HabitGuard-{VERSION}-linux-x86_64.tar.gz")


# ------------------------------------------------------------------------------ writing
def test_files_are_written_with_unix_line_endings_under_the_given_root(tmp_path: Path) -> None:
    sums = tmp_path / "SHA256SUMS.txt"
    sums.write_text("\n".join(f"{d}  {n}" for n, d in SUMS.items()) + "\n", encoding="utf-8")
    root = tmp_path / "out"
    assert gen.main(["--version", VERSION, "--sums", str(sums), "--root", str(root)]) == 0
    written = sorted(p for p in root.rglob("*") if p.is_file())
    assert len(written) == 8
    for path in written:
        assert b"\r" not in path.read_bytes(), path
    assert (root / "bucket" / "habit-guard.json").is_file()
    assert (root / "packaging" / "aur" / "habit-guard-bin" / ".SRCINFO").is_file()


# --------------------------------------------------------------- the committed manifests
def test_the_committed_manifests_agree_with_each_other_and_are_not_ahead_of_the_code() -> None:
    scoop = ROOT / "bucket" / "habit-guard.json"
    cask = ROOT / "Casks" / "habit-guard.rb"
    srcinfo = ROOT / "packaging" / "aur" / "habit-guard-bin" / ".SRCINFO"
    if not (scoop.is_file() and cask.is_file() and srcinfo.is_file()):
        pytest.skip("the manifests are written by the packages workflow after a release")
    manifest = json.loads(scoop.read_text(encoding="utf-8"))
    version = manifest["version"]
    assert f'version "{version}"' in cask.read_text(encoding="utf-8")
    assert srcinfo_values(srcinfo.read_text(encoding="utf-8"), "pkgver") == [version]
    assert re.fullmatch(r"[0-9a-f]{64}", manifest["architecture"]["64bit"]["hash"])
    parse = lambda v: tuple(int(x) for x in v.split("-")[0].split(".")[:3])  # noqa: E731
    assert parse(version) <= parse(__version__)


# ----------------------------------------------------------------------------- workflows
WORKFLOWS = ROOT / ".github" / "workflows"


def workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_the_packages_workflow_installs_the_release_with_each_package_manager() -> None:
    text = workflow("packages.yml")
    for job in ("manifests:", "winget-schema:", "scoop:", "homebrew:", "aur:"):
        assert f"\n  {job}\n" in text, job
    assert "scripts/make_package_manifests.py" in text
    assert "scoop install habit-guard/habit-guard" in text
    assert "brew install --cask bugraskl/habit-guard/habit-guard" in text
    assert "archlinux:base-devel" in text
    assert "packaging/aur/validate.sh" in text
    assert "check-jsonschema" in text
    assert "manifest.installer.1.12.0.json" in text  # the schema version the files declare
    assert "git add bucket Casks packaging/aur" in text
    assert (
        "winget/" not in text.split("git add")[1].split("\n")[0]
    )  # winget files are not committed


def test_every_action_in_the_packages_workflow_is_pinned_to_a_commit() -> None:
    for line in workflow("packages.yml").splitlines():
        match = re.search(r"uses:\s*(\S+)", line)
        if match:
            assert re.search(r"@[0-9a-f]{40}$", match.group(1)), line


def test_a_release_starts_the_packages_workflow_unless_it_is_a_pre_release() -> None:
    text = workflow("release.yml")
    assert "gh workflow run packages.yml" in text
    step = text.split("Update the package-manager manifests")[1]
    assert "needs.build.outputs.prerelease != 'true'" in step.split("run:")[0]


def test_windows_signing_is_optional_and_off_without_the_signpath_settings() -> None:
    text = workflow("build.yml")
    switch = text.split("SIGNPATH_ENABLED:")[1].split("\n")[0]
    for part in (
        "inputs.upload",
        "github.ref_type == 'tag'",
        "vars.SIGNPATH_ORGANIZATION_ID != ''",
    ):
        assert part in switch, part
    assert "secrets.SIGNPATH_API_TOKEN != '' }}" in text
    sign_steps = [
        block
        for block in text.split("\n      - name: ")[1:]
        if "SignPath" in block.splitlines()[0]
        or "for signing" in block.splitlines()[0]
        or "signed " in block.splitlines()[0]
    ]
    assert len(sign_steps) == 6  # upload, sign, put in place: for the programs and the installer
    for block in sign_steps:
        assert "if: ${{ env.SIGNPATH_ENABLED == 'true' }}" in block, block.splitlines()[0]
    assert re.search(r"SignPath/github-action-submit-signing-request@[0-9a-f]{40} # v3", text)
    assert "SIGNPATH_API_TOKEN" in workflow("release.yml")


def test_the_signed_files_are_checked_before_they_are_packaged() -> None:
    text = workflow("build.yml")
    assert text.count("Get-AuthenticodeSignature") == 2
    assert text.count("-ne 'Valid'") == 2
    # the programs are signed before the ZIP and the installer are made, the installer after it
    order = [
        text.index("Sign the program files (SignPath)"),
        text.index("Create the portable ZIP"),
        text.index("Build the installer"),
        text.index("Sign the installer (SignPath)"),
        text.index("Smoke-test the installer"),
    ]
    assert order == sorted(order)


def test_the_release_downloads_the_packages_by_name_never_everything() -> None:
    text = workflow("release.yml")
    assert (
        "merge-multiple" not in text
    )  # the unsigned files must not be able to replace signed ones
    for name in ("windows-x64", "macos-arm64", "linux-x86_64", "release-notes"):
        assert f"name: {name}\n" in text, name


def test_signing_can_be_rerun_waits_for_the_manual_approval_and_only_runs_for_tags() -> None:
    text = workflow("build.yml")
    assert text.count("overwrite: true") == 2  # the two unsigned uploads keep fixed names
    assert text.count("wait-for-completion-timeout-in-seconds: 3600") == 2
    assert "github.ref_type == 'tag'" in text.split("SIGNPATH_ENABLED:")[1].split("\n")[0]
