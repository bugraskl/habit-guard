from __future__ import annotations

import io
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

from habit_guard import i18n
from habit_guard.alerts import speech
from habit_guard.alerts.manager import AlertManager
from habit_guard.alerts.sound import (
    SAMPLE_RATE,
    SoundPlayer,
    build_command,
    effective_volume,
    scale_wav,
    synthesize,
    wav_bytes,
)
from habit_guard.config import Settings
from habit_guard.types import Habit


# ------------------------------------------------------------------------------- sounds
@pytest.mark.parametrize("level", [1, 2, 3])
def test_tones_are_valid_audio_of_reasonable_length(level: int) -> None:
    samples = synthesize(level)
    assert 0.3 < samples.size / SAMPLE_RATE < 2.0
    assert np.abs(samples).max() <= 1.0
    assert np.abs(samples).max() > 0.5  # audible
    with wave.open(io.BytesIO(wav_bytes(level))) as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == SAMPLE_RATE
        assert wav.getnframes() == samples.size


def test_levels_sound_different_and_step_up_in_length() -> None:
    lengths = [synthesize(level).size for level in (1, 2, 3)]
    assert len(set(lengths)) == 3
    assert wav_bytes(1) != wav_bytes(2) != wav_bytes(3)


def test_tones_start_and_end_silently() -> None:
    for level in (1, 2, 3):
        samples = synthesize(level)
        assert abs(samples[0]) < 0.05
        assert abs(samples[-1]) < 0.05  # no click at the end


def test_volume_rises_with_the_level_and_stays_in_range() -> None:
    volumes = [effective_volume(level, 0.7) for level in (1, 2, 3)]
    assert volumes == sorted(volumes)
    assert all(0.0 <= v <= 1.0 for v in volumes)
    assert effective_volume(3, 5.0) == 1.0
    assert effective_volume(1, -1.0) == 0.0


