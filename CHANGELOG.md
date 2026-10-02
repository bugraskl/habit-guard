# Changelog

All notable changes are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- A project website in English and Turkish with an interactive zone demo drawn from the real zone
  geometry, published to GitHub Pages.
- Interface screenshots in English and Turkish in the READMEs and on the website. The camera picture
  in the preview is an illustration, never a photograph.

### Fixed

- The alarm sound never played: Qt Multimedia is not part of PySide6-Essentials. Sound now uses what
  the system has (`winsound`, `afplay`, `paplay`, `pw-play`, `aplay` or `play`).
- A sound that is still playing is no longer restarted by another alarm of the same or a lower
  level, so a long custom sound no longer stutters when two habits raise their alarms together.
- Models failed to load from a folder with letters outside the Windows ANSI code page (for example
  a Turkish user name).
- A raised alarm is released when the camera is lost, the camera is released again when the preview
  is closed while paused, statistics are saved on logoff, and the camera thread survives driver
  errors.

## [0.1.0] - 2026-10-02

First public version (alpha).

### Added

- Watching for four habits: nail and finger biting, mustache, beard and lip picking, brow, lash and
  hair pulling, and face touching, each with its own zone, dwell time and zone size, and an
  optional wider area (chin and beard line, scalp).
- Face zones measured in eye distances, so they follow distance and head tilt.
- Hand finding and 21-point hand landmarks with OpenCV's DNN module (MediaPipe's models, ONNX
  conversions by the OpenCV Zoo), with hand following between pictures and face memory while a
  hand covers the face.
- A low-cost analysis cadence: motion gate, three speeds, three performance profiles.
- Alarms: sound (three escalating built-in tones or your own WAV), screen curtain (dim or pulsing
  red frame, click-through), spoken phrase with the system's offline voice, desktop notification.
- Escalation while the hand stays, and a timed pause from the tray (15 minutes, 1 hour, 3 hours).
- Statistics: daily counts per habit, 7-day chart, clean streak. Stored locally as plain numbers.
- Tray app with settings, camera preview and statistics windows, in English and Turkish.
- Command line: `doctor`, `bench`, `stats`, `reset`, `autostart`, `--camera`, `--config-dir`.
- Privacy scan (`scripts/check_privacy.py`) and model verification (`scripts/fetch_models.py`) in CI.

[Unreleased]: https://github.com/bugraskl/habit-guard/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/bugraskl/habit-guard/releases/tag/v0.1.0
