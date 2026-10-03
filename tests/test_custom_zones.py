"""Zones the user draws: the geometry, the settings, the names, the editor and the whole alarm."""

from __future__ import annotations

import json
from datetime import date

import pytest

from conftest import make_face, make_hand
from habit_guard import i18n
from habit_guard.alerts.manager import AlertManager
from habit_guard.config import DEFAULT_CUSTOM_ZONES, NAME_MAX, CustomZone, Settings
from habit_guard.engine.decision import HabitEngine, Trigger
from habit_guard.types import BUILT_IN_HABITS, CUSTOM_HABITS, Habit, Observation
from habit_guard.zones import Ellipse, FaceFrame, ZoneSpec, build_zones, evaluate

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTabWidget

from habit_guard.app import Controller
from habit_guard.stats import Stats
from habit_guard.ui.custom_zones_tab import CustomZonesTab
from habit_guard.ui.settings_dialog import SettingsDialog
from habit_guard.ui.stats_dialog import StatsDialog
from habit_guard.ui.zone_editor import ZoneEditor


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    existing = QApplication.instance()
    return existing if isinstance(existing, QApplication) else QApplication([])


# ----------------------------------------------------------------------------- geometry
def frame_of_the_test_face() -> FaceFrame:
    frame = FaceFrame.from_face(make_face())
    assert frame is not None
    return frame


def counts_at(specs: dict[Habit, ZoneSpec], uv: tuple[float, float]) -> dict[Habit, int]:
    frame = frame_of_the_test_face()
    hand = make_hand(face_u_v=uv)
    return {h: n for h, n in evaluate(frame, build_zones(frame, specs), [hand]).items() if n}


def custom(shape: tuple[Ellipse, ...], **kwargs: object) -> ZoneSpec:
    return ZoneSpec(shape=shape, **kwargs)  # type: ignore[arg-type]


def test_the_habit_enum_separates_built_in_and_custom_ones() -> None:
    assert [h.is_custom for h in Habit] == [False] * 4 + [True] * 3
    assert tuple(Habit) == BUILT_IN_HABITS + CUSTOM_HABITS


def test_a_fingertip_in_a_custom_ellipse_counts_for_that_habit() -> None:
    specs = {Habit.CUSTOM_1: custom((Ellipse(1.3, 0.35, 0.3, 0.5),))}
    assert counts_at(specs, (1.3, 0.35)) == {Habit.CUSTOM_1: 5}
    assert counts_at(specs, (1.3, 1.5)) == {}


def test_a_custom_zone_without_a_shape_or_switched_off_watches_nothing() -> None:
    assert build_zones(frame_of_the_test_face(), {Habit.CUSTOM_1: ZoneSpec()}) == []
    off = custom((Ellipse(0.0, 0.0, 1.0, 1.0),), enabled=False)
    assert build_zones(frame_of_the_test_face(), {Habit.CUSTOM_1: off}) == []


def test_the_mirrored_shape_is_watched_on_both_sides() -> None:
    zone = CustomZone(cu=1.3, cv=0.35, rx=0.3, ry=0.5, mirror=True)
    specs = {Habit.CUSTOM_1: custom(zone.ellipses())}
    assert counts_at(specs, (1.3, 0.35)) == {Habit.CUSTOM_1: 5}
    assert counts_at(specs, (-1.3, 0.35)) == {Habit.CUSTOM_1: 5}


def test_a_shape_in_the_middle_is_not_doubled_by_mirroring() -> None:
    assert len(CustomZone(cu=0.0, mirror=True).ellipses()) == 1
    assert len(CustomZone(cu=0.04, mirror=True).ellipses()) == 1
    assert len(CustomZone(cu=0.5, mirror=True).ellipses()) == 2
    assert len(CustomZone(cu=0.5, mirror=False).ellipses()) == 1


def test_a_custom_zone_wins_over_the_built_in_zone_it_overlaps() -> None:
    mouth = (0.0, 1.3)
    built_in = {h: ZoneSpec() for h in BUILT_IN_HABITS}
    assert set(counts_at(built_in, mouth)) == {Habit.NAIL_BITING}
    over_the_mouth = custom((Ellipse(0.0, 1.3, 0.5, 0.4),))
    both = {**built_in, Habit.CUSTOM_2: over_the_mouth}
    assert set(counts_at(both, mouth)) == {Habit.CUSTOM_2}  # one movement, one alarm
    assert set(counts_at(both, (1.0, 0.2))) <= {
        Habit.FACE_TOUCH,
        Habit.HAIR_PULLING,
        Habit.MUSTACHE,
    }


