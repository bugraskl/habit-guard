#!/usr/bin/env python3
"""Render the interface screenshots for the README and the website, in English and Turkish.

The windows are the real ones (``habit_guard.ui``), drawn offscreen with demo data. The camera
picture in the preview is an *illustration* drawn here, never a photograph, so no real face is in
the repository. Output: ``assets/screenshots/<lang>/<name>.png`` and ``assets/hero.png``.

Run it on a machine with the Segoe UI font (Windows) or a similar system UI font; the screenshots
are committed, so CI does not run this script.

Usage::

    python scripts/make_screenshots.py
"""

from __future__ import annotations

import itertools
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

# Qt settings must be in place before Qt is first imported.
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_SCALE_FACTOR"] = "2"  # twice the pixels, for sharp pictures
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
os.environ["HABIT_GUARD_HOME"] = tempfile.mkdtemp(prefix="habit-guard-shots-")

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QBrush,
    QColor,
    QFont,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer  # noqa: E402
from PySide6.QtWidgets import QApplication, QTabWidget, QWidget  # noqa: E402

from habit_guard import i18n  # noqa: E402
from habit_guard.alerts.curtain import CurtainWindow  # noqa: E402
from habit_guard.config import Settings  # noqa: E402
from habit_guard.stats import Stats  # noqa: E402
from habit_guard.types import FaceInfo, Habit, HandInfo, Observation  # noqa: E402
from habit_guard.ui.icons import IconState, pixmap  # noqa: E402
from habit_guard.ui.preview import PreviewWindow  # noqa: E402
from habit_guard.ui.settings_dialog import SettingsDialog  # noqa: E402
from habit_guard.ui.stats_dialog import StatsDialog  # noqa: E402
from habit_guard.ui.tray import Tray  # noqa: E402
from habit_guard.zones import FaceFrame, ZoneSpec, build_zones, evaluate  # noqa: E402

OUT = REPO_ROOT / "assets" / "screenshots"
SCALE = 2  # device pixels per logical pixel in the framed windows
TODAY = date(2026, 10, 2)  # a Friday: the weekday labels of the statistics chart


