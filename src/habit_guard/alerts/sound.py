"""The alarm tones, made on the fly, and their playback.

Three built-in tones step up with the alarm level: a soft two-note chime, three
beeps, and a warbling alarm. They are synthesised into small WAV files in the
settings folder the first time they are needed, so the package ships no audio
and there is nothing to license. A sound file of your own can replace them.

Playback uses what the operating system already has, so the app needs no audio
library: ``winsound`` on Windows, ``afplay`` on macOS, and ``paplay``,
``pw-play``, ``aplay`` or ``play`` on Linux. The volume is baked into the WAV
file that is played, because those tools do not all have a volume control. A
custom sound that is not a WAV (an MP3, say) cannot be rewritten that way, so
the volume is handed to the player instead: Windows' Media Control Interface,
``afplay``, or ``ffplay``, ``mpv``, ``mpg123`` or VLC on Linux.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import logging
import shutil
import subprocess
import sys
import time
import wave
from collections.abc import Callable
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

SAMPLE_RATE = 22050
#: How loud each level plays relative to the volume setting (before the setting is applied).
LEVEL_GAIN = {1: 0.55, 2: 0.8, 3: 1.0}
#: Volumes are rounded to this step, so only a handful of files are ever written.
VOLUME_STEP = 0.05


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


def wav_bytes(level: int, gain: float = 1.0) -> bytes:
    """The tone for ``level`` as the bytes of a 16-bit mono WAV file, scaled by ``gain``."""
    pcm = (synthesize(level) * 32767.0 * max(0.0, min(gain, 1.0))).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(pcm.tobytes())
    return buffer.getvalue()


def effective_volume(level: int, volume: float) -> float:
    """The playback volume (0 to 1) for an alarm ``level`` and the user's volume setting."""
    return max(0.0, min(1.0, volume * LEVEL_GAIN.get(level, 1.0)))


def scale_wav(data: bytes, gain: float) -> bytes:
    """``data`` (a WAV file) with every sample multiplied by ``gain``.

    Only 16-bit PCM is scaled; any other format is returned as it is, so a
    custom file still plays, just without the volume setting.
    """
    if gain >= 0.999:
        return data
    try:
        with wave.open(io.BytesIO(data)) as source:
            params = source.getparams()
            frames = source.readframes(source.getnframes())
    except (wave.Error, EOFError):
        return data
    if params.sampwidth != 2:
        return data
    samples = np.frombuffer(frames, dtype="<i2").astype(np.float64) * max(0.0, gain)
    scaled = np.clip(samples, -32768, 32767).astype("<i2")
    out = io.BytesIO()
    with wave.open(out, "wb") as target:
        target.setparams(params)
        target.writeframes(scaled.tobytes())
    return out.getvalue()