def _peak(data: bytes) -> int:
    with wave.open(io.BytesIO(data)) as wav:
        return int(np.abs(np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")).max())


def test_the_gain_is_baked_into_the_wav() -> None:
    loud, soft = _peak(wav_bytes(2, 1.0)), _peak(wav_bytes(2, 0.25))
    assert loud > 20000
    assert soft == pytest.approx(loud * 0.25, rel=0.05)
    assert wav_bytes(2, 0.0) != wav_bytes(2, 1.0)
    assert _peak(wav_bytes(2, 0.0)) == 0
    assert _peak(wav_bytes(2, 7.0)) == loud  # gain is capped at 1


def test_scale_wav_scales_16_bit_and_leaves_other_data_alone() -> None:
    original = wav_bytes(1, 1.0)
    assert _peak(scale_wav(original, 0.5)) == pytest.approx(_peak(original) * 0.5, rel=0.05)
    assert scale_wav(original, 1.0) == original
    assert scale_wav(b"not a wav file", 0.5) == b"not a wav file"
    eight_bit = io.BytesIO()
    with wave.open(eight_bit, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(1)
        wav.setframerate(8000)
        wav.writeframes(bytes([128, 200, 50] * 100))
    assert scale_wav(eight_bit.getvalue(), 0.5) == eight_bit.getvalue()


def test_playback_command_per_platform(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from habit_guard.alerts import sound

    monkeypatch.setattr(sound.shutil, "which", lambda name: f"/bin/{name}")
    assert build_command("darwin", Path("a.wav")) == ["/bin/afplay", "a.wav"]
    assert build_command("linux", Path("a.wav")) == ["/bin/paplay", "a.wav"]
    monkeypatch.setattr(
        sound.shutil, "which", lambda name: "/bin/aplay" if name == "aplay" else None
    )
    assert build_command("linux", Path("a.wav")) == ["/bin/aplay", "-q", "a.wav"]
    monkeypatch.setattr(sound.shutil, "which", lambda name: None)
    assert build_command("linux", Path("a.wav")) is None
    assert build_command("darwin", Path("a.wav")) is None


class FakeWinsound:
    SND_FILENAME = 1
    SND_ASYNC = 2
    SND_PURGE = 4

    def __init__(self) -> None:
        self.calls: list[tuple[object, int]] = []

    def PlaySound(self, sound, flags):  # type: ignore[no-untyped-def]
        self.calls.append((sound, flags))


def test_windows_playback_uses_winsound_with_the_volume_baked_in(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    from habit_guard.alerts import sound

    fake = FakeWinsound()
    monkeypatch.setitem(sys.modules, "winsound", fake)
    monkeypatch.setattr(sound.sys, "platform", "win32")
    player = SoundPlayer(tmp_path / "sounds")
    player.play(2, 0.7)
    ((played, flags),) = fake.calls
    assert flags == FakeWinsound.SND_FILENAME | FakeWinsound.SND_ASYNC
    path = Path(played)
    assert path.is_file()
    assert _peak(path.read_bytes()) == pytest.approx(_peak(wav_bytes(2, 0.56)), rel=0.06)
    player.play(2, 0.7)  # the same file is reused, not written again
    assert fake.calls[1][0] == played
    player.play(2, 0.1)  # another volume, another file
    assert fake.calls[2][0] != played
    player.stop()
    assert fake.calls[-1] == (None, FakeWinsound.SND_PURGE)


def test_custom_sound_file_is_used_and_scaled(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from habit_guard.alerts import sound

    fake = FakeWinsound()
    monkeypatch.setitem(sys.modules, "winsound", fake)
    monkeypatch.setattr(sound.sys, "platform", "win32")
    custom = tmp_path / "mine.wav"
    custom.write_bytes(wav_bytes(3, 1.0))
    player = SoundPlayer(tmp_path / "sounds")
    player.play(1, 1.0, str(custom))
    played = Path(fake.calls[0][0])
    assert played.name.startswith("custom-")
    assert _peak(played.read_bytes()) == pytest.approx(_peak(custom.read_bytes()) * 0.55, rel=0.06)
    # A missing custom file falls back to the built-in tone.
    player.play(1, 1.0, str(tmp_path / "gone.wav"))
    assert Path(fake.calls[1][0]).name.startswith("alarm-1-")


def test_command_line_playback_starts_the_player_and_replaces_it(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    from habit_guard.alerts import sound

    started: list[list[str]] = []

    class FakeProcess:
        def __init__(self, command, **kwargs):  # type: ignore[no-untyped-def]
            started.append(command)
            self.stopped = False

        def poll(self):  # type: ignore[no-untyped-def]
            return 0 if self.stopped else None

        def terminate(self) -> None:
            self.stopped = True

    monkeypatch.setattr(sound.sys, "platform", "linux")
    monkeypatch.setattr(
        sound.shutil, "which", lambda name: "/bin/paplay" if name == "paplay" else None
    )
    monkeypatch.setattr(sound.subprocess, "Popen", FakeProcess)
    player = SoundPlayer(tmp_path)
    player.play(3, 1.0)
    first = player._process
    assert started[0][0] == "/bin/paplay"
    assert started[0][1].endswith("alarm-3-100.wav")
    player.play(3, 1.0)
    assert first is not None
    assert first.stopped  # the previous sound is cut off, not layered
    player.stop()
    assert player._process is None


def test_no_player_is_a_quiet_no(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from habit_guard.alerts import sound

    monkeypatch.setattr(sound.sys, "platform", "linux")
    monkeypatch.setattr(sound.shutil, "which", lambda name: None)
    player = SoundPlayer(tmp_path)
    player.play(2, 0.7)
    player.play(2, 0.7)
    assert player._process is None


# ------------------------------------------------------------------------------- speech
def test_speech_text_is_cleaned() -> None:
    assert speech.clean_text("  Elini\x00 indir\n ") == "Elini indir"
    assert len(speech.clean_text("x" * 1000)) == speech.MAX_CHARS


def test_speech_command_carries_text_in_the_environment_on_windows(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        speech.shutil,
        "which",
        lambda name: "C:/ps/powershell.exe" if name == "powershell" else None,
    )
    built = speech.build_command("win32", "x'; Remove-Item -Recurse C:\\ #", "tr")
    assert built is not None
    command, env = built
    assert "Remove-Item" not in " ".join(command)  # text never reaches the command line
    assert env[speech.TEXT_ENV].startswith("x'; Remove-Item")
    assert env[speech.LANG_ENV] == "tr-TR"
    assert "-NoProfile" in command


def test_speech_command_on_other_systems(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(speech.shutil, "which", lambda name: f"/usr/bin/{name}")
    mac = speech.build_command("darwin", "-rm hands down", "en")
    assert mac is not None
    assert mac[0] == ["/usr/bin/say", "--", "-rm hands down"]  # "--": text is never an option
    linux = speech.build_command("linux", "hands down", "en")
    assert linux is not None
    assert linux[0][0] == "/usr/bin/spd-say"


def test_speech_without_a_voice_or_text_is_a_quiet_no(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(speech.shutil, "which", lambda name: None)
    assert speech.build_command("linux", "hands down", "en") is None
    assert speech.build_command("darwin", "hands down", "en") is None
    assert speech.build_command("win32", "hands down", "en") is None
    assert speech.build_command("linux", "   ", "en") is None


# ------------------------------------------------------------------------------- manager
class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def play(self, level, volume, custom_file=""):  # type: ignore[no-untyped-def]
        self.calls.append(("play", (level, volume, custom_file)))

    def say(self, text, language):  # type: ignore[no-untyped-def]
        self.calls.append(("say", (text, language)))
        return True

    def show(self, style, level, message):  # type: ignore[no-untyped-def]
        self.calls.append(("show", (style, level, message)))

    def hide(self):  # type: ignore[no-untyped-def]
        self.calls.append(("hide", ()))

    def stop(self):  # type: ignore[no-untyped-def]
        self.calls.append(("stop", ()))

    def notify(self, title, body):  # type: ignore[no-untyped-def]
        self.calls.append(("notify", (title, body)))


def make_manager(settings: Settings | None = None) -> tuple[AlertManager, Recorder]:
    rec = Recorder()
    manager = AlertManager(
        settings or Settings(), sound=rec, speech=rec, curtain=rec, notify=rec.notify
    )
    return manager, rec


def names(rec: Recorder) -> list[str]:
    return [name for name, _ in rec.calls]


def test_first_alarm_uses_everything_that_is_on() -> None:
    i18n.set_language("en")
    settings = Settings()
    settings.alerts.speech = True
    manager, rec = make_manager(settings)
    manager.fire(Habit.NAIL_BITING, 1, first=True)
    assert sorted(names(rec)) == ["notify", "play", "say", "show"]
    title, body = next(args for name, args in rec.calls if name == "notify")
    assert title == "Hands down!"
    assert body == "Nail biting detected"


def test_escalation_does_not_repeat_the_notification() -> None:
    manager, rec = make_manager()
    manager.fire(Habit.NAIL_BITING, 2, first=False)
    assert "notify" not in names(rec)
    assert ("show", ("dim", 2, i18n.tr("alert.title"))) in rec.calls


def test_every_output_can_be_switched_off() -> None:
    settings = Settings()
    settings.alerts.sound = False
    settings.alerts.curtain = False
    settings.alerts.notification = False
    settings.alerts.speech = False
    manager, rec = make_manager(settings)
    manager.fire(Habit.MUSTACHE, 3, first=True)
    assert rec.calls == []


def test_speech_uses_the_custom_phrase_and_language() -> None:
    i18n.set_language("tr")
    settings = Settings()
    settings.alerts.speech = True
    settings.alerts.speech_text = "Dur bakalım"
    manager, rec = make_manager(settings)
    manager.fire(Habit.NAIL_BITING, 1, first=True)
    assert ("say", ("Dur bakalım", "tr")) in rec.calls
    i18n.set_language("en")


def test_curtain_stays_until_the_last_raised_habit_is_cleared() -> None:
    manager, rec = make_manager()
    manager.fire(Habit.NAIL_BITING, 1, first=True)
    manager.fire(Habit.MUSTACHE, 1, first=True)
    rec.calls.clear()
    manager.clear(Habit.NAIL_BITING)
    assert rec.calls == []  # mustache pulling is still going on
    manager.clear(Habit.MUSTACHE)
    assert names(rec) == ["hide", "stop"]


def test_clear_all_always_calms_everything() -> None:
    manager, rec = make_manager()
    manager.fire(Habit.NAIL_BITING, 1, first=True)
    rec.calls.clear()
    manager.clear()
    assert names(rec) == ["hide", "stop"]


# --------------------------------------------------------------------------------- i18n
def test_every_string_exists_in_every_language() -> None:
    assert i18n.missing_translations() == []


def test_placeholders_match_between_languages() -> None:
    import re

    for key in i18n.all_keys():
        found = {
            lang: set(re.findall(r"{(\w+)}", i18n._STRINGS[key][lang])) for lang in i18n.LANGUAGES
        }
        assert found["en"] == found["tr"], key


def test_translation_lookup_and_fallbacks() -> None:
    i18n.set_language("tr")
    assert i18n.tr("alert.title") == "Elini indir!"
    assert i18n.tr("no.such.key") == "no.such.key"
    assert i18n.set_language("klingon") == "en"
    assert i18n.tr("alert.title") == "Hands down!"
    assert i18n.set_language("auto") in i18n.LANGUAGES


def test_every_habit_has_names() -> None:
    for habit in Habit:
        assert i18n.habit_name(habit) != f"habit.{habit.value}"
        assert i18n.habit_short(habit) != f"habit.{habit.value}.short"


@pytest.mark.parametrize(
    ("seconds", "expected"), [(30, "30 s"), (125, "2 min"), (7500, "2 h 05 min")]
)
def test_duration_formatting(seconds: int, expected: str) -> None:
    i18n.set_language("en")
    assert i18n.format_duration(seconds) == expected
