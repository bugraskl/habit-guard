"""Turns the engine's events into what the user asked for: sound, speech, curtain, notification.

The four outputs are passed in as small objects, so the policy (which output
fires at which moment) can be tested without a screen or a speaker.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from ..config import Settings
from ..i18n import current_language, habit_short, tr, upper_first
from ..types import Habit


class SoundOut(Protocol):
    def play(self, level: int, volume: float, custom_file: str = "") -> None: ...

    def stop(self) -> None: ...


class SpeechOut(Protocol):
    def say(self, text: str, language: str) -> bool: ...

    def stop(self) -> None: ...


class CurtainOut(Protocol):
    def show(self, style: str, level: int, message: str) -> None: ...

    def hide(self) -> None: ...


Notify = Callable[[str, str], None]


class AlertManager:
    def __init__(
        self,
        settings: Settings,
        *,
        sound: SoundOut,
        speech: SpeechOut,
        curtain: CurtainOut,
        notify: Notify,
    ):
        self.settings = settings
        self._sound = sound
        self._speech = speech
        self._curtain = curtain
        self._notify = notify
        self._raised: set[Habit] = set()

    def fire(self, habit: Habit, level: int, first: bool) -> None:
        """An alarm is due for ``habit``; ``first`` marks the first of its run."""
        cfg = self.settings.alerts
        self._raised.add(habit)
        message = tr("alert.title")
        if cfg.notification and first:
            self._notify(message, upper_first(tr("alert.body", habit=habit_short(habit))))
        if cfg.curtain:
            self._curtain.show(cfg.curtain_style, level, message)
        if cfg.sound:
            self._sound.play(level, cfg.volume, cfg.sound_file)
        if cfg.speech:
            self._speech.say(cfg.speech_text or tr("alert.speech"), current_language())

    def clear(self, habit: Habit | None = None) -> None:
        """The hand is down (or tracking stopped): calm everything."""
        if habit is not None:
            self._raised.discard(habit)
            if self._raised:
                return
        else:
            self._raised.clear()
        self._curtain.hide()
        self._sound.stop()

    def test(self, level: int = 2) -> None:
        """Play the alarm the way the settings have it, so it can be tried out."""
        self.fire(Habit.NAIL_BITING, level, first=True)
