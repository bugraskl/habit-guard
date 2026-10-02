"""Where Habit Guard keeps its files."""

from __future__ import annotations

import os
from pathlib import Path

import platformdirs

APP_NAME = "habit-guard"
#: Environment variable that moves every file into one folder (portable use, tests).
HOME_ENV = "HABIT_GUARD_HOME"


def config_dir() -> Path:
    """The folder with ``settings.json`` and ``stats.json``."""
    override = os.environ.get(HOME_ENV)
    if override:
        return Path(override).expanduser()
    return Path(platformdirs.user_config_dir(APP_NAME, appauthor=False))


def settings_path() -> Path:
    return config_dir() / "settings.json"


def stats_path() -> Path:
    return config_dir() / "stats.json"


def sounds_dir() -> Path:
    """Where the generated alarm tones are cached."""
    return config_dir() / "sounds"


def lock_path() -> Path:
    return config_dir() / "habit-guard.lock"


def models_dir() -> Path:
    """The folder with the bundled ONNX models."""
    return Path(__file__).resolve().parent / "vision" / "models"