def test_a_custom_zone_is_never_also_face_touching() -> None:
    specs = {
        Habit.FACE_TOUCH: ZoneSpec(),
        Habit.CUSTOM_1: custom((Ellipse(0.9, 0.9, 0.3, 0.3),)),
    }
    assert counts_at(specs, (0.9, 0.9)) == {Habit.CUSTOM_1: 5}
    assert Habit.FACE_TOUCH in counts_at(
        specs, (-0.9, 0.9)
    )  # elsewhere on the face it still counts


def test_an_earlier_custom_zone_wins_over_a_later_one() -> None:
    shape = (Ellipse(0.0, 2.5, 0.5, 0.5),)
    specs = {Habit.CUSTOM_1: custom(shape), Habit.CUSTOM_3: custom(shape)}
    assert counts_at(specs, (0.0, 2.5)) == {Habit.CUSTOM_1: 5}


def test_a_custom_zone_is_scaled_like_the_others() -> None:
    specs = {Habit.CUSTOM_1: custom((Ellipse(0.0, 2.5, 0.5, 0.5),), scale=2.0)}
    assert counts_at(specs, (0.0, 3.3)) == {Habit.CUSTOM_1: 5}


# ------------------------------------------------------------------------------ settings
def test_new_settings_start_with_three_switched_off_custom_zones() -> None:
    settings = Settings()
    assert set(settings.custom_zones) == {h.value for h in CUSTOM_HABITS}
    assert not any(settings.habit(h).enabled for h in CUSTOM_HABITS)
    specs = settings.zone_specs()
    assert all(specs[h].shape for h in CUSTOM_HABITS)
    assert all(specs[h].shape == () for h in BUILT_IN_HABITS)


def test_settings_survive_a_save_and_a_load(tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = Settings()
    settings.custom_zones["custom_2"] = CustomZone(
        name="lip biting", cu=0.0, cv=1.3, rx=0.45, ry=0.2, mirror=False
    )
    settings.habits["custom_2"].enabled = True
    settings.habits["custom_2"].dwell_s = 2.0
    path = tmp_path / "settings.json"
    settings.save(path)
    loaded = Settings.load(path)
    assert loaded == settings
    assert loaded.custom_names()[Habit.CUSTOM_2] == "lip biting"


def test_a_settings_file_from_before_custom_zones_gets_the_defaults(tmp_path) -> None:  # type: ignore[no-untyped-def]
    old = {"language": "tr", "habits": {"nail_biting": {"enabled": False, "dwell_s": 2.0}}}
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(old), encoding="utf-8")
    loaded = Settings.load(path)
    assert loaded.language == "tr"
    assert loaded.habit(Habit.NAIL_BITING).dwell_s == 2.0
    assert loaded.custom_zones == Settings().custom_zones
    assert not loaded.habit(Habit.CUSTOM_1).enabled


def test_damaged_custom_zone_values_fall_back_or_are_clamped() -> None:
    raw = {
        "custom_zones": {
            "custom_1": {"cu": 99, "cv": -99, "rx": 0, "ry": "wide", "mirror": "yes", "name": 7},
            "custom_2": "nonsense",
            "custom_3": {"name": "  neck \n\t scratching  "},
        }
    }
    zones = Settings.from_dict(raw).custom_zones
    first = zones["custom_1"]
    assert (first.cu, first.cv) == (3.0, -3.0)
    assert first.rx == 0.1  # clamped to the smallest allowed
    assert first.ry == DEFAULT_CUSTOM_ZONES[Habit.CUSTOM_1].ry  # not a number: the default
    assert first.mirror is DEFAULT_CUSTOM_ZONES[Habit.CUSTOM_1].mirror
    assert first.name == ""
    assert zones["custom_2"] == DEFAULT_CUSTOM_ZONES[Habit.CUSTOM_2]
    assert zones["custom_3"].name == "neck scratching"  # one tidy line


def test_a_long_name_is_cut_and_control_characters_are_dropped() -> None:
    raw = {"custom_zones": {"custom_1": {"name": "x" * 100 + "\x00\x07"}}}
    assert len(Settings.from_dict(raw).custom_zones["custom_1"].name) == NAME_MAX
    assert (
        Settings.from_dict({"custom_zones": {"custom_1": {"name": "a\x00b"}}})
        .custom_zones["custom_1"]
        .name
        == "a b"
    )


