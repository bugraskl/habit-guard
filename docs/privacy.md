# Privacy

Habit Guard looks at your face and hands through your camera. This page says exactly what happens
to those pictures and how you can check it.

## What happens to a camera picture

1. The camera driver hands a picture to the app.
2. The picture is analysed in memory: where the face is, where the hands are.
3. The picture is dropped. Only the *numbers* from it (face points, hand points) are used for the
   next few moments, in memory, and then forgotten.

Nothing is written to disk and nothing is sent anywhere. The statistics file holds counters, such
as "3 alarms on 2 October", and nothing else about you.

## What the app does and does not do

| | |
|---|---|
| Network access | None. No telemetry, no accounts, no update check, no crash reports. |
| Pictures on disk | Never. No screenshots, no recordings, no thumbnails. |
| Files it writes | `settings.json`, `stats.json`, the generated alarm tones and a small log, in your config folder (see [configuration](configuration.md#files)). |
| The camera | Opened only while tracking runs. Pausing releases it, and the webcam light goes out. |
| The screen | Never read. The curtain draws *over* the screen; it does not look at it. |
| Keyboard and mouse | Never read. |

## How you can check it

The promises are enforced by `scripts/check_privacy.py`, which CI runs on every change. It walks the
source under `src/habit_guard` and fails when it finds

- an import of a networking library (sockets, HTTP clients, Qt's network and web modules, ...), or
- a call to OpenCV's image and video writers (`imwrite`, `imencode`, `VideoWriter`), or a `save` on
  a Qt picture.

The scan is syntactic: it catches accidents and makes a review easy, but it is not a sandbox. The
code is small enough to read. The output of `habit-guard doctor` contains versions and paths (with
your home folder shown as `~`) and no pictures, so it is safe to paste into a bug report.

## Why not the MediaPipe runtime

Google's `mediapipe` Python package bundles a usage-logging client that uploads to Google servers.
Habit Guard uses only the *weights* of MediaPipe's hand networks (converted to ONNX by the OpenCV
Zoo) and runs them with OpenCV's DNN module, so the runtime, and its logging, is not in the app.
Licences and provenance of every model file, with the SHA-256 checksums that
`scripts/fetch_models.py --check` verifies, are in
[`NOTICE.md`](../src/habit_guard/vision/models/NOTICE.md).

## Voice alarms

The voice uses your operating system's own offline text-to-speech: SAPI through PowerShell on
Windows, `say` on macOS, `spd-say` or `espeak` on Linux. The phrase is passed to it through an
environment variable, never spliced into a command, and nothing leaves the computer.
