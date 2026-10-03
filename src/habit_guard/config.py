"""User settings: what to watch for, how fast to look, and what to do about it.

Settings live in ``settings.json``. Reading is forgiving on purpose: a missing
file, a corrupt file or a hand-edited value out of range never stops the app,
it falls back to the default for that one value.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, TypeVar

from .engine.decision import EngineSettings
from .stats import write_json_atomic
from .types import CUSTOM_HABITS, Habit
from .zones import Ellipse, ZoneSpec

PROFILES = ("eco", "balanced", "responsive")
LANGUAGES = ("auto", "en", "tr")
CURTAIN_STYLES = ("dim", "flash")
CAMERA_APIS = ("auto", "dshow", "msmf", "any")


@dataclass(frozen=True, slots=True)
class Cadence:
    """How often the camera picture is analysed, in seconds between analyses."""

    #: No face in view.
    no_face_s: float
    #: Face in view, hands away: look only when something moved ...
    idle_s: float
    #: ... or at least this often.
    forced_s: float
    #: A hand is near the face.
    active_s: float


CADENCES: dict[str, Cadence] = {
    "eco": Cadence(no_face_s=1.5, idle_s=0.8, forced_s=3.0, active_s=0.20),
    "balanced": Cadence(no_face_s=1.0, idle_s=0.5, forced_s=2.0, active_s=0.125),
    "responsive": Cadence(no_face_s=0.7, idle_s=0.3, forced_s=1.0, active_s=0.07),
}


@dataclass
class HabitConfig:
    enabled: bool = False
    #: Seconds a hand must stay in the zone before the alarm goes off.
    dwell_s: float = 1.5
    #: Zone size factor: below 1 stricter, above 1 more generous.
    zone_scale: float = 1.0
    #: Also cover the chin and beard line (moustache) or the scalp (hair pulling).
    wide_area: bool = False


DEFAULT_HABITS: dict[Habit, HabitConfig] = {
    Habit.NAIL_BITING: HabitConfig(enabled=True, dwell_s=1.0),
    Habit.MUSTACHE: HabitConfig(enabled=True, dwell_s=1.5),
    Habit.HAIR_PULLING: HabitConfig(enabled=False, dwell_s=1.5),
    Habit.FACE_TOUCH: HabitConfig(enabled=False, dwell_s=4.0),
    **{habit: HabitConfig(enabled=False, dwell_s=1.5) for habit in CUSTOM_HABITS},
}

#: The longest name a custom zone can have.
NAME_MAX = 40
#: Two mirrored ellipses closer to the middle than this are one ellipse.
MIRROR_MIN_OFFSET = 0.05


@dataclass
class CustomZone:
    """A zone the user drew, in face coordinates (see ``habit_guard.zones``).

    The origin is the middle between the eyes and one unit is the eye distance, so ``cu`` is to
    the right in the picture and ``cv`` is down toward the chin. ``mirror`` adds the same shape
    on the other side of the face, for ears or cheeks.
    """

    #: What the habit is called ("ear picking"); empty gives "Custom zone 1" and so on.
    name: str = ""
    cu: float = 0.0
    cv: float = 0.0
    rx: float = 0.4
    ry: float = 0.4
    mirror: bool = False

    def ellipses(self) -> tuple[Ellipse, ...]:
        shape = Ellipse(self.cu, self.cv, self.rx, self.ry)
        if self.mirror and abs(self.cu) >= MIRROR_MIN_OFFSET:
            return (shape, Ellipse(-self.cu, self.cv, self.rx, self.ry))
        return (shape,)


#: Where the three custom zones start: an ear on each side, a cheek on each side, the neck.
DEFAULT_CUSTOM_ZONES: dict[Habit, CustomZone] = {
    CUSTOM_HABITS[0]: CustomZone(cu=1.3, cv=0.35, rx=0.32, ry=0.5, mirror=True),
    CUSTOM_HABITS[1]: CustomZone(cu=0.95, cv=0.95, rx=0.4, ry=0.4, mirror=True),
    CUSTOM_HABITS[2]: CustomZone(cu=0.0, cv=2.5, rx=1.0, ry=0.45, mirror=False),
}


@dataclass
class AlertConfig:
    sound: bool = True
    #: 0 to 1; escalation plays louder on top of this.
    volume: float = 0.7
    #: A sound file (WAV, MP3, ...) to play instead of the built-in tones; empty uses those.
    sound_file: str = ""
    notification: bool = True
    #: Darken the screen (dim) or pulse a coloured frame (flash) until the hand leaves.
    curtain: bool = True
    curtain_style: str = "dim"
    #: Say a short phrase with the system's offline voice.
    speech: bool = False
    #: The phrase; empty uses a default in the interface language.
    speech_text: str = ""
    #: Step up the alarm while the hand stays in the zone.
    escalate: bool = True
    #: Seconds between escalation steps.
    repeat_s: float = 4.0


@dataclass
class Settings:
    language: str = "auto"
    #: Camera number, as the operating system counts them.
    camera_index: int = 0
    #: Which capture interface to open the camera with (Windows has two; "auto" picks the best).
    camera_api: str = "auto"
    profile: str = "balanced"
    habits: dict[str, HabitConfig] = field(
        default_factory=lambda: {
            h.value: HabitConfig(**asdict(c)) for h, c in DEFAULT_HABITS.items()
        }
    )
    #: The zones the user drew, by habit key ("custom_1" to "custom_3").
    custom_zones: dict[str, CustomZone] = field(
        default_factory=lambda: {
            h.value: CustomZone(**asdict(z)) for h, z in DEFAULT_CUSTOM_ZONES.items()
        }
    )
    alerts: AlertConfig = field(default_factory=AlertConfig)
    #: Set once the first-run setup has been shown.
    onboarded: bool = False

    # ------------------------------------------------------------------------ derived values
    def habit(self, habit: Habit) -> HabitConfig:
        return self.habits[habit.value]

    def cadence(self) -> Cadence:
        return CADENCES[self.profile]

    def zone_specs(self) -> dict[Habit, ZoneSpec]:
        return {
            h: ZoneSpec(
                enabled=self.habit(h).enabled,
                scale=self.habit(h).zone_scale,
                wide=self.habit(h).wide_area,
                shape=self.custom_zones[h.value].ellipses() if h.is_custom else (),
            )
            for h in Habit
        }

    def custom_names(self) -> dict[Habit, str]:
        """What the user called each custom zone (empty for the ones left unnamed)."""
        return {h: self.custom_zones[h.value].name for h in CUSTOM_HABITS}

    def dwell_map(self) -> dict[Habit, float]:
        return {h: self.habit(h).dwell_s for h in Habit}

    def engine_settings(self) -> EngineSettings:
        return EngineSettings(repeat_s=self.alerts.repeat_s, escalate=self.alerts.escalate)

    def any_habit_enabled(self) -> bool:
        return any(self.habit(h).enabled for h in Habit)

    # ------------------------------------------------------------------------------ files
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: object) -> Settings:
        """Build settings from parsed JSON, replacing anything unusable by its default."""
        if not isinstance(raw, dict):
            return cls()
        settings = _coerce(cls, raw)
        habits_raw = raw.get("habits")
        habits_raw = habits_raw if isinstance(habits_raw, dict) else {}
        habits: dict[str, HabitConfig] = {}
        for habit in Habit:
            sub = habits_raw.get(habit.value)
            habits[habit.value] = _coerce(
                HabitConfig, sub if isinstance(sub, dict) else {}, DEFAULT_HABITS[habit]
            )
        settings.habits = habits
        zones_raw = raw.get("custom_zones")
        zones_raw = zones_raw if isinstance(zones_raw, dict) else {}
        custom: dict[str, CustomZone] = {}
        for habit in CUSTOM_HABITS:
            sub = zones_raw.get(habit.value)
            zone = _coerce(
                CustomZone, sub if isinstance(sub, dict) else {}, DEFAULT_CUSTOM_ZONES[habit]
            )
            zone.name = _clean_name(zone.name)
            custom[habit.value] = zone
        settings.custom_zones = custom
        return settings

    @classmethod
    def load(cls, path: Path) -> Settings:
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return cls()

    def save(self, path: Path) -> None:
        write_json_atomic(path, self.to_dict())


# --------------------------------------------------------------------------------- coercion
#: Allowed range for every number setting; values outside are clamped.
LIMITS: dict[str, tuple[float, float]] = {
    "dwell_s": (0.3, 30.0),
    "zone_scale": (0.5, 2.0),
    "volume": (0.0, 1.0),
    "repeat_s": (1.0, 60.0),
    "camera_index": (0, 16),
    # Custom zones, in face coordinates (eye distances).
    "cu": (-3.0, 3.0),
    "cv": (-3.0, 4.0),
    "rx": (0.1, 2.0),
    "ry": (0.1, 2.0),
}
CHOICES: dict[str, tuple[str, ...]] = {
    "language": LANGUAGES,
    "profile": PROFILES,
    "curtain_style": CURTAIN_STYLES,
    "camera_api": CAMERA_APIS,
}

T = TypeVar("T")


def _clean_name(name: str) -> str:
    """A zone name as one short line of text, without control characters."""
    printable = "".join(ch if ch.isprintable() else " " for ch in name)
    return " ".join(printable.split())[:NAME_MAX]


def _coerce_value(name: str, default: Any, raw: Any) -> Any:
    if isinstance(default, bool):
        return raw if isinstance(raw, bool) else default
    if isinstance(default, int):
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return default
        lo, hi = LIMITS.get(name, (-(2**31), 2**31))
        return int(min(max(raw, lo), hi))
    if isinstance(default, float):
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return default
        lo, hi = LIMITS.get(name, (float("-inf"), float("inf")))
        return float(min(max(raw, lo), hi))
    if isinstance(default, str):
        if not isinstance(raw, str):
            return default
        choices = CHOICES.get(name)
        return raw if choices is None or raw in choices else default
    return default


def _coerce(cls: type[T], raw: dict[str, Any], template: T | None = None) -> T:
    """Fill a settings dataclass from ``raw``; ``template`` gives the defaults to fall back on."""
    values: dict[str, Any] = {}
    base = template if template is not None else cls()
    for f in fields(cls):  # type: ignore[arg-type]
        default = getattr(base, f.name)
        if is_dataclass(default) and not isinstance(default, type):
            sub = raw.get(f.name)
            values[f.name] = _coerce(type(default), sub if isinstance(sub, dict) else {}, default)
        elif isinstance(default, dict):
            values[f.name] = default  # filled in by the caller (habits)
        else:
            values[f.name] = _coerce_value(f.name, default, raw.get(f.name, default))
    return cls(**values)  # type: ignore[call-arg]
