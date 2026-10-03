# Changelog

All notable changes are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-10-03

Custom zones, a setup wizard that checks the camera, package managers, and a fix for a
finger in the mouth.

### Added

- A ten-second animation that shows what Habit Guard does, on the website (English and
  Turkish) and in both READMEs. It is an illustration, not a screen recording.
- Custom zones: **Settings → Custom zones** has three zones you draw yourself, for a habit that
  is not on the list (ears, cheeks, neck, lips ...). Each has a name, a dwell time and an optional
  mirror image; you drag the shape on a schematic face, or use the arrow keys.
- A setup wizard on the first run (and **Setup wizard…** in the tray menu, `habit-guard ctl
  wizard`): check the camera, choose the habits, choose the alarms. The camera page shows a
  checklist (face found, light, distance, room for the hands, a hand seen) and says in words what
  to change. No real alarm is raised while it is open.
- The camera preview shows the same advice in a line under the picture.
- Package managers: the repository is a Scoop bucket (`bucket/`) and a Homebrew tap (`Casks/`),
  an Arch `habit-guard-bin` PKGBUILD is in `packaging/aur/`, and winget manifests are made for
  every release. `scripts/make_package_manifests.py` writes them from the release's checksums, and
  the packages workflow installs each release with Scoop, Homebrew and `makepkg` and runs it
  (see [package managers](docs/package-managers.md)).
- Optional Windows code signing through SignPath in the release build (off until its settings
  are made, then the programs and the installer are signed and their signatures checked).
- `actionlint` checks the workflows in CI.

### Changed

- The first run opens the setup wizard instead of the settings window (the settings are one click
  away in the tray menu, and the wizard can be opened again from there).
- The Turkish website and `README.tr.md` were rewritten in natural Turkish.

### Fixed

- A finger in the mouth was not detected when the hand model put the hidden fingertips on the
  palm, below the chin. A hand lying on the mouth now counts for nail biting when at least three
  knuckles or finger joints of one hand are on the (widened) mouth zone and no fingertip is in any
  zone. It can be turned off per habit (`hidden_tips`).
- Numbers that are not numbers (NaN, infinity) in `settings.json` fall back to the default, like
  any other value that cannot be used.

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
- A low-cost analysis cadence: motion gate, three speeds, three performance profiles. Measured
  0.34 % of a 16-thread machine with the face in view and the hands away.
- Alarms: sound (three escalating built-in tones, or your own WAV, MP3 or similar file), screen
  curtain (dim or pulsing red frame, click-through), spoken phrase with the system's offline voice,
  desktop notification.
- Escalation while the hand stays, and a timed pause from the tray (15 minutes, 1 hour, 3 hours).
- Statistics: daily counts per habit, 7-day chart, clean streak. Stored locally as plain numbers.
- Tray app with settings, camera preview and statistics windows, in English and Turkish.
- Installers: a per-user Windows installer (optional PATH entry and start at sign-in, upgrades over
  a running app, English and Turkish) and a portable ZIP, a macOS disk image (Apple silicon) and a
  Linux AppImage and tarball, built and smoke-tested by CI, with checksums and build-provenance
  attestations.
- Command line: `doctor`, `bench`, `stats`, `reset`, `autostart`, `selftest`, `ctl` (control a
  running app: status, pause, resume, toggle, test, settings, preview, stats, quit), `--camera`,
  `--config-dir`. `ctl` talks through small files in the settings folder, not a socket.
- A project website in English and Turkish with an interactive zone demo drawn from the real zone
  geometry, and interface screenshots in both languages in the READMEs and on the site. The camera
  picture in the preview is an illustration, never a photograph.
- Privacy scan (`scripts/check_privacy.py`), bundle check (`scripts/check_bundle.py`) and model
  verification (`scripts/fetch_models.py`) in CI.

### Fixed

- Models failed to load from a folder with letters outside the Windows ANSI code page (for example
  a Turkish user name): they are now read in Python and handed to OpenCV as bytes.
- The alarm sound never played in early builds: Qt Multimedia is not part of PySide6-Essentials.
  Sound now uses what the system has (`winsound`, `afplay`, `paplay`, `pw-play`, `aplay` or `play`).
- A sound that is still playing is no longer restarted by another alarm of the same or a lower
  level, so a long custom sound does not stutter when two habits raise their alarms together.
- A raised alarm is released when the camera is lost, the camera is released again when the preview
  is closed while paused, statistics are saved on logoff, and the camera thread survives driver
  errors.

[Unreleased]: https://github.com/bugraskl/habit-guard/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/bugraskl/habit-guard/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/bugraskl/habit-guard/releases/tag/v0.1.0
