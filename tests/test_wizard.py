"""The first-run setup wizard, its camera check and how the application uses it."""

from __future__ import annotations

import numpy as np
import pytest

from conftest import make_face, make_hand
from habit_guard import control, i18n, paths
from habit_guard.alerts.manager import AlertManager
from habit_guard.config import Settings
from habit_guard.types import BUILT_IN_HABITS, Habit, Observation

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from habit_guard.app import Controller
from habit_guard.ui.preview import PreviewWindow
from habit_guard.ui.wizard import (
    BAD,
    OK,
    PAGE_ALERTS,
    PAGE_CAMERA,
    PAGE_DONE,
    PAGE_HABITS,
    PAGE_WELCOME,
    PENDING,
    SetupWizard,
)


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    existing = QApplication.instance()
    return existing if isinstance(existing, QApplication) else QApplication([])


def picture(level: int) -> np.ndarray:
    return np.full((480, 640, 3), level, dtype=np.uint8)


def observation(
    level: int | None = 130, *, with_face: bool = True, hands: int = 0, center=(320.0, 200.0)
) -> Observation:  # type: ignore[no-untyped-def]
    return Observation(
        ts=0.0,
        face=make_face(center=center) if with_face else None,
        hands=tuple(make_hand(face_u_v=(0.0, 1.3)) for _ in range(hands)),
        frame_size=(640, 480),
        frame=picture(level) if level is not None else None,
    )


def look(wizard: SetupWizard, obs: Observation, times: int = 6) -> None:
    for _ in range(times):
        wizard.show_observation(obs)


def to_page(wizard: SetupWizard, page: int) -> None:
    while wizard.page() < page:
        wizard.next.click()


# ------------------------------------------------------------------------------ pages
def test_the_wizard_walks_through_five_pages(qapp: QApplication) -> None:
    wizard = SetupWizard(Settings())
    assert wizard.page() == PAGE_WELCOME
    assert not wizard.back.isEnabled()
    assert not wizard.next.isHidden()
    assert wizard.finish.isHidden()
    seen = [wizard.page()]
    while wizard.page() < PAGE_DONE:
        wizard.next.click()
        seen.append(wizard.page())
    assert seen == [0, 1, 2, 3, 4]
    assert wizard.next.isHidden()
    assert not wizard.finish.isHidden()
    assert wizard.skip.isHidden()  # nothing left to skip
    assert wizard.step_label.text() == "Step 5 of 5"
    wizard.back.click()
    assert wizard.page() == PAGE_ALERTS
    assert wizard.back.isEnabled()
    assert wizard.finish.isHidden()


def test_every_page_draws_in_both_languages(qapp: QApplication) -> None:
    for language in ("en", "tr"):
        i18n.set_language(language)
        wizard = SetupWizard(Settings())
        wizard.show()
        for page in range(PAGE_DONE + 1):
            while wizard.page() < page:
                wizard.next.click()
            qapp.processEvents()
            assert not wizard.grab().isNull()
        assert wizard.windowTitle() == i18n.tr("wizard.title")
        wizard.close()
    i18n.set_language("en")


def test_the_wizard_has_texts_for_every_page_and_quality_advice_in_both_languages() -> None:
    keys = [k for k in i18n.all_keys() if k.startswith(("wizard.", "quality."))]
    assert len(keys) > 35
    assert i18n.missing_translations() == []


# ----------------------------------------------------------------------- the result
def test_an_untouched_wizard_returns_the_settings_with_setup_marked_done(
    qapp: QApplication,
) -> None:
    assert SetupWizard(Settings()).result_settings() == Settings(onboarded=True)


def test_the_chosen_habits_and_alarms_are_returned(qapp: QApplication) -> None:
    wizard = SetupWizard(Settings())
    wizard.habit_boxes[Habit.NAIL_BITING].setChecked(False)
    wizard.habit_boxes[Habit.HAIR_PULLING].setChecked(True)
    wizard.sound.setChecked(False)
    wizard.speech.setChecked(True)
    wizard.curtain.setChecked(False)
    wizard.notification.setChecked(False)
    wizard.volume.setValue(40)
    wizard.camera.setValue(2)
    result = wizard.result_settings()
    assert not result.habit(Habit.NAIL_BITING).enabled
    assert result.habit(Habit.HAIR_PULLING).enabled
    assert result.habit(Habit.MUSTACHE).enabled  # untouched
    assert (result.alerts.sound, result.alerts.speech) == (False, True)
    assert (result.alerts.curtain, result.alerts.notification) == (False, False)
    assert result.alerts.volume == pytest.approx(0.4)
    assert result.camera_index == 2
    assert result.onboarded


