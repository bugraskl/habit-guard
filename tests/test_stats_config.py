from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from habit_guard.config import DEFAULT_HABITS, Settings
from habit_guard.stats import MAX_TICK_S, Stats
from habit_guard.types import Habit

DAY = date(2026, 10, 2)


# ------------------------------------------------------------------------------- stats
def test_record_counts_per_day_and_resets_the_streak() -> None:
    stats = Stats()
    for _ in range(24):
        stats.add_watched(5.0)
    assert stats.clean_s == 120.0
    stats.record(Habit.NAIL_BITING, DAY)
    stats.record(Habit.NAIL_BITING, DAY)
    stats.record(Habit.MUSTACHE, DAY)
    assert stats.count(DAY) == 3
    assert stats.count(DAY, Habit.NAIL_BITING) == 2
    assert stats.clean_s == 0.0
    assert stats.best_clean_s == 120.0


def test_watched_time_ignores_long_gaps() -> None:
    stats = Stats()
    stats.add_watched(3600.0)  # the laptop slept; this is not watched time
    assert stats.watched_s == MAX_TICK_S
    stats.add_watched(-4.0)
    assert stats.watched_s == MAX_TICK_S


def test_last_days_is_oldest_first_and_fills_gaps() -> None:
    stats = Stats()
    stats.record(Habit.NAIL_BITING, date(2026, 9, 30))
    stats.record(Habit.NAIL_BITING, DAY)
    week = stats.last_days(DAY, 4)
    assert [d.isoformat() for d, _ in week] == [
        "2026-09-29",
        "2026-09-30",
        "2026-10-01",
        "2026-10-02",
    ]
    assert [n for _, n in week] == [0, 1, 0, 1]


def test_old_days_are_pruned() -> None:
    stats = Stats(days={"2020-01-01": {"nail_biting": 4}})
    stats.record(Habit.NAIL_BITING, DAY)
    assert "2020-01-01" not in stats.days


def test_stats_roundtrip_and_survive_garbage(tmp_path: Path) -> None:
    stats = Stats()
    stats.add_watched(4.0)
    stats.record(Habit.HAIR_PULLING, DAY)
    path = tmp_path / "stats.json"
    stats.save(path)
    assert Stats.load(path) == stats

    path.write_text("{not json", encoding="utf-8")
    assert Stats.load(path) == Stats()
    assert Stats.load(tmp_path / "missing.json") == Stats()
    junk = {
        "days": {"not-a-date": {"nail_biting": 1}, "2026-10-02": {"nail_biting": -3, "x": 1}},
        "clean_s": "soon",
    }
    assert Stats.from_dict(junk) == Stats()
    assert Stats.from_dict([1, 2]) == Stats()


# ----------------------------------------------------------------------------- settings
def test_defaults_enable_nail_biting_and_mustache_only() -> None:
    settings = Settings()
    enabled = {h for h in Habit if settings.habit(h).enabled}
    assert enabled == {Habit.NAIL_BITING, Habit.MUSTACHE}
    assert settings.any_habit_enabled()


def test_default_habits_are_not_shared_between_instances() -> None:
    a, b = Settings(), Settings()
    a.habit(Habit.NAIL_BITING).dwell_s = 9.0
    assert b.habit(Habit.NAIL_BITING).dwell_s == DEFAULT_HABITS[Habit.NAIL_BITING].dwell_s


def test_settings_roundtrip(tmp_path: Path) -> None:
    settings = Settings()
    settings.profile = "eco"
    settings.alerts.volume = 0.25
    settings.alerts.speech = True
    settings.habit(Habit.HAIR_PULLING).enabled = True
    settings.habit(Habit.MUSTACHE).wide_area = True
    path = tmp_path / "settings.json"
    settings.save(path)
    assert Settings.load(path) == settings


def test_bad_values_fall_back_or_clamp() -> None:
    raw = {
        "profile": "turbo",
        "language": "tr",
        "camera_index": 99,
        "habits": {
            "nail_biting": {"enabled": "yes", "dwell_s": 0.0, "zone_scale": 50},
            "mustache": "nope",
            "unknown_habit": {"enabled": True},
        },
        "alerts": {"volume": 7, "curtain_style": "disco", "repeat_s": "often", "sound": False},
    }
    settings = Settings.from_dict(raw)
    assert settings.profile == "balanced"
    assert settings.language == "tr"
    assert settings.camera_index == 16
    nail = settings.habit(Habit.NAIL_BITING)
    assert nail.enabled is True  # "yes" is not a bool: the default stays
    assert nail.dwell_s == 0.3
    assert nail.zone_scale == 2.0
    assert settings.habit(Habit.MUSTACHE) == DEFAULT_HABITS[Habit.MUSTACHE]
    assert settings.alerts.volume == 1.0
    assert settings.alerts.curtain_style == "dim"
    assert settings.alerts.repeat_s == Settings().alerts.repeat_s
    assert settings.alerts.sound is False


def test_unreadable_settings_file_gives_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("][", encoding="utf-8")
    assert Settings.load(path) == Settings()
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert Settings.load(path) == Settings()


def test_derived_engine_and_zone_settings() -> None:
    settings = Settings()
    settings.alerts.escalate = False
    settings.alerts.repeat_s = 9.0
    settings.habit(Habit.NAIL_BITING).zone_scale = 1.3
    engine = settings.engine_settings()
    assert engine.escalate is False
    assert engine.repeat_s == 9.0
    assert settings.zone_specs()[Habit.NAIL_BITING].scale == 1.3
    assert settings.dwell_map()[Habit.FACE_TOUCH] == 4.0
