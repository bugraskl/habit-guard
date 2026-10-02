#!/usr/bin/env python3
"""Draw the README pictures from the real zone geometry.

``assets/zones.svg`` shows where each habit's zone sits on a face, drawn with
the same ellipses the app uses (``habit_guard.zones``), so the picture can
never drift away from the behaviour. ``assets/icon.svg`` is the app icon.

Usage::

    python scripts/make_assets.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from habit_guard.types import FaceInfo, Habit  # noqa: E402
from habit_guard.zones import Ellipse, FaceFrame, Zone, ZoneSpec, build_zones  # noqa: E402

ASSETS = REPO_ROOT / "assets"
COLORS = {
    Habit.NAIL_BITING: "#f08c00",
    Habit.MUSTACHE: "#1c9be6",
    Habit.HAIR_PULLING: "#9a5cf0",
    Habit.FACE_TOUCH: "#3fb36b",
}
LABELS = {
    Habit.NAIL_BITING: "Nail and finger biting",
    Habit.MUSTACHE: "Mustache, beard, lip picking",
    Habit.HAIR_PULLING: "Brow, lash, hair pulling",
    Habit.FACE_TOUCH: "Face touching, skin picking",
}
UNIT = 100.0  # pixels per face unit
ORIGIN = (300.0, 250.0)  # the point between the eyes
INK = "#3a2a20"
FONT = "Segoe UI, Helvetica, Arial, sans-serif"


def _frontal_face() -> FaceInfo:
    """A frontal face in picture pixels, with the proportions the tests use."""

    def at(u: float, v: float) -> tuple[float, float]:
        return (ORIGIN[0] + u * UNIT, ORIGIN[1] + v * UNIT)

    return FaceInfo(
        box=(*at(-1.0, -0.6), 2.0 * UNIT, 2.9 * UNIT),
        left_eye=at(-0.5, 0.0),
        right_eye=at(0.5, 0.0),
        nose=at(0.0, 0.75),
        mouth_left=at(-0.4, 1.3),
        mouth_right=at(0.4, 1.3),
    )


def _ellipse(frame: FaceFrame, e: Ellipse, color: str, *, dashed: bool, opacity: float) -> str:
    cx, cy = frame.to_image(e.cu, e.cv)
    dash = ' stroke-dasharray="7 5"' if dashed else ""
    return (
        f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{e.rx * UNIT:.1f}" ry="{e.ry * UNIT:.1f}" '
        f'fill="{color}" fill-opacity="{opacity}" stroke="{color}" stroke-width="2.5"{dash}/>'
    )


def _stroke(d: str, color: str, width: int) -> str:
    return (
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" '
        'stroke-linecap="round"/>'
    )


def _features(frame: FaceFrame) -> list[str]:
    """Eyes, brows, nose and mouth, drawn over the zones so the face stays readable."""
    out: list[str] = []
    for u in (-0.5, 0.5):
        x, y = frame.to_image(u, 0.0)
        out.append(
            f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="22" ry="11" fill="#fff" '
            f'stroke="{INK}" stroke-width="2"/>'
        )
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{INK}"/>')
        bx, by = frame.to_image(u, -0.3)
        brow = f"M {bx - 30:.1f} {by + 4:.1f} Q {bx:.1f} {by - 10:.1f} {bx + 30:.1f} {by + 4:.1f}"
        out.append(_stroke(brow, INK, 5))
    nx, ny = frame.to_image(0.0, 0.75)
    nose = (
        f"M {nx - 3:.1f} {ny - 48:.1f} Q {nx - 18:.1f} {ny - 5:.1f} {nx - 14:.1f} {ny:.1f} "
        f"Q {nx:.1f} {ny + 8:.1f} {nx + 14:.1f} {ny:.1f}"
    )
    out.append(_stroke(nose, "#a9744f", 3))
    mx, my = frame.to_image(0.0, 1.3)
    mouth = f"M {mx - 40:.1f} {my:.1f} Q {mx:.1f} {my + 16:.1f} {mx + 40:.1f} {my:.1f}"
    out.append(_stroke(mouth, "#a5483f", 5))
    return out


def _legend() -> list[str]:
    out = [f'<g font-family="{FONT}" font-size="19" fill="#26323d" transform="translate(0 60)">']
    out.append(
        '<text x="500" y="110" font-size="24" font-weight="700">Where each habit is watched</text>'
    )
    y = 165
    for habit in Habit:
        out.append(
            f'<rect x="500" y="{y - 18}" width="26" height="26" rx="6" fill="{COLORS[habit]}" '
            f'fill-opacity="0.35" stroke="{COLORS[habit]}" stroke-width="2.5"/>'
        )
        out.append(f'<text x="540" y="{y + 2}">{LABELS[habit]}</text>')
        y += 52
    out.append(
        '<rect x="500" y="372" width="26" height="26" rx="6" fill="none" stroke="#5b6773" '
        'stroke-width="2.5" stroke-dasharray="7 5"/>'
    )
    out.append('<text x="540" y="392">Wider area (optional)</text>')
    note = '<text x="500" y="{y}" font-size="16" fill="#5b6773">{text}</text>'
    out.append(note.format(y=450, text="A zone counts when a fingertip is inside it for"))
    out.append(note.format(y=474, text="longer than the dwell time. Sizes are adjustable."))
    out.append("</g>")
    return out


def _face_base() -> list[str]:
    """Neck, head and hair, in the diagram's own coordinates (no zones, no features)."""
    return [
        '<rect x="262" y="475" width="76" height="70" fill="#e9b992"/>',  # neck
        '<ellipse cx="300" cy="305" rx="125" ry="185" fill="#f2c9a5" stroke="#c99a74" '
        'stroke-width="3"/>',
        '<path d="M 178 160 C 215 60 385 60 422 160 C 400 130 350 108 300 108 C 250 108 200 '
        '130 178 160 Z" fill="#5b4a3f"/>',  # hair
    ]