def test_the_wizard_only_offers_the_built_in_habits(qapp: QApplication) -> None:
    assert tuple(SetupWizard(Settings()).habit_boxes) == BUILT_IN_HABITS


def test_finishing_applies_once_and_closes(qapp: QApplication) -> None:
    wizard = SetupWizard(Settings())
    applied: list[Settings] = []
    wizard.applied.connect(applied.append)
    to_page(wizard, PAGE_DONE)
    wizard.finish.click()
    assert len(applied) == 1
    assert applied[0].onboarded
    wizard.close()  # closing afterwards must not apply a second time
    assert len(applied) == 1


def test_skipping_keeps_the_old_settings_and_only_marks_setup_as_shown(qapp: QApplication) -> None:
    original = Settings()
    wizard = SetupWizard(original)
    applied: list[Settings] = []
    wizard.applied.connect(applied.append)
    wizard.habit_boxes[Habit.NAIL_BITING].setChecked(False)  # a change that must be dropped
    wizard.skip.click()
    assert len(applied) == 1
    assert applied[0] == Settings(onboarded=True)
    assert applied[0].habit(Habit.NAIL_BITING).enabled
    wizard.close()
    assert len(applied) == 1


def test_closing_the_window_counts_as_skipping(qapp: QApplication) -> None:
    wizard = SetupWizard(Settings())
    applied: list[Settings] = []
    wizard.applied.connect(applied.append)
    wizard.show()
    wizard.close()
    assert [s.onboarded for s in applied] == [True]


def test_the_last_page_names_what_will_be_watched(qapp: QApplication) -> None:
    wizard = SetupWizard(Settings())
    to_page(wizard, PAGE_DONE)
    assert "Nail and finger biting" in wizard.summary.text()
    assert "Mustache" in wizard.summary.text()
    wizard.back.click()
    wizard.back.click()
    for box in wizard.habit_boxes.values():
        box.setChecked(False)
    to_page(wizard, PAGE_DONE)
    assert wizard.summary.text() == i18n.tr("wizard.done.none")


def test_the_test_button_asks_for_the_alarm_as_the_wizard_has_it(qapp: QApplication) -> None:
    wizard = SetupWizard(Settings())
    wizard.sound.setChecked(False)
    asked: list[Settings] = []
    wizard.test_requested.connect(asked.append)
    to_page(wizard, PAGE_ALERTS)
    tests = [
        b
        for b in wizard.findChildren(type(wizard.skip))
        if b.text() == i18n.tr("settings.alerts.test")
    ]
    assert len(tests) == 1
    tests[0].click()
    assert len(asked) == 1
    assert not asked[0].alerts.sound


# ---------------------------------------------------------------------- camera check
def test_the_camera_page_ignores_pictures_on_the_other_pages(qapp: QApplication) -> None:
    wizard = SetupWizard(Settings())
    look(wizard, observation(130))
    assert all(c.state == PENDING for c in wizard.checks.values())
    to_page(wizard, PAGE_HABITS)
    look(wizard, observation(130))
    assert all(c.state == PENDING for c in wizard.checks.values())


def test_a_good_setup_ticks_every_line_once_a_hand_was_seen(qapp: QApplication) -> None:
    wizard = SetupWizard(Settings())
    to_page(wizard, PAGE_CAMERA)
    look(wizard, observation(130))
    states = {name: c.state for name, c in wizard.checks.items()}
    assert states == {"face": OK, "light": OK, "distance": OK, "room": OK, "hands": PENDING}
    assert wizard.advice.text() == i18n.tr("wizard.camera.raise_hand")
    look(wizard, observation(130, hands=1), times=1)
    assert wizard.checks["hands"].state == OK
    assert wizard.advice.text() == i18n.tr("wizard.camera.all_good")
    look(wizard, observation(130), times=8)  # the hand goes away: it stays ticked
    assert wizard.checks["hands"].state == OK


def test_a_dark_picture_fails_the_light_line_and_says_what_to_do(qapp: QApplication) -> None:
    wizard = SetupWizard(Settings())
    to_page(wizard, PAGE_CAMERA)
    look(wizard, observation(15))
    assert wizard.checks["face"].state == OK
    assert wizard.checks["light"].state == BAD
    assert wizard.checks["distance"].state == OK
    assert wizard.advice.text() == i18n.tr("quality.too_dark")


