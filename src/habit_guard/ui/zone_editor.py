"""Draw a custom zone: a schematic face on which one ellipse is moved and resized.

The face is a drawing in *face coordinates* (the same ones the zones use: the origin is the middle
between the eyes, one unit is the eye distance, ``v`` points toward the chin), so what is drawn
here lands on the same place of the real face, whatever its size or tilt. The built-in zones are
shown faintly for orientation.

The mouse moves the ellipse (drag inside it) and resizes it (drag a handle on its edge); the arrow
keys move it and Shift with the arrow keys resize it, so it can be done without a mouse. When the
zone is mirrored, the other half follows and can be grabbed as well.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..config import MIRROR_MIN_OFFSET, CustomZone
from ..types import BUILT_IN_HABITS
from ..zones import Ellipse, FaceFrame, ZoneSpec, build_zones
from .preview import HABIT_COLORS

#: The drawing's extent, in face coordinates.
U_RANGE = (-2.2, 2.2)
V_RANGE = (-2.6, 3.4)
#: Smallest and largest radius, in face units.
RADIUS_RANGE = (0.1, 2.0)
#: One key press moves or resizes by this much.
KEY_STEP = 0.05
HANDLE_PX = 5.0
GRAB_PX = 11.0


def schematic_frame() -> FaceFrame:
    """The face coordinate system of an average, frontal face, one pixel per face unit."""
    return FaceFrame(
        origin=(0.0, 0.0),
        axis=(1.0, 0.0),
        down=(0.0, 1.0),
        unit=1.0,
        nose=(0.0, 0.75),
        mouth=(0.0, 1.3),
        mouth_width=0.8,
    )


@dataclass(frozen=True, slots=True)
class _Grab:
    """What the mouse took hold of: the shape, or one of its four handles."""

    kind: str  # "move", "rx" or "ry"
    #: -1 when it is the mirrored half (the drag then works in mirrored coordinates).
    side: int
    #: Where inside the shape it was taken, so that it does not jump to the pointer.
    offset: tuple[float, float] = (0.0, 0.0)


class ZoneEditor(QWidget):
    """Shows one custom zone and lets the user change it. ``changed`` fires after every edit."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(300, 400)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self._zone = CustomZone()
        self._color = QColor(255, 90, 160)
        self._grab: _Grab | None = None
        frame = schematic_frame()
        specs = {h: ZoneSpec() for h in BUILT_IN_HABITS}
        self._background = [(z.habit, z.include) for z in build_zones(frame, specs)]

    # ----------------------------------------------------------------------------- the zone
    def set_zone(self, zone: CustomZone, color: QColor) -> None:
        """Edit ``zone`` (the object itself is changed) and draw it in ``color``."""
        self._zone = zone
        self._color = color
        self._grab = None
        self.update()

    def zone(self) -> CustomZone:
        return self._zone

    # ------------------------------------------------------------------------- coordinates
    def _scale(self) -> tuple[float, float, float]:
        """Pixels per face unit, and the pixel position of ``(U_RANGE[0], V_RANGE[0])``."""
        width = U_RANGE[1] - U_RANGE[0]
        height = V_RANGE[1] - V_RANGE[0]
        scale = min(self.width() / width, self.height() / height)
        ox = (self.width() - width * scale) / 2.0
        oy = (self.height() - height * scale) / 2.0
        return scale, ox, oy

    def face_to_canvas(self, u: float, v: float) -> QPointF:
        scale, ox, oy = self._scale()
        return QPointF(ox + (u - U_RANGE[0]) * scale, oy + (v - V_RANGE[0]) * scale)

    def canvas_to_face(self, point: QPointF) -> tuple[float, float]:
        scale, ox, oy = self._scale()
        return ((point.x() - ox) / scale + U_RANGE[0], (point.y() - oy) / scale + V_RANGE[0])

    def _ellipse_rect(self, e: Ellipse) -> QRectF:
        top_left = self.face_to_canvas(e.cu - e.rx, e.cv - e.ry)
        bottom_right = self.face_to_canvas(e.cu + e.rx, e.cv + e.ry)
        return QRectF(top_left, bottom_right)

    def _main(self) -> Ellipse:
        z = self._zone
        return Ellipse(z.cu, z.cv, z.rx, z.ry)

    def _mirror_shown(self) -> bool:
        return self._zone.mirror and abs(self._zone.cu) >= MIRROR_MIN_OFFSET

    def handle_positions(self, side: int = 1) -> dict[str, QPointF]:
        """Where the four handles are on the canvas, for the shape (``side`` 1) or its mirror."""
        z = self._zone
        cu = z.cu * side
        return {
            "rx+": self.face_to_canvas(cu + z.rx, z.cv),
            "rx-": self.face_to_canvas(cu - z.rx, z.cv),
            "ry+": self.face_to_canvas(cu, z.cv + z.ry),
            "ry-": self.face_to_canvas(cu, z.cv - z.ry),
        }

    # -------------------------------------------------------------------------------- paint
    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.base())
        self._paint_face(painter)
        self._paint_background_zones(painter)
        self._paint_zone(painter)
        if self.hasFocus():
            painter.setPen(QPen(palette.highlight().color(), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.rect().adjusted(1, 1, -1, -1))

    def _paint_face(self, painter: QPainter) -> None:
        line = self.palette().mid().color()
        painter.setPen(QPen(line, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self._ellipse_rect(Ellipse(0.0, 2.9, 0.55, 0.55)))  # neck
        head = QColor(line)
        head.setAlpha(40)
        painter.setBrush(head)
        painter.drawEllipse(self._ellipse_rect(Ellipse(0.0, 0.15, 1.25, 2.15)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for side in (-1, 1):  # ears, eyes, brows
            painter.drawEllipse(self._ellipse_rect(Ellipse(side * 1.3, 0.35, 0.1, 0.3)))
            painter.drawEllipse(self._ellipse_rect(Ellipse(side * 0.5, 0.0, 0.2, 0.09)))
            painter.drawLine(
                self.face_to_canvas(side * 0.5 - 0.3, -0.32),
                self.face_to_canvas(side * 0.5 + 0.3, -0.32),
            )
        painter.drawLine(self.face_to_canvas(0.0, 0.25), self.face_to_canvas(0.0, 0.75))
        painter.drawLine(self.face_to_canvas(-0.4, 1.3), self.face_to_canvas(0.4, 1.3))

    def _paint_background_zones(self, painter: QPainter) -> None:
        for habit, ellipses in self._background:
            color = QColor(HABIT_COLORS[habit])
            color.setAlpha(110)
            pen = QPen(color, 1.2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for ellipse in ellipses:
                painter.drawEllipse(self._ellipse_rect(ellipse))

    def _paint_zone(self, painter: QPainter) -> None:
        z = self._zone
        fill = QColor(self._color)
        fill.setAlpha(70)
        painter.setPen(QPen(self._color, 2.2))
        painter.setBrush(fill)
        painter.drawEllipse(self._ellipse_rect(self._main()))
        sides = [1]
        if self._mirror_shown():
            sides.append(-1)
            mirrored = QColor(self._color)
            painter.setPen(QPen(mirrored, 2.2, Qt.PenStyle.DashLine))
            painter.drawEllipse(self._ellipse_rect(Ellipse(-z.cu, z.cv, z.rx, z.ry)))
        painter.setPen(QPen(self._color.darker(140), 1.5))
        painter.setBrush(QColor(255, 255, 255))
        for side in sides:
            for point in self.handle_positions(side).values():
                painter.drawRect(
                    QRectF(
                        point.x() - HANDLE_PX, point.y() - HANDLE_PX, 2 * HANDLE_PX, 2 * HANDLE_PX
                    )
                )

    # ------------------------------------------------------------------------------- mouse
    def _grab_at(self, point: QPointF) -> _Grab | None:
        """What lies under ``point``: a handle first, then the inside of the shape."""
        sides = [1, -1] if self._mirror_shown() else [1]
        for side in sides:
            for name, handle in self.handle_positions(side).items():
                if (
                    abs(handle.x() - point.x()) <= GRAB_PX
                    and abs(handle.y() - point.y()) <= GRAB_PX
                ):
                    return _Grab(name[:2], side)
        u, v = self.canvas_to_face(point)
        for side in sides:
            su = u * side  # the mirrored half is edited in mirrored coordinates
            if self._main().contains(su, v):
                return _Grab("move", side, (su - self._zone.cu, v - self._zone.cv))
        return None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self._grab = self._grab_at(event.position())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._grab is None:
            self._update_cursor(event.position())
            return
        u, v = self.canvas_to_face(event.position())
        grab, z = self._grab, self._zone
        u *= grab.side
        if grab.kind == "move":
            z.cu = _clamp(u - grab.offset[0], *U_RANGE)
            z.cv = _clamp(v - grab.offset[1], *V_RANGE)
        elif grab.kind == "rx":
            z.rx = _clamp(abs(u - z.cu), *RADIUS_RANGE)
        else:
            z.ry = _clamp(abs(v - z.cv), *RADIUS_RANGE)
        self._edited()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._grab = None
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self.unsetCursor()
        super().leaveEvent(event)

    def _update_cursor(self, point: QPointF) -> None:
        grab = self._grab_at(point)
        if grab is None:
            self.unsetCursor()
        elif grab.kind == "move":
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        elif grab.kind == "rx":
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeVerCursor)

    # ----------------------------------------------------------------------------- keyboard
    def keyPressEvent(self, event: QKeyEvent) -> None:
        steps = {
            int(Qt.Key.Key_Left): (-1, 0),
            int(Qt.Key.Key_Right): (1, 0),
            int(Qt.Key.Key_Up): (0, -1),
            int(Qt.Key.Key_Down): (0, 1),
        }
        step = steps.get(event.key())
        if step is None:
            super().keyPressEvent(event)
            return
        z = self._zone
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            z.rx = _clamp(z.rx + step[0] * KEY_STEP, *RADIUS_RANGE)
            z.ry = _clamp(z.ry + step[1] * KEY_STEP, *RADIUS_RANGE)
        else:
            z.cu = _clamp(z.cu + step[0] * KEY_STEP, *U_RANGE)
            z.cv = _clamp(z.cv + step[1] * KEY_STEP, *V_RANGE)
        self._edited()

    # ---------------------------------------------------------------------------------- misc
    def _edited(self) -> None:
        z = self._zone
        z.cu, z.cv, z.rx, z.ry = (round(x, 3) for x in (z.cu, z.cv, z.rx, z.ry))
        self.update()
        self.changed.emit()

    def reset_to(self, default: CustomZone) -> None:
        """Put the shape back to ``default`` (the name and the mirror choice are kept)."""
        z = self._zone
        z.cu, z.cv, z.rx, z.ry = default.cu, default.cv, default.rx, default.ry
        self._edited()


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)
