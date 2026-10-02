"""Logging to a small rotating file (the tray app has no console) and to stderr."""

from __future__ import annotations

import logging
import logging.handlers
import sys

from . import paths

LOG_NAME = "habit-guard.log"


def log_path() -> str:
    return str(paths.config_dir() / LOG_NAME)


def setup(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    if sys.stderr is not None:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(fmt)
        root.addHandler(stream)
    try:
        paths.config_dir().mkdir(parents=True, exist_ok=True)
        file = logging.handlers.RotatingFileHandler(
            log_path(), maxBytes=200_000, backupCount=1, encoding="utf-8"
        )
        file.setFormatter(fmt)
        root.addHandler(file)
    except OSError:
        pass  # an unwritable folder must never stop the app