def test_a_face_against_the_edge_fails_the_room_line(qapp: QApplication) -> None:
    wizard = SetupWizard(Settings())
    to_page(wizard, PAGE_CAMERA)
    look(wizard, observation(130, center=(90.0, 200.0)))
    assert wizard.checks["room"].state == BAD
    assert wizard.advice.text() == i18n.tr("quality.no_room")


def test_without_a_face_only_the_face_line_is_marked(qapp: QApplication) -> None:
    wizard = SetupWizard(Settings())
    to_page(wizard, PAGE_CAMERA)
    look(wizard, observation(130, with_face=False))
    assert wizard.checks["face"].state == BAD
    assert wizard.checks["light"].state == PENDING
    assert wizard.advice.text() == i18n.tr("quality.no_face")


def test_the_picture_is_drawn_on_the_camera_page(qapp: QApplication) -> None:
    wizard = SetupWizard(Settings())
    to_page(wizard, PAGE_CAMERA)
    wizard.show()
    look(wizard, observation(130, hands=1), times=1)
    assert not wizard.canvas.grab().isNull()
    wizard.close()


def test_changing_the_camera_number_asks_for_that_camera_and_starts_the_check_over(
    qapp: QApplication,
) -> None:
    wizard = SetupWizard(Settings())
    to_page(wizard, PAGE_CAMERA)
    look(wizard, observation(130, hands=1))
    asked: list[tuple[int, str]] = []
    wizard.camera_requested.connect(lambda i, a: asked.append((i, a)))
    wizard.camera.setValue(1)
    assert asked == [(1, "auto")]
    assert all(c.state == PENDING for c in wizard.checks.values())


def test_a_camera_that_shows_nothing_gets_a_hint(qapp: QApplication) -> None:
    wizard = SetupWizard(Settings())
    to_page(wizard, PAGE_CAMERA)
    wizard._hint_no_picture()  # what the timer does after a few seconds of silence
    assert wizard.advice.text() == i18n.tr("wizard.camera.busy")
    look(wizard, observation(130), times=1)
    wizard._hint_no_picture()  # a picture arrived: no hint
    assert wizard.advice.text() != i18n.tr("wizard.camera.busy")


# ------------------------------------------------------------------ the preview window
def test_the_preview_says_what_is_wrong_with_the_camera_set_up(qapp: QApplication) -> None:
    window = PreviewWindow()
    for _ in range(6):
        window.show_observation(observation(15), None, [], {})
    assert window.quality.text() == f"{i18n.tr('preview.quality')}: {i18n.tr('quality.too_dark')}"
    for _ in range(8):
        window.show_observation(observation(130), None, [], {})
    assert window.quality.text() == ""
    for _ in range(8):
        window.show_observation(observation(130, with_face=False), None, [], {})
    assert window.quality.text() == ""  # "no face" is already in the status line
    window.close()


# ------------------------------------------------------------------ the application
class Recorder:
    def __init__(self) -> None:
        self.events: list[str] = []

    def play(self, level, volume, custom_file=""):  # type: ignore[no-untyped-def]
        self.events.append("play")

    def say(self, text, language):  # type: ignore[no-untyped-def]
        return True

    def show(self, style, level, message):  # type: ignore[no-untyped-def]
        self.events.append("show")

    def hide(self):  # type: ignore[no-untyped-def]
        pass

    def stop(self):  # type: ignore[no-untyped-def]
        pass


def make_controller(settings: Settings | None = None) -> tuple[Controller, Recorder]:
    controller = Controller(settings or Settings(onboarded=True))
    rec = Recorder()
    controller.alerts = AlertManager(
        controller.settings, sound=rec, speech=rec, curtain=rec, notify=lambda t, b: None
    )
    return controller, rec


def bite(controller: Controller, start: float, stop: float) -> None:
    face = make_face()
    t = start
    while t < stop:
        controller._on_observation(
            Observation(
                ts=t,
                face=face,
                hands=(make_hand(face_u_v=(0.0, 1.3)),),
                hand_near=True,
                frame_size=(640, 480),
            )
        )
        t += 0.125


def test_the_wizard_opens_from_the_tray_and_keeps_the_camera_running(qapp: QApplication) -> None:
    controller, _ = make_controller()
    try:
        assert not controller._previewing
        controller.tray.wizard_requested.emit()
        assert controller._wizard is not None
        assert controller._previewing
        first = controller._wizard
        controller.open_wizard()  # a second request brings the same window forward
        assert controller._wizard is first
    finally:
        controller.shutdown()


