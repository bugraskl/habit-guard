"""The alarm tones, made on the fly, and their playback.

Three built-in tones step up with the alarm level: a soft two-note chime, three
beeps, and a warbling alarm. They are synthesised into small WAV files in the
settings folder the first time they are needed, so the package ships no audio
and there is nothing to license. A WAV file of your own can replace them.

The tone generator is pure numpy; only :class:`SoundPlayer` needs Qt.
"""

from __future__ import annotations

import io
import logging
import wave
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

SAMPLE_RATE = 22050
#: How loud each level plays relative to the volume setting (before the setting is applied).
LEVEL_GAIN = {1: 0.55, 2: 0.8, 3: 1.0}


def _tone(freq: float, seconds: float, *, fade: float = 0.015) -> np.ndarray:
    t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
    wave_ = np.sin(2.0 * np.pi * freq * t)
    ramp = min(int(SAMPLE_RATE * fade), wave_.size // 2)
    if ramp:
        envelope = np.ones_like(wave_)
        envelope[:ramp] = np.linspace(0.0, 1.0, ramp)
        envelope[-ramp:] = np.linspace(1.0, 0.0, ramp)
        wave_ = wave_ * envelope
    return wave_


def _silence(seconds: float) -> np.ndarray:
    return np.zeros(int(SAMPLE_RATE * seconds))


def synthesize(level: int) -> np.ndarray:
    """The samples (floats in -1..1) of the built-in tone for ``level`` (1 to 3)."""
    if level <= 1:  # a soft two-note chime
        parts = [_tone(660.0, 0.18, fade=0.04), _tone(880.0, 0.26, fade=0.08)]
    elif level == 2:  # three beeps
        parts = []
        for _ in range(3):
            parts += [_tone(880.0, 0.14), _silence(0.09)]
    else:  # a warble between two pitches
        parts = []
        for _ in range(5):
            parts += [_tone(740.0, 0.16, fade=0.005), _tone(1040.0, 0.16, fade=0.005)]
    return np.concatenate(parts) * 0.9


def wav_bytes(level: int) -> bytes:
    """The tone for ``level`` as the bytes of a 16-bit mono WAV file."""
    pcm = (synthesize(level) * 32767.0).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(pcm.tobytes())
    return buffer.getvalue()


def ensure_tones(directory: Path) -> dict[int, Path]:
    """Write the built-in tones to ``directory`` if they are not there yet."""
    paths: dict[int, Path] = {}
    directory.mkdir(parents=True, exist_ok=True)
    for level in (1, 2, 3):
        path = directory / f"alarm-{level}.wav"
        if not path.is_file():
            path.write_bytes(wav_bytes(level))
        paths[level] = path
    return paths


def effective_volume(level: int, volume: float) -> float:
    """The playback volume (0 to 1) for an alarm ``level`` and the user's volume setting."""
    return max(0.0, min(1.0, volume * LEVEL_GAIN.get(level, 1.0)))


class SoundPlayer:
    """Plays the alarm tone for a level, or the user's own WAV file."""

    def __init__(self, directory: Path):
        self._directory = directory
        self._tones: dict[int, Path] = {}
        self._effects: dict[str, object] = {}

    def play(self, level: int, volume: float, custom_file: str = "") -> None:
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QSoundEffect
        except ImportError:  # pragma: no cover - Qt multimedia is part of the dependency
            return
        path = self._resolve(level, custom_file)
        if path is None:
            return
        effect = self._effects.get(str(path))
        if effect is None:
            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(str(path)))
            self._effects[str(path)] = effect
        effect.setVolume(effective_volume(level, volume))  # type: ignore[attr-defined]
        effect.play()  # type: ignore[attr-defined]

    def stop(self) -> None:
        for effect in self._effects.values():
            effect.stop()  # type: ignore[attr-defined]

    def _resolve(self, level: int, custom_file: str) -> Path | None:
        if custom_file:
            custom = Path(custom_file).expanduser()
            if custom.is_file():
                return custom
            log.warning("sound file not found, using the built-in tone: %s", custom)
        try:
            if not self._tones:
                self._tones = ensure_tones(self._directory)
        except OSError:
            log.exception("could not write the alarm tones")
            return None
        return self._tones.get(min(max(level, 1), 3))
