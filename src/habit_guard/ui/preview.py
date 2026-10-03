"""The camera preview: your picture with the zones, the face and the hand points drawn on it.

It is the way to see what Habit Guard sees, to tune the zone sizes, and to
check that the camera is placed well. Nothing shown here is recorded; the
window only exists while it is open, and the camera analysis runs at full
speed only for that time.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..i18n import habit_name, tr
from ..types import FaceInfo, Habit, HandInfo, Observation
from ..zones import FaceFrame, Zone

HABIT_COLORS = {
    Habit.NAIL_BITING: QColor(255, 140, 0),
    Habit.MUSTACHE: QColor(0, 170, 255),
    Habit.HAIR_PULLING: QColor(170, 90, 255),
    Habit.FACE_TOUCH: QColor(80, 200, 120),
    Habit.CUSTOM_1: QColor(255, 90, 160),
    Habit.CUSTOM_2: QColor(0, 205, 205),
    Habit.CUSTOM_3: QColor(225, 195, 40),
}

#: The bones of a hand, as pairs of landmark indices.
HAND_BONES = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
)  # fmt: skip


def to_qimage(frame: np.ndarray) -> QImage:
    """A BGR camera picture as a QImage (copied, so the array may go away)."""
    h, w = frame.shape[:2]
    contiguous = np.ascontiguousarray(frame)
    return QImage(contiguous.data, w, h, contiguous.strides[0], QImage.Format.Format_BGR888).copy()


class PreviewCanvas(QWidget):
    """Paints the picture and its overlays, scaled to fit."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(480, 360)
        self._image: QImage | None = None
        self._face: FaceInfo | None = None
        self._hands: tuple[HandInfo, ...] = ()
        self._frame: FaceFrame | None = None
        self._zones: list[Zone] = []
        self._hits: dict[Habit, int] = {}
        self._held = False

    def show_observation(
        self,
        obs: Observation,
        frame: FaceFrame | None,
        zones: list[Zone],
        hits: dict[Habit, int],
    ) -> None:
        if obs.frame is not None:
            self._image = to_qimage(obs.frame)
        self._face, self._hands, self._held = obs.face, obs.hands, obs.face_held
        self._frame, self._zones, self._hits = frame, zones, hits
        self.update()

    def clear(self) -> None:
        self._image = None
        self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(24, 26, 30))
        if self._image is None:
            painter.setPen(QColor(200, 200, 200))
            painter.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter), tr("preview.waiting"))
            return
        iw, ih = self._image.width(), self._image.height()
        scale = min(self.width() / iw, self.height() / ih)
        ox, oy = (self.width() - iw * scale) / 2, (self.height() - ih * scale) / 2
        painter.drawImage(QRectF(ox, oy, iw * scale, ih * scale), self._image)

        def pt(x: float, y: float) -> QPointF:
            return QPointF(ox + x * scale, oy + y * scale)

        if self._frame is not None:
            for zone in self._zones:
                color = HABIT_COLORS[zone.habit]
                hit = self._hits.get(zone.habit, 0) > 0
                fill = QColor(color)
                fill.setAlpha(110 if hit else 38)
                painter.setPen(QPen(color, 3 if hit else 1.5))
                painter.setBrush(fill)
                for ellipse in zone.include:
                    poly = QPolygonF([pt(x, y) for x, y in self._frame.ellipse_polygon(ellipse)])
                    painter.drawPolygon(poly)
        if self._face is not None:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255, 120 if self._held else 200), 1.5))
            x, y, w, h = self._face.box
            painter.drawRect(QRectF(pt(x, y), pt(x + w, y + h)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 230))
            for p in (
                self._face.left_eye,
                self._face.right_eye,
                self._face.nose,
                self._face.mouth_left,
                self._face.mouth_right,
            ):
                painter.drawEllipse(pt(*p), 3.0, 3.0)
        for hand in self._hands:
            painter.setPen(QPen(QColor(255, 255, 0, 200), 2))
            for a, b in HAND_BONES:
                painter.drawLine(pt(*hand.landmarks[a]), pt(*hand.landmarks[b]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 60, 60))
            for tip in hand.fingertips():
                painter.drawEllipse(pt(*tip), 4.5, 4.5)


class PreviewWindow(QWidget):
    """A window around the canvas, with a status line."""

    closed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(tr("preview.title"))
        self.canvas = PreviewCanvas()
        self.status = QLabel(tr("preview.waiting"))
        hint = QLabel(tr("preview.hint"))
        hint.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(self.status)
        layout.addWidget(hint)

    def show_observation(
        self,
        obs: Observation,
        frame: FaceFrame | None,
        zones: list[Zone],
        hits: dict[Habit, int],
    ) -> None:
        self.canvas.show_observation(obs, frame, zones, hits)
        parts = [tr("preview.face") if obs.face is not None else tr("preview.no_face")]
        parts.append(tr("preview.hands", n=len(obs.hands)))
        active = [habit_name(h) for h, n in hits.items() if n > 0]
        if active:
            parts.append(" · ".join(active))
        self.status.setText("   |   ".join(parts))

    def closeEvent(self, event: object) -> None:
        self.canvas.clear()
        self.closed.emit()
        super().closeEvent(event)  # type: ignore[arg-type]