def test_no_real_alarm_is_raised_while_the_wizard_is_open(qapp: QApplication) -> None:
    controller, rec = make_controller()
    try:
        controller.open_wizard()
        bite(controller, 0.0, 3.0)  # a hand at the mouth for longer than any dwell time
        assert rec.events == []
        assert controller.stats.total() == 0
        controller._wizard.skip.click()  # type: ignore[union-attr]
        bite(controller, 10.0, 12.0)
        assert "play" in rec.events  # the alarms work again afterwards
    finally:
        controller.shutdown()


def test_finishing_the_wizard_saves_the_choices_and_releases_the_camera_hold(
    qapp: QApplication,
) -> None:
    controller, _ = make_controller(Settings(onboarded=False))
    try:
        controller.open_wizard()
        wizard = controller._wizard
        assert wizard is not None
        wizard.habit_boxes[Habit.HAIR_PULLING].setChecked(True)
        to_page(wizard, PAGE_DONE)
        wizard.finish.click()
        assert controller._wizard is None
        assert not controller._previewing
        assert controller.settings.onboarded
        assert controller.settings.habit(Habit.HAIR_PULLING).enabled
        saved = Settings.load(paths.settings_path())
        assert saved.onboarded
        assert saved.habit(Habit.HAIR_PULLING).enabled
    finally:
        controller.shutdown()


def test_skipping_leaves_the_settings_alone_but_does_not_ask_again(qapp: QApplication) -> None:
    controller, _ = make_controller(Settings(onboarded=False))
    try:
        controller.open_wizard()
        controller._wizard.habit_boxes[Habit.NAIL_BITING].setChecked(False)  # type: ignore[union-attr]
        controller._wizard.skip.click()  # type: ignore[union-attr]
        assert controller.settings.onboarded
        assert controller.settings.habit(Habit.NAIL_BITING).enabled
        assert Settings.load(paths.settings_path()).onboarded
    finally:
        controller.shutdown()


def test_trying_another_camera_in_the_wizard_is_not_kept_unless_finished(
    qapp: QApplication,
) -> None:
    controller, _ = make_controller()
    seen: list[int] = []
    real = controller.pipeline.apply_settings
    controller.pipeline.apply_settings = lambda s: (seen.append(s.camera_index), real(s))[1]  # type: ignore[method-assign]
    try:
        controller.open_wizard()
        controller._wizard.camera.setValue(3)  # type: ignore[union-attr]
        assert seen[-1] == 3
        assert controller.settings.camera_index == 0  # nothing saved yet
        controller._wizard.skip.click()  # type: ignore[union-attr]
        assert seen[-1] == 0  # back to the saved camera
    finally:
        controller.shutdown()


def test_the_camera_chosen_in_the_wizard_is_saved_on_finish(qapp: QApplication) -> None:
    controller, _ = make_controller()
    try:
        controller.open_wizard()
        wizard = controller._wizard
        assert wizard is not None
        wizard.camera.setValue(2)
        to_page(wizard, PAGE_DONE)
        wizard.finish.click()
        assert controller.settings.camera_index == 2
    finally:
        controller.shutdown()


def test_pictures_reach_the_wizard_through_the_controller(qapp: QApplication) -> None:
    controller, _ = make_controller()
    try:
        controller.open_wizard()
        wizard = controller._wizard
        assert wizard is not None
        to_page(wizard, PAGE_CAMERA)
        for _ in range(6):
            controller._on_observation(observation(130, hands=1))
        assert wizard.checks["face"].state == OK
        assert wizard.checks["hands"].state == OK
    finally:
        controller.shutdown()


def test_a_first_run_opens_the_wizard_by_itself(qapp: QApplication) -> None:
    controller, _ = make_controller(Settings(onboarded=False))
    try:
        controller.start()
        QTest.qWait(700)
        assert controller._wizard is not None
        assert controller._settings_dialog is None  # no settings window any more on the first run
    finally:
        controller.shutdown()


def test_an_onboarded_start_opens_nothing(qapp: QApplication) -> None:
    controller, _ = make_controller(Settings(onboarded=True))
    try:
        controller.start()
        QTest.qWait(700)
        assert controller._wizard is None
        assert controller._settings_dialog is None
    finally:
        controller.shutdown()


def test_the_wizard_can_be_opened_with_ctl(qapp: QApplication) -> None:
    assert "wizard" in control.COMMANDS
    controller, _ = make_controller()
    try:
        control.send("wizard")
        controller.poll_control()
        assert controller._wizard is not None
    finally:
        controller.shutdown()
