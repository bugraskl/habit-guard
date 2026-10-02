# Architecture

```
camera thread                              Qt thread
─────────────                              ─────────
Camera ──grab/retrieve──▶ Analyzer ──Observation──▶ Controller
 (vision/camera.py)        (vision/analyzer.py)      (app.py)
                             │ MotionGate                 │ zones.evaluate
                             │ FaceDetector (YuNet)       │ HabitEngine.update
                             │ HandTracker                │ AlertManager.fire / clear
                             └ FaceMemory                 │ Stats.record
                                                          └ tray, preview, statistics windows
```

## Layers and what may import what

| Layer | Modules | Imports Qt / OpenCV? |
|---|---|---|
| Pure logic | `types`, `zones`, `engine/decision`, `stats`, `config`, `i18n` | no / no |
| Vision | `vision/*` | no / yes |
| Alarms | `alerts/sound` (tones), `alerts/speech`, `alerts/manager` | no |
| Qt | `alerts/curtain`, `alerts/sound.SoundPlayer`, `ui/*`, `app` | yes |

Pure logic takes time as an argument and never reads a clock, so the decision engine, the zones and
the statistics are tested with hand-made numbers. The camera thread and the Qt thread meet at one
place: the pipeline calls a function with an `Observation`, and the application connects that to a
Qt signal, so everything that touches windows runs on the Qt thread.

## One analysis step (`vision/analyzer.py`)

1. **Gate.** With a face known, no hand near it and nothing moved in the area around the face (a
   32×24 greyscale thumbnail compared with the last analysed one), the picture is skipped. A step
   runs anyway every "forced" interval, so a hand that is already resting near the face is found.
2. **Face.** YuNet on a copy no wider than 320 px: box, eyes, nose tip, mouth corners.
3. **Hands.** Around the face (the face box widened by 1.2 box sizes) the palm detector looks for
   palms; each palm becomes a rotated crop that the landmark network turns into 21 points. Once a
   hand is found, the next picture's crop comes from its previous landmarks and the palm detector
   is not run again until no hand is followed (or once a second, to look for a second hand).
4. **Face memory.** A hand over the mouth is exactly when the face detector tends to lose the face.
   While a hand is in view, the last face stays valid for 2 s; with no hand in view a lost face
   means the person left.
5. **Cadence.** Next picture in 1 s with nobody there, in 0.5 s with a face and hands away, in
   0.125 s (balanced) while a hand is near the face, and for 1.5 s after it was last near. See
   [configuration](configuration.md#performance-profiles).

A *new* hand must score 0.7 on the landmark network's presence output to be believed; a hand that is
already followed is kept down to 0.5. Skin-coloured shoulders, knees and beards produce palm
candidates around 0.5, a real hand scores 0.9 and more.

The camera is *grabbed* at the camera's pace (cheap) and only *retrieved* (decoded) when an analysis
is due, so the 30 pictures a second cost almost nothing.

## Zones (`zones.py`)

See [zones and tuning](zones.md). A `FaceFrame` turns pixels into face coordinates (origin between
the eyes, unit = eye distance, `u` along the eye line, `v` toward the chin); a `Zone` is a set of
ellipses in those coordinates minus the ellipses of habits that own the area.

## Decision (`engine/decision.py`)

One *run* per habit. A run starts when a fingertip is in the zone and goes on while it is there, with
gaps shorter than `gap_s` (0.6 s) forgiven. At the dwell time the engine emits `Trigger(level=1,
first=True)`. While the run goes on it emits a `Trigger` with a higher level every `repeat_s`, up to
level 3, and keeps repeating at the top. When the run ends it emits `Release`, which calms the
screen curtain and the sound. A per-habit cooldown (5 s) keeps rapid in-and-out from raising a new
alarm each time.

## Alarms (`alerts/`)

`AlertManager` is the policy: the notification fires on the first alarm of a run only; the curtain,
the sound and the voice fire on every `Trigger`, with the level choosing the intensity (the tone, the
volume, the darkness). The four outputs are passed in as small objects, so the policy is tested with
recorders. Tones are synthesised with numpy into WAV files on first use. Speech runs the system's
own voice as a short-lived child process, with the phrase passed in an environment variable and never
on a command line.

## Tests

`pytest` covers the pure logic with synthetic faces and hands, the vision geometry (anchors,
rotated crops, round trips), the analyzer with fake detectors, the camera thread with a fake camera,
the Qt windows and the controller offscreen (`QT_QPA_PLATFORM=offscreen`), the privacy scan and the
model manifest. Model-dependent tests are skipped when the model files are missing.
