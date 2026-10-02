"""The app icon: a raised hand on a coloured disc, drawn in code so no image files ship."""

from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap


class IconState(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ALERT = "alert"
    PROBLEM = "problem"


_COLORS = {
    IconState.ACTIVE: QColor("#0f9d8a"),
    IconState.PAUSED: QColor("#7b8794"),
    IconState.ALERT: QColor("#e03131"),
    IconState.PROBLEM: QColor("#e8890c"),
}


def _paint_hand(p: QPainter, s: float) -> None:
    p.setBrush(QColor("white"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(0.30 * s, 0.46 * s, 0.40 * s, 0.30 * s), 0.08 * s, 0.08 * s)  # palm
    for x, top in ((0.30, 0.24), (0.405, 0.16), (0.51, 0.16), (0.615, 0.24)):  # four fingers
        p.drawRoundedRect(QRectF(x * s, top * s, 0.085 * s, (0.56 - top) * s), 0.04 * s, 0.04 * s)
    p.save()  # thumb
    p.translate(0.31 * s, 0.62 * s)
    p.rotate(-38)
    p.drawRoundedRect(QRectF(-0.20 * s, -0.045 * s, 0.22 * s, 0.09 * s), 0.045 * s, 0.045 * s)
    p.restore()


def pixmap(state: IconState, size: int = 64) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(_COLORS[state])
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(0.03 * size, 0.03 * size, 0.94 * size, 0.94 * size))
    _paint_hand(p, size)
    if state is IconState.PAUSED:  # two bars
        p.setBrush(QColor("white"))
        p.drawRoundedRect(QRectF(0.62 * size, 0.60 * size, 0.07 * size, 0.26 * size), 2, 2)
        p.drawRoundedRect(QRectF(0.74 * size, 0.60 * size, 0.07 * size, 0.26 * size), 2, 2)
    p.end()
    return pm


def icon(state: IconState) -> QIcon:
    out = QIcon()
    for size in (16, 24, 32, 48, 64, 128):
        out.addPixmap(pixmap(state, size))
    return out
