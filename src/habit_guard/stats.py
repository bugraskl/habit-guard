"""Counters and the "clean time" streak, kept as plain numbers in a local JSON file.

Only counts are stored: how many times each habit raised an alarm on each day,
and how long you were watched since the last one. Dates are passed in so the
logic stays deterministic; nothing here touches the clock.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .types import Habit

#: How many days of history are kept.
KEEP_DAYS = 400
#: A gap between two observations longer than this is not counted as watched time.
MAX_TICK_S = 5.0


@dataclass(slots=True)
class Stats:
    #: ISO date -> habit value -> number of alarms.
    days: dict[str, dict[str, int]] = field(default_factory=dict)
    #: Watched seconds since the last alarm.
    clean_s: float = 0.0
    #: The longest clean stretch ever.
    best_clean_s: float = 0.0
    #: Watched seconds in total.
    watched_s: float = 0.0

    def record(self, habit: Habit, day: date) -> None:
        """Count one alarm and restart the clean streak."""
        counts = self.days.setdefault(day.isoformat(), {})
        counts[habit.value] = counts.get(habit.value, 0) + 1
        self.clean_s = 0.0
        self._prune(day)

    def add_watched(self, seconds: float) -> None:
        """Add watched time (the face was in view and tracking was on)."""
        seconds = max(0.0, min(seconds, MAX_TICK_S))
        self.watched_s += seconds
        self.clean_s += seconds
        self.best_clean_s = max(self.best_clean_s, self.clean_s)

    def count(self, day: date, habit: Habit | None = None) -> int:
        counts = self.days.get(day.isoformat(), {})
        return counts.get(habit.value, 0) if habit else sum(counts.values())

    def last_days(self, today: date, n: int = 7) -> list[tuple[date, int]]:
        """``(day, total alarms)`` for the ``n`` days ending today, oldest first."""
        days = [today - timedelta(days=i) for i in range(n - 1, -1, -1)]
        return [(d, self.count(d)) for d in days]

    def total(self, habit: Habit | None = None) -> int:
        return sum(
            (c.get(habit.value, 0) if habit else sum(c.values())) for c in self.days.values()
        )

    def _prune(self, today: date) -> None:
        cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
        for key in [k for k in self.days if k < cutoff]:
            del self.days[key]

    # ------------------------------------------------------------------------------ files
    def to_dict(self) -> dict[str, Any]:
        return {
            "days": self.days,
            "clean_s": round(self.clean_s, 1),
            "best_clean_s": round(self.best_clean_s, 1),
            "watched_s": round(self.watched_s, 1),
        }

    @classmethod
    def from_dict(cls, raw: object) -> Stats:
        """Read stats from parsed JSON; anything malformed is dropped, never raised."""
        stats = cls()
        if not isinstance(raw, dict):
            return stats
        days = raw.get("days")
        if isinstance(days, dict):
            for key, counts in days.items():
                if not (isinstance(key, str) and isinstance(counts, dict)):
                    continue
                try:
                    date.fromisoformat(key)
                except ValueError:
                    continue
                clean = {
                    h.value: int(counts[h.value])
                    for h in Habit
                    if isinstance(counts.get(h.value), int) and counts[h.value] > 0
                }
                if clean:
                    stats.days[key] = clean
        for name in ("clean_s", "best_clean_s", "watched_s"):
            value = raw.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
                setattr(stats, name, float(value))
        return stats

    @classmethod
    def load(cls, path: Path) -> Stats:
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return cls()

    def save(self, path: Path) -> None:
        write_json_atomic(path, self.to_dict())


def write_json_atomic(path: Path, data: object) -> None:
    """Write JSON next to ``path`` and move it into place, so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".part", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out, indent=2, ensure_ascii=False)
            out.write("\n")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
