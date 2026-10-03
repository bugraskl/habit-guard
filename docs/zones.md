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
- *face touching* is whatever the other enabled habits do not own;
- a [custom zone](#custom-zones) you drew wins over all of them, and an earlier custom zone
  wins over a later one.

## Custom zones

The built-in habits cover the usual places. For anything else (picking at the ears, the cheeks or
the neck, biting the lip, a place of your own) **Settings → Custom zones** has three zones you draw
yourself.

1. Pick a zone (1 to 3), tick **Watch for this** and give it a **name**, for example `ear picking`.
   The name is what the notification, the statistics and the preview call it.
2. Drag the shape on the drawing of the face to move it, and the square handles on its edge to
   resize it. The arrow keys move the shape and Shift with the arrow keys resizes it. The built-in
   zones are shown as dashed outlines so you can see where they are.
3. Tick **Also on the other side of the face** for ears or cheeks: the mirror image follows and
   can be dragged as well.
4. Set the **alarm time** (the dwell time) and press **Save**. **Camera preview** then shows your
   zone on your own face, in its own colour, so you can check it.

The drawing is of an average face, but the zones are measured in eye distances like the built-in
ones, so they land on the same place of *your* face and follow it when you lean in or tilt your
head. A custom zone counts fingertips only. Where it overlaps a built-in zone, yours wins and the
built-in zone steps around it.

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
