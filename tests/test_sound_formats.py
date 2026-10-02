"""Custom sounds in formats other than WAV (MP3 and similar), and the playing-state rules."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from habit_guard.alerts import sound
from habit_guard.alerts.sound import (
    AUDIO_EXTENSIONS,
    FILE_DIALOG_FILTER,
    MCI_ALIAS,
    SoundPlayer,
    build_command,
    is_wav,
)


def stepping_clock(step: float = 100.0):  # type: ignore[no-untyped-def]
    now = [0.0]

    def clock() -> float:
        now[0] += step
        return now[0]

    return clock


def test_the_file_dialog_offers_the_supported_formats() -> None:
    for extension in (".wav", ".mp3", ".m4a", ".ogg", ".flac"):
        assert extension in AUDIO_EXTENSIONS
        assert f"*{extension}" in FILE_DIALOG_FILTER
    assert FILE_DIALOG_FILTER.startswith("Audio (")


def test_wav_is_recognised_by_its_extension() -> None:
    assert is_wav(Path("a.wav"))
    assert is_wav(Path("A.WAV"))
    assert not is_wav(Path("a.mp3"))


# ------------------------------------------------------------------------------ macOS, Linux
def test_afplay_gets_the_volume_for_a_compressed_file(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(sound.shutil, "which", lambda name: f"/bin/{name}")
    assert build_command("darwin", Path("a.mp3"), 0.5) == ["/bin/afplay", "-v", "0.50", "a.mp3"]
    assert build_command("darwin", Path("a.wav")) == ["/bin/afplay", "a.wav"]  # volume is baked in


def test_linux_picks_a_decoder_for_compressed_files(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    only = {"mpv": "/usr/bin/mpv"}
    monkeypatch.setattr(sound.shutil, "which", only.get)
    command = build_command("linux", Path("a.ogg"), 0.4)
    assert command == ["/usr/bin/mpv", "--no-video", "--really-quiet", "--volume=40", "a.ogg"]
    only.clear()
    assert build_command("linux", Path("a.ogg"), 0.4) is None  # no decoder installed


def test_mpg123_is_only_used_for_mp3(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    only = {"mpg123": "/usr/bin/mpg123"}
    monkeypatch.setattr(sound.shutil, "which", only.get)
    mp3 = build_command("linux", Path("a.mp3"), 1.0)
    assert mp3 is not None
    assert mp3[0] == "/usr/bin/mpg123"
    assert build_command("linux", Path("a.m4a"), 1.0) is None


def test_a_compressed_custom_sound_is_played_by_a_process_and_not_restarted(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    started: list[list[str]] = []

    class Process:
        running = True

        def __init__(self, command, **kwargs):  # type: ignore[no-untyped-def]
            started.append(command)

        def poll(self):  # type: ignore[no-untyped-def]
            return None if Process.running else 0

        def terminate(self) -> None:
            Process.running = False

    monkeypatch.setattr(sound.sys, "platform", "linux")
    monkeypatch.setattr(
        sound.shutil, "which", lambda name: "/bin/ffplay" if name == "ffplay" else None
    )
    monkeypatch.setattr(sound.subprocess, "Popen", Process)
    song = tmp_path / "mine.mp3"
    song.write_bytes(b"ID3")
    player = SoundPlayer(tmp_path / "sounds", clock=stepping_clock())
    player.play(1, 0.8, str(song))
    assert len(started) == 1
    assert started[0][0] == "/bin/ffplay"
    assert started[0][-1] == str(song)
    assert "-volume" in started[0]
    player.play(1, 0.8, str(song))  # still playing, same level: left alone
    assert len(started) == 1
    player.play(2, 0.8, str(song))  # escalation: starts again
    assert len(started) == 2
    Process.running = False  # the sound has ended
    player.play(2, 0.8, str(song))
    assert len(started) == 3


# ----------------------------------------------------------------------------------- Windows
class FakeMci:
    """Records the commands sent to Windows' Media Control Interface."""

    def __init__(self, length_ms: int = 5000, fail_on: str = "") -> None:
        self.commands: list[str] = []
        self.length_ms = length_ms
        self.fail_on = fail_on

    def __call__(self, command: str) -> str:
        self.commands.append(command)
        if self.fail_on and command.startswith(self.fail_on):
            raise OSError("MCI says no")
        return str(self.length_ms) if command.startswith("status") else ""


