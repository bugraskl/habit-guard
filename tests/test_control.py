"""``habit-guard ctl``: the command files, the status file, the CLI and the running app."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from habit_guard import cli, control

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication

from conftest import make_face, make_hand
from habit_guard.app import Controller
from habit_guard.config import Settings
from habit_guard.types import Observation


# ------------------------------------------------------------------------------ the files
def test_commands_are_queued_oldest_first_and_consumed() -> None:
    first = control.send("pause")
    second = control.send("resume")
    queued = control.pending()
    assert [command for _, command in queued] == ["pause", "resume"]
    assert [p for p, _ in queued] == [first, second]
    control.consume(first)
    assert [command for _, command in control.pending()] == ["resume"]


def test_unknown_commands_are_refused_when_sending_and_dropped_when_found() -> None:
    with pytest.raises(ValueError, match="unknown command"):
        control.send("format-the-disk")
    folder = control.control_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stray = folder / "1-1.cmd"
    stray.write_text("rm -rf /\n", encoding="utf-8")
    assert control.pending() == []
    assert not stray.exists()  # junk is removed, never acted on


def test_a_command_file_that_is_not_text_does_not_block_the_others() -> None:
    folder = control.control_dir()
    folder.mkdir(parents=True, exist_ok=True)
    junk = folder / "00000000000000000001-000000-1-aaaaaa.cmd"
    junk.write_bytes(b"\xff\xfe\x80 not utf-8")
    control.send("quit")
    assert [command for _, command in control.pending()] == ["quit"]
    assert not junk.exists()


def test_discard_pending_removes_every_waiting_command_and_leftover_part() -> None:
    folder = control.control_dir()
    folder.mkdir(parents=True, exist_ok=True)
    control.send("quit")
    control.send("pause")
    (folder / "1-1.cmd.part").write_text("quit\n", encoding="utf-8")
    control.discard_pending()
    assert list(folder.iterdir()) == []
    control.discard_pending()  # nothing left: not an error


def test_half_written_commands_are_not_seen() -> None:
    folder = control.control_dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "1-1.cmd.part").write_text("quit\n", encoding="utf-8")
    assert control.pending() == []


def test_status_roundtrip_staleness_and_removal() -> None:
    assert control.read_status() is None
    control.write_status({"state": "watching", "today": 4})
    status = control.read_status()
    assert status is not None
    assert (status["state"], status["today"], status["pid"]) == ("watching", 4, os.getpid())
    # A file left behind by a crashed app goes stale.
    old = {"state": "watching", "updated": time.time() - control.STALE_AFTER_S - 1}
    control.status_path().write_text(json.dumps(old), encoding="utf-8")
    assert control.read_status() is None
    control.write_status({"state": "paused"})
    control.clear_status()
    assert control.read_status() is None
    control.clear_status()  # nothing to remove: not an error


@pytest.mark.parametrize("content", ["{broken", "[]", '{"updated": "yesterday"}', ""])
def test_a_damaged_status_file_means_not_running(content: str) -> None:
    control.status_path().parent.mkdir(parents=True, exist_ok=True)
    control.status_path().write_text(content, encoding="utf-8")
    assert control.read_status() is None


def test_wait_until_stopped() -> None:
    assert control.wait_until_stopped(timeout=0.2)  # nothing running
    control.write_status({"state": "watching"})
    assert not control.wait_until_stopped(timeout=0.3, interval=0.05)  # still beating


# ------------------------------------------------------------------------------- the CLI
def test_ctl_without_a_running_app(capsys) -> None:  # type: ignore[no-untyped-def]
    assert cli.main(["ctl", "status"]) == control.EXIT_NOT_RUNNING
    assert "not running" in capsys.readouterr().out
    assert cli.main(["ctl", "pause"]) == control.EXIT_NOT_RUNNING
    assert control.pending() == []  # nothing is queued for an app that is not there


def test_ctl_status_and_commands_with_a_running_app(capsys) -> None:  # type: ignore[no-untyped-def]
    control.write_status({"version": "9.9", "state": "watching", "today": 2})
    assert cli.main(["ctl", "status"]) == 0
    assert "state watching" in capsys.readouterr().out
    assert cli.main(["ctl", "toggle"]) == 0
    assert [c for _, c in control.pending()] == ["toggle"]


def test_ctl_quit_waits_for_the_app_to_stop(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    control.write_status({"state": "watching"})
    assert cli.main(["ctl", "quit", "--timeout", "0.3"]) == 1  # the app does not react
    assert "did not quit" in capsys.readouterr().err
    monkeypatch.setattr(control, "wait_until_stopped", lambda timeout=10.0, interval=0.25: True)
    assert cli.main(["ctl", "quit"]) == 0


def test_ctl_rejects_unknown_actions() -> None:
    with pytest.raises(SystemExit):
        cli.main(["ctl", "explode"])


def test_selftest_passes_on_a_working_installation(capsys) -> None:  # type: ignore[no-untyped-def]
    assert cli.main(["selftest"]) == 0
    out = capsys.readouterr().out
    for name in ("models", "vision", "sound", "windows"):
        assert f"ok       {name}" in out
    assert "selftest passed" in out


def test_selftest_reports_a_missing_model(monkeypatch, capsys, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(cli.paths, "models_dir", lambda: tmp_path)
    assert cli.main(["selftest"]) == 1
    captured = capsys.readouterr()
    assert "FAILED   models" in captured.out
    assert "selftest failed" in captured.err


# ---------------------------------------------------------------------------- the running app
@pytest.fixture(scope="module")
def qapp() -> QApplication:
    existing = QApplication.instance()
    return existing if isinstance(existing, QApplication) else QApplication([])


def make_controller() -> Controller:
    return Controller(Settings(onboarded=True))


def test_the_app_publishes_its_state_and_carries_out_commands(qapp: QApplication) -> None:
    controller = make_controller()
    controller.start()
    try:
        status = control.read_status()
        assert status is not None
        assert status["state"] in {"starting", "watching", "no_camera", "paused"}

        control.send("pause")
        controller.poll_control()
        assert controller.pipeline.paused
        status = control.read_status()
        assert status is not None
        assert (status["paused"], status["state"]) == (True, "paused")

        control.send("resume")
        controller.poll_control()
        assert not controller.pipeline.paused

        control.send("toggle")
        controller.poll_control()
        assert controller.pipeline.paused
        assert control.pending() == []  # every command was consumed
    finally:
        controller.shutdown()
    assert control.read_status() is None  # a quit app leaves no heartbeat behind


def test_quit_through_ctl_stops_everything(qapp: QApplication) -> None:
    controller = make_controller()
    controller.start()
    control.send("pause")
    control.send("quit")
    control.send("resume")  # after the quit: never reached
    controller.poll_control()
    assert controller._closed
    assert control.read_status() is None
    assert control.pending() == []  # nothing queued behind the quit survives for the next run


def test_commands_left_by_an_earlier_run_are_not_carried_out(qapp: QApplication) -> None:
    control.send("quit")  # a double "ctl quit", or one sent just after a crash
    control.send("pause")
    controller = make_controller()
    try:
        assert control.pending() == []
        controller.poll_control()
        assert not controller._closed
        assert not controller.pipeline.paused
    finally:
        controller.shutdown()


def test_the_status_stays_until_the_camera_is_released_and_the_statistics_saved(
    qapp: QApplication, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    controller = make_controller()
    controller.start()
    seen: dict[str, bool] = {}
    stop = controller.pipeline.stop

    def stop_and_look() -> None:
        seen["status_during_stop"] = control.read_status() is not None
        stop()

    monkeypatch.setattr(controller.pipeline, "stop", stop_and_look)
    controller.shutdown()
    assert seen == {"status_during_stop": True}  # "ctl quit" waits for the end of all this
    assert control.read_status() is None


def test_opening_windows_and_the_test_alarm_by_command(qapp: QApplication) -> None:
    controller = make_controller()
    try:
        for command in ("settings", "preview", "stats", "test"):
            control.send(command)
        controller.poll_control()
        assert controller._settings_dialog is not None
        assert controller._previewing
        assert controller._stats_window is not None
    finally:
        controller.shutdown()


def test_the_status_reports_a_raised_alarm(qapp: QApplication) -> None:
    controller = make_controller()
    try:
        face = make_face()
        t = 0.0
        while t < 1.6:
            hand = make_hand(face_u_v=(0.0, 1.3))
            controller._on_observation(
                Observation(ts=t, face=face, hands=(hand,), hand_near=True, frame_size=(640, 480))
            )
            t += 0.125
        controller.write_status()
        status = control.read_status()
        assert status is not None
        assert status["alarm"] is True
        assert status["today"] >= 1
    finally:
        controller.shutdown()


def test_commands_sent_within_the_same_clock_tick_are_all_kept_in_order(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(control.time, "time_ns", lambda: 1_000_000_000)  # a coarse clock
    for command in ("pause", "resume", "toggle", "pause"):
        control.send(command)
    assert [c for _, c in control.pending()] == ["pause", "resume", "toggle", "pause"]
