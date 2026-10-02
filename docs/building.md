# Building and releasing

Habit Guard is packaged with [PyInstaller](https://pyinstaller.org/) into a self-contained folder,
then wrapped for each system: an Inno Setup installer and a portable ZIP on Windows, a disk image on
macOS, an AppImage and a tarball on Linux. The one definition of all this is
[`.github/workflows/build.yml`](../.github/workflows/build.yml); a pull request that touches the
packaging runs it (`bundle.yml`), and a tag runs it and publishes the result (`release.yml`).

## Build on your own machine

You need [uv](https://docs.astral.sh/uv/). From the repository root:

```bash
uv sync --group build
uv run python scripts/make_icons.py
uv run --group build pyinstaller packaging/pyinstaller/habit-guard.spec --noconfirm --clean
uv run python scripts/check_bundle.py dist/HabitGuard        # Windows
uv run python scripts/check_bundle.py "dist/Habit Guard.app" # macOS
uv run python scripts/check_bundle.py dist/habit-guard       # Linux
```

| System | Result | Programs |
|---|---|---|
| Windows | `dist/HabitGuard/` | `HabitGuard.exe` (tray app, no console), `habit-guard-cli.exe` |
| macOS | `dist/Habit Guard.app` | `Habit Guard` (tray app), `habit-guard-cli` next to it |
| Linux | `dist/habit-guard/` | `habit-guard`, which is both |

Try the frozen copy the way the CI does:

```bash
dist/HabitGuard/habit-guard-cli.exe --version
dist/HabitGuard/habit-guard-cli.exe selftest     # models, vision, tones and the Qt windows
dist/HabitGuard/habit-guard-cli.exe doctor
```

`selftest` runs in a scratch settings folder with Qt's offscreen platform, so it opens no window and
touches none of your files.

### Windows installer

[Inno Setup 6](https://jrsoftware.org/isinfo.php) is needed (`choco install innosetup`):

```powershell
iscc /DAppVersion=0.1.0 packaging\windows\installer.iss
```

It writes `dist\HabitGuard-0.1.0-windows-x64-setup.exe`: a per-user install (no administrator
rights) with optional start at sign-in and an optional `habit-guard` command on the user's PATH. An
upgrade asks a running Habit Guard to quit (`habit-guard-cli ctl quit`) and starts it again when the
upgrade is silent; the uninstaller removes the program, the PATH entry and, if you agree, your
settings. `installer.iss` is UTF-8 **with** a byte order mark and CRLF line endings: without the BOM
Inno Setup reads the Turkish messages in the wrong code page.

### macOS disk image

```bash
bash packaging/macos/make_dmg.sh --app "dist/Habit Guard.app" --version 0.1.0
```

The app is signed ad hoc by default, so macOS asks for the camera again after each update. Signing
every release with the same certificate keeps the permission: see the header of
[`make_dmg.sh`](../packaging/macos/make_dmg.sh) for how to provide one through the repository
secrets `MACOS_SIGNING_CERT_P12`, `MACOS_SIGNING_CERT_PASSWORD` and `MACOS_SIGNING_IDENTITY`.

### Linux AppImage and tarball

```bash
bash packaging/linux/build_appimage.sh --version 0.1.0
```

`appimagetool` and the AppImage runtime are downloaded once and checked against pinned SHA-256
values in the script, which refuses unverified downloads.

## What the bundle contains, and what it must not

`scripts/check_bundle.py` runs on every build and fails when the bundle

- contains a networking or telemetry component the app never uses (Qt's network and web modules,
  MediaPipe's runtime, an HTTP client package);
- lacks a model file, or the notice and licence texts that must travel with them;
- is far bigger than it should be (a normal bundle is about 190 MB; the limit is 400 MB).

The spec leaves out what nothing uses: the software OpenGL renderer, Qt's network and SVG libraries
and its translations, and on Windows OpenCV's FFmpeg. Camera capture uses DirectShow and Media
Foundation, so only *video file replay* (`--camera clip.mp4`) needs FFmpeg, and that works when
running from source.

## Releasing

1. Move the `## [Unreleased]` notes in `CHANGELOG.md` under a new `## [X.Y.Z] - YYYY-MM-DD`
   heading, and set `__version__` in `src/habit_guard/__init__.py` to `X.Y.Z`.
2. Commit, then tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. `release.yml` checks that the tag matches `__version__` and that the changelog has the section,
   builds and smoke-tests all packages, writes `SHA256SUMS.txt`, attests the build provenance
   (`gh attestation verify <file> --repo bugraskl/habit-guard`), publishes the release with the
   changelog section as its notes, and starts the website build so the download buttons point at
   the new files.

A version with letters in it (`0.2.0rc1`) is published as a pre-release and is not shown on the
website.