#: Formats a custom sound may have besides WAV. They are played by what the system provides:
#: Media Control Interface on Windows, ``afplay`` on macOS, ``ffplay``, ``mpv``, ``mpg123`` or
#: VLC on Linux; the volume setting is passed to the player, as WAV files cannot be rewritten.
COMPRESSED_EXTENSIONS = (".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".flac", ".wma")
AUDIO_EXTENSIONS = (".wav", *COMPRESSED_EXTENSIONS)
FILE_DIALOG_FILTER = "Audio (" + " ".join(f"*{e}" for e in AUDIO_EXTENSIONS) + ")"

#: Linux decoders for compressed files: tool and the arguments that set the volume (0 to 1).
_DECODERS: tuple[tuple[str, Callable[[float], list[str]]], ...] = (
    (
        "ffplay",
        lambda v: ["-nodisp", "-autoexit", "-loglevel", "quiet", "-volume", str(round(v * 100))],
    ),
    ("mpv", lambda v: ["--no-video", "--really-quiet", f"--volume={round(v * 100)}"]),
    ("mpg123", lambda v: ["-q", "-f", str(round(v * 32768))]),  # MP3 only
    ("cvlc", lambda v: ["--play-and-exit", "--quiet", f"--gain={v:.2f}"]),
)
#: The MCI name the alarm sound is opened under (Windows).
MCI_ALIAS = "habitguardsound"


def is_wav(path: Path) -> bool:
    return path.suffix.lower() == ".wav"


def build_command(platform: str, path: Path, volume: float | None = None) -> list[str] | None:
    """The command that plays ``path`` on this platform, or ``None`` when nothing can.

    ``volume`` (0 to 1) is passed to the player when it is given; a WAV file normally has the
    volume baked in already and passes none.
    """
    if platform == "darwin":
        player = shutil.which("afplay")
        if not player:
            return None
        return (
            [player, "-v", f"{volume:.2f}", str(path)]
            if volume is not None
            else [player, str(path)]
        )
    if not is_wav(path):
        level = 1.0 if volume is None else volume
        for tool, arguments in _DECODERS:
            if tool == "mpg123" and path.suffix.lower() != ".mp3":
                continue
            found = shutil.which(tool)
            if found:
                return [found, *arguments(level), str(path)]
        return None
    for tool, extra in (("paplay", []), ("pw-play", []), ("aplay", ["-q"]), ("play", ["-q"])):
        found = shutil.which(tool)
        if found:
            return [found, *extra, str(path)]
    return None


def wav_seconds(path: Path) -> float:
    """The length of a WAV file in seconds; 0 when it cannot be read."""
    try:
        with wave.open(str(path)) as wav:
            return wav.getnframes() / float(wav.getframerate())
    except (wave.Error, EOFError, OSError, ZeroDivisionError):
        return 0.0


class SoundPlayer:
    """Plays the alarm tone for a level, or the user's own sound file.

    A sound that is still playing is left alone when another alarm of the same or a lower level
    asks for it (two habits can raise their alarms half a second apart, and the alarm repeats while
    the hand stays): restarting it would cut a long sound off and make it stutter. Only a higher
    level starts it again, louder.
    """

    def __init__(self, directory: Path, clock: Callable[[], float] = time.monotonic):
        self._directory = directory
        self._clock = clock
        self._process: subprocess.Popen[bytes] | None = None
        self._warned = False
        self._busy_until = 0.0
        self._busy_level = 0
        self._by_process = False  # the running sound is one of our own child processes
        self._mci_open = False

    def play(self, level: int, volume: float, custom_file: str = "") -> None:
        now = self._clock()
        if level <= self._busy_level and self._still_playing(now):
            return
        gain = effective_volume(level, volume)
        custom = self._custom(custom_file)
        if custom is not None and not is_wav(custom):
            self._start_compressed(custom, gain, level, now)
            return
        path = self._render(level, volume, custom)
        if path is None:
            return
        self._busy_until = now + wav_seconds(path)
        self._busy_level = level
        self._by_process = False
        if sys.platform == "win32":
            self._play_windows(path)
        else:
            self._play_command(path, None)

    def stop(self) -> None:
        self._busy_until = 0.0
        self._busy_level = 0
        if sys.platform == "win32":
            self._stop_mci()
            try:
                import winsound

                winsound.PlaySound(None, winsound.SND_PURGE)
            except (ImportError, RuntimeError):
                pass
        elif self._process is not None and self._process.poll() is None:
            self._process.terminate()
        self._process = None

    def _still_playing(self, now: float) -> bool:
        if self._by_process:
            return self._process is not None and self._process.poll() is None
        return now < self._busy_until

    # ---------------------------------------------------------------------------- playing
    def _start_compressed(self, path: Path, gain: float, level: int, now: float) -> None:
        """An MP3 (or similar) of the user's own, played by what the system offers."""
        self._busy_level = level
        if sys.platform == "win32":
            self._by_process = False
            seconds = self._play_mci(path, gain)
            self._busy_until = now + seconds
        else:
            self._by_process = True
            self._play_command(path, gain)

    def _mci(self, command: str) -> str:
        """Send one Media Control Interface command (Windows); the reply text, or ``OSError``."""
        if sys.platform != "win32":
            raise OSError("MCI is a Windows interface")
        import ctypes

        winmm = ctypes.windll.winmm  # type: ignore[attr-defined]
        reply = ctypes.create_unicode_buffer(256)
        error = winmm.mciSendStringW(command, reply, 255, 0)
        if error:
            message = ctypes.create_unicode_buffer(256)
            winmm.mciGetErrorStringW(error, message, 255)
            raise OSError(message.value or f"MCI error {error}")
        return str(reply.value)

    def _stop_mci(self) -> None:
        if self._mci_open:
            for command in (f"stop {MCI_ALIAS}", f"close {MCI_ALIAS}"):
                with contextlib.suppress(OSError):
                    self._mci(command)
            self._mci_open = False

    def _play_mci(self, path: Path, gain: float) -> float:
        """Play a compressed file on Windows; returns its length in seconds (0 if unknown)."""
        if '"' in str(path):
            log.warning("a sound file name with a double quote cannot be played: %s", path)
            return 0.0
        self._stop_mci()
        try:
            self._mci(f'open "{path}" type mpegvideo alias {MCI_ALIAS}')
            self._mci_open = True
            self._mci(f"set {MCI_ALIAS} time format milliseconds")
            with contextlib.suppress(OSError):  # some decoders have no volume control
                self._mci(f"setaudio {MCI_ALIAS} volume to {round(gain * 1000)}")
            self._mci(f"play {MCI_ALIAS}")
            try:
                return int(self._mci(f"status {MCI_ALIAS} length")) / 1000.0
            except (OSError, ValueError):
                return 0.0
        except OSError:
            log.exception("could not play the sound file %s", path)
            self._stop_mci()
            return 0.0

    def _play_windows(self, path: Path) -> None:
        if sys.platform != "win32":  # also lets type checkers on other systems skip the rest
            return
        self._stop_mci()
        try:
            import winsound

            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        except (ImportError, RuntimeError):
            log.exception("could not play the alarm sound")

    def _play_command(self, path: Path, volume: float | None) -> None:
        command = build_command(sys.platform, path, volume)
        if command is None:
            if not self._warned:
                log.warning("no command-line audio player found for %s: the alarm is silent", path)
                self._warned = True
            self._by_process = False
            return
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()  # a higher level replaces the lower one, never layers on it
        try:
            self._process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            log.exception("could not start the audio player")
            self._by_process = False

    # --------------------------------------------------------------------------- the file
    def _custom(self, custom_file: str) -> Path | None:
        """The user's own sound file, if one is set and exists."""
        if not custom_file:
            return None
        custom = Path(custom_file).expanduser()
        if custom.is_file():
            return custom
        log.warning("sound file not found, using the built-in tone: %s", custom)
        return None

    def _render(self, level: int, volume: float, custom: Path | None) -> Path | None:
        """The WAV file to play, with the volume baked in (written once, then reused)."""
        gain = round(effective_volume(level, volume) / VOLUME_STEP) * VOLUME_STEP
        pct = round(gain * 100)
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
            if custom is not None:
                stamp = f"{custom.resolve()}|{custom.stat().st_mtime_ns}"
                name = f"custom-{hashlib.sha1(stamp.encode()).hexdigest()[:10]}-{pct}.wav"
                return self._write(name, lambda: scale_wav(custom.read_bytes(), gain))
            tone = min(max(level, 1), 3)
            return self._write(f"alarm-{tone}-{pct}.wav", lambda: wav_bytes(tone, gain))
        except OSError:
            log.exception("could not prepare the alarm sound")
            return None

    def _write(self, name: str, make: object) -> Path:
        path = self._directory / name
        if not path.is_file():
            path.write_bytes(make())  # type: ignore[operator]
        return path