def test_enabling_a_custom_zone_makes_the_app_watch() -> None:
    settings = Settings()
    for h in BUILT_IN_HABITS:
        settings.habit(h).enabled = False
    assert not settings.any_habit_enabled()
    settings.habit(Habit.CUSTOM_3).enabled = True
    assert settings.any_habit_enabled()
    assert settings.dwell_map()[Habit.CUSTOM_3] == 1.5


# --------------------------------------------------------------------------------- names
def test_a_custom_zone_is_called_by_its_name_and_falls_back_to_its_number() -> None:
    assert i18n.habit_name(Habit.CUSTOM_1) == "Custom zone 1"
    i18n.set_custom_names({Habit.CUSTOM_1: "ear picking", Habit.CUSTOM_2: "  "})
    assert i18n.habit_name(Habit.CUSTOM_1) == "Ear picking"
    assert i18n.habit_short(Habit.CUSTOM_1) == "ear picking"
    assert i18n.habit_name(Habit.CUSTOM_2) == "Custom zone 2"  # blank: the default
    i18n.set_custom_names({})
    assert i18n.habit_name(Habit.CUSTOM_1) == "Custom zone 1"


def test_turkish_capitals_keep_their_dots() -> None:
    i18n.set_language("tr")
    assert i18n.upper_first("ısırma") == "Isırma"
    assert i18n.upper_first("iç dudak") == "İç dudak"
    assert i18n.upper_first("") == ""
    i18n.set_language("en")
    assert i18n.upper_first("ısırma") == "Isırma"
    assert i18n.upper_first("ear") == "Ear"


def test_the_notification_uses_the_name_the_user_gave() -> None:
    i18n.set_custom_names({Habit.CUSTOM_1: "ear picking"})
    sent: list[tuple[str, str]] = []

    class Quiet:
        def play(self, *a: object) -> None: ...
        def stop(self) -> None: ...
        def say(self, *a: object) -> bool:
            return True

        def show(self, *a: object) -> None: ...
        def hide(self) -> None: ...

    quiet = Quiet()
    manager = AlertManager(
        Settings(),
        sound=quiet,
        speech=quiet,
        curtain=quiet,
        notify=lambda t, b: sent.append((t, b)),
    )
    manager.fire(Habit.CUSTOM_1, 1, first=True)
    assert sent == [("Hands down!", "Ear picking detected")]


# --------------------------------------------------------------------------- the engine
def test_a_custom_habit_raises_an_alarm_after_its_own_dwell_time() -> None:
    settings = Settings()
    settings.habit(Habit.CUSTOM_1).enabled = True
    settings.habit(Habit.CUSTOM_1).dwell_s = 1.0
    engine = HabitEngine(settings.dwell_map(), settings.engine_settings())
    events = []
    t = 0.0
    while t < 1.5:
        events += engine.update(t, {Habit.CUSTOM_1: 5})
        t += 0.125
    assert [(e.habit, e.level) for e in events if isinstance(e, Trigger)][:1] == [
        (Habit.CUSTOM_1, 1)
    ]


# ---------------------------------------------------------------------------- the editor
def pixel(editor: ZoneEditor, u: float, v: float) -> QPoint:
    return editor.face_to_canvas(u, v).toPoint()


def editor_for(zone: CustomZone) -> ZoneEditor:
    editor = ZoneEditor()
    editor.resize(330, 450)
    editor.set_zone(zone, QColor(255, 90, 160))
    return editor


def test_the_editor_maps_face_units_to_pixels_and_back(qapp: QApplication) -> None:
    editor = editor_for(CustomZone())
    for u, v in ((0.0, 0.0), (1.3, 0.35), (-1.9, 3.0)):
        back = editor.canvas_to_face(QPointF(editor.face_to_canvas(u, v)))
        assert back == pytest.approx((u, v))
    assert editor.face_to_canvas(0.0, 1.0).y() > editor.face_to_canvas(0.0, 0.0).y()  # down is down


