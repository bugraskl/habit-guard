# The ten-second animation

`demo.mp4`, `demo.webp` and `demo-poster.jpg` show what Habit Guard does: a hand drifts to the
mouth, the camera finds it in the zone, the dwell ring fills, the alarm goes off and calms when the
hand is down. It is an **illustration made with an AI video tool, not a recording of the app** (the
skeleton hand is drawn for the picture; the program works with 21 hand points and keeps no picture).

| File | Used by | What it is |
|---|---|---|
| `demo.mp4` | the website (`assets/demo.mp4`), the link under the README animation | 1280x720, 10 s, H.264 with AAC sound, about 1.8 MB, "faststart" |
| `demo.webp` | both READMEs | the same animation, 800x450, 15 frames a second, endless loop, about 1 MB |
| `demo-poster.jpg` | the website, shown before the video plays | the frame at 5.4 s |

`scripts/build_site.py` copies `demo.mp4` and `demo-poster.jpg` into the site. `demo.webp` is only
for the READMEs and is not published on the site.

## Making them again from a new source clip

Needs `ffmpeg` and Pillow (`uv sync` installs the latter). With the clip saved as `source.mp4`:

```bash
# the website's video: the same pictures, container metadata removed, index at the front
ffmpeg -i source.mp4 -map_metadata -1 -c copy -movflags +faststart demo.mp4

# the poster
ffmpeg -ss 5.4 -i source.mp4 -frames:v 1 -q:v 3 demo-poster.jpg

# the README animation: frames first, then an animated WebP with explicit frame times
mkdir frames && ffmpeg -i source.mp4 -vf "fps=15,scale=800:-1:flags=lanczos" frames/f_%03d.png
```

```python
import glob
from PIL import Image

frames = [Image.open(f).convert("RGB") for f in sorted(glob.glob("frames/f_*.png"))]
frames[0].save(
    "demo.webp",
    save_all=True,
    append_images=frames[1:],
    duration=[67, 66, 67] * 50,
    loop=0,
    quality=55,
    method=6,
)
```

The Pillow route writes every frame's time explicitly (66 or 67 ms, 10 s in all, looping
forever), which a browser needs to play at the right speed. Keep the
files under 5 MB (video) and 2 MB (WebP): `tests/test_site.py` checks both.
