"""Speaking the alarm phrase with the operating system's own offline voice.

Nothing is installed or downloaded: Windows has SAPI (through PowerShell),
macOS has ``say``, and Linux uses ``spd-say`` or ``espeak`` when present. The
voice runs as a short-lived child process, so it costs nothing while idle.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys

log = logging.getLogger(__name__)

TEXT_ENV = "HABIT_GUARD_SPEECH_TEXT"
LANG_ENV = "HABIT_GUARD_SPEECH_LANG"
MAX_CHARS = 200
_CULTURES = {"tr": "tr-TR", "en": "en-US"}

# The phrase and the language travel in environment variables, never in the command line,
# so no text a user types can be read as PowerShell code.
_POWERSHELL = (
    "Add-Type -AssemblyName System.Speech;"
    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
    "try { $s.SelectVoiceByHints('NotSet', 'NotSet', 0, "
    f"[cultureinfo]$env:{LANG_ENV}) }} catch {{}};"
    f"$s.Speak($env:{TEXT_ENV})"
)


def clean_text(text: str) -> str:
    """The phrase without control characters, at a sane length."""
    return "".join(ch for ch in text if ch.isprintable()).strip()[:MAX_CHARS]


def build_command(
    platform: str, text: str, language: str
) -> tuple[list[str], dict[str, str]] | None:
    """The command and extra environment that speak ``text``, or ``None`` if nothing can."""
    text = clean_text(text)
    if not text:
        return None
    env = {TEXT_ENV: text, LANG_ENV: _CULTURES.get(language, "en-US")}
    if platform == "win32":
        shell = shutil.which("powershell") or shutil.which("pwsh")
        if shell is None:
            return None
        return [shell, "-NoProfile", "-NonInteractive", "-Command", _POWERSHELL], env
    if platform == "darwin":
        say = shutil.which("say")
        return ([say, "--", text], {}) if say else None
    for tool in ("spd-say", "espeak-ng", "espeak"):
        found = shutil.which(tool)
        if found:
            if tool == "spd-say":
                return [found, "--wait", "--", text], {}
            return [found, "--", text], {}
    return None


class Speaker:
    """Speaks one phrase at a time; a request while it is still talking is dropped."""

    def __init__(self) -> None:
        self._process: subprocess.Popen[bytes] | None = None

    @property
    def busy(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def say(self, text: str, language: str) -> bool:
        """Start speaking; ``False`` when nothing could be started."""
        if self.busy:
            return False
        built = build_command(sys.platform, text, language)
        if built is None:
            return False
        command, extra_env = built
        # On Windows the voice's PowerShell must not flash a console window.
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self._process = subprocess.Popen(
                command,
                env={**os.environ, **extra_env},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
        except OSError:
            log.exception("could not start the speech command")
            return False
        return True

    def stop(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
        self._process = None