def test_dragging_inside_the_shape_moves_it(qapp: QApplication) -> None:
    zone = CustomZone(cu=0.0, cv=2.5, rx=0.6, ry=0.4)
    editor = editor_for(zone)
    changes: list[int] = []
    editor.changed.connect(lambda: changes.append(1))
    start, end = pixel(editor, 0.1, 2.5), pixel(editor, 0.6, 2.0)
    QTest.mousePress(editor, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(editor, end)
    QTest.mouseRelease(editor, Qt.MouseButton.LeftButton, pos=end)
    assert zone.cu == pytest.approx(0.5, abs=0.03)  # moved by the drag, not jumped to the pointer
    assert zone.cv == pytest.approx(2.0, abs=0.03)
    assert (zone.rx, zone.ry) == (0.6, 0.4)
    assert changes


def test_dragging_a_handle_resizes_one_radius(qapp: QApplication) -> None:
    zone = CustomZone(cu=0.0, cv=1.0, rx=0.5, ry=0.5)
    editor = editor_for(zone)
    handle = editor.handle_positions()["rx+"].toPoint()
    target = pixel(editor, 0.9, 1.0)
    QTest.mousePress(editor, Qt.MouseButton.LeftButton, pos=handle)
    QTest.mouseMove(editor, target)
    QTest.mouseRelease(editor, Qt.MouseButton.LeftButton, pos=target)
    assert zone.rx == pytest.approx(0.9, abs=0.03)
    assert zone.ry == 0.5
    handle = editor.handle_positions()["ry-"].toPoint()
    top = pixel(editor, 0.0, 0.2)
    QTest.mousePress(editor, Qt.MouseButton.LeftButton, pos=handle)
    QTest.mouseMove(editor, top)
    QTest.mouseRelease(editor, Qt.MouseButton.LeftButton, pos=top)
    assert zone.ry == pytest.approx(0.8, abs=0.03)


def test_the_mirrored_half_can_be_dragged_too(qapp: QApplication) -> None:
    zone = CustomZone(cu=1.2, cv=0.3, rx=0.3, ry=0.4, mirror=True)
    editor = editor_for(zone)
    start, end = pixel(editor, -1.2, 0.3), pixel(editor, -1.0, 0.3)
    QTest.mousePress(editor, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(editor, end)
    QTest.mouseRelease(editor, Qt.MouseButton.LeftButton, pos=end)
    assert zone.cu == pytest.approx(1.0, abs=0.03)  # the mirror moved inward, so the shape did too


def test_a_press_outside_the_shape_changes_nothing(qapp: QApplication) -> None:
    zone = CustomZone(cu=0.0, cv=2.5, rx=0.3, ry=0.3)
    editor = editor_for(zone)
    far = pixel(editor, 1.5, -2.0)
    QTest.mousePress(editor, Qt.MouseButton.LeftButton, pos=far)
    QTest.mouseMove(editor, pixel(editor, 1.0, -1.0))
    QTest.mouseRelease(editor, Qt.MouseButton.LeftButton, pos=pixel(editor, 1.0, -1.0))
    assert (zone.cu, zone.cv, zone.rx, zone.ry) == (0.0, 2.5, 0.3, 0.3)


def test_the_shape_cannot_leave_the_drawing_or_shrink_to_nothing(qapp: QApplication) -> None:
    zone = CustomZone(cu=0.0, cv=0.0, rx=0.5, ry=0.5)
    editor = editor_for(zone)
    start = pixel(editor, 0.0, 0.0)
    QTest.mousePress(editor, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(editor, QPoint(-500, -500))
    QTest.mouseRelease(editor, Qt.MouseButton.LeftButton, pos=QPoint(-500, -500))
    assert -2.2 <= zone.cu <= 2.2
    assert -2.6 <= zone.cv <= 3.4
    zone.rx = 0.12
    for _ in range(10):
        QTest.keyClick(editor, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
    assert zone.rx == 0.1


def test_the_arrow_keys_move_and_shift_arrows_resize(qapp: QApplication) -> None:
    zone = CustomZone(cu=0.0, cv=1.0, rx=0.3, ry=0.3)
    editor = editor_for(zone)
    QTest.keyClick(editor, Qt.Key.Key_Right)
    QTest.keyClick(editor, Qt.Key.Key_Down)
    QTest.keyClick(editor, Qt.Key.Key_Down)
    assert (zone.cu, zone.cv) == (0.05, 1.1)
    QTest.keyClick(editor, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    QTest.keyClick(editor, Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
    assert (zone.rx, zone.ry) == (0.35, 0.25)


def test_the_editor_paints_with_and_without_the_mirror(qapp: QApplication) -> None:
    for mirror in (False, True):
        editor = editor_for(CustomZone(cu=1.2, cv=0.3, rx=0.3, ry=0.4, mirror=mirror))
        editor.show()
        assert not editor.grab().isNull()
        editor.hide()


# ---------------------------------------------------------------------------- the tab
def test_the_tab_returns_the_settings_unchanged_when_nothing_was_touched(
    qapp: QApplication,
) -> None:
    settings = Settings()
    tab = CustomZonesTab(settings)
    out = Settings()
    tab.apply(out)
    assert out == settings


def test_the_tab_keeps_each_zones_edits_when_switching_between_them(qapp: QApplication) -> None:
    tab = CustomZonesTab(Settings())
    tab.enabled.setChecked(True)
    tab.name.setText("ear picking")
    tab.name.textEdited.emit("ear picking")
    tab.dwell.setValue(2.5)
    tab.mirror.setChecked(False)
    tab.slot.setCurrentIndex(2)
    assert not tab.enabled.isChecked()  # the third zone is still off
    assert tab.name.text() == ""
    tab.enabled.setChecked(True)
    tab.slot.setCurrentIndex(0)
    assert tab.enabled.isChecked()
    assert tab.name.text() == "ear picking"
    assert tab.dwell.value() == 2.5
    assert not tab.mirror.isChecked()
    out = Settings()
    tab.apply(out)
    assert out.habit(Habit.CUSTOM_1).enabled
    assert out.habit(Habit.CUSTOM_1).dwell_s == 2.5
    assert out.habit(Habit.CUSTOM_3).enabled
    assert out.custom_zones["custom_1"].name == "ear picking"
    assert not out.custom_zones["custom_1"].mirror


def test_the_name_shows_in_the_zone_list_as_it_is_typed(qapp: QApplication) -> None:
    tab = CustomZonesTab(Settings())
    assert tab.slot.itemText(0) == "Custom zone 1"
    tab.name.setText("ears")
    tab.name.textEdited.emit("ears")
    assert tab.slot.itemText(0) == "ears"
    tab.name.setText("")
    tab.name.textEdited.emit("")
    assert tab.slot.itemText(0) == "Custom zone 1"


def test_resetting_brings_the_shape_back_but_not_the_name(qapp: QApplication) -> None:
    tab = CustomZonesTab(Settings())
    tab.name.setText("ears")
    tab.name.textEdited.emit("ears")
    tab.editor.zone().cu = 0.1
    tab.reset.click()
    zone = tab.editor.zone()
    assert zone.cu == DEFAULT_CUSTOM_ZONES[Habit.CUSTOM_1].cu
    assert zone.name == "ears"


def test_the_settings_dialog_saves_a_drawn_zone(qapp: QApplication) -> None:
    dialog = SettingsDialog(Settings())
    tab = dialog._custom_tab
    tab.enabled.setChecked(True)
    tab.name.setText("neck scratching")
    tab.name.textEdited.emit("neck scratching")
    tab.slot.setCurrentIndex(2)
    saved = dialog.result_settings()
    assert saved.habit(Habit.CUSTOM_1).enabled
    assert saved.custom_zones["custom_1"].name == "neck scratching"
    assert saved.zone_specs()[Habit.CUSTOM_1].shape


def test_the_dialog_has_the_custom_tab_in_both_languages(qapp: QApplication) -> None:
    for language, tab_title, zone_title in (
        ("en", "Custom zones", "Custom zone 1"),
        ("tr", "Özel bölgeler", "Özel bölge 1"),
    ):
        i18n.set_language(language)
        dialog = SettingsDialog(Settings())
        tabs = dialog.findChild(QTabWidget)
        assert tabs is not None
        assert [tabs.tabText(i) for i in range(tabs.count())][1] == tab_title
        assert dialog._custom_tab.slot.itemText(0) == zone_title
    i18n.set_language("en")


# ------------------------------------------------------------------ the whole application
class Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, int]] = []
        self.notes: list[tuple[str, str]] = []

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


def feed(controller: Controller, start: float, stop: float, uv) -> None:  # type: ignore[no-untyped-def]
    face = make_face()
    t = start
    while t < stop:
        hands = (make_hand(face_u_v=uv),) if uv is not None else ()
        controller._on_observation(
            Observation(ts=t, face=face, hands=hands, hand_near=bool(hands), frame_size=(640, 480))
        )
        t += 0.125


def test_a_drawn_zone_raises_a_counted_alarm_under_its_own_name(qapp: QApplication) -> None:
    settings = Settings(onboarded=True)
    for h in BUILT_IN_HABITS:
        settings.habit(h).enabled = False
    settings.habit(Habit.CUSTOM_1).enabled = True
    settings.habit(Habit.CUSTOM_1).dwell_s = 1.0
    settings.custom_zones["custom_1"] = CustomZone(
        name="ear picking", cu=1.3, cv=0.35, rx=0.3, ry=0.5
    )
    controller = Controller(settings)
    rec = Recorder()
    controller.alerts = AlertManager(
        controller.settings,
        sound=rec,
        speech=rec,
        curtain=rec,
        notify=lambda title, body: rec.notes.append((title, body)),
    )
    feed(controller, 0.0, 0.6, (1.3, 0.35))  # shorter than the dwell time
    assert rec.events == []
    feed(controller, 0.6, 1.5, (1.3, 0.35))
    assert ("show", 1) in rec.events
    assert rec.notes == [("Hands down!", "Ear picking detected")]
    assert controller.stats.count(date.today(), Habit.CUSTOM_1) == 1
    feed(controller, 1.5, 3.0, (0.0, 1.3))  # the mouth: nail biting is off, so nothing there
    assert controller.engine.active_habits() == set()
    controller.shutdown()


def test_applying_settings_updates_the_names_everywhere(qapp: QApplication) -> None:
    controller = Controller(Settings(onboarded=True))
    new = Settings(onboarded=True)
    new.custom_zones["custom_2"].name = "cheek picking"
    controller.apply_settings(new)
    assert i18n.habit_name(Habit.CUSTOM_2) == "Cheek picking"
    controller.shutdown()


def test_the_statistics_list_a_drawn_zone_once_it_has_counted(qapp: QApplication) -> None:
    i18n.set_custom_names({Habit.CUSTOM_1: "ear picking"})
    window = StatsDialog()
    stats = Stats()
    window.refresh(stats, date.today())
    window.show()
    rows = window._by_habit
    assert all(not rows.isRowVisible(i) for i, h in enumerate(Habit) if h.is_custom)
    assert all(rows.isRowVisible(i) for i, h in enumerate(Habit) if not h.is_custom)
    stats.record(Habit.CUSTOM_1, date.today())
    window.refresh(stats, date.today())
    assert rows.isRowVisible(list(Habit).index(Habit.CUSTOM_1))
    assert window._habit_titles[Habit.CUSTOM_1].text() == "Ear picking"
    window.close()


def test_numbers_that_are_not_numbers_fall_back_to_the_defaults() -> None:
    raw = json.loads(
        '{"custom_zones": {"custom_1": {"cu": NaN, "rx": Infinity, "cv": -Infinity}},'
        ' "habits": {"nail_biting": {"dwell_s": NaN, "zone_scale": Infinity}}, "camera_index": NaN}'
    )
    settings = Settings.from_dict(raw)
    default = Settings()
    zone, expected = settings.custom_zones["custom_1"], default.custom_zones["custom_1"]
    assert (zone.cu, zone.rx, zone.cv) == (expected.cu, expected.rx, expected.cv)
    assert settings.habit(Habit.NAIL_BITING).dwell_s == default.habit(Habit.NAIL_BITING).dwell_s
    assert settings.habit(Habit.NAIL_BITING).zone_scale == 1.0
    assert settings.camera_index == default.camera_index


def test_the_hidden_fingertips_switch_is_on_by_default_and_reaches_the_zones() -> None:
    settings = Settings()
    assert settings.habit(Habit.NAIL_BITING).hidden_tips
    assert settings.zone_specs()[Habit.NAIL_BITING].hidden_tips
    settings.habit(Habit.NAIL_BITING).hidden_tips = False
    assert not settings.zone_specs()[Habit.NAIL_BITING].hidden_tips
    assert Settings.from_dict(settings.to_dict()) == settings  # it is saved and read back
    assert (
        Settings.from_dict({"habits": {"nail_biting": {"hidden_tips": "yes"}}})
        .habit(Habit.NAIL_BITING)
        .hidden_tips
    )  # junk: the default


def test_the_settings_window_has_the_hidden_fingertips_box_for_nail_biting_only(
    qapp: QApplication,
) -> None:
    dialog = SettingsDialog(Settings())
    boxes = {b.habit: b for b in dialog._habit_boxes}
    assert boxes[Habit.NAIL_BITING].hidden_tips is not None
    assert all(b.hidden_tips is None for h, b in boxes.items() if h is not Habit.NAIL_BITING)
    boxes[Habit.NAIL_BITING].hidden_tips.setChecked(False)  # type: ignore[union-attr]
    assert not dialog.result_settings().habit(Habit.NAIL_BITING).hidden_tips
