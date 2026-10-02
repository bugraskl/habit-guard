# Contributing

Thanks for helping make Habit Guard better. Reproducible bug reports, real-desk feedback (what
caused a false alarm, what a hand looked like when it was missed) and small focused pull requests
are the most valuable contributions.

## Ground rules

- **Privacy is a hard constraint.** No network code under `src/`, no camera pictures written to disk,
  no telemetry. `scripts/check_privacy.py` enforces this in CI; please don't work around it.
- **Degrade, never crash.** A missing camera, voice or tray is handled quietly and the app keeps
  running.
- **Pure logic stays pure.** `types`, `zones`, `engine/*`, `stats`, `config` and `i18n` import neither
  Qt nor OpenCV and take time as an argument, so they can be tested deterministically.
- **Measure performance claims.** If a change affects CPU use or latency, include `habit-guard bench`
  numbers before and after.
- **Both languages.** A new interface string needs an English and a Turkish text in
  `src/habit_guard/i18n.py` (a test fails otherwise).

## Development setup

You need [uv](https://docs.astral.sh/uv/) (it installs the right Python automatically).

```bash
git clone https://github.com/bugraskl/habit-guard.git
cd habit-guard
uv sync
uv run habit-guard             # start the tray app from source
uv run habit-guard doctor      # environment report
```

No webcam, or a repeatable test? Point the app at a video:

```bash
uv run habit-guard --camera path/to/clip.mp4
```

## Checks

Run everything CI runs before opening a pull request:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run mypy scripts
uv run python scripts/check_privacy.py
uv run python scripts/fetch_models.py --check
uv run pytest
```

The Qt tests run without a display (`QT_QPA_PLATFORM=offscreen`).

After changing the zone shapes in `src/habit_guard/zones.py`, regenerate the README picture with
`uv run python scripts/make_assets.py`.

## Reporting a problem

Open an issue with the output of `habit-guard doctor`. It contains versions, paths and the state of
the model files, and no pictures. **Never attach pictures or screenshots that show your face.**

For a false alarm or a missed hand it helps to say:

- which habit, and its dwell time and zone size,
- what you were doing (drinking, talking on the phone, resting your chin, ...),
- how the camera is placed, and the light,
- what **Camera preview** showed at that moment (describe it in words).

Security or privacy issues go through the private route described in [SECURITY.md](SECURITY.md).

## Pull requests

Small, focused changes with tests. Describe what you checked by hand. Keep the code in the style of
its surroundings: type hints, short docstrings that say *why*, line length 100.
