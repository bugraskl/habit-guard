"""The packaging: entry point, spec, installer, bundle check and release notes stay consistent."""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from types import ModuleType

import pytest

from habit_guard import __version__, autostart, paths

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


entry = load("hg_entry", ROOT / "packaging" / "pyinstaller" / "entry.py")
bundle_check = load("check_bundle", ROOT / "scripts" / "check_bundle.py")
notes_script = load("release_notes", ROOT / "scripts" / "release_notes.py")


def _find_bash() -> str | None:
    """A usable bash, as a full path, or ``None``.

    On Windows a bare ``bash`` handed to ``subprocess`` is looked up in System32 first, where it can
    be the stub of the Windows Subsystem for Linux, while ``shutil.which`` may find Git's bash. So
    the path that was tried is the path that is used.
    """
    found = shutil.which("bash")
    if found is None:
        return None
    try:
        result = subprocess.run(
            [found, "-c", "echo ok"], capture_output=True, text=True, timeout=20, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return found if result.returncode == 0 and result.stdout.strip() == "ok" else None


BASH = _find_bash()


SPEC = (ROOT / "packaging" / "pyinstaller" / "habit-guard.spec").read_text(encoding="utf-8")
ISS = (ROOT / "packaging" / "windows" / "installer.iss").read_bytes()


# ------------------------------------------------------------------------------ entry point
@pytest.mark.parametrize(
    ("path", "gui"),
    [
        ("C:\\Program Files\\Habit Guard\\HabitGuard.exe", True),
        ("C:\\Users\\x\\AppData\\Local\\Programs\\Habit Guard\\habitguard.EXE", True),
        ("/Applications/Habit Guard.app/Contents/MacOS/Habit Guard", True),
        ("C:\\Program Files\\Habit Guard\\habit-guard-cli.exe", False),
        ("C:\\Program Files\\Habit Guard\\habit-guard.exe", False),
        ("/Applications/Habit Guard.app/Contents/MacOS/habit-guard-cli", False),
        ("/usr/bin/habit-guard", False),
        ("python.exe", False),
    ],
)
def test_the_entry_point_tells_the_windowed_program_from_the_command_line_one(
    path: str, gui: bool
) -> None:
    assert entry._is_gui_executable(path) is gui


def test_the_spec_names_the_windowed_programs_the_entry_point_expects() -> None:
    gui_names = re.findall(r'program\("([^"]+)", console=False\)', SPEC)
    assert gui_names, "no windowed program in the spec"
    for name in gui_names:
        assert name.casefold() in entry._GUI_EXECUTABLES, name
    cli_names = re.findall(r'program\("([^"]+)", console=True\)', SPEC)
    assert "habit-guard-cli" in cli_names
    assert "habit-guard" in cli_names  # the Linux program serves both roles


def test_the_spec_ships_the_models_and_leaves_qt_network_out() -> None:
    assert "vision" in SPEC
    assert "models" in SPEC
    assert '"PySide6.QtNetwork"' in SPEC
    assert "LSUIElement" in SPEC
    assert "NSCameraUsageDescription" in SPEC


# --------------------------------------------------------------------------- the installer
def test_the_installer_script_is_utf8_with_a_bom_and_crlf() -> None:
    assert ISS.startswith(b"\xef\xbb\xbf")  # needed for the Turkish messages and the name
    assert b"\r\n" in ISS
    assert b"\n" not in ISS.replace(b"\r\n", b"")


def test_the_installer_agrees_with_the_app() -> None:
    from habit_guard.app import APP_USER_MODEL_ID

    text = ISS.decode("utf-8-sig")
    assert f'#define RunValueName "{autostart.RUN_VALUE}"' in text
    assert f'#define AppUserModelID "{APP_USER_MODEL_ID}"' in text
    assert f"{{localappdata}}\\{paths.APP_NAME}" in text  # the settings folder
    assert '#define AppExeName "HabitGuard.exe"' in text
    assert '#define CliExeName "habit-guard-cli.exe"' in text
    assert "ctl quit" in text
    assert "CtlNotRunning = 3" in text
    from habit_guard import control

    assert control.EXIT_NOT_RUNNING == 3


def test_the_installer_guid_is_not_the_one_of_another_project() -> None:
    text = ISS.decode("utf-8-sig")
    guid = re.search(r'#define AppGuid "([0-9A-F-]{36})"', text)
    assert guid is not None
    other = ROOT.parent / "eye-tracker" / "packaging" / "windows" / "installer.iss"
    if other.is_file():
        assert guid.group(1) not in other.read_bytes().decode("utf-8-sig")


def test_the_windows_installer_output_name_matches_the_release_workflow() -> None:
    text = ISS.decode("utf-8-sig")
    assert "OutputBaseFilename=HabitGuard-{#AppVersion}-windows-x64-setup" in text
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    assert "HabitGuard-$env:VERSION-windows-x64-setup.exe" in workflow


# ------------------------------------------------------------------------------ Linux, macOS
def test_linux_desktop_entry() -> None:
    text = (ROOT / "packaging" / "linux" / "habit-guard.desktop").read_text(encoding="utf-8")
    assert "Exec=habit-guard" in text
    assert "Icon=habit-guard" in text
    assert "Terminal=false" in text
    assert text.startswith("[Desktop Entry]")


@pytest.mark.skipif(BASH is None, reason="needs a working bash")
@pytest.mark.parametrize(
    "script",
    ["packaging/macos/make_dmg.sh", "packaging/linux/build_appimage.sh", "packaging/linux/AppRun"],
)
def test_shell_scripts_have_valid_syntax_and_unix_line_endings(script: str) -> None:
    path = ROOT / script
    assert b"\r" not in path.read_bytes(), "shell scripts need LF line endings"
    assert BASH is not None
    result = subprocess.run(
        [BASH, "-n", script], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_no_packaging_file_still_says_eye_tracker() -> None:
    for path in (ROOT / "packaging").rglob("*"):
        if path.is_file() and path.suffix in {".sh", ".iss", ".py", ".spec", ".desktop", ""}:
            text = path.read_bytes().decode("utf-8", errors="ignore").casefold()
            assert "eye tracker" not in text, path
            assert "eye_tracker" not in text, path
            assert "eye-tracker" not in text, path


# ------------------------------------------------------------------------------ autostart
def test_a_frozen_console_program_autostarts_the_windowed_one(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    gui = tmp_path / "HabitGuard.exe"
    cli = tmp_path / "habit-guard-cli.exe"
    gui.write_bytes(b"")
    cli.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.setattr(sys, "executable", str(cli))
    assert autostart.launch_command() == [str(gui)]
    monkeypatch.setattr(sys, "executable", str(gui))
    assert autostart.launch_command() == [str(gui)]


def test_the_installers_path_copy_of_the_console_program_autostarts_the_windowed_one(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    """The installer adds a copy of the console build as habit-guard.exe next to HabitGuard.exe."""
    gui = tmp_path / "HabitGuard.exe"
    copy = tmp_path / "habit-guard.exe"
    gui.write_bytes(b"")
    copy.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.setattr(sys, "executable", str(copy))
    assert autostart.launch_command() == [str(gui)]


def test_one_linux_program_serving_both_roles_autostarts_itself(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    program = tmp_path / "habit-guard"
    program.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.setattr(sys, "executable", str(program))
    assert autostart.launch_command() == [str(program)]


def test_autostart_and_the_entry_point_agree_on_which_programs_are_windowed() -> None:
    assert autostart._GUI_STEMS == entry._GUI_EXECUTABLES


def test_an_appimage_autostarts_itself_not_its_temporary_mount(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/tmp/.mount_abc123/usr/lib/habit-guard/habit-guard")
    monkeypatch.setenv("APPIMAGE", "/home/me/Apps/HabitGuard-0.1.0-linux-x86_64.AppImage")
    assert autostart.launch_command() == ["/home/me/Apps/HabitGuard-0.1.0-linux-x86_64.AppImage"]


# ------------------------------------------------------------------------------ bundle check
def make_bundle(root: Path, *, models: bool = True, licences: bool = True) -> Path:
    folder = root / "_internal" / "habit_guard" / "vision" / "models"
    folder.mkdir(parents=True)
    if models:
        for name in bundle_check.MODEL_FILES:
            (folder / name).write_bytes(b"model")
    if licences:
        (folder / "licenses").mkdir()
        for name in bundle_check.LICENCE_FILES:
            (folder / name).write_text("text", encoding="utf-8")
    (root / "HabitGuard.exe").write_bytes(b"x")
    return root


def test_a_complete_bundle_passes(tmp_path: Path) -> None:
    assert bundle_check.problems(make_bundle(tmp_path / "ok")) == []
    assert bundle_check.main([str(tmp_path / "ok")]) == 0


@pytest.mark.parametrize(
    "component",
    ["Qt6Network.dll", "QtNetwork.pyd", "Qt6WebEngineCore.dll", "mediapipe", "requests", "urllib3"],
)
def test_networking_and_telemetry_components_fail_the_bundle(
    tmp_path: Path, component: str
) -> None:
    bundle = make_bundle(tmp_path / "bad")
    target = bundle / "_internal" / component
    if "." in component:
        target.write_bytes(b"x")
    else:
        target.mkdir()
    found = bundle_check.problems(bundle)
    assert any("forbidden component" in line for line in found), found
    assert bundle_check.main([str(bundle)]) == 1


def test_missing_models_or_licences_fail_the_bundle(tmp_path: Path) -> None:
    no_models = bundle_check.problems(make_bundle(tmp_path / "a", models=False))
    assert any("palm_detection" in line for line in no_models)
    no_licences = bundle_check.problems(make_bundle(tmp_path / "b", licences=False))
    assert any("NOTICE.md" in line for line in no_licences)
    assert bundle_check.problems(tmp_path / "does-not-exist")


def test_a_bloated_bundle_fails(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    bundle = make_bundle(tmp_path / "big")
    monkeypatch.setattr(bundle_check, "MAX_BUNDLE_BYTES", 10)
    assert any("over the limit" in line for line in bundle_check.problems(bundle))


@pytest.mark.skipif(not (ROOT / "dist" / "HabitGuard").is_dir(), reason="no local build")
def test_the_local_windows_build_passes_the_bundle_check() -> None:
    assert bundle_check.problems(ROOT / "dist" / "HabitGuard") == []


# ----------------------------------------------------------------------------- release notes
def test_the_version_and_the_changelog_agree() -> None:
    assert notes_script.read_version(ROOT / "src" / "habit_guard" / "__init__.py") == __version__
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    section = notes_script.changelog_section(text, __version__)
    assert section
    assert "Watching for four habits" in section


def test_changelog_sections_end_at_the_next_heading_or_the_link_list() -> None:
    text = textwrap.dedent(
        """
        # Log

        ## [Unreleased]

        soon

        ## [1.2.0] - 2026-01-01

        new thing

        ### Added

        - a

        ## [1.1.0]

        old

        [1.2.0]: https://x
        """
    ).strip()
    assert notes_script.changelog_section(text, "1.2.0") == "new thing\n\n### Added\n\n- a"
    assert notes_script.changelog_section(text, "1.1.0") == "old"
    assert notes_script.changelog_section(text, "9.9.9") is None


@pytest.mark.parametrize(
    ("version", "numeric", "pre"),
    [
        ("0.1.0", "0.1.0", False),
        ("1.2", "1.2", False),
        ("0.2.0rc1", "0.2.0", True),
        ("1.0.0b2", "1.0.0", True),
    ],
)
def test_version_helpers(version: str, numeric: str, pre: bool) -> None:
    assert notes_script.numeric_version(version) == numeric
    assert notes_script.is_prerelease(version) is pre


def test_release_notes_name_every_download_and_the_signing_state() -> None:
    text = notes_script.notes("0.1.0", "Body.")
    assert text.startswith("Body.")
    for name in (
        "HabitGuard-0.1.0-windows-x64-setup.exe",
        "HabitGuard-0.1.0-windows-x64-portable.zip",
        "HabitGuard-0.1.0-macos-arm64.dmg",
        "HabitGuard-0.1.0-linux-x86_64.AppImage",
        "HabitGuard-0.1.0-linux-x86_64.tar.gz",
        "SHA256SUMS.txt",
    ):
        assert name in text
    assert "ad hoc" in text
    assert "ad hoc" not in notes_script.notes("0.1.0", "Body.", stable_signature=True)


def test_the_script_checks_the_tag_against_the_version(tmp_path: Path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "notes.md"
    monkeypatch.setenv("GITHUB_REF_TYPE", "tag")
    monkeypatch.setenv("GITHUB_REF_NAME", f"v{__version__}")
    assert notes_script.main(["--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert f"version={__version__}" in printed
    assert "prerelease=false" in printed
    assert out.read_text(encoding="utf-8").startswith("Watching") or out.exists()
    monkeypatch.setenv("GITHUB_REF_NAME", "v9.9.9")
    assert notes_script.main([]) == 1
    assert "does not match" in capsys.readouterr().out


def test_a_tag_build_needs_a_changelog_section(tmp_path: Path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## [Unreleased]\n", encoding="utf-8")
    monkeypatch.setenv("GITHUB_REF_TYPE", "tag")
    monkeypatch.setenv("GITHUB_REF_NAME", f"v{__version__}")
    assert notes_script.main(["--changelog", str(changelog)]) == 1
    assert "no '## [" in capsys.readouterr().out
    monkeypatch.delenv("GITHUB_REF_TYPE")  # an ordinary build only warns
    assert notes_script.main(["--changelog", str(changelog)]) == 0


# -------------------------------------------------------------------------------- workflows
def test_a_release_waits_for_the_tests_and_the_privacy_scan() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    verify = workflow[workflow.index("  verify:") : workflow.index("  build:")]
    assert "check_privacy.py" in verify
    assert "pytest" in verify
    build = workflow[workflow.index("  build:") : workflow.index("  release:")]
    assert "needs: verify" in build


def test_the_installer_leaves_the_autostart_entry_alone_only_in_a_silent_upgrade() -> None:
    text = ISS.decode("utf-8")
    assert "Result := (not IsUpgrade) or (not WizardSilent);" in text
    assert "IsUpgrade and (not WizardSilent) and (not WizardIsTaskSelected('startup'))" in text
