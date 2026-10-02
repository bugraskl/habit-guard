"""Decides when a hand in a zone has become an alarm.

A habit run starts when a hand first reaches the zone and goes on while it
stays there. Short drop-outs (the hand detector flickers, a finger hides
behind another) do not end it. The alarm fires once the run has lasted the
habit's dwell time, which is what keeps drinking, wiping your lips or a quick
scratch from setting it off. While the hand stays, the alarm escalates step by
step; when the hand leaves, the run is released so the UI can calm down.

Time is passed in, never read, so the whole thing is deterministic to test.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from ..types import Habit


@dataclass(frozen=True, slots=True)
class EngineSettings:
    #: A hand missing for less than this many seconds is still counted as there.
    gap_s: float = 0.6
    #: Seconds between escalation steps while the hand stays in the zone.
    repeat_s: float = 4.0
    #: The highest alarm level (1 is the gentlest).
    max_level: int = 3
    #: Fewest seconds between two *new* alarms for the same habit.
    cooldown_s: float = 5.0
    #: Step up the level while the hand stays; off means one alarm per run.
    escalate: bool = True


@dataclass(frozen=True, slots=True)
class Trigger:
    """An alarm to raise now."""

    habit: Habit
    level: int
    #: The first alarm of this run, as opposed to an escalation or a repeat.
    first: bool
    #: Seconds the hand has been in the zone.
    duration: float


@dataclass(frozen=True, slots=True)
class Release:
    """The hand left a zone that had raised an alarm."""

    habit: Habit
    duration: float


Event = Trigger | Release


@dataclass(slots=True)
class _Run:
    since: float
    last_hit: float
    level: int = 0
    last_fire: float = float("-inf")


@dataclass(slots=True)
class HabitEngine:
    """Tracks one run per habit and turns them into :class:`Trigger` and :class:`Release` events."""

    dwell: dict[Habit, float]
    settings: EngineSettings = field(default_factory=EngineSettings)
    _runs: dict[Habit, _Run] = field(default_factory=dict, init=False)
    _last_new_alarm: dict[Habit, float] = field(default_factory=dict, init=False)

    def active_habits(self) -> set[Habit]:
        """Habits that currently have an alarm raised."""
        return {h for h, run in self._runs.items() if run.level > 0}

    def update(self, now: float, counts: Mapping[Habit, int]) -> list[Event]:
        """Feed one observation: ``counts[habit]`` is how many hand points are in its zone."""
        events: list[Event] = []
        habits = set(self._runs) | {h for h, n in counts.items() if n > 0}
        for habit in habits:
            hit = counts.get(habit, 0) > 0
            run = self._runs.get(habit)
            if run is not None and not hit and now - run.last_hit > self.settings.gap_s:
                if run.level > 0:
                    events.append(Release(habit, run.last_hit - run.since))
                del self._runs[habit]
                continue
            if run is None:
                if not hit:
                    continue
                run = self._runs[habit] = _Run(since=now, last_hit=now)
            if hit:
                run.last_hit = now
            events.extend(self._advance(habit, run, now, hit))
        return events

    def _advance(self, habit: Habit, run: _Run, now: float, hit: bool) -> list[Event]:
        # Duration counts up to the last time the hand was actually seen.
        duration = run.last_hit - run.since
        if run.level == 0:
            # A first alarm needs the hand to be there now, not just within the forgiven gap.
            if not hit or duration < self.dwell.get(habit, 1.0):
                return []
            if now - self._last_new_alarm.get(habit, float("-inf")) < self.settings.cooldown_s:
                return []
            run.level = 1
            run.last_fire = now
            self._last_new_alarm[habit] = now
            return [Trigger(habit, 1, first=True, duration=duration)]
        if not self.settings.escalate:
            return []
        if now - run.last_fire < self.settings.repeat_s:
            return []
        run.level = min(run.level + 1, self.settings.max_level)
        run.last_fire = now
        return [Trigger(habit, run.level, first=False, duration=duration)]

    def reset(self) -> list[Event]:
        """Forget every run (tracking paused, camera lost). Raised alarms are released."""
        events: list[Event] = [
            Release(h, run.last_hit - run.since) for h, run in self._runs.items() if run.level > 0
        ]
        self._runs.clear()
        return events
