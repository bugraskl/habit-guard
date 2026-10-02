from __future__ import annotations

import itertools

from habit_guard.engine.decision import EngineSettings, HabitEngine, Release, Trigger
from habit_guard.types import Habit

NAIL = Habit.NAIL_BITING
IN = {NAIL: 3}
OUT = {NAIL: 0}


def make_engine(**overrides: object) -> HabitEngine:
    settings = EngineSettings(**overrides)  # type: ignore[arg-type]
    return HabitEngine(dwell=dict.fromkeys(Habit, 1.0), settings=settings)


def run(
    engine: HabitEngine, start: float, stop: float, counts: dict[Habit, int], step: float = 0.1
):
    """Feed ``counts`` every ``step`` seconds from ``start`` up to (not including) ``stop``."""
    events = []
    n = round((stop - start) / step)
    for i in range(n):
        events.extend(engine.update(start + i * step, counts))
    return events


def test_alarm_fires_once_the_dwell_time_has_passed() -> None:
    engine = make_engine()
    assert run(engine, 0.0, 0.95, IN) == []
    events = run(engine, 0.95, 1.2, IN)
    assert events == [Trigger(NAIL, 1, first=True, duration=events[0].duration)]
    assert 1.0 <= events[0].duration < 1.2


def test_a_quick_touch_never_fires() -> None:
    engine = make_engine()
    assert run(engine, 0.0, 0.5, IN) == []
    assert run(engine, 0.5, 5.0, OUT) == []
    assert engine.active_habits() == set()


def test_short_dropouts_do_not_end_the_run() -> None:
    engine = make_engine(gap_s=0.6)
    events = []
    t = 0.0
    for _ in range(5):  # hand seen for 0.4 s, lost for 0.3 s, over and over
        events += run(engine, t, t + 0.4, IN)
        events += run(engine, t + 0.4, t + 0.7, OUT)
        t += 0.7
    assert any(isinstance(e, Trigger) for e in events)
    assert not any(isinstance(e, Release) for e in events)


def test_a_long_gap_ends_the_run_and_releases_the_alarm() -> None:
    engine = make_engine(gap_s=0.6)
    run(engine, 0.0, 1.5, IN)
    assert engine.active_habits() == {NAIL}
    events = run(engine, 1.5, 3.0, OUT)
    releases = [e for e in events if isinstance(e, Release)]
    assert len(releases) == 1
    assert releases[0].habit is NAIL
    assert engine.active_habits() == set()


def test_alarm_escalates_while_the_hand_stays() -> None:
    engine = make_engine(repeat_s=4.0, max_level=3)
    events = run(engine, 0.0, 14.0, IN)
    triggers = [e for e in events if isinstance(e, Trigger)]
    assert [t.level for t in triggers[:3]] == [1, 2, 3]
    assert [t.first for t in triggers[:3]] == [True, False, False]
    # Level 3 is the ceiling; it repeats instead of rising further.
    assert all(t.level <= 3 for t in triggers)
    gaps = [b.duration - a.duration for a, b in itertools.pairwise(triggers)]
    assert all(g >= 3.9 for g in gaps)


def test_without_escalation_there_is_one_alarm_per_run() -> None:
    engine = make_engine(escalate=False)
    events = run(engine, 0.0, 30.0, IN)
    assert len([e for e in events if isinstance(e, Trigger)]) == 1


def test_cooldown_holds_back_a_second_alarm_for_the_same_habit() -> None:
    engine = make_engine(cooldown_s=5.0, gap_s=0.3)
    first = run(engine, 0.0, 1.2, IN)
    assert any(isinstance(e, Trigger) for e in first)
    run(engine, 1.2, 1.8, OUT)  # released
    # Back after 2 s: the dwell is over at 3.8 s but the cooldown runs until 6.0 s.
    assert [e for e in run(engine, 1.8, 5.9, IN) if isinstance(e, Trigger)] == []
    later = run(engine, 5.9, 7.0, IN)
    assert any(isinstance(e, Trigger) and e.first for e in later)


def test_habits_are_tracked_independently() -> None:
    engine = HabitEngine(dwell={**dict.fromkeys(Habit, 1.0), Habit.FACE_TOUCH: 4.0})
    events = run(engine, 0.0, 2.0, {Habit.NAIL_BITING: 2, Habit.FACE_TOUCH: 1})
    triggered = {e.habit for e in events if isinstance(e, Trigger)}
    assert triggered == {Habit.NAIL_BITING}
    events = run(engine, 2.0, 5.0, {Habit.NAIL_BITING: 2, Habit.FACE_TOUCH: 1})
    assert Habit.FACE_TOUCH in {e.habit for e in events if isinstance(e, Trigger)}


def test_reset_releases_raised_alarms_and_forgets_runs() -> None:
    engine = make_engine()
    run(engine, 0.0, 1.5, IN)
    events = engine.reset()
    assert [type(e) for e in events] == [Release]
    assert engine.active_habits() == set()
    assert engine.reset() == []


def test_missing_habit_in_counts_counts_as_absent() -> None:
    engine = make_engine()
    run(engine, 0.0, 1.5, IN)
    events = run(engine, 1.5, 3.0, {})
    assert any(isinstance(e, Release) for e in events)


def test_no_first_alarm_once_the_hand_has_left_even_inside_the_forgiven_gap() -> None:
    # The dwell time is reached only after the hand is gone, with the cooldown of an earlier
    # alarm ending inside the gap. The alarm must not fire for a hand that is no longer there.
    engine = make_engine(cooldown_s=5.0, gap_s=0.6)
    run(engine, 0.0, 1.2, IN)  # first alarm at 1.0 s
    run(engine, 1.2, 1.9, OUT)  # released
    events = run(engine, 5.1, 5.9, IN)  # a new run, the cooldown ends at 6.0 s
    assert [e for e in events if isinstance(e, Trigger)] == []
    events = run(engine, 5.9, 6.5, OUT)  # past the dwell and the cooldown, inside the gap
    assert [e for e in events if isinstance(e, Trigger)] == []