def _face_group() -> list[str]:
    """The face with every zone drawn on it, in the diagram's own coordinates (about 0-640 high)."""
    frame = FaceFrame.from_face(_frontal_face())
    assert frame is not None
    narrow = {z.habit: z for z in build_zones(frame, dict.fromkeys(Habit, ZoneSpec()))}
    wide = {z.habit: z for z in build_zones(frame, dict.fromkeys(Habit, ZoneSpec(wide=True)))}
    parts = ['<g transform="translate(0 80)">', *_face_base()]
    face_touch: Zone = narrow[Habit.FACE_TOUCH]
    parts += [
        _ellipse(frame, e, COLORS[Habit.FACE_TOUCH], dashed=False, opacity=0.10)
        for e in face_touch.include
    ]
    for habit, zone in wide.items():  # the optional extras, dashed and faint
        extras = [e for e in zone.include if e not in narrow[habit].include]
        parts += [_ellipse(frame, e, COLORS[habit], dashed=True, opacity=0.08) for e in extras]
    for habit, zone in narrow.items():
        if habit is not Habit.FACE_TOUCH:
            parts += [
                _ellipse(frame, e, COLORS[habit], dashed=False, opacity=0.22) for e in zone.include
            ]
    parts += _features(frame)
    parts.append("</g>")
    return parts


#: Where a fingertip goes to "do" each habit, in face coordinates: the demo on the website.
DEMO_TARGETS = {
    Habit.NAIL_BITING: (0.0, 1.36),
    Habit.MUSTACHE: (0.0, 0.92),
    Habit.HAIR_PULLING: (-0.5, -0.3),
    Habit.FACE_TOUCH: (0.95, 0.6),
}


def demo_face() -> tuple[str, dict[str, tuple[float, float]]]:
    """The face for the website's interactive demo, and the fingertip target of each habit.

    Every zone is its own ``<g class="zone" data-habit=...>`` so a script can light it up; the
    coordinates are the diagram's own (the face is centred on x = 300).
    """
    frame = FaceFrame.from_face(_frontal_face())
    assert frame is not None
    zones = {z.habit: z for z in build_zones(frame, dict.fromkeys(Habit, ZoneSpec()))}
    parts = list(_face_base())
    for habit in (Habit.FACE_TOUCH, Habit.HAIR_PULLING, Habit.MUSTACHE, Habit.NAIL_BITING):
        ellipses = "".join(
            _ellipse(frame, e, "currentColor", dashed=False, opacity=1.0)
            for e in zones[habit].include
        )
        parts.append(
            f'<g class="zone zone-{habit.value}" data-habit="{habit.value}" '
            f'style="color:{COLORS[habit]}">{ellipses}</g>'
        )
    parts += _features(frame)
    targets = {h.value: frame.to_image(*uv) for h, uv in DEMO_TARGETS.items()}
    return "\n".join(parts), targets