def make_windows_player(tmp_path: Path, monkeypatch, mci: FakeMci) -> SoundPlayer:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(sound.sys, "platform", "win32")
    player = SoundPlayer(tmp_path / "sounds", clock=lambda: 1000.0)
    monkeypatch.setattr(player, "_mci", mci)
    return player


def test_windows_plays_an_mp3_through_mci_with_the_volume(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mci = FakeMci(length_ms=4200)
    player = make_windows_player(tmp_path, monkeypatch, mci)
    song = tmp_path / "ya bi elini indir.mp3"
    song.write_bytes(b"ID3")
    player.play(2, 0.5, str(song))
    assert mci.commands[0] == f'open "{song}" type mpegvideo alias {MCI_ALIAS}'
    assert f"setaudio {MCI_ALIAS} volume to 400" in mci.commands  # 0.5 x 0.8 of the level
    assert f"play {MCI_ALIAS}" in mci.commands
    assert player._busy_until == pytest.approx(1000.0 + 4.2)
    # Still playing, same level: no new open or play.
    before = len(mci.commands)
    player.play(2, 0.5, str(song))
    assert len(mci.commands) == before


def test_stopping_closes_the_mci_sound(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mci = FakeMci()
    player = make_windows_player(tmp_path, monkeypatch, mci)
    song = tmp_path / "x.mp3"
    song.write_bytes(b"ID3")
    player.play(1, 1.0, str(song))
    mci.commands.clear()
    monkeypatch.setitem(
        sys.modules,
        "winsound",
        type("W", (), {"SND_PURGE": 4, "PlaySound": staticmethod(lambda *a: None)}),
    )
    player.stop()
    assert mci.commands == [f"stop {MCI_ALIAS}", f"close {MCI_ALIAS}"]
    assert player._busy_until == 0.0


def test_a_failing_mci_open_is_logged_and_does_not_crash(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mci = FakeMci(fail_on="open")
    player = make_windows_player(tmp_path, monkeypatch, mci)
    song = tmp_path / "broken.mp3"
    song.write_bytes(b"not audio")
    player.play(1, 1.0, str(song))  # no exception
    assert not any(c.startswith("play") for c in mci.commands)


def test_a_missing_volume_control_does_not_stop_the_sound(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mci = FakeMci(fail_on="setaudio")
    player = make_windows_player(tmp_path, monkeypatch, mci)
    song = tmp_path / "x.m4a"
    song.write_bytes(b"x")
    player.play(1, 1.0, str(song))
    assert f"play {MCI_ALIAS}" in mci.commands


def test_a_file_name_with_a_double_quote_is_refused_not_injected(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    mci = FakeMci()
    player = make_windows_player(tmp_path, monkeypatch, mci)
    assert player._play_mci(Path('evil" alias x'), 1.0) == 0.0
    assert mci.commands == []


def test_a_missing_custom_file_falls_back_to_the_built_in_tone(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mci = FakeMci()
    player = make_windows_player(tmp_path, monkeypatch, mci)
    played: list[object] = []
    monkeypatch.setattr(player, "_play_windows", played.append)
    player.play(1, 1.0, str(tmp_path / "gone.mp3"))
    assert mci.commands == []
    assert played
    assert Path(str(played[0])).name.startswith("alarm-1-")


def test_mci_is_not_available_off_windows(tmp_path: Path) -> None:
    if sys.platform == "win32":
        pytest.skip("this is the Windows machine")
    with pytest.raises(OSError, match="Windows"):
        SoundPlayer(tmp_path)._mci("play x")
