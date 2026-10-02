"""The command line, the autostart files, the diagnostics report and the documentation."""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from habit_guard import __version__, autostart, cli, diagnostics, paths
from habit_guard.config import AlertConfig, HabitConfig, Settings
from habit_guard.stats import Stats
from habit_guard.types import Habit

ROOT = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------------------------ CLI
def test_version_flag(capsys) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--version"])
    assert exit_info.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_camera_source_parsing() -> None:
    assert cli._camera_source(None) is None
    assert cli._camera_source("2") == 2
    assert cli._camera_source("clip.mp4") == "clip.mp4"


def test_camera_option_works_with_and_without_a_subcommand() -> None:
    parser = cli.build_parser()
    assert parser.parse_args(["--camera", "1"]).camera == "1"
    assert parser.parse_args(["run", "--camera", "clip.mp4"]).camera == "clip.mp4"
    assert parser.parse_args(["bench", "--camera", "3", "--seconds", "5"]).camera == "3"
    assert parser.parse_args(["bench"]).seconds == 20.0


def test_stats_command_prints_the_counters(capsys) -> None:  # type: ignore[no-untyped-def]
    stats = Stats()
    from datetime import date

    stats.record(Habit.NAIL_BITING, date.today())
    stats.save(paths.stats_path())
    assert cli.main(["stats"]) == 0
    out = capsys.readouterr().out
    assert "today        1" in out
    assert "all time     1" in out


def test_reset_deletes_settings_and_statistics(capsys) -> None:  # type: ignore[no-untyped-def]
    Settings().save(paths.settings_path())
    Stats().save(paths.stats_path())
    assert cli.main(["reset", "--yes"]) == 0
    assert not paths.settings_path().exists()
    assert not paths.stats_path().exists()
    assert cli.main(["reset", "--yes"]) == 0
    assert "Nothing to reset" in capsys.readouterr().out


def test_config_dir_option_moves_the_files(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv(paths.HOME_ENV, raising=False)
    target = tmp_path / "portable"
    cli.main(["--config-dir", str(target), "stats"])
    assert paths.config_dir() == target


# ------------------------------------------------------------------------------ autostart
def test_launch_command_starts_the_module_or_the_gui_script() -> None:
    command = autostart.launch_command()
    assert command
    assert command[0]
    if len(command) > 1:
        assert command[1:] == ["-m", "habit_guard"]


def test_plist_and_desktop_entries_hold_the_command() -> None:
    command = ["/opt/habit guard/bin/python", "-m", "habit_guard"]
    plist = autostart.plist_text(command)
    assert "<string>/opt/habit guard/bin/python</string>" in plist
    assert "<key>RunAtLoad</key>" in plist
    desktop = autostart.desktop_text(command)
    assert "Exec='/opt/habit guard/bin/python' -m habit_guard" in desktop
    assert desktop.startswith("[Desktop Entry]")


def test_plist_escapes_xml() -> None:
    assert "&amp;" in autostart.plist_text(["/a&b/python"])


@pytest.mark.skipif(
    not __import__("sys").platform.startswith("linux"), reason="XDG autostart is Linux-only"
)
def test_autostart_enable_and_disable_on_linux(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert not autostart.is_enabled()
    autostart.enable()
    assert autostart.is_enabled()
    assert (tmp_path / "autostart" / autostart.DESKTOP_NAME).is_file()
    assert autostart.disable()
    assert not autostart.disable()


# ------------------------------------------------------------------------------ diagnostics
def test_doctor_report_lists_models_and_hides_the_home_folder() -> None:
    report = diagnostics.report()
    assert f"habit-guard      {__version__}" in report
    for name in ("face_detection", "palm_detection", "handpose_estimation"):
        assert re.search(rf"ok\s+{name}", report), name
    assert str(Path.home()) not in report


def test_short_path() -> None:
    home = Path.home()
    assert diagnostics.short_path(home / "x" / "y").startswith("~")
    assert str(home) not in diagnostics.short_path(home / "x" / "y")
    assert diagnostics.short_path("/somewhere/else") == "/somewhere/else"


# --------------------------------------------------------------------------------- docs
def _setting_keys() -> set[str]:
    keys = {f.name for f in dataclasses.fields(Settings)} - {"habits", "alerts"}
    keys |= {f.name for f in dataclasses.fields(HabitConfig)}
    keys |= {f.name for f in dataclasses.fields(AlertConfig)}
    keys |= {h.value for h in Habit}
    return keys


def test_every_setting_is_documented() -> None:
    text = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    missing = sorted(k for k in _setting_keys() if f"`{k}`" not in text)
    assert missing == []


def _markdown_files() -> list[Path]:
    skip = {".venv", ".git", "graft", ".claude"}
    return [p for p in ROOT.rglob("*.md") if not skip & set(p.relative_to(ROOT).parts)]


@pytest.mark.parametrize("path", _markdown_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_in_documents_resolve(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    broken = []
    for target in re.findall(r"\]\(([^)\s]+)\)", text) + re.findall(r'src="([^"]+)"', text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        file_part = target.split("#", 1)[0]
        if file_part and not (path.parent / file_part).exists():
            broken.append(target)
    assert broken == []


def test_both_readmes_have_the_same_structure() -> None:
    def headings(name: str) -> int:
        return len(re.findall(r"^## ", (ROOT / name).read_text(encoding="utf-8"), re.MULTILINE))

    assert headings("README.md") == headings("README.tr.md")


def test_changelog_mentions_the_current_version() -> None:
    assert f"## [{__version__}]" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
