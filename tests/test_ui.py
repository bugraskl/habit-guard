"""Smoke tests for the Qt side, run without a display (QT_QPA_PLATFORM=offscreen)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from conftest import make_face, make_hand

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication

from habit_guard import i18n, paths
from habit_guard.alerts.curtain import Curtain
from habit_guard.alerts.manager import AlertManager
from habit_guard.app import Controller, acquire_lock
from habit_guard.config import Settings
from habit_guard.stats import Stats
from habit_guard.types import Habit, Observation
from habit_guard.ui.icons import IconState, icon, pixmap
from habit_guard.ui.preview import PreviewWindow, to_qimage
from habit_guard.ui.settings_dialog import SettingsDialog
from habit_guard.ui.stats_dialog import StatsDialog
from habit_guard.ui.tray import Tray
from habit_guard.zones import FaceFrame, build_zones, evaluate


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    existing = QApplication.instance()
    return existing if isinstance(existing, QApplication) else QApplication([])


# ----------------------------------------------------------------------------- icons
def test_icons_render_for_every_state(qapp: QApplication) -> None:
    for state in IconState:
        assert not pixmap(state, 32).isNull()
        assert not icon(state).isNull()
    image = pixmap(IconState.ACTIVE, 64).toImage()
    assert image.pixelColor(32, 8).alpha() > 0  # the disc is painted


# -------------------------------------------------------------------------- settings
def test_settings_dialog_returns_what_the_controls_show(qapp: QApplication) -> None:
    settings = Settings()
    dialog = SettingsDialog(settings)
    assert dialog.result_settings() == Settings(onboarded=True)

    box = next(b for b in dialog._habit_boxes if b.habit is Habit.HAIR_PULLING)
    box.setChecked(True)
    box.dwell.setValue(2.5)
    box.scale.setValue(130)
    wide = next(b for b in dialog._habit_boxes if b.habit is Habit.MUSTACHE)
    assert wide.wide is not None
    wide.wide.setChecked(True)
    dialog.sound.setChecked(False)
    dialog.volume.setValue(30)
    dialog.speech.setChecked(True)
    dialog.speech_text.setText("  Stop  ")
    dialog.curtain_style.setCurrentIndex(dialog.curtain_style.findData("flash"))
    dialog.profile.setCurrentIndex(dialog.profile.findData("eco"))
    dialog.language.setCurrentIndex(dialog.language.findData("tr"))
    dialog.camera.setValue(2)

    out = dialog.result_settings()
    hair = out.habit(Habit.HAIR_PULLING)
    assert (hair.enabled, hair.dwell_s, hair.zone_scale) == (True, 2.5, 1.3)
    assert out.habit(Habit.MUSTACHE).wide_area is True
    assert out.alerts.sound is False
    assert out.alerts.volume == pytest.approx(0.3)
    assert (out.alerts.speech, out.alerts.speech_text) == (True, "Stop")
    assert out.alerts.curtain_style == "flash"
    assert (out.profile, out.language, out.camera_index, out.onboarded) == ("eco", "tr", 2, True)
    assert settings == Settings()  # the dialog never edits the caller's copy


def test_settings_dialog_emits_on_save(qapp: QApplication) -> None:
    dialog = SettingsDialog(Settings())
    received: list[Settings] = []
    dialog.applied.connect(received.append)
    dialog._save()
    assert len(received) == 1
    assert received[0].onboarded is True


def test_settings_dialog_opens_in_both_languages(qapp: QApplication) -> None:
    for code in ("en", "tr"):
        i18n.set_language(code)
        dialog = SettingsDialog(Settings())
        dialog.show()
        assert dialog.windowTitle() == i18n.tr("settings.title")
        assert not dialog.grab().isNull()
    i18n.set_language("en")


# ---------------------------------------------------------------------------- preview
def test_preview_draws_zones_hands_and_face(qapp: QApplication) -> None:
    face = make_face()
    hand = make_hand(face_u_v=(0.0, 1.3))
    frame = FaceFrame.from_face(face)
    assert frame is not None
    zones = build_zones(frame, Settings().zone_specs())
    hits = evaluate(frame, zones, [hand])
    picture = np.full((480, 640, 3), 90, np.uint8)
    obs = Observation(
        ts=1.0, face=face, hands=(hand,), hand_near=True, frame_size=(640, 480), frame=picture
    )
    window = PreviewWindow()
    window.resize(700, 600)
    window.show()
    window.show_observation(obs, frame, zones, hits)
    shot = window.grab().toImage()
    assert not shot.isNull()
    assert Habit.NAIL_BITING in {h for h, n in hits.items() if n}
    assert "Nail" in window.status.text() or "Tırnak" in window.status.text()
    closed: list[bool] = []
    window.closed.connect(lambda: closed.append(True))
    window.close()
    assert closed == [True]


def test_preview_without_a_picture_shows_the_waiting_text(qapp: QApplication) -> None:
    window = PreviewWindow()
    window.show()
    assert not window.grab().isNull()


def test_to_qimage_copies_the_picture() -> None:
    picture = np.zeros((10, 20, 3), np.uint8)
    picture[:, :, 2] = 255  # red in BGR
    image = to_qimage(picture)
    assert (image.width(), image.height()) == (20, 10)
    colour = image.pixelColor(3, 3)
    assert (colour.red(), colour.green(), colour.blue()) == (255, 0, 0)
    picture[:] = 0
    assert image.pixelColor(3, 3).red() == 255


# ---------------------------------------------------------------------------- stats
def test_stats_dialog_shows_the_numbers(qapp: QApplication) -> None:
    i18n.set_language("en")
    stats = Stats()
    today = date(2026, 10, 2)
    stats.record(Habit.NAIL_BITING, today)
    stats.record(Habit.NAIL_BITING, today)
    stats.add_watched(5.0)
    window = StatsDialog()
    window.show()
    window.refresh(stats, today)
    assert window._today.text() == "2"
    assert window._total.text() == "2"
    assert window._habit_labels[Habit.NAIL_BITING].text().startswith("2")
    assert not window.grab().isNull()


# ----------------------------------------------------------------------------- tray
def test_tray_updates_its_texts(qapp: QApplication) -> None:
    i18n.set_language("en")
    tray = Tray()
    tray.set_today(3)
    tray.set_status("Watching")
    tray.set_paused(True)
    assert tray._today_action.text() == "Today: 3 alarms"
    assert tray._pause_action.text() == "Resume tracking"
    i18n.set_language("tr")
    tray.retranslate()
    assert tray._today_action.text() == "Bugün: 3 alarm"
    assert tray._pause_action.text() == "İzlemeyi sürdür"
    i18n.set_language("en")


# --------------------------------------------------------------------------- curtain
def test_curtain_shows_and_hides_on_every_screen(qapp: QApplication) -> None:
    curtain = Curtain()
    curtain.show("dim", 2, "Hands down!")
    assert curtain._windows
    assert all(w.isVisible() for w in curtain._windows)
    curtain.show("flash", 3, "Hands down!")
    assert not curtain._windows[0].grab().isNull()
    curtain.hide()
    curtain.close()
    assert curtain._windows == []


# ------------------------------------------------------------------------ controller
class Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, int]] = []

    def play(self, level, volume, custom_file=""):  # type: ignore[no-untyped-def]
        self.events.append(("play", level))

    def say(self, text, language):  # type: ignore[no-untyped-def]
        return True

    def show(self, style, level, message):  # type: ignore[no-untyped-def]
        self.events.append(("show", level))

    def hide(self):  # type: ignore[no-untyped-def]
        self.events.append(("hide", 0))

    def stop(self):  # type: ignore[no-untyped-def]
        pass


def make_controller(qapp: QApplication) -> tuple[Controller, Recorder]:
    controller = Controller(Settings(onboarded=True))
    rec = Recorder()
    controller.alerts = AlertManager(
        controller.settings, sound=rec, speech=rec, curtain=rec, notify=lambda t, b: None
    )
    return controller, rec


def feed(controller: Controller, start: float, stop: float, hand_at) -> None:  # type: ignore[no-untyped-def]
    face = make_face()
    t = start
    while t < stop:
        hands = (make_hand(face_u_v=hand_at),) if hand_at is not None else ()
        controller._on_observation(
            Observation(ts=t, face=face, hands=hands, hand_near=bool(hands), frame_size=(640, 480))
        )
        t += 0.125


def test_controller_turns_a_biting_hand_into_one_counted_alarm(qapp: QApplication) -> None:
    controller, rec = make_controller(qapp)
    feed(controller, 0.0, 0.8, (0.0, 1.3))  # shorter than the dwell time
    assert rec.events == []
    feed(controller, 0.8, 1.6, (0.0, 1.3))
    assert ("show", 1) in rec.events
    assert ("play", 1) in rec.events
    assert controller.stats.count(date.today(), Habit.NAIL_BITING) == 1
    assert controller.engine.active_habits() == {Habit.NAIL_BITING}
    feed(controller, 1.6, 3.5, None)  # the hand comes down
    assert ("hide", 0) in rec.events
    assert controller.engine.active_habits() == set()
    assert controller.stats.count(date.today()) == 1  # still one alarm, not one per frame


def test_controller_ignores_habits_that_are_off(qapp: QApplication) -> None:
    controller, rec = make_controller(qapp)
    feed(controller, 0.0, 4.0, (0.0, -1.0))  # the forehead: hair pulling is off by default
    assert rec.events == []
    assert controller.stats.total() == 0


def test_controller_counts_watched_time_only_with_a_face(qapp: QApplication) -> None:
    controller, _ = make_controller(qapp)
    controller._on_observation(Observation(ts=0.0, face=make_face()))
    controller._on_observation(Observation(ts=2.0, face=make_face()))
    controller._on_observation(Observation(ts=4.0, face=None))
    assert controller.stats.watched_s == pytest.approx(2.0)


def test_pausing_releases_a_raised_alarm(qapp: QApplication) -> None:
    controller, rec = make_controller(qapp)
    feed(controller, 0.0, 1.5, (0.0, 1.3))
    assert controller.engine.active_habits()
    controller.toggle_pause()
    assert controller.engine.active_habits() == set()
    assert ("hide", 0) in rec.events
    assert controller.pipeline.paused


def test_applying_settings_saves_them_and_reconfigures_the_engine(qapp: QApplication) -> None:
    controller, _ = make_controller(qapp)
    new = Settings(onboarded=True)
    new.habit(Habit.NAIL_BITING).dwell_s = 3.3
    new.language = "tr"
    controller.apply_settings(new)
    assert controller.engine.dwell[Habit.NAIL_BITING] == 3.3
    assert Settings.load(paths.settings_path()).habit(Habit.NAIL_BITING).dwell_s == 3.3
    assert i18n.current_language() == "tr"
    i18n.set_language("en")


def test_resetting_stats_clears_the_file(qapp: QApplication) -> None:
    controller, _ = make_controller(qapp)
    feed(controller, 0.0, 1.5, (0.0, 1.3))
    controller._save_stats()
    assert Stats.load(paths.stats_path()).total() == 1
    controller._reset_stats()
    assert Stats.load(paths.stats_path()).total() == 0


def test_second_instance_cannot_take_the_lock(qapp: QApplication) -> None:
    first = acquire_lock()
    assert first is not None
    try:
        assert acquire_lock() is None
    finally:
        first.unlock()
    again = acquire_lock()
    assert again is not None
    again.unlock()


def test_timed_pause_resumes_by_itself(qapp: QApplication) -> None:
    controller, _ = make_controller(qapp)
    controller.pause_for(15)
    assert controller.pipeline.paused
    assert controller._resume_timer.isActive()
    assert controller._resume_at is not None
    assert "Paused until" in controller.tray._status
    controller._resume_timer.stop()
    controller._resume_after_pause()
    assert not controller.pipeline.paused
    assert controller._resume_at is None
    controller.toggle_pause()  # a manual pause cancels any timer
    assert controller.pipeline.paused
    assert not controller._resume_timer.isActive()
