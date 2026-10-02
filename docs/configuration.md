# Configuration

Everything below can be changed in the settings window (tray icon → **Settings…**). The values are
kept in `settings.json` in the config folder; `habit-guard doctor` prints where that is. A missing
or damaged file is never an error: every value that cannot be read falls back to its default, and
numbers outside their range are clamped.

Use `--config-dir FOLDER` (or the environment variable `HABIT_GUARD_HOME`) to keep the settings, the
statistics and the generated alarm sounds in a folder of your choice, for example on a USB stick.

## General

| Key | Default | Values | What it does |
|---|---|---|---|
| `language` | `auto` | `auto`, `en`, `tr` | Interface language; `auto` follows the system. |
| `camera_index` | `0` | 0 to 16 | Which camera, as the operating system numbers them. `habit-guard doctor --probe-cameras` lists them. |
| `camera_api` | `auto` | `auto`, `dshow`, `msmf`, `any` | The capture interface. On Windows `dshow` opens fastest and `msmf` may let two programs share a camera; `auto` tries them in turn. |
| `profile` | `balanced` | `eco`, `balanced`, `responsive` | How often pictures are analysed, see below. |
| `onboarded` | `false` | `true`, `false` | Set once the first-run settings window has been shown. |

### Performance profiles

Seconds between analyses in each situation. "Idle" analyses only run when something near the face
moved, or at least every "forced" interval.

| Profile | No face in view | Face, hands away (idle) | At least every | A hand near the face |
|---|---:|---:|---:|---:|
| `eco` | 1.5 | 0.8 | 3.0 | 0.20 |
| `balanced` | 1.0 | 0.5 | 2.0 | 0.125 |
| `responsive` | 0.7 | 0.3 | 1.0 | 0.07 |

## Habits

One block per habit under `habits`: `nail_biting`, `mustache`, `hair_pulling`, `face_touch`.

| Key | Default | Range | What it does |
|---|---|---|---|
| `enabled` | on for `nail_biting` and `mustache`, off for the others | `true`, `false` | Watch for this habit. |
| `dwell_s` | `1.0` nail biting, `1.5` mustache, `1.5` hair pulling, `4.0` face touch | 0.3 to 30 | Seconds a hand must stay in the zone before the alarm goes off. |
| `zone_scale` | `1.0` | 0.5 to 2.0 | Zone size: below 1 is stricter, above 1 more generous. |
| `wide_area` | `false` | `true`, `false` | Mustache: also the chin and beard line. Hair pulling: also the scalp. No effect on the others. |

## Alarms

Under `alerts`.

| Key | Default | Range | What it does |
|---|---|---|---|
| `sound` | `true` | | Play an alarm sound. |
| `volume` | `0.7` | 0 to 1 | Volume. Each escalation level plays at 55 %, 80 % and 100 % of it. |
| `sound_file` | empty | a path | A WAV file to play instead of the built-in tones. |
| `notification` | `true` | | Desktop notification on the first alarm of each episode. |
| `curtain` | `true` | | Cover the screen until the hand is down. |
| `curtain_style` | `dim` | `dim`, `flash` | Darken the screen, or pulse a red frame. |
| `speech` | `false` | | Say a phrase with the system voice. |
| `speech_text` | empty | up to 200 characters | The phrase; empty uses a default in the interface language. |
| `escalate` | `true` | | Step up the alarm while the hand stays. Off means one alarm per episode. |
| `repeat_s` | `4.0` | 1 to 60 | Seconds between escalation steps. |

## Files

| File | Contents |
|---|---|
| `settings.json` | The settings above. |
| `stats.json` | Alarm counts per day and habit, the clean streak and the total watched time. Numbers only. |
| `sounds/` | The built-in alarm tones, generated on first use. Safe to delete. |
| `habit-guard.log` | A small rotating log, for bug reports. Contains no pictures. |
| `habit-guard.lock` | Keeps a second copy from starting. |

`habit-guard reset` deletes `settings.json` and `stats.json`.