# ------------------------------------------------------------------------------- framing
def framed(content: QPixmap, title: str, *, chrome: bool = True) -> QImage:
    """``content`` in a window frame (a title bar and a soft shadow), on a transparent ground."""
    dpr = content.devicePixelRatio()
    w, h = content.width() / dpr, content.height() / dpr
    pad, bar = 2.0, (36.0 if chrome else 0.0)
    img = QImage(
        round((w + 2 * pad) * SCALE),
        round((h + bar + 2 * pad) * SCALE),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.scale(SCALE, SCALE)
    body = QRectF(pad, pad, w, h + bar)
    radius = 10.0 if chrome else 6.0
    clip = QPainterPath()
    clip.addRoundedRect(body, radius, radius)
    p.save()
    p.setClipPath(clip)
    p.fillRect(body, QColor("#f7f8fa"))
    if chrome:
        p.fillRect(QRectF(pad, pad, w, bar), QColor("#eef1f5"))
        p.drawPixmap(
            QRectF(pad + 12, pad + 10, 16, 16), pixmap(IconState.ACTIVE, 64), QRectF(0, 0, 64, 64)
        )
        font = QFont(QGuiApplication.font())
        font.setPointSizeF(9.0)
        p.setFont(font)
        p.setPen(QColor("#2b3340"))
        p.drawText(QRectF(pad + 36, pad, w - 150, bar), int(Qt.AlignmentFlag.AlignVCenter), title)
        pen = QPen(QColor("#4a5360"), 1.2)
        p.setPen(pen)
        cx = pad + w - 22
        cy = pad + bar / 2
        p.drawLine(QPointF(cx - 5, cy - 5), QPointF(cx + 5, cy + 5))  # close
        p.drawLine(QPointF(cx - 5, cy + 5), QPointF(cx + 5, cy - 5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(cx - 46 - 5, cy - 5, 10, 10))  # maximise
        p.drawLine(QPointF(cx - 92 - 5, cy), QPointF(cx - 92 + 5, cy))  # minimise
    p.drawPixmap(QPointF(pad, pad + bar), content)
    p.restore()
    p.setPen(QPen(QColor(120, 130, 145, 120), 0.8))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(body, radius, radius)
    p.end()
    return img


def shot(widget: QWidget, title: str, *, size: tuple[int, int] | None = None) -> QImage:
    if size is not None:
        widget.resize(*size)
    widget.show()
    QApplication.processEvents()
    return framed(widget.grab(), title)


# ----------------------------------------------------------------------------- the scene
def _skin(p: QPainter, color: str = "#f0c7a0", edge: str = "#c99a74") -> None:
    p.setBrush(QColor(color))
    p.setPen(QPen(QColor(edge), 2))


def illustrated_scene(face: FaceInfo, d: float, hand: np.ndarray, hand_len: float) -> np.ndarray:
    """A 640x480 cartoon of a person with a hand at the mouth, as a BGR picture."""
    img = QImage(640, 480, QImage.Format.Format_RGB888)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    sky = QLinearGradient(0, 0, 0, 480)
    sky.setColorAt(0, QColor("#c9d6e6"))
    sky.setColorAt(1, QColor("#e9eef4"))
    p.fillRect(0, 0, 640, 480, QBrush(sky))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#f6f9fc"))
    p.drawRoundedRect(QRectF(30, 40, 130, 190), 6, 6)  # a window
    p.setBrush(QColor("#b9c7d9"))
    p.drawRect(QRectF(92, 40, 6, 190))
    p.drawRect(QRectF(30, 130, 130, 6))
    cx = (face.left_eye[0] + face.right_eye[0]) / 2
    ey = face.left_eye[1]
    # shoulders and neck
    p.setBrush(QColor("#5a7ca8"))
    shoulders = QPainterPath()
    shoulders.moveTo(60, 480)
    shoulders.cubicTo(70, 420, 170, 400, cx - 70, 395)
    shoulders.lineTo(cx + 70, 395)
    shoulders.cubicTo(cx + 150, 400, 570, 420, 580, 480)
    shoulders.closeSubpath()
    p.drawPath(shoulders)
    _skin(p, "#e8b992", "#c99a74")
    p.drawRoundedRect(QRectF(cx - 36, ey + 1.45 * d, 72, 90), 14, 14)
    # hair behind the head, the head, the ears
    head_c = QPointF(cx, ey + 0.55 * d)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#4b3a30"))
    p.drawEllipse(QPointF(cx, head_c.y() - 0.12 * d), 1.34 * d, 1.92 * d)
    _skin(p)
    for side in (-1, 1):
        p.drawEllipse(QPointF(cx + side * 1.22 * d, ey + 0.35 * d), 0.16 * d, 0.3 * d)
    p.drawEllipse(head_c, 1.25 * d, 1.85 * d)
    fringe = QPainterPath()
    fringe.addEllipse(head_c, 1.25 * d, 1.85 * d)
    cut = QPainterPath()
    cut.addRect(QRectF(cx - 2 * d, head_c.y() - 2.2 * d, 4 * d, 1.28 * d))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#4b3a30"))
    p.drawPath(fringe.intersected(cut))
    # eyes, brows, nose, mouth
    for fx, side in ((face.left_eye[0], -1), (face.right_eye[0], 1)):
        p.setPen(QPen(QColor("#33241b"), 1.5))
        p.setBrush(QColor("white"))
        p.drawEllipse(QPointF(fx, ey), 0.23 * d, 0.115 * d)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#33241b"))
        p.drawEllipse(QPointF(fx + side * 0.02 * d, ey), 0.075 * d, 0.075 * d)
        p.setPen(QPen(QColor("#33241b"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        brow = QPainterPath(QPointF(fx - 0.28 * d, ey - 0.26 * d))
        brow.quadTo(QPointF(fx, ey - 0.42 * d), QPointF(fx + 0.28 * d, ey - 0.26 * d))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(brow)
    p.setPen(QPen(QColor("#b07a55"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    nx, ny = face.nose
    nose = QPainterPath(QPointF(nx, ey + 0.15 * d))
    nose.quadTo(QPointF(nx - 0.18 * d, ny - 0.06 * d), QPointF(nx - 0.13 * d, ny))
    nose.quadTo(QPointF(nx, ny + 0.08 * d), QPointF(nx + 0.13 * d, ny))
    p.drawPath(nose)
    mx = (face.mouth_left[0] + face.mouth_right[0]) / 2
    my = face.mouth_left[1]
    p.setPen(QPen(QColor("#a5483f"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    mouth = QPainterPath(QPointF(mx - 0.4 * d, my))
    mouth.quadTo(QPointF(mx, my + 0.14 * d), QPointF(mx + 0.4 * d, my))
    p.drawPath(mouth)
    # the hand, drawn over the face
    chains = ((5, 6, 7, 8), (9, 10, 11, 12), (13, 14, 15, 16), (17, 18, 19, 20), (1, 2, 3, 4))
    palm = QPainterPath(QPointF(*hand[0]))
    for i in (1, 5, 9, 13, 17):
        palm.lineTo(QPointF(*hand[i]))
    palm.closeSubpath()
    for width, color in ((hand_len * 0.27, "#c28a63"), (hand_len * 0.23, "#eab68e")):
        pen = QPen(
            QColor(color),
            width,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        p.setPen(pen)
        p.setBrush(QColor(color))
        p.drawPath(palm)
        for chain in chains:
            for a, b in itertools.pairwise(chain):
                p.drawLine(QPointF(*hand[a]), QPointF(*hand[b]))
    p.end()
    ptr = img.constBits()
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(img.height(), img.bytesPerLine())
    rgb = arr[:, : img.width() * 3].reshape(img.height(), img.width(), 3).copy()
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


#: A hand with the fingers together, in palm lengths: x to the right, y toward the fingertips.
HAND_TEMPLATE = np.array(
    [
        (0.00, 0.00),  # wrist
        (-0.28, 0.20), (-0.46, 0.42), (-0.56, 0.60), (-0.60, 0.74),  # thumb
        (-0.24, 0.98), (-0.25, 1.22), (-0.25, 1.38), (-0.25, 1.52),  # index
        (-0.02, 1.02), (-0.02, 1.30), (-0.02, 1.48), (-0.02, 1.64),  # middle
        (0.20, 0.97), (0.21, 1.20), (0.21, 1.36), (0.21, 1.48),  # ring
        (0.40, 0.88), (0.42, 1.06), (0.42, 1.17), (0.42, 1.27),  # pinky
    ]
)  # fmt: skip


def hand_to_the_mouth(mouth: tuple[float, float], d: float) -> tuple[np.ndarray, float]:
    """Landmarks of a hand coming up from the lower right with its fingertips at the mouth."""
    tip = np.array([mouth[0] + 0.06 * d, mouth[1] + 0.02 * d])
    wrist = np.array([mouth[0] + 1.15 * d, mouth[1] + 2.0 * d])
    direction = tip - wrist
    length = float(np.hypot(*direction)) / 1.64  # the middle fingertip is 1.64 palm lengths out
    up = direction / np.hypot(*direction)
    right = np.array([-up[1], up[0]])
    points = wrist + length * (HAND_TEMPLATE[:, :1] * right + HAND_TEMPLATE[:, 1:] * up)
    return points, length


def preview_shot() -> QImage:
    d = 84.0
    cx, ey = 320.0, 196.0

    def at(u: float, v: float) -> tuple[float, float]:
        return (cx + u * d, ey + v * d)

    face = FaceInfo(
        box=(*at(-1.0, -0.6), 2.0 * d, 2.9 * d),
        left_eye=at(-0.5, 0.0),
        right_eye=at(0.5, 0.0),
        nose=at(0.0, 0.75),
        mouth_left=at(-0.4, 1.3),
        mouth_right=at(0.4, 1.3),
        score=0.97,
    )
    landmarks, length = hand_to_the_mouth(at(0.0, 1.3), d)
    picture = illustrated_scene(face, d, landmarks, length)
    hand = HandInfo(landmarks=landmarks, score=0.96)
    frame = FaceFrame.from_face(face)
    assert frame is not None
    specs = {h: ZoneSpec(enabled=h is not Habit.FACE_TOUCH) for h in Habit}
    zones = build_zones(frame, specs)
    hits = evaluate(frame, zones, [hand])
    obs = Observation(
        ts=1.0, face=face, hands=(hand,), hand_near=True, frame_size=(640, 480), frame=picture
    )
    window = PreviewWindow()
    window.resize(680, 570)
    window.show()
    window.show_observation(obs, frame, zones, hits)
    QApplication.processEvents()
    return framed(window.grab(), i18n.tr("preview.title"))


# ----------------------------------------------------------------------------- the alarm
def _desktop(w: int, h: int) -> QImage:
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    bg = QLinearGradient(0, 0, w, h)
    bg.setColorAt(0, QColor("#1f4e5f"))
    bg.setColorAt(1, QColor("#2e3a6e"))
    p.fillRect(0, 0, w, h, QBrush(bg))
    win = QRectF(w * 0.12, h * 0.1, w * 0.76, h * 0.74)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#ffffff"))
    p.drawRoundedRect(win, 10, 10)
    p.setBrush(QColor("#2b579a"))
    p.drawRoundedRect(QRectF(win.left(), win.top(), win.width(), 42), 10, 10)
    p.drawRect(QRectF(win.left(), win.top() + 20, win.width(), 22))
    font = QFont(QGuiApplication.font())
    font.setPointSizeF(10.5)
    p.setFont(font)
    p.setPen(QColor("white"))
    p.drawText(
        QRectF(win.left() + 18, win.top(), 400, 42),
        int(Qt.AlignmentFlag.AlignVCenter),
        "Quarterly report.docx",
    )
    p.setPen(Qt.PenStyle.NoPen)
    rng = np.random.default_rng(4)
    y = win.top() + 90
    p.setBrush(QColor("#dfe3e8"))
    p.drawRoundedRect(QRectF(win.left() + 60, y - 28, win.width() * 0.4, 16), 4, 4)
    for _ in range(14):
        width = win.width() * float(rng.uniform(0.55, 0.88))
        p.setBrush(QColor("#e9ecf0"))
        p.drawRoundedRect(QRectF(win.left() + 60, y, width, 10), 4, 4)
        y += 28
    p.setBrush(QColor(20, 24, 32, 235))  # the taskbar
    p.drawRect(QRectF(0, h - 44, w, 44))
    p.setBrush(QColor("#4da3ff"))
    p.drawRoundedRect(QRectF(w / 2 - 70, h - 34, 24, 24), 5, 5)
    for i in range(4):
        p.setBrush(QColor(255, 255, 255, 60 + 20 * i))
        p.drawRoundedRect(QRectF(w / 2 - 28 + i * 34, h - 34, 24, 24), 5, 5)
    p.drawPixmap(
        QRectF(w - 150, h - 34, 24, 24), pixmap(IconState.ACTIVE, 64), QRectF(0, 0, 64, 64)
    )
    p.setPen(QColor("white"))
    p.drawText(QRectF(w - 110, h - 44, 100, 44), int(Qt.AlignmentFlag.AlignCenter), "15:42")
    p.end()
    return img


def alarm_shot(style: str, level: int) -> QImage:
    w, h = 1280, 720
    desktop = _desktop(w, h)
    curtain = CurtainWindow(QGuiApplication.primaryScreen())
    curtain.resize(w, h)
    curtain._style, curtain._level, curtain._message = style, level, i18n.tr("alert.title")
    curtain._pulse = 0.9
    p = QPainter(desktop)
    curtain.render(p, QPoint(0, 0))
    p.end()
    curtain.close()
    image = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    q = QPainter(image)
    q.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, w, h), 10, 10)
    q.setClipPath(clip)
    q.drawImage(0, 0, desktop)
    q.end()
    return image


# ------------------------------------------------------------------------------- the rest
def demo_stats() -> Stats:
    stats = Stats()
    nail = [6, 5, 7, 4, 5, 3, 4, 3, 2, 3, 2, 2, 1, 1]
    mustache = [2, 3, 1, 2, 1, 1, 2, 0, 1, 1, 0, 1, 0, 1]
    for back in range(14):
        day = TODAY - timedelta(days=13 - back)
        for _ in range(nail[back]):
            stats.record(Habit.NAIL_BITING, day)
        for _ in range(mustache[back]):
            stats.record(Habit.MUSTACHE, day)
    stats.clean_s = 2 * 3600 + 18 * 60
    stats.best_clean_s = 5 * 3600 + 40 * 60
    stats.watched_s = 41 * 3600 + 20 * 60
    return stats


def tray_shot() -> QImage:
    tray = Tray()
    tray.set_status(i18n.tr("tray.status.running"))
    tray.set_today(3)
    menu = tray._menu
    menu.ensurePolished()
    menu.popup(QPoint(0, 0))
    QApplication.processEvents()
    pm = menu.grab()
    menu.hide()
    return framed(pm, "", chrome=False)


def settings_shots(settings: Settings) -> dict[str, QImage]:
    out: dict[str, QImage] = {}
    dialog = SettingsDialog(settings)
    tabs = dialog.findChild(QTabWidget)
    assert tabs is not None
    dialog.show()
    QApplication.processEvents()
    height = dialog.sizeHint().height()
    for index, name in enumerate(("settings-habits", "settings-alarms", "settings-general")):
        tabs.setCurrentIndex(index)
        out[name] = shot(dialog, i18n.tr("settings.title"), size=(520, height))
    dialog.close()
    return out


def optimise(image: QImage, path: Path) -> None:
    """Save as PNG, squeezed with Pillow when it is installed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(path))
    try:
        from PIL import Image
    except ImportError:
        return
    with Image.open(path) as im:
        small = im.convert("RGBA").quantize(
            colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE
        )
        small.save(path, optimize=True)


def hero() -> None:
    svg = REPO_ROOT / "assets" / "hero.svg"
    if not svg.is_file():
        return
    renderer = QSvgRenderer(str(svg))
    image = QImage(1920, 960, QImage.Format.Format_ARGB32)
    image.fill(QColor("#0f1012"))
    p = QPainter(image)
    renderer.render(p)
    p.end()
    target = REPO_ROOT / "assets" / "hero.png"
    image.save(str(target))
    try:
        from PIL import Image

        with Image.open(target) as im:
            im.convert("RGB").quantize(
                colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
            ).save(target, optimize=True)
    except ImportError:
        pass


def icon_png() -> None:
    """``assets/icon.png`` (512 px, transparent), from the app icon SVG; favicons come from it."""
    svg = REPO_ROOT / "assets" / "icon.svg"
    renderer = QSvgRenderer(str(svg))
    image = QImage(512, 512, QImage.Format.Format_ARGB32)
    image.fill(0)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(p)
    p.end()
    image.save(str(REPO_ROOT / "assets" / "icon.png"))


def main() -> int:
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    for lang in ("en", "tr"):
        i18n.set_language(lang)
        folder = OUT / lang
        settings = Settings()
        settings.alerts.speech = True
        for name, image in settings_shots(settings).items():
            optimise(image, folder / f"{name}.png")
        optimise(preview_shot(), folder / "preview.png")
        stats_window = StatsDialog()
        stats_window.show()
        stats_window.refresh(demo_stats(), TODAY)
        QApplication.processEvents()
        optimise(framed(stats_window.grab(), i18n.tr("stats.title")), folder / "stats.png")
        stats_window.close()
        optimise(tray_shot(), folder / "tray.png")
        optimise(alarm_shot("dim", 1), folder / "alarm-dim.png")
        optimise(alarm_shot("flash", 2), folder / "alarm-flash.png")
        print(f"{lang}: {sorted(p.name for p in folder.glob('*.png'))}")
    hero()
    icon_png()
    total = sum(p.stat().st_size for p in OUT.rglob("*.png"))
    print(f"screenshots: {total / 1024:.0f} KiB in total")

    return 0


if __name__ == "__main__":
    sys.exit(main())