def zones_svg() -> str:
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 860 640" role="img" '
        'aria-labelledby="t d">',
        '<title id="t">Habit Guard zones</title>',
        '<desc id="d">A face with the zone of each watched habit drawn over it: the mouth, the '
        "moustache and beard area, the brows and hairline, and the rest of the face.</desc>",
        '<rect width="860" height="640" rx="18" fill="#f4f6f8"/>',
        *_face_group(),
        *_legend(),
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


def hero_svg() -> str:
    """The social preview picture (1920 x 960): name, promise and the zones on a face."""
    colors = [COLORS[h] for h in Habit]
    bars = "".join(
        f'<rect x="{i * 480}" y="0" width="480" height="10" fill="{c}"/>'
        for i, c in enumerate(colors)
    )
    chips = []
    x = 120
    for text, width in (
        ("Offline", 190),
        ("Private", 190),
        ("Light on the CPU", 330),
        ("MIT", 120),
    ):
        chips.append(
            f'<rect x="{x}" y="716" width="{width}" height="60" rx="30" fill="#1c1d22" '
            'stroke="#3d4049" stroke-width="2"/>'
            f'<text x="{x + width / 2}" y="755" text-anchor="middle" font-size="28" '
            f'fill="#d9dbe0">{text}</text>'
        )
        x += width + 20
    return "\n".join(
        [
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 960" role="img" '
            'aria-label="Habit Guard">',
            '<rect width="1920" height="960" fill="#0f1012"/>',
            bars,
            '<circle cx="190" cy="230" r="70" fill="#0f9d8a"/>',
            '<g transform="translate(126 166) scale(1.0)">'
            '<g transform="scale(1)">'
            + "".join(
                f'<rect x="{x * 128:.1f}" y="{y * 128:.1f}" width="{w * 128:.1f}" '
                f'height="{h * 128:.1f}" rx="{r * 128:.1f}" fill="#fff"/>'
                for x, y, w, h, r in (
                    (0.30, 0.46, 0.40, 0.30, 0.08),
                    (0.30, 0.32, 0.085, 0.24, 0.04),
                    (0.405, 0.24, 0.085, 0.32, 0.04),
                    (0.51, 0.24, 0.085, 0.32, 0.04),
                    (0.615, 0.32, 0.085, 0.24, 0.04),
                )
            )
            + "</g></g>",
            f'<g font-family="{FONT}" fill="#f4f4f5">',
            '<text x="120" y="440" font-size="124" font-weight="700" letter-spacing="-2">'
            "Habit Guard</text>",
            '<text x="120" y="536" font-size="40" fill="#b9bbc2">Catches the hand on its way to '
            "your mouth,</text>",
            '<text x="120" y="592" font-size="40" fill="#b9bbc2">mustache, brows or hair, and '
            "nudges you to stop.</text>",
            *chips,
            "</g>",
            '<rect x="1090" y="70" width="640" height="820" rx="32" fill="#f4f6f8"/>',
            '<g transform="translate(1050 66) scale(1.2)">',
            *_face_group(),
            "</g>",
            "</svg>",
            "",
        ]
    )


def icon_svg() -> str:
    """The app icon, in the same shapes as ``ui/icons.py``."""
    s = 128.0

    def rect(x: float, y: float, w: float, h: float, rad: float, extra: str = "") -> str:
        return (
            f'<rect x="{x * s:.1f}" y="{y * s:.1f}" width="{w * s:.1f}" height="{h * s:.1f}" '
            f'rx="{rad * s:.1f}" fill="#fff"{extra}/>'
        )

    fingers = [
        rect(x, top, 0.085, 0.56 - top, 0.04)
        for x, top in ((0.30, 0.24), (0.405, 0.16), (0.51, 0.16), (0.615, 0.24))
    ]
    transform = f' transform="translate({0.31 * s:.1f} {0.62 * s:.1f}) rotate(-38)"'
    thumb = rect(-0.20, -0.045, 0.22, 0.09, 0.045, transform)
    return "\n".join(
        [
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" role="img" '
            'aria-label="Habit Guard">',
            '<circle cx="64" cy="64" r="60" fill="#0f9d8a"/>',
            rect(0.30, 0.46, 0.40, 0.30, 0.08),
            *fingers,
            thumb,
            "</svg>",
            "",
        ]
    )


def main() -> int:
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "zones.svg").write_text(zones_svg(), encoding="utf-8", newline="\n")
    (ASSETS / "icon.svg").write_text(icon_svg(), encoding="utf-8", newline="\n")
    (ASSETS / "hero.svg").write_text(hero_svg(), encoding="utf-8", newline="\n")
    print(f"wrote zones.svg, icon.svg and hero.svg in {ASSETS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
