# Troubleshooting

Run `habit-guard doctor` first: it prints versions, paths, the state of the model files and the
settings, and it is what to paste into a bug report. `habit-guard doctor --probe-cameras` also
lists the cameras that open (it switches each camera on briefly).

## "Camera unavailable, trying again"

Another program holds the camera. Most webcams can be opened by one program at a time on Windows,
so a video call, a camera app or another tracker will block Habit Guard until it lets go. Habit
Guard retries every 3 seconds and starts by itself.

- Close the other program, or pause it, and the status turns to *Watching* within seconds.
- **Settings → General → Camera interface** changes how the camera is opened. On Windows,
  *Media Foundation* sometimes lets two programs share a camera that DirectShow does not.
- Wrong camera? Change **Camera number** (0 is the first one). `habit-guard doctor
  --probe-cameras` shows which numbers open.
- Windows: check *Settings → Privacy & security → Camera* and that desktop apps may use it.
- macOS: allow the terminal or the app to use the camera in *System Settings → Privacy &
  Security → Camera*.

## "Cannot start: Missing model file(s)"

The files in `src/habit_guard/vision/models` are damaged or missing. Run
`python scripts/fetch_models.py` from a source checkout; it downloads and verifies them.

## False alarms

See the table in [zones and tuning](zones.md#tuning). The short version: a longer dwell time, a
smaller zone and a pause from the tray while you eat or talk on the phone.

## It does not notice my hand

Open **Camera preview**. If the hand has no yellow skeleton, the hand is not being found: add light
on your hands, raise the camera so both hands fit in the picture when raised, and try again. A hand
seen edge-on (a flat palm turned sideways) is hard for any hand detector.

## There is no tray icon

Some Linux desktops hide tray icons (GNOME needs an extension). Habit Guard opens its settings
window when there is no tray. On Windows 11 the icon may sit behind the **^** on the taskbar.

## No sound, or no voice

- The sound uses Qt Multimedia; check the system volume and the output device.
- The voice needs `spd-say` or `espeak` on Linux. On Windows, *Settings → Time & language →
  Speech* controls which voices exist; the app picks one that matches the interface language when
  there is one.
- Use **Test the alarm** in the tray menu or the alarm settings to try your setup.

## The screen curtain blocks my clicks

It should not: it is created transparent to input. Some Wayland compositors ignore that. Turn the
curtain off in **Settings → Alarms** and use sound, voice or notification instead.

## Start fresh

`habit-guard reset` removes the settings and the statistics. The folder is shown by `habit-guard
doctor`.
