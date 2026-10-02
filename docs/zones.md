# Zones and tuning

![The zones on a face](../assets/zones.svg)

## How a zone works

Each habit has a **zone**: one or a few ellipses on the face. They are measured in **eye
distances**: the origin is the point between your eyes, one unit is the distance between them, and
the axes follow the line of your eyes. That is why the zones grow when you lean in, shrink when you
lean back and tilt with your head, and why the mouth and nose points of the face detector keep them
in the right place when you turn or nod.

A hand is "in" a zone when one of its **fingertips** (or, for plain face touching, the middle of the
palm) falls inside one of the zone's ellipses. The alarm goes off when that has been true for the
habit's **dwell time**, with short drop-outs forgiven (0.6 s).

Zones are kept from overlapping so that one movement raises one habit's alarm:

- the lips belong to *nail biting*; *mustache* is the band between the nose and the lips (when nail
  biting is turned off, the lips belong to *mustache*, since lip picking is part of it);
- *face touching* is whatever the other enabled habits do not own.

## Tuning

| Symptom | Try |
|---|---|
| Alarms while you drink, talk on the phone or rest your chin | A longer dwell time for that habit, a smaller zone size, or pause from the tray for a while. |
| The alarm comes too late | A shorter dwell time (down to 0.3 s), or the **Responsive** profile. |
| The alarm never comes although your hand is at your mouth | Open **Camera preview** and check that the hand is drawn with its yellow skeleton. If not, improve the light on your hand and raise the camera so both hands fit in the picture. A larger zone size helps when the zone sits a little off. |
| Brow or hair pulling is missed | Turn on the **wider area** for hair pulling (it adds the scalp) and enlarge the zone. |
| Glasses | Work fine. Strong reflections on the lenses can hide the eyes, which are used to place the zones; tilt the lamp or the camera. |

## The preview window

**Camera preview** in the tray menu shows your picture with the zones drawn on it. A zone fills in
when a fingertip is inside it; the face is boxed in white (dimmed when the face is remembered from
a moment ago because a hand covers it); each detected hand shows its 21 points, with the
fingertips in red. While the preview is open the analysis runs at full speed, so close it when you
are done. Nothing shown there is recorded.
